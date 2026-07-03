"""
Excel (.xlsx / .xls) loader.

Each sheet becomes its own "page" (page_number = 1-based sheet
index), with rows flattened into readable "col | col | col" lines.
This lets a retrieved chunk retain which sheet it came from, the
same way PDF chunks retain which page they came from.

.xlsx and legacy .xls use different libraries (openpyxl vs xlrd)
since no single library reads both formats reliably.
"""
import os

import openpyxl
import xlrd


def load_excel(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".xls":
        return _load_xls(file_path)
    return _load_xlsx(file_path)


def _load_xlsx(file_path):
    workbook = openpyxl.load_workbook(file_path, data_only=True)
    pages = []
    for sheet_index, sheet in enumerate(workbook.worksheets, start=1):
        lines = []
        for row in sheet.iter_rows(values_only=True):
            values = [str(v) for v in row if v is not None]
            if values:
                lines.append(" | ".join(values))
        pages.append((sheet_index, "\n".join(lines)))

    total_chars = sum(len(t) for _, t in pages)
    print(f"✅ Extracted {total_chars} characters from {len(pages)} Excel sheet(s)")
    return pages


def _load_xls(file_path):
    workbook = xlrd.open_workbook(file_path)
    pages = []
    for sheet_index, sheet in enumerate(workbook.sheets(), start=1):
        lines = []
        for row_index in range(sheet.nrows):
            values = [str(v) for v in sheet.row_values(row_index) if v not in ("", None)]
            if values:
                lines.append(" | ".join(values))
        pages.append((sheet_index, "\n".join(lines)))

    total_chars = sum(len(t) for _, t in pages)
    print(f"✅ Extracted {total_chars} characters from {len(pages)} Excel sheet(s) (legacy .xls)")
    return pages