"""Use the ecoinvent 3.12 -> 3.13 resources with an UNMODIFIED BrightPath 1.0.0a14 installation.

BrightPath 1.0.0a14 has a supported hook for external *catalogs* (``catalog_provider=`` argument or the
``BRIGHTPATH_REFERENCE_DIR`` environment variable), but NOT for external *migration resources*: they are
only discovered under ``brightpath/data/migrations`` and must match ``RESOURCE_MANIFEST.json``.

This helper is an explicit, process-local workaround (not a BrightPath API): it builds an overlay copy of
the installed ``data/migrations`` folder in a directory you choose, adds the two new migration files and
their manifest entries there, and points ``brightpath.migrations.resources.DATA_DIR`` at the overlay for
the current Python process only. The installed package is never written to. Remove it once the files
are part of a BrightPath release.

Usage in a notebook (any env with brightpath 1.0.0a14):

    import sys; sys.path.insert(0, r"C:/Users/treyer_k/Documents/GitHub/ecoinvent_313_migration/output/use_now")
    from brightpath_ei313_overlay import enable_ecoinvent_313
    provider = enable_ecoinvent_313()          # returns a CatalogProvider including the 3.13 catalog

    from brightpath import BrightwayInventory, BackgroundContext, TechnosphereProfile, BiosphereProfile
    inv = BrightwayInventory.from_excel("my_inventory_ei312.xlsx", context=...)   # ecoinvent 3.12 cutoff
    target = BackgroundContext(TechnosphereProfile("ecoinvent", "3.13", "cutoff"), BiosphereProfile("ecoinvent", "3.13"))
    migrated = inv.migrate_background(target, catalog_provider=provider)
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESOURCES = HERE.parent / "brightpath" / "data"
MIGRATIONS = [
    "ecoinvent/cutoff/ecoinvent-3.12-cutoff-ecoinvent-3.13-cutoff.json",
    "ecoinvent/biosphere/ecoinvent-3.12-biosphere-ecoinvent-3.13-biosphere.json",
]
CATALOG = "ecoinvent__3.13__cutoff.json"


def _migration_entry(path: Path, relative: str) -> dict:
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
        "licenses": sorted(str(i.get("name")) for i in payload.get("licenses", ()) if isinstance(i, dict) and i.get("name")),
    }


def enable_ecoinvent_313(overlay_dir: str | Path | None = None):
    """Activate the overlay for this process and return a catalog provider that includes ecoinvent 3.13."""
    import brightpath
    import brightpath.migrations.resources as resources
    from brightpath.background.catalogs import CompositeCatalogProvider, DirectoryCatalogProvider, PackageCatalogProvider

    overlay = Path(overlay_dir) if overlay_dir else Path.home() / ".brightpath_ei313_overlay" / brightpath.__version__
    installed = Path(brightpath.DATA_DIR)
    migrations = overlay / "migrations"
    if migrations.exists():
        shutil.rmtree(migrations)
    shutil.copytree(installed / "migrations", migrations)
    for relative in MIGRATIONS:
        target = migrations / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RESOURCES / "migrations" / relative, target)
    manifest_path = migrations / "RESOURCE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    new = [_migration_entry(migrations / rel, rel) for rel in MIGRATIONS]
    manifest["resources"] = sorted(
        [r for r in manifest["resources"] if r["path"] not in {e["path"] for e in new}] + new, key=lambda r: r["path"]
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    catalogs = overlay / "reference_catalogs"
    catalogs.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RESOURCES / "export" / "reference_catalogs" / CATALOG, catalogs / CATALOG)
    raw = (catalogs / CATALOG).read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    catalog_manifest = {
        "schema_version": 1,
        "status": "legal_review_required",
        "description": "Overlay catalog manifest for the ecoinvent 3.13 cut-off catalog (not part of BrightPath).",
        "generator": "brightpath_ei313_overlay.py",
        "resources": [
            {
                "file": CATALOG,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
                "schema_version": int(payload.get("schema_version", 1)),
                "profile": payload["profile"],
                "technosphere_identities": len(payload["technosphere"]),
                "biosphere_identities": len(payload["biosphere"]),
                "technosphere_uuid_references": sum(bool(r.get("activity_id") and r.get("flow_id")) for r in payload["technosphere"]),
                "biosphere_uuid_references": sum(bool(r.get("flow_id")) for r in payload["biosphere"]),
            }
        ],
    }
    (catalogs / "RESOURCE_MANIFEST.json").write_text(json.dumps(catalog_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    import brightpath.background.patches as patches

    # Process-local redirect of migration-resource discovery. Both modules bind DATA_DIR at import time and
    # verify every resource path against data/migrations/RESOURCE_MANIFEST.json.
    resources.DATA_DIR = overlay
    patches.DATA_DIR = overlay
    for cached in (
        resources.load_technosphere_resources,
        resources.load_biosphere_resources,
        resources.load_uvek_technosphere_resource,
        resources.load_uvek_biosphere_resource,
        resources.load_uvek_release_resources,
        resources._load_resource_manifest,
        patches.compatibility_resource,
    ):
        cached.cache_clear()
    if "3.13" not in resources.available_ecoinvent_versions("cutoff"):
        raise RuntimeError("Overlay did not expose ecoinvent 3.13")
    # The overlay catalog folder has its own RESOURCE_MANIFEST.json, so the 3.13 catalog is integrity-checked
    # like packaged catalogs. Equivalent alternative: set BRIGHTPATH_REFERENCE_DIR to that folder.
    return CompositeCatalogProvider((DirectoryCatalogProvider(catalogs), PackageCatalogProvider()))
