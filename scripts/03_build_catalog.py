"""Build a BrightPath schema-version-2 reference catalog from a licensed ecoSpold2 release.

Usage (from the repository root):
    conda run -n esa_import python scripts/03_build_catalog.py 3.12 --compare <packaged 3.12 catalog>
    conda run -n esa_import python scripts/03_build_catalog.py 3.13

The 3.12 run is a reproducibility check: the output must be byte-identical to BrightPath's packaged
``ecoinvent__3.12__cutoff.json``. Only identity metadata (names, products, locations, units,
categories, UUIDs) is written; never amounts or LCIA factors.

Serialization follows BrightPath's ``scripts/enrich_reference_catalog_uuids.py``:
``json.dumps(payload, indent=2, sort_keys=True) + "\\n"`` (ASCII-escaped), rows sorted by identity.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ei_identity_lib import biosphere_flows, technosphere_identities  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def add_unique(target: dict, identity: tuple, reference, source: str) -> None:
    if not all(identity) or not reference or (isinstance(reference, tuple) and not all(reference)):
        raise ValueError(f"Missing identity or UUID in {source}: {identity!r} -> {reference!r}")
    previous = target.setdefault(identity, reference)
    if previous != reference:
        raise ValueError(f"Ambiguous UUID references in {source} for {identity!r}: {previous!r} != {reference!r}")


def build(version: str, system_model: str = "cutoff") -> dict:
    technosphere = {}
    for row in technosphere_identities(version, system_model):
        add_unique(
            technosphere,
            (row["name"], row["reference product"], row["location"], row["unit"]),
            (row["activity"], row["flow"]),
            f"ecoinvent {version} {system_model}",
        )
    biosphere = {}
    for flow in biosphere_flows(version):
        add_unique(
            biosphere,
            (flow["name"], tuple(flow["categories"]), flow["unit"]),
            str(flow["code"]),
            f"ecoinvent {version} biosphere",
        )
    return {
        "schema_version": 2,
        "profile": {"family": "ecoinvent", "version": version, "system_model": system_model},
        "technosphere": [
            {
                "name": n,
                "reference_product": rp,
                "location": loc,
                "unit": u,
                "activity_id": technosphere[(n, rp, loc, u)][0],
                "flow_id": technosphere[(n, rp, loc, u)][1],
            }
            for n, rp, loc, u in sorted(technosphere)
        ],
        "biosphere": [
            {"name": n, "categories": list(c), "unit": u, "flow_id": biosphere[(n, c, u)]}
            for n, c, u in sorted(biosphere)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--system-model", default="cutoff")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare", type=Path, help="Reference catalog that must be byte-identical")
    args = parser.parse_args()

    payload = build(args.version, args.system_model)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    default_dir = ROOT / ("work" if args.compare else "output/brightpath/data/export/reference_catalogs")
    output = args.output or default_dir / f"ecoinvent__{args.version}__{args.system_model}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    print(
        f"wrote {output}: {len(payload['technosphere'])} technosphere, {len(payload['biosphere'])} biosphere, "
        f"sha256={hashlib.sha256(encoded).hexdigest()} size={len(encoded)}"
    )
    if args.compare:
        reference = args.compare.read_bytes()
        if reference == encoded:
            print("IDENTICAL to", args.compare)
        else:
            ref = json.loads(reference)
            for key in ("technosphere", "biosphere"):
                a = {json.dumps(r, sort_keys=True) for r in ref[key]}
                b = {json.dumps(r, sort_keys=True) for r in payload[key]}
                print(key, "only in reference:", len(a - b), "only in rebuilt:", len(b - a))
                for item in sorted(a - b)[:5]:
                    print("  ref  ", item)
                for item in sorted(b - a)[:5]:
                    print("  built", item)
            raise SystemExit("DIFFERENT from reference catalog")


if __name__ == "__main__":
    main()
