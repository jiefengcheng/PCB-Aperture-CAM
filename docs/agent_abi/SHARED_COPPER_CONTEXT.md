# Shared copper preparation and large-copper inspection

Implemented direction, 2026-11-22. This is preparation and bounded inspection,
not a full-board treatment or acceptance result.

For the current original-source cleanup checkpoint, agent startup ABI, user
decisions, remaining work and viewer continuation steps, start with
[BIG_COPPER_CLEANUP_HANDOFF.md](BIG_COPPER_CLEANUP_HANDOFF.md).

## Reuse the existing T02/T05 construct

`src/indexed_polygon_distance.py` remains the owner of the exact ordered
32-edge boundary sections, their native search tree and GEOS distance engine.
`prepared_boundary` is the single builder for both the existing operation cache
and its board-lifetime `BoundaryPreparation`. `component_distance` and the T05
prior screens acquire that same engine. No second large-polygon search algorithm
is introduced in the board context.

`CopperContext` adds durable source/revision custody and lifetime. Activate it
around a worker to make existing distance consumers use its retained preparation.
The connected Gerber T02/T05 worker entry does this automatically, including its
post-stage checks, and keeps timing
diagnostics separate from deterministic stage proofs. Physical clearance reuses
the same `OriginalOwners` construct. Distinct exact plotting representations have
separate version bindings within that one context; they are never substituted
using an area tolerance. Inactive geometry stays on disk in a native-stage worker.
Reopened native owner partitions validate their material, connectivity and source
assignments before use. A different functional partition keeps its original checks.

## Interface and lifetime

- `for_board(original)` derives the existing source identity from source-bound
  occurrence IDs. Explicit `CopperContext(..., source_binding=..., frame=...)`
  supports callers with independently supplied bindings. Inputs are complete,
  ordered positive material contributions after polarity composition.
- `acquire(changes, parent=...)` returns an immutable revision. Changed source
  occurrences overlay the original source index; deleted occurrences are
  suppressed. Affected complete owners are recomposed to handle merges/splits.
- `revision.sources(window)` prepares relevant neighbours before construction.
  `boundary_sections` returns complete source runs and `boundary_adjacency`
  exposes their closed-ring neighbours. No edge clipping or simplification.
- `activate()` shares the existing T02/T05 boundary/engine objects and validates
  resident boundary integrity at the stage boundary. `close()` releases native
  handles and trees. A new process reconstructs native structures once.

The retained client source and the raw native plotting path have a 45-vertex
count difference and zero measured symmetric-difference area. Their exact owner fingerprints
therefore remain separate. This distinction was reproduced and fixed before
claiming reuse of actual T02/T05 source ownership.

Format `shared-copper-context/2` stores source preparation, content-addressed
geometry, revision deltas and ordered boundary preparation under
`out/lacie_work/shared_copper_context/`. Source bytes/order, precision/SRID,
coordinate frame, format and kernel versions bind the entries. A change misses;
corruption stops. A locked atomic publication and fsync protect complete entries;
interrupted pending files never replace committed preparation. No native pointer,
stage verdict, eligibility decision or protected-pin history is persisted here.

Sealed T05 outer-acceptance jobs retain their stricter job-only write fence. An
authenticated explicit profile uses the same context implementation under that
job's `performance_cache/shared_copper_context`; it does not write the global
cache or widen the certified read/write policy. Ordinary connected workers use
the board-owned global preparation above.

The existing 128 MiB indexed-distance budget and 192 MiB geometry-snapshot budget
remain separate. Loaded source geometry is borrowed, not copied. Active native
handles and boundary indexes are pinned and share the 128 MiB budget; they are
not independently evicted between features. Capacity overflow is explicit.
Reported estimates are not an RSS limit: stage operands and temporary overlays
are measured separately.

## Batched cleanup

`CleanupBatch` freezes neighbours and bounded material crops for the feature list.
Proposals construct only
local source-supported cuts and retain terminal/path rules. `finish()` performs
one complete assembled-material check for the batch, then publishes its revision.
`trim_features` retains unqualified cases without applying them. The one-feature
compatibility entry is for individual cases, not a loop over board features.
Pad cleanup uses the shared source index. Joint-pocket completion prepares its
neighbours together and checks the assembled additions once per batch.

The area rule remains **strictly under 10% of the original causing pad/trace**.
The shallow-edge rule is separate. No tolerance, clearance, pin, nominal-width
or source-custody threshold is weakened.

## Current trim-only phase

The current bounded construction imports only the previously approved removal
mask over the original source. It excludes saved recess additions and T04 trace
growth. `CleanupBatch` requests `trim_only=True`; any proposed addition is rejected
before foreign-copper clearance work. Its assembled check requires zero added
material, the expected subtraction and unchanged component/hole counts. Retained
terminal contacts, declared/protected pins and original rectangular terminals
are still checked. Subtraction cannot reduce separation from other copper, but
does not by itself prove connectivity, width or electrical intent.

The missed straight-edge bump at source trace 2688 was detected but held by four
duplicate source flashes classified as lands. The explicit cleanup-only exception
requires exact duplicate aliases, binding to the existing Gerber disk constructor,
a matching-aperture original stroke endpoint, and support within the existing
coordinate envelope. Declared terminals and protected aliases still block it.
It never changes source family metadata or grants T01/T02/T04/T05 authority.
The complete physical bump, including overlapping contributions, must satisfy
the original causing trace's strictly-under-10% rule; individual tiny fragments
are not used to reduce the numerator. Failure evidence remains retained.

## Dedicated viewer

Large copper cleanup displays only large original connected copper objects
associated with the saved findings, plus their cleanup deltas. It does **not**
use the T04 widened-trace overlay. Original copper connected within these objects
stays grey. Unrelated trace objects and growth highlights are excluded.

An object picker, Original/Corrected/Comparison views, place navigation, filters,
reference edges and numbered markers inspect saved results only. The area-rule
and shallow-rule checkboxes filter the list; they do not alter treatment settings.
Source areas, percentages, saved contact evidence and unresolved reasons appear
per feature. The nominal 0.25 mm widening policy remains in the trace workspace.

Play/Pause advances the currently filtered detail list every four seconds and
fits each place, wrapping at the end. Manual navigation, pan/zoom, filter/object
changes, revision changes and hiding the page pause playback. Playback reads
saved cases only and makes no treatment or selection requests.

## Eight-place review extension

The eight retained findings were reviewed against their actual original source
contributions. Four nonrectangular places now pass; three remain above the area
limit and one rectangular bump is ignored by owner instruction. A trace-only
causing-source search had omitted pad caps. The explicit pad exception requires
that the complete physical bump is contained in the causing pad, remains strictly
under 10% of its original area, retains its centre and every original contact,
and has local broad-copper backing and supported flanks. Declared/protected pins
and terminals still block it. A nearby large pad cannot supply a denominator
for an unrelated trace bump. Rectangular causing pads are disabled by default.
The earlier bounded trim of rectangle 17569 is superseded: that rectangle and
its overlapping source contributions are restored exactly to the verified
parent. All rectangles and the nominal 0.250 mm trace remain unchanged.

A single flash may also qualify as redundant plotting at two distinct original
matching-aperture stroke endpoints, with the same source-disk and coverage proof
as the existing duplicate-flash exception. Source-family metadata remains intact.

The dedicated view retains all eight in numbered review order, including the
four corrected entries and the explicitly ignored rectangle. Each shows the original area, complete protrusion,
percentage, reference flanks and plain-English disposition. The current bounded
result contains 45 trimmed places, three unresolved findings and one ignored
rectangle, with no added
copper. Owner acceptance was recorded from the user's explicit review message;
it does not change the three retained over-limit findings or run the full board.
Evidence: `review_eight_no_rectangles_35/` and `review_no_rectangles_viewer_38/`
under the shared-copper qualification directory. The earlier `review_eight_30/`
and `review_eight_viewer_34/` remain superseded evidence without modification.

## Circular edge at a round stroke endpoint

The further marked curved-edge kink is at the round end of native line 15673,
centred at (45.164, -14.859) mm. Its smaller inner pad has a different centre.
The earlier circular reference family admitted native pad centres only, while
the straight-flank inventory did not cover this curved transition. The added
reference family binds the native circular aperture, original endpoint and
original stroke geometry, then reuses the existing circular-flank fit and its
unchanged 0.004 mm maximum fit-error bound.

Only the surrounding copper, contributed by strokes 14440 and 14451, is cut.
The entire physical patch is 0.01344373369847533 mm²: 4.73445% and 5.00349% of
their respective original areas. The fixed round-stroke owner and all rectangles
remain byte-preserved. Whole-material addition is zero; component/hole counts
stay 275/114. Native centre paths are retained and no clearance search executes.

Curved corrections use an explicit bounded removal mask and an exactly bound
difference reference. The constructor only subtracts; it does not synthesize
target copper by re-overlaying curved boundaries. Earlier rejected attempts are
retained separately. No geometry tolerance or clearance threshold was relaxed.
Boundary support comes from the same board-owned T02/T05 32-edge structure,
built once in the worker. No per-defect board union is introduced.

The viewer includes a Circular edges filter and the native endpoint explanation.
Current bounded evidence is `circular_endpoint_trim_50/`; its addition brings the
saved view to 46 trimmed places, three unresolved and one ignored rectangle.
This is a qualified owner-marked local case, not complete circular-defect
discovery or a full-board run.

## Qualification boundary

Evidence and the earlier retained capacity rejection are under
`out/lacie_work/shared_copper_qualification_20261122/`; top-level
`out/lacie_work/shared_copper_*.log` files retain test/build execution. Bounded
saved-cap parity covers 14 accepted and 3 rejected candidates, with 6 additional
inventory candidates lacking an established area rule. Exact large-copper distance
witnesses and shared native object identity are tested separately. The viewer
earlier displayed 40 trimmed places, 2 recesses and 9 unresolved findings.

That earlier restoration snapshot remains historical evidence. The current
trim-only replay and dedicated viewer verification are retained separately under
`trim_only_23/` and `trim_only_viewer_25/`; it contains 41 trimmed places and
8 unresolved findings. The displayed phase excludes recesses and labels
unresolved findings explicitly. The earlier `_24` viewer probe ran before its
revision-bound presentation was ready and retained that failure without accepting
an older sidecar.

There is no fresh complete T02/T05 pipeline, full-board T04 growth or export/
reparse qualification in this work. Six earlier joint findings outside qualified
windows remain outside this cleanup list. The owner accepted the reviewed result
and then deferred rectangular bumps; this grants no full-board or manufacturing
acceptance. Independent review is NOT_RUN / CHANNEL_UNAVAILABLE;
electrical/manufacturing is NOT_ESTABLISHED.


## Native revision publication retention fix — 2026-11-26

Native-stage revisions now use the existing LazyOwners representation on both
cold publication and warm restore. Output owner/delta blobs are persisted and
authenticated without becoming an additional resident snapshot beside active
T04 preparation. Active owners/indexes remain pinned; explicit owner loading
still enforces the same geometry budget. Repeated owner access reuses its
resident native object. Unchanged owners keep their existing geometry keys.

Publication borrows the existing source/overlay index to select possible new
contacts, keeps the exact owner predicate and metadata closure, and screens
remaining candidates once per owner. Already affected owners need no repeated
intersection proof. Fixed-grid inputs retain the exhaustive-owner fallback.
Inactive screening operands are temporary; no private owner index is introduced.
Affected-owner recomposition, source order, polarity-composed geometry, original
boundary coordinates, native distance machinery, kernel binding, format, and
128/192 MiB budgets remain unchanged. No stage accepts cached preparation as a
verification result.

Evidence is
`out/lacie_work/t04_shoulders_joined_20261125_01/publication_blocker_20261126/FINAL_REPORT.md`.
The saved client publication passes at 158.012 MiB with the active boundary index
and all 275 native ownership polygons retained, adding only 80,000 bytes. Its
revision bytes equal the old publisher's output exactly. Restart performs zero
owner recompositions. All 222 focused regressions passed. This is publication-
only evidence: the failed T04 job remains failed and no full-board treatment,
viewer publication or export was rerun.
