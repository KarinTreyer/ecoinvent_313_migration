"""Turn the raw ecoinvent_migrate outputs into BrightPath-ready migration resources.

* Technosphere (cut-off): rule content is taken unchanged from ecoinvent_migrate; the file is only
  re-serialized with LF line endings (``json.dumps(indent=2, ensure_ascii=False) + "\\n"``), the
  convention of BrightPath's packaged files (the Windows run wrote CRLF).
* Biosphere: BrightPath's enrichment convention (``scripts/enrich_biosphere_migration_sources.py``):
  every rule source gets its exact Brightway ``(name, categories, unit)`` identity, resolved by UUID
  against the exact ecoinvent 3.12 biosphere (bw2io ``Ecospold2BiosphereImporter``) and verified by
  name; the upstream UUID (and formula) is retained.
  Additionally, and documented in PROVENANCE.md: ecoinvent_migrate 0.7.1 writes ecoSpold-style
  ``context`` lists (e.g. ``["air", "unspecified"]``) on the four 2-Propen-1-ol -> Allyl alcohol
  rules. BrightPath copies target fields verbatim onto exchanges and matches on Brightway
  ``categories``, so ``context`` is replaced by the exact Brightway ``categories``/``unit`` of the
  target UUID in the exact 3.13 biosphere (verified by name), and dropped from sources (whose
  enriched ``categories`` carry the same information). No rule is added, removed or re-targeted.

Run:  conda run -n esa_import python scripts/05_build_brightpath_resources.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ei_identity_lib import biosphere_by_uuid  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "work" / "raw"
OUT = ROOT / "output" / "brightpath" / "data" / "migrations" / "ecoinvent"
TECH = "ecoinvent-3.12-cutoff-ecoinvent-3.13-cutoff.json"
BIO = "ecoinvent-3.12-biosphere-ecoinvent-3.13-biosphere.json"
VERBS = ("replace", "delete", "disaggregate")


def dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def bw_identity(flow: dict) -> dict:
    return {"name": flow["name"], "categories": list(flow["categories"]), "unit": flow["unit"]}


def context_matches(context: list, categories: list) -> bool:
    """ecoSpold (compartment, subcompartment) vs Brightway categories (unspecified dropped)."""
    expected = [value for value in context if value not in {"unspecified", "(unspecified)", "", None}]
    return expected == list(categories)


def enrich_biosphere(payload: dict, source_index: dict, target_index: dict) -> list[str]:
    notes = []
    identities = set()
    for verb in VERBS:
        for index, rule in enumerate(payload.get(verb, ())):
            source = rule["source"]
            uuid = source["uuid"]
            flow = source_index.get(uuid)
            if flow is None:
                raise SystemExit(f"{verb}[{index}]: source UUID {uuid} not in exact 3.12 biosphere")
            if flow["name"] != source["name"]:
                raise SystemExit(f"{verb}[{index}]: source {uuid} named {source['name']!r}, 3.12 has {flow['name']!r}")
            if "context" in source and not context_matches(source["context"], flow["categories"]):
                raise SystemExit(f"{verb}[{index}]: source context {source['context']} != 3.12 {flow['categories']}")
            enriched = bw_identity(flow)
            enriched.update((k, v) for k, v in source.items() if k not in {"name", "categories", "unit", "context"})
            identity = (enriched["name"], tuple(enriched["categories"]), enriched["unit"])
            if identity in identities:
                raise SystemExit(f"repeated source identity {identity}")
            identities.add(identity)
            rule["source"] = enriched
            if "context" in source:
                notes.append(f"{verb}[{index}] source {uuid}: context {source['context']} -> categories {enriched['categories']}")

            target = rule.get("target")
            if target is None:
                continue
            target_uuid = target.get("uuid")
            target_flow = target_index.get(target_uuid)
            if target_flow is None:
                raise SystemExit(f"{verb}[{index}]: target UUID {target_uuid} not in exact 3.13 biosphere")
            expected_name = target.get("name", enriched["name"])
            if target_flow["name"] != expected_name:
                raise SystemExit(f"{verb}[{index}]: target {target_uuid} named {expected_name!r}, 3.13 has {target_flow['name']!r}")
            if "context" in target:
                if not context_matches(target["context"], target_flow["categories"]):
                    raise SystemExit(f"{verb}[{index}]: target context {target['context']} != 3.13 {target_flow['categories']}")
                new_target = bw_identity(target_flow)
                new_target.update((k, v) for k, v in target.items() if k not in {"name", "categories", "unit", "context"})
                rule["target"] = new_target
                notes.append(
                    f"{verb}[{index}] target {target_uuid}: context {target['context']} -> categories {new_target['categories']}, unit {new_target['unit']}"
                )
    return notes


def main() -> None:
    tech = json.loads((RAW / TECH).read_text(encoding="utf-8"))
    dump(OUT / "cutoff" / TECH, tech)
    print("technosphere:", {v: len(tech.get(v, [])) for v in VERBS})

    bio = json.loads((RAW / BIO).read_text(encoding="utf-8"))
    notes = enrich_biosphere(bio, biosphere_by_uuid("3.12"), biosphere_by_uuid("3.13"))
    bio["description"] = (
        bio["description"]
        + "; rule sources enriched with exact Brightway (name, categories, unit) identities resolved by UUID "
        "against the exact ecoinvent 3.12 biosphere (BrightPath convention); ecoSpold 'context' lists replaced "
        "by the exact Brightway categories of the same UUIDs"
    )
    dump(OUT / "biosphere" / BIO, bio)
    print("biosphere:", {v: len(bio.get(v, [])) for v in VERBS})
    for note in notes:
        print("  ", note)
    (ROOT / "work" / "biosphere_enrichment_notes.json").write_text(json.dumps(notes, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
