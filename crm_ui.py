"""Receivables CRM tab: customer book, action items, sourcing queue, and outreach drafts."""
from __future__ import annotations

import os
from datetime import date

import pandas as pd
import streamlit as st

import crm_data
import crm_email
import crm_logic
from crm_logic import COLLECTIONS, CURRENT, LEGAL

CRM_CSS = """
<style>
    .crm-stats { display: flex; gap: 0.9rem; margin-bottom: 1.4rem; }
    .crm-stat {
        flex: 1;
        border: 1px solid #E3E7EC;
        border-radius: 8px;
        padding: 0.9rem 1.1rem;
        background-color: #FAFBFC;
    }
    .crm-stat .label {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #5A6472;
    }
    .crm-stat .value { font-size: 1.7rem; font-weight: 700; color: #1F3A5F; }
    .crm-stat.amber { border-left: 3px solid #C9A227; }
    .crm-stat.red { border-left: 3px solid #A32424; }
    .crm-legend { font-size: 0.88rem; color: #5A6472; margin: 0.4rem 0 1rem 0; }
    .crm-legend span.swatch {
        display: inline-block; width: 0.8rem; height: 0.8rem;
        border: 1px solid #D6DBE1; border-radius: 2px;
        margin: 0 0.35rem 0 1.1rem; vertical-align: middle;
    }
    .crm-legend span.swatch:first-of-type { margin-left: 0; }
    .crm-card {
        border: 1px solid #E3E7EC;
        border-left: 3px solid #C9A227;
        border-radius: 6px;
        padding: 0.85rem 1.1rem;
        margin-bottom: 0.7rem;
        background-color: #FDFDFE;
    }
    .crm-card.legal { border-left-color: #A32424; }
    .crm-card.cleared { border-left-color: #1B6E3C; }
    .crm-card .head { font-weight: 600; color: #1F3A5F; }
    .crm-card .meta { font-size: 0.85rem; color: #5A6472; margin: 0.15rem 0 0.4rem 0; }
    .crm-card .step { font-size: 0.93rem; color: #2B333D; }
</style>
"""


def _stat(label: str, value: str, tone: str = "") -> str:
    return (
        f'<div class="crm-stat {tone}"><div class="label">{label}</div>'
        f'<div class="value">{value}</div></div>'
    )


def render() -> None:
    st.markdown(CRM_CSS, unsafe_allow_html=True)

    as_of = date.today()
    raw = crm_data.load_customers()
    df = crm_logic.enrich(raw, as_of)

    previous = crm_logic.load_snapshot(raw, as_of)
    changes = crm_logic.status_changes(previous, df)
    tasks, new_tasks = crm_logic.sync_tasks(df, crm_logic.load_tasks())
    open_tasks = [t for t in tasks if t["status"] in ("Queued", "In Progress")]

    n_collections = int((df["status"] == COLLECTIONS).sum())
    n_legal = int((df["status"] == LEGAL).sum())
    exposure = df.loc[df["status"] != CURRENT, "receivables_outstanding"].sum()

    st.markdown(
        '<div class="crm-stats">'
        + _stat("Customers", f"{len(df)}")
        + _stat("Total Receivables", f"€{df['receivables_outstanding'].sum():,.0f}")
        + _stat("Collections Watch", f"{n_collections}", "amber")
        + _stat("Legal Escalation", f"{n_legal}", "red")
        + _stat("Delinquent Exposure", f"€{exposure:,.0f}", "red")
        + "</div>",
        unsafe_allow_html=True,
    )

    tab_book, tab_actions, tab_queue, tab_email = st.tabs(
        [
            "Customer Book",
            f"Action Items ({len(changes)})",
            f"Task Queue ({len(open_tasks)})",
            "Outreach Drafts",
        ]
    )

    with tab_book:
        _render_book(df, raw)
    with tab_actions:
        _render_actions(changes, df, new_tasks)
    with tab_queue:
        _render_queue(tasks)
    with tab_email:
        _render_email(df, tasks)


# ---------------------------------------------------------------------------
# Customer book
# ---------------------------------------------------------------------------


def _render_book(df: pd.DataFrame, raw: pd.DataFrame) -> None:
    st.markdown(
        f'<div class="source-note">Receivables over €{crm_logic.AR_THRESHOLD:,.0f} are flagged '
        f"for collections after {crm_logic.DAYS_COLLECTIONS} days and for legal escalation "
        f"after {crm_logic.DAYS_LEGAL} days from the last completed work.</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1.2, 1.2, 2])
    status_filter = c1.multiselect(
        "Status", [CURRENT, COLLECTIONS, LEGAL], default=[CURRENT, COLLECTIONS, LEGAL]
    )
    region_filter = c2.multiselect("Region", sorted(df["region"].unique()))
    search = c3.text_input("Search", placeholder="Customer, country or business area")

    view = df[df["status"].isin(status_filter)]
    if region_filter:
        view = view[view["region"].isin(region_filter)]
    if search:
        needle = search.lower()
        mask = (
            view["customer"].str.lower().str.contains(needle)
            | view["country"].str.lower().str.contains(needle)
            | view["business_area"].str.lower().str.contains(needle)
        )
        view = view[mask]

    view = view.sort_values(
        ["status", "receivables_outstanding"],
        key=lambda s: s.map(crm_logic.RANK) if s.name == "status" else s,
        ascending=[False, False],
    )

    st.markdown(
        '<div class="crm-legend">'
        '<span class="swatch" style="background:#FFFFFF"></span>Current'
        '<span class="swatch" style="background:#FDF6E0"></span>Collections referral'
        '<span class="swatch" style="background:#FAECEA"></span>Legal escalation'
        "</div>",
        unsafe_allow_html=True,
    )

    if view.empty:
        st.info("No customers match the current filters.")
    else:
        st.dataframe(
            crm_logic.style_table(view), width="stretch", hide_index=True, height=560
        )

    with st.expander("Edit customer records"):
        st.caption(
            "Adjust outstanding balances or work dates and save — statuses, action items "
            "and the task queue refresh immediately."
        )
        edited = st.data_editor(
            raw,
            width="stretch",
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "customer_id": st.column_config.TextColumn("ID", disabled=True),
                "customer": st.column_config.TextColumn("Customer"),
                "last_work_date": st.column_config.TextColumn("Last Work (YYYY-MM-DD)"),
                "cash_received": st.column_config.NumberColumn(
                    "Cash Received (EUR)", format="%.2f"
                ),
                "receivables_outstanding": st.column_config.NumberColumn(
                    "Receivables (EUR)", format="%.2f"
                ),
            },
            key="crm_editor",
        )
        if st.button("Save changes", type="primary"):
            crm_data.save_customers(edited)
            st.rerun()

    with st.expander("Reset to seed data"):
        st.caption(
            "Regenerates the 60 example customers and clears the review baseline and task queue."
        )
        confirm = st.checkbox("I understand this discards current CRM records")
        if st.button("Reset", disabled=not confirm):
            crm_data.reset_customers()
            for path in (crm_logic.SNAPSHOT_JSON, crm_logic.TASKS_JSON):
                if os.path.exists(path):
                    os.remove(path)
            st.rerun()


# ---------------------------------------------------------------------------
# Action items
# ---------------------------------------------------------------------------


def _render_actions(changes: pd.DataFrame, df: pd.DataFrame, new_tasks: int) -> None:
    if changes.empty:
        st.success("No delinquency status changes since the last review.")
        return

    escalations = int((changes["direction"] == "Escalation").sum())
    st.markdown(
        f'<div class="source-note">{len(changes)} account(s) changed delinquency status since '
        f"the last review — {escalations} escalation(s). "
        f"{new_tasks} sourcing task(s) were queued automatically.</div>",
        unsafe_allow_html=True,
    )

    for _, row in changes.iterrows():
        tone = (
            "cleared"
            if row["direction"] == "Cleared"
            else ("legal" if row["to_status"] == LEGAL else "")
        )
        st.markdown(
            f"""
            <div class="crm-card {tone}">
                <div class="head">{row['customer']} &nbsp;·&nbsp; {row['from_status']} → {row['to_status']}</div>
                <div class="meta">{row['location']} · {row['business_area']} ·
                    €{row['receivables_outstanding']:,.0f} outstanding ·
                    {int(row['days_since_work'])} days since work</div>
                <div class="step">{row['next_step']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.download_button(
        "Download action items (CSV)",
        changes.to_csv(index=False).encode("utf-8"),
        file_name=f"action_items_{date.today().isoformat()}.csv",
        mime="text/csv",
    )

    if st.button("Mark reviewed", type="primary"):
        crm_logic.save_snapshot(dict(zip(df["customer_id"], df["status"])))
        st.rerun()


# ---------------------------------------------------------------------------
# Task queue
# ---------------------------------------------------------------------------


def _render_queue(tasks: list[dict]) -> None:
    if not tasks:
        st.info("No sourcing tasks queued.")
        return

    show_closed = st.checkbox("Show completed and obsolete tasks", value=False)
    visible = [
        t for t in tasks if show_closed or t["status"] in ("Queued", "In Progress")
    ]
    if not visible:
        st.success("All sourcing tasks are closed.")
        return

    table = pd.DataFrame(visible)[
        ["task_id", "customer", "task_type", "city", "country",
         "receivables_outstanding", "days_since_work", "status", "created"]
    ].rename(
        columns={
            "task_id": "Task",
            "customer": "Customer",
            "task_type": "Task Type",
            "city": "City",
            "country": "Country",
            "receivables_outstanding": "Receivables (EUR)",
            "days_since_work": "Days",
            "status": "Status",
            "created": "Queued",
        }
    )
    st.dataframe(
        table.style.format({"Receivables (EUR)": "{:,.0f}"}),
        width="stretch",
        hide_index=True,
    )

    st.markdown('<div class="section-title">Run sourcing</div>', unsafe_allow_html=True)
    labels = {f"{t['task_id']} — {t['customer']} ({t['task_type']})": t for t in visible}
    choice = st.selectbox("Task", list(labels))
    task = labels[choice]

    st.caption(
        f"{task['task_type']} for {task['city']}, {task['country']} · "
        f"{task['business_area']} · €{task['receivables_outstanding']:,.0f} outstanding"
    )

    if crm_email.api_key_available():
        if st.button("Source partners", type="primary", key=f"src_{task['task_id']}"):
            with st.spinner("Researching firms in this jurisdiction..."):
                task["findings"] = crm_email.source_partners(task)
            task["status"] = "In Progress"
            crm_logic.save_tasks(tasks)
            st.rerun()
    else:
        st.warning(
            "ANTHROPIC_API_KEY is not set, so automated sourcing is unavailable. "
            "Use the search link below instead."
        )
        st.markdown(
            f"[Search for firms in {task['city']}, {task['country']}]"
            f"({crm_email.google_search_url(crm_email.sourcing_query(task))})"
        )

    if task.get("findings"):
        st.markdown(task["findings"])
        if st.button("Mark task complete", key=f"done_{task['task_id']}"):
            task["status"] = "Completed"
            crm_logic.save_tasks(tasks)
            st.rerun()


# ---------------------------------------------------------------------------
# Outreach drafts
# ---------------------------------------------------------------------------


def _render_email(df: pd.DataFrame, tasks: list[dict]) -> None:
    delinquent = df[df["status"] != CURRENT].sort_values(
        "receivables_outstanding", ascending=False
    )
    if delinquent.empty:
        st.success("No delinquent accounts require outreach.")
        return

    labels = {
        f"{r['customer']} — €{r['receivables_outstanding']:,.0f} ({r['status']})": r
        for _, r in delinquent.iterrows()
    }
    choice = st.selectbox("Delinquent account", list(labels))
    row = labels[choice]
    is_legal = row["status"] == LEGAL
    customer = row.to_dict()

    findings = next(
        (
            t.get("findings")
            for t in tasks
            if t["customer_id"] == row["customer_id"] and t.get("findings")
        ),
        None,
    )
    suggested_firm, suggested_email = crm_email.extract_recommendation(findings or "")

    c1, c2 = st.columns(2)
    firm_name = c1.text_input(
        "Recipient firm", value=suggested_firm, placeholder="Collection agency or law firm"
    )
    firm_email = c2.text_input(
        "Recipient email", value=suggested_email, placeholder="contact@firm.com"
    )
    if findings and not suggested_email:
        st.caption(
            "No contact address was published by the recommended firm — add one manually."
        )
    elif not findings:
        st.caption(
            f"Run the sourcing task for this account in the Task Queue tab to pre-fill a "
            f"{'law firm' if is_legal else 'collection agency'} and its contact address."
        )

    draft_key = f"draft_{row['customer_id']}"
    if st.button("Draft email", type="primary"):
        with st.spinner("Drafting..."):
            st.session_state[draft_key] = crm_email.draft_email(customer, firm_name, is_legal)

    if draft_key not in st.session_state:
        return

    subject, body = st.session_state[draft_key]
    subject = st.text_input("Subject", value=subject, key=f"subj_{row['customer_id']}")
    body = st.text_area("Body", value=body, height=420, key=f"body_{row['customer_id']}")

    st.markdown('<div class="section-title">Send</div>', unsafe_allow_html=True)
    with st.expander("Connect Gmail", expanded=True):
        st.caption(
            "Opening the draft in Gmail uses the account you are already signed into in this "
            "browser — no credentials are stored by this app. Nothing is sent until you press "
            "Send inside Gmail."
        )
        if not firm_email:
            st.info("Add a recipient email address above to enable the Gmail hand-off.")
        else:
            st.link_button(
                "Open draft in Gmail",
                crm_email.gmail_compose_url(firm_email, subject, body),
            )
            st.link_button(
                "Open in default mail client",
                crm_email.mailto_url(firm_email, subject, body),
            )

    st.download_button(
        "Download draft (.txt)",
        f"To: {firm_email}\nSubject: {subject}\n\n{body}".encode("utf-8"),
        file_name=f"draft_{row['customer_id']}.txt",
        mime="text/plain",
    )
