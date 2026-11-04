# Stage C: spatial queries, dependency updates and coverage diagnosis

Authorized 2026-11-04 after Stage B. The subsequent owner instruction makes
diagnosing loss of original T0–T5 coverage a priority during this development.
T04 coverage repair remains deferred. No treatment, admission, crop, permission,
clearance, source-family or native export rule is changed in this slice.

Evidence directory:
`out/lacie_work/evidence/stage_c_c03_spatial_20261104T043912Z/`.
Its final report and receipt distinguish performance, functional parity,
historical coverage differences and custody; none substitutes for another.

## Implemented execution service

`src/stage_abi/spatial_queries.py` returns conservative, lexically ordered source
IDs matching the AABB candidates of a full rebuilt STRtree. Full engineering
identities are retained. Exact intersection, contact, distance, clearance,
permission and treatment decisions remain with their existing callers.

- One immutable base tree plus a bounded changed/deleted overlay. An updated
  object masks its old base entry; its new bounds may be anywhere. There is no
  assumed maximum growth displacement. The overlay rebuilds when necessary.
- A bounded LRU stores query envelopes and ordered member geometry versions.
  Reverse dependencies invalidate former neighbors. Old **and** new bounds
  also invalidate intersecting query footprints, including empty neighborhoods;
  reverse edges alone cannot discover a newly entering object.
- Deletion, insertion, same-bounds geometry changes and rejected-trial rollback
  all use the same update path. Unaffected neighborhoods remain reusable.
- Every hit hashes complete ordered membership, envelope and context. Compact
  SHA-256 member tokens bind each full source ID and geometry version. Their
  bindings are revalidated before a verdict, along with all original Stage B
  geometry/artifact checks. No cached policy verdict or changed tolerance.
- T05's frozen predecessor lookup uses this service. It still runs exact
  `intersects`, every ordered foreign/accepted-patch witness, complete barriers,
  all bounded attempts, full simultaneous checks and complete ordered assembly.
  A fresh geometry memo remains mandatory for verification.

The mutable update API is qualified by controls and a retained-geometry diagnostic
with actual C03 additions, removals and rollback. T05's source snapshot is immutable
within an operation; this slice does **not** replace its complete accepted-patch
checks with incremental verdicts. There is no cross-stage treatment scheduler,
general policy-proof reuse or incremental native export claim.

Retention budgets: 32 MiB estimated index metadata, 4 MiB estimated query/dependency
payload, 1,024 cached neighborhoods and 128 changed overlay IDs. Geometry references
share the existing 192 MiB snapshot; operation geometry memo remains 32 MiB. Zero
query budget means fresh queries, never omitted checks. These are retention
estimates, not a hard process-RSS or transient GEOS allocation limit.

## Benchmark boundary

Three fresh alternating frozen-Stage-B/Stage-C process pairs measure first and
resident run+verification time and peak RSS. Separate profiles are excluded from
medians. Compare retained Stage B medians as well. Exact parity includes decisions,
ordered witnesses, WKB, attachments and output content; only new implementation
and plan lineage may differ. All 70 immutable assets are checked before each run.

The spatial diagnostic compares 131 actual-geometry transitions and 13,596 queries
over 17,855 source contributions with full index rebuilding. It is an index
benchmark, not a faster full T05 or fresh native qualification claim. No new
copper is produced. The original protocol pins a 10% dynamic-query improvement
target and at most 5% full-pair/RSS regression against fresh Stage B.

The first candidate failed the dynamic target. Its source, measurements, profile,
failed target and test log remain retained. The refinement uses compact member
digests instead of repeatedly serializing long IDs through the general JSON
validator. The checksum, complete membership validation and targets remain.
`refinement_v3/` contains wholly fresh reference/candidate repetitions.

## Coverage is a separate obligation

The source-bound audit is `tools/c03_stage_coverage_audit.py`. It maps the earlier
C03 T01/T02 records by exact source IDs and aliases, compares their stored geometry
with the retained native stage models, joins T04's complete-parent diagnosis and
retains T03/T05 evidence. Detailed findings are in
`C03_STAGE_C_COVERAGE_FINDINGS.md` and the evidence directory.

Each future engineering checkpoint must distinguish:

1. Source custody and complete source occurrence accounting.
2. Intended treatment targets, independent of the generator's admitted list.
3. Admission and explicit per-target reasons for any change from that inventory.
4. Positive effect, stage-specific extent/shape obligations and complete groups
   or attachments; a larger total count or any nonzero addition is insufficient.
5. Preservation of earlier stages and correspondence in actual native exports.

Reconstruction against a newly narrowed plan can pass while original design
coverage is lost. A changed policy or family requires an explicit reconciliation;
it must not disappear into a `KEEP` count. Spatial/dependency parity against Stage
B proves preservation of Stage B behavior, not restoration of the old C03 scope.

The current audit leaves coverage reconciliation open, particularly T01/T02/T04.
It does not authorize relaxing a safety rule, substituting historical copper,
splitting whole paths/groups, broadening the crop or changing old acceptance.

## Custody and status

Stage A's two changed existing `.DS_Store` files remain a strict custody **FAIL**;
writer **NOT_ESTABLISHED**, without deletion, restoration, exclusion or waiver.
At Stage C entry all 2,521 Stage B sealed output hashes match. An additional
unsealed Stage B `.DS_Store` is recorded separately and preserved from entry.
Start-to-finish custody checks do not repair historical findings.

Retained and failed jobs are not resumed or resealed. No real managed C03 job,
whole-board run, new native export, commit, push or subsequent stage is implied.
Owner **PENDING_USER**; independent **NOT_RUN: CHANNEL_UNAVAILABLE**;
electrical/manufacturing **NOT_ESTABLISHED**.
