"""Extract the cut-off sheet of ecoinvent's 'Correspondence File v3.12 - v3.13.xlsx' to a compact JSON.

Only identity columns are kept (activity/product UUIDs, names, geographies, units, difference flags).
The output goes to ``work/`` (local, not for distribution: it is derived from a licensed file).

Run:  conda run -n esa_import python scripts/04_load_correspondence.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import openpyxl  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def side(row, offset):
    if row[offset] is None:
        return None
    return {
        "activity_id": str(row[offset]).strip(),
        "activity_type": row[offset + 2],
        "name": row[offset + 3],
        "location": row[offset + 4],
        "product_id": str(row[offset + 8]).strip(),
        "product": row[offset + 9],
        "unit": row[offset + 10],
        "product_classification": row[offset + 12],
    }


def main() -> None:
    sources = json.loads((ROOT / "work" / "sources.json").read_text(encoding="utf-8"))
    path = Path(sources["extras"]["Correspondence File v3.12 - v3.13.xlsx"]["files"][0]["path"])
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["Cut-off"]
    rows = sheet.iter_rows(values_only=True)
    first = next(rows)
    header = next(rows)
    if str(first[0]) != "3.12" or str(first[13]) != "3.13" or header[0] != "Activity UUID" or header[13] != "Activity UUID":
        raise SystemExit(f"Unexpected correspondence layout: {first[:14]} / {header[:14]}")
    flag_names = list(header[26:40])
    records = []
    for row in rows:
        if all(value is None for value in row[:26]):
            continue
        records.append(
            {
                "source": side(row, 0),
                "target": side(row, 13),
                "flags": {name: row[26 + i] for i, name in enumerate(flag_names) if row[26 + i] not in (None, "")},
            }
        )
    out = ROOT / "work" / "correspondence_cutoff.json"
    out.write_text(json.dumps({"file": path.name, "sheet": "Cut-off", "records": records}, indent=1, ensure_ascii=False), encoding="utf-8")
    both = sum(1 for r in records if r["source"] and r["target"])
    print(f"wrote {out}: {len(records)} rows; both sides: {both}; source only: "
          f"{sum(1 for r in records if r['source'] and not r['target'])}; target only: "
          f"{sum(1 for r in records if r['target'] and not r['source'])}")
    print("flag columns:", flag_names)


if __name__ == "__main__":
    main()
