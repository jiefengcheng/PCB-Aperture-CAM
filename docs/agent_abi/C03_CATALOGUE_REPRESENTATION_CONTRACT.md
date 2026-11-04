# Stage A — C03 U04→T05 catalogue and representation contract

Authorized on 2026-11-04: establish the contract and baseline measurements,
preserve existing work and checks, and report findings before Stage B.

This is an additive, read-only projection of the exact corrected C03 case.
It does not replace a production catalogue, change a treatment module, or
qualify a shared execution service. Stage B is **NOT_STARTED**.

## Bound case and acceptance

- U04: `20261103T121121Z-1068388351fb4a01b7b855bcd930c489`; native scene and
  actual saved KiCad are bound by the corrected U05's `U05_START.json`.
- U05: `20261103T180142Z-723fa543c2f7415ab2f0d36c6e4cb76a`.
- Original source SHA-256:
  `850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0`.
- Retained producer fingerprint:
  `9ee62cccd282fa8897d61ddcb8e9afbbca109904238bf749af56cf500d9ea432`.
- The historical C03 sequence supplies source-bound functional witnesses;
  construction uses the current native U04. Historical shape identity is not
  asserted. The four blocked nonreference contacts and eleven outside-write
  contacts remain explicit.

Owner remains **PENDING_USER**; independent **NOT_RUN: CHANNEL_UNAVAILABLE**;
electrical/manufacturing **NOT_ESTABLISHED**. Retained machine PASS is not owner
acceptance or independent review. The 43 U04 gates remain retained-verified.

The machine-readable contract is
[`contracts/catalogue/c03_u04_t05_v1.json`](../../contracts/catalogue/c03_u04_t05_v1.json).
The existing adopted [attachment rules](U05_ATTACHMENT_RULES.md), numerical
policies and operational contracts remain authoritative for treatment.

## One catalogue, three linked representations

“One catalogue” means a common revision/identity contract across stored views.
It does not require one table, duplicate geometry in every record, or immediate
migration of the existing SQLite catalogue and Stage ABI stores.

| Representation | Records in this slice | Current authority and retained links |
|---|---|---|
| Source | Original staged native/Gerber bytes; 17,849 native occurrences with exact byte spans, source-slice hashes, primitive metadata, layer membership and nominal geometry references | `data_board/source_manifest.json`, `source_wkb/`, retained intake and original files. Original bytes preserve parameters, Gerber apertures, command order, polarity and transforms. No source normalization or rewrite. |
| Engineering | 7,427 complete paths, T04's 14 admitted width groups, lands and aliases, six derived inclusive lands, 108 local T05 cluster views, 180 attachment obligations and declared context contacts | T04 inspection/plan; exact U04 native contribution scene; T05 qualification artifacts, plan, candidate and actual-export attachment ledger. Physical/parallel relations carry their original qualification; no electrical intent is inferred. |
| Execution | Original/current WKB references, native frame and units, derived construction parameters, spatial-index ownership and reusable measurement/dependency keys | Existing Stage ABI geometry artifacts and U03/U04/U05 adapters. Execution structures are rebuildable; their persisted bytes are not source truth or acceptance. |

Native geometry uses `native-kicad-mm` with KiCad Y orientation. Exported Gerber
uses X=x, Y=−y in this pinned route. Display transforms are separate and retained
by the existing viewer; they cannot change a geometry/predicate cache key.

The source occurrence key is `(source revision SHA-256, byte start, byte end)`.
Native UUID, path ID, T05 cluster ID, alias representative and graph/storage IDs
are different identities. Reopening a representation must verify both its
revision and its source membership.

## Ownership and relationships

1. Every original source occurrence belongs to exactly one physical contribution
   record. An unchanged source is still present. A derived inclusive land names
   its original members and their original-contact support.
2. A T05 `trace` cluster is a local engineering view, with **empty native source
   ownership**. It references its selected source contributors and its complete
   parent path. Several clusters may reference the same complete path. This grants
   no permission to split that path's uniform-width policy or add copper twice.
3. An index may contain smaller fragments, but each fragment retains the complete
   path/group identity and current geometry version. Fragment-local clearance is
   not a substitute for complete route/group obligations.
4. Alias sets must resolve and retain matching original/current geometry. Covered
   lands stay in the frozen land set, radius, window and verification denominator.
5. Contact, electrical intent, spatial influence and operation permission remain
   separate relation types. Existing parallel relations are source-qualified
   selection evidence, not clearance PASS or electrical net membership.
6. This projection does not invent a full-board physical-component graph. Missing
   component or intent materializations remain explicit gaps, not guessed links.

## Independent permissions and coverage

T04 alone controls width changes to admitted complete paths/groups, with its
existing factors, scalar rules and complete-path crop admission. T04 `KEEP` is
not a T05 eligibility verdict.

T05 independently evaluates qualified source attachments and may only add copper
inside the approved writable region. All existing U04 nodes/contributions remain
protected. Preserve-existing-copper and no-addition-space are distinct rights.
Only `J-966bf7ea0116147b` has the existing exact hash-pinned scope extension.

The independent C03 denominator is 97 reference clusters, including 85 positive
clusters and 162 required attachments. The current inventory contains 108 clusters
and 180 attachment records. It also retains eleven outside-write contacts as
context. Four nonreference attachments are blocked and are not counted as covered.
Removing a required attachment from both generator and result must still fail
the independent denominator check.

`TREATED_VERIFIED` requires the full approved extent in effective actual export
copper. `ALREADY_SATISFIED_VERIFIED` requires the predecessor to meet the same
positive obligation before barrier clipping. Neither a nonzero added area nor a
cluster-level `GROWN` establishes complete attachment coverage.

## Reuse and invalidation contract for subsequent work

| Reusable item | Required binding | Recompute/reject conditions |
|---|---|---|
| Geometry | Operand bytes, constructor/version, parameters, frame/units, numerical model | Any changed binding; no identity-only lookup or unverified stat reuse |
| Measurement | Ordered operand geometry versions, metric/predicate, frame/units and numerical model | Changed operand/predicate; centerline distance cannot replace copper-surface distance |
| Policy decision | Measurement binding, stage policy, complete memberships, permissions, neighbor set/versions, scene and search order | Changed policy/membership/permissions/context; changed decisions do not imply geometry changed |
| Spatial neighborhood | Conservative permitted growth envelope or current old/new bounds; complete owner/group identities | Discover newly entering interactions; reverse dependency edges alone are insufficient |
| Evidence/checkpoint | Immutable artifact bytes, inputs, implementation, scope, process and verdict | Missing/corrupted/stale evidence rejects; historical FAIL/NOT_RUN stays unchanged |

Rejected trials must leave accepted state and its bindings intact. Rollback still
invalidates any incompatible trial dependencies. Bounded eviction permits later
recomputation; it cannot remove a required check. Persistent caches and resident
working sets are separate lifecycle choices.

The fixed-base-plus-changed-overlay index remains a hypothesis to benchmark.
Existing U03 packed-envelope indexing is scoped implementation evidence, not
proof that a new cross-stage overlay service has already been adopted.

## Closure and baseline protocol

Full reconstruction, including KEEP and all bounded attempts; simultaneous final
scene checking; native write/reread; actual nine-layer export/reparse; corruption
controls; and both fresh process-bound machine evaluations remain mandatory.
No clearance floor, numerical bound, coverage denominator or gate is relaxed.

Stage A runs the unchanged `CoverageAdapter.run` and `.verify` over the retained
plan/scene in a new diagnostic store. Every result must equal the retained complete
candidate/check, including decisions, geometry references and attachment outcomes.
It neither starts nor resumes an operator job and makes no native CLI call.

The baseline uses three fresh processes, each with two successive run/verify
passes. The first run initializes its context; verification then shares that
context. The second pair measures resident-context behavior. OS/filesystem caches
are not flushed. A fourth, separately profiled process supplies call counts and
component costs and is excluded from latency medians. Process peak RSS includes
input load; it is not a per-operation allocation delta. Diagnostic read counters
and the extra retained lookup layer contribute overhead.

Measure geometry decoding/construction, index builds/queries, detailed predicates,
canonical/WKB serialization, artifact read/hash/put bytes and time, process memory,
and complete diagnostic pair time. Cumulative profiler times overlap. Keep this
baseline separate from the retained 894.516-second managed U05 continuation and
from any future full pipeline timing. Stage A claims **zero treatment changes**,
not a new speedup.

The detailed findings and receipts are under
[`out/lacie_work/evidence/stage_a_c03_catalogue_20261104T022133Z/`](../../out/lacie_work/evidence/stage_a_c03_catalogue_20261104T022133Z/).
Reproduction commands are recorded there. No commit, push, new qualification,
shared service extraction or Stage B follows automatically from this contract.
