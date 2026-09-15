"""Delinquency classification, status-change detection, and the sourcing task queue."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

import pandas as pd

_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_JSON = os.path.join(_DIR, "crm_status_snapshot.json")
TASKS_JSON = os.path.join(_DIR, "crm_tasks.json")

AR_THRESHOLD = 2_000.0
DAYS_COLLECTIONS = 30
DAYS_LEGAL = 90

# Days back used to seed the review baseline the very first time the app runs, so
# the action-items view reflects "what changed since the last review" rather than
# starting empty.
BASELINE_LOOKBACK_DAYS = 14

CURRENT = "Current"
COLLECTIONS = "Collections"
LEGAL = "Legal"

RANK = {CURRENT: 0, COLLECTIONS: 1, LEGAL: 2}

ROW_FILL = {
    CURRENT: "",
    COLLECTIONS: "background-color: #FDF6E0;",
    LEGAL: "background-color: #FAECEA;",
}

TASK_COLLECTION = "Source collection agency"
TASK_LEGAL = "Source legal counsel"

TASK_FOR_STATUS = {COLLECTIONS: TASK_COLLECTION, LEGAL: TASK_LEGAL}


def classify(receivables: float, days: int) -> str:
    if receivables > AR_THRESHOLD and days > DAYS_LEGAL:
        return LEGAL
    if receivables > AR_THRESHOLD and days > DAYS_COLLECTIONS:
        return COLLECTIONS
    return CURRENT


def enrich(df: pd.DataFrame, as_of: date | None = None) -> pd.DataFrame:
    """Add derived delinquency columns to a raw customer frame."""
    as_of = as_of or date.today()
    out = df.copy()
    last_work = pd.to_datetime(out["last_work_date"]).dt.date
    out["days_since_work"] = [(as_of - d).days for d in last_work]
    out["status"] = [
        classify(r, d)
        for r, d in zip(out["receivables_outstanding"], out["days_since_work"])
    ]
    out["refer_to_collections"] = out["status"] == COLLECTIONS
    out["refer_to_legal"] = out["status"] == LEGAL
    return out


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

DISPLAY_COLUMNS = {
    "customer_id": "ID",
    "customer": "Customer",
    "phone": "Phone",
    "email": "Email",
    "city": "City",
    "country": "Country",
    "region": "Region",
    "business_area": "Business Area",
    "times_hired": "Times Hired",
    "last_work_date": "Last Work Completed",
    "days_since_work": "Days",
    "cash_received": "Cash Received (EUR)",
    "receivables_outstanding": "Receivables (EUR)",
    "status": "Status",
    "refer_to_collections": "Refer: Collections",
    "refer_to_legal": "Refer: Legal",
}


def style_table(df: pd.DataFrame):
    """Render the enriched frame as a Styler with rows tinted by delinquency status."""
    source = df.reset_index(drop=True)
    view = source[list(DISPLAY_COLUMNS)].rename(columns=DISPLAY_COLUMNS).copy()
    view["Refer: Collections"] = view["Refer: Collections"].map({True: "✓", False: ""})
    view["Refer: Legal"] = view["Refer: Legal"].map({True: "✓", False: ""})

    def _row_style(row):
        return [ROW_FILL[source.at[row.name, "status"]]] * len(row)

    return (
        view.style.apply(_row_style, axis=1)
        .format({"Cash Received (EUR)": "{:,.0f}", "Receivables (EUR)": "{:,.0f}"})
    )


# ---------------------------------------------------------------------------
# Status-change detection
# ---------------------------------------------------------------------------


def load_snapshot(df: pd.DataFrame, as_of: date | None = None) -> dict[str, str]:
    """Statuses as of the last review. Seeded from an earlier as-of date on first run."""
    if os.path.exists(SNAPSHOT_JSON):
        with open(SNAPSHOT_JSON, encoding="utf-8") as f:
            return json.load(f)
    as_of = as_of or date.today()
    baseline = enrich(df, as_of - timedelta(days=BASELINE_LOOKBACK_DAYS))
    mapping = dict(zip(baseline["customer_id"], baseline["status"]))
    save_snapshot(mapping)
    return mapping


def save_snapshot(mapping: dict[str, str]) -> None:
    with open(SNAPSHOT_JSON, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)


def recommended_step(row, previous: str) -> str:
    amount = f"EUR {row['receivables_outstanding']:,.0f}"
    days = int(row["days_since_work"])
    if row["status"] == COLLECTIONS:
        return (
            f"Issue a formal demand letter, then engage a collection agency covering "
            f"{row['city']}, {row['country']}. {amount} outstanding, {days} days since work completed."
        )
    if row["status"] == LEGAL:
        base = (
            f"Escalate to legal counsel licensed in {row['country']} and prepare the claim file "
            f"(contract, invoices, delivery evidence). {amount} outstanding, {days} days since "
            f"work completed."
        )
        if previous == COLLECTIONS:
            base += " Withdraw the open collection referral before filing."
        return base
    return (
        f"Balance cleared the delinquency thresholds ({amount} outstanding). Close out any open "
        f"collection or legal referral and resume normal terms."
    )


def status_changes(previous: dict[str, str], current: pd.DataFrame) -> pd.DataFrame:
    """Rows whose delinquency status differs from the last reviewed snapshot."""
    records = []
    for _, row in current.iterrows():
        prev = previous.get(row["customer_id"], CURRENT)
        if prev == row["status"]:
            continue
        escalation = RANK[row["status"]] > RANK[prev]
        records.append(
            {
                "customer_id": row["customer_id"],
                "customer": row["customer"],
                "location": f"{row['city']}, {row['country']}",
                "business_area": row["business_area"],
                "from_status": prev,
                "to_status": row["status"],
                "direction": "Escalation" if escalation else "Cleared",
                "receivables_outstanding": row["receivables_outstanding"],
                "days_since_work": row["days_since_work"],
                "next_step": recommended_step(row, prev),
            }
        )
    changes = pd.DataFrame(records)
    if changes.empty:
        return changes
    return changes.sort_values(
        ["direction", "receivables_outstanding"], ascending=[True, False]
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Task queue
# ---------------------------------------------------------------------------


def load_tasks() -> list[dict]:
    if not os.path.exists(TASKS_JSON):
        return []
    with open(TASKS_JSON, encoding="utf-8") as f:
        return json.load(f)


def save_tasks(tasks: list[dict]) -> None:
    with open(TASKS_JSON, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)


def sync_tasks(current: pd.DataFrame, tasks: list[dict]) -> tuple[list[dict], int]:
    """Queue a sourcing task for every delinquent customer that doesn't already have one.

    Collections delinquency queues agency sourcing; legal delinquency queues counsel
    sourcing. Tasks for customers that have since cleared are marked obsolete.
    """
    existing = {(t["customer_id"], t["task_type"]) for t in tasks if t["status"] != "Obsolete"}
    delinquent = current[current["status"] != CURRENT]
    added = 0

    for _, row in delinquent.iterrows():
        task_type = TASK_FOR_STATUS[row["status"]]
        if (row["customer_id"], task_type) in existing:
            continue
        tasks.append(
            {
                "task_id": f"T{len(tasks) + 1:04d}",
                "customer_id": row["customer_id"],
                "customer": row["customer"],
                "task_type": task_type,
                "city": row["city"],
                "country": row["country"],
                "business_area": row["business_area"],
                "receivables_outstanding": float(row["receivables_outstanding"]),
                "days_since_work": int(row["days_since_work"]),
                "status": "Queued",
                "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "findings": None,
            }
        )
        added += 1

    still_delinquent = set(delinquent["customer_id"])
    for task in tasks:
        if task["customer_id"] not in still_delinquent and task["status"] == "Queued":
            task["status"] = "Obsolete"

    if added or tasks:
        save_tasks(tasks)
    return tasks, added
