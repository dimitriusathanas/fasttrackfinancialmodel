"""KPI calculations for the Fast Track dashboard."""
from __future__ import annotations

from dataclasses import dataclass

from data_loader import Workbook


@dataclass
class KpiResult:
    label: str
    value: float | None
    display: str


def _trailing_avg_growth(series: list[float]) -> tuple[float | None, float | None, float | None]:
    """Latest value vs. trailing-3-month average (including the latest month).

    Returns (latest, trailing_avg, growth_pct) where growth_pct is a fraction (0.0328 = 3.28%).
    """
    if not series:
        return None, None, None
    latest = series[-1]
    window = series[-3:] if len(series) >= 3 else series[:]
    avg = sum(window) / len(window)
    growth = (latest / avg - 1) if avg else None
    return latest, avg, growth


def revenue_growth(wb: Workbook) -> KpiResult:
    series = wb.income_statement.series("Revenue")
    _, _, growth = _trailing_avg_growth(series)
    return KpiResult(
        label="Revenue Growth vs. Trailing 3-Mo Avg",
        value=growth,
        display=f"{growth:+.1%}" if growth is not None else "N/A",
    )


def cogs_growth(wb: Workbook) -> KpiResult:
    label = next(l for l in wb.income_statement.rows if l.startswith("COGS"))
    series = wb.income_statement.series(label)
    _, _, growth = _trailing_avg_growth(series)
    return KpiResult(
        label="COGS Growth vs. Trailing 3-Mo Avg",
        value=growth,
        display=f"{growth:+.1%}" if growth is not None else "N/A",
    )


def cash_mom_change(wb: Workbook) -> KpiResult:
    series = wb.balance_sheet.series("Cash")
    if len(series) < 2:
        return KpiResult(label="Net MoM Change in Cash", value=None, display="N/A")
    change = series[-1] - series[-2]
    return KpiResult(
        label="Net MoM Change in Cash",
        value=change,
        display=f"{change:+,.0f}",
    )


def net_income_growth(wb: Workbook) -> KpiResult:
    label = next(l for l in wb.income_statement.rows if "Net Income" in l and "Scrubbed" in l)
    series = wb.income_statement.series(label)
    _, _, growth = _trailing_avg_growth(series)
    return KpiResult(
        label="Net Income Growth vs. Trailing 3-Mo Avg (Scrubbed)",
        value=growth,
        display=f"{growth:+.1%}" if growth is not None else "N/A",
    )


def one_time_cash_expenditures(wb: Workbook, months: int = 6) -> KpiResult:
    """Sum of (scrubbed Net Income - reported Net Profit) over the trailing N actual months."""
    scrubbed_label = next(l for l in wb.income_statement.rows if "Net Income" in l and "Scrubbed" in l)
    reported_label = next(
        l for l in wb.income_statement.rows if "Net Profit" in l and "report" in l.lower()
    )
    scrubbed = wb.income_statement.series(scrubbed_label)
    reported = wb.income_statement.series(reported_label)

    n = min(months, len(scrubbed), len(reported))
    scrubbed_tail = scrubbed[-n:]
    reported_tail = reported[-n:]
    total = sum(s - r for s, r in zip(scrubbed_tail, reported_tail))

    return KpiResult(
        label=f"One-Time Cash Expenditures (Last {n} Mo.)",
        value=total,
        display=f"{total:,.0f}",
    )


def all_kpis(wb: Workbook) -> list[KpiResult]:
    return [
        revenue_growth(wb),
        cogs_growth(wb),
        cash_mom_change(wb),
        net_income_growth(wb),
        one_time_cash_expenditures(wb),
    ]
