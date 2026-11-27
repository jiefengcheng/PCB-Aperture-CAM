# Original-source full-board T04 after large-copper cleanup

## Numerical-check correction — 2026-11-27

T04 now distinguishes complete-face numerical overlay artefacts from actual
source loss or positive additions, using the existing shared copper boundary
sections. This is implemented in the repository and carried unchanged into
the portable package. The widening constructor is unchanged. See
[T04_NUMERICAL_OUTPUT_CHECKS.md](T04_NUMERICAL_OUTPUT_CHECKS.md) for the exact
proof, regression controls, fresh Neo completion and memory/time accounting.

## Current corrected full-board result — 2026-11-24

The latest run is
`out/lacie_work/t04_connection_corner_endpoint_fullboard_20261124_03/`.
It passed 1,465 connection checks, 3,205 endpoint checks, reference/functional/
pocket and preservation checks, and the separate cap-projection check.
There are zero unresolved corner findings. The dedicated T04 viewer displays
its checked saved result in grey. Details and earlier retained failures are in
[T04_NATIVE_INTERFACE_REPAIR.md](T04_NATIVE_INTERFACE_REPAIR.md). The earlier
capacity/finalization findings below are retained history; this new run does
not resume or promote those attempts. Export and production acceptance remain
outside the diagnostic scope.

## Completed construction and corrected finalization — 2026-11-24

`out/lacie_work/t04_constructor_fixed_fullboard_20261124_05/` completed the
fresh full-board T04 construction in 540.404 seconds. Its existing reference,
functional clearance, route connection, pocket and fixed-group checks pass.
An added integration-only zero-overlap guard then blocked completion. That
guard was incorrect: subtractive cleanup does not create a permanent keep-out
for otherwise eligible narrow-trace widening. It did not change construction.

`out/lacie_work/t04_after_cleanup_finalized_20261124_06/RESULT.json` separately
finalizes those same completed contours. The old failed job remains unchanged.
The finalizer authenticates exact inputs, all construction-source file hashes,
settings and eligibility snapshots; it accepts only this specific obsolete
post-construction guard failure. It reruns the existing component predicates
and materializes the serialized contours without executing treatment again.
The retained construction hashes and 540.404-second execution are explicit;
the separate finalization took 98.078 seconds and is marked replay.

All 13,319 fixed contributions, including 12,675 protected large-fill source
contributions, remain byte-identical to the trimmed input. All 1,804 terminal
contributions are unchanged. Thirty-three admitted narrow-trace contributions
widen into 0.017032588807 mm² of previously removed space; this is reported
explicitly, not converted into an unrequested obstacle. Unadmitted restoration
or a changed fixed/terminal contribution still fails. Shared prepared source
and entry images supply the removal mask, avoiding three duplicate full-board
unions in the old guard. The revised handoff tests passed 21 tests.

The diagnostic covers 558 grown routes and 907 covered KEEP routes, with 1,465
passing native connection checks. It retains 104 unresolved corner records and
22 endpoint-section failures among 4,018 endpoint checks. It is not completed
T04 acceptance, export qualification or manufacturing approval.

## Architecture correction — 2026-11-24

The established T04 entry is the behavioral reference. The input handoff must
not implicitly activate a board-owned distance engine across T04. T04 retains
its existing `indexed_polygon_distance.measurement_engine()` instance, ordered
distance operands, thresholds, fallback behavior and handle lifetime. No search
or measurement algorithm, memory budget or verification threshold was changed
by this correction.

Shared source preparation is supplied explicitly through the optional `copper`
dependency of `group_stage.run` and `group_components.run`, solely to the
source-baseline pocket boundary. It supplies source custody, the explicit
trimmed baseline revision and batched candidate-neighbour queries. It does not
control T04's ambient measurement engine. T02/T05's existing shared-context
activation remains unchanged.

The normal original-source entry and an identity input handoff were executed
on the three retained original-source route cases. Their emitted copper,
allocations, coverage decisions/witnesses, native inventory, phase order and all
hybrid non-timing construction/proof fields matched exactly. Both preserved
their baseline distance engine throughout execution and retained 9,798,666
native-handle bytes. Input scene/lineage custody and corresponding preparation
identifiers differ intentionally. This is cohort parity, not full-board parity.
Evidence: `out/lacie_work/t04_architecture_parity_20261124_01/PARITY.json`
and its `REPORT.md` and two arm constructions. Relevant regressions: 118 passed,
one skipped, in `out/lacie_work/t04_architecture_preflight_20261124_01.log`.

The input-only architecture correction removed the resource failure. The
full-board attempt in `out/lacie_work/t04_architecture_fullboard_20261124_02/`
then stopped on actual extra route components. Its source cores were intact.
A full untrimmed-source control in
`out/lacie_work/t04_architecture_raw_board_20261124_03/` failed on exactly the
same seven routes, with the same component counts. Trimming did not cause
these failures. `BASELINE_COMPARISON.json` retains that comparison; this does
not claim all raw and trimmed contours are identical.

The local cause was independently buffered true-end points with extremely
small side-growth allocations. A point can lie outside the plotted chord by
more than that allocation, producing an unattached disk. The arc constructor
now retains every source face, including sub-epsilon originals, and rejects
only unsupported optional faces within both existing native area and coordinate
error bounds. A larger disconnected proposal is deferred explicitly. This is
a member-local attachment condition, with rejected WKB retained; it builds no
scene index and changes no allocation, clearance or shared search policy.

A separate optional tangent subtraction minted a tiny extra face. Ordinary
overlay bytes remain unchanged. A problematic overlay is reconstructed per
original optional polygon, and a parent that would acquire a new tiny face is
retained with `KEEP_ORIGINAL_OPTIONAL_PART; NUMERICAL_TANGENT_FACE_LIMIT`.
This conservative fallback neither deletes original copper nor weakens the
connection counter. Local limits remain in `tangent_finishing.attachment`.

The real saved-operand replay is `LOCAL_CONSTRUCTOR_REPLAY.json` in the failed
trimmed job. It includes all member-local rejections, not just islands visible
in the final failing route unions. Two pre-existing non-contained numerical
overlays are recorded as unchanged, not silently repaired or accepted by this
probe. The replay is not full-board verification. Constructor/input regressions
passed 69 tests with one skipped in
`out/lacie_work/t04_constructor_fix_tests_20261124_04.log`.

The corrected full-board job is
`out/lacie_work/t04_constructor_fixed_fullboard_20261124_05/`. Inspect its actual
RESULT/FAILURE before inferring completion or publishing. The `_04` attempt
stopped before treatment because raw-source role preparation was supplied for
the trimmed entry. It remains unchanged. Reuse trimmed preparation from
`out/lacie_work/t04_after_cleanup_fullboard_20261123_03/preparation`, not the
raw-source parity arm's preparation.

## Historical integration failure

Latest attempt: `out/lacie_work/t04_after_cleanup_fullboard_20261124_08/`.
It stopped after 561.567 seconds in final assembled functional-clearance
verification with `SHARED_COPPER_RESIDENT_CAPACITY_EXCEEDED` at the unchanged
128 MiB index/native-handle budget. Final cleanup preservation and viewer
publication are NOT_RUN. See its `REPORT.md`, `STOP_REPORT.json`, `FAILURE.json`
and sibling `.log`. Do not treat intermediate construction counts as accepted
assembled geometry. The viewer still has the prior validated cleanup revision.

The integration regression set has 107 passing tests and one skipped test.
Earlier failed/interrupted attempts remain retained. The query-only candidate
view avoids duplicate full-board owner/delta snapshots within the unchanged
192 MiB geometry-snapshot budget; it supplies exact source neighbours and changed
bounds, never verified ownership or acceptance. Optional numerical tangent
failures retain their original copper and exact operands as unresolved findings.

The owner explicitly requested this full-board T04 diagnostic on 2026-11-23,
superseding the earlier hold for this run. It invokes no T01/T02/T03/T05 or export.
The separate accepted-T03 `group_board_job` readiness route is unchanged.

`tools/run_t04_after_cleanup.py --source-job <original-source-job>
--cleanup-result <authenticated-cleanup-RESULT.json> --output <new-LaCie-job>`
authenticates the saved subtractive construction, original source identity and
all original refs. The current growth settings and nominal width policy are
captured together. The entry scene keeps the immutable raw `original_ref` and
source metadata; the explicit hash-bound `trimmed_entry` operand contract uses
verified current geometry as the constructor's preservation floor. Ordinary
untrimmed callers remain unchanged. No T03 acceptance is fabricated.

The existing full native-route selector accounts for every admitted path and
KEEP disposition with no bounded route list. Existing reference/functional,
connection, pocket, fixed-group and covered-copper checks still execute.
The combined result additionally checks unchanged fixed cleanup contributions
and trimmed terminals, and accounts for admitted widening into prior removals.
The prior removal mask is not a new clearance or permanent keep-out policy.
Only a passing result is serialized as a complete contour map relative to raw
source, so publishing cannot drop cleanup changes that T04 did not touch.

This is a construction diagnostic; endpoint/corner findings remain explicit.
`complete_t04=false`, `publication_ready=false`, no export or manufacturing
acceptance. Failure evidence remains in the exclusive output directory; no
automatic resume or retry. Viewer publication requires the completed validated
report/construction and a genuine native display acknowledgement.

For declared leading-zero source formats and exact mixed-dimensional overlay
handling, see [T04_DECLARED_SOURCE_INTAKE.md](T04_DECLARED_SOURCE_INTAKE.md).
