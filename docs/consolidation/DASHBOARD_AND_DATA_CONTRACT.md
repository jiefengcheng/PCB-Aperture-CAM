# Proposed dashboard and data contract — consolidate, do not broaden operation scope

This is a design proposal for implementation inside the existing PCB project. It is not a description of capabilities already shipped.

## 1. One product surface, three views

### A. Processing dashboard — what happened to this input?

Organize the upstream pipeline around the original four objectives: recognition/grouping, structured storage, preservation, and selective export.

```text
Project / source revision / layer set / run / backend / query scope

Sources → Inventory → Spatial candidates → Exact relationships → Groups
                                                           ↓
Artifacts ← Export/inspect ← Operation context ← Query ← Stored revision

Selected-stage table          Shared board viewport        Evidence inspector
counts / omissions / timings   hits, groups, roles           hashes / predicates
```

The pipeline is a recorded dependency graph, not an assumed universal execution order. Display only events actually retained for a historical run; use NOT_RECORDED for absent stage evidence. Do not retrospectively invent timings, search candidate counts or database activity for V2.

Each stage exposes:
- input/output artifact identities, parent stages, source revision and algorithm/config digest;
- execution state, result coverage, warnings/omissions, and evidence locator;
- counts with named denominators (source objects, indexed layer instances, components, persisted records, exported records);
- measured time, memory, cache/index build identity, and completed/incomplete result flags when recorded;
- a link into the same viewport and evidence inspector used by the case workbench.

Representative stage views:

| Stage | Inspectable geometry/data | Necessary distinction |
|---|---|---|
| Source/inventory | tracks, pads, vias, filled regions, mask openings, unsupported records | source objects versus per-layer instances; retained bytes versus indexed semantics |
| Candidate search | query region, clearance halo, bounding boxes, candidate hits | broad-phase candidates versus actual matches |
| Exact relationships | witnesses for touches/overlaps/within-distance | physical contact versus proximity versus intended net |
| Grouping | selected component members, isolated objects, membership digest | computed component versus KiCad PCB_GROUP label |
| Persistence | revision-bound records, payload hashes, relation occurrences | catalog/index references versus original bytes |
| Selection | region/type/property queries with selected rows highlighted | selected-for-inspection versus authorized-to-write |
| Context export | target/dependents/protected/read-only references, retained dependencies | diagnostic extraction versus deliverable manufacturing job |
| Validation/replay | existing findings and recorded V2 result | historical outcome versus selected replay event |

Dashboard counters must reconcile exclusions. A nested source object can yield multiple layer instances; do not demand an incorrect one-to-one equality. Require every omission or expansion to have a typed reason and source locator.

### B. Case inspector — why was this result accepted or rejected?

Retain existing synchronized before/after, overlay/difference, finding evidence, HALPI2 controls, GlowStitch unknown intent and V2 execution replay. Fix replay event state first. Add a stable link from any dashboard record to case/run/revision/object/finding.

Use plain observation labels before raw JSON. Keep Requirement, Observed result, Evidence, and Limitation separate. Put original aggregate, profile result and current candidate decision in distinct scope-labeled regions; do not flood every local object view with unrelated global badges.

### C. Storage/index view — how was this query answered?

Present query inputs and results before showing physical implementation:
- exact identity lookup or ordered range (B-tree candidate role);
- conservative spatial range/halo search (R-tree candidate role);
- typed relation traversal (gfs candidate role);
- source bytes and proof-reference retrieval (artifact/catalog role).

Show backend/version, snapshot identity, candidate count, exact-match count, returned-record count, completion status, elapsed time and result digest. Allow baseline-versus-native comparison on the same query and revision. A diagnostic tree-box overlay can be useful, but a B-tree animation or global graph hairball is not the primary dashboard.

An empty complete result is different from missing index, wrong revision, error, cancelled query or budget truncation.

## 2. Layered data model

```text
Immutable source artifacts + supplied intent + operation policy
                           ↓
       Revision-bound object / geometry / relation catalog
                           ↓
       Rebuildable materializations and indexes
       [ordered lookup] [spatial candidates] [typed graph]
                           ↓
          Context queries → dashboard → existing V2
                           ↓
          Original independent exported-result validator
```

Do not replace authoritative source artifacts or validation receipts with a mutable index. Prefer an immutable catalog snapshot plus materialization manifests. All three indexes must address the same declared source/geometry/policy revision; reject mixed-generation results.

Proposed logical entities (adapt names to existing repository types; do not create duplicate managers):

- **SourceArtifact:** content hash, source path/origin, format, license/access class, source timestamp if available, immutable bytes locator.
- **BoardRevision:** board identity, source-artifact set, coordinate/layer definitions, parent revision and explicit lineage map.
- **ObjectVersion:** revision-bound key, source identifier or composite locator, type, layers/parent, exact source locator, geometry reference, raw or parsed net assignment with evidence class.
- **GeometryRef:** source/composition revision, authoritative numeric representation and units, bounds, approximation/error metadata, optional display-only derivative.
- **RelationOccurrence:** stable fact key, relation type and direction, endpoints, scope, derivation/source, algorithm/predicate version, witness and evidence. Preserve multiple supporting occurrences outside any adjacency index that deduplicates them.
- **ComponentSnapshot:** revision/layer/predicate/membership digest, member object-version keys, display label, complete/incomplete flag.
- **ModificationCase:** source revision, rule/policy reference, direct target, writable dependents, protected objects, read-only context, fixed references, permitted region and required evidence.
- **ProcessingEvent / QueryReceipt:** run/event identities, dependencies, start/finish when recorded, input/output hashes, backend/query parameters, counts, coverage, errors, result digest.
- **ValidationRun / Decision:** existing qualified check results and scope; do not reimplement their meaning in storage or frontend.

Identity distinction:
- `ObjectVersionRef` identifies an exact object occurrence in a source revision.
- A `LineageRef` can connect versions only through an explicit mapping. Coordinate changes are expected during edits; coordinates alone cannot be a revision-independent object ID.
- Native UUIDs may be reused across boards/revisions, legacy IDs can repeat, and numeric gfs VIDs are materialization-local. Bind all translations explicitly.

## 3. Query adapter contract

Conceptual signatures only; not claims about existing gfs APIs:

```text
lookup_objects(snapshot, object_keys)
range_objects(snapshot, field, interval, filters)
spatial_candidates(snapshot, layer, query_box, expansion)
exact_relations(snapshot, candidate_pairs, predicate_id)
neighbors(snapshot, seeds, relation_types, direction, budget)
load_case(snapshot, case_key)
```

Every response carries snapshot/source identity, query digest, record refs, completeness, error/unknown state, and receipt. Stable ordering is a presentation/reproducibility choice, not an assumption that a native traversal already returns a canonical set. Keep incidence, unique neighbors and proof occurrences distinct.

Native boundaries require explicit units, signed ranges, outward-rounded envelopes, finite-value checks, untruncated identities, buffer ownership, lifetime and error semantics. Use batch transfers where measurements justify them. Select an existing stable binding before adding a new C ABI or Python extension; do not change shared ABI contracts as a side effect of PCB work.

For proximity searches: expand the search envelope conservatively, admit all possible pairs, then calculate the exact predicate from qualified geometry. Search tolerance is not a copper-clearance acceptance threshold. Never join physical components because a nonzero-distance neighbor was found.

## 4. Publication and cache safety

Build new catalog/index materializations in a new staging location. Verify full manifest consistency, source custody and parity, then expose a revision reference. On failure, retain diagnostics and keep the old snapshot selected. Rebuilding a cache must not rewrite source history.

Directory publication alone does not prove power-loss durability; preserve the current V2 limitation. Any stronger crash-recovery claim needs a specified contract and crash/reopen tests. A catalog transaction must not imply atomicity across unrelated graph/spatial files unless that has been demonstrated.

Cache keys include source revision, layer scope, units, geometry/predicate version and relevant policy. Legacy group label or filename is insufficient. Deleting copper can split a component; insert-only Union-Find state cannot certify the changed revision. Recompute or use a separately qualified update algorithm.

## 5. Useful measured workloads

Prioritize the actual questions used by the viewer/executor:
1. Find one selected pad and its fixed aperture/source evidence.
2. Find its connected physical component, then intersect with the case's write allowlist.
3. Find nearby protected copper using an explicit halo and exact filtering.
4. Filter components by explicit bbox area/aspect definition and inspect their members.
5. Reopen a stored revision and recover identical context/evidence references.
6. Retrieve HALPI2 J22.1 and its recorded 15 failing relationships without broadening to whole-board electrical approval.
7. Retrieve all GlowStitch source terminals without manufacturing a net map from geometry.

Use the synthetic coupon, already pinned public designs and pcb_Z/test.kicad_pcb as declared fixtures. Larger replicated layouts may test scaling but must be labeled synthetic workloads, not customer validation.

Record extraction/build/serialization time separately from steady-state lookup, warm versus cold cache, memory/storage size, repeated-run distributions, and boundary-call count. Do not promise C++ speedups before measuring the baseline; current Rtree and GEOS paths already involve native libraries.

## 6. Demonstration of successful consolidation

Select a recorded source revision → inspect object inventory and any omissions → click spatial search and see candidates versus exact hits → click a component and see its members → load a persisted operation case → see writable/protected distinctions → replay the same qualified V2 execution → inspect unchanged validation evidence.

Switch between baseline and qualified native query backend for that recorded snapshot and observe identical object/relation/result digests. Reload the stored run and repeat. No new PCB modification family or AI planner is necessary.
