# Declared source formats and exact addition overlays

## Cleanup proposal isolation before T04

The later 4,225-occurrence source (`cdaed1566b093b0b1c9fda9252c99f7534a9482b4015fd32dab8ddf72b0721c5`)
opened successfully but failed cleanup before T04. A proposed cut split a filled
source contribution and left a positive-area detached sliver. The final board
topology check correctly rejected the batch (269 to 270 components).

`source_edge_cleanup.check_split_source_contacts` now checks proposals that
increase a source's polygon-face count before committing them. It borrows the
already prepared neighbours and the existing finite-face contact sweep. An
overlapping contribution can support a split; an increased local component
count leaves that feature unchanged and unresolved. There is no area waiver,
coordinate adjustment, new clearance search, union or index. The final assembled
board check remains mandatory. This correction changes neither T04 nor T05.

The exact bounded failure replay preserves all 4,225 source contributions,
passes the unchanged final topology check and records the rejected proposal
separately. Regression cases include an arbitrarily small detached face, a
substantial split, overlapping support and whole-contribution removal. Fresh
full-source execution and packaged-viewer results are separate evidence.

The fresh packaged run then exposed `RESIDUAL_MITER_OUTLIER` while preparing
optional chain end matching on native route `JR-6f799e808dee0413`. The frame
check ran outside the existing local construction-limit handler. The caller
now records this recognized limit and `RESIDUAL_REVERSAL_JOIN_UNSUPPORTED` as
`KEEP_PRECEDING_RESULT; CONSTRUCTION_LIMIT` before rail allocation. Every source
body and prior growth decision stays unchanged. The ribbon constructor still
rejects the same frames; unexpected frame errors and final-output checks still
propagate. This changes no growth rule, clearance threshold or search structure.

The completed full-board diagnostic subsequently exposed a saved-display-only
wire overlay. `viewer_abi.board_growth.area_parts` borrows every positive-area
polygon recursively and omits zero-area wires/points from display partitions.
It changes no sealed geometry or treatment verdict. Both whole-board and T04
display serializers use it. A failed presentation can be retained while a new
display derivative is prepared with `run_copper_pipeline.py prepare-display
--job /ABSOLUTE/COMPLETED_JOB --output /ABSOLUTE/FRESH_DISPLAY_DIRECTORY`.
This authenticates the same phase seals, writes separate viewer data, and runs
neither trimming nor T04. Existing failed presentation directories cannot be
resumed by this option; the destination must be fresh.

The 2026-11-27 `01_top.art.gbr` failure happened before treatment. Its standard
millimetre, absolute, leading-zero 3:5 declaration was absent from the intake
whitelist. `gerber_source_profile.py` now uses the declared matching X/Y digit
counts (1 through 6 each), preserving integer source-grid coordinates, original
bytes, modal coordinates, object order and source spans. Existing L33, L46 and
legacy trailing-zero behavior stays qualified separately. Ambiguous formats,
units, incomplete input and unsupported polarity still fail explicitly.

Source arc recognition follows the declared source grid. The existing L46
recognition allowance remains unchanged. This is not a clearance tolerance or
permission to alter source coordinates.

The subsequent full local run exposed a second checker defect. Subtracting two
valid polygon bodies returned two valid area components and a coincident line
4.44e-16 mm long. `normalized_additions.py` now extracts every exact polygon
component of that derived difference, including arbitrarily small polygons.
Zero-area lines and points are not copper. Extraction performs no union,
buffer, simplification, coordinate rounding or area-based exemption. Invalid
input/output bodies, invalid foreign copper and mixed direct construction
patches remain fatal. Every positive area component keeps the existing
clearance reservation and threshold.

A later local assembly exposed a GEOS unary-union shell assertion on three
valid trace/corner operands. The normal union remains the first operation.
On a kernel exception, `finite_profile_union.assembly_union` tries exact
binary unions in the two operand orders. A recovery must be valid polygonal
copper and retain every operand's complete area with zero missing area; no
threshold waiver is used. Otherwise the original error remains fatal. The
existing local finish-input, route-floor and emitted-body assembly sites use
this helper and record exceptional recoveries in
`local_assembly_union_recoveries`. There is no board search or preparation
rebuild. The exact reproducer
is `tests/gerber_u05/fixtures/l35_local_union.json`.

The same kernel can silently return nested shells from valid route inputs.
`native_contact_support.assemble` screens the route union's validity before
ownership/counting consumes it and uses the same exact recovery for this case.
This adds no clearance pass; the operand-area custody checks execute only for
a recovered union. The eleven-source exact regression is
`tests/gerber_u05/fixtures/l35_route_union.json`. A saved assembly replay of all
384 routes passed, with one reverse-order recovery. That replay is distinct
from a fresh T04 run.

The same duplicate nested face also affected the pocket checking image and
shoulder discovery outline. The existing `finite_profile_union.polygonal`
helper now omits a redundant face only when another retained valid face
exactly covers it. Retained faces keep their original WKB coordinates. The
result must be valid; invalid rings and overlapping faces without exact
containment are not repaired. No extra union, buffer, snapping or area waiver
is involved in this containment recovery. Holes and positive disjoint islands
remain intact. The exact shoulder outline regression is
`tests/gerber_u05/fixtures/l35_shoulder_overlay.json`.

This central recovery replaces the engineering trial of a second, route-grouped
board image. That alternative is not included in the final source. The pocket
checker keeps its existing image assembly and union count. The exact saved
2,355-contribution board and shoulder replays passed with every original
overlay face still completely covered; a fresh run is a separate obligation.

These corrections retain the widening rules, local shoulder families, shared
preparation, phase order and T05 boundary. The exact failed
operand regression is `tests/gerber_u05/fixtures/l35_addition_overlay.json`.
Its source identity and coordinates remain bound to the retained failure.

## Original source floors remain obstacles throughout construction

The first complete construction exposed nine real guard violations. Its
temporary working profiles had omitted original trace end caps, which were
restored when source contours were emitted. Checks against those shortened
working profiles passed at 0.04013–0.04233 mm, while the actual original caps
left only 0.03677–0.03987 mm. These findings must not be downgraded.

`ResidualScene` now borrows the admitted traces' immutable constructor floors.
For a changed working profile it prepares only `floor - working_profile`, once
per accepted geometry object. Queries conservatively include the floor bounds
in the existing index. Residual/default, arc and corner constructors consume
the same disjoint current/floor reservation parts. There is no second board
index, per-defect union, ownership reconstruction or cached clearance verdict.
Required floor reservations fail explicitly on an index capacity miss.

The floor is the caller's authenticated constructor floor, including approved
trimming. It does not restore raw pre-trimming copper or turn removed areas
into keep-outs. Working profile geometry and widening rules remain unchanged;
unsafe proposals now encounter the original obstacle before acceptance.
`l35_source_floor_reservations.json` retains all nine exact witnesses.

An uncommitted optional source trial may also raise a GEOS overlay exception.
With valid admitted/source operands, the shoulder step retains its rejection
operands and tries the next existing bounded variant. It never commits the
failed proposal. Invalid source floors and erroneous final output still halt.

The source-floor fix passed spacing and all connection cases in the separate
17-route cohort `bounded_floor_fix_03`. That run then caught a bookkeeping
error: a zero-change feature previously labelled resolved by a neighboring
bridge still had its old shoulder. Such a record is now explicitly unresolved
when its baseline is preserved and added/removed areas are both zero. A
material-changing failed correction retains its failure status.

The earlier complete `local_joined_06` and bounded attempts remain failed and
unchanged. They do not qualify a package. Fresh bounded and full-board checks
remain required on the corrected implementation.

Failed jobs remain unchanged under
`out/lacie_work/new_input_3020_debug_20261127_01/`. A corrected implementation
requires a fresh job; never resume or relabel a retained failure. Consult that
directory and `out/lacie_work/copper_pipeline_viewer_038_20261127_01/` for
execution receipts and the actual deployment result. A package build alone is
not a completed viewer test or manufacturing acceptance.


## Detached generated carriers on the new input

The first full run with the source-floor correction (`local_joined_07`) had no
remaining spacing violations. It still failed component counting for two routes.
Inspection showed intact original trace paths, two numerical slivers and a
1.182319e-6 mm² generated corner fragment. These were detached optional skin,
not an original source gap. The bounded cohort had not produced the same skin
because its surrounding routes remained fixed.

`native_contact_support.retain_generated_carriers` now reuses the existing local
carrier selector only when an existing route assembly reports extra components.
It retains complete source polygon faces with their exact coordinates. Removal
must touch no positive original source area and lose no positive area from the
attached widening. The resulting route must retain every original component and
show nonnegative growth over its authenticated entry floor. Otherwise the old
failure remains fatal. This creates no addition, clearance query, board union,
new index, new repair family or source/ownership reconstruction.

The same narrow correction runs before optional contact recovery and, when
needed, at the existing final boundary assembly. Exact source gaps remain failed;
distinct original islands remain present. The real two-route regression retains
all attached widening and leaves respectively 0.1004348172 and 0.0299794132 mm²
of growth over source. The earlier failed construction remains immutable.

The following full run (`local_joined_08`) exposed a union-dependent count:
the route union hid a detached generated face, while the containing owner union
retained it and failed final connectivity. Native route custody now counts the
actual per-source finite faces through the existing `boundary_finish` contact
sweep. Overlaps, holes and touching contacts retain their exact predicates;
there is no area tolerance or second ownership index. Route count refreshes
after local edits use those same operands instead of another union topology.
The carrier selector retains whole attached contact groups unchanged and
rejects only detached generated faces with zero original source overlap.

`test_generated_carriers.py` includes the exact hidden-face case, overlapping
sources, edge/point contacts, a real gap, a hole, inherited original islands
and invalid operands. The 0.3.11 isolated snapshot contains these source
corrections and excludes unrelated dirty T02/T05 work. Qualification receipts
are under `out/lacie_work/copper_pipeline_viewer_0311_20261127_01/`; inspect
its report for the current bounded, full-board and Neo viewer dispositions.
The 0.3.10 bounded regression remains failed: a later interface edit also
produced detached skin. The same carrier rule now runs at existing wider-end
and interface contact refreshes as well as initial and boundary assemblies.
An unchanged route gets no extra contact scan, index or complete-board union.

Fresh `bounded_finite_contacts_08` passed the combined 22-route regression
cohort. Fresh joined `local_joined_09` completed on the 0.3.11 source: all 384
native-route connection checks and functional/reference/pocket checks passed.
The nine remaining endpoint/corner review findings remain recorded and
nonfatal. Both phase views were prepared. The release report separately
records the actual packaged Neo trial; do not infer it from local completion.

The fresh Neo normal file-chooser run
`viewer-EFE9E8B1-4328-43D9-9036-47283C17D3CD` also completed with all 384
native-route checks and functional/reference/pocket checks passed. All 18
same-window phase-navigation checks passed, including grey copper, green
additions and zero treatment requests. See the 0.3.11 release report and
`NEO_COMPLETION.json` for exact fingerprints, timing, memory and retained
review findings. Core/payload hash parity passed after completion.
