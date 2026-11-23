# Provenance: ecoinvent 3.12 → 3.13 resources for BrightPath

Generated on 2026-11-23 (Windows 11, conda env `esa_import`), for a later contribution to
BrightPath (https://github.com/romainsacchi/brightpath). This work is generic: it does not depend on
any other database or project.

## Outputs

| File | SHA-256 | Bytes |
|---|---|---|
| `output/brightpath/data/migrations/ecoinvent/cutoff/ecoinvent-3.12-cutoff-ecoinvent-3.13-cutoff.json` | `57bcc0fe4fa12749f734d791b9fbc0a5572a303e29fad63a96ed8e5084602d51` | 58,678 |
| `output/brightpath/data/migrations/ecoinvent/biosphere/ecoinvent-3.12-biosphere-ecoinvent-3.13-biosphere.json` | `8efe2858225e68f7775903d86943396eacbc2b025ce3ff38b066a07318c536f6` | 7,662 |
| `output/brightpath/data/export/reference_catalogs/ecoinvent__3.13__cutoff.json` | `935ef2d5c2f297a10b67b0391ead69d4d02ca2d35ed1805b86e60bf286a35c54` | 10,496,509 |
| `output/manifest_snippets/*.entries.json` | the manifest entries for the three files above | |
| `output/proposed_supplements/ecoinvent-3.12-cutoff-ecoinvent-3.13-cutoff.proposed-supplement.json` | proposals for review only. This file is not part of the resources. | |

Rule counts:
- Technosphere (cut-off): 35 `replace` and 29 `disaggregate` rules, with 188 target identities. No `delete` rules.
- Biosphere: 9 `replace` and 3 `delete` rules.
  - 4 replace rules change the identity: 2-Propen-1-ol becomes Allyl alcohol.
  - 5 replace rules change only the formula of organotin flows. They keep the identity, and BrightPath ignores `formula` when it applies a rule.

Catalog: 27,400 technosphere and 9,893 biosphere identities. Every identity has its exact ecoSpold2 UUIDs (`activity_id`/`flow_id`).

## Software

| Package | Version |
|---|---|
| ecoinvent_migrate | 0.7.1 (has built-in `("3.12", "3.13")` technosphere by-product patches and biosphere patches) |
| ecoinvent_interface | 3.1 (credentials from `Settings()` / `permanent_setting`; never read or copied) |
| randonneur | 0.7.2 |
| randonneur_data | 0.8 (used only for comparison) |
| bw2io / bw2data | 0.9.17 / 4.7 |
| BrightPath (reference) | 1.0.0a14 wheel, and upstream `main` at `898ff20beb54a35f2d28e6d3ace7208532f5cb88` (2026-11-18) |

## Licensed source files (stay in the ecoinvent_interface cache, not copied)

| Source | SHA-256 |
|---|---|
| `ecoinvent 3.12_cutoff_ecoSpold02.7z` (26,533 datasets) | `c00cf9a5704f2b8139995e8af9a62c5a432bd33b60f3c978788073e82bdc416f` |
| `ecoinvent 3.13_cutoff_ecoSpold02.7z` (27,400 datasets) | `6d34eda584ef488aacc340e110381173f03d2fba7905aac5e2fafe9a6fe39819` |
| 3.12 `MasterData/ElementaryExchanges.xml` | `afef20df80ec4823ff93f83bc4f5c965f39302975c08c4a3682b6c86f79a92c1` |
| 3.13 `MasterData/ElementaryExchanges.xml` | `69e52fce84c0a156cbd5f979e97b4140c6adbc2cfe0ceec1f0e46f16131b035b` |
| 3.12 `MasterData/IntermediateExchanges.xml` | `b0155f1b838ff3f8f46af2621fb3217e39252e8b95bc0b24b6c887c6f1387672` |
| 3.13 `MasterData/IntermediateExchanges.xml` | `3a6d90c8d8db3f941a2bff6f50237546ff53f697ab1c04d5b5bbd68bfeea02ae` |
| `ecoinvent 3.13_Change Report_including_Annex.7z` | `28b8640fdb33feaed4168e885a566d3969a26f7500b96aea9c248634f63af2a8` |
| ↳ `Change Report Annex v3.12 - v3.13.xlsx` | `baf0b170edd1be39cae9c860fec9346585ea3943ad382bd4060a5ca7b9746935` |
| ↳ `Change Report v3.13.pdf` | `210c4eb10d4543de5f12527c8d7e624d975badec043f4e1f1ce30b87de580642` |
| `Correspondence File v3.12 - v3.13.xlsx` | `97b00a65db5049998f28fc8a639e7fa1e596e0922df6069b37fe465408ea6657` |

`work/sources.json` lists the full set, including the ActivityNames and Geographies files.

Download note: on 2026-11-23, ecoinvent_interface logged "Downloaded file doesn't match expected size" for two files:
- the 3.13 ecoSpold archive: 125,549,412 bytes received, 125,314,898 expected;
- the change-report archive: 5,157,518 bytes received, 5,165,118 expected.

Both archives pass a full 7z CRC test (`scripts/01b_check_archive_crc.py`), and both extracted completely. The mismatch is in the API's size metadata, not in the downloaded data.

## How the files were generated

1. `scripts/01_fetch_sources.py` gets the 3.12 and 3.13 cut-off ecoSpold2 releases, the change report and the correspondence file through `EcoinventRelease(Settings())`. It records their paths and SHA-256 digests in `work/sources.json`.
2. `scripts/02_run_ecoinvent_migrate.py` runs these calls (they finished at 14:55:27 and 14:55:32 UTC):
   ```python
   generate_technosphere_mapping(source_version="3.12", target_version="3.13", system_model="cutoff",
                                 write_logs=True, write_file=True, licenses=[CC-BY-4.0], output_directory=work/raw)
   generate_biosphere_mapping(source_version="3.12", target_version="3.13", keep_deletions=False,
                              write_logs=True, write_file=True, licenses=[CC-BY-4.0], output_directory=work/raw)
   ```
   The raw outputs are `work/raw/*.json`:
   - cut-off: `f6992bc5…d43c`, 60,589 bytes, CRLF;
   - biosphere: `287d02da…5299`, 6,862 bytes.

   The ecoinvent_migrate logs are copied to `work/logs/`. ecoinvent_migrate warned about 9 sources that "changed but have no migration": 5 NL residual-mix electricity datasets, 2 bark-chips by-products of folding boxboard carton production, and 2 steam by-products of formaldehyde production. Its own `patches.py` documents all 9 as deliberately not patched.

   Biosphere: the `EE Deletions` sheet is **not empty** this time. It holds seven 2-Propen-1-ol rows, and its UUID column is labelled "ID - 3.11" and left empty. The high-level generator therefore returned rules, and the direct fallback call that BrightPath used for 3.11→3.12 was **not needed**. The generator still ran `supplement_biosphere_changes_with_real_data_comparison` internally. The rules came from two places:
   - ecoinvent_migrate's manual `BIOSPHERE_PATCHES[("3.12","3.13")]` gave the 4 Allyl-alcohol replacements;
   - the master-data comparison gave the 5 formula-only changes and the 3 soil deletions.
3. `scripts/03_build_catalog.py` builds the 3.13 catalog. It reads Brightway-equivalent identities directly from the ecoSpold2 files (`scripts/ei_identity_lib.py`), using:
   - bw2io's `normalize_units`, `update_ecoinvent_locations` and "reference product = product with non-zero amount" strategies;
   - `Ecospold2BiosphereImporter` with its strategies for the biosphere.

   It serializes the catalog exactly like BrightPath's `scripts/enrich_reference_catalog_uuids.py` (`json.dumps(indent=2, sort_keys=True) + "\n"`).
   **Equivalence proof:** running the same script for 3.12 reproduces BrightPath's packaged `ecoinvent__3.12__cutoff.json` byte for byte (`b0bc1eb7…e58e`, 10,227,423 bytes). This is the reason the full `bw2io.import_ecoinvent_release` route was not needed.
4. `scripts/04_load_correspondence.py` extracts the cut-off sheet of the correspondence file to `work/correspondence_cutoff.json`. The extract keeps identity columns only and stays local.
5. `scripts/05_build_brightpath_resources.py` turns the raw outputs into BrightPath resources (see Decisions).
6. `scripts/06_validate.py <brightpath package dir>` runs the validation in `VALIDATION.md` and writes the proposals.
7. `scripts/07_install_into_brightpath.py` copies the files into a BrightPath package directory and adds the manifest entries. `scripts/08_test_brightpath_migration.py` runs the synthetic migration test.

## Decisions

- **The technosphere rules are taken unchanged from ecoinvent_migrate.** The file is only re-serialized with LF line endings and a trailing newline, as BrightPath's packaged files are; the Windows run had written CRLF. No rule was added, removed or re-targeted.
- **Biosphere enrichment** follows BrightPath's `scripts/enrich_biosphere_migration_sources.py`.
  - Every rule source gets the exact Brightway `(name, categories, unit)`. The values are resolved by UUID against the exact 3.12 biosphere (`Ecospold2BiosphereImporter` on the 3.12 `ElementaryExchanges.xml`) and verified by name.
  - The UUID and formula are kept.
  - The key order is name, categories, unit, then the upstream keys, which matches the enrichment script.
- **Conversion from ecoSpold `context` to Brightway `categories`.** ecoinvent_migrate 0.7.1 writes `context` lists such as `["air", "unspecified"]` on the four 2-Propen-1-ol → Allyl alcohol rules. BrightPath matches on `categories` and copies every target field verbatim onto exchanges. Left unchanged, the rules would have kept the old compartment and added a stray `context` key to exchanges.
  - Each `context` was therefore replaced by the exact Brightway `categories` (plus `unit` on targets) of the same UUID. Targets were resolved in the exact 3.13 biosphere, and each `context` was checked against those categories.
  - `context` was then dropped from both sides.
  - This changes the format only, not the mapping.
- **The Allyl-alcohol mapping across subcompartments is an upstream decision and needs review.** ecoinvent's change report deletes 2-Propen-1-ol "without replacement". ecoinvent_migrate instead maps four of the seven flows to the existing `Allyl alcohol` flows, citing the same CAS number, 107-18-6:
  - `air, non-urban air or from high stacks` → `air`;
  - `water, surface water` → `water`.

  The three soil flows are deleted because no soil Allyl alcohol flow exists. The decision is kept here, and Karin and Romain should confirm it.
- **The 5 formula-only biosphere rules are kept** for consistency with upstream. They have no effect in BrightPath.
- **Cross-check with `randonneur_data` 0.8.** That package ships upstream files with the same names, created on 2026-11-04 and labelled as made with ecoinvent_migrate 0.6.2.
  - The technosphere rule sets are identical: same sources, same targets, same allocation values.
  - The biosphere mappings are identical: same source UUIDs, target UUIDs, names and formulas.
  - The only differences are cosmetic: the upstream file has `unit` and `context` on sources and slightly different comments.

## Licensing

The outputs contain only identity and mapping metadata: names, reference products, locations, units, categories, UUIDs, and allocation shares produced by ecoinvent_migrate. They contain no exchange amounts, inventories or LCIA factors. The migration files carry CC-BY-4.0, as the existing ecoinvent_migrate resources in BrightPath do.

BrightPath's catalog manifest marks all derived identity catalogs `legal_review_required`, and the same applies to the 3.13 catalog. The licence-derived intermediates in `work/` (correspondence extract, raw outputs, logs) are git-ignored and are not for distribution.
