# C01 T05 junction implementation — 2026-10-29

The owner authorized the earlier T05 neck design to be implemented and applied to C01 before T02. This overrides the historical planning-only header of `docs/crop_dynamic_tasks/tasks/T05_JUNCTIONS_AND_DYNAMIC_DECISIONS.md` for this bounded operation. No T02, T06, routing, deletion, ABI implementation or native-board modification is included.

## Implementation and constraints

`src/trace_land_junctions.py` constructs additive smoothstep tapers along the current fixed route into an explicitly source-qualified circle or rectangle. It uses one fixed contract: maximum local flare 1.5 times the existing T04 neck width, two-width approach length, half-width penetration, 17 declared cross-sections, 12 bounded reduction iterations after the full-flare trial, and 0.02010 mm added-copper clearance to foreign copper (0.02000 mm hard floor). This local junction flare does not change the T04 nominal width or route of any source part. Width measurements allow the declared 0.00001 mm geometry error on each side. The protected-owner difference bound is 1e-12 mm²; exact immutable-part hashes remain authoritative for preservation.

The patch must stay in the route-bound writable window, intersect both owner operands by positive area, and retain the route witness after erosion by 0.45 times the current trace width. Existing owner contributions are never removed. Foreign copper receives no component/net exemption. Only complete coverage by the explicitly selected trace–land union qualifies a foreign primitive as internal, recorded in each check. Optional growth that cannot fit is rejected, preserving the original state. Clearance checks concern actual additions; they neither repair nor certify inherited original gaps.

The implementation uses a bounded taper operator, not a universal fillet solver. Curved polygons that become invalid, insufficient approach spans and side contacts without a qualified route entry remain explicit unchanged/unresolved records. No proof of arbitrary electrical intent or continuous differential width is claimed.

## C01 result and source binding

Authoritative candidate: `out/crop_dynamic_tasks/c01_t05_junction_proposal_20261029_256/`.

- 47 source-qualified approaches: 12 additive tapers, 35 unchanged candidates.
- Two additional source-side contacts remain `UNRESOLVED_LOCAL_OPERATOR`; they are not credited as completed repairs.
- All 47 qualified contacts involve circles. No qualifying actual C01 rectangle contact was found; rectangle support is demonstrated by the positive operator test, not an invented C01 rectangle result.
- Added crop copper: 0.02277093484042142 mm².
- Cumulative after WKB SHA-256: `68ddaf83b23cd3aa2dfc45838e7852ba9b8fe44c75199f514589361f86a299a9`.
- All 266 frozen T01 files and 126 T04 source parts retain their hashes. Fixed routes and nominal widths remain unchanged. T02 is not applied.

`tools/run_c01_t05_junctions.py` binds native source identities, the original positive-area trace/land contacts, frozen T01 operands, T04 widths, full-route source IDs, direction and original route-span arclength. Accepted patches, windows, stations, every bounded attempt and final simultaneous checks are saved. Runs 253–255 remain historical diagnostics; 256 adds explicit source-span binding without changing the 255 geometry.

`tools/verify_c01_t05_junctions.py` independently reconstructs the saved approach from its bound full route and arclength, reconstructs each patch and window byte-for-byte, verifies source-contact and width identities, queries the complete current source scene around the reconstructed window, checks all other accepted patches, and reassembles the final cumulative WKB exactly. This is a second execution path by the same assistant, not independent review.

Replay: `out/crop_dynamic_tasks/c01_t05_replay_20261029_257/REPLAY.json`, status `PASS_SAME_ASSISTANT_SOURCE_BOUND_T05_REPLAY` for all 12 patches.

## Validation and visuals

33 focused tests pass: the 11 T05 cases plus source-offset width, bounded width solver and prepared-scene regressions. Required negative controls reject oversized writable-window violations, disconnected patches and too-thin necks for their declared reasons. Circle and rectangle positive cases pass. Additional controls cover foreign copper contact, bounded fitting, invalid widths and contract changes.

Command:

```
.venv/bin/python -m pytest -q tests/test_trace_land_junctions.py tests/test_source_offset_width.py tests/test_bounded_width_solver.py tests/test_prepared_width_scene.py
```

Review: `out/crop_dynamic_tasks/c01_t05_visual_review_20261029_258/index.html`.

The review contains ORG, pre-T05, final and exact-added-copper full-crop panels at common coordinates; before/after detail pairs and exact patch-bound locators for every accepted taper; all unchanged reasons and the two unresolved side contacts. Forty rendered images have individual source/result/viewport/hash bindings. The full growth panel and first detail were visually inspected. This is local geometric delivery, not native export, electrical/manufacturing acceptance, independent qualification or automatic authority for T02/T06.

## Completion boundary

The requested bounded T05 operator is implemented, tested, source-replayed and applied to C01 with saved visuals before T02. Full-crop neck remediation is not established: the explicit KEEP and unresolved records remain. Future T02 must consume this cumulative scene and must not erase or recompute frozen contributions without separate authority. No audit verdict or human visual judgment is prefilled.
