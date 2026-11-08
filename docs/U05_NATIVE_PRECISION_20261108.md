# Coordinate-preserving native assembly — isolated correction

3020212849's fresh 710-route ladder completed with exactly the retained factors
and nominal/envelope union hashes. Both complete width checks passed. Its T04
completion then failed `PREDECESSOR_SOURCE_COPPER_REMOVED`; the whole stage remains
failed, with subsequent operations NOT_RUN. All 75,203 files remain preserved.

The native model combines unchanged analytic source cores with serialized grid
parents. In the undeclared pin profile, those parents retain GEOS fixed-precision
metadata. A cascaded union can propagate that model and snap the source cores,
despite their own floating precision. The actual diagnostic reproduces the exact
failed current-image hash: 91 of 143 owners show source loss, totaling roughly
2.34e-5 mm² in the global comparison.

Clearing only the parents' precision metadata, without changing any input WKB
byte, makes all 143 owner checks pass and the global missing-source geometry
empty. The isolated correction keeps the existing pin-profile canonicalization,
then resets a fixed-precision parent to floating metadata. An exact WKB identity
check rejects any coordinate change. Already floating parents are unchanged.

This applies to initial and later channel-completion unions. The declared 1 nm
serialization grid, 2 nm file budget, strict source-core predicate, clearance,
pin separation, source holes, complete fill rejection and cumulative 20% budgets
remain unchanged. Real removed source copper must still fail. This is neither
an area-epsilon increase nor an exemption from source retention.

Evidence is under `out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/`
`export_inclusive_identity_01/remaining_boards_01/shared_gap_entry_contour_01/`
`t04_final_scene_01/`: `ACTUAL_WIDTH_QUALIFICATION_01.json`,
`FAILED_CONTINUATION_CUSTODY_01.json`, `FINISH_DIAGNOSTIC_RESULT_01.json`,
`PRECISION_DIAGNOSTIC_01.json` and `FINISH_FINDINGS_01.json`.

Only the exact source hash pair is eligible for retaining connected T01 and
zero-movement T03. Connected T04/T02 completion cannot be retained under this
exception. Legacy workers do not execute channel completion; their qualified
geometry and proofs remain immutable. Fresh downstream native qualification is
still required. The primary 3020212826 board receives no further full run.

The change is unintegrated. Six deferred findings, explicit unwaived/unattributed
`.DS_Store` custody, and separate unfinished flattening remain preserved.
Owner PENDING_USER; independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.

Qualification under `native_precision_01/`: 102 focused regressions pass
(`FOCUSED_PRECISION_03.log`). The first test run retained a fixture failure: it
compared the established pin canonicalizer using floating equality instead of
its exact native-integer material contract. The corrected regression requires
byte identity with the existing pin canonicalizer and exact integer material.
The correction does not change that profile's existing behavior.

Production replay of the captured scene passes the strict source-retention and
143-to-143 component mapping predicates, all 143 owner checks and native
clearance. Its image hash exactly matches the coordinate-only diagnostic
(`CAPTURED_REPLAY_01.json`, 61.54 seconds). This is captured-scene qualification,
not complete T04 acceptance. All 47 native synthetic operations also pass,
including separate evaluations, actual export/reparse, corruption controls,
defect audit and highlighted rendering (`synthetic_nested_route_01/`).
