# Fast Track Financial Dashboard

The supporting model for the Fast Track accounting work. 9.15.2026
The first tab contains historical data + forecasted financials. One-time expenditures in Month 8 and 9 have been scrubbed out for consistency.

A 5-tab Streamlit dashboard built on top of that model:

1. **KPI Overview** — revenue growth, COGS growth, net MoM cash change, scrubbed net income growth (all vs. trailing 3-month average), and total one-time cash expenditures over the trailing 6 months.
2. **Trends** — Revenue, COGS, and Net Income plotted over the last 6 months of actuals.
3. **Income Statement** — current month plus the trailing 3 months.
4. **Balance Sheet** — the latest period.
5. **Market Research** — ask Claude (with live web search) to research market conditions that could affect forecasted growth rates.

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

By default the app loads `Fast Track Supporting Model.xlsx` (bundled in this repo). Use the sidebar to upload a different workbook at any time — every tab updates automatically.

## Market Research tab (optional)

The Market Research tab uses the Anthropic API. Without a key it falls back to a plain Google search link. To enable it:

- **Locally:** set the `ANTHROPIC_API_KEY` environment variable.
- **On Streamlit Community Cloud:** add `ANTHROPIC_API_KEY = "sk-ant-..."` under your app's Settings -> Secrets.

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (already done if you're reading this on GitHub).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in, and click "New app".
3. Point it at this repo, branch `main`, main file `app.py`.
4. (Optional) Add your `ANTHROPIC_API_KEY` under Settings -> Secrets to enable the Market Research tab.
5. Deploy — you'll get a public `*.streamlit.app` URL anyone can open.
