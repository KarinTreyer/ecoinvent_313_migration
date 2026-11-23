# ecoinvent 3.12 → 3.13 migration resources for BrightPath

This folder holds the files needed to migrate ecoinvent 3.12 cut-off inventories to ecoinvent 3.13 with [BrightPath](https://github.com/romainsacchi/brightpath). They are meant for a later contribution upstream.

The deliverables:

| Path | What |
|---|---|
| `output/brightpath/data/migrations/ecoinvent/cutoff/ecoinvent-3.12-cutoff-ecoinvent-3.13-cutoff.json` | Technosphere (cut-off) randonneur datapackage: 35 `replace` and 29 `disaggregate` rules |
| `output/brightpath/data/migrations/ecoinvent/biosphere/ecoinvent-3.12-biosphere-ecoinvent-3.13-biosphere.json` | Biosphere: 9 `replace` and 3 `delete` rules. Sources are enriched with their Brightway identity |
| `output/brightpath/data/export/reference_catalogs/ecoinvent__3.13__cutoff.json` | Exact 3.13 cut-off reference catalog (schema_version 2) |
| `output/manifest_snippets/` | The `RESOURCE_MANIFEST.json` entries for the three files |
| `output/pr/brightpath-ecoinvent-3.13.patch` | A ready diff against upstream `main` 898ff20 with everything except the 10 MB catalog |
| `output/proposed_supplements/` | Five optional rules for review. They are not applied and not loadable |
| `output/use_now/brightpath_ei313_overlay.py` | Lets you use the files now with an unmodified BrightPath 1.0.0a14 |
| `PROVENANCE.md` | How the files were made: versions, source SHA-256s, function calls, decisions |
| `VALIDATION.md` | Validation results: identities, allocations, co-product gaps, correspondence-file cross-check, BrightPath test |
| `scripts/` | Re-runnable generation scripts, numbered in run order |

`work/` holds licence-derived intermediates (raw generator output, correspondence extract, logs). It is git-ignored and is not for distribution. `brightpath_upstream/` is a read-only clone of the upstream repository. `brightpath_pr/` is a local working copy with the PR changes staged; nothing has been committed or pushed.

## Re-running

All scripts run in the conda env `esa_import` except where noted. The ecoinvent credentials must already be stored with `ecoinvent_interface` (`permanent_setting`).

```bash
C="/c/Users/treyer_k/AppData/Local/miniforge3/Scripts/conda.exe"
BP=<path to an extracted brightpath 1.0.0a14 package dir>   # only for the 3.12 equivalence check and the 3.11 method check
$C run -n esa_import python scripts/01_fetch_sources.py               # download/cache, record SHA-256s
$C run -n esa_import python scripts/02_run_ecoinvent_migrate.py       # ecoinvent_migrate 0.7.1 -> work/raw
$C run -n esa_import python scripts/03_build_catalog.py 3.12 --compare $BP/data/export/reference_catalogs/ecoinvent__3.12__cutoff.json
$C run -n esa_import python scripts/03_build_catalog.py 3.13          # -> output/.../ecoinvent__3.13__cutoff.json
$C run -n esa_import python scripts/04_load_correspondence.py         # -> work/correspondence_cutoff.json
$C run -n esa_import python scripts/05_build_brightpath_resources.py  # -> output/.../migrations
$C run -n esa_import python scripts/06_validate.py $BP                # -> work/validation_results.json, proposals
$C run -n bp_dev     python scripts/07_install_into_brightpath.py brightpath_pr/brightpath
$C run -n bp_dev     python scripts/08_test_brightpath_migration.py installed
$C run -n esa_import python scripts/08_test_brightpath_migration.py overlay
```

If you re-run `02`, the `created` timestamps in the migration files change. Their SHA-256 values then change too, and so must the manifest entries.

## Using the files now, before they are in a BrightPath release

BrightPath 1.0.0a14 finds the two kinds of files differently:

- **Reference catalogs: a supported hook exists.** You can pass `catalog_provider=` to `validate` or `migrate_background`, using `DirectoryCatalogProvider(dir)` or `CompositeCatalogProvider(...)`. Alternatively, set `BRIGHTPATH_REFERENCE_DIR=<dir>` before importing. The directory may contain its own `RESOURCE_MANIFEST.json`; if it does, the catalogs in it are integrity-checked.
- **Migration resources: no supported hook exists.** They are discovered only under the installed `brightpath/data/migrations/ecoinvent/{cutoff,biosphere}/*.json`.
  - Each file must have an entry in `brightpath/data/migrations/RESOURCE_MANIFEST.json` with matching path, SHA-256, size, name, `source_id` and `target_id`.
  - Each file's `source_id`/`target_id` must match `ecoinvent-<X.Y>-<cutoff|consequential|biosphere>`.
  - Routes are composed from adjacent version pairs. 3.11 → 3.13 therefore chains the packaged 3.11→3.12 resource with the new one.
  - There is no environment variable and no parameter for external migration files.

You have two options:

1. **Overlay (no install change).** This is tested on unmodified 1.0.0a14 in `esa_import`.
   ```python
   import sys; sys.path.insert(0, r"C:/Users/treyer_k/Documents/GitHub/ecoinvent_313_migration/output/use_now")
   from brightpath_ei313_overlay import enable_ecoinvent_313
   provider = enable_ecoinvent_313()   # copies data/migrations to ~/.brightpath_ei313_overlay/<version>, adds files
   from brightpath import BrightwayInventory, BackgroundContext, TechnosphereProfile, BiosphereProfile
   target = BackgroundContext(TechnosphereProfile("ecoinvent", "3.13", "cutoff"), BiosphereProfile("ecoinvent", "3.13"))
   migrated = inventory.migrate_background(target, catalog_provider=provider)   # inventory: ecoinvent 3.12 cutoff
   print([(i.severity, i.code, i.message) for i in migrated.last_migration_report.issues])
   ```
   The overlay redirects `brightpath.migrations.resources.DATA_DIR` and `brightpath.background.patches.DATA_DIR` for the current process only. This is a workaround, not an API. Always pass `catalog_provider=provider`, also to `validate()`.
2. **Separate env with an editable clone** (`bp_dev` here). Run `pip install -e brightpath_pr` (upstream `main` plus these files), or install the files into any clone with `scripts/07_install_into_brightpath.py <clone>/brightpath`.

The default strict policy refuses lossy steps:
- An inventory that uses one of the 3.12 datasets deleted without a replacement fails with "coverage below 1": the 5 NL residual-mix electricity datasets, 2 bark-chip by-products and 2 steam by-products, all listed in `VALIDATION.md`.
- Soil emissions of 2-Propen-1-ol need `MigrationPolicy(on_deletion=PolicyAction.WARN)` to be dropped.

## Contributing to BrightPath (do not push without Karin's go-ahead)

The patch `output/pr/brightpath-ecoinvent-3.13.patch` applies to upstream `main` 898ff20. It contains:

- `brightpath/data/migrations/ecoinvent/cutoff/ecoinvent-3.12-cutoff-ecoinvent-3.13-cutoff.json` (new)
- `brightpath/data/migrations/ecoinvent/biosphere/ecoinvent-3.12-biosphere-ecoinvent-3.13-biosphere.json` (new)
- `brightpath/data/migrations/RESOURCE_MANIFEST.json`: 2 entries added. This equals a full re-run of `scripts/generate_migration_manifest.py`.
- `brightpath/data/export/reference_catalogs/RESOURCE_MANIFEST.json`: 1 entry added by **insertion**. Do **not** re-run `scripts/generate_catalog_manifest.py` in a fresh clone: `main` lists `ecoinvent__3.10.1__consequential.json`, which is git-ignored and untracked, so a re-run would silently drop that entry.
- `ATTRIBUTION.md` paragraphs in `data/migrations/` and `data/export/reference_catalogs/`, a CHANGELOG entry, and version ranges in README, `docs/limitations.rst` and `docs/architecture.rst`.
- Tests:
  - `tests/test_migration_manifest.py`: resource count 23 → 25, plus the new paths;
  - `tests/test_migrations.py`: "3.13" added to `available_ecoinvent_versions()`;
  - new `tests/test_ecoinvent_313_migration.py` (5 tests).

The catalog itself is **not** in the patch (10.5 MB). `.gitignore` ignores `brightpath/data/export/reference_catalogs/*` except for a short whitelist, so you must either add it with `git add -f` or add a `!…/ecoinvent__3.13__cutoff.json` line, as was done for 3.9.1 and 3.10.1.

Steps:
```bash
git clone https://github.com/<your-fork>/brightpath && cd brightpath && git checkout -b ecoinvent-3.13
git apply /c/Users/treyer_k/Documents/GitHub/ecoinvent_313_migration/output/pr/brightpath-ecoinvent-3.13.patch
cp /c/Users/treyer_k/Documents/GitHub/ecoinvent_313_migration/output/brightpath/data/export/reference_catalogs/ecoinvent__3.13__cutoff.json brightpath/data/export/reference_catalogs/
git add -f brightpath/data/export/reference_catalogs/ecoinvent__3.13__cutoff.json
pytest tests/test_ecoinvent_313_migration.py tests/test_migration_manifest.py tests/test_migrations.py
```

In the PR description, mention:
- the open issues in `VALIDATION.md` (O1–O6 in the summary below);
- that the catalog needs the same `legal_review_required` consideration as the other identity catalogs;
- that `background/migration.py` hard-codes the set of UVEK export target versions, `{"3.6", …, "3.12"}`. A UVEK → ecoinvent 3.13 route therefore stays disabled, which is a separate decision.

### Open issues for Karin's or Romain's judgement

- **O1.** The 2-Propen-1-ol → Allyl alcohol mapping is an ecoinvent_migrate patch based on CAS 107-18-6, which ecoinvent's change report does not state. It also maps across subcompartments: `air/non-urban air or from high stacks` → `air` and `water/surface water` → `water`. Accept it, or turn those flows into deletions?
- **O2.** The RoW heat from `heat and power co-generation, wood chips, 6667 kW` is split equally (1/6 each) into RoW and 5 Indian states, because all targets have zero production volume. The RoW source still exists in 3.13. Keep the rule, or override it so RoW stays at 1.0?
- **O3.** The `market for seed-cotton[, organic] | GLO` disaggregations include the 3.13 RoW market (0.346 and 0.187), which the correspondence file does not list.
- **O4.** 9 datasets are deleted without any successor. For steam in kg versus "heat, from steam, in chemical industry" in MJ, a proxy would need a documented conversion factor. Leave them unmapped (strict failure) or author reviewed proxies?
- **O5.** Optional mirrored splits for 5 co-products (`output/proposed_supplements/`). They are non-breaking. The allocation shares are copied from the sibling reference product, and one of them uses the O2 equal shares.
- **O6.** 22 rules split datasets that still exist in 3.13 (mainly RoW) into newly carved-out regions, using production-volume shares. This is standard ecoinvent_migrate practice and agrees with the correspondence file, but it changes links that are still valid. BrightPath applies these rules without a warning.
- Side finding: the method check on the **packaged 3.11→3.12** resource finds 27 co-product gaps in total, including the known chlor-alkali sodium hydroxide and hydrogen case (see `VALIDATION.md`).
