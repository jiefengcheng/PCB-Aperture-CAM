# Big-copper cleanup: continuation ABI and engineering handoff

Current independent execution checkpoint, 2026-11-23: profile
`large-copper-source-supported-boundaries/3` runs all agreed families under one
fixed source-bound policy. Its source-independent circular/straight discovery
and retained safeguards are described in
[LARGE_COPPER_EXECUTION.md](LARGE_COPPER_EXECUTION.md). Evidence:
`out/lacie_work/large_copper_parity_fix_20261123_02/`.
Fresh final source run: 356 corrected / 77 unresolved / 24 ignored, 895 changed
contributions, zero additions, topology 275 components / 114 holes retained.
All 46 exact reviewed removal witnesses are covered; the three reviewed KEEP
windows and ignored rectangle remain unchanged. The generic result includes
additional removals, so whole-result byte equality to the old bounded checkpoint
is false. The local packaged viewer and fresh second-Mac viewer match all 17,849 final
contribution bytes, with authenticated native display ACKs. Package 0.2.0 replaces the partial
0.1.1 profile; portable qualification is recorded separately.

The earlier `large_copper_marked_parity_20261123_01/` 38/46 result and DMG 0.1.1
remain historical failed milestones, not current parity evidence. The read-only
inspector ABI below and the trusted 50-place live checkpoint remain separate and
unchanged. No saved witness masks, board ordinals or windows feed execution.
Individual approved plotting-fragment/free-end retreats are explicit evidence;
see the precise AREA_NOISE exception and strict shallow-edge path rule in the
execution document. Unsupported/ambiguous families and `treatment_complete=false`
remain explicit; no whole-board electrical/manufacturing or export acceptance.

Checkpoint: 2026-11-22, Singapore. This is the entry document for another agent.
Restored-workspace rerun: 2026-11-23. The live head is now
`3d8b5e1a9d794f5284d3c305e5a748a3`, with construction SHA-256
`63bea069a4b7ebbe1d3f6b63601ebdfd5ae87b062d5bea75b46abedc9b385727`.
Evidence: `out/lacie_work/t04_restored_trim_rerun_20261123/REPORT.md`,
`PARITY.json`, `03_circular/RESULT.json`, and `native_final/cleanup-ui.json`.
This replayed approved cuts and freshly reran held endpoint, eight-place review,
and circular endpoint checks; it did not add generic discovery. All 17,849 final
source contributions match the historical checkpoint byte-for-byte. The 46
corrected, 3 unresolved and 1 ignored places are preserved; 97 native UI checks
passed and the new display ACK was authenticated. The descriptor below retains
the historical checkpoint, so `checkpoint_match=false` is expected for this head.
The LaCie and native viewer storage identity now use reformatted volume UUID
`6D461CE3-1544-4670-BA1D-BE4DA490D97E`.

Read the repository AGENTS.md and this document before editing. Work only in this
checkout; preserve unrelated dirty/untracked T02–T05 work. Do not reset, clean,
commit, upload, change global settings or modify frozen inputs as a startup step.

## Start here

From the checkout root:

```bash
tools/Prepare_LaCie_Workspace.command
.venv/bin/python -B tools/bulk_copper_cleanup_agent.py --describe
.venv/bin/python -B tools/bulk_copper_cleanup_agent.py --status
.venv/bin/python -B tools/bulk_copper_cleanup_agent.py --check-saved
.venv/bin/python -B tools/bulk_copper_cleanup_agent.py --list unresolved
.venv/bin/python -B tools/bulk_copper_cleanup_agent.py --list ignored
.venv/bin/python -B tools/bulk_copper_cleanup_agent.py --list reviewed
.venv/bin/python -B tools/bulk_copper_cleanup_agent.py --list circular
```

The executable ABI is **read-only**: no native geometry parsing, geometry
construction, treatment, publication, acceptance update or full-board execution.
`check_saved` authenticates stored bytes and fingerprints; it does not rerun or
replace geometry verification. Its compact phase summary is a saved claim; full
local witnesses remain in the returned authenticated construction. A missing/corrupted/stale dependency fails; do not
substitute an old construction. `checkpoint_match=false` means the live head has
advanced: reconcile its authenticated report before using it as a new parent.

The contract is
[bulk_copper_cleanup_v1.json](../../contracts/agent_abi/bulk_copper_cleanup_v1.json).
The implementation is [bulk_copper_cleanup.py](../../src/agent_abi/bulk_copper_cleanup.py).
It uses the current committed viewer state, not a remembered filename or PID.

JSON transport accepts exactly these five keys; selectors irrelevant to an
operation must be null. Unknown operations, overrides and extra fields reject:

```json
{"abi_version":"1","operation":"list_places","filter":"unresolved","place_id":null,"revision":null}
```

Success returns `status=OK`, `result`, and explicit false flags for writes,
geometry execution, acceptance change and full-board execution. Failure returns
`status=FAIL`, `error`, and a nonzero CLI exit. Do not treat a missing display ACK
as lost geometry: `display_current=false` requires checking the viewer connection.
An authenticated saved result and a current native display are separate facts.

```bash
printf '%s\n' '{"abi_version":"1","operation":"status","filter":null,"place_id":null,"revision":null}' | .venv/bin/python -B tools/bulk_copper_cleanup_agent.py --input -
```

Inspect a case ID returned by `--list`, using the revision returned in that same
response:

```bash
.venv/bin/python -B tools/bulk_copper_cleanup_agent.py --inspect 'cleanup:CASE_NUMBER' --revision 'CURRENT_REVISION'
```

Case IDs are revision-local, and array positions can change when a correction is
added. Never reuse a case ID with another revision. `reviewNumber` preserves the
original eight-place review order. UI place counters are filtered list positions.

## Authoritative checkpoint and custody

| Item | Bound value |
|---|---|
| Original Gerber SHA-256 | `207a51318f103190a4d61e76f4a0457fcfd11fd3db560c9439dd2f5f460f9b90` |
| Original scene SHA-256 | `0b3cb8da3614f8b19c38dd59eb4e88e0be0ed42ae7a1e66a7c059d93e5da962a` |
| Connection ID | `fc924313bca84b4eb040573f45bcf7af` |
| Native revision | `515c0cc7d92a41738da934049e4c5cbb` |
| Construction gzip SHA-256 | `dad108b81ae8ee2d98db625380b84a51d07ce6b008c97840e52bf67f4a5f2303` |
| Snapshot SHA-256 | `3dfcd14eaf8c62dacb8c402e83fd60d48861790e21f3ddf7b26c8a4b928cbc42` |
| Source occurrences | 17,849 |
| Saved places | 46 corrected, 3 unresolved, 1 ignored; 50 total |
| Original/remaining physical topology | 275 components, 114 holes |
| Added / total removed material | 0 / 0.07359225454818061 mm² |

All following paths are relative to this checkout, unless absolute paths are
returned by the ABI:

- Live connection: `out/lacie_work/t04_large_fill_audit_20261122/source_viewer/`.
- Session: that connection's `session/` directory.
- Latest construction: `out/lacie_work/shared_copper_qualification_20261122/circular_endpoint_trim_50/construction.json.gz`.
- Latest report: the same directory's `RESULT.json`.
- Complete visual/evidence delivery: `out/lacie_work/shared_copper_qualification_20261122/FINAL_54/REPORT.md` and `RESULT.json`.
- Native controls and screenshots: `out/lacie_work/shared_copper_qualification_20261122/circular_endpoint_viewer_53/`.
- Original source file: `dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top_layer.gdo.gbr` (immutable).
- Shared preparation: `out/lacie_work/shared_copper_context/2634adc51b5c62864ed7e4cd044d4633923803d48939559f311f4182b1239dd2/`.

**The connection.json construction field points to the connection's initial
construction. It is not the current result.** Resolve `session/current.json` →
hash-bound snapshot and producer state → committed event → report/construction.
The ABI performs that traversal and binds the presentation to the same revision.
The connection's scene_ref is the original-source catalogue and is the correct
original reference. Do not substitute accepted T03, T01, or old full-board T04.
The ABI does not load or revalidate native shared-context preparation; its owning
`CopperContext` must authenticate format/kernel/dependencies when engineering
opens it. Byte authentication of a saved treatment never grants new eligibility.

## User decisions that remain requirements

1. Work directly over the original source. This phase is **trimming only**.
   Recess filling, smoothing by addition, trace widening, rerouting and exports
   are excluded. Old saved recess additions and T04 growth were removed from
   the active construction, not hidden by colouring.
2. The complete physical protrusion must be **strictly below 10%** of the
   **original causing pad or trace area**. Use the full unioned bump numerator;
   do not count overlapped native draws twice, use a large copper-owner area as
   denominator, split a bump into smaller accepted pieces or repeatedly shave it.
3. The shallow trace-edge rule is separate: genuine source-supported straight
   flanks, depth below half the original trace width, retained original path and
   contacts. It is not permission to bypass the pad-area rule.
4. Provisional depth limit: 0.100 mm. Existing circular fit maximum error:
   0.004 mm. Preserve coordinate/area tolerances and fallback semantics.
5. **Rectangular bumps are ignored for now.** Rectangle 17569 and all four of its
   overlapping source contributions were restored to the verified trim-only
   parent. Keep an Ignored record. Do not enable allow_causing_rectangles.
6. Nominal trace-growth cutoff: 0.25 mm. A stored 0.249935 mm trace displayed as
   0.250 mm stays unchanged for growth. That control belongs in trace growth,
   not the big-copper view. Growth was not executed by this cleanup.
7. Copper is **GREY in every state**. Optional pink removal ghosts are allowed.
   No brown copper, blue selected-trace overlay or unrelated T04 growth ribbons
   in the dedicated cleanup view. Original connected copper within a treated
   object stays grey.
8. Viewer navigation/selection/playback reads saved results only. It must never
   run treatment or silently update geometry eligibility.
9. The owner said “I reviewed already and accepted”, then deferred rectangular
   bumps. The scoped receipt is
   `review_eight_no_rectangles_35/OWNER_REVIEW_AND_RECTANGLE_RESTORATION.json`
   under the shared qualification directory. It does not imply a separate owner
   acceptance of the later circular correction, full-board or manufacturing approval.

## What the eight-place review found

| Review | Source / original issue | Current disposition |
|---|---|---|
| 1 | Pad 14249 cap, approximately 11.05% | Keep: exceeds strict 10%; shallow trace rule does not apply to a pad cap. |
| 2 | Compound trace-end bump near (14.200, −9.392), primary stroke 4100, 54.41% | Keep: original stroke denominator too small; shallow depth/path checks fail. Adjacent rectangles only graze the window. |
| 3 | Compound trace-end bump near (14.785, −9.392), primary stroke 4105, 94.49% | Keep: same area and shallow-rule failures. No qualified larger native route was found in the retained complete route inventory. |
| 4 | Pad 14455, 7.4375% | Corrected; the trace-only cause search had omitted this pad. |
| 5 | Pad 14467, 7.4375% | Corrected; same omitted pad cause. |
| 6 | Pad 15598, 0.8640% | Corrected; centre and contacts retained. |
| 7 | Trace 1226, whole bump 9.2146%; tiny flash 68 blocked it | Corrected; flash is proven plotting support at two distinct matching-aperture original stroke endpoints. |
| 8 | Rectangle 17569, initially qualified at 6.8717% | **Ignored** per latest instruction; the rectangular trim is rolled back, including its overlaps. |

The three remaining entries have measured reasons; they are not unexplained
misses. Their keep dispositions were part of the reviewed result. Do not force
them below the limit or inflate their denominators to make the count zero.

Earlier fixed trace 2688 was blocked by four duplicate endpoint flashes. The
whole bump was 5.4092% of its original trace area. The cleanup-only exception
does not reclassify generic pads/lands or change another stage's authority.
Declared terminals, protected aliases, contacts and pin domains remain protected.

## Latest circular-edge correction

The further marked kink is near (45.537, −14.860). Its true reference is the
round endpoint of native line **15673**, centre (45.164, −14.859), original width
0.599947 mm. Smaller pad 15263 is offset and must not supply the circle centre.
Two original source flanks fit radius 0.3989677853085732 mm with maximum radial
error 0.0012049042722514502 mm, below the unchanged 0.004 mm fit bound.

Only surrounding-copper strokes 14440 and 14451 change. The entire physical patch
is 0.01344373369847533 mm², respectively 4.73445% and 5.00349% of their original
areas. Both original centre paths and the whole fixed reference copper owner
remain intact. No rectangle changes, addition, clearance search or growth occurs.

This was absent from the straight-flank inventory, and the earlier circular
reference family admitted native pad centres only. The implementation now admits
an authenticated **round native line endpoint** as a reference. It does not claim
complete curved-edge discovery. The qualification driver pins a local window and
two angular support sectors; do not advertise it as an automatic board scanner.

## Implementation map and Python construction boundary

| Owner | File / interface |
|---|---|
| Board source/revision custody and persistence | `src/shared_copper_context.py`: for_board, CopperContext, Revision |
| Existing T02/T05 exact ordered edge structure | `src/indexed_polygon_distance.py`: prepared_boundary, BoundaryPreparation, existing Engine |
| Batch preparation, proposal and assembled checks | `src/gerber_u05/source_edge_cleanup.py`: CleanupBatch |
| Primitive fit / subtraction | `src/bulk_edge_restore.py`: fit_straight_flanks, fit_circular_void_flanks, fit_circular_stroke_end_flanks, shallow_trace_edge_check, propose |
| Source endpoint flash proof | `src/gerber_u05/redundant_plotting_caps.py`: qualify |
| Earlier pad-only helper | `src/gerber_u05/source_pad_cleanup.py`; retain controls, do not use its old fill classification as universal cause discovery |
| Presentation of saved masks and decisions | `src/viewer_abi/board_growth.py`, `src/viewer_abi/copper_cleanup.py` |
| Queue, commit, source-bound camera | `src/viewer_abi/live.py` |
| Native decoder | `viewer/Sources/ViewerCore/BoardGrowth.swift` |
| Controls and saved-only drawing | `viewer/Sources/GerberViewer/Resources/canvas.html` |
| Native UI proof and captures | `viewer/Sources/GerberViewer/main.swift`: --cleanup-smoke |

Read [SHARED_COPPER_CONTEXT.md](SHARED_COPPER_CONTEXT.md) for architecture,
persistence, measurements and the sealed T05 job-only cache exception.

Treatment consumes **complete ordered positive source contributions after the
maintained Gerber polarity composition**, with source IDs and authenticated
original geometry refs. Do not union raw dark/clear operands unordered or infer
electrical intent from physical ownership. Use the catalogue's object order.

The continuation pattern is:

```python
with for_board(original) as copper:
    current = copper.acquire(changed_contributions_from_verified_current_stage)
    batch = CleanupBatch(
        rows, original, current, features,
        protected_source_ids=protected_ids,
        protected_domains=protected_geometry,
        allow_redundant_flashes=True,   # only with actual source proofs
        allow_causing_pads=True,        # explicit original-circle pad exception
        # allow_causing_rectangles stays False
    )
    # Propose in a loop; retain each rejection with its source identity/reason.
    # Do not materialize full-board unions or rebuild ownership in this loop.
    for index in range(len(features)):
        ...  # record batch.propose(index), or retain its ValueError disposition
    accepted_revision, batch_proof = batch.finish()
    copper.validate()
```

Each feature supplies causing_id, domain, smooth_edge, reference_evidence and
backing_point. A curved trim additionally supplies a valid removal_mask contained
in domain. It is an **explicit subtraction mask**, not a replacement polygon.
The primitive checks its exact difference reference, constructs no added copper,
then the batch checks actual assembled subtraction/topology and source scope.
Never subtract the whole rectangular inspection window for a curved mask.

The original causing trace/pad remains the denominator even if earlier revisions
already removed copper; cumulative removal is checked. Pad cuts require the full
bump to lie in the actual pad, local broad backing, retained centre and original
contacts. A large nearby pad cannot provide an unrelated denominator.

The endpoint-flash exception requires a canonical source disk and matching
original stroke endpoint/aperture support: duplicate aliases, or two distinct
matching stroke supports for a single flash. Declared/protected terminals still
block it. Never globally change qualified_land/source-family metadata.

Use current.sources(window) for neighbours and copper.boundary_sections / existing
boundary preparation for relevant ordered edge runs. Preparation is shared, but
eligibility and verification remain exact-revision/policy bound. Keep original
preparation immutable; publish a changed contribution revision after verification.
Do not use legacy_trim_supported_feature in a per-defect loop.

128 MiB indexed preparation and 192 MiB geometry-snapshot budgets remain separate.
These are retained-estimate budgets, not RSS limits. Native handles stay in their
worker, are not serialized, and reconstruct once after restart. A capacity failure
is explicit; do not silently increase budgets, evict active indexes between
features, use an internal fallback, or delete/rebuild corrupted cache entries.

## Resume engineering without losing the current result

1. Run the read-only ABI startup sequence. Reconcile any live-head drift. Preserve
   the latest construction as parent; overlay its changed contributions onto the
   original catalogue. Missing contributions mean original source, not empty.
2. Inspect saved features and actual source contributions. Discover further
   defects and prepare neighbours/reference supports in batches. Distinguish a
   true circular pad anchor, round stroke endpoint, ordinary trace connection,
   protected feature, and unsupported curved contour.
3. Do not assume discovery is finished. Survey remaining large-copper boundaries,
   holes and curved transitions. Retain unsupported/ambiguous findings explicitly.
   Known three over-limit keeps and the ignored rectangle remain valid outcomes.
   Six earlier joint findings outside qualified windows also remain outside this
   cleanup's acceptance; consult their original construction evidence rather than
   inventing identities or claiming all corner/endpoint work is solved.
4. Add the smallest relevant positive/negative controls for a new repair family:
   wrong cause/anchor, contact loss, declared/protected pin, overlapping draws,
   exact 10% boundary, excessive depth, mask scope, topology change and any addition.
5. Construct locally, then validate the batch against its actual dependencies and
   complete assembled material. Required checks include expected cut equality,
   no addition under the existing area error, retained centres/paths/contacts,
   protected scope, ownership/topology and preservation of unrelated contributions.
   Subtraction avoids positive-copper clearance searches, not these checks.
6. Persist a **new** construction/report under a unique LaCie output directory.
   Keep earlier stages and failed evidence unchanged. Preserve original input
   binding, full contribution map, reviewed/ignored metadata and no-growth flags.
7. Publish only the completed, saved result; display every accepted cut and every
   unresolved/ignored finding. Keep native display evidence distinct from geometry
   checks and owner review. Update the handoff checkpoint after authenticating it.

The following are **pinned qualification examples**, not generic continuation
operators: tools/qualify_bulk_trim.py, tools/review_bulk_unresolved.py and
tools/qualify_circular_endpoint_trim.py. They contain particular ordinals, parent
inventories and/or windows. Read them to reuse the real constructors and checks.
Do not blindly rerun them against old parents: that can drop later accepted cuts
or resurrect old source/T04/recess results. Never reuse an existing output directory.

This handoff authorizes no automatic final full-board T04 growth, T02/T05 pipeline,
export/reparse or acceptance promotion. The user's current request adds ABI and
continuation documentation; completing treatment remains separate engineering.

## Viewer publishing and restart

The maintained entry points are:

```bash
.venv/bin/python -B tools/viewer_live.py --connection out/lacie_work/t04_large_fill_audit_20261122/source_viewer status
.venv/bin/python -B tools/viewer_live.py --connection out/lacie_work/t04_large_fill_audit_20261122/source_viewer start
```

Use start only if needed; its existing process lock prevents duplicate watchers.
PIDs from another session are not authority. Do not recreate the connection or
write queue entries, receipts, current.json or native acknowledgements manually.

For an actually completed new candidate, the existing publisher is:

```bash
.venv/bin/python -B tools/viewer_live.py --connection out/lacie_work/t04_large_fill_audit_20261122/source_viewer complete --label 'ORIGINAL SOURCE · saved trim-only cleanup' --report '/ABSOLUTE/NEW/RESULT.json' --construction '/ABSOLUTE/NEW/construction.json.gz'
```

Wait for its authentic committed receipt, then prepare the saved presentation:

```bash
.venv/bin/python -B tools/viewer_board_growth.py --connection out/lacie_work/t04_large_fill_audit_20261122/source_viewer
```

This computes display derivatives, not treatment. It can take minutes on this
source. Do not start another treatment or fabricate an acknowledgement because
presentation is slow. A sidecar from another revision must never be reused. Wait
for completion before running the native cleanup UI probe.

Open the existing app against the correct session:

```bash
tools/Start_Gerber_Viewer.command --workspace "$PWD/out/lacie_work/t04_large_fill_audit_20261122/source_viewer/session"
```

For UI verification, add `--smoke-report "$PWD/out/lacie_work/UNIQUE_NATIVE_REPORT" --cleanup-smoke`.
This checks saved controls and captures screenshots; it does not run treatment.
Use the ABI --status to check the current native acknowledgement. Never claim a
native visual result from merely enqueuing or building a sidecar.

The dedicated view includes Original/Corrected/Comparison, Previous/Next/Fit
place, All changes, Fit copper objects, object/status/rule filters, Reviewed 8
places, Circular edges and Ignored. Play advances the current filtered details
every four seconds and pauses on manual navigation, pan/zoom, filters, object or
revision change, or hiding the page. It performs no geometry/selection requests.

Optional report viewer_source_focus requires a real source route_points_mm index.
A circular flash has no route point: passing a pad to this optional camera API
was rejected earlier. Omit the camera hint or use an authenticated native stroke
endpoint; never invent coordinates/points or alter a saved report in place.

## Tests, evidence and completion criteria

Use tools/Run_PCB_Tests.command for Python tests and keep all logs/temp/cache on
LaCie. The focused regression set is:

```bash
tools/Run_PCB_Tests.command tests/test_circular_stroke_endpoint.py tests/gerber_u05/test_redundant_plotting_caps.py tests/gerber_u05/test_source_edge_cleanup.py tests/gerber_u05/test_source_pad_cleanup.py tests/test_bulk_edge_restore.py tests/test_shared_copper_context.py tests/test_viewer_cleanup.py tests/test_viewer_board_growth.py tests/test_bulk_copper_cleanup_agent.py
tools/Test_Gerber_Viewer.command
```

At the treatment checkpoint, 74 geometry/context/viewer-data tests, 37 viewer ABI
tests, 16 Swift tests and 97 native UI checks passed. Native distance/owner parity,
restart reuse, corruption, interrupted publication and budget controls are under
the shared qualification root. Saved tests are evidence, not permission to skip
new checks after algorithm/policy/dependency changes.

The added inspector has **12 passing tests** for byte custody, no writes,
corruption, wrong source/lineage/policy, path escape, head drift, stale selection
and unsupported execution. All five CLI operations were exercised against the
current saved client checkpoint, including every list filter and negative
requests. See
[ABI verification](../../out/lacie_work/shared_copper_qualification_20261122/agent_handoff_58/REPORT.md)
and its machine record. That later verification ran no treatment or native
geometry checks and did not restart the viewer.

Retained treatment failures include circular_endpoint_trim_46 (curved target
overlay/no-add gate) and circular_endpoint_trim_48 (whole-window neighbour
bookkeeping). Final code uses exact mask subtraction and intersects the real mask
before changing source contributions. Earlier preparation/cap failures also
remain; do not overwrite them, resume failed managed jobs, relax thresholds or
promote their dispositions.

Cleanup is ready to consolidate when the relevant large-copper inventory is
explicitly covered; every candidate is corrected, justified KEEP, ignored by
policy or unresolved with source evidence; assembled checks and regressions pass;
all saved places are navigable in grey without treatment execution; and current
artifacts/owner decisions remain authenticated. Discovery completeness is still
open. No present evidence establishes whole-board growth/export, electrical intent
or manufacturing acceptance. Independent review remains NOT_RUN / CHANNEL_UNAVAILABLE.
