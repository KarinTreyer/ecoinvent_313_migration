# Validation: ecoinvent 3.12 → 3.13 resources (2026-11-23)

Produced by `scripts/06_validate.py` (machine-readable results in `work/validation_results.json`) and
`scripts/08_test_brightpath_migration.py` (`work/brightpath_test_*.json`).

## 0. Reproducibility of the catalog builder

`scripts/03_build_catalog.py 3.12` reproduces BrightPath's packaged `ecoinvent__3.12__cutoff.json` byte
for byte (sha256 `b0bc1eb7…e58e`, 26,533 technosphere / 9,850 biosphere). The identical reader produced
`ecoinvent__3.13__cutoff.json` (27,400 / 9,893; every row carries UUIDs).

## (a) Identities against the exact catalogs

Names, reference products, locations and categories are compared exactly (case-sensitive). The ecoSpold
units in the technosphere rules (`kg`, `MJ`, `kWh`) are compared after bw2io's `normalize_units`, the
same function that produced the catalog units (`kilogram`, `megajoule`, `kilowatt hour`); BrightPath
applies the equivalent `normalize_unit` at runtime. Biosphere rules are additionally checked UUID ==
catalog `flow_id`.

| Check | Result |
|---|---|
| Technosphere rule sources (64) in exact 3.12 catalog | **64/64** |
| Technosphere targets (188 identities) in exact 3.13 catalog | **188/188** |
| Biosphere sources (12) in exact 3.12 catalog, UUID equal | **12/12** |
| Biosphere replace targets (9) in exact 3.13 catalog, UUID equal | **9/9** |
| 3.12 technosphere identities absent from 3.13 | 51; 42 covered by a rule, **9 without rule** (see d) |
| 3.12 biosphere identities absent from 3.13 | 7 (all 2-Propen-1-ol); **7/7 covered** (4 replace, 3 delete) |
| Same biosphere UUID with changed identity | 0 |
| Biosphere UUIDs removed / added | 7 / 50 (net +43 identities) |
| Technosphere rules whose source still exists in 3.13 | 22 (geographic splits of RoW/GLO datasets, see d) |

## (b) Disaggregation allocations

29/29 rules sum to 1 (max |Σ−1| = 1.1e-16); no zero, negative, missing or duplicate targets.
One rule uses ecoinvent_migrate's **equal-allocation fallback** because all targets have zero
production volume: `heat and power co-generation, wood chips, 6667 kW | heat, district or industrial,
other than natural gas | RoW` → RoW + 5 Indian states at 1/6 each. The source still exists in 3.13,
so this rule moves 5/6 of an RoW link to Indian state datasets on an arbitrary basis
(**open issue O2**).

## (c) Co-product gap pattern

*Method check:* run on BrightPath's packaged 3.11→3.12 resource, the check flags the known
`chlor-alkali electrolysis, diaphragm cell` case (chlorine covered; **sodium hydroxide** and
**hydrogen, gaseous, low pressure** uncovered) and 25 further uncovered siblings — 27 in total
(listed at the end; outside this task's scope, but relevant to Romain).

*3.12→3.13, breaking gaps* (sibling disappears from 3.13 without a rule): **4**, all with no target in
ecoinvent's correspondence file and explicitly left unpatched by ecoinvent_migrate (`patches.py`):

| Covered product (rule) | Uncovered sibling (3.12) |
|---|---|
| folding boxboard carton production · folding boxboard carton · RER | bark chips, green, measured as dry mass · RER (by-product dropped in 3.13) |
| folding boxboard carton production · folding boxboard carton · RoW | bark chips, green, measured as dry mass · RoW |
| formaldehyde production, methanol oxidation · formaldehyde · RER | steam, in chemical industry (kg) · RER — 3.13 has "heat, from steam, in chemical industry" in MJ, no documented conversion |
| formaldehyde production, methanol oxidation · formaldehyde · RoW | steam, in chemical industry (kg) · RoW |

*3.12→3.13, non-breaking asymmetry* (new check, c2): a rule splits a still-valid reference product of
a multi-output activity across new geographies, but the still-valid co-product keeps its old link,
although the correspondence file lists the same split for it: **5**

| Rule (still-valid source) | Co-product left unsplit |
|---|---|
| cottonseed to generic market for energy feed · energy feed, gross · RoW | · protein feed, 100% crude · RoW |
| cottonseed, organic to generic market for energy feed · energy feed, gross · RoW | · protein feed, 100% crude · RoW |
| fibre production, cotton, ginning · fibre, cotton · RoW | · cottonseed · RoW |
| fibre production, cotton, organic, ginning · fibre, cotton, organic · RoW | · cottonseed, organic · RoW |
| heat and power co-generation, wood chips, 6667 kW · heat, district or industrial, other than natural gas · RoW | · electricity, high voltage · RoW |

Candidate mirrored disaggregations (allocation copied from the sibling rule; reviewer must confirm)
are in `output/proposed_supplements/…proposed-supplement.json`. They are **not applied**.

## (d) Cross-check with `Correspondence File v3.12 - v3.13.xlsx` (sheet "Cut-off")

27,415 rows; joined on exact (activity UUID, product UUID): 100 % of rows match the catalogs
(26,678 source rows → all 26,533 3.12 datasets; 27,406 target rows → all 27,400 3.13 datasets).
Classification of every 3.12 cut-off identity:

| Category | Count |
|---|---|
| still valid in 3.13, correspondence = identity, no rule needed | 26,455 |
| still valid, rule (geographic split) **agrees** with correspondence | 22 |
| still valid, correspondence lists a split but no rule (the c2 co-products above) | 5 |
| obsolete, rule **agrees** with correspondence | 40 |
| obsolete, rule **partially agrees** | 2 |
| obsolete, **no rule but correspondence has a target** | **0** |
| obsolete, no rule, no correspondence target (deleted) | 9 |
| rule **contradicting** the correspondence | **0** |

Details:
- *Partial (2):* `market for seed-cotton | GLO` and `market for seed-cotton, organic | GLO`
  (disaggregations). The rules include the 3.13 **RoW** market as an extra target
  (allocation 0.346 resp. 0.187), which the correspondence does not list (it lists only the named
  countries). RoW markets exist in 3.13 (**open issue O3**).
- *Deleted without target (9):* NL residual-mix electricity (5: high/medium/low voltage residual mix
  and the two residual-mix transformation datasets), the two bark-chips by-products and the two
  steam by-products above. Under BrightPath's strict policy, inventories linking these fail
  (coverage < 1), as tested. No proposal is made; any replacement would be a modelling choice
  (**open issue O4**).
- No missing rules were found where the correspondence offers a target, so the proposals file only
  contains the 5 optional co-product splits.

## BrightPath integration test (task 5)

`scripts/08_test_brightpath_migration.py`, synthetic inventory with made-up amounts, strict policy,
`BrightwayInventory.migrate_background` from ecoinvent 3.12 cut-off/biosphere 3.12 to 3.13/3.13:

| Case | Result (both `installed` in `bp_dev` and `overlay` on unmodified 1.0.0a14 in `esa_import`) |
|---|---|
| replace: calcined petroleum coke production CN | → `…, vertical shaft` CN, amount 2.0 kept |
| disaggregate (obsolete GLO): market for seed-cotton, 10 kg | → 7 markets (BD, BR, CN, IN, RoW, TR, US), Σ = 10 kg |
| still-valid RoW split: wind 1-3MW onshore RoW, 5 kWh | → RoW 4.985, BR-South-eastern/Mid-western grid 0.0048, CN-XZ 0.0100 |
| unchanged: market for electricity, low voltage CH | unchanged |
| biosphere rename: 2-Propen-1-ol (air) / (water, surface water) | → Allyl alcohol (air) / (water) |
| biosphere formula-only rule (Dibutyltin, water/ocean) | unchanged (no-op) |
| source and target validation | no errors; report has no issues |
| biosphere deletion (2-Propen-1-ol, soil/agricultural) | strict: `MigrationError` (deletion); `on_deletion=WARN`: exchange removed |
| obsolete source without rule (NL residual mix) | strict: `MigrationError` (coverage below 1) — expected |
| chained 3.11 → 3.13 | works (3.11→3.12 packaged + 3.12→3.13 new) |

Upstream test suite in `bp_dev` (editable `brightpath_pr` = upstream `main` 898ff20 + the new files):
see "Upstream test suite" below. Two existing tests pin counts and were updated in the PR copy
(`tests/test_migration_manifest.py` 23→25 resources; `tests/test_migrations.py` versions + "3.13");
new `tests/test_ecoinvent_313_migration.py` (5 tests) passes.

### Upstream test suite

The complete suite (504 test files) did not finish within about 85 minutes on this machine and was
stopped. A targeted run of the ten migration/catalog/manifest test modules was completed instead
(`test_catalog_manifest`, `test_migration_manifest`, `test_migrations`, `test_catalogs`,
`test_background_providers`, `test_facade_migration`, `test_lightweight_migration`,
`test_system_model_migration_scope`, `test_catalog_3101_consequential`,
`test_recycled_paper_migrations`):

- with the new files, before updating any test: 556 passed and 8 failed;
- 6 of those 8 failures also occur on **pristine** upstream `main` 898ff20 (baseline run with the
  same env). Their cause: the manifest lists `ecoinvent__3.10.1__consequential.json`, which is
  git-ignored and not in the repository;
- the other 2 were count assertions (23 manifest resources; versions up to 3.12). These were updated
  in the PR copy, and afterwards these tests plus the new `test_ecoinvent_313_migration.py` give
  15 passed.

Before a PR, run the full suite on a faster machine or in CI.

## Side finding: 3.11→3.12 co-product gaps in the packaged resource (method check, 27)

- acrylic acid production, propylene oxidation · acetic acid · RER, RoW
- aluminium oxide production · aluminium oxide, non-metallurgical · IAI Area, EU27 & EFTA; IAI Area, Russia & RER w/o EU27 & EFTA
- bark chips, wet, measured as dry mass to generic market for residual hardwood, wet · residual softwood, wet · CA-QC, CH, Europe without Switzerland, RoW
- chlor-alkali electrolysis, diaphragm cell · hydrogen, gaseous, low pressure · GLO; · sodium hydroxide, without water, in 50% solution state · GLO
- debarking, softwood, in forest · bark chips, wet, measured as dry mass · RER, RoW
- industrial gases production, cryogenic air separation · argon, crude, liquid · RoW; · nitrogen, liquid · RoW
- natural gas liquids production · helium, crude · GLO
- sawdust, wet, measured as dry mass to generic market for residual softwood, wet · residual hardwood, wet · CA-QC, CH, Europe without Switzerland, RoW
- unsaturated hydrocarbons production, steam cracking operation, average · butene, mixed / hydrogen, gaseous, low pressure / pyrolysis fuel gas / pyrolysis fuel oil · RER, RoW

These 3.11 identities disappear in 3.12 without any rule while a sibling product of the same 3.11
activity is migrated. Not investigated further (out of scope); worth a correspondence-file check
analogous to (d) for 3.11→3.12.
