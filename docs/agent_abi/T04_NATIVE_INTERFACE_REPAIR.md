# T04 native interface repair — 2026-11-24

This is the T04-only continuation after the saved large-copper trimming result.
It does not execute T01, T02, T05, re-run cleanup, export artwork, or promote a
saved diagnostic to production acceptance. Copper stays grey in the dedicated
**T04 trace growth** workspace.

## Construction and verification

`ribbon_profile.build` retains exact frozen end sections. It detects locally
folded cross-section cells even when the complete outline is a valid polygon;
those cells use the established swept-cell union and ordinary positive-addition
verification. Free-interior packing budgets cannot shrink a frozen interface.
One shared residual field continues through native occurrence seams.

`corner_transition.describe` carries the actual saved end sections and true
member spans. Plotting-end chords cannot substitute another corner normal.
An unconstructed connector inherits an adjoining frozen frame for proposal
construction, while its actual narrow skin remains the starting operand.
`joint_receiver_chain.extend` follows same-width, unbranched native adjacency,
including true ends of complete shared members. It never joins a shared member
at an internal custody seam or crosses a fixed covered occurrence for growth.

Joint skin proposals must attach to their route support. Detached generated
faces below both the existing native area and thickness bounds are retained as
rejected evidence, not emitted as copper. Subtractive tangent proposals that
produce invalid contours or newly detached long, thin faces retain the valid
original optional part. Original source/group operands are not repaired,
rounded, snapped, or buffered as output. Final component counters still count
all positive emitted faces.

When additions cannot reconcile an interface, `joint_reconciliation.run`
constructs local C1 retractions of optional widening. It matches both physical
sides, including equal-width sections with different offsets. Inputs are the
saved endpoint/corner work batch, emitted source contours, native descriptors,
width caps, covered-source IDs, and immutable original copper. It builds no
scene index and makes no clearance search. Masks retain original and covered
copper; local component, pocket, native error, and interface predicates remain.
Interior cut islands are omitted rather than creating holes. Newly detached
optional tips use the existing bounded tip treatment and retain exact evidence.

The new sections at internal custody seams are derived from the admitted cubic
field and its input skin before the final audit. They supersede old optional
width records inside that taper; they do not reset its derivative at a source
occurrence. Every replacement is audited against the final emitted route.
A completely bounded mutable native chain between two fixed, same-width
continuations can return to its exact original contours when no admitted C1
transition exists. This is a failed-construction KEEP decision, not a new
connected-to-fill eligibility rule or a whole-route freeze.

The full-board follow-up exposed a sampled wider section absent at the exact
arc joint and an equal-width right-angle turn whose additive transition was
outside its reach cap. The subtractive constructor first tries the common
emitted section, then (if it contains the native carrier) the original carrier
width. This second target retracts optional growth on either side; it cannot
add copper or remove original material. All original-floor, contact, pocket,
custody-section and final endpoint predicates still apply. It is a local
taper, not a route-wide growth exclusion. Both target modes and rejected
attempts are retained in the recipe.

For the original-carrier target, retraction includes the shared outer joint
cap beyond both incoming native endpoint planes. Per-arm masks alone can
leave thin connected projections that component and endpoint counts do not
detect. The cap uses the exact protected source floor; an independently
tessellated circle is not a substitute. The local radius remains bound to
the existing width caps. Positive-delta, floor and topology checks are unchanged.
The bounded 08 numeric pass was explicitly rejected by this visual gate and
was never published.

Raw constructed group bytes remain immutable evidence. An explicitly recorded
final interface mask can retract optional emitted group ends. Inspect
`joint_interface_reconciliation` and `joint_interface_cut_shapes`; do not read
raw group-preservation flags as a claim that these final optional ends were
never refined. Original source geometry remains the floor.

Final functional checks consume the exact source contours serialized for the
viewer, rather than reintroducing redundant raw group/joint operands.
Endpoint audit buffers are process-local and reused only for the exact same
immutable route operand; changed route operands rebuild their own buffers.
No distance-engine override, resident-index budget increase, clearance-threshold
change, or persistent keep-out on previously trimmed space is introduced.

The nominal 0.250 mm cutoff and adopted 80% coverage threshold remain in force.
Policy revision 6 measures every complete candidate route against independent
stage-entry copper as well as the broad-fill image. The earlier broad-fill
image excluded all maintained native strokes, which missed filled artwork
represented by overlapping strokes: the six owner-reviewed chains belonged
to four routes with more than 99% independent area coverage. Those complete
routes must stay unchanged before any growth or smoothing constructor runs.
The measurement excludes every member of the candidate route and all exact
normalized member aliases. It borrows the shared revision contribution index,
clips neighbours to the route, and unions only those local intersections.
No transitive connected-to-fill protection or private full-board index is
introduced. Ordered support, area, fraction and covered-geometry hashes are
retained in `candidate_route_coverage`; historical policy snapshots retain
their earlier semantics.

The occurrence coverage classifier also distinguishes an
exact cover from a coincident-edge residual within **both** existing native
area and coordinate bounds. Exact aliases remain excluded from coverage.
A real deeper tip cannot be suppressed by its small area alone.

## Execution and evidence

Prepare LaCie with `tools/Prepare_LaCie_Workspace.command`. Run tests with
`tools/Run_PCB_Tests.command`. All jobs, caches, logs, intermediate geometry and
UI evidence belong under `out/lacie_work/`. Failed attempts remain separate.

Use `tools/run_t04_after_cleanup.py` with explicit `--source-job`,
`--cleanup-result`, `--preparation-from`, and a fresh `--output` directory.
A bounded `--scope` JSON contains `requested_routes`; omit that flag only for
the authorized full-board run. Do not resume an old failure or overwrite it.
The source inventory and policy are captured in each job. Existing trimmed
preparation is a donor, not a treatment acceptance certificate.

The engineering continuation is under
`out/lacie_work/t04_connection_corner_endpoint_fix_20261124_01/`.
`CONNECTION_PROBE.json` identifies the original spurious component;
`AFFECTED_ROUTE_SCOPE.json` covers all 69 routes with prior connection, corner
or endpoint findings. `ELIGIBILITY_AND_REPAIR_SCOPE.json` extends that cohort
to 73 routes, including all four owner-reviewed covered routes. The stopped
first full-board job is retained as an owner-directed eligibility correction,
not published. Replays are explicitly separated from fresh bounded
jobs. `audit_result.py` extracts completed saved results without treating
geometry and checks code identity, final native connections, endpoint sections,
corner dispositions, and preserved contributions.

A diagnostic runner status alone is insufficient: require the engineering
audit's `all_requested_geometry_checks_passed` before using a result as the
completed correction. It must have zero failed native connections, zero failed
endpoint sections, zero unresolved corner records, and passed existing reference,
functional, pocket and preservation checks. Visual profile review is required
in addition to these numeric checks. Preserve actual remaining findings.

Publish only a completed geometry/report pair through `tools/viewer_live.py`.
Prepare its existing board presentation with `tools/viewer_board_growth.py`,
then its dedicated T04 presentation with `tools/viewer_t04.py`. Navigation and
selection consume saved data; they do not execute geometry treatment. Run the
native `--t04-smoke` workflow and inspect the visible grey result.

## Qualified engineering checkpoint

The final fresh bounded cohort is
`out/lacie_work/t04_connection_corner_endpoint_bounded_20261124_09/`:
75 route connection checks, 1,324 endpoint checks, zero unresolved corners,
and passed saved cap-projection and owner-reviewed KEEP proofs.

The final fresh full-board diagnostic is
`out/lacie_work/t04_connection_corner_endpoint_fullboard_20261124_03/`:
1,465 route connection checks, 3,205 endpoint checks and zero unresolved
corner findings. Its complete job wall time is 459.903661 seconds.
The six owner-flagged chains have 24 byte-identical input/output source
segments across four routes. The independent cap checks pass both additional
full-board cases. All 23 native T04 viewer smoke checks passed, including grey
rendering in every state and zero treatment execution requests. The visible
dedicated T04 viewer was inspected on revision
`9e3d9e381df44f3cb3f852a5eaba0cb9`.

The report, sealed receipt, negative controls, positive profiles and viewer
evidence are under
`out/lacie_work/t04_connection_corner_endpoint_fix_20261124_01/FINAL_REPORT.md`.
This is an engineering diagnostic checkpoint; export and production acceptance
remain outside its scope. Earlier failed and visually rejected results remain
separate and were not published.
