# Native qualification boundary

The actual admitted implementation is gfs L0 DB0, accessed through a small
PCB-owned C++ executable (`native/pcb_graph_shadow.cc`). The wrapper uses DB0
build/open and directed ForEachEdgeByAFromShard / ForEachEdgeByB reads, with
`a_vid()`, `b_vid()` and `tag()` accessors. It does not invoke a mock graph,
introduce a shared C ABI, execute upstream build scripts, or modify shared code.

The recorded source HEAD is a5e9a2509f8c3da0c18640f289079ba4bba8a55f and the
source was dirty. Exact content hashes in contracts/native_gfs_source_pin.json,
including the private headers needed by the compiled core, define the admitted
snapshot. The PCB-owned build uses clang++ C++17, -O1 and staged pinned sources.
The build receipt records each compiler invocation, object and linked executable
hash. Tensor-specific gnn sources are excluded because this wrapper uses DB0
reads, not the separate L4 tensor runtime. No source cleanliness or full upstream
test-suite claim follows from a successful PCB wrapper build.

VIDs are bounded numeric materialization-local identities. PCB identities are
complete strings translated through an immutable sidecar; long identities are
not copied into fixed-width native name fields. Relation tags are local numeric
codes; the wrapper rejects out-of-range tags (255) and tests 0/254 boundaries.
No native coordinate conversion is used: geometry and exact predicates remain
with the qualified GEOS/libspatialindex paths.

The wrapper eagerly returns bounded rows and COMPLETE/TRUNCATED markers. Its
process owns the DB0 lifetime and is not reused across requests. The adapter
checks every manifest file and executable before and after reads, binds layer
and relation scope, bounds seeds/results/time, and records query inputs. It does
not claim thread safety, shared-core callback cancellation, concurrent writer
snapshots or stable VIDs across rebuilds. Process timeouts affect only PCB-owned
children; no shared process is terminated.

Reopen, duplicate adjacency/proof separation, wrong revision/layer/type,
corruption, local remapping, numeric bounds, truncation and failure-before-index
publication are exercised by tests/test_native_graph_adapter.py. Actual source
relations are compared against native outgoing identity sets for all admitted
materialized vertices in six dataset/layer scopes. Incoming/outgoing recorded
samples and isolated benchmark probes remain linked to the same materialization.
These checks qualify bounded typed reads, not a universal graph semantic model.

Index failure injection retains the prior published index. Directory/manifest
publication does not establish power-loss durability, full crash recovery or
atomicity across catalog and native files. Duplicate evidence occurrences remain
in the revision catalog and proof sidecar even when adjacency deduplicates them.

No separately callable custom C++ B-tree/R-tree was established in the admitted
DB0 source. Ordered access stays on SQLite; spatial candidates stay on native
libspatialindex through Rtree. These are explicit KEEP_REFERENCE / DEFER
decisions. DB0 is SHADOW_ONLY: actual parity is established in the recorded
scope, but measured process/proof/mapping overhead does not justify promotion.
The admitted native snapshot's license remains NOT_ESTABLISHED; no native
source or binary redistribution is authorized by this local qualification.
