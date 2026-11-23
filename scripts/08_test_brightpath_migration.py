"""Synthetic-inventory test of BrightwayInventory.migrate_background ecoinvent 3.12 -> 3.13 cut-off.

Modes:
  installed  - BrightPath with the files installed into its package data (env ``bp_dev``, editable
               clone ``brightpath_pr`` after ``scripts/07_install_into_brightpath.py``).
  overlay    - unmodified BrightPath 1.0.0a14 (e.g. env ``esa_import``) via
               ``output/use_now/brightpath_ei313_overlay.py`` (process-local, nothing is written to the env).

Run:
  conda run -n bp_dev python scripts/08_test_brightpath_migration.py installed
  conda run -n esa_import python scripts/08_test_brightpath_migration.py overlay

Only identity metadata and made-up amounts are used; no ecoinvent inventory data.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
MODE = sys.argv[1] if len(sys.argv) > 1 else "installed"

provider = None
if MODE == "overlay":
    sys.path.insert(0, str(ROOT / "output" / "use_now"))
    from brightpath_ei313_overlay import enable_ecoinvent_313

    provider = enable_ecoinvent_313(Path(tempfile.gettempdir()) / "brightpath_ei313_overlay_test")

import brightpath  # noqa: E402
from brightpath import BrightwayInventory  # noqa: E402
from brightpath.core.context import BackgroundContext, BiosphereProfile, FormatProfile, InventoryContext, TechnosphereProfile  # noqa: E402
from brightpath.core.policies import MigrationPolicy, PolicyAction  # noqa: E402
from brightpath.exceptions import MigrationError  # noqa: E402
from brightpath.migrations.resources import available_ecoinvent_versions  # noqa: E402

print("brightpath", brightpath.__version__, "from", Path(brightpath.__file__).parent, "mode", MODE)
print("available cut-off versions:", available_ecoinvent_versions("cutoff"))


def ctx(version: str) -> BackgroundContext:
    return BackgroundContext(TechnosphereProfile("ecoinvent", version, "cutoff"), BiosphereProfile("ecoinvent", version))


def tech(name, product, location, unit, amount=1.0):
    return {"name": name, "reference product": product, "location": location, "unit": unit, "amount": amount, "type": "technosphere"}


def bio(name, categories, unit, amount=1.0):
    return {"name": name, "categories": tuple(categories), "unit": unit, "amount": amount, "type": "biosphere"}


def inventory(version: str, exchanges: list[dict]) -> BrightwayInventory:
    data = [{
        "name": "synthetic foreground process",
        "reference product": "synthetic product",
        "location": "CH",
        "unit": "unit",
        "comment": "synthetic test activity (made-up amounts)",
        "exchanges": [
            {"name": "synthetic foreground process", "reference product": "synthetic product", "location": "CH",
             "unit": "unit", "amount": 1.0, "type": "production"},
            *exchanges,
        ],
    }]
    return BrightwayInventory.from_data(
        data, context=InventoryContext(format=FormatProfile("brightway_excel"), background=ctx(version)), database_name="synthetic"
    )


def show(inv: BrightwayInventory) -> list[tuple]:
    rows = []
    for exc in inv.data[0]["exchanges"]:
        if exc["type"] == "production":
            continue
        if exc["type"] == "biosphere":
            rows.append(("biosphere", exc["name"], tuple(exc["categories"]), exc["unit"], round(exc["amount"], 6)))
        else:
            rows.append(("technosphere", exc["name"], exc["reference product"], exc["location"], exc["unit"], round(exc["amount"], 6)))
    return rows


def migrate(inv, target, policy=None):
    kwargs = {"catalog_provider": provider} if provider is not None else {}
    if policy is not None:
        kwargs["policy"] = policy
    return inv.migrate_background(target, **kwargs)


results = {"mode": MODE, "brightpath": brightpath.__version__, "cases": {}}

# ---- Case 1: strict policy; replace, disaggregate (obsolete GLO market), RoW split, biosphere rename, unchanged
case1 = [
    tech("calcined petroleum coke production", "calcined petroleum coke", "CN", "kilogram", 2.0),          # replace
    tech("market for seed-cotton", "seed-cotton", "GLO", "kilogram", 10.0),                                # disaggregate (obsolete)
    tech("electricity production, wind, 1-3MW turbine, onshore", "electricity, high voltage", "RoW", "kilowatt hour", 5.0),  # still-valid RoW split
    tech("market for electricity, low voltage", "electricity, low voltage", "CH", "kilowatt hour", 3.0),   # unchanged
    bio("2-Propen-1-ol", ("air",), "kilogram", 0.5),                                                       # renamed -> Allyl alcohol
    bio("2-Propen-1-ol", ("water", "surface water"), "kilogram", 0.25),                                    # renamed + subcompartment -> water
    bio("Dibutyltin", ("water", "ocean"), "kilogram", 0.1),                                        # formula-only rule (no-op)
    bio("Carbon dioxide, fossil", ("air",), "kilogram", 7.0),                                              # unchanged
]
inv = inventory("3.12", case1)
report = inv.validate(catalog_provider=provider) if provider else inv.validate()
print("source validation errors:", report.has_errors, [(i.code, i.message[:220]) for i in report.issues if str(getattr(i.severity, "value", i.severity)) == "error"][:8])
migrated = migrate(inv, ctx("3.13"))
after = show(migrated)
val = migrated.validate(catalog_provider=provider) if provider else migrated.validate()
issues = [(i.severity.value, i.code, i.message[:160]) for i in migrated.last_migration_report.issues]
print("CASE 1 migrated exchanges:")
for row in after:
    print("   ", row)
print("CASE 1 report issues:", issues)
print("CASE 1 target validation has errors:", val.has_errors, [(i.code, i.message[:220]) for i in val.issues if str(getattr(i.severity, "value", i.severity)) == "error"][:8])
seed = [r for r in after if r[0] == "technosphere" and r[1] == "market for seed-cotton"]
results["cases"]["1_strict"] = {
    "ok": not val.has_errors,
    "exchanges_after": after,
    "issues": issues,
    "seed_cotton_split_amount_sum": round(sum(r[5] for r in seed), 9),
    "seed_cotton_targets": len(seed),
}

# ---- Case 2: biosphere deletion (2-Propen-1-ol, soil, agricultural) under strict vs on_deletion=WARN
case2 = [bio("2-Propen-1-ol", ("soil", "agricultural"), "kilogram", 0.01), bio("Carbon dioxide, fossil", ("air",), "kilogram", 1.0)]
inv2 = inventory("3.12", case2)
try:
    migrate(inv2, ctx("3.13"))
    strict_outcome = "succeeded"
except MigrationError as error:
    strict_outcome = f"MigrationError: {str(error)[:200]}"
print("CASE 2 strict:", strict_outcome)
migrated2 = migrate(inv2, ctx("3.13"), MigrationPolicy(on_deletion=PolicyAction.WARN))
print("CASE 2 on_deletion=WARN:", show(migrated2))
results["cases"]["2_deletion"] = {"strict": strict_outcome, "warn_policy_exchanges_after": show(migrated2)}

# ---- Case 3: obsolete source without any rule (NL residual mix) -> must fail strictly
inv3 = inventory("3.12", [tech("electricity, low voltage, residual mix", "electricity, low voltage", "NL", "kilowatt hour", 1.0)])
try:
    migrate(inv3, ctx("3.13"))
    outcome3 = "succeeded (unexpected)"
except MigrationError as error:
    outcome3 = f"MigrationError (expected): {str(error)[:200]}"
print("CASE 3:", outcome3)
results["cases"]["3_unmapped_obsolete"] = outcome3

# ---- Case 4: chained 3.11 -> 3.13 route (uses the packaged 3.11->3.12 resource then the new one)
inv4 = inventory("3.11", [tech("4-methyl-2-pentanone production", "4-methyl-2-pentanone", "RER", "kilogram", 1.0),
                          tech("calcined petroleum coke production", "calcined petroleum coke", "CN", "kilogram", 1.0)])
try:
    migrated4 = migrate(inv4, ctx("3.13"))
    outcome4 = show(migrated4)
    steps = [str(getattr(s, "name", s))[:80] for s in getattr(migrated4.last_migration_report, "stages", ())]
except MigrationError as error:
    outcome4, steps = f"MigrationError: {str(error)[:300]}", []
print("CASE 4 (3.11 -> 3.13):", outcome4)
results["cases"]["4_chained_3.11_to_3.13"] = outcome4

out = ROOT / "work" / f"brightpath_test_{MODE}.json"
out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
print("wrote", out)
