"""Parses the Fast Track Supporting Model workbook into structured Python data.

Uses label-based lookups (not fixed row numbers) so the parser keeps working
as new months are appended to the workbook.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import openpyxl


@dataclass
class SheetTable:
    """A label -> list[value] table for one worksheet, plus its month headers."""

    months: list[str]                  # header labels for each data column, in order
    actual_flags: list[bool]           # True if that column is an actual (not forecast) month
    rows: dict[str, list[float | None]]  # line-item label -> values aligned with `months`

    def actual_months(self) -> list[str]:
        return [m for m, is_actual in zip(self.months, self.actual_flags) if is_actual]

    def series(self, label: str, actual_only: bool = True) -> list[float]:
        """Return the numeric series for a line item, actual months only by default."""
        values = self.rows.get(label)
        if values is None:
            raise KeyError(f"Line item '{label}' not found. Available: {list(self.rows)}")
        if not actual_only:
            return [v for v in values if v is not None]
        return [v for v, is_actual in zip(values, self.actual_flags) if is_actual and v is not None]


@dataclass
class Workbook:
    income_statement: SheetTable
    balance_sheet: SheetTable
    source_path: str


def _is_forecast_header(header: str) -> bool:
    return "(F)" in str(header)


def _find_header_row(ws, max_scan_rows: int = 15) -> int:
    """Find the row that contains the 'Line Item' header cell."""
    for row in range(1, max_scan_rows + 1):
        val = ws.cell(row=row, column=1).value
        if val and str(val).strip().lower() in ("line item", "€"):
            return row
    raise ValueError(f"Could not locate header row in sheet '{ws.title}'")


def _load_sheet_table(ws) -> SheetTable:
    header_row = _find_header_row(ws)

    # Collect header cells from column B onward, stopping at the first fully empty cell
    # that is followed by only empty cells (handles trailing "Total" columns fine, we keep them
    # but exclude any column whose header is a "Total" column since those aren't real months).
    raw_headers: list[tuple[int, str]] = []
    col = 2
    empty_streak = 0
    max_col = ws.max_column
    while col <= max_col:
        val = ws.cell(row=header_row, column=col).value
        if val is None or str(val).strip() == "":
            empty_streak += 1
            if empty_streak >= 3:
                break
        else:
            empty_streak = 0
            raw_headers.append((col, str(val).strip()))
        col += 1

    # Exclude aggregate/total columns (e.g. "5-Month Total", "3-Mo Forecast Total")
    month_cols = [(c, h) for c, h in raw_headers if "total" not in h.lower()]

    months = [h for _, h in month_cols]
    actual_flags = [not _is_forecast_header(h) for h in months]
    col_indices = [c for c, _ in month_cols]

    rows: dict[str, list[float | None]] = {}
    for r in range(header_row + 1, ws.max_row + 1):
        label = ws.cell(row=r, column=1).value
        if label is None or str(label).strip() == "":
            continue
        label = str(label).strip()
        values: list[float | None] = []
        for c in col_indices:
            v = ws.cell(row=r, column=c).value
            if isinstance(v, (int, float)):
                values.append(float(v))
            else:
                values.append(None)
        # Skip rows that are entirely blank (likely section headers/notes)
        if any(v is not None for v in values):
            rows[label] = values

    return SheetTable(months=months, actual_flags=actual_flags, rows=rows)


def load_workbook(path: str) -> Workbook:
    wb = openpyxl.load_workbook(path, data_only=True)

    is_sheet_name = next(n for n in wb.sheetnames if "income" in n.lower())
    bs_sheet_name = next(n for n in wb.sheetnames if "balance" in n.lower())

    income_statement = _load_sheet_table(wb[is_sheet_name])
    balance_sheet = _load_sheet_table(wb[bs_sheet_name])

    return Workbook(
        income_statement=income_statement,
        balance_sheet=balance_sheet,
        source_path=path,
    )
