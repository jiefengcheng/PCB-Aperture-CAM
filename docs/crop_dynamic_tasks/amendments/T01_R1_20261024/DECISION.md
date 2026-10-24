# T01-R1 local completion decision

**Owner acceptance: NOT ACCEPTED.** The earlier local technical status below does not establish that the delivered enlargement fits the EDIT-implied range.

**Correction status:** range-bounded replacement run prepared for review; acceptance remains `NOT_ACCEPTED`. See [OWNER_REVIEW.md](OWNER_REVIEW.md) and the new, separately bound evidence at `out/crop_dynamic_tasks/t01_r1_edit_calibrated/`. The completion result below describes the superseded 0.20 mm run only and is retained as historical evidence.

**Baseline:** `ee619a01be1f6b8d4088380b5234f06f7d33fefa`

**ORG source SHA-256:** `850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0`

**Owner amendment package SHA-256:** `70c320a1e3f59a0422faa2ce0e11677da599effd4340f8744940f139ffc115de`

## Result

T01-R1 was implemented as a separate ORG-only source-construction path. The historical T01 code, source files, receipts, and WKB outputs remain unchanged. The revised census contains all 53 supported filled-circle source occurrences intersecting the fixed review viewport, represented as 51 unique geometries; exact duplicate occurrences retain their own source identities. There is no size cutoff or viewport-edge write truncation.

The full ORG F.Cu intersection graph identifies 26 physical components containing admitted target circles. One round priority outline was reserved per component before companion growth. The result has 26 `KEEP_PRIORITY_ROUND`, 23 `GROW`, and 2 `KEEP_CONSTRAINED` decisions. Seventeen evolving-scene changes are recorded. The 0.20 mm common reach is touched by 20 growing sites and is the sole limiter for zero sites; each actual stopping object and role is retained with the decision.

The assembled scene has a minimum measured non-port separation of 0.024990165659575483 mm against a 0.020 mm experimental threshold and 0.00001 mm tolerance. There are zero hard-gap violations, zero source-existing attachment-port spill violations, zero lost priority outlines, and zero detached-island failures. The 0.025 mm construction buffer remains identified as a construction value, not a clearance guarantee. Three fixed-neighbor counterfactuals and one real-source same-seed open/crowded replay demonstrate that neighboring geometry changes the result.

The separate smaller-roomier/larger-crowded synthetic control passes in the focused tests. This real crop has no natural final-radius reversal: the larger original circles are the reserved priorities. The report therefore records `NOT_DEMONSTRATED_REAL_CROP` instead of implying a real-source pair that does not exist.

## Verification

- 11 relevant regression and T01-R1 tests pass: `out/crop_dynamic_tasks/t01_r1/focused_tests.log`.
- The fresh-process verifier passes 16/16 checks, reruns construction, compares every persisted WKB against the fresh replay, and checks the source, frozen policy, ports, gaps, priorities, and output bindings: `out/crop_dynamic_tasks/t01_r1/fresh_verification.json`.
- Every source occurrence and component decision is indexed in `out/crop_dynamic_tasks/t01_r1/selection_and_priority_map.json`; per-site sizes, areas, eight directional area bins, actual constraints, ports, and dispositions are in `out/crop_dynamic_tasks/t01_r1/owner_issue_site_details.json`.
- Before/after/effective-copper and focused issue images are in `out/crop_dynamic_tasks/t01_r1/full_crop/` and `out/crop_dynamic_tasks/t01_r1/owner_issues/`. Rasterization uses `sips` and preserves each SVG's aspect ratio.
- The frozen T01 manifest still has the historical single mismatch in `t01_full_crop.png` (90/91 entries match). It was preserved; R1 reconstructs its comparison from verified source geometry artifacts and does not rely on that PNG.
- The local results manifest is `out/crop_dynamic_tasks/t01_r1/SHA256SUMS`.

## Limits and disposition

This remains geometry-only experiment evidence using the same native inventory and Shapely kernel as the prior T01 work. It does not establish electrical net intent, independent parser/kernel agreement, equivalence to the expert EDIT, a native KiCad-exported candidate, DFM, manufacturing approval, or engineering acceptance. The physical component IDs mean source same-layer geometric contact, not net identity. Independent Cursor review is `NOT_RUN: CHANNEL_UNAVAILABLE`.

The accepted amendment requirements for coverage, dynamic growth, designated round outlines, bounded trace ports, real same-seed response, counterfactuals, assembled checks, reproducibility, fair static comparison, and inspectable outputs are met within those limits. No T02–T07 work is authorized or started. Commit the owned T01-R1 changes locally and stop for review; do not push.
