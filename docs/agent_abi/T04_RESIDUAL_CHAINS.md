# Bounded T04 residual-chain matching

The opt-in actual caller uses `residual_end_matching=True` with
`residual_chain_matching=True`. The older per-occurrence matching remains the
reference arm. This extension does not activate a full-board job or change
the seven-pass schedule, durable parallel catalogue, clearance policy or caps.

`residual_chain_match` compiles maximal unbranched, same-width native chains
outside fixed straight/arc members. Already-grown residuals participate.
Branching, closed and nonuniform-width components retain explicit deferrals;
no memory or route-count budget can silently remove an occurrence. Covered
sources and group interiors remain fixed context.

`residual_chain_budget` hashes the complete current operand inventory once.
It derives two source rails per chain, fixed-neighbor reach caps and actual
source-rail pair budgets before allocating growth. It uses vector bounds
queries, without an R-tree or original-copper visibility unions. The existing
pair allocator shares reach between future chains; rejected proposals do not
leave hypothetical bounding rectangles reserved.

Complete native rail segments are also enclosed in small lookup boxes before
fixed-copper distance evaluation. A foreign operand outside every expanded
box cannot restrict the rail's reach. This is only an input lookup screen: it
creates no new growth member, source seam or width-profile boundary. Bounded
scratch memory changes batching only; every potentially binding neighbor is
retained. Qualification compares this screen against the unscreened compiler
with exact copper, allocation and decision parity.

The ribbon constructor intersects those budgets with source caps and each
independent 10% end interval. Unknown free ends are no longer forced back to
nominal width. The four endpoint-face variables use the existing pair-packing
optimum when feasible. Otherwise `endpoint_budget` enumerates the vertices of
a fixed, totally unimodular integer constraint matrix, retaining exact primal
inequalities and selecting maximum total endpoint growth. This is a bounded
scalar allocation, not an iterative geometry search or route-wide optimum.

The existing full-span cubic is materialized over the native chain, without
refitting centerlines. Each occurrence retains its source interval and exact
source identity in a shared-contour record, following the maximal-arc pattern.
Source seams do not restart tapers. Existing grown material is the floor of
the union; the nominal-skin stitch reserves its width explicitly. The existing
residual positive-addition check evaluates new residual copper once before
admission. Subsequent chains see accepted additions as fixed operands. Group
shapes are obstacles, never audited growth candidates.

Before invoking the pair allocator, exact zero budgets are propagated and
redundant edges removed. Independent constraint components then use the same
existing solver. Resulting growth is checked against every original integer
cap and pair bound. This removes computational coupling through zero faces
without removing a source or candidate. Scalar optimum parity on the saved
330-face input is recorded separately from face-choice tie differences.

All source-interval receipts are prepared before any chain member changes.
Roundoff at a true chain end is clamped in the unit parameter only after an
explicit domain bound; genuinely out-of-domain intervals still fail. The
existing differential pocket kernel checks each proposed route addition
against its exact prior route floor and fixed group support before admission.

Corner descriptors identify shared-chain interior seams and use the full
chain length at true ends. This permits longer existing joint transitions
without borrowing certified group interiors. Existing reference, functional,
native connection, pocket, covered-copper and source custody conditions remain.
Retaining pre-joint growth and retaining every optional old final joint patch
are different comparisons; qualification reports their differences explicitly.

`JR` identifies a connected native route. Durable straight/arc parallel groups
remain separate. `RC` identifies a residual treatment chain inside one route;
it does not create or rename a parallel group.

Qualification artifacts and source snapshots belong under
`out/lacie_work/t04_residual_chains_20261121`. The paired hard/five/64 caller
measurements, visual comparisons and final disposition are recorded there.
This file documents the implementation, not full T04/export acceptance.

## Python boundary and invocation

The machine-readable capability descriptor is
[t04_residual_chains.json](../../contracts/agent_abi/t04_residual_chains.json).
It describes the existing Python interface; it is not a new CLI, JSON Schema
validator or authorization to launch a board job. Start with the
[agent handoff](T04_RESIDUAL_CHAIN_HANDOFF.md) for the mental model and limits.

Call the existing entry only after accepted-T03 intake has verified the source,
scene, settings, schedule and audit bindings. Reuse its bound store and existing
source/group preparation paths. A minimal in-process invocation is:

```python
from src.gerber_u05 import group_stage

# store, scene, settings, input_binding, preparation and route_ids come from
# the existing qualified intake/cohort. Never infer them from a screenshot.
rule = dict(preparation, scope="BOUNDED", input_binding=input_binding,
            hybrid_components=True, residual_end_matching=True,
            residual_chain_matching=True, residual_end_deviation=0.1)
stage = group_stage.run(store, scene, route_ids=route_ids,
                        settings=settings, rule=rule)
matching = stage["hybrid_components"]["residual_end_matching"]
```

Both matching flags must be true to select chains. With end matching enabled
and chain matching omitted, the nominal-only per-occurrence reference remains.
With end matching omitted, a chain flag alone enables nothing. The deviation
defaults to 0.1 and is independently applied at each registered end; it is not
a route-wide width band. An unmatched free end can grow within the existing cap.

## Treatment sequence and responsibilities

1. Existing straight and arc construction fixes group interiors; the unchanged
   default ladder treats remaining sources.
2. `residual_chain_match.chains` follows native endpoint identity within a route
   to collect maximal, open, unbranched, same-width residual chains, including
   sources that already grew. Covered/group sources are excluded by the caller.
3. `residual_chain_budget.Budgets` binds fixed operands and computes original-rail
   neighbor/pair reach limits before allocation. `allocate_components` reuses the
   established integer pair solver on independent constraint components.
4. `endpoint_budget.allocate` intersects these limits with independent end-width
   intervals and side-slope bounds. `ribbon_profile.match_ends` constructs the
   existing full-span cubic on unchanged native centerlines.
5. Existing exact-floor assembly, residual positive-addition verification and
   differential pocket checks govern admission. Every source recipe is prepared
   before any member changes. Only accepted additions enter later-chain context.
6. `corner_transition.describe` passes the whole shared chain and its true ends
   to existing joint finishing. Internal source seams remain custody boundaries.
   Existing connection, reference, functional and pocket checks consume the result.

## Inputs, outputs and failure dispositions

The internal `residual_chain_match.run` receives source metadata, mutable current
material, route/source membership, existing per-source decisions, registered
endpoint sections, source-width caps, fixed-source IDs and owner identity lookup.
Optional protected domains, exact source cores and fixed route support come from
the existing caller. All coordinates, widths, lengths and reach caps use mm.
It updates admitted material/decisions and returns `(accepted_recipes, report)`.

| Record | Meaning |
|---|---|
| `t04-residual-chain-end-match/1` | Chain proposals, deferrals, budgets, witnesses, admission decisions and timing |
| `t04-budgeted-endpoint-allocation/1` | Four integer face variables, exact inequalities, objective and deterministic method |
| `t04-component-pair-budget-packing/1` | Original/propagated face caps, pair constraints and component allocations |
| `MAXIMAL_RESIDUAL_CHAIN_SHARED_CONTOUR` | Serialized source body with shared chain ID and complete member source IDs |

`constructed_sources` counts sources assigned an admitted shared profile,
including a profile already contained by the floor. `new_copper_sources` counts
only sources on chains adding material; `constructed_chains` counts those new-
copper chains. `profiled_chains` also includes floor-only transition extensions.
Never use these counters interchangeably or as counts of fully repaired joints.

| Status | Action |
|---|---|
| `CONSTRUCTED_FROM_MATCHED_CHAIN_ENDS` | Admit new residual copper and its shared profile |
| `MATCHED_CHAIN_FLOOR; TRANSITIONS_EXTENDED` | Retain copper and admit shared transition descriptors |
| `KEEP_PRECEDING_RESULT; CONSTRUCTION_LIMIT` | Retain preceding chain with the exact reason |
| `KEEP_PRECEDING_RESULT; RESIDUAL_ADDITION_CONFLICT` | Retain preceding chain after the existing residual check rejects an addition |
| `KEEP_PRECEDING_RESULT; NEW_RESIDUAL_POCKET` | Retain preceding chain after the differential pocket check rejects an addition |

Branches, closed/nonuniform chains and missing wider boundaries remain explicit
deferrals. Infeasible budgets, exact-floor incompatibility and transition outliers
do not relax bounds or partially mutate a chain. A constructor/corridor limit is
not itself evidence of a physical clearance conflict. Unexpected failures still
stop the enclosing diagnostic with retained evidence.

## Qualification and continuation contract

Every new qualification uses a T04-only frozen source, immutable accepted-T03
bindings, the same hard/five/64 cohorts and the seven-pass schedule. Record test
source hashes, complete stage and harness wall time, raw group/body hashes,
source coverage, allocations, non-timing decisions/proofs and visual comparisons.
Declare timing/source-binding exclusions explicitly; do not hide changed
allocation witnesses or decisions through generic report normalization.

Source04 is the consolidation behavior reference. Compare fresh output against
its chain arms, not against the older nominal-only matching arm, whose intended
geometry differs. Historical operand-order proof differences remain separately
documented in the retained report; they are not an exact-byte parity claim.

Use `tools/Run_PCB_Tests.command tests/gerber_u05 -q` inside the isolated source
snapshot after the required storage preparation. Never test a mixed T02/T05
working tree and label it the T04-only candidate. Requalification is a fresh
bounded caller execution, not a replay. No board job, replay, export or default
enablement follows from these documents. Remaining endpoint records and shape
limitations must remain visible in summaries even when component checks pass.
