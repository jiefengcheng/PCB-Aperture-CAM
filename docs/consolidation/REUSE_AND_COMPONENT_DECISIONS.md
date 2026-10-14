# Reuse and component decisions

This matrix distinguishes upstream code reuse from newly maintained PCB code.
It does not claim a wholesale pcb_Z or gfs merger.

| Component | Decision | Actual responsibility and boundary |
|---|---|---|
| Immutable artifact/revision catalog | ADOPT | PCB-owned CAS plus SQLite revision/object/relation records; exact source bytes and locators remain authoritative |
| SQLite identity/range queries | KEEP_REFERENCE | Revision-scoped keys, indexed ordered lookup and bounded queries; no UUID-global identity |
| Rtree/libspatialindex | KEEP_REFERENCE | Native broad-phase candidates by layer/snapshot, conservative distance envelopes; exact predicates remain separate |
| Shapely/GEOS | KEEP_REFERENCE | Qualified geometry/contact/distance operations; display simplification never enters acceptance |
| Pinned gfs DB0 typed reads | SHADOW_ONLY | Actual C++ materializations, local VID/tag translations, incoming/outgoing reads and parity receipts; no acceptance or edit authority |
| Custom C++ B-tree/R-tree | DEFER | No separately usable implementation established in the admitted DB0 source snapshot; no mock replacement or performance claim |
| Frozen V2 executor and validators | KEEP_REFERENCE | Existing bounded operation, pinned policy and independent exported-result acceptance remain unchanged |
| Legacy general SQLite import/export | DEFER | UUID-only and empty-selection ambiguities are not adopted; maintained revision-safe catalog/selection replaces those responsibilities |
| Native pcbnew and grouping-save paths | DEFER | Not executed by this consolidation; no full legacy integration claim |

The existing V2 pcb_Z adapter retains its pinned expression/helper and grouping
reuse. New native inventory uses maintained sexpdata decoding plus exact byte
locators; it separately indexes nested pads and records unsupported semantics.
The spatial adapter corrects positive-distance candidate recall and recomputes
components after removals. Catalog selection defines explicit empty/all,
deduplication, missing/ambiguous-reference errors, dependencies and read-only
context. General KiCad reassembly is explicitly unsupported; selections are
preserved-source diagnostic bundles.

The graph wrapper calls the admitted DB0 API from a PCB-owned executable.
Full source occurrence identities stay in a sidecar mapping; numeric VIDs and
relation tags are materialization-local. Deduplicated adjacency does not erase
independent proof occurrences retained in the catalog. Each materialization
binds revision, layer, relation type, input manifest and executable hash.
Isolated child-process bounds are not shared-core callback cancellation,
concurrent snapshot semantics or lifetime guarantees.

Native source is pinned by `contracts/native_gfs_source_pin.json`; the exact
compiled copy, staged wrapper, compiler/link arguments and input/output hashes
are retained in each build receipt. The admitted source was dirty. Its observed
HEAD alone is insufficient provenance; content hashes bind the build. License
qualification of the admitted native snapshot remains NOT_ESTABLISHED, so this
is local evaluation rather than redistribution approval.

Measured native queries include process startup, manifest/proof validation and
mapping costs. A fast C++ traversal does not establish an end-to-end speedup.
The benchmark report separates reference query time, native process/API time,
isolated-child memory, decoding, geometry/index construction, persistence,
serialization and artifact footprint. Warm caches are explicit; OS cache
flushing, production scaling and GPU rendering performance are not established.

Publication establishes application-level consistency with transactions and
staged manifest/directory publication. Failure tests retain the previously
published catalog/index. Full power-loss durability and atomic publication
across unrelated stores are not established.
