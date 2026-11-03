# U03 dependency graph, geometry reuse and conditional proof certificates

User authorization, 2026-11-03: implement R-tree-backed dependencies, reusable
geometry/proof certificates and local invalidation; preserve clearance rules and
final checks; benchmark retained cases before another real whole-board run.

`DependencyWidthScene` extends the existing U03 incremental checker. Its source
binding includes the raw source SHA-256 supplied by the native caller, geometry
family, route-to-group membership, complete original object IDs/WKB hashes and
widths, and the unchanged clearance contract. Caches are private to one model;
retained benchmark certificates are examples, never native input or acceptance.

## Index and dependency discovery

A packed Shapely/GEOS STRtree indexes immutable conservative maximum AABBs. For
source-offset trace widths 1..1.5, each original trace box expands by .25 of its
original width plus the existing ERROR_MM checking margin and one ERROR_MM of
additional conservative index-only padding. This padding avoids roundoff-driven
fallbacks; it does not change a candidate, query guard or clearance tolerance.
Fixed sources retain
their original boxes. Each query filters these candidates against the actual
version's exact AABBs with inclusive comparisons. This preserves the legacy
neighbor set and sorted witness order, including query-boundary contacts.

Fixed bounds are retained; only changed route bounds are refreshed. Accepted and
trial views reuse the same packed tree. An out-of-frame candidate or unexpected
fixed-object replacement falls back to the complete legacy dynamic index. The
original source STRtree used for copper unions stays untouched, preserving its
operand order and existing floating-point behavior.

The existing symmetric old/new-neighborhood calculation still determines the
affected routes. Reverse proof edges invalidate known consumers when geometry
versions change between successive trials, including failed-trial rollback.
Newly entering neighbors are discovered through the R-tree, not just through
previous graph edges. Every route-proof lookup validates the complete current
query membership and versions; missing graph edges cannot authorize reuse.

## Reusable pieces

Route certificates contain the original result/failure witnesses. Their context
includes the owning route geometry, current neighbor identities/geometry versions,
and visible-geometry tokens. Visibility tokens also distinguish the original
near-epsilon exact-query fallback from an accelerated cached representation.
Certificates carry explicit dependency versions, a source/policy binding, a
context digest, payload bytes and SHA-256. Corruption is rejected, not recomputed
silently. Negative witnesses can be reused only under the same complete context.

Pair certificates bind the actual checked-copper and visible-neighbor WKB hashes.
They retain the exact distance, without rounding or changed thresholds. Checked
port-subtracted copper and source-relative visibility geometry have bounded
multi-version caches, so rollback need not repeat Boolean operations.
Geometry-cache keys are structured tuples, keeping delimiter-containing source
IDs unambiguous. Accepted/trial index views use bounded LRU retention.

An empty checked-copper witness proves that the existing pair predicate's gap is
None, irrespective of neighbor visibility. The implementation retains that exact
predicate result without computing an irrelevant visibility union. Port hashes
and neighbor identity/order remain in the original result. This is a feasibility
certificate, not an independently optimal width or a new clearance exemption.

## Unchanged closure and evidence semantics

The solver, source constructor, widths, tolerances, original-contact ports, pair
predicate, epsilon-boundary exact query/distance fallback, full native
reconstruction, export/reparse and negative controls remain. Default checker
hooks preserve the pre-change reference behavior. Full materialization always
executes the original PreparedWidthScene path and clears proof caches; fresh
verification constructs a new model and independently reconstructs native parts.

ABI check reports retain the same logical checked/carried route counts and
ordered witnesses, whether a route is geometrically recomputed or its exact
certificate is validated. Separate diagnostics expose route/pair proof hits,
geometry hits, invalidations, bounds updates and index fallbacks. They are not
human observations or independent review.

Default additional budgets are 32 MiB for certificate payloads, 64 MiB for
versioned geometry (weighted estimate), 100,000 active reverse edges, and three
index views with bounded query memoization. The existing original-union cache is
separate. Allocation overhead and base geometry are not included in these limits.

## Verification and bounded benchmarks

Run tests with tools/Run_PCB_Tests.command. Focused tests cover exact R-tree query
sets, outside-frame fallback, neighbor insertion/removal, failed trials/rollback,
certificate source/policy binding and corruption, empty-checked witnesses,
budget eviction, full closure, and the existing epsilon-boundary rejection.

`tools/benchmark_u03_dependencies.py --case <retained native directory>
--reference-checker <pre-change checker snapshot> --output <LaCie JSON>` compares
bounded retained prefix/largest-group/middle windows in cold/warm states. Passing
authority for window initialization comes explicitly from retained ledger
evidence; passing-state chain hashes are excluded only for those seeded windows.
All geometry fields, exact gap values, verdicts and coverage counts must match.

The optional --full-solver mode runs reference/dependency/dependency/reference
solver replays and requires every complete check hash, decision/ledger and full
final nominal/envelope check to match retained results. Use that bounded mode on
C03; it must not implicitly start a multi-hour whole-board solver replay.
For final hardening checks, --baseline-results may pair dependency-only reruns
with an earlier exact-case/reference-checker benchmark; the linked result hash
is retained, and reused reference timings are explicitly labelled.
Outputs are additive under out/lacie_work; the store rejects retained writes.

This is implementation/retained-case evidence. No new real whole-board pipeline,
rendering, owner acceptance, independent review or manufacturing approval follows.

## Subsequent first-time union slice

[U03_SOURCE_UNION.md](U03_SOURCE_UNION.md) describes the later bounded concurrent
execution of identical ordered source unions. Pruning prototypes were rejected
because they changed historical numerical witnesses. The implemented path keeps
all source operands and requires exact retained gaps/check hashes, with the
original serial final checks.
