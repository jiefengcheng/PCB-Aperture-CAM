# Stage B — C03 repeated geometry work and bounded memory

Authorized on 2026-11-04 after review of Stage A: implement operation-scoped
geometry reuse, bound retained memory, preserve every check and prior evidence,
benchmark against Stage A, and keep its `.DS_Store` custody finding explicit.

This is the C03 U04→T05 consolidation slice. It introduces reusable computation
through the existing T05 adapter. T01–T04 eligibility, permissions, source paths,
groups, numerical policies and native export code remain unchanged. Stage C is
not started. There is no new whole-board or managed native qualification claim.

## Implemented service

`src/stage_abi/loaded_geometry.py` contains two reusable components:

| Component | Responsibility | Lifetime and binding |
|---|---|---|
| `GeometrySnapshot` | Deduplicate immutable decoded geometry while retaining separate original/current source identities; provide full ordered scene assembly | One source/policy/frame snapshot, bounded by estimated retained geometry bytes. Every access reads and hashes the actual artifact through the unchanged store. |
| `GeometryMemo` | Reuse buffers, differences, intersections, unions and symmetric differences; retain separately typed scalar containment measurements | One operation only. Keys bind the complete context, ordered operand WKB identities and parameters. Result checksums reject altered cache payloads. |

The snapshot is used with the existing qualified Stage ABI scene. It does not
replace source admission, attachment inventory, complete-route/group accounting,
alias qualification or writable-space rules. Current and original maps retain
source identities even when they share an immutable decoded geometry object.

The memo never stores stage PASS/FAIL, clearance acceptance, T04/T05 eligibility,
electrical intent or writable authority. The reused scalar measurement is the
exact emptiness of `foreign.difference(owner)`. The caller still evaluates the
existing source-qualified owner test, every clearance decision and every ordered
witness. Different geometry, context or parameters require a different key.

`spindle_blend` and `check_spindle` accept an optional geometry service. Their
default path preserves the original calculations. T05's coverage adapter opts
into the service; other existing callers keep the default path.

## Memory and integrity

Final default limits are:

- Snapshot: **192 MiB estimated retained geometry**, including map overhead and
  the retained predecessor union. Oversized snapshots fail explicitly.
- Operation memo: **32 MiB estimated retained payload**, at most **8,192 entries**.
  The initial engineering diagnostic used 64 MiB; its result remains retained.
- Weak operand-signature table: at most **32,768 entries**. Signatures do not keep
  otherwise dead operands alive.

Charges include twice serialized WKB bytes plus entry/key overhead. These are
explicit retention estimates, not a hard cap on process RSS, input JSON, temporary
WKB, allocator retention or transient GEOS work. Process peak memory is measured
separately. No OS resource limit or global setting is changed.

LRU eviction and disabled/tiny caches cause recomputation, never omission of a
check. The operation memo is cleared on successful return and on exceptions.
Explicit adapter `close()` releases its retained snapshot. A changed source or
policy replaces the prior snapshot rather than accumulating revisions.

Before a verdict returns, execution checks complete scene/policy metadata, scope
and cache configuration; validates every original/current geometry binding and
unique decoded geometry checksum; and re-reads/hashes every actual artifact
operand. Cache corruption raises a failure instead of silently recomputing it.
The adapter implementation fingerprint includes the new service and its budgets.

## Preserved engineering obligations

- The same complete worklist, source contributors, covered lands, aliases and
  attachment membership remain present. T04 KEEP supplies no T05 eligibility.
- The same four radius scales, 64 buffer quadrants, construction/barrier/hard
  gaps, area thresholds, file uncertainty and single approved boundary exception
  apply.
- Every bounded trial and KEEP decision remains reconstructable. Every required
  attachment retains its full positive extent obligation.
- Full simultaneous final checks still evaluate all relevant objects. Final
  assembly processes every contribution/view in the original order with the
  original union and clipping. No operand pruning or hierarchical substitute
  union is introduced.
- Verification starts a fresh operation memo and independently rebuilds expected
  patches. It revalidates actual artifact bytes before using decoded operands.
  No construction verdict is reused as verification.
- Native write/reread, nine-layer actual export/reparse, polarity guards, corruption
  controls, native gate counts and both fresh machine evaluations remain required.
  This component benchmark does not execute or claim those managed gates.

## Benchmark and evidence

Evidence is additive under
`out/lacie_work/evidence/stage_b_c03_geometry_20261104T030744Z/`.
The reference is a hash-bound copy of Stage A's coverage adapter and original
spindle geometry/check functions, executed with the exact saved scene/policy/plan.
New implementations receive new plan/implementation lineage; retained receipts
are never resealed or promoted.

Parity requires identical decisions, ordered witnesses, before/after WKB refs,
all attachment outcomes, evaluation counts, protected contributions and complete
verification results. A direct output-scene comparison allows only the declared
new implementation/plan lineage. Those checks run outside timing where possible.

The protocol pins 10% improvement targets for complete diagnostic-pair median
time and process high-water RSS against Stage A and a fresh frozen reference.
Three fresh reference/candidate process pairs alternate order. A separate profile
is excluded from timing medians. “Cold” means a new context; OS/filesystem caches
are not flushed, and verification follows construction in the same process.

The first benchmark reduced peak RSS by 9.836% against the fresh reference and
therefore missed its 10% memory target. Its benchmark, source snapshot and samples
remain unchanged. The refinement tightened the memo to 32 MiB and added loaded
binding validation; targets and engineering checks stayed fixed. Three new
candidate repetitions and a new profile are compared with the unaffected,
hash-bound reference samples. This reuse is explicit in the final report.

Use `tools/benchmark_c03_loaded_geometry.py` only for bounded diagnostic replay
in a new LaCie evidence directory with the pinned inputs/reference packet. It is
not an operator command or an authorization to retry an existing native job.

## Custody and acceptance

Stage A's strict custody result remains **FAIL** for two changed existing
`.DS_Store` files. Their writer remains **NOT_ESTABLISHED**. No file is restored,
deleted, excluded or waived. Stage B checks preservation from its captured
starting state separately; any such PASS does not repair the historical failure.

Owner remains **PENDING_USER**; independent **NOT_RUN: CHANNEL_UNAVAILABLE**;
electrical/manufacturing **NOT_ESTABLISHED**. Report bounded replay performance
separately from actual native qualification and whole-pipeline runtime. No commit,
push, publication, new index architecture or subsequent stage follows automatically.
