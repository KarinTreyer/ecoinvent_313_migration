"""Validate the ecoinvent 3.12 -> 3.13 BrightPath resources (task 4 checks a-d).

(a) every rule source identity exists in the exact 3.12 catalog and every target in the 3.13 catalog
    (names, products, locations, categories exact and case-sensitive; ecoSpold units compared after
    bw2io's ``normalize_units`` function - the same mapping that produced the catalogs - e.g. kg -> kilogram;
    biosphere UUIDs must also equal the catalog flow_id);
(b) disaggregation allocations per source sum to 1;
(c) co-product gap pattern: a rule covers one product of a multi-output activity while a sibling
    product of the same 3.12 activity disappears from 3.13 without any rule (demonstrated on the
    packaged 3.11 -> 3.12 resource first, where it must find the chlor-alkali sodium hydroxide case);
(d) cross-check against ecoinvent's 'Correspondence File v3.12 - v3.13.xlsx' (cut-off sheet), joined
    on exact (activity UUID, product UUID) pairs.

Writes ``work/validation_results.json`` and proposals (NOT applied) to
``output/proposed_supplements/``.

Run:  conda run -n esa_import python scripts/06_validate.py <path to BrightPath package dir>
"""

from __future__ import annotations

import io
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "brightpath" / "data"
TECH = OUT / "migrations/ecoinvent/cutoff/ecoinvent-3.12-cutoff-ecoinvent-3.13-cutoff.json"
BIO = OUT / "migrations/ecoinvent/biosphere/ecoinvent-3.12-biosphere-ecoinvent-3.13-biosphere.json"
CAT13 = OUT / "export/reference_catalogs/ecoinvent__3.13__cutoff.json"
CAT12_REBUILT = ROOT / "work" / "ecoinvent__3.12__cutoff.json"

try:
    from bw2io.units import normalize_units as normalize_units_function
except Exception:  # pragma: no cover
    raise SystemExit("bw2io is required (esa_import env)")


def nu(unit: str) -> str:
    return normalize_units_function(unit)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tkey(d: dict) -> tuple:
    """Technosphere identity of a rule side, unit normalized to the Brightway alias."""
    return (d["name"], d["reference product"], d["location"], nu(d["unit"]))


def cat_tech(catalog: dict):
    rows = {}
    by_ref = {}
    by_activity = defaultdict(list)
    for r in catalog["technosphere"]:
        key = (r["name"], r["reference_product"], r["location"], r["unit"])
        rows[key] = r
        by_ref[(r["activity_id"], r["flow_id"])] = key
        by_activity[r["activity_id"]].append(key)
    return rows, by_ref, by_activity


def cat_bio(catalog: dict):
    return {(r["name"], tuple(r["categories"]), r["unit"]): r["flow_id"] for r in catalog["biosphere"]}


def rule_targets(resource: dict) -> dict:
    """source identity -> (verb, [target identities], rule)"""
    result = {}
    for rule in resource.get("replace", []):
        result[tkey(rule["source"])] = ("replace", [tkey(rule["target"])], rule)
    for rule in resource.get("disaggregate", []):
        key = tkey(rule["source"])
        if key in result:
            raise SystemExit(f"source in both replace and disaggregate: {key}")
        result[key] = ("disaggregate", [tkey(t) for t in rule["targets"]], rule)
    return result


def fmt(key: tuple) -> str:
    return " | ".join(str(k) for k in key)


def coproduct_gaps(rules: dict, cat_src, cat_dst_rows) -> list[dict]:
    rows, _, by_activity = cat_src
    activity_of = {key: rows[key]["activity_id"] for key in rows}
    gaps = []
    for source in sorted(rules):
        activity = activity_of.get(source)
        if activity is None:
            continue
        for sibling in sorted(by_activity[activity]):
            if sibling == source or sibling in rules or sibling in cat_dst_rows:
                continue
            gaps.append({"covered_source": fmt(source), "covered_by": rules[source][0], "uncovered_sibling": fmt(sibling),
                         "sibling": list(sibling), "activity_id": activity})
    # de-duplicate siblings (several covered products of one activity)
    seen, unique = set(), []
    for gap in gaps:
        if gap["uncovered_sibling"] not in seen:
            seen.add(gap["uncovered_sibling"])
            unique.append(gap)
    return unique


def main() -> None:
    package = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    results: dict = {}

    tech, bio = load(TECH), load(BIO)
    cat12, cat13 = load(CAT12_REBUILT), load(CAT13)
    if package:
        packaged12 = (package / "data/export/reference_catalogs/ecoinvent__3.12__cutoff.json").read_bytes()
        results["catalog_3_12_rebuilt_identical_to_packaged"] = packaged12 == CAT12_REBUILT.read_bytes()
    t12 = cat_tech(cat12)
    t13 = cat_tech(cat13)
    rows12, ref12, _ = t12
    rows13, ref13, _ = t13
    b12, b13 = cat_bio(cat12), cat_bio(cat13)

    # ---------------- (a) identities -----------------
    rules = rule_targets(tech)
    a = {"technosphere": {}, "biosphere": {}}
    missing_src = [fmt(s) for s in rules if s not in rows12]
    missing_tgt = sorted({fmt(t) for s, (_, ts, _) in rules.items() for t in ts if t not in rows13})
    unit_alias = Counter((r["source"]["unit"], nu(r["source"]["unit"])) for v in ("replace", "disaggregate") for r in tech.get(v, []))
    a["technosphere"] = {
        "rules": {v: len(tech.get(v, [])) for v in ("replace", "disaggregate", "delete")},
        "target_identities": sum(len(ts) for _, ts, _ in rules.values()),
        "sources_missing_from_3.12_catalog": missing_src,
        "targets_missing_from_3.13_catalog": missing_tgt,
        "unit_aliases_used": {f"{k[0]} -> {k[1]}": n for k, n in unit_alias.items()},
        "sources_still_present_in_3.13": sorted(fmt(s) for s in rules if s in rows13),
    }
    bio_issues = []
    bio_rules = []
    for verb in ("replace", "delete", "disaggregate"):
        for i, rule in enumerate(bio.get(verb, [])):
            s = rule["source"]
            sid = (s["name"], tuple(s["categories"]), s["unit"])
            if sid not in b12:
                bio_issues.append(f"{verb}[{i}] source not in 3.12 catalog: {sid}")
            elif b12[sid] != s.get("uuid"):
                bio_issues.append(f"{verb}[{i}] source UUID {s.get('uuid')} != 3.12 catalog {b12[sid]}")
            if verb == "replace":
                t = rule["target"]
                tid = (t.get("name", s["name"]), tuple(t.get("categories", s["categories"])), t.get("unit", s["unit"]))
                if tid not in b13:
                    bio_issues.append(f"{verb}[{i}] target not in 3.13 catalog: {tid}")
                elif t.get("uuid") and b13[tid] != t["uuid"]:
                    bio_issues.append(f"{verb}[{i}] target UUID {t['uuid']} != 3.13 catalog {b13[tid]}")
                bio_rules.append((sid, tid))
            else:
                bio_rules.append((sid, None))
    covered_bio = {sid for sid, _ in bio_rules}
    obsolete_bio = sorted(set(b12) - set(b13))
    uuid12 = {v: k for k, v in b12.items()}
    uuid13 = {v: k for k, v in b13.items()}
    a["biosphere"] = {
        "rules": {v: len(bio.get(v, [])) for v in ("replace", "delete", "disaggregate")},
        "issues": bio_issues,
        "identity_changing_replace_rules": sum(1 for s, t in bio_rules if t is not None and s != t),
        "identity_preserving_replace_rules (formula-only)": sum(1 for s, t in bio_rules if t is not None and s == t),
        "obsolete_3.12_identities": len(obsolete_bio),
        "obsolete_identities_without_rule": [list(k) for k in obsolete_bio if k not in covered_bio],
        "uuids_removed_in_3.13": len(set(uuid12) - set(uuid13)),
        "uuids_added_in_3.13": len(set(uuid13) - set(uuid12)),
        "same_uuid_identity_changed": [
            {"uuid": u, "3.12": list(uuid12[u]), "3.13": list(uuid13[u])} for u in sorted(set(uuid12) & set(uuid13)) if uuid12[u] != uuid13[u]
        ],
    }

    # obsolete technosphere identities coverage
    obsolete_tech = sorted(set(rows12) - set(rows13))
    a["technosphere"]["obsolete_3.12_identities"] = len(obsolete_tech)
    a["technosphere"]["obsolete_identities_without_rule"] = [fmt(k) for k in obsolete_tech if k not in rules]
    results["a_identities"] = a

    # ---------------- (b) allocations -----------------
    b = []
    for rule in tech.get("disaggregate", []):
        allocations = [t.get("allocation") for t in rule["targets"]]
        total = sum(x for x in allocations if x is not None)
        b.append({
            "source": fmt(tkey(rule["source"])),
            "targets": len(allocations),
            "sum": total,
            "ok": all(x is not None and x > 0 for x in allocations) and math.isclose(total, 1.0, rel_tol=1e-9, abs_tol=1e-9),
            "comment": rule.get("comment", ""),
            "duplicate_targets": len(allocations) != len({tkey(t) for t in rule["targets"]}),
        })
    results["b_allocations"] = {
        "rules": len(b),
        "sum_to_one": sum(x["ok"] for x in b),
        "max_abs_deviation": max((abs(x["sum"] - 1) for x in b), default=0.0),
        "failures": [x for x in b if not x["ok"]],
        "with_duplicate_targets": [x["source"] for x in b if x["duplicate_targets"]],
        "equal_allocation_fallbacks": [x for x in b if x["comment"]],
    }

    # ---------------- (c) co-product gaps -----------------
    c = {"3.12->3.13": coproduct_gaps(rules, t12, rows13)}
    if package:
        cat11 = load(package / "data/export/reference_catalogs/ecoinvent__3.11__cutoff.json")
        pkg12 = load(package / "data/export/reference_catalogs/ecoinvent__3.12__cutoff.json")
        res1112 = load(package / "data/migrations/ecoinvent/cutoff/ecoinvent-3.11-cutoff-ecoinvent-3.12-cutoff.json")
        gaps1112 = coproduct_gaps(rule_targets(res1112), cat_tech(cat11), cat_tech(pkg12)[0])
        c["3.11->3.12 (method check on packaged resource)"] = gaps1112
        c["3.11->3.12 detects chlor-alkali NaOH"] = any(
            "chlor-alkali electrolysis, diaphragm cell" in g["uncovered_sibling"] and "sodium hydroxide" in g["uncovered_sibling"]
            for g in gaps1112
        )
    results["c_coproduct_gaps"] = c

    # ---------------- (d) correspondence -----------------
    corr = load(ROOT / "work" / "correspondence_cutoff.json")["records"]
    corr_targets = defaultdict(set)
    corr_rows = defaultdict(list)
    unmatched_rows = 0
    for rec in corr:
        s, t = rec["source"], rec["target"]
        skey = ref12.get((s["activity_id"], s["product_id"])) if s else None
        tkey_ = ref13.get((t["activity_id"], t["product_id"])) if t else None
        if (s and skey is None) or (t and tkey_ is None):
            unmatched_rows += 1
            continue
        if skey is not None:
            corr_rows[skey].append(rec)
            if tkey_ is not None:
                corr_targets[skey].add(tkey_)
    d = {"rows": len(corr), "rows_not_matched_to_catalog_uuids": unmatched_rows}
    categories = defaultdict(list)
    for source in sorted(rows12):
        C = corr_targets.get(source, set())
        rule = rules.get(source)
        R = set(rule[1]) if rule else set()
        obsolete = source not in rows13
        entry = {"source": fmt(source), "rule": rule[0] if rule else None,
                 "rule_targets": sorted(fmt(x) for x in R), "correspondence_targets": sorted(fmt(x) for x in C)}
        if obsolete:
            if rule and R == C:
                cat = "obsolete: rule agrees with correspondence"
            elif rule and not C:
                cat = "obsolete: rule, correspondence has no target"
            elif rule and R & C:
                cat = "obsolete: rule partially agrees (target sets differ)"
            elif rule:
                cat = "obsolete: rule CONTRADICTS correspondence"
            elif C:
                cat = "obsolete: NO RULE but correspondence has target(s)"
            else:
                cat = "obsolete: no rule, deleted without correspondence target"
        else:
            if rule and R == C:
                cat = "still valid: rule agrees with correspondence"
            elif rule and R & C:
                cat = "still valid: rule partially agrees (target sets differ)"
            elif rule:
                cat = "still valid: rule CONTRADICTS correspondence"
            elif C == {source}:
                cat = "still valid: identity (no rule needed)"
            elif source in C:
                cat = "still valid: correspondence also lists other targets (split), no rule"
            elif C:
                cat = "still valid: correspondence maps elsewhere, no rule"
            else:
                cat = "still valid: no correspondence row"
        categories[cat].append(entry)
    d["counts"] = {k: len(v) for k, v in sorted(categories.items())}
    for k, v in categories.items():
        if k != "still valid: identity (no rule needed)":
            d[k] = v
    results["d_correspondence"] = d

    # ---------------- proposals (not applied) -----------------
    unit_raw = {}
    for rec in corr:
        for side, ref in (("source", ref12), ("target", ref13)):
            x = rec[side]
            if x:
                key = ref.get((x["activity_id"], x["product_id"]))
                if key:
                    unit_raw[key] = x["unit"]

    def side_dict(key):
        return {"unit": unit_raw.get(key, key[3]), "name": key[0], "reference product": key[1], "location": key[2]}

    proposals = {"replace": [], "disaggregate": []}
    for entry in categories.get("obsolete: NO RULE but correspondence has target(s)", []):
        source = next(k for k in rows12 if fmt(k) == entry["source"])
        targets = sorted(corr_targets[source])
        flags = [r["flags"] for r in corr_rows[source]]
        review = {
            "status": "proposed - requires review, not applied",
            "evidence": "ecoinvent 'Correspondence File v3.12 - v3.13.xlsx', sheet 'Cut-off', rows joined on exact "
            "3.12/3.13 (activity UUID, product UUID)",
            "correspondence_flags": flags,
            "source_ids": [rows12[source]["activity_id"], rows12[source]["flow_id"]],
            "target_ids": [[rows13[t]["activity_id"], rows13[t]["flow_id"]] for t in targets],
        }
        if len(targets) == 1:
            proposals["replace"].append({"source": side_dict(source), "target": side_dict(targets[0]), "brightpath_review": review})
        else:
            proposals["disaggregate"].append({
                "source": side_dict(source),
                "targets": [side_dict(t) | {"allocation": None} for t in targets],
                "brightpath_review": review | {"allocation": "not determined - needs production-volume shares or reviewer decision"},
            })
    # (c2) non-breaking co-product asymmetry: a rule splits a still-valid reference product of a
    # multi-output activity across new geographies, while a sibling co-product of the same activity
    # (also still valid) keeps its old link although the correspondence file lists the same split.
    _, _, by_activity12 = t12
    asymmetry = []
    for source, (verb, targets, rule) in sorted(rules.items()):
        if source not in rows13:
            continue
        for sibling in sorted(by_activity12[rows12[source]["activity_id"]]):
            if sibling == source or sibling in rules or sibling not in rows13:
                continue
            C = corr_targets.get(sibling, set())
            if C == {sibling}:
                continue
            allocation = {tkey(t)[2]: t.get("allocation") for t in rule.get("targets", [])}
            mirrored = {(sibling[0], sibling[1], loc, sibling[3]) for loc in allocation}
            entry = {
                "rule_source": fmt(source),
                "rule_verb": verb,
                "sibling_without_rule": fmt(sibling),
                "correspondence_targets_of_sibling": sorted(fmt(x) for x in C),
                "mirrored_targets_match_correspondence": mirrored == C,
            }
            asymmetry.append(entry)
            if mirrored == C and verb == "disaggregate":
                proposals["disaggregate"].append({
                    "source": side_dict(sibling),
                    "targets": [side_dict(t) | {"allocation": allocation[t[2]]} for t in sorted(C)],
                    "brightpath_review": {
                        "status": "proposed - optional (non-breaking), requires review, not applied",
                        "rationale": "Co-product of the same 3.12 activity as '" + fmt(source) + "', which ecoinvent_migrate "
                        "disaggregates; the correspondence file lists the same geographic split for this co-product. "
                        "Allocation shares are mirrored from the sibling rule (reference-product production volumes), "
                        "an assumption the reviewer must confirm.",
                        "evidence": "ecoinvent 'Correspondence File v3.12 - v3.13.xlsx', sheet 'Cut-off', exact UUID join",
                        "source_ids": [rows12[sibling]["activity_id"], rows12[sibling]["flow_id"]],
                        "target_ids": [[rows13[t]["activity_id"], rows13[t]["flow_id"]] for t in sorted(C)],
                    },
                })
    c["3.12->3.13 non-breaking co-product split asymmetry"] = asymmetry
    print("(c2) co-product split asymmetry:", len(asymmetry))
    for e in asymmetry:
        print("    ", e["rule_source"], "=> sibling:", e["sibling_without_rule"], "| mirror matches corr:", e["mirrored_targets_match_correspondence"])
    prop_dir = ROOT / "output" / "proposed_supplements"
    prop_dir.mkdir(parents=True, exist_ok=True)
    (prop_dir / "ecoinvent-3.12-cutoff-ecoinvent-3.13-cutoff.proposed-supplement.json").write_text(
        json.dumps({
            "description": "PROPOSED supplements for review only - NOT part of the generated resource and NOT loadable "
            "by BrightPath as-is. Candidates derived from ecoinvent's Correspondence File v3.12 - v3.13 (exact UUID join): "
            "(1) 3.12 cut-off identities that disappear in 3.13 without an ecoinvent_migrate rule although the "
            "correspondence names a target; (2) optional, non-breaking co-product splits mirroring a sibling rule.",
            "source_id": "ecoinvent-3.12-cutoff",
            "target_id": "ecoinvent-3.13-cutoff",
            **{k: v for k, v in proposals.items() if v},
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    results["proposals"] = {k: len(v) for k, v in proposals.items()}

    (ROOT / "work" / "validation_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ------------- summary -------------
    print("3.12 catalog rebuilt identical:", results.get("catalog_3_12_rebuilt_identical_to_packaged"))
    print("(a) tech rules", a["technosphere"]["rules"], "targets", a["technosphere"]["target_identities"])
    print("    sources missing from 3.12:", len(missing_src), "targets missing from 3.13:", len(missing_tgt))
    print("    sources still present in 3.13:", len(a["technosphere"]["sources_still_present_in_3.13"]))
    print("    obsolete 3.12 identities:", len(obsolete_tech), "without rule:", len(a["technosphere"]["obsolete_identities_without_rule"]))
    print("    bio rules", a["biosphere"]["rules"], "issues:", bio_issues)
    print("    bio obsolete identities", len(obsolete_bio), "without rule:", a["biosphere"]["obsolete_identities_without_rule"])
    print("    bio same-uuid identity changed:", a["biosphere"]["same_uuid_identity_changed"])
    print("(b)", {k: (v if not isinstance(v, list) else len(v)) for k, v in results["b_allocations"].items()})
    print("(c) 3.12->3.13 gaps:", len(c["3.12->3.13"]))
    for g in c["3.12->3.13"]:
        print("    ", g["covered_source"], "=> sibling:", g["uncovered_sibling"])
    if package:
        print("    3.11->3.12 gaps:", len(c["3.11->3.12 (method check on packaged resource)"]), "NaOH detected:", c["3.11->3.12 detects chlor-alkali NaOH"])
    print("(d)", json.dumps(d["counts"], indent=1))
    print("proposals:", results["proposals"])


if __name__ == "__main__":
    main()
