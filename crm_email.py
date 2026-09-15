"""Sourcing of collection/legal partners and drafting of outreach email.

Uses Claude with web search when an API key is configured; falls back to search
links and a deterministic template otherwise, so the tab is usable either way.
"""
from __future__ import annotations

import os
import re
import urllib.parse

import anthropic

MODEL = "claude-opus-4-7"
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}

SENDER_ORG = "Fast Track"

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _get_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


def api_key_available() -> bool:
    return bool(_get_api_key())


def google_search_url(query: str) -> str:
    return "https://www.google.com/search?q=" + urllib.parse.quote(query)


def sourcing_query(task: dict) -> str:
    if task["task_type"].startswith("Source legal"):
        return (
            f"commercial debt recovery law firm {task['city']} {task['country']} "
            f"B2B unpaid invoice litigation contact email"
        )
    return (
        f"commercial debt collection agency {task['city']} {task['country']} "
        f"B2B receivables recovery contact email"
    )


def _call_claude(prompt: str, max_tokens: int = 2048) -> str:
    client = anthropic.Anthropic(api_key=_get_api_key())
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            tools=[WEB_SEARCH_TOOL],
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError:
        return "Authentication failed. Check that ANTHROPIC_API_KEY is set correctly."
    except anthropic.RateLimitError:
        return "Rate limit reached. Please wait a moment and try again."
    except anthropic.APIConnectionError:
        return "Could not connect to the Anthropic API. Check your internet connection."
    except anthropic.APIStatusError as e:
        return f"API error ({e.status_code}): {e.message}"

    parts = [b.text for b in response.content if b.type == "text"]
    return "\n\n".join(parts) if parts else "No response text returned."


def source_partners(task: dict) -> str:
    """Research firms that can act on a delinquent account in the customer's market."""
    is_legal = task["task_type"].startswith("Source legal")
    kind = (
        "law firms specialising in commercial debt recovery and unpaid-invoice litigation"
        if is_legal
        else "commercial debt collection agencies handling B2B receivables"
    )
    prompt = (
        f"Using web search, identify three to five {kind} that operate in "
        f"{task['city']}, {task['country']}. The debtor is a {task['business_area']} company "
        f"with EUR {task['receivables_outstanding']:,.0f} outstanding, "
        f"{task['days_since_work']} days past completion of the work.\n\n"
        "For each firm give: name, a one-line note on why it fits this jurisdiction and "
        "sector, the website, and a contact email address if one is published (say "
        "'not published' rather than guessing). Finish with a single line "
        "'RECOMMENDED: <firm name> <email or n/a>' naming the best fit. "
        "Keep the whole answer under 350 words and cite your sources."
    )
    return _call_claude(prompt)


def extract_recommendation(findings: str) -> tuple[str, str]:
    """Pull the firm name and email out of the RECOMMENDED line of a sourcing result."""
    if not findings:
        return "", ""
    match = re.search(r"RECOMMENDED:\s*(.+)", findings)
    if not match:
        emails = _EMAIL_RE.findall(findings)
        return "", emails[0] if emails else ""
    line = match.group(1).strip()
    emails = _EMAIL_RE.findall(line)
    email = emails[0] if emails else ""
    name = line.replace(email, "").strip(" -–—,;|")
    if name.lower() in {"n/a", "none"}:
        name = ""
    return name, email


# ---------------------------------------------------------------------------
# Email drafting
# ---------------------------------------------------------------------------


def _fallback_draft(customer: dict, firm_name: str, is_legal: bool) -> tuple[str, str]:
    firm = firm_name or ("the firm" if is_legal else "your agency")
    action = (
        "formal legal recovery proceedings" if is_legal else "third-party collection"
    )
    subject = (
        f"{'Legal recovery' if is_legal else 'Collection'} instruction — "
        f"{customer['customer']} — EUR {customer['receivables_outstanding']:,.0f} outstanding"
    )
    body = f"""Dear {firm},

We are seeking support with an overdue commercial receivable and would like to understand your terms for {action}.

Debtor details
  Company:        {customer['customer']}
  Location:       {customer['city']}, {customer['country']}
  Sector:         {customer['business_area']}
  Relationship:   {customer['times_hired']} engagements to date
  Work completed: {customer['last_work_date']} ({customer['days_since_work']} days ago)
  Amount paid:    EUR {customer['cash_received']:,.0f}
  Outstanding:    EUR {customer['receivables_outstanding']:,.0f}

The balance is undisputed to our knowledge and our own reminders have gone unanswered. Contract documentation, signed acceptance of the work and the full invoice history are available on request.

Could you confirm:
  1. Whether you can act in {customer['country']} for a claim of this size
  2. Your fee structure and expected timeline
  3. What documentation you need from us to open the file

We are ready to proceed once terms are agreed.

Kind regards,

Accounts Receivable
{SENDER_ORG}
"""
    return subject, body


def draft_email(customer: dict, firm_name: str, is_legal: bool) -> tuple[str, str]:
    """Draft the outreach email. Returns (subject, body)."""
    if not api_key_available():
        return _fallback_draft(customer, firm_name, is_legal)

    if firm_name:
        recipient = f"the {'law firm' if is_legal else 'collection agency'} {firm_name}"
    else:
        recipient = (
            "a commercial debt recovery law firm" if is_legal else "a commercial collection agency"
        )
    prompt = (
        f"Write a professional outreach email from the accounts receivable team at "
        f"{SENDER_ORG} to {recipient} in {customer['city']}, {customer['country']}, "
        "instructing them on an overdue commercial receivable.\n\n"
        "Debtor profile:\n"
        f"- Company: {customer['customer']}\n"
        f"- Location: {customer['city']}, {customer['country']}\n"
        f"- Sector: {customer['business_area']}\n"
        f"- Prior engagements: {customer['times_hired']}\n"
        f"- Work completed on: {customer['last_work_date']} "
        f"({customer['days_since_work']} days ago)\n"
        f"- Cash received to date: EUR {customer['cash_received']:,.0f}\n"
        f"- Outstanding balance: EUR {customer['receivables_outstanding']:,.0f}\n\n"
        "Requirements: measured, businesslike tone; no legal threats against the debtor in "
        "this email since it is addressed to our prospective agent, not the debtor; ask for "
        "confirmation of jurisdiction coverage, fee structure, timeline and required "
        "documentation; keep it under 250 words. Reflect the jurisdiction and sector where "
        "it genuinely matters.\n\n"
        "Return exactly two sections and nothing else:\n"
        "SUBJECT: <one line>\n"
        "BODY:\n<email body>"
    )

    raw = _call_claude(prompt, max_tokens=1200)
    subject_match = re.search(r"SUBJECT:\s*(.+)", raw)
    body_match = re.search(r"BODY:\s*\n?(.*)", raw, re.DOTALL)
    if not subject_match or not body_match:
        return _fallback_draft(customer, firm_name, is_legal)
    return subject_match.group(1).strip(), body_match.group(1).strip()


# ---------------------------------------------------------------------------
# Gmail hand-off
# ---------------------------------------------------------------------------


def gmail_compose_url(to: str, subject: str, body: str) -> str:
    """Deep link that opens a pre-filled draft in the signed-in Gmail account."""
    params = urllib.parse.urlencode(
        {"view": "cm", "fs": "1", "to": to, "su": subject, "body": body}
    )
    return f"https://mail.google.com/mail/?{params}"


def mailto_url(to: str, subject: str, body: str) -> str:
    query = urllib.parse.urlencode({"subject": subject, "body": body})
    return f"mailto:{urllib.parse.quote(to)}?{query}"
