# Bounded bulk-edge restoration ABI

Status: opt-in prototype with bounded T04 entry integration, 2026-11-16. No full
pipeline enablement or full-board qualification. The user authorized leveling local bumps and open recesses up to
100 um against the supported smooth edge, with all safety checks retained.

## Adjustable provisional setting

`contracts/edge_restoration/settings.json` is the shared registry. Its
`maximum_depth_mm: 0.100` applies to both removal and addition. Change this value
for future captures, or pass a separate registry to
`src.edge_restoration_settings.capture(path)`. It is independent of trace-width
growth, the earlier ordinary corner-cut limit, and required clearance.

Capture once at job entry and retain `policy.resolved()` in the job snapshot.
The immutable policy records the exact registry SHA256. No environment variables,
global OS settings, or live mutation of a running job are involved. Invalid,
nonpositive, nonfinite and duplicate settings reject. A feature over the limit
rejects as a whole; do not repeatedly trim it in 100 um steps.

## Geometry call and responsibilities

`bulk_edge_restore.propose(material, reference, window, contacts=..., protected=...,
foreign=..., gap_mm=..., reference_evidence=..., smooth_edge=..., policy=...)`
returns `(candidate, removal, addition, proof)`. A failed proof must never be
applied. All geometry is in millimetres. The caller must supply complete related
contacts/protected features and all relevant foreign copper; empty sequences do
not prove a board has no constraints.

Reference construction supports two collinear, source-backed straight flanks, or
an unchanged qualified bulk-region boundary already underneath a protrusion.
Ambiguous flanks reject. There is no general detector for every curved edge or
every dispensable recess. Bind the full feature window and reference to the
original source; do not use a cropped window to conceal a larger feature.

Compute removal and addition once. Require the entire two deltas to lie in the
captured-depth band around the supported edge. The window perimeter is never a
depth reference. The round polygonal buffer conservatively screens curved ends;
no sampled distance alone grants a pass. Retain component/hole counts and source
contact existence, preserve positive-area attachments, reject edits through
protected geometry, and check additions against complete foreign geometries.

The caller must then assemble a separate working source with an explicit change
ledger; verify source-to-component correspondence, all untouched source objects,
pin domains and the normal stage checker. Do not silently redefine historical
source geometry. The user-authorized original circular-land cap exception in
case 2 does not establish general permission to shave unrelated lands or pins.
Recess fixtures are synthetic; no real-board recess has been qualified here.

## Retained case 2 result

Evidence: `out/lacie_work/evidence/bulk_edge_restore_20261116/actual_100um/`.
Source circle suffix `bytes:95749:95769`, route `JR-a87acaa59b257031`, factor 1.35.
The 49.69007569 um cap was removed completely (0.007818184104 mm²); no copper was
added. Its center and single positive-area source contact remain. All 1,917 other
source occurrences remain unchanged, 126 connected components retain their
source-membership and hole counts, and all 13 declared pin checks pass.

The same candidate changes from FAIL at 37.94209616 um minimum gap to PASS at
41.19000000 um against a 40.100 um requirement. Both physical and functional
owner checks, source-void/topology and pin checks pass. This is intentional
geometry change; equality of before/after copper or proof hashes is not claimed.
The candidate itself is identical. The timed probe body is 13.723 s including
both reference/restored preparations and input readback, excluding process import
and visual rendering. Restoration predicate time is 0.00268 s, working partition
1.730 s. This is a correctness experiment, not a paired speedup benchmark.

Focused tests: 47 passed, covering 99/100/101 um in both directions, adjustable
capture, invalid settings, foreign-copper bridge, protected recess, lost contact,
ambiguous reference and topology rejection. Exact paths render at 3x without
simplification in `BEFORE_AFTER_3x.png`; the before panel is the failing control.

## Case 1 routing boundary

`JR-341d4afec3bc2fe9` is a 50 um open route with eight source members, with terminal
coordinates (12.7050, -21.6498) and (13.2277, -11.2964) mm. Moving it away from its
neighbor is a distinct candidate family. `IncrementalRoutes.evaluate` currently
requires the grown candidate to cover the original trace core. A relocation that
removes original route copper therefore rejects as `ORIGINAL_TRACE_CORE_REMOVED`.
Do not disable that predicate to claim a reroute pass. An endpoint-preserving
relocation needs explicit new construction and relationship/clearance proofs;
none has yet been executed or qualified in this experiment.

The 512 MiB T05 cache and existing stage policies are unchanged. No full-board
run, export, stage acceptance or manufacturing claim.

## T04 entry integration — 2026-11-16

The user placed edge smoothing at the beginning of T04. The bounded Gerber entry
now supports:

```python
result = pipeline.run_t04(
    store, retained_t03_scene,
    route_ids=[route_id],
    edge_restore_ids=[cap_source_id],
    # Optional captured alternative to the shared 100 um provisional registry:
    edge_policy=captured_policy,
)
```

`edge_restore_ids` identifies complete circular occurrences on qualified large
Regions; it does not accept cropped removal windows. Omitting it preserves the
existing path. Explicit bounded route ids are currently required. This is not
automatic whole-board feature discovery, and real recess detection remains
unqualified. The shared geometric proposal routine still tests synthetic recess
filling and rejects bridges, pin-slot fills and over-depth features.

`gerber_u05.t04_edge_entry.prepared` executes once before `width_admission`, route
coverage decisions, `IncrementalRoutes`, obstacle indexes and the ladder. It
captures the depth policy, binds original occurrence references and source roles,
qualifies the >5%-outline bulk Regions, checks each complete cap, verifies source
component membership and holes, and runs the pin checks. It serializes a
`t04-edge-entry-bounded/1` receipt containing exact additions/removals and the input
scene reference. Only `geometry_ref` changes in the scene; original references
remain immutable provenance. A separate working context supplies the authorized
baseline to T04, and original globals are restored on success or exception.

The integrated family requires unchanged source circular lands, integral physical
and functional partitions, and no retained native floor, checking envelope or
partial-pocket reservation. Unsupported contexts reject explicitly; their safety
operands are never discarded. Each requested feature must pass before the new
context becomes active. Repeated smoothing of the output rejects.

The native exporter currently retains original atoms and appends positive copper;
it cannot represent this original-cap removal. Fresh-worker reconstruction and
T02/T05 prior floors also need subtraction-aware custody. Therefore marked output
scenes reject at initialization, T02, T05 and connected export entry with
`T04_EDGE_ENTRY_DOWNSTREAM_REPLAY_NOT_QUALIFIED`. This is a concrete remaining
integration boundary, not a failed geometry check or a request for authorization.
Do not enable the full pipeline by removing these guards. Next work is persistent
working-source reconstruction, original-versus-working reference custody, native
subtraction serialization/reparse, and downstream retention checks, followed by
bounded qualification. No full-board run is needed to develop those pieces.

Paired evidence: `out/lacie_work/evidence/t04_edge_entry_20261116/`.
One route's complete ladder selected 1.25× from the original T03 entry and 1.35×
from the smoothed entry. Both final nominal and envelope checks passed. The
restored cap has exactly the same WKB hash as the earlier case 2 result. The
100 um setting, 126-component relationships, source attachments and 13 pin slots
remain enforced. This is intentional geometry change, not identical paired
before/after proof hashes. The final smoothed T04 call took 10.906 s including
preparation versus 8.730 s for the reference; the smoothed arm evaluates more
growth candidates. No speedup is claimed. Focused suite: 117 passed.

The initial smoothed harness completed geometry checks but its generic readback
searched only the overlay store. Its failure log is retained. A separate
hash-validating readback verified all 1,974 references through both roots, and a
fresh final bounded run using the corrected harness and added source-reference
guards passed. `smoothed_final/REPORT.json` is the final geometry result;
`ENTRY_FINAL_3x.png` renders exact nominal output paths without simplification.
