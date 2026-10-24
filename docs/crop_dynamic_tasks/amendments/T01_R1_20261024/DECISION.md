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

## Post-run range qualification — 2026-10-24

The separately calibrated run is bounded by the **largest observed EDIT radius within each ORG radius class**: 0.14506 mm for the 0.12497 mm class and 0.17012 mm for the 0.14999 mm class. These are same-job empirical class maxima, not universal design rules or per-site predictions.

A read-only comparison measured each of the 20 GROW candidate contours by its maximum boundary distance from its ORG source center and compared that radial extent with the uniquely center-matched EDIT circle radius. Eighteen of 20 candidate extents exceed their corresponding EDIT radius by more than the 0.00001 mm comparison tolerance; the largest excess is 0.015878655 mm. A direct maximum-boundary-distance check reports 20/20 within their ORG-class maximum final radius plus a 0.00001 mm radial tolerance. The result therefore supports **class-maximum-bounded growth**, not per-site EDIT-consistent sizing or expert-equivalent behavior. An exceedance is a descriptive difference, not an established design-rule or manufacturing failure.

This comparison does not feed EDIT geometry or per-site radii into construction. Maximum radial extent is a one-number summary of a potentially noncircular contour and may include local attachment-zone geometry. The source inventory and Shapely kernel are shared with construction. The comparison is diagnostic evidence only; it does not change the frozen acceptance policy, which remains at 0 of 3 required actual-crop adaptation events.

- Diagnostic report: `out/crop_dynamic_tasks/t01_r1_feasibility_20261024/site_range_comparison.json` (SHA-256 `377c15b72769c98da3c0b5b8174082bf5db0e913238f96e33ddb36830bb965c0`).
- Reproduction script: `out/crop_dynamic_tasks/t01_r1_feasibility_20261024/compare_site_ranges.py` (SHA-256 `9bd104c7616b574056bffe1d551c808994513d2f568b21f6a5b17c77f09ea6d9`).
- Review checkpoint: the existing ChatGPT conversation judged the class-bounded claim supported, the broader EDIT-implied per-site sizing claim not established, and recommended documenting the limitation without retrofitting per-site targets or changing the constructor. The review was summary-based; local files were not attached for direct inspection.

**Current disposition remains `PARTIAL / NOT_ACCEPTED`.** Task execution is complete and class-maximum compliance is reported PASS_WITH_SCOPE_LIMITS; individual EDIT-radius correspondence is 18/20 EXCEED; actual-crop adaptation is 0/3; owner acceptance remains NOT_ACCEPTED. No construction, priorities, order, or acceptance thresholds were changed as a result of this diagnostic.

## Nearest-copper spacing review — 2026-10-24

After visual review of the calibrated output, the owner selected nearest-copper spacing as the primary growth boundary. A new ORG-bound run replaces the class-radius cap as the controlling reach: for each target, isotropic reach is its edge-to-edge distance to the nearest other target's current geometry minus the 0.020 mm hard experimental gap, floored at zero. Source F.Cu copper, source-owned trace-port zones, and reserved priority outlines still clip growth directionally. EDIT is descriptive only and does not select sites or limit construction. The nominal 0.025 mm construction buffer is used to build obstacle envelopes; it is not a claim of final clearance. The nearest-target bound controls reach, while the complete source-copper obstacle model controls local collision clipping.

The fresh run is at `out/crop_dynamic_tasks/t01_r1_spacing_driven_20261024/`. It records 53 source occurrences across 51 unique geometries: 26 `KEEP_PRIORITY_ROUND`, 23 `GROW`, and 2 `KEEP_CONSTRAINED`. The fresh-process verifier reports `PASS_WITH_SCOPE_LIMITS` (18/18 checks after pair-count reconciliation). The minimum measured final gap is 0.024990165659575386 mm: it clears the 0.020 mm hard experimental criterion, but is 0.000009834340424614 mm below the nominal 0.025 mm construction buffer. No manufacturing clearance is claimed.

The oversize report records source radius, nearest-target spacing, reach, maximum radial extent, added area, and clipping evidence for all 25 nonpriority sites. The largest review examples remain unqualified by size: a 0.0254 mm source radius reaches 0.1733 mm (6.82x, +0.1479 mm); a 0.12497 mm source reaches 0.23785 mm (1.90x, +0.1129 mm, 0.11249 mm² added). These are inspectable space-feasible results, not established sizing intent. The report's top-three flags are navigation aids only; they are not rejection thresholds.

The interaction screen compares each earlier accepted addition with each later nonpriority site's frozen-ORG maximum spacing envelope. There are 25 nonpriority sites and 300 possible ordered earlier/later pairs in the fixed schedule. It screens 291 pairs whose earlier site actually grows. The remaining 9 are the later successors of the two `KEEP_CONSTRAINED` sites at orders 45 and 46 (one and eight successors, respectively); those earlier sites add no copper and cannot cause a prior-acceptance adaptation. All 300 pairs are therefore reconciled. None of the 291 screened additions comes within the 0.025 mm construction buffer; the closest is 0.086818944 mm. Dynamic and frozen-ORG candidate geometries are identical across all 51 sites. This actual crop demonstrates 0/3 required accepted-neighbor adaptation events, so behavioral acceptance remains `PARTIAL`.

The existing ChatGPT review thread judged this evidence sufficient for **conditional owner review**, not T01 acceptance. It recommended retaining the separate statuses: task execution `COMPLETE`, local checks `PASS_WITH_SCOPE_LIMITS`, visual size qualification pending owner judgment, behavioral objective `PARTIAL (0/3)`, owner acceptance `NOT_ACCEPTED`, and electrical/manufacturing/native qualification `NOT_ESTABLISHED / NOT_RUN`. This was a summary-based audit; the reviewer did not independently inspect or execute the local artifacts.

- Run report and scene: `out/crop_dynamic_tasks/t01_r1_spacing_driven_20261024/t01_r1_report.md`, `t01_r1_run.json`, and `full_crop/t01_r1_added_copper_overlay.png`.
- Per-site size and interaction audit: `out/crop_dynamic_tasks/t01_r1_spacing_driven_20261024/spacing_oversize_and_interaction_audit.json`.
- Fresh verification and exact checks: `out/crop_dynamic_tasks/t01_r1_spacing_driven_20261024/fresh_verification.json`.
- Artifact hashes: `out/crop_dynamic_tasks/t01_r1_spacing_driven_20261024/SHA256SUMS`.
