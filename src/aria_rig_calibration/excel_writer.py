"""Excel workbook writer + validator (openpyxl). Professional formatting; validates each sheet
against its source DataFrame. No personal identifiers are written."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter


def _safe(name: str) -> str:
    for ch in "\\/?*[]:":
        name = name.replace(ch, " ")
    return name[:31]


def write_workbook(sheet_map: dict[str, pd.DataFrame | None], dest: Path, log) -> Path | None:
    wb = Workbook(); wb.remove(wb.active)
    for name, df in sheet_map.items():
        ws = wb.create_sheet(_safe(name))
        if df is None or len(df) == 0:
            ws["A1"] = "no rows"; continue
        ws.append(list(df.columns))
        for _, r in df.iterrows():
            ws.append(["" if pd.isna(v) else v for v in r.tolist()])
        for c in range(1, len(df.columns) + 1):
            ws.cell(1, c).font = Font(bold=True)
            ws.cell(1, c).fill = PatternFill("solid", fgColor="DDDDDD")
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, col in enumerate(df.columns, start=1):
            mx = df[col].astype(str).str.len().max()
            mx = 8 if pd.isna(mx) else int(mx)
            width = min(max(len(str(col)) + 2, mx + 2), 55)
            ws.column_dimensions[get_column_letter(i)].width = width
            if any(t in str(col).lower() for t in ("path", "reason", "note", "status", "source")):
                for row in range(2, len(df) + 2):
                    ws.cell(row, i).alignment = Alignment(wrap_text=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dest); log.info("excel: workbook -> %s", dest)
    return dest


def validate_workbook(dest: Path, sheet_map: dict, out_csv: Path, log) -> pd.DataFrame:
    wb = load_workbook(dest, read_only=True)
    rows = []
    for name, df in sheet_map.items():
        sn = _safe(name)
        try:
            ws = wb[sn]; xrows = ws.max_row - 1 if ws.max_row else 0; xcols = ws.max_column
        except KeyError:
            rows.append({"sheet": name, "status": "missing"}); continue
        src_rows = 0 if df is None else len(df)
        status = "pass" if (df is None or len(df) == 0 or (src_rows == xrows)) else "fail"
        rows.append({"sheet": name, "csv_rows": src_rows, "xlsx_rows": xrows,
                     "csv_cols": 0 if df is None else len(df.columns), "xlsx_cols": xcols, "status": status})
    v = pd.DataFrame(rows); v.to_csv(out_csv, index=False)
    log.info("excel validation: %d/%d sheets pass", int((v.status == "pass").sum()), len(v))
    return v
