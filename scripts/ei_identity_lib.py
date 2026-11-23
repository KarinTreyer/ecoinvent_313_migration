"""Shared helpers: read Brightway-equivalent identity metadata from licensed ecoSpold2 releases.

The identities reproduce what ``bw2io.import_ecoinvent_release`` stores in Brightway, which is how
BrightPath's ``scripts/generate_reference_catalogs.py`` builds its packaged catalogs:

* technosphere: ``(name, reference product, location, unit)`` plus ``activity_id`` / ``flow_id``,
  after bw2io's ``normalize_units``, ``update_ecoinvent_locations`` and
  ``es2_assign_only_product_with_amount_as_reference_product`` strategies;
* biosphere: ``Ecospold2BiosphereImporter`` with its strategies (``normalize_units``,
  ``drop_unspecified_subcategories``, ``ensure_categories_are_tuples``), keyed by flow UUID.

Only identity metadata is read. No exchange amounts or other inventory values are kept.
``scripts/03_build_catalog.py --check-3.12`` proves byte-identity with BrightPath's packaged
3.12 catalog, i.e. that this reader is equivalent to the upstream Brightway route.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# Keep bw2data (imported by bw2io) away from the user's real Brightway projects.
_BW_SCRATCH = Path(tempfile.gettempdir()) / "bw_ei313_identity_scratch"
_BW_SCRATCH.mkdir(exist_ok=True)
os.environ.setdefault("BRIGHTWAY2_DIR", str(_BW_SCRATCH))

from lxml import etree  # noqa: E402

NS = "{http://www.EcoInvent.org/EcoSpold02}"


def release_directory(version: str, system_model: str = "cutoff") -> Path:
    from ecoinvent_interface import CachedStorage, ReleaseType

    key = ReleaseType.ecospold.filename(version=version, system_model_abbr=system_model)
    entry = CachedStorage().catalogue[key]
    path = Path(entry["path"])
    if not (path / "datasets").is_dir():
        raise FileNotFoundError(f"ecoinvent {version} {system_model} not extracted at {path}")
    return path


def _text(element, path: str) -> str:
    found = element.find(path)
    return found.text if found is not None and found.text is not None else ""


def read_dataset_identity(path: Path) -> dict:
    """Return the Brightway identity of one single-output ecoSpold2 dataset (before strategies)."""
    root = etree.parse(str(path)).getroot()
    stem = root.find(NS + "activityDataset")
    if stem is None:
        stem = root.find(NS + "childActivityDataset")
    activity = stem.find(f"{NS}activityDescription/{NS}activity")
    geography = stem.find(f"{NS}activityDescription/{NS}geography")
    products = []
    for exchange in stem.find(NS + "flowData").findall(NS + "intermediateExchange"):
        group = exchange.find(NS + "outputGroup")
        if group is not None and group.text == "0":
            products.append(
                {
                    "name": _text(exchange, NS + "name"),
                    "unit": _text(exchange, NS + "unitName"),
                    "amount": float(exchange.get("amount")),
                    "flow": exchange.get("intermediateExchangeId"),
                }
            )
    with_amount = [p for p in products if p["amount"] != 0]
    if len(with_amount) != 1:
        raise ValueError(f"{path.name}: expected one reference product with non-zero amount, got {len(with_amount)}")
    product = with_amount[0]
    return {
        "name": _text(activity, NS + "activityName"),
        "reference product": product["name"],
        "location": _text(geography, NS + "shortname"),
        "unit": product["unit"],
        "activity": activity.get("id"),
        "flow": product["flow"],
        "filename": path.name,
        "exchanges": [],
    }


def technosphere_identities(version: str, system_model: str = "cutoff") -> list[dict]:
    """Read every dataset of a release and apply bw2io's identity-relevant strategies."""
    from bw2io.strategies import normalize_units, update_ecoinvent_locations

    directory = release_directory(version, system_model) / "datasets"
    data = [read_dataset_identity(p) for p in sorted(directory.iterdir()) if p.suffix.lower() == ".spold"]
    data = normalize_units(data)
    data = update_ecoinvent_locations(data)
    return data


def biosphere_flows(version: str) -> list[dict]:
    """Return bw2io's processed biosphere flows (name, categories, unit, code=UUID, formula, CAS)."""
    from bw2io.importers.ecospold2_biosphere import Ecospold2BiosphereImporter

    path = release_directory(version) / "MasterData" / "ElementaryExchanges.xml"
    importer = Ecospold2BiosphereImporter(name=f"ecoinvent-{version}-biosphere", filepath=path)
    importer.apply_strategies()
    return [dict(flow) for flow in importer.data]


def biosphere_by_uuid(version: str) -> dict[str, dict]:
    index = {}
    for flow in biosphere_flows(version):
        code = str(flow["code"])
        if code in index:
            raise ValueError(f"Duplicate biosphere UUID {code} in ecoinvent {version}")
        index[code] = flow
    return index


def write_json(path: Path, payload, *, indent=2, sort_keys=True) -> None:
    path.write_text(json.dumps(payload, indent=indent, sort_keys=sort_keys, ensure_ascii=False) + "\n", encoding="utf-8")
