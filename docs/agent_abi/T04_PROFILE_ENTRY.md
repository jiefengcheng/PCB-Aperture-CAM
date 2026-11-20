# Source-built T04 profile entry

The incremental direct parallel-group construction entry is documented in
[T04_DIRECT_GROUP_CONSTRUCTION.md](T04_DIRECT_GROUP_CONSTRUCTION.md). It uses the
same intake and caller with an explicit algorithm selection, publishes group
interiors only, and cannot be treated as the complete checked path below.

This explicit T04-only entry starts from an accepted T03 job. It constructs the
25% baseline in the current run, checks it, and then offers additive side-specific
growth over that accepted copper. Saved 10% and 25% studies are comparison inputs
for qualification, not dependencies of a full-board job.

The connected native route and a local parallel group remain different objects.
Source-role classification uses the existing original-owner index to distinguish
bulk from trace occurrences before choosing the mutable set. Native source
identities, original refs, aliases and bulk subtraction records remain explicit.

The first phase uses source-derived conservative band parameters to construct
the 25% candidate; it does not execute a separate 10% T04 ladder. The native
ladder may reduce unaccepted source proposals. The second phase treats the first
phase's checked route bodies and bulk operands as an unconditional copper floor.
Both faces share one total-width budget; an open face can take optional copper
while the crowded face remains fixed. The accepted route pose is fixed throughout
this second phase.

Each phase retains the captured seven-pass schedule `[1,1,1,1,2,2,2]`, the two
source-width caps, complete nominal/envelope checks, source-void checks and actual
pre-motion owner/terminal validation. A rejected optional supplement leaves the
accepted floor available. A rejected native final gate stops the operation.

`profile_floor.CopperFloor` is the geometry-only boundary between phases. It binds
the source scene, route membership, poses, widths and exact WKB refs. It does not
import checker verdicts. Source roles and parallel catalogues are shared once per
job. Route shape caches have byte budgets; positive side witnesses are keyed by
complete geometry/recipe hashes and cleared between constructions.

Owner and source-void neighbor indexes use complete possible profile bounds,
including the retained floor and all optional extension operands. The old
symmetric source-width radius does not bound side-specific growth. Every trial
must fit the prepared bound before clearance evaluation. A regression case
places a source void beyond the old radius but inside a one-sided supplement;
the complete profile index discovers and rejects the filled void.

If finite section checks reject an optional supplement after local trimming,
the constructor records those rejected sections and discards the supplement.
It revalidates the exact floor and still runs the native proposal and complete
final checks. It never accepts the over-cap shape or removes accepted copper.

For scope, use the operation's `scope`, `full_board_run` and
`source_built_profile` fields. Some nested planner labels remain from the older
bounded report contract; they are diagnostic compatibility fields and do not
select execution scope or establish whole-board acceptance.

Prepare a job without executing T04:

```sh
tools/Run_T04_Profile.command prepare \
  --accepted-t03 "<absolute accepted T03 job>" \
  --output "<absolute new job under out/lacie_work>"
```

Execute an explicitly bounded qualification:

```sh
tools/Run_T04_Profile.command run --job "<prepared job>" \
  --route-ids "<JSON with unique native route IDs>"
```

The whole-board variant uses `--whole-board` instead of `--route-ids`, together
with `--qualification "<hash-bound bounded qualification manifest>"`. It removes
the route filter, not any native checks. Its gate revalidates source code,
accepted T03, policies, bounded results, proposal artifacts and proof chains.
Preparation never starts a whole-board run. An attempted job cannot be resumed
or silently rerun; retain its failure and make a new job after an implementation
correction.

The ordinary U05/T04 defaults remain unchanged. Translated/subtractive outputs
are blocked from downstream replay/export through older additive-only consumers.
This entry completes T04 geometry only; replay and Gerber export require their
own qualification.

The machine-readable contract is
[`t04_profile_entry.json`](../../contracts/agent_abi/t04_profile_entry.json).

## Debugging qualification after the 2026-11-19 full-board failure

The failed full-board job is immutable. Its equal-width profile unnecessarily
clipped an upper buffer identical to the lower buffer, creating an invalid
intermediate on valid source copper. Equal-width construction now uses the
single exact buffer. Optional nonuniform overlay failures are recorded as
candidate rejections; they do not establish acceptance of another candidate.

Profile fallback factors describe progress to the recorded, capped shape.
Physical width fields and eligibility now use that shape's width band rather
than multiplying the original width by progress a second time. Both physical
source caps and all native checks remain mandatory. The seven pass increments
are unchanged. Candidate selection uses conservative bounds for all retained
poses and deltas, preserving the original exact tests and route order.

The old 64-route qualification is code-bound and does not qualify these fixes.
Debugging evidence is under `out/lacie_work/t04_debug_20261119/`. The saved
failing route has a separate bounded native qualification. No full-board rerun
or downstream replay/export is implied.

The former scaling defect divided the candidate budget by the number of
mutable routes and discarded candidates exceeding that share. Planning now
keeps every admissible candidate as an immutable parameter/geometry recipe.
There is no memory-derived candidate-count cutoff. One 512 MiB geometry-only
LRU serves the complete planning call. A miss or oversized shape triggers exact
reconstruction and a WKB/SRID/precision/bounds identity check; it cannot remove
the candidate. The zero-byte-cache path uses the same eligibility and order.
Active source/chosen-route geometry and small recipes are separate from this
reuse-cache budget. Conservative neighbor bounds include every eligible recipe,
irrespective of which shapes happen to be cached.

Budget-dependent counters are emitted through operational progress, outside
the construction receipt and native proof authority. The old code-bound
qualification is historical; the corrected implementation requires fresh
five-case and 64-route native qualification. No full-board run or replay is
authorized by these engineering changes.

The 2026-11-19 memory-independent implementation completed fresh bounded
qualification: 240 targeted tests, both complete native cohorts, all final
checks and stored proof-chain audits. Sequential cold-job stage times were
743.19 s for the five marked cases and 1183.54 s for the 64 requested paths
(62 mutable trace routes). The current receipt is
`out/lacie_work/t04_candidate_cache_20261119/QUALIFICATION.json`.

Side-growth performance remains a separate architectural concern. Its current
constructor inherits the checked floor/poses but does not consume the parallel
and route-containment relation data. Bounded exact-output profiles attribute
most constructor time to dense polygon section/gap intersections; tree-query
time is small. See the complete profiling report at
`out/lacie_work/t04_candidate_cache_20261119/SIDE_GROWTH_PROFILE_REPORT.md`.
No relation-based replacement, default activation, full-board run or replay
was performed as part of this qualification.
