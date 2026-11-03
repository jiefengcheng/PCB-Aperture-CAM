# U03 first-time source unions: exact bounded lookahead

Authorized 2026-11-03: address first-time source unions, preserve every clearance
rule and final check, benchmark retained cases before another real board run.

## Identical geometry operations, concurrent execution

`SourceUnionWidthScene` extends the existing dependency checker with up to three
project-local worker threads. The coordinator continues the existing ordered
clearance loop while workers construct upcoming independent source unions.
The source R-tree, query windows, complete ordered operand lists, GEOS unary
union, cache encoding and visibility subtraction are unchanged. No sources are
removed, clipped, simplified, rounded or merged in a different tree/order.

Lookahead covers at most eight upcoming neighbors in the current route's exact
finite-neighbor query. It checks the existing source-contact port and actual
checked-copper emptiness before scheduling a union. New candidate copper never
hides a neighbor. Known current visibility and existing geometry/union cache hits
are skipped. Union keys deduplicate identical work across source objects.
All cache, port, graph, proof, acceptance and report mutations stay on the
coordinator. Workers only read immutable source geometry and return a union.

A worker result certificate binds the complete source/policy/group model, the
ordered original R-tree indices, exact WKB hash and GEOS precision model. The
coordinator validates it before use. Corruption or a failed unused computation
raises; it is not hidden by an eviction or silently recomputed. Valid immutable
results are verified once, with their binding/value fields checked on reuse.
Consumed values enter the existing serial union-cache path in the original
request order, with unchanged retention/compression/eviction policy.

## Bounded resources and lifecycle

Defaults: three worker threads, at most four pending tasks, eight-neighbor
lookahead, and 128 MiB of estimated pending input work (64 bytes per source
coordinate plus ordered-key overhead). Small unions below 4,096 input coordinates
remain serial. The estimate is not a hard bound on native GEOS allocation or
intersection-result size. Original union, geometry and proof budgets remain.
Zero workers/budget/lookahead disables prefetch. Thread count is capped at three;
no global executor, environment, settings or dependency installation is needed.

Unused completed tasks can be evicted between route/trial epochs. Pending tasks
for the current ordered route stay available for consumption. All unused
certificates/errors are checked. Full materialization drains and closes the
executor, then permanently disables lookahead for that checker. The original
PreparedWidthScene nominal/envelope check executes; final-neighbor upper proofs
remain serial too. A fresh source reconstruction verifier begins with full
checks and therefore never starts workers. The shared solver, constructor,
clearance contract, final verifier, exports/reparse and negative controls remain
byte-identical.

## Rejected pruning experiments

Exact-intersection pruning and single-cover shortcuts are mathematically valid
set reductions, but changing a GEOS overlay's operand set changed historical
slivers and distance witnesses. Even component-based numerical fallbacks did not
preserve all retained gaps. Those prototypes and failures remain on LaCie and
are not used by the implemented class. No benchmark tolerance was widened to
accept them. The shipped implementation keeps the original complete operands.

## Reproduction and timing scope

Use tools/Run_PCB_Tests.command for the focused source-union/dependency/geometry
families. Tests cover exact threaded versus serial report/WKB/precision parity,
failed-trial rollback, deduplication, bounded/zero budgets, corrupt certificates,
unused worker failures, and final closure without workers.

`tools/benchmark_u03_source_union.py --case <retained native directory>
--output <new LaCie JSON>` compares bounded prefix/largest/middle windows,
cold and warm. The read-only store rejects retained writes; no native route or
export starts. Passing authority for seeded windows is explicitly retained
ledger evidence. Every geometry field, exact gap, verdict and coverage count
must match; only seeded-window passing-chain hashes are excluded.

`--full-solver` is for bounded C03, not whole-board solver replay. Fresh
reference/optimized/optimized/reference runs require all 1,486 complete check
hashes, the entire solver ledger/decisions/scales and full final nominal/envelope
payloads to match retained evidence. Native construction caches are cleared per
run. Hashes are never copied from old reports into new results.

`--baseline-results` may pair fresh optimized windows with the previous slice's
identical retained-window dependency timings. Case identity, dependency source
hash and retained report parity are checked and the earlier file SHA-256 is
recorded. Reused reference timings are clearly labelled, not represented as
fresh paired executions.

Timing separates setup, assembly and checking. Window totals include waiting for
pending unions at each cold/warm boundary; closing cannot hide speculative work.
Parity comparison and retained report I/O are excluded. Native window geometry is
preconstructed identically. Source-union callback timing measures coordinator
calls/waiting, not aggregate worker CPU. Cold/warm diagnostic histories are not
a whole-run cache distribution, and bounded samples cannot establish whole-command
savings. All evidence stays additive under out/lacie_work. Owner PENDING_USER;
independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.
