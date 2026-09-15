"""Fast Track financial dashboard — Streamlit entry point."""
from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import kpis
import market_research
from data_loader import load_workbook

_LOCAL_DEFAULT = r"C:\Users\jimmy\OneDrive\Desktop\Fast Track Supporting Model.xlsx"
_BUNDLED_DEFAULT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "Fast Track Supporting Model.xlsx"
)


def _resolve_default_path() -> str:
    """Prefer the local desktop copy (when run on this machine); fall back to a copy
    bundled alongside app.py (used when deployed, e.g. Streamlit Community Cloud)."""
    if os.path.exists(_LOCAL_DEFAULT):
        return _LOCAL_DEFAULT
    if os.path.exists(_BUNDLED_DEFAULT):
        return _BUNDLED_DEFAULT
    return _LOCAL_DEFAULT


DEFAULT_PATH = _resolve_default_path()

st.set_page_config(page_title="Fast Track Dashboard", layout="wide")

CUSTOM_CSS = """
<style>
    html, body, [class*="css"] {
        font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    }
    .app-title {
        font-size: 2.1rem;
        font-weight: 600;
        color: #1F3A5F;
        margin-bottom: 0.1rem;
    }
    .app-subtitle {
        font-size: 1rem;
        color: #5A6472;
        margin-bottom: 1.5rem;
    }
    .section-title {
        font-size: 1.4rem;
        font-weight: 600;
        color: #1F3A5F;
        margin-bottom: 1rem;
        border-bottom: 2px solid #E3E7EC;
        padding-bottom: 0.4rem;
    }
    .kpi-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        border: 1px solid #E3E7EC;
        border-radius: 8px;
        padding: 1.1rem 1.6rem;
        margin-bottom: 0.9rem;
        background-color: #FAFBFC;
    }
    .kpi-label {
        font-size: 1.15rem;
        font-weight: 500;
        color: #2B333D;
    }
    .kpi-value {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1F3A5F;
    }
    .kpi-value.positive { color: #1B6E3C; }
    .kpi-value.negative { color: #A32424; }
    .source-note {
        font-size: 0.9rem;
        color: #5A6472;
        margin-bottom: 1rem;
    }
    div[data-testid="stTabs"] button p {
        font-size: 1.05rem;
        font-weight: 500;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner="Loading workbook...")
def _load(path: str, mtime: float):
    return load_workbook(path)


def get_workbook():
    path = st.session_state.get("wb_path", DEFAULT_PATH)

    if not os.path.exists(path):
        st.info(
            "No workbook is loaded yet. Upload an .xlsx file using the sidebar to get started."
        )
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
    st.caption("Loads the file below by default. Upload your own workbook to replace it.")

    if "wb_path" not in st.session_state:
        st.session_state["wb_path"] = DEFAULT_PATH

    uploaded = st.file_uploader("Upload a workbook (.xlsx)", type=["xlsx"])
    if uploaded is not None:
        tmp_path = f"_uploaded_{uploaded.name}"
        with open(tmp_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.session_state["wb_path"] = tmp_path

    if st.session_state["wb_path"] != DEFAULT_PATH:
        if st.button("Reset to default file"):
            st.session_state["wb_path"] = DEFAULT_PATH
            st.rerun()

    st.markdown("---")
    st.caption(f"Active file:\n`{os.path.basename(st.session_state['wb_path'])}`")

wb = get_workbook()

st.markdown('<div class="app-title">Fast Track Financial Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="app-subtitle">Source: {os.path.basename(st.session_state["wb_path"])}</div>',
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["KPI Overview", "Trends", "Income Statement", "Balance Sheet", "Market Research"]
)

# ---------------------------------------------------------------------------
# Tab 1: KPI Overview
# ---------------------------------------------------------------------------
with tab1:
    st.markdown('<div class="section-title">Key Performance Indicators</div>', unsafe_allow_html=True)
    results = kpis.all_kpis(wb)
    for kpi in results:
        css_class = "kpi-value"
        if kpi.value is not None:
            css_class += " positive" if kpi.value >= 0 else " negative"
        st.markdown(
            f"""
            <div class="kpi-row">
                <span class="kpi-label">{kpi.label}</span>
                <span class="{css_class}">{kpi.display}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Tab 2: Trend chart
# ---------------------------------------------------------------------------
with tab2:
    st.markdown(
        '<div class="section-title">Revenue, COGS &amp; Net Income — Last 6 Months</div>',
        unsafe_allow_html=True,
    )
    is_table = wb.income_statement
    cogs_label = next(l for l in is_table.rows if l.startswith("COGS"))
    ni_label = next(l for l in is_table.rows if "Net Income" in l and "Scrubbed" in l)

    months = is_table.actual_months()[-6:]
    n = len(months)
    revenue = is_table.series("Revenue")[-n:]
    cogs = is_table.series(cogs_label)[-n:]
    net_income = is_table.series(ni_label)[-n:]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=months, y=revenue, mode="lines+markers", name="Revenue",
                              line=dict(color="#1F3A5F", width=3)))
    fig.add_trace(go.Scatter(x=months, y=cogs, mode="lines+markers", name="COGS",
                              line=dict(color="#A32424", width=3)))
    fig.add_trace(go.Scatter(x=months, y=net_income, mode="lines+markers", name="Net Income",
                              line=dict(color="#1B6E3C", width=3)))
    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="EUR",
        hovermode="x unified",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font=dict(family="Segoe UI, Helvetica Neue, Arial, sans-serif", size=14),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 3: Income Statement
# ---------------------------------------------------------------------------
with tab3:
    st.markdown(
        '<div class="section-title">Income Statement — Current Month + Trailing 3</div>',
        unsafe_allow_html=True,
    )
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
    st.markdown('<div class="section-title">Balance Sheet — Current Period</div>', unsafe_allow_html=True)
    bs_table = wb.balance_sheet
    latest_month = bs_table.months[-1]
    data = {label: values[-1] for label, values in bs_table.rows.items()}
    df = pd.DataFrame.from_dict(data, orient="index", columns=[latest_month])
    st.dataframe(df.style.format("{:,.2f}", na_rep="—"), use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 5: Market Research
# ---------------------------------------------------------------------------
with tab5:
    st.markdown('<div class="section-title">Market Research</div>', unsafe_allow_html=True)
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
