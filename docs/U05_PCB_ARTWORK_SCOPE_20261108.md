# Explicit 3020212866 PCB artwork scope

The user authorized PCB artwork only, excluding the drawing sheet, title block
and example patterns. The original `a-top.art.gbr` has 25,496 native plotting
objects. The alternative `tcir.gbr` remains excluded after its existing arc
radius check failed; that check is unchanged.

The isolated intake binds the exact original artwork hash, mechanical
`a-outline.art.gbr` hash and one native closed-contour geometry hash. The
contour comes from validated native lines/arcs, not screenshot pixels or an
arbitrary rectangle. Missing or changed registered inputs halt. All original
files remain read-only.

Whole plotting objects inside the contour are retained. A positive object
straddling the contour halts, except an original stroke whose complete native
centerline lies on that contour within the existing polygon sag bound of
**0.000001 mm (1 nm)**. Such a marker must subsequently
be removed by the unchanged confirmed-enclosure predicate. It is never clipped
in half, retained as electrical copper or granted a growth exemption. The
actual first crossing, ordinal 6719, is the illustrative perimeter stroke;
the native overview and zoom prove its location on the mechanical contour.

Necessary clear objects remain whole even when their footprint extends beyond
the contour. The selected objects keep their original drawing order: dark,
clear and later dark restoration remain distinct native operations. Excluded
draws/flashes become moves; excluded region delimiters become comments. All
coordinate words, byte offsets and modal state remain. Every retained native
atom must have identical type, polarity and geometry WKB. The complete resolved
selection is compared with its designated original material using the existing
1e-12 mm² area and polygon-sag numerical bounds. This is source selection only:
no growth, clipping, smoothing, hole filling or positive-only flattening.

The source-selection trial retains 5,284 objects and excludes 20,212 sheet
objects. All retained native atom checks pass; the actual complete resolved
material is exactly equal before perimeter removal, with no numerical buffer
needed. Forty-six boundary-crossing marker atoms are specifically bound to
mandatory confirmed-frame removal. The combined receipt maps both exclusions
and later enclosure removal to original source ordinals and hashes.

Scope metadata and the staged original outline are included in producer and
assembly bindings. Construction and both native assembly evaluations remain
mandatory. Normal unscoped receipts and prepared bytes must remain unchanged;
incremental adoption still requires three fresh assembly workers and exact
prepared-source/build equality before retaining earlier stage results.

At this coding checkpoint, 50 scope/assembly/prefix regressions and 954 focused
tests pass. They include ordered clear/dark restoration, surviving cutouts,
unclipped clear footprints, rejected straddling pads, mandatory perimeter
removal, source/outline mutation and retained occurrence identity. The earlier
test failures and read-only studies remain separately retained. Full native
source-assembly qualification and normal-app integration are pending.

Evidence is under `out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/`
`export_inclusive_identity_01/remaining_boards_01/shared_gap_entry_contour_01/`
`pcb_artwork_scope_01/`. The parent contains the user scope authorization and
native outline study; the slice contains `actual_selection_04/RESULT.json`,
`outline_crossing_visual_01/native_outline_crossing.png`, `TEST_SCOPE_03.log`
and `FOCUSED_01.log`.

The active 3020212849 continuation uses its separate immutable bounded-memory
revision; this slice cannot alter that running producer. Primary 3020212826
must not receive another full run. All checks, limits and six deferred broad
test findings remain. The 10% performance target is waived. Prior `.DS_Store`
custody remains EXPLICIT_UNWAIVED_UNATTRIBUTED. Owner PENDING_USER, independent
NOT_RUN, electrical/manufacturing NOT_ESTABLISHED.

The first actual native assembly qualification was deliberately stopped with
its failed operation retained. A one-second sample placed all 768 main-thread
samples in GEOS's general Hausdorff-distance calculation on the complete,
identical source scene. The correction first proves exact complete set
equality, including every hole and disconnected island. That proof establishes
Hausdorff distance zero mathematically; unequal geometries still run the
unchanged distance calculation and both area checks. No predicate, tolerance,
input or geometry is removed. The added regression rejects any redundant
distance call after exact equality. All 51 scope/assembly/prefix tests pass.
The stopped job remains unchanged; native qualification uses a fresh immutable
source revision and a separate job, never a resume of the stopped worker.
