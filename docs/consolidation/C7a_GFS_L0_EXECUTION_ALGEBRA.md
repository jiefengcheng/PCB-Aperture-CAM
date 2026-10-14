# C7a-B — Minimum invariant execution algebra and ABI projection

## 0. Executive conclusion

**`gfs_l0` contains a useful but qualified deterministic middle, not a ready-made universal semantic model.** The smallest justified baseline is four semantic obligations: scoped referential identity; distinguishable directed facts with interpretable values where required; an explicit observation domain and visibility boundary; and deterministic selection/composition with declared result semantics. These are obligations supported by particular native mechanisms—not four proposed product API methods, nor four universally satisfied guarantees.

The strongest existing realization is graph-local identity plus directed, tag-classified adjacency and reusable native read kernels. Canonical identity attachment adds external-to-internal translation. `StorageViewReadDomain` separates logical direction and readable partition coverage from physical access. Higher queries compose those reads. **Neither the complete `StorageView` API nor GraphBatch nor domain landing ports passes the baseline admission test as an indivisible semantic concept.**

GraphBatch adds iterative state computation with a BSP publication boundary. Landing ports adapt, inspect, export, reconstruct, and report domain assets. ABI capabilities, cursors, descriptors, jobs, and operation guidance help wrappers use these facilities; their breadth does not establish a larger baseline.

The principal constraints discovered here are:

- Internal `vid_t` values are not canonical external identities. Reordering identical input edges changed the same canonical identity's VID from 0 to 2.
- `edge_tag_t` is an 8-bit, database-local storage/filter classification that can be assigned from schema relations. It is not independently a globally meaningful relation identity, and adjacency does not preserve arbitrary parallel fact identity.
- Read-domain tag declarations are not enforced as scope restrictions by the inspected native read path. The C ABI rebuilds full physical coverage rather than executing against the saved view/delivery plan. Reported scope therefore need not equal executed scope.
- An ordinary read domain is not a pinned committed snapshot. Native callback stopping is partition-local, neighbor output can contain duplicates, and ABI cursor creation eagerly collects results.
- Two distinct 301-byte canonical values were returned as identical 255-byte ABI values with success status. Consequently identity projection is not generally lossless.
- Fresh testing found a stale read-domain fixture and an intermittent BSP resume edge-state mismatch. A first passing resume run was insufficient: a dedicated 20-run sequence reproduced the mismatch once. General deterministic resume is **not qualified** by this investigation.

This is architecture discovery, not production qualification. It supplies candidate capabilities and explicit counterexamples to C7a-C; it does not perform the A/B intersection, define C7b, implement C7c, or change the C1–C6 acceptance boundary.

### Evidence and worktree boundary

Inspected on 2026-08-31 at `020e18d092504766712149422919c9ef68ecd6e2`, branch `codex/gine-dst-durableout-integrated-20260529`. The pre-existing MLX/GraphGPS edits and untracked files were preserved. The core native files cited below matched that commit. Only this report is a task-created repository artifact; diagnostic code and builds are temporary.

The existing default-ignore Git whitelist does not include `docs/research/`, so this new report is currently ignored/untracked. No ignore rules, staging, commits, or remotes were changed; the report is present at the requested filesystem path.

Navigation began with `CODEBASE_REVIEW_GUIDE.md`, `identity_track.md`, `binding_surface_track.md`, `graph_batch_summary.md`, and `domain_landing_port_track.md`. The review guide is a map, not an override of current code. In particular, its directional DB0 examples and GraphBatch entrypoint inventory include older vocabulary or currently disabled entrypoints. The current raw A/B interface, shared query kernels, and BSP-only guards govern the corresponding claims. Historical track entries are dated decisions, not evidence that later implementations remain absent.

The existing Graphify index under `tests/` was consulted only for navigation. It mostly identified training-test content and contributed no semantic authority. No comparison-system ontology was imported. Native source, named test assertions, fresh outcomes, and architectural judgments are distinguished throughout. Source-derived counterexamples not executed are explicitly labelled.

## PART I — Minimum invariant execution substrate

## 1. Identity algebra

### 1.1 What each identifier identifies

`vid_t` is `uint32_t`, with the all-ones value reserved as `INVALID_VID`. It is the native endpoint and state-address handle. An unattached numeric graph can already be opened and traversed: canonical identity is not a prerequisite for adjacency. A VID may persist in one materialized database but has no source-independent meaning across rematerialization. Partition indices, shard IDs, and `logical_pid` identify storage/execution placements, not semantic entities. [`types.h`, aliases](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/types.h:11); [`interface0.h`, DB0](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/interface0.h:49); probe P08, §18.

`IdentityKey` is the pair `(id_space, value)`. The attached resolver owns a DB-wide bidirectional mapping between that pair and VID. The textual space name is part of canonical identity; its numeric `id_space_id` is an internal catalog code, not an external identity. Current state describes UTF-8, case-sensitive values and registration-order dense VIDs. Direct lookup uses exact string bytes; this is not Unicode normalization or a demonstrated UTF-8 validator. [`identity.h`, IdentityKey/IdentityState/IdentityResolver](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/identity.h:25); [`identity.cc`, MakeForwardKey and resolver](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/identity.cc:314).

`AttachCanonicalIdentityRecords` is a one-time attachment to materialized storage. It rejects an already-attached database, empty pairs, duplicate VIDs, duplicate canonical keys, and incomplete interval coverage. It writes a space catalog and partition slots/blobs, then identity metadata. This is not a dynamic alias registry, arbitrary many-to-many identity equivalence, or a transaction over every file. Per-value storage length is bounded by a 16-bit length; blob offsets are 32-bit. [`identity.cc`, attachment](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/identity.cc:1116); [`test_identity.cc`, numeric/mixed-space/reopen cases](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_identity.cc:107); `identity_track.md`, D001 and V0 implementation notes.

### 1.2 Stability and boundary crossing

Numeric ingestion assigns dense VIDs by first encounter, scanning source then destination. The textual canonical value is derived from the parsed number. Desc ingestion trims endpoint text and uses the configured spaces. These are adapter normalization policies: canonical lookup's byte sensitivity does not imply that ingestion preserved all input spelling. [`identity.cc`, numeric remap](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/identity.cc:514); desc registration and row parsing, same file, lines 615–814.

Probe P09 ingested the same cycle in two row orders. `("source", "10")` resolved to 0 and 2, while reverse lookup recovered `"10"` in each database. Thus:

- A VID may cross a boundary only with the identity of the exact graph/mapping it addresses.
- A canonical pair may cross when the producer and consumer agree on the namespace and normalization contract. A name alone does not prove global namespace ownership or collision freedom across producers.
- The existing attached catalog is persistent identity evidence, not a semantic graph-version identifier.
- The fixed-width ABI adds a further restriction: long pairs cannot be assumed to round-trip (§13, P11).

**Baseline admission:** reference equality and unambiguous scope are necessary. Dense allocation, text-pair representation, catalog codes, attachment files, and registration order are not. Removing those particular mechanisms would not make graph semantics impossible; removing referential identity would make incidence and result attribution ill-defined. Stability is strongest within a fixed mapping, not across rematerialization. Falsifiers F01/F10 appear in §18.

## 2. Minimal graph/fact representation

### 2.1 Adjacency is smaller than a general fact database

The storage-facing fact is an edge with two endpoint handles and a tag. `PersistentEdge` additionally carries a floating weight and linked-index/deletion bits. `StorageEdgeRef` presents direction-neutral A/B endpoints; logical source/destination is resolved above storage using layout information. The packed binary fields are not an ontology. A vertex is addressable through intervals and, optionally, identity/property data; interval membership alone does not prove an observed entity exists. [`edge_list.h`, records and references](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/edge_list.h:12); [`StorageViewReadDomain::LogicallyOrientedEdge`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/storage_view_query.h:513); P08.

Multiplicity is a material limitation. `WriteEdgeListSortedUnique` sorts and collapses identical endpoint/tag triples. Desc identity ingestion additionally collapses repeated endpoint pairs within an edge-label input, recording collapsed counts. A repeated source row or a separate evidentiary occurrence is therefore not automatically retained as a distinct adjacency fact. Conversely, different tags can produce the same neighbor VID more than once. Neither “all outputs are sets” nor “arbitrary multigraph identity is preserved” is valid. [`edge_list.cc`, writer](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/edge_list.cc:195); [`identity.cc`, seen_pairs](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/identity.cc:789); [`test_db0_primitives.cc`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_db0_primitives.cc:49); P04/P05.

### 2.2 What tags do—and do not—mean

`edge_tag_t` is `uint8_t`; 255 is `INVALID_TAG` and serves as a wildcard in these query surfaces. Schema definitions use wider `uint32_t` tags. `SchemaStore::GetEdgeTag` resolves the triple `(label, src_label, dst_label)`. Default assignment follows schema encounter order; an explicit tag-map file can reassign it. A desc importer eventually narrows the tag to `edge_tag_t`. Thus a tag simultaneously participates in schema classification, physical subpartition selection, and execution filtering, but is not self-describing without a graph-local schema/mapping. [`types.h`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/types.h:15); [`schema_store.h`, EdgeLabelDef](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/schema_store.h:36); [`schema_store.cc`, AssignTags/GetEdgeTag](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/schema_store.cc:401); [`test_schema_store_tag_map.cc`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_schema_store_tag_map.cc:39).

The baseline need is distinguishable relationship meaning when the source has distinct relationships. It does not require one external relation per byte tag. Wider schema tags, wildcard reservation, independent source mappings, and parallel occurrences all need separate fidelity checks. This report does not select an encoding for them.

### 2.3 Values and schema

Vertex/edge inline bytes, typed columns, and sparse property stores exist alongside topology. Their layouts/types supply interpretation; an arbitrary byte array is not a self-describing semantic assertion. `DB0::*WithData` exposes edge payloads with caller-supplied width; sparse property stores have their own APIs. GraphBatch vertex/edge state is algorithm state and must not be mistaken for immutable source facts. [`inline_data.h`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/inline_data.h:1); [`vertex_property_store.h`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/vertex_property_store.h:1); [`edge_property_store.h`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/edge_property_store.h:1); aligned payload assertions in `test_db0_primitives.cc`.

The semantic obligation is to retain distinctions and values that the requested computation needs. It does **not** admit a universal property-graph subsystem into BASELINE. Particular payload codecs, schemas, property indexes, and specialized enrichment are EXTENSIONS or ADAPTER / DOMAIN FACILITIES. Native adjacency alone does not establish preservation of all normalized source facts, n-ary assertions, evidence identities, or proof provenance. These remain explicit limits, not an invitation to redesign the fact model in this task.

## 3. Logical execution domain

### 3.1 The genuine invariant

A read must have an explicit universe and visibility interpretation. Otherwise the same “no result” could mean absent, outside scope, unavailable, or not yet published. This semantic requirement is BASELINE. `StorageView` is a current realization that maps dense logical partition ordinals to physical shard/partition intervals and tag declarations. Delivery plans separately declare local owned/executable/readable partition lists. Ownership and delivery are execution context, **not an authorization boundary**. [`storage_view.h`, manifest/partition/delivery structures](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/storage_view.h:67); [`CODEBASE_REVIEW_GUIDE.md`, logical read domain](/Users/geoffcheng/Projects/context/gfs/gfs_l0/CODEBASE_REVIEW_GUIDE.md:198).

`BuildVirtualGlobalView` sorts physical interval references, rejects overlapping intervals, and assigns dense logical ordinals. This abstracts lookup placement, but those ordinals are not content identities stable under every repartitioning. A single-shard virtual build delegates to the physical view. There is no semantic graph digest, immutable view ID, or MVCC snapshot token in the read manifest. [`storage_view.h`, builders](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/storage_view.h:224); [`test_storage_view.cc`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_storage_view.cc:27).

### 3.2 Declaration is not enforcement

`StorageViewReadDomain::Open` validates and copies a view/delivery plan, resolves readable partition references, and opens their physical shards. One endpoint direction reads matching intervals; the other searches all readable partitions. Consequently an edge can remain visible when its queried seed lies outside the local interval set. Readable partition coverage is not an induced vertex subgraph (P06).

Three additional counterexamples were executed:

- `view.tags={1}` did not prevent wildcard reads from emitting physically present tag 2, nor explicit tag-2 queries (P01/P02).
- A direct delivery list `{0,0}` was accepted and doubled emitted rows (P05). Save/load normalization and direct `Open` are different admission paths.
- Direct `Open` accepted manifest version 999 and an unknown `kind` (P07). The validator checks dense ordinals, direction agreement, interval ordering, and PID bounds, not a full semantic/version contract.

Sources: [`ValidateDeliveryPlanAgainstView`/`ValidateViewManifest`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/storage_view.h:690); [`ResolvePartitionRefsForPids`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/storage_view.h:747); [`read loops and OpenReadableShards`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/storage_view_query.h:405). The standard builders are stronger than arbitrary accepted manifest objects; neither proves enforcement of tag declarations.

### 3.3 Visibility and physical independence

Ordinary reads open DB0 base `SubEdgePartition` readers. They do not select BSP vertex slots or resolve committed LSM iteration fences. That storage path is distinct from GraphBatch's snapshot stores. Do not infer “latest committed GraphBatch state” from a read-domain object or a separately reported coordinator iteration. [`DB0::OpenShard`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/interface0.cc:223); [`EdgePartition::Open`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/edge_partition.cc:5); [`SubEdgePartition::OpenReader`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/sub_edge_partition.cc:176).

Logical direction normalization permits equivalent source/destination layouts when storage and metadata agree. It does not authorize relabelling existing indexes by changing metadata. The unmodified `test_storage_view_query_domain` fails for exactly that fixture sequence on this checkout; a temporary consistent-layout and payload-alignment variant passes (§18). ABI query tests exercise both layouts successfully. This supports conditional logical equivalence, not arbitrary physical-layout invariance or stable result order.

## 4. Primitive read/traversal algebra

The useful semantic primitive is **enumeration of incident directed edge facts within the selected visible domain, with explicit classification selection**. Native DB0 A/B indexed access implements it; the physical choice of contiguous range versus linked index is an IMPLEMENTATION DETAIL.

- **NATIVE PRIMITIVE:** attached identity lookup in either direction; base incident-edge enumeration; payload-bearing access in the relevant storage API. These are primitives relative to the inspected reusable boundary, not irreducible mathematical axioms.
- **DETERMINISTIC COMPOSITION:** logical IN/OUT adapts physical A/B orientation; BOTH concatenates IN then OUT; neighbor vertices project endpoint handles; exact edge existence selects matching endpoints/tags; degree counts selected incidence; BFS adds frontier/visited/depth; shortest paths add predecessor reconstruction; temporal reads interpret and filter payload timestamps; more advanced paths compose these kernels.
- **CONVENIENCE QUERY:** named query entrypoints, CLI commands, prepared statement families, and result-shaping variants package the compositions. A compiled native implementation of BFS does not make BFS a new baseline primitive.
- **IMPLEMENTATION DETAIL:** index layout, partition routing, shard enumeration, eager vectors, cursor positions, and compatibility direction wrappers.

Evidence: [`StorageViewReadDomain` neighborhood methods](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/storage_view_query.h:180); [`query_internal.h`, OperationKind/options/results](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/query_internal.h:21); [`query_internal.cc`, CollectNeighborEdges/TraverseVertices](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/query_internal.cc:1635); [`test_c_api_query.cc`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_c_api_query.cc:145); [`test_c_api_traversal.cc`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_c_api_traversal.cc:35); `binding_surface_track.md`, P4 and Q2/R1/R2 status sections.

### Result semantics that must remain explicit

Neighbor enumeration preserves incidence rather than deduplicating endpoints. BOTH emits a self-loop twice (P04). BFS uses a visited set, includes the root, and emits a discovered vertex once with depth and discovery direction. These are intentionally different derived results. A traversal depth bound does not bound graph degree, total rows, memory use, or elapsed work.

Returning `false` from the low-level callback stops the current partition's scan, not necessarily the enclosing multi-partition/domain operation: P03 received two callbacks after always returning false. ABI cursor consumption cannot test this behavior because collection already occurred before the first row was requested. No universal cancellation/work-budget contract was established.

Temporal access requires a known payload width and timestamp offset. Missing `edata` files can be skipped by the DB0 payload path; therefore no temporal match is not proof of no underlying edge. The controlled read-domain fixture exercises this explicitly. Timestamp ordering is a native derived predicate, not an intrinsic meaning of all edges. [`TemporalQueryPolicy`/timestamp resolution](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/storage_view_query.h:32); [`DB0` data-presence check](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/interface0.cc:107); `test_storage_view_query_domain.cc`, lines 503 onward.

Names such as callers, dependencies, impact, and reachability do not introduce independent repository-semantic primitives here. A domain could interpret selected relations and compose traversal to construct such views, but the interpretation is not supplied by `gfs_l0`. No general logical entailment, Datalog engine, or proof-producing rule substrate was established by the inspected graph/program/ABI surfaces.

## 5. Whole-graph deterministic computation

### 5.1 Smallest additional semantic operation

For the supported BSP path, a defensible abstraction is:

```text
selected domain + program + published graph state
    → gather visible incident state
    → compute private center/out-edge updates
    → stage next state
    → worker completion and storage checks
    → publish iteration
    → repeat to the requested target
```

Fresh engine state starts at committed index -1; loop iteration `i` stages target `i` while reading the previously published state. This is the same conceptual step as `state(t) → state(t+1)` with different indexing. Private center/out-edge getters can observe their own writes; “every read is immutable old state” is too strong. Incoming-edge proxies are read-only. This is state computation over existing graph structure, not general insertion/deletion or a sound-inference guarantee. [`graph_batch.h`, proxies/context](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/graph_batch.h:243); [iteration setup](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/graph_batch.h:1838); [publication](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/graph_batch.h:4392); `graph_batch_summary.md`, §§1–3.

The program adapter exposes gather/apply/scatter hooks and lane/state schemas. Present materialization supports center state and incident edge state, not arbitrary readable/writable neighbor-vertex state. Some frame positions exist without materialized state; edge tags in that adapter are `INVALID_TAG`. Describing a lane does not prove it carries all native fact distinctions. [`graph_batch_program_registry.h`, ProgramAdapter](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/graph_batch_program_registry.h:109); negative lane assertions in [`test_graph_batch_program_registry.cc`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_graph_batch_program_registry.cc:1077) (inspected, not freshly run).

### 5.2 Modes and whole-domain coverage

`Run` writes back sequential intervals and can expose earlier interval changes to later work. `RunSnapshot` captures edge run fences but is not the same durable vertex-slot publication protocol. `RunBSP` selects the supported threaded implementation. Public `RunThreaded` and `RunAsync` reject calls in current BSP-only mode. The guide's inventory is not proof that all modes are supported. [`graph_batch.h`, entrypoints](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/graph_batch.h:4535).

Fresh `test_graph_batch_async_diff` asserts **Run versus BSP differ**, despite its name. Fresh `test_graph_batch_snapshot_smoke` establishes equality for its integer fixture. Fresh `test_graph_batch_async_checkpoint` verifies that disabled async calls create no checkpoint artifacts. None establishes equivalence of all modes.

The engine's local interval set is not automatically the whole semantic graph. The maintained runner creates a synthetic global namespace for selected physical shards/tags; view-backed edge access remains an opt-in route. A barrier cannot recover omitted cross-shard dependencies. `ctx.nvertices` sums interval widths, which need not equal an independently enumerated semantic entity count. [`graph_batch.h`, domain/counting](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/graph_batch.h:1233); [`graph_batch_run_main.cc`, global route](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/graph_batch_run_main.cc:2601); `graph_batch_summary.md`, §5.4.

### 5.3 Determinism, publication, and resume limits

The runtime stabilizes tag ordering and attaches remote replies in partition order, but does not enforce associative/commutative reducers or a canonical floating-point reduction tree. PageRank adds floating values sequentially; random walk selects an outgoing-edge ordinal using VID, iteration, and seed. Equivalent graph sets with different lane orders can therefore differ. A descriptor's `kDeterministic` value is a declaration, not a verified property. [`graph_batch_builtin_programs.cc`, PageRankApply/RandomWalkApply](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/graph_batch_builtin_programs.cc:200); [`graph_batch_program_abi.h`, policies](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/graph_batch_program_abi.h:168).

Current resume restores selected persisted graph state and checks program metadata; it does not checkpoint arbitrary program-owned memory. Resource-identity matching also has an older-manifest compatibility exception. Stateful FastUnfolding initializes working vectors at iteration zero; a newly constructed later-iteration resume needs separate validation. Its shared move counter is a source-identified race candidate under concurrent updates, not a sanitizer-proven result here. The BSP loop also lacks the `last_iteration` check used by the sequential paths. These are remaining falsifiers, not fixes made by this report. [`program metadata equality`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/graph_batch_program_abi.h:138); [`FastUnfolding` initialization/update](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/graph_batch_builtin_programs.cc:310); `graph_batch.h`, lines 1838 and 3463.

More decisively, the fresh `test_graph_batch_bsp_resume_fence` is **intermittent** at this checkout/build. It compares uninterrupted execution with one-step checkpoint, injected future iteration-98 edge state, and resume. The first run passed; a repeated suite failed `e_clean == e_resume`; 20 subsequent sequential runs yielded 19 passes and the same failure once. Vertex equality passed before the failing assertion. This falsifies unconditional qualification by that test. The underlying cause and which run diverged are not established solely by the equality failure. [`test_graph_batch_bsp_resume_fence.cc`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_graph_batch_bsp_resume_fence.cc:310).

One **unconfirmed source-supported hypothesis** is partial-run publication: queue draining and producer-completion observation are separate, while completion can trigger a flush; a late final batch could then produce another run for the same iteration. The explicit-run snapshot path reads the latest run and cleanup retains one, so the completeness of that run matters. This could affect either side of the parity comparison; no causal trace was collected, and iteration-98 contamination is not asserted. [`drain/flush decision`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/graph_batch.h:2024), same file at line 2499; [`IsAllDone`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/graph_batch_hub.cc:643); [`latest-run read`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/lsm_sub_edge_partition.cc:2430), cleanup at line 1269.

Staging validation resolves an eligible snapshot, not necessarily an exact target run in every partition. Publication writes authority and compatibility mirror separately, then removes intent; later failure can be reported after authority changed. The inspected rename helper does not itself establish power-loss durability. Cleanup can remove older runs, so arbitrary historical snapshots are not retained. [`bsp_snapshot_store.h`, publication/validation](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/bsp_snapshot_store.h:876); [`lsm_sub_edge_partition.cc`, eligible-run resolution/cleanup](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/lsm_sub_edge_partition.cc:1223); fresh `test_lsm_bsp_iteration_contract` and `test_bsp_snapshot_view_store` cover selected successful paths, not all failure windows.

Coordinator `committed_iteration` records a completed-count/next-position value (`i+1`), unlike the engine snapshot's last committed index. The tested follower sees an already committed manifest; it does not prove distributed concurrent correctness. Default global runner resume is rejected, and the distributed multi-shard path has an explicit unsafe override guard. [`global_bsp_coordinator.h`, CommitIteration/Barrier](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/global_bsp_coordinator.h:394); [`test_global_bsp_coordinator.cc`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_global_bsp_coordinator.cc:399); `graph_batch_run_main.cc`, lines 2604 and 2898.

**Classification:** EXTENSIONS. Iteration and publication are necessary for BSP semantics, but removing BSP does not prevent local graph selection, composed retrieval, or deterministic reasoning outside this runtime. Double buffers, hub queues, manifests, and LSM tokens are its TRANSPORT / IMPLEMENTATION mechanisms, not additional baseline concepts.

## 6. Determinism / ordering / visibility

The following identities must not be substituted for one another:

1. **Input identity:** names/bytes of ingested source artifacts and adapter normalization.
2. **Graph referential identity:** the current canonical-pair ↔ VID mapping and relation/schema mapping.
3. **Logical domain identity:** selected graph/partition coverage and intended visibility; no general semantic content identity was found in the manifest.
4. **Snapshot identity:** an actually pinned visibility boundary, where one exists, not a delivery epoch or ABI handle address.
5. **Result determinism:** fixed inputs, visibility, operation, arithmetic, and policies produce equivalent results.
6. **Ordering determinism:** the same sequence, a stronger claim than equal membership.
7. **Serialization determinism:** repeatable representation; neither necessary nor sufficient for semantic equivalence.

The maintained query contract explicitly preserves family-native order rather than promising global sort. BFS tie selection, all-path enumeration, prefix limits, and fixed-seed ordinal selection can depend on that order. Partition normalization and deterministic filenames do not establish physical-layout-independent result sequences. [`binding_surface_track.md`, ordering contract](/Users/geoffcheng/Projects/context/gfs/gfs_l0/binding_surface_track.md:3232); [`query_internal.cc`, traversal queue](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/query_internal.cc:1740).

Read absence means “no emitted fact under this path and its effective visibility,” unless completeness is separately established. Causes include absent relation, omitted partition, payload unavailable, depth bound, typed filter, projection, or current storage version. No general closed-world completeness certificate or inference provenance accompanies ordinary neighbor rows. Declared state, successful transport, deterministic computation, and semantic justification remain distinct.

## PART II — Layering

## 7. BASELINE

The four candidate obligations below are the entire baseline proposed by this investigation. They deliberately do not require a graph database API, a property-graph ontology, a storage layout, or a general rule language.

**B1 — Scoped referential identity.** Incidence and results require stable equality within an identified graph/mapping; translation must preserve that equality when crossing a boundary. Native evidence: VIDs and optional canonical resolver (§1). Removing equality makes attribution ill-defined. Current support is conditional: registration order and ABI truncation prohibit broader claims. F01/F10.

**B2 — Distinguishable facts and relationships.** The computation must preserve the endpoint roles, relationship distinctions, multiplicity, and values it actually uses. Native evidence: directed adjacency, tag/schema mapping, payload APIs (§2). Removing relevant distinctions changes the question being executed. Current adjacency is a restricted realization, not proof that arbitrary facts can be embedded losslessly. F04/F10.

**B3 — Explicit observation scope and visibility.** A result must be interpreted against a defined visible universe. Native evidence: readable domains and the separate BSP visibility mechanisms (§3/§5). Removing this boundary makes absence and repeatability ambiguous. Full manifest semantics are not admitted; enforced tag scope and read snapshot pinning are incomplete. F02/F07.

**B4 — Deterministic selection and composition with explicit outcomes.** Operations require declared incidence/direction, selection, duplicate/order behavior, bounds, and failure interpretation. Native evidence: incident reads and shared query kernels (§4/§6). Without these, a deterministic middle is materially ill-defined. This does not require all-path search, a native fixed-point engine, streaming cursors, or universal cancellation. F03/F05/F06.

These are **minimum semantic invariants, not blanket claims that all existing paths satisfy them**. The principal discovery is the distinction between a small invariant target and the partially faithful mechanisms already present.

## 8. EXTENSIONS

Each extension adds capability without changing what a baseline fact or identity means:

- Baseline + **iterative state and fenced publication** → BSP-style graph algorithms. Present, qualified by §5; not general logical entailment.
- Baseline + **advanced traversal plans** → shortest/all-shortest/all-path and source/sink reachability. Present in `query_internal`; not all projected through the public C ABI. Membership/order/limit semantics remain family-specific.
- Baseline + **typed payload interpretation** → temporal predicates and property-dependent computation. Present native mechanisms; timestamp bytes and missing-data behavior remain explicit.
- Baseline + **result shaping** → typed field projection, decoration, narrow filters, and native-order prefix limits. Internal Q2/R1/R2 work is richer than the current public query ABI. Shaping is not a new source fact.
- Baseline + **persisted computation/audit artifacts** → inspectable program results, export verification records, and history. Present for particular workflows. These are not generic evidence proofs or semantic memory.
- Baseline + **mutation journaling/recovery mechanisms** → local replay/recovery infrastructure. Native modules exist and the binding track distinguishes this from build resume; a general public L0 transactional query/write algebra was not established or qualified here.

Sources: [`query_internal.h`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/query_internal.h:21), `binding_surface_track.md` §§P4/Q2/R1/R2 and opening mutation notes; [`mutation_journal.h`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/mutation_journal.h:1); domain evidence in §9. No new generic incremental inference, truth-maintenance, proof provenance, or persistent research-memory semantics are inferred from these mechanisms.

## 9. ADAPTER / DOMAIN FACILITIES

### 9.1 Landing ports pass the adapter hypothesis

`BuildDomainLandingPlan` selects artifact roots, paths, and identity/export/reconstruction modes. It precedes identity attachment and adjacency/property materialization; it is not the constructor of the executable graph-read domain. Existing valid native storage can be opened without invoking a landing plan. That semantic bypass is the removal proof—not a claim that deleting a linked C++ module would compile. [`domain_landing_port_track.md`, boundary](/Users/geoffcheng/Projects/context/gfs/gfs_l0/domain_landing_port_track.md:63); [`BuildDomainLandingPlan`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/domain_landing_port.cc:8824); P01–P10 create/read native storage without landing operations.

The finite catalog describes grounded-document, issuer-filing, Cora, and ZINC-subset families. This is actual adapter vocabulary, cited to classify it—not vocabulary imported into BASELINE. Catalog flags do not dynamically prove exporter availability, instance readiness, or executable compatibility. [`ReadDomainLandingPortCapabilities`/catalog](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/domain_landing_port.cc:8037); [`test_domain_landing_port.cc`, catalog assertions](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_domain_landing_port.cc:83).

### 9.2 Deterministic policy is not semantic necessity

`SelectGroundedDocumentCorpus` can select a subtree holding at least 70% of detected documents. That is a deterministic corpus-selection heuristic, not a proof of semantic completeness. Explicit file inventory could replace it without changing graph execution. Materialization also invokes domain-specific exporters and applies path/readiness policies; `OK`, materialization outcome, and complete validation are separate. [`selection`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/domain_landing_port.cc:1273); [`readiness/materialization`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/domain_landing_port.cc:8792); test selected-root assertions at line 429.

`VerifyDomainLandingExportPackage` checks package/schema/input shape, not all endpoint referential integrity or domain truth. The existing test changes a vertex table while retaining an edge reference to the old identity and still expects package readiness. That freshly passing test is evidence of the checker's limited authority, not semantic validation success. [`verifier`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/domain_landing_port.cc:9399); [`changed package accepted`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_domain_landing_port.cc:865).

Graph-task reuse inspection checks metadata, expected files, and selected layout conditions; it does not decode and validate all graph/tensor contents. Compatibility reproduction can rewrite requested order/configuration metadata without reordering graph bytes. A returned `reuse` or successful reconstruction report is not independent proof that the requested physical transformation occurred. [`reuse inspection`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/domain_landing_port.cc:13515); [`target metadata/rewrite`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/domain_landing_port.cc:14180); [`test_domain_landing_gnn_reuse.cc`, rewrite assertions](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_domain_landing_gnn_reuse.cc:629) (inspected, not freshly run).

### 9.3 Projection, reconstruction, and evidence records

`ResolveGraphExportRow` reads selected domain export tables. `stable_only` filters against a field catalog; full projection adds domain-specific joins and blob payloads. “Stable” here means catalog-defined projection stability, not source truth, graph identity, or universal schema stability. The corresponding scan follows TSV order and resumes after an exact ID without a snapshot/regeneration token. A recommended limit of 100 is advisory: an existing test requests 101 and expects 101 effective. [`row reconstruction`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/domain_landing_port.cc:13002); [`projection/scan tests`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_domain_landing_port.cc:2436).

Package fingerprints hash selected schema/path/input representation using FNV-1a; they are not a semantic graph digest and do not cover every possible sidecar. Verification records preserve reports and history, with best-effort multi-artifact integrity, not generic proof provenance or an atomic research-memory transaction. [`ComputePackageFingerprint`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/domain_landing_port.cc:7943); [`record preservation`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/domain_landing_port.cc:9743); test fingerprint/history assertions at lines 836–973; `domain_landing_port_track.md`, best-effort audit note at line 3093.

The reusable invariants inside these facilities—preserving identity distinctions, distinguishing ready from executed, and separating stable fields from enrichment—do not promote the module itself to BASELINE. Generic artifact tracking may be an EXTENSION; these family mappings, repair policies, export joins, and reconstruction plans remain ADAPTER / DOMAIN FACILITIES. F09/F12 specify how to falsify this classification.

## 10. TRANSPORT / IMPLEMENTATION

Primary members of this layer are packed storage records, physical shard/tag partitions, A/B indexes, run IDs, buffer slots, hub scheduling, manifest encoding, file paths, ABI structs and capacities, object lifetimes, error transport, cursors, and compatibility wrappers.

Some implement essential guarantees: a publication fence realizes visibility; correct lifetime management makes access safe. Their necessity **as mechanisms in this build** does not make those particular mechanisms semantically invariant. The accelerator header dependency encountered during the isolated build is a concrete example of build coupling that cannot justify promoting tensor/accelerator machinery into BASELINE (§18).

ABI-only names such as connection, prepared statement, cursor kind, intent preset, and job handle must be classified by role. They can expose or package a native operation without becoming independent graph concepts. Context/ownership is not authorization; an in-process pointer or readable-PID list is not an access-control proof.

## PART III — ABI projection

## 11. Native → ABI projection proof

The relevant public wrapper surface is `include/l0/c_api.h` plus `src/c_api.cc` and the native `binding_service`. GraphBatch's plugin ABI is a separate executable interface. A route is called DIRECT when it exposes the operation directly, not when every input/result is necessarily lossless. Table 4 gives one summary classification; the qualifications below govern it.

### 11.1 Identity, presence, and incidence

**Canonical translation: DIRECT operation, PARTIAL fidelity.** `gfs_l0_graph_lookup_vid_by_canonical_identity` and its reverse open the attached native resolver. Missing keys retain native error behavior; short identities round-trip in the fresh identity test. The reverse uses fixed fields rather than the native string domain, causing the executed P11 collision. This is semantic loss, not merely formatting. [`lookup implementation`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:8493); [`test_c_api_identity.cc`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_c_api_identity.cc:112).

**Vertex presence: DIRECT, with an explicit distinction from placement.** `gfs_l0_vertex_presence_t` reports present, readable-partition-present, and canonical-identity-present separately. The native kernel checks identity or incident edges, not interval membership alone. However, traversal admits a root through readable partition placement before emitting depth zero. A gap VID can therefore be absent by presence yet appear as a traversal root; this is a source-derived, unexecuted cross-operation falsifier, not a new observed probe result. [`presence kernel`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/query_internal.cc:1441); [`traversal kernel`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/query_internal.cc:1719); gap-presence assertions in [`test_c_api_query.cc`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_c_api_query.cc:350).

**Directed tagged incidence: DIRECT on the fixed topology projection.** Neighbor-edge cursors expose query VID, source, destination, edge tag, and direction. Graph-direct, connection, and prepared routes lower into shared native queries. They do not expose `PersistentEdge` weight, edge payload bytes, occurrence identity, provenance, or a snapshot token. Neighbor vertices project incidence endpoints; BFS is a directly callable **derived operation**, not a newly primitive fact relation. Fresh query/traversal tests cover fixed fixtures and both physical layouts. [`public row contracts`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/c_api.h:329); [`query builders`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:1418).

**Exact edges, degree, bounded paths: COMPOSED where the available rows suffice.** A wrapper can filter/count edge rows and compose bounded search over known seeds. It must preserve multiplicity and direction rules. This does not provide a complete vertex-universe scan, native temporal payload access, or a consistent multi-call snapshot. “Can implement a search externally” is weaker than faithful projection of every native path family and its visibility/error contract.

### 11.2 Logical domain and visibility

**View/delivery state: METADATA ONLY; effective custom query domain: MISSING/PARTIAL.** State inspection loads persisted manifests and delivery plans. Query construction instead discovers physical shards and invokes `BuildFullCoverage(..., tags={})`. No public query parameter binds the saved view, local readable PID set, or a committed iteration. This difference is intentional surface separation in the maintained binding track, but it falsifies treating reported state as query enforcement. [`ReadStorageViewStateSnapshot`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/binding_service.cc:223); [`BuildFullReadDomain`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:1068); `binding_surface_track.md`, implementation snapshot around line 2806.

P10 saved a view with only tag 1 and delivery with only readable PID 0. The ABI reported one tag/one readable partition, then returned six wildcard edges including two tag-2 edges and two from excluded PID 1. The test proves a projection/enforcement distinction, **not an authorization bypass**, because these manifests are not established security controls.

**Cursor stability: materialized results, not snapshot acquisition.** Opening a cursor executes the query and constructs vectors; advancing moves a position. An already-open cursor can preserve rows while a later execution changes, without the first execution ever having acquired a coherent storage snapshot. Native scope/callback behavior is not repaired by row-at-a-time consumption. [`cursor construction`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:1601); [`cursor advancement`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:680).

### 11.3 Richer native and adapter capabilities

The internal typed query algebra includes exact edges, degree, two-hop, secondary edges, temporal/non-temporal paths and reachability, selected filters/projections, and prefix limits. The public prepared statement enum remains six variants: neighbor vertices, neighbor edges, and traversal, each by VID or canonical identity. Current Q3 deliberately reuses the private bridge without expanding those public families. Rich internal values such as partition records, lists, paths, and 64-bit fields do not automatically become public cursor types. Public generic cells are U32 or canonical identity; a null cell can be rejected despite nullable metadata being representable. [`statement/value enums`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/c_api.h:54); [`bridge conversion`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:1210); `binding_surface_track.md`, Q3 at line 3524.

**GraphBatch: executable through a separate plugin ABI, not the generic wrapper job API.** Plugins expose lifecycle and gather/apply/scatter/iteration hooks; the loader validates exact ABI version, lifecycle pairing, and supported state widths. This is genuine executable native adaptation. Program contracts may be absent, falling back to opaque parameters/resources, so typed discovery is not universal. The plugin does not independently select a graph or make the wrapper's reserved GraphBatch job controls usable. [`graph_batch_plugin_abi.h`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/graph_batch_plugin_abi.h:128); [`plugin loader`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/graph_batch_plugin_loader.cc:15); [`opaque-contract fallback`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/graph_batch_plugin_bridge.cc:638); [`C plugin execution assertions`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_graph_batch_plugin_abi.c:297) (inspected, not freshly run).

**Landing facilities: selected DIRECT operations with PARTIAL result transport.** Readiness, materialization, verification, row reconstruction, scan, and comparison have native-to-C forwarding. Row/scan JSON has byte-count/truncation indicators, unlike ordinary fixed strings. Native graph-task reuse/reproduction has native/CLI callers but no corresponding sufficient public C operation was found. [`landing forwarding`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:4889); [`row conversion`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:3945); [`native reuse declarations`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/domain_landing_port.h:1239); C adapter assertions in `tests/test_c_api.c` (inspected only).

## 12. ABI-only concept classification

- **Handles, connection/prepared/cursor lifetime, enums, status/error objects, fixed fields:** TRANSPORT / IMPLEMENTATION. They package existing operations. Closing a parent invalidates owned children; these are not independent semantic identities or reference-counted lifetime promises. Errors require separate destruction. [`context close`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:4130); [`graph/connection teardown`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:8283); `test_c_api_handles.c` and `test_c_api_connection.cc` are inspection anchors, not fresh results here.
- **Capability flags, statement/parameter/cursor descriptors, layout/view summaries:** DESCRIPTIVE METADATA under TRANSPORT / IMPLEMENTATION. They help discovery but do not establish graph truth or universal executability.
- **Identifier decoration:** projection of the native identity relation, an EXTENSION surfaced through transport. VID-only/canonical-only/both affect generic projected columns, not membership/order. Specialized fixed rows remain VID-bearing even when generic projection is canonical-only; the maintained track explicitly distinguishes them.
- **Landing family, stable/full projection, intent defaults, export labels and repair outcomes:** ADAPTER / DOMAIN FACILITIES. These are scenario contracts, not generic graph predicates.
- **Legacy numeric-ID entrypoint aliases:** HISTORICAL / COMPATIBILITY implementations of existing behavior. Their names do not create a second identity algebra.
- **Execution-context opaque type, reserved job kinds, job control verbs:** FUTURE / UNIMPLEMENTED where current code says so; not executable baseline capabilities.

`gfs_l0_job_cancel`, `pause`, `resume`, and `force_stop` return `NOT_IMPLEMENT`. Opening generic GraphBatch/landing-export jobs returns `NOT_EXIST`; this contradicts header wording suggesting inspectable zero-capability snapshots for reserved kinds. Current bulk-load job enumeration is metadata readback of at most the current job, not a history scheduler. [`job control implementation`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:2195); [`job open`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:9467); [`test_c_api_job.cc`, expected unsupported behavior](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_c_api_job.cc:182) (inspected only).

Another source-derived mismatch: generic job state maps a succeeded phase to final/succeeded and `run_complete`, whereas the resume inspector only treats committed completion as complete. A succeeded intermediate phase can therefore yield different completion interpretations. Existing committed-success assertions do not settle that case. [`generic mapping`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:1974); [`resume phase semantics`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/bulk_load_resume_inspector.cc:71). No new job workflow was run to resolve this.

## 13. Semantic loss / missing projection

### 13.1 Loss that is demonstrated

`CopyString` silently copies at most capacity minus one and NUL-terminates. Native identity permits much longer values than `gfs_l0_identity_key_t`'s 64-byte space and 256-byte value arrays. P11 attached two distinct 301-byte values sharing their prefix. Direct forward lookup of the full second value returned VID 1, but reverse projections of VIDs 0 and 1 were the same 255-byte value, both with `OK`. This falsifies general injectivity of the native-to-ABI identity projection. It can also split UTF-8 by bytes. [`CopyString`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:231); [`FillIdentityKey`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:360); [`identity ABI layout`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/c_api.h:271).

Long paths, summaries, job IDs, fingerprints, and coordinator JSON are subject to analogous fixed-field loss where they use the same copier. Some export JSON surfaces report truncation and full byte count, but disclosure does not recover the missing bytes and truncated JSON may be unparsable. Do not treat all fixed buffers as equivalent to a dynamic native result.

### 13.2 Projection not currently supplied

The fixed query ABI does not sufficiently expose arbitrary vertex/edge properties, edge occurrence identity, all native temporal/path operations, caller-selected read-domain enforcement, pinned ordinary-read snapshots, a general complete vertex/fact scan, query work budgets/cancellation, or general rule/proof semantics. Some operations can be externally composed for a restricted known graph; that does not remove these fidelity and completeness limits.

GraphBatch state/schema metadata and landing evidence records are not general proof provenance. A derived result needs an explicit interpretation and evidence contract before it can support a claim. This investigation does not invent that contract or relabel report metadata as semantic proof.

## PART IV — Agent self-description

## 14. Capability discovery

An unfamiliar wrapper with the **matching header** can discover library/graph capabilities, identity attachment/spaces, saved layout/view/coordinator summaries, statement kinds and parameters, cursor columns, and landing catalogs. It can drive the narrow query families without reading their C++ algorithms, provided it already knows ownership and input conventions. This is valuable support, but not complete machine-readable contract reconstruction.

`GraphCapabilities` includes broad facility flags such as bulk-load submission/resume, offline property columns, property schema, and read domains. Some describe native/library facilities rather than executable C methods: no general C bulk-load submit is established, job resume is a stub, property bits do not expose arbitrary property cells, and the read-domain flag does not allow selecting a saved restricted domain. Graph-specific canonical support is inferred from attached identity metadata, not a full health check of every slot/blob. [`capability defaults`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/binding_service.h:19); [`capability construction`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/binding_service.cc:76).

Statement descriptors report kind, result kind, support, canonical-input requirement, and parameter count. Parameter descriptors report names, bind kinds, and requiredness. They do not encode all defaults, valid ranges, wildcard meaning, ordering, visibility, work bounds, or execution-stage errors. Canonical statements can report unsupported when no identity is attached, while preparation still accepts their kind; failure is deferred to execution. [`descriptor layout`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/c_api.h:278); [`parameter catalog`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:924); [`prepare`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:9263); fresh [`statement-discovery test`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/tests/test_c_api_statement_discovery.cc:120).

## 15. Agent reconstructability

The categories here separate runtime metadata from external header/documentation knowledge; “without reading C++ implementation” does not mean “without any binding/header.”

- **Fully self-described within the narrow descriptor schema:** enumerated statement names/kinds, parameter names and bind kinds, current cursor column kinds/roles, reported identity spaces and attached state (subject to fixed-field loss).
- **Partially self-described:** available capabilities, current graph/view summaries, canonical versus numeric addressing, operation admissibility, stable versus enriched adapter fields, and supported projection modes. Metadata supplies part of the answer but not enforcement, complete data health, or all execution preconditions.
- **Requires external documentation/header:** default OUT direction, tag-255 wildcard, native-order versus sorted results, BFS depth behavior, ownership/error cleanup, field capacities, specialized-versus-generic decoration differences, and advisory versus hard adapter limits.
- **Requires implementation knowledge today:** saved view versus executed full coverage, the breadth gap behind capability flags, fixed-string silent loss, output-capacity assumptions, reserved job behavior, and the gap-VID presence/traversal distinction.
- **Not discoverable as an established semantic guarantee:** a semantic graph content identity, complete fact/vertex universe, ordinary-query snapshot pin, generic completeness/provenance certificate, verified arbitrary-program determinism, or universal resume safety. A descriptor cannot reconstruct a guarantee the implementation has not established.

Table 5 answers the user-facing questions individually. These classifications are about the **current exposed surfaces**, not a proposed future discovery protocol.

## 16. Limits / stability / contract discovery

### 16.1 Version validation is not general negotiation

The ABI version is currently 1. `gfs_l0_abi_version()` returns that constant. Selected request structs require `version==1` and `size>=sizeof(current struct)`; larger same-version tails are unused, and smaller prefixes are rejected. P12 executed the unknown-version and too-small-size rejections. There is no demonstrated negotiated downgrade.

Output initialization is asymmetric: `InitAbiStruct` clears the entire current structure and writes its version/size without checking caller capacity. P13 supplied a correctly allocated current output object whose initial version was 999 and size zero; the function succeeded and overwrote both. This demonstrates that those output fields are descriptive, **not** a capacity negotiation. A genuinely undersized old-client allocation was not tested; source inspection shows why the helper alone cannot make that case safe. Header “forward-extensible” wording is not sufficient proof. [`InitAbiStruct`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:151); [`request validation`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:1032); [`ABI version`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/src/c_api.cc:4110).

### 16.2 Boundedness and contract authority

The public traversal depth is a semantic path-length bound, not a global resource limit. Public cursors are eager, and no general row budget, page token, cancellation, or arbitrary filter language is exposed there. Internal `limit_hint` is a native-order prefix on selected row-set families, not a universal traversal-work bound. Adapter scan recommendations are advisory and separate from graph-query contracts. [`internal limit policy`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/binding_surface_track.md:3354); [`public traversal rows`](/Users/geoffcheng/Projects/context/gfs/gfs_l0/include/l0/c_api.h:350); §9 scan evidence.

Program descriptors include schema, parameters/resources, determinism and resume policy; loader/adapter tests establish parts of their structural admission. They do not independently verify callback purity, arithmetic reproducibility, complete program-state checkpointing, or that every declared lane is materialized. Operation contract, structural admission, and successful execution must remain distinct.

## PART V — Authority and maturity

## 17. Stable / transitional / historical surfaces

Here **STABLE** means established behavior at the inspected boundary with maintained callers/tests. It does not mean an immutable future product API or universal semantic correctness.

- **STABLE, bounded:** graph-local VID addressing; attached short canonical lookup; base A/B reads and aligned payload primitives; schema/tag mapping mechanics; narrow C neighbor/traversal families and current descriptor shapes. Fresh tests support these specific paths. The richer cross-boundary invariants remain qualified by P01–P13.
- **TRANSITIONAL:** ordinary logical-view enforcement and snapshot interpretation; full physical independence; complete canonical ABI fidelity; richer internal-query-to-public projection; output cross-version compatibility; GraphBatch programmability/lane completeness and resume qualification; domain readiness/reconstruction authority. These have substantial implementations, but current evidence prevents promoting stronger guarantees.
- **HISTORICAL / COMPATIBILITY:** directional DB0 wrappers around raw A/B, legacy numeric-ID aliases, GraphBatch compatibility mirrors and older-resource matching. They remain relevant to behavior but are not baseline vocabulary. Earlier “descriptor-only” landing-port notes are historical, superseded by implemented workflows.
- **EXPERIMENTAL / SCAFFOLD:** distributed independently progressing GraphBatch participants and unsafe multi-shard distributed routes; reserved execution-context and generic job control shape. Disabled `RunAsync`/`RunThreaded` are unsupported entrypoints, not experimentally working modes.
- **UNKNOWN / NOT ESTABLISHED:** complete external fact preservation, general multigraph occurrence identity, rule entailment/proof production, layout-independent floating or arbitrary-program determinism, crash/power-loss atomicity across all publication artifacts, and old-client/new-library output safety. Lack of proof is not a claim that every such use fails.

Authority order is current implementation plus the exact assertion tested, then maintained current architecture sections, then historical notes. For example, `graph_batch_summary.md` §§1–5 accurately guides BSP-first investigation; it cannot override the intermittent fresh resume result. `binding_surface_track.md` Q3 establishes why richer internal query work does not imply new public operations. The original read-domain fixture failure likewise stays visible even though a temporary corrected fixture passes.

## PART VI — Falsification

## 18. Falsification cases

### 18.1 Fresh build and run record

An isolated archive of the inspected HEAD was extracted under `/tmp/c7b-gfs-algebra.MX0te1`. Native library and selected tests were compiled with `-std=c++17 -Wall -O0 -g0 -I include`, with assertions enabled. This avoided rebuilding or altering the user's working binaries and excluded unrelated dirty source changes.

The first full-library attempt without sibling accelerator headers failed in `gnn_tensor_runtime.cc` on undeclared `gfs_l4` types. Retrying with `-I /Users/geoffcheng/Projects/context/gfs/gfs_l4/include` succeeded. The selected tests linked using only `-L. -ll0`; they did not link or qualify the accelerator library. The header was pristine in sibling HEAD `6fc34c7fd34aabed0c5de546a941b1c38aace813`; its `accel_runtime.h` SHA-256 was `1f4cea4058d1dad8fa52cf426f074f100bb26e933a94ee4d9a191fe5d6798840`. Existing sibling backend edits were not changed. This is a build-dependency observation, not evidence that accelerator execution belongs in the semantic baseline.

**Nineteen original test executables were freshly built and run.** Seventeen passed both observed rounds:

```text
test_identity                         test_schema_store_tag_map
test_storage_view                     test_db0_primitives
test_c_api_identity                   test_c_api_storage_view_state
test_c_api_query                      test_c_api_traversal
test_c_api_statement_discovery        test_domain_landing_port
test_graph_batch_async_diff           test_graph_batch_snapshot_smoke
test_graph_batch_threaded_pagerank     test_graph_batch_async_checkpoint
test_lsm_bsp_iteration_contract        test_bsp_snapshot_view_store
test_global_bsp_coordinator
```

The other two require explicit qualification:

1. `test_storage_view_query_domain`: failed in both original runs at `out_full == {10,12,20,22}`. The fixture creates indexes before writing `dst` layout metadata. `WriteEdgeListSortedUnique` and reopened readers select their index interpretation using that metadata. A temporary copy that sets `dst` before writing got past ordinary reads but failed temporal expectations because payload order still assumed the earlier sort. A second temporary adjustment aligned timestamp bytes to the actual persisted edge order; the complete variant then passed. **The repository test remains unchanged and failing.** This is controlled diagnosis, not a production fix or an unmodified pass.
2. `test_graph_batch_bsp_resume_fence`: passed the first run, failed the repeated suite's edge-byte equality, then failed again in trial 11 of 20 separate sequential repeats. The repeated sequence produced 19 passes/1 failure. The test checks vertex equality first, which passed in the observed failures. This is an intermittent counterexample, not a statistically estimated failure rate or a diagnosed root cause.

The integer snapshot/BSP tests and the PageRank test establish only their fixture comparisons. The latter uses one intra-partition thread; its name must not be read as broad thread-count determinism. The coordinator follower test observes an already published iteration. Async rejection is a negative capability result, not async execution success.

Temporary evidence is retained at:

- [Original test/probe run output](/tmp/c7b-gfs-algebra.MX0te1/c7b-test-results.txt)
- [Twenty resume repeat outputs](/tmp/c7b-gfs-algebra.MX0te1/c7b-resume-repeat-results.txt)
- [Native/ABI diagnostic probe](/tmp/c7b-gfs-algebra.MX0te1/c7b_probe.cc)
- [Controlled read-domain fixture variant](/tmp/c7b-gfs-algebra.MX0te1/c7b_query_domain_fixture.cc)

These paths are temporary, not repository acceptance artifacts. Tests create their own temporary fixture databases; this task did not delete the retained diagnostics. The textual outcomes and reproduction conditions below remain in this report if temporary files expire. No device, remote, distributed deployment, sanitizer, optimized-build, or whole-project qualification is claimed.

### 18.2 Executed additional probes

The single standalone probe exited 0 with all thirteen assertions below satisfied. Its success means the **counterexamples were reproduced**, not that the stronger proposed guarantees passed.

- **P01 — View tag restriction:** native view declares `{1}`, physical storage has tags 1 and 2; wildcard OUT(1) returns six edges, two with tag 2. Falsifies declaration-as-enforced-filter.
- **P02 — Explicit out-of-view tag:** asking for tag 2 returns both tag-2 edges despite `{1}` declaration. Falsifies automatic intersection with view tags.
- **P03 — Callback bound:** callback always returns false; two partitions still invoke it twice. Falsifies a global one-callback stop interpretation.
- **P04 — BOTH multiplicity:** one tag-1 self-loop is emitted twice. Falsifies set-valued incidence union.
- **P05 — Duplicate coverage:** direct readable PID list `{0,0}` is accepted and duplicates rows. Falsifies normalization on every admission path.
- **P06 — Non-induced coverage:** with only PID 1 readable, seed VID 1 has no readable owning interval but its edges into that partition are returned. Falsifies induced-subgraph membership interpretation.
- **P07 — Manifest admission:** direct `Open` accepts version 999 and unknown kind with otherwise valid references. Falsifies comprehensive version/kind validation.
- **P08 — Placement versus identity:** VID 7 lies in a readable interval with no incident facts; identity is unattached, yet graph reads work. Falsifies interval-membership-as-registration and canonical-attachment-as-read-prerequisite.
- **P09 — Input permutation:** identical cycle rows reordered; canonical `source:10` maps to VID 0 versus 2 and reverses correctly in each. Falsifies rematerialization-invariant VIDs, not scoped canonical equality.
- **P10 — ABI effective domain:** reported one tag/one readable PID coexists with six returned edges including tag 2 and excluded PID 1. Falsifies reported-view-as-executed-view.
- **P11 — Canonical output injectivity:** distinct 301-byte values successfully project to the same 255-byte value; full-string forward lookup still distinguishes them. Falsifies lossless identity projection.
- **P12 — Input negotiation:** unsupported version and undersized options return `INVALID_ARGUMENT`. Supports explicit same-version admission, not negotiated compatibility.
- **P13 — Output capacity interpretation:** a full-size allocated output initialized with version 999/size 0 is overwritten successfully as current version/current size. Falsifies caller-size-as-output-capacity interpretation without attempting an unsafe undersized allocation.

P01–P08/P10 use a two-shard `dst` graph, metadata installed before index construction: shard 1 interval `[0,15]` has `1→1` and `1→10` at each of tags 1/2; shard 2 interval `[16,30]` has `1→20` and `1→22` at tag 1. P09 uses the cycle `10→20→30→10` in two row orders. P11 uses two native identities with 300 identical prefix bytes followed by distinct suffix bytes. These fixture definitions make the reported counterexamples reproducible without promoting temporary code into the product.

### 18.3 Falsification ledger for every major conclusion

**F01 — Scoped identity, not stable VIDs.** Preserve canonical pairs and permute input rows. If canonical equality is lost within a fixed mapping, even the restricted identity model is falsified; if VIDs remain unchanged only on one order, no cross-order invariant follows. P09 falsified the stronger VID claim; `test_identity` supports scoped lookup and persistence. Long-key ABI equality is separately falsified by P11.

**F02 — Logical abstraction is conditional, not arbitrary layout independence.** Build equivalent graphs under genuine src/dst layouts and repartitionings, translate canonical identities, and compare complete edge multisets and query results. A semantic membership difference under correctly constructed equivalent storage falsifies the abstraction; sequence differences only falsify canonical ordering. Fresh ABI query tests support the bounded two-layout case. The original read-domain fixture demonstrates that metadata relabelling alone is invalid. Complete repartitioning equivalence remains unqualified.

**F03 — Reads compose into different result algebras.** Use parallel tags, self-loops, cycles, gap VIDs, and callback-stop requests. Duplicate neighbor rows do not falsify incidence semantics; duplicated BFS visits or incorrect depth would. P03–P05 falsify global-stop/set assumptions. Fresh traversal tests support visited/depth behavior on their fixture. The gap-VID cross-operation case remains source-derived and unexecuted.

**F04 — Tags are local classifications, not universal relations.** Reorder schema declarations, apply a tag map, exceed the byte domain, and query multiple tags under a restricted view. A changed relation interpretation without a corresponding mapping change would falsify a claimed stable semantic tag identity. The tag-map test demonstrates reassignment; P01/P02 falsify implicit scope enforcement. Overflow/collision and parallel-occurrence preservation require separate validation; no lossless external relation mapping is asserted.

**F05 — Determinism is conditional on operation, state, order, and program.** Repeat fixed inputs and compare all results, not only a top-k summary. Vary scheduling/thread count and use order-sensitive arithmetic/programs. Fresh resume repeats already falsify unconditional checkpoint parity at this build. Floating-point, random-walk ordering, shared-program-state, and stateful-program resume cases remain source-derived risk hypotheses, not executed proofs of their exact failure mechanism.

**F06 — Native order is not canonical graph order.** Preserve graph membership while changing physical partition/lane order; compare sequences, BFS tie paths, limited prefixes, and fixed-seed ordinal choices. Sequence changes falsify canonical-order claims even if memberships agree. The maintained contract expressly declines global sorting. P04/P05 establish multiplicity/order-sensitive inputs; no universal permutation-invariance result is claimed.

**F07 — Ordinary visibility is not a pinned snapshot.** Change base data or publish BSP state between executions; separately compare an already materialized cursor with newly acquired reads. A guarantee of one committed snapshot requires consistent vertex/edge acquisition at the same fence, not merely stable cursor rows. P06/P10 already falsify stronger scope interpretations; source paths show no ordinary-read snapshot pin. Concurrent mutation/snapshot acquisition was not executed. Missing-payload behavior is exercised by the controlled fixture variant.

**F08 — BSP is an optional state-publication extension.** Check staged-state isolation, injected-future-run resume, mode differences, premature-stop requests, incomplete staging, and failure between authority/mirror writes. Same-step remote visibility would falsify BSP isolation; differing resumed bytes falsify parity. Fresh mode/store tests support limited mechanisms, while the resume test intermittently fails. Exact-target completeness, stopping, stateful recreation, publication-failure and power-loss guarantees remain open. A required GraphBatch execution for a minimum adjacency read would falsify its extension classification; the independent native/ABI probes exhibit the contrary bypass.

**F09 — Landing ports are adapters.** Supply already-valid native storage without a landing plan; perform identity and graph reads. If those operations require a landing-family concept for their semantic definition, the adapter classification would fail. P01–P13 and existing primitive tests perform the bypass. Package readiness despite an unresolved source endpoint, advisory limits, and metadata-only compatibility repair falsify stronger readiness/reconstruction interpretations, not baseline graph execution. Future domain additions should not have to redefine native incidence.

**F10 — ABI projection is operation-specific and partial.** Compare native/C outputs for identity length, scope, payload, multiplicity, decoration and errors. Any changed equality/membership or unrecoverable required field falsifies faithful projection for that case. P10/P11 supply executed counterexamples. Short-identity/query/traversal tests support narrower fidelity. A complete native query/ABI matrix and nullable/rich-value transport are not established.

**F11 — Version/capability discovery is not universal negotiation.** Try unsupported versions, smaller requests, larger same-version tails, old output allocations in a safe instrumented harness, unavailable job verbs, and capability-advertised but non-callable operations. P12/P13 establish current request/output asymmetry; source and `test_c_api_job` assertions identify reserved/stub behavior. Larger-tail and cross-version memory-safety cases were not executed. Descriptor existence alone would be falsified as an execution guarantee by successful preparation followed by unsupported execution.

**F12 — Self-description is useful but incomplete.** Give a consumer only the matching header and runtime descriptors; require it to infer effective scope, defaults, hard budgets, identity loss, phase-versus-run completion, and complete facts. A correct self-contained discovery trace would falsify the corresponding claimed discovery gap. Current descriptors omit those guarantees or require prose/source knowledge; P10/P11/P13 demonstrate why naïve inference is wrong. Landing stable/full field catalogs answer a narrower adapter question, not universal semantic truth. No autonomous-agent benchmark was run.

## 19. Candidate execution capabilities available to C7a-C

The following are investigation outputs, **not a proposed application contract or an A/B mapping**:

1. Scoped graph-local referencing and optional persistent canonical translation, with explicit remapping and ABI capacity limits.
2. Directed, tag-distinguished adjacency and native payload mechanisms, with explicit duplicate-collapse and representation limits.
3. Logical-direction/readable-partition abstraction under consistent storage construction, but no presumption that saved tag/delivery metadata binds wrapper queries.
4. Incident selection and derived neighbor/BFS/path operations with family-specific membership, ordering, bounds, and missing-data behavior.
5. Optional BSP state computation and publication mechanisms, with resume determinism, complete program-state recovery, and broader concurrency/failure properties still unqualified.
6. A useful fixed-shape C read projection and separate programmable compute ABI; richer native operations and restricted-domain execution are not universally projected.
7. Adapter catalogs, reconstruction, projection, and audit records as facilities beside the baseline, carrying their own evidentiary limits.

C7a-C can now test whether independently established source distinctions survive these actual mechanisms. No source entity, relation, evidence ID, confidence, or snapshot is assigned a native encoding here. In particular, no `source ID → vid_t`, `relation → edge_tag_t`, or `source snapshot → StorageView/iteration` identity is presumed.

## 20. Unresolved architectural judgments

- **How much of B2 is required for a particular semantic workload?** The baseline obligation is preservation of distinctions, not mandatory properties or multigraphs. Native adjacency's limited multiplicity may be sufficient for some operations and insufficient for others. Only C7a-C may resolve the source-specific case.
- **What observation boundary is acceptable?** Static, exclusively managed base storage may support deterministic bounded operations without MVCC. Concurrent mutation or mixed BSP/base reads require stronger evidence. This report does not choose a product consistency contract.
- **Can the current ABI be used without identity/domain loss for the intended subset?** Small identities and full-coverage topology reads are plausible bounded candidates. The safe subset must be proved, not inferred from descriptors.
- **What explains the intermittent resume mismatch?** It is reproduced but not closed. A first pass, a majority of passes, and intact vertex equality do not qualify edge-state resume. Investigation/fix authority is separate from this discovery task.
- **Which richer facilities are worth adopting later?** Whole-graph iteration, typed property/temporal access, durable result materialization, and adapter evidence may be valuable. None becomes baseline merely because it exists or is expensive to remove from this implementation.
- **What is semantically justified inference?** Current graph queries compute derived views; programmable callbacks can implement algorithms or heuristics. Neither entails domain soundness or supplies a general proof theory. Semantic entailment, model reasoning, authorization, memory, and research semantics remain separate architectural responsibilities.

The minimum invariant model survives the falsification exercise as a small set of semantic obligations. **The stronger claim that current `gfs_l0` plus its ABI already satisfies those obligations universally does not.** That distinction is the principal result for the next investigation.

### Table 1 — Minimum invariant algebra

| Concept | Why Semantically Necessary | Native Evidence | Stable? | Falsification |
|---|---|---|---|---|
| Scoped referential identity | Incidence and attribution need unambiguous equality | VID; optional IdentityResolver, §1 | Fixed mapping yes; cross-materialization/ABI qualified | F01; P09/P11 |
| Distinguishable directed facts and relevant values | Losing distinctions changes the executed question | Adjacency, schema/tag maps, payload paths, §2 | Restricted realization, not arbitrary fact preservation | F04/F10 |
| Explicit observation scope/visibility | Absence and repeatability need a defined universe | Read domain; separate BSP fences, §3 | Partial enforcement; no ordinary snapshot pin | F02/F07; P01/P10 |
| Deterministic selection/composition and outcomes | Execution needs defined membership/order/bounds/errors | Incident reads; shared query kernels, §4 | Established narrow operations; broader claims qualified | F03/F05/F06 |

### Table 2 — Layer classification

| Capability | BASELINE | EXTENSION | ADAPTER / DOMAIN | TRANSPORT / IMPLEMENTATION | Reason |
|---|---|---|---|---|---|
| Scoped equality; preservation of relevant fact distinctions | Yes | — | — | — | Minimum semantic obligations, not one encoding |
| Explicit visible universe and deterministic read composition | Yes | — | — | — | Required interpretation of results |
| Canonical catalog attachment/translation realization | — | Yes | — | — | Adds external addressing; particular catalog not mandatory |
| Advanced path/temporal/property computation | — | Yes | — | — | Adds operations to restricted baseline |
| BSP iterative state/publication | — | Yes | — | — | Optional computation semantics |
| Artifact fingerprint/history tracking | — | Yes | — | — | Retains workflow evidence, not universal proof |
| Ingestion normalization and domain landing plans | — | — | Yes | — | Converts source/assets into native inputs |
| Domain export joins, stable/full views, compatibility repair | — | — | Yes | — | Scenario-specific reconstruction/projection |
| Dense VIDs, byte tags, partition manifests/indexes | — | — | — | Yes | Current representation of higher obligations |
| Hub queues, LSM tokens, double-buffer slots | — | — | — | Yes | Realize optional execution contracts |
| ABI handles, cursors, descriptors, capacities, job stubs | — | — | — | Yes | Exposure/inspection/lifecycle, not fact ontology |

### Table 3 — Primitive versus derived

| Operation | Native Primitive | Deterministic Composition | Convenience Surface | Implementation Detail | Evidence |
|---|---|---|---|---|---|
| Identity resolver lookup | Yes | — | — | — | §1; `test_identity` |
| Base incident-edge/payload enumeration | Yes | — | — | — | §4; `test_db0_primitives` |
| Logical direction; BOTH | — | Yes | — | — | Orientation adapter; P04 |
| Neighbor vertices; exact edge; degree | — | Yes | — | — | Projection/selection/counting, §4 |
| BFS, reachability, shortest/all paths | — | Yes | — | — | Frontier/visited/predecessor kernels |
| Temporal predicates and paths | — | Yes | — | — | Timestamp interpretation + read/search |
| BSP state transition/publication | Yes, within extension | — | — | — | §5; not a baseline primitive |
| Named prepared/CLI/domain query entrypoints | — | — | Yes | — | Packaging, §§9/11 |
| A/B index layout, shard routing, cursor advancement | — | — | — | Yes | Physical access/transport, §§3/10 |

### Table 4 — Native → ABI projection

| Native Concept | ABI Surface | Direct / Composed / Metadata / Partial / Missing | Semantic Loss | Maturity |
|---|---|---|---|---|
| Canonical identity ↔ VID | Forward/reverse lookup; canonical cells | Partial | Fixed output pairs can collapse distinct identities | Stable short path; broader fidelity transitional |
| Vertex presence versus placement | Presence struct | Direct | Gap-root cross-operation consistency unqualified | Stable bounded presence |
| Directed tagged incidence | Neighbor-edge cursor | Direct | Only fixed topology fields; no payload/occurrence proof | Stable narrow projection |
| Neighbor/BFS derived views | Vertex/traversal cursors | Direct | Eager rows; no global resource bound/snapshot | Stable narrow families |
| Exact edge/degree/bounded search over known seeds | Filter/count/compose cursors | Composed | Inherits incidence and multi-call visibility limits | Conditional |
| Saved view/delivery/coordinator | State summaries | Metadata | Description is not the executed query scope | Stable summary; enforcement absent |
| Caller-bound read scope or snapshot | No sufficient query binding | Missing | Full-coverage rebuild; no pin | Missing |
| Rich properties, native temporal/path/result algebra | Narrow public cells/statements | Partial | Richer kernels/types not generally projected | Internal evolving; public narrow |
| GraphBatch program execution | Separate plugin hooks/loader | Partial | Not generic job execution; lane/state/resume limits | Transitional |
| Landing inspection/export/reconstruction | Context adapter operations | Partial | Bounded strings/JSON; reuse API gap; outcome != OK | Established adapter, qualified |
| General rule entailment/proof algebra | No established native or ABI contract | Missing | Cannot infer from graph/program metadata | Unknown/not established |

### Table 5 — Agent reconstructability

| Question an Unfamiliar Agent Must Answer | Current Discovery Surface | Fully / Partially / Not Discoverable | External Knowledge Required |
|---|---|---|---|
| What narrow statement/parameter kinds exist? | Statement/parameter descriptors | Fully, within that schema | Matching ABI binding/header |
| What capabilities can I actually execute? | Capability bits + support descriptors | Partially | Native-vs-C scope; deferred failures/stubs |
| What identity space am I using? | Identity state/catalog | Partially | Namespace ownership, normalization, capacity/fidelity |
| What graph/view will this query observe? | Graph path + saved-view summary | Partially | Full-coverage query construction; no saved-view binding |
| What operations are admissible? | Parameter kinds/requiredness/support | Partially | Defaults, ranges, wildcard, data health, runtime guards |
| What projection modes exist? | Decoration enums; adapter catalogs | Partially | Generic-vs-fixed rows; private query capabilities |
| Which fields are stable or advisory? | Adapter field/policy descriptors | Partially | Catalog meaning, not truth/semantic invariance |
| What hard limits must I obey? | Header capacities; depth; recommendations | Partially | Eager memory, truncation, advisory-vs-enforced bounds |
| Is the result complete and snapshot-consistent? | No general certificate/pin | Not discoverable as a guarantee | Effective visibility and external exclusivity assumptions |
| Which operation contract governs ordering/failure? | Row kinds, statuses, program metadata | Partially | Header/maintained docs; source-level gaps |
| What version negotiation is supported? | ABI constant and struct version/size | Partially | Request checks; output-capacity asymmetry; loader rules |
| Is arbitrary inference/resume semantically justified? | Program/audit descriptors only | Not discoverable as a guarantee | Program proof, source evidence, unresolved qualification |
