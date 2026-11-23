"""Copy the three new resources into a BrightPath package directory and add their manifest entries.

Usage:
    python scripts/07_install_into_brightpath.py <path/to/brightpath>   # the package dir containing data/
    python scripts/07_install_into_brightpath.py --snippets-only

Manifest entries are computed exactly like BrightPath's ``scripts/generate_migration_manifest.py`` and
``scripts/generate_catalog_manifest.py`` but *inserted* (sorted like the generators sort) instead of
regenerating the whole manifests: upstream ``main`` lists ``ecoinvent__3.10.1__consequential.json`` in
the catalog manifest although that file is git-ignored/untracked, so a blind regeneration in a fresh
clone would silently drop that entry. Existing entries are never modified. Manifests are written with
LF line endings (``json.dumps(..., indent=2, sort_keys=True) + "\\n"``).

Also writes ``output/manifest_snippets/*.json`` (the entries to add in a PR).
Only the standard library is used, so any Python >= 3.10 works.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "output" / "brightpath" / "data"
MIGRATIONS = [
    "ecoinvent/cutoff/ecoinvent-3.12-cutoff-ecoinvent-3.13-cutoff.json",
    "ecoinvent/biosphere/ecoinvent-3.12-biosphere-ecoinvent-3.13-biosphere.json",
]
CATALOGS = ["ecoinvent__3.13__cutoff.json"]


def migration_entry(path: Path, relative: str) -> dict:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    return {
        "path": relative,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
        "schema_version": int(payload.get("schema_version", 1)),
        "name": str(payload.get("name") or ""),
        "status": str(payload.get("status") or "active"),
        "source_id": str(payload.get("source_id") or ""),
        "target_id": str(payload.get("target_id") or ""),
        "licenses": sorted(
            str(item.get("name") or "") for item in payload.get("licenses", ()) if isinstance(item, dict) and item.get("name")
        ),
    }


def catalog_entry(path: Path) -> dict:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    profile = payload["profile"]
    tech, bio = payload.get("technosphere", ()), payload.get("biosphere", ())
    return {
        "file": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
        "schema_version": int(payload.get("schema_version", 1)),
        "profile": {k: str(profile[k]) for k in ("family", "version", "system_model")},
        "technosphere_identities": len(tech),
        "biosphere_identities": len(bio),
        "technosphere_uuid_references": sum(bool(r.get("activity_id") and r.get("flow_id")) for r in tech),
        "biosphere_uuid_references": sum(bool(r.get("flow_id")) for r in bio),
    }


def upsert(manifest_path: Path, entries: list[dict], key: str) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    resources = [r for r in manifest["resources"] if r[key] not in {e[key] for e in entries}]
    resources.extend(entries)
    resources.sort(key=lambda r: r[key])
    manifest["resources"] = resources
    manifest_path.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", nargs="?", type=Path, help="BrightPath package directory (contains data/)")
    parser.add_argument("--snippets-only", action="store_true")
    args = parser.parse_args()

    migration_entries = [migration_entry(SRC / "migrations" / rel, rel) for rel in MIGRATIONS]
    catalog_entries = [catalog_entry(SRC / "export" / "reference_catalogs" / name) for name in CATALOGS]
    snippets = ROOT / "output" / "manifest_snippets"
    snippets.mkdir(parents=True, exist_ok=True)
    (snippets / "migrations_RESOURCE_MANIFEST.entries.json").write_text(
        json.dumps(migration_entries, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (snippets / "reference_catalogs_RESOURCE_MANIFEST.entries.json").write_text(
        json.dumps(catalog_entries, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print("snippets written to", snippets)
    if args.snippets_only:
        return
    if args.package is None:
        sys.exit("package directory required")
    data = args.package / "data"
    if not (data / "migrations" / "RESOURCE_MANIFEST.json").is_file():
        sys.exit(f"{data} does not look like a BrightPath data directory")
    for rel in MIGRATIONS:
        target = data / "migrations" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SRC / "migrations" / rel, target)
    for name in CATALOGS:
        shutil.copyfile(SRC / "export" / "reference_catalogs" / name, data / "export" / "reference_catalogs" / name)
    upsert(data / "migrations" / "RESOURCE_MANIFEST.json", migration_entries, "path")
    upsert(data / "export" / "reference_catalogs" / "RESOURCE_MANIFEST.json", catalog_entries, "file")
    print("installed into", data)


if __name__ == "__main__":
    main()
