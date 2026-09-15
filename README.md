# Fast Track Financial Dashboard

The supporting model for the Fast Track accounting work. 9.15.2026
The first tab contains historical data + forecasted financials. One-time expenditures in Month 8 and 9 have been scrubbed out for consistency.

A 6-tab Streamlit dashboard built on top of that model:

1. **KPI Overview** — revenue growth, COGS growth, net MoM cash change, scrubbed net income growth (all vs. trailing 3-month average), and total one-time cash expenditures over the trailing 6 months.
2. **Trends** — Revenue, COGS, and Net Income plotted over the last 6 months of actuals.
3. **Income Statement** — current month plus the trailing 3 months.
4. **Balance Sheet** — the latest period.
5. **Market Research** — ask Claude (with live web search) to research market conditions that could affect forecasted growth rates.
6. **Receivables CRM** — delinquent receivables tracking across the global customer book.

## Receivables CRM

Seeded with 60 example customers. Delinquency is derived on every refresh from the outstanding balance and the days elapsed since the last completed work:

| Condition | Status | Row |
| --- | --- | --- |
| > EUR 2,000 outstanding and > 30 days | Collections referral | yellow |
| > EUR 2,000 outstanding and > 90 days | Legal escalation | red |
| otherwise | Current | white |

Four sub-tabs:

- **Customer Book** — the full table with row tinting and `Refer: Collections` / `Refer: Legal` checkmark columns. Records are editable; saving re-derives everything.
- **Action Items** — accounts whose status changed since the last review, each with a recommended next step. "Mark reviewed" sets the new baseline.
- **Task Queue** — a sourcing task is queued automatically for every delinquent account: a collection agency for yellow, legal counsel for red. Running a task searches the web for firms in the debtor's own jurisdiction and extracts a recommended firm and contact address.
- **Outreach Drafts** — drafts an instruction email to the sourced agency or law firm using the debtor's profile, then hands it off to Gmail.

State lives in `crm_customers.csv`, `crm_status_snapshot.json`, and `crm_tasks.json` beside `app.py`. They are generated on first run and git-ignored; "Reset to seed data" rebuilds them.

### Gmail hand-off

"Open draft in Gmail" opens a pre-filled compose window in whichever Gmail account is signed in to that browser. No credentials are requested or stored by the app, and nothing sends until you press Send in Gmail. A `mailto:` link is offered for desktop mail clients.

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

By default the app loads `Fast Track Supporting Model.xlsx` (bundled in this repo). Use the sidebar to upload a different workbook at any time — every tab updates automatically.

## Anthropic API key (optional)

The Market Research tab and the CRM's agency sourcing / email drafting use the Anthropic API. Without a key, research falls back to Google search links and emails fall back to a structured template. To enable them:

- **Locally:** set the `ANTHROPIC_API_KEY` environment variable.
- **On Streamlit Community Cloud:** add `ANTHROPIC_API_KEY = "sk-ant-..."` under your app's Settings -> Secrets.

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (already done if you're reading this on GitHub).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in, and click "New app".
3. Point it at this repo, branch `main`, main file `app.py`.
4. (Optional) Add your `ANTHROPIC_API_KEY` under Settings -> Secrets to enable Market Research and the CRM's sourcing and drafting features.
5. Deploy — you'll get a public `*.streamlit.app` URL anyone can open.
