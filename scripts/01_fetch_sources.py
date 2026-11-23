"""Fetch (or reuse from cache) the licensed ecoinvent sources needed for the 3.12 -> 3.13 resources.

Uses ecoinvent_interface with credentials stored via ``permanent_setting`` (``Settings()``).
No credentials are read, printed or written by this script.

Writes ``work/sources.json`` with the local paths, archive names and SHA-256 digests of every
source file (ecoSpold archives, MasterData XML, change report annex, correspondence file).
The licensed files themselves stay in the ecoinvent_interface cache and are never copied here.

Run:  conda run -n esa_import python scripts/01_fetch_sources.py
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from ecoinvent_interface import CachedStorage, EcoinventRelease, ReleaseType, Settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
WORK.mkdir(exist_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def describe(path: Path) -> dict:
    return {"path": str(path), "name": path.name, "size": path.stat().st_size, "sha256": sha256(path)}


def main() -> None:
    release = EcoinventRelease(Settings())
    versions = release.list_versions()
    for needed in ("3.12", "3.13"):
        if needed not in versions:
            raise SystemExit(f"Licence does not list ecoinvent {needed}: {versions}")

    record: dict = {"fetched": datetime.now(timezone.utc).isoformat(), "releases": {}, "extras": {}}
    cache = CachedStorage()
    for version in ("3.12", "3.13"):
        directory = release.get_release(version, "cutoff", ReleaseType.ecospold)
        archive_name = ReleaseType.ecospold.filename(version=version, system_model_abbr="cutoff")
        archive = Path(cache.dir) / archive_name
        master = Path(directory) / "MasterData"
        datasets = Path(directory) / "datasets"
        record["releases"][version] = {
            "directory": str(directory),
            "archive": describe(archive) if archive.is_file() else {"name": archive_name, "note": "archive not kept"},
            "dataset_files": sum(1 for p in datasets.iterdir() if p.suffix.lower() == ".spold"),
            "master_data": {
                name: describe(master / name)
                for name in ("ElementaryExchanges.xml", "IntermediateExchanges.xml", "ActivityNames.xml", "Geographies.xml")
                if (master / name).is_file()
            },
        }
        print(version, "->", directory)

    extras = release.list_extra_files("3.13")
    print("3.13 extra files:", sorted(extras))
    wanted = [
        name
        for name in extras
        if ("change report" in name.lower() and "annex" in name.lower()) or "correspondence file" in name.lower()
    ]
    for name in wanted:
        target = Path(release.get_extra("3.13", name))
        archive = Path(cache.dir) / name
        files = [target] if target.is_file() else sorted(p for p in target.rglob("*") if p.is_file())
        record["extras"][name] = {
            "archive": describe(archive) if archive.is_file() else None,
            "files": [describe(p) for p in files],
        }
        print(name, "->", [p.name for p in files])

    out = WORK / "sources.json"
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
