"""Fast Track financial dashboard — Streamlit entry point."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import kpis
import market_research
from data_loader import load_workbook

DEFAULT_PATH = r"C:\Users\jimmy\OneDrive\Desktop\Fast Track Supporting Model.xlsx"

st.set_page_config(page_title="Fast Track Dashboard", layout="wide")


@st.cache_data(show_spinner="Loading workbook...")
def _load(path: str, mtime: float):
    return load_workbook(path)


def get_workbook():
    path = st.session_state.get("wb_path", DEFAULT_PATH)
    import os

    if not os.path.exists(path):
        st.error(f"File not found: {path}")
        st.stop()
    mtime = os.path.getmtime(path)
    try:
        return _load(path, mtime)
    except PermissionError:
        st.error(
            f"Can't open '{path}' — it's locked by another program (most likely it's "
            "currently open in Excel, or OneDrive is mid-sync). Close the file in Excel "
            "and click the button below to retry."
        )
        if st.button("Retry"):
            st.cache_data.clear()
            st.rerun()
        st.stop()
    except Exception as e:
        st.error(f"Failed to load workbook: {e}")
        st.stop()


with st.sidebar:
    st.header("Data Source")
    path_input = st.text_input("Workbook path", value=DEFAULT_PATH)
    st.session_state["wb_path"] = path_input
    uploaded = st.file_uploader("...or upload an .xlsx file", type=["xlsx"])
    if uploaded is not None:
        tmp_path = f"_uploaded_{uploaded.name}"
        with open(tmp_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.session_state["wb_path"] = tmp_path

wb = get_workbook()

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 KPI Overview", "📈 Trends", "🧾 Income Statement", "🏦 Balance Sheet", "🔎 Market Research"]
)

# ---------------------------------------------------------------------------
# Tab 1: KPI Overview
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("Key Performance Indicators")
    results = kpis.all_kpis(wb)
    cols = st.columns(5)
    for col, kpi in zip(cols, results):
        col.metric(kpi.label, kpi.display)

# ---------------------------------------------------------------------------
# Tab 2: Trend chart
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("Revenue, COGS & Net Income — Last 6 Months")
    is_table = wb.income_statement
    cogs_label = next(l for l in is_table.rows if l.startswith("COGS"))
    ni_label = next(l for l in is_table.rows if "Net Income" in l and "Scrubbed" in l)

    months = is_table.actual_months()[-6:]
    n = len(months)
    revenue = is_table.series("Revenue")[-n:]
    cogs = is_table.series(cogs_label)[-n:]
    net_income = is_table.series(ni_label)[-n:]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=months, y=revenue, mode="lines+markers", name="Revenue"))
    fig.add_trace(go.Scatter(x=months, y=cogs, mode="lines+markers", name="COGS"))
    fig.add_trace(go.Scatter(x=months, y=net_income, mode="lines+markers", name="Net Income"))
    fig.update_layout(xaxis_title="Month", yaxis_title="€", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 3: Income Statement
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("Income Statement — Current Month + Trailing 3")
    is_table = wb.income_statement
    months = is_table.months[-4:] if len(is_table.months) >= 4 else is_table.months
    n = len(months)
    data = {label: values[-n:] for label, values in is_table.rows.items()}
    df = pd.DataFrame(data, index=months).T
    st.dataframe(df.style.format("{:,.2f}", na_rep="—"), use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 4: Balance Sheet
# ---------------------------------------------------------------------------
with tab4:
    st.subheader("Balance Sheet — Current Period")
    bs_table = wb.balance_sheet
    latest_month = bs_table.months[-1]
    data = {label: values[-1] for label, values in bs_table.rows.items()}
    df = pd.DataFrame.from_dict(data, orient="index", columns=[latest_month])
    st.dataframe(df.style.format("{:,.2f}", na_rep="—"), use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 5: Market Research
# ---------------------------------------------------------------------------
with tab5:
    st.subheader("Market Research")
    st.write(
        "Select keywords to research current market conditions that could affect "
        "forecasted growth rates."
    )
    keywords = st.text_input(
        "Search keywords",
        placeholder="e.g. SaaS industry growth outlook 2026, inflation impact on SMB costs",
    )
    context = st.text_input("Business context (optional)", placeholder="e.g. B2B SaaS company")

    if market_research.api_key_available():
        if st.button("Run Research", type="primary", disabled=not keywords):
            with st.spinner("Researching..."):
                result = market_research.run_market_research(keywords, context)
            st.markdown(result)
    else:
        st.warning(
            "ANTHROPIC_API_KEY is not set. Set it as an environment variable to enable "
            "AI-powered research. Showing a plain Google search link instead."
        )
        if keywords:
            url = market_research.google_search_url(keywords)
            st.markdown(f"[Open Google search for '{keywords}']({url})")
