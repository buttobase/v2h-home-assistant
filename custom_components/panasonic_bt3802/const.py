from __future__ import annotations

DOMAIN = "panasonic_bt3802"

PANASONIC_URL = (
    "http://192.168.0.2/contents/csv/sys_current.csv"
    "?unit_number=1&code=2"
)

# Based on your confirmed CSV format:
# - Data row is line index 3 (0-based) in raw text
# - Bought is column 65, Sold is column 66
CSV_DATA_LINE_INDEX = 3
CSV_COL_BOUGHT = 65
CSV_COL_SOLD = 66
