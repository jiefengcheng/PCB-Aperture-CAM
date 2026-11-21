# Viewer route selection and read-only explanations

This is the agent entry for the maintained-route viewer extension. It changes
selection and presentation, not T04 geometry, processing or acceptance.

## Identities and display

A native route (`JR`) contains source occurrences. A parallel group (`PGS` or
arc-group ID) relates parallel members and is a separate identity. A residual
chain (`RC`) is an engineering treatment inside a route; it is not a viewer
selection unit or an electrical net.

Route mode fills the union of the displayed revision's saved member copper and
overlays original native centerlines as dotted open polylines. The segment picker
and Segment mode retain source inspection and source-growth comparisons. Group
references remain labels and inspector records. Area/growth figures concern the
clicked segment unless explicitly stated otherwise. No copper is repaired,
snapped, trimmed or regenerated for the display.

## ABI map

| Boundary | Purpose and binding |
|---|---|
| Snapshot/manifest v1 | Existing immutable polygon artwork and current/previous lineage; unchanged by route selection |
| Selection outbox v1 | Exact clicked source `object`, job and revision; adds `selectionMode` and validated route context |
| Explanation envelope v1 | Checksummed, selection-bound text; optional source comparison, route presentation and picking index |
| Compact route catalogue | Viewer-only projection of existing admission and recorded roles, pinned to source and accepted-T03 scene |
| Derived route/index caches | Per-revision presentation and picking metadata; never engineering input or approval |

See the [capability descriptor](../../contracts/viewer/route_selection_v1.json),
[snapshot schema](../../contracts/viewer/snapshot_v1.schema.json) and
[manifest schema](../../contracts/viewer/manifest_v1.schema.json). The descriptor
documents the Python/Swift boundary; it is not a JSON Schema validator or a new
engineering execution contract. `ViewerCore` validates the actual payloads.

The optional explanation fields are:

- `comparison`: original/added/removed area artwork for the clicked source,
  bound to its displayed-path SHA256 and original/current WKB digests.
- `route`: filled assembled artwork, original centerline points and group
  references for every member. Each member retains its object/source ID,
  displayed-path digest and original/current WKB digests.
- `routeIndex`: compact route-to-object-index membership for picking. Its digest
  binds the complete ordered object table; duplicate or foreign membership fails.
- `routeUnavailable`: explicit reason for retaining source-level display.

Job, revision, selected object and complete membership must agree across fields.
Source and route metadata must not be rebound to a newer snapshot by filename.
Old payloads without these optional fields retain source-based behavior.

## Data flow and reusable components

`trace_selection` resolves the exact displayed lineage, shares construction
decoding within a request, and keeps clicked-source comparisons separate from
route presentation. `route_presentation` reads the maintained membership and
recorded roles, assembles saved copper in native member order and caches the
derived display. It performs no route grouping, classifier run or T04 operation.

`RoutePresentation`/`RouteCatalogueIndex` validate finite data, source/path hashes,
membership, bounds and resource limits in the native reader. The canvas prefers
catalogued trace members over covering context on the active layer, preserves
overlap cycling, and discards late responses after selection/revision changes.
The outbox still carries the clicked source for segment-level explanations.

## Agent operations

Run `tools/Prepare_LaCie_Workspace.command` before writes. All sessions, derived
caches, build/test scratch and reports stay under `out/lacie_work`.

1. Read the active connection and `session/outbox/selection.json`; validate its
   job/revision/source against the committed snapshot and bound evidence.
2. When needed, register an **existing** source-role preparation with
   `tools/viewer_trace.py --workspace <session> --catalogue-preparation <directory>`.
   This checks recorded hashes and creates compact viewer metadata. It does not
   execute T04 or load the full-board construction just to obtain membership.
3. For a frozen selection, use `tools/viewer_trace.py --workspace <session>
   --request <request.json> --response <response.json>` for the automatic retained
   comparison. Both files must be inside that viewer session.
4. For a chat explanation, use `tools/viewer_explain.py --workspace <session>
   --selection <frozen-selection.json> --text-file <answer.txt> --author <name>
   --evidence <bound-report>`; `--comparison` optionally attaches a source overlay.
   This text channel does not publish a geometry revision.
5. Run `tools/Test_Gerber_Viewer.command` for scoped Python/Swift checks. It owns
   its LaCie test namespace. Native WebKit controls and client-route screenshots
   use the existing `--smoke-report` launch support; keep synthetic controls
   explicitly separate from client evidence.

Missing catalogue/centerlines, missing displayed members, unsupported derivatives
or oversized complete payloads must remain explicit. Do not truncate a route,
guess a net, weaken a geometry guard or rerun T04 to make selection succeed.

## Qualified reference and remaining scope

`out/lacie_work/viewer/route_selection_20261121` binds 34 Python tests, 14 Swift
tests, 21 route-canvas checks and 26 generic controls. The maintained index covers
1,524 trace routes and 4,524 source members. Membership/order matched all 62 native
routes in the displayed 64-entry slice. Two real routes with seven/eight members
were exercised, including a normal worker round trip without an injected second
route response. Pinned source, construction, report and snapshot hashes remained
unchanged. Earlier overlap-priority failures are retained separately.

This is viewer qualification, not validation of every route's geometry, current
full-board T04 completion, export, electrical intent or manufacturing readiness.
The snapshot can intentionally show an older engineering slice. Complete
operator detail is in [the live viewer guide](../GERBER_VIEWER_LIVE_T04.md).
