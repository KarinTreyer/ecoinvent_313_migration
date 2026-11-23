"""Run ecoinvent_migrate for ecoinvent 3.12 -> 3.13 (cut-off technosphere and biosphere).

Same approach as BrightPath's 3.11 -> 3.12 resources: the high-level ecoinvent_migrate generators,
falling back to ``supplement_biosphere_changes_with_real_data_comparison`` only if the biosphere
generator returns nothing (empty ``EE Deletions`` sheet).

Raw, unmodified generator outputs are written to ``work/raw/``. Logs are copied to ``work/logs/``.
Run:  conda run -n esa_import python scripts/02_run_ecoinvent_migrate.py
"""

from __future__ import annotations

import io
import json
import shutil
import sys
from datetime import datetime, timezone
from importlib.metadata import version as dist_version
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from platformdirs import user_log_dir  # noqa: E402

import ecoinvent_migrate  # noqa: E402
from ecoinvent_migrate import generate_biosphere_mapping, generate_technosphere_mapping  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "work" / "raw"
LOGS = ROOT / "work" / "logs"
RAW.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

LICENSES = [
    {
        "name": "CC-BY-4.0",
        "path": "https://creativecommons.org/licenses/by/4.0/legalcode",
        "title": "Creative Commons Attribution 4.0 International",
    }
]


def newest_log_dir() -> Path | None:
    base = Path(user_log_dir("ecoinvent_migrate", "pylca"))
    dirs = sorted((p for p in base.glob("*") if p.is_dir()), key=lambda p: p.stat().st_mtime)
    return dirs[-1] if dirs else None


def main() -> None:
    record = {
        "started": datetime.now(timezone.utc).isoformat(),
        "packages": {
            name: dist_version(name)
            for name in ("ecoinvent_migrate", "ecoinvent_interface", "randonneur", "randonneur_data", "bw2io", "bw2data")
        },
        "calls": [],
    }

    call = (
        'generate_technosphere_mapping(source_version="3.12", target_version="3.13", system_model="cutoff", '
        "write_logs=True, write_file=True, licenses=LICENSES, output_directory=work/raw)"
    )
    result = generate_technosphere_mapping(
        source_version="3.12",
        target_version="3.13",
        system_model="cutoff",
        write_logs=True,
        write_file=True,
        licenses=LICENSES,
        output_directory=RAW,
    )
    log_dir = newest_log_dir()
    if log_dir:
        shutil.copytree(log_dir, LOGS / f"technosphere_{log_dir.name}", dirs_exist_ok=True)
    record["calls"].append({"call": call, "result": str(result), "time": datetime.now(timezone.utc).isoformat()})
    print("technosphere ->", result)

    call = (
        'generate_biosphere_mapping(source_version="3.12", target_version="3.13", keep_deletions=False, '
        "write_logs=True, write_file=True, licenses=LICENSES, output_directory=work/raw)"
    )
    result = generate_biosphere_mapping(
        source_version="3.12",
        target_version="3.13",
        write_logs=True,
        write_file=True,
        licenses=LICENSES,
        output_directory=RAW,
    )
    log_dir = newest_log_dir()
    if log_dir:
        shutil.copytree(log_dir, LOGS / f"biosphere_{log_dir.name}", dirs_exist_ok=True)
    record["calls"].append({"call": call, "result": str(result), "time": datetime.now(timezone.utc).isoformat()})
    print("biosphere ->", result)

    if result is None:
        # Fallback documented in BrightPath's ATTRIBUTION.md for 3.11 -> 3.12.
        from ecoinvent_migrate.main import supplement_biosphere_changes_with_real_data_comparison

        data = supplement_biosphere_changes_with_real_data_comparison(
            data={"delete": [], "replace": []}, affected_uuids=set(), source_version="3.12", target_version="3.13"
        )
        out = RAW / "biosphere_supplement_only.json"
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        record["calls"].append(
            {
                "call": "supplement_biosphere_changes_with_real_data_comparison(data={'delete': [], 'replace': []}, "
                "affected_uuids=set(), source_version='3.12', target_version='3.13')",
                "result": str(out),
            }
        )

    record["finished"] = datetime.now(timezone.utc).isoformat()
    record["ecoinvent_migrate_module"] = ecoinvent_migrate.__file__
    (ROOT / "work" / "generation_record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
