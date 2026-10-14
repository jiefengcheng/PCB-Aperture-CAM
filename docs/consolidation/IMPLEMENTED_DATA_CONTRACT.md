# Implemented consolidation data contract

The supplied DASHBOARD_AND_DATA_CONTRACT.md remains the original proposal.
This document identifies the maintained implementation and its boundaries.

| Responsibility | Maintained implementation | Binding |
|---|---|---|
| Exact source occurrence | src/source_locators.py | source SHA-256 plus original byte start/end; UUID is metadata |
| Native inventory | src/native_inventory.py | extraction version, source, layers, parent occurrence, geometry or typed unsupported reason |
| Persistent revision | src/revision_catalog.py | content-addressed payloads, revision+occurrence keys, foreign keys, manifest/table integrity |
| Query/selection | src/catalog_selection.py | explicit selectors, ordered paging, row/work/byte budgets, recorded dependencies and context |
| Spatial/context relations | src/spatial_context.py | source/layer/kernel snapshot, Rtree candidates, exact GEOS predicate, proof occurrences |
| Native graph materialization | src/native_graph_adapter.py | local VID/tag mapping, source revision/layer/type, manifests and executable hash |
| Pipeline receipts | tools/consolidation_pipeline.py | actual stage inputs/outputs, counts, omissions, timings and implementation digests |
| Existing operation admission | tools/catalog_v2_run.py | persisted source/context matched to frozen contract, unchanged executor and validator sources |
| Portable dashboard | src/pipeline_scene.py and web/pipeline_views.js | verified receipt artifacts, exact source bytes, shared object/witness/case mappings |
| Replay projection | web/replay_model.js | selected event's retained snapshot or explicit unavailable state |
| Finding records | src/evidence_records.py | original report hash plus exact RFC 6901 pointer; full original report retained |

All coordinates are millimetres. Native shape geometry is nominal source
geometry; actual exported Gerber copper and frozen acceptance are separate.
Layer instances, source objects, computed physical components and native
PCB_GROUP labels have different denominators. Unsupported semantics remain
source-located records. A complete query over available geometry does not
establish complete engineering coverage when unsupported shapes remain.

Bounds area and filled area are distinct square-millimetre fields. Aspect is
width/height with an explicit degenerate status. Curved native geometry carries
its approximation budget; display paths simplify separately at 0.001 mm.
Snapshot identity binds geometry/predicate code and kernel versions.

A zero-contact physical relation does not assert intended connectivity.
Within-distance queries expand envelopes conservatively and then apply exact
distance filtering; proximity does not merge physical components. Changed
geometry recomputes components, including splits. Operation permissions come
only from the frozen contract. Container dependencies and physical neighbors
never gain write authority merely by being selected.

Catalog query and selection results distinguish COMPLETE, truncation,
cancellation, stale/missing source, unsupported geometry and errors. Explicit
empty selection is empty; all must be requested. Missing, ambiguous and cyclic
references reject. Returned public records cannot mutate the private verified
cache. Reopen and failed-import tests exercise revision safety and preservation
of the previous publication.

The graph adapter normalizes full identity sets for comparison; native traversal
order is not semantic. A deduplicated adjacency has separately retained proof
occurrences. Outside materialization, missing recorded sample, unavailable
backend and empty-complete are distinct states. Materialization manifests are
verified before and after reads. Bounded child processes contain evaluation;
no shared-core cancellation or concurrent read snapshot guarantee is claimed.

The visual checksum verifies the embedded snapshot. The standalone verifier
checks retained files, original evidence bindings and exact source bytes.
Build source digest, historical execution revision/dirty metadata and eventual
sealing commit are separate provenance facts. A sealing receipt must not
rewrite historical build metadata or imply a fresh native execution.
