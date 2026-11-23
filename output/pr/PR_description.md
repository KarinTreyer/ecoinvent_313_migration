**Title:** Add ecoinvent 3.12 → 3.13 migration resources and 3.13 cut-off reference catalog

---

This adds the ecoinvent 3.12 → 3.13 step (cut-off and biosphere), so that `migrate_background` can route inventories to ecoinvent 3.13 (also chained, e.g. 3.11 → 3.13).

### What is included
- `data/migrations/ecoinvent/cutoff/ecoinvent-3.12-cutoff-ecoinvent-3.13-cutoff.json` — 35 `replace`, 29 `disaggregate` rules.
- `data/migrations/ecoinvent/biosphere/ecoinvent-3.12-biosphere-ecoinvent-3.13-biosphere.json` — 9 `replace`, 3 `delete` rules. Following the existing enrichment convention, every source carries its exact Brightway `(name, categories, unit)` plus UUID (resolved by UUID against the exact 3.12 biosphere, verified by name). On the four 2-Propen-1-ol → Allyl alcohol rules, the targets' ecoSpold `context` lists were replaced by the Brightway categories of the same UUIDs (otherwise the old compartment would be copied onto the exchanges).
- `data/export/reference_catalogs/ecoinvent__3.13__cutoff.json` — schema_version 2, identity metadata only (27,400 technosphere, 9,893 biosphere identities); built with the same script that reproduces the packaged 3.12 catalog byte for byte.
- Manifest entries, `tests/test_ecoinvent_313_migration.py`, two updated count assertions, ATTRIBUTION paragraphs, CHANGELOG, version ranges in README/docs.

### Provenance
Rules generated with `ecoinvent_migrate` 0.7.1 (`generate_technosphere_mapping`, `generate_biosphere_mapping`) from ecoinvent's change report and master data of 3.12 and 3.13. They are identical to the `randonneur_data` 0.8 files of the same names (biosphere: apart from comments and extra unit/context fields). Versions, function calls and SHA-256 of all sources and outputs: `PROVENANCE.md` in the companion repository (shared separately; it also holds the re-runnable generation scripts).

### Validation (details: `VALIDATION.md` in the companion repository)
- All rule sources exist in the exact 3.12 catalog and all targets in the 3.13 catalog (64/64 sources, 188/188 targets; biosphere 12/12 and 9/9 with matching UUIDs).
- All 29 disaggregations sum to 1.
- Cross-check against ecoinvent's *Correspondence File v3.12 – v3.13*: 100 % of rows join on UUIDs; no rule missing where the file names a successor, no rule contradicting it.
- `migrate_background` 3.12 → 3.13 under the strict policy on a synthetic inventory (replace, disaggregate, biosphere rename, unchanged exchanges) and on a real inventory of ~1,000 datasets (ESA LCA Database 1.4.0: 4 replacements, 1 disaggregation, 136 biosphere replacements, 0 errors after migration).
- Tests: migration/catalog/manifest modules pass (6 failures also occur on unchanged `main` 898ff20: the catalog manifest lists a 3.10.1 consequential file that is not in the repository). **The full test suite has not been run** (it did not finish locally) — please run it.

### Open points for review
- **O1** 2-Propen-1-ol → Allyl alcohol is an `ecoinvent_migrate` patch based on CAS 107-18-6, not stated in the change report; it also maps across subcompartments (non-urban air → air, surface water → water).
- **O2** RoW heat from wood-chip CHP 6667 kW is split 1/6 each to RoW and five Indian states (all targets have zero production volume), although the RoW dataset still exists in 3.13.
- **O3** The GLO seed-cotton market disaggregations include the RoW market (shares 0.346 and 0.187), which the correspondence file does not list.
- **O4** Nine datasets are deleted without successor (NL residual mix ×5, bark chips ×2, steam ×2): links to them fail under the strict policy; no proxies added.
- **O5** Five optional co-product splits (protein feed ×2, cottonseed ×2, electricity of the 6667 kW CHP) are proposed in the companion repo but **not** included.
- **O6** 22 rules split datasets that still exist in 3.13 into new regions by production volume (standard `ecoinvent_migrate` practice, applied by BrightPath to valid links without a warning).
- The 3.13 catalog needs the same legal review as the other identity catalogs.
- Side finding: `background/migration.py` hard-codes UVEK export targets up to 3.12; the packaged 3.11 → 3.12 resource has 27 co-product gaps (incl. chlor-alkali sodium hydroxide and hydrogen), listed in `VALIDATION.md`.
