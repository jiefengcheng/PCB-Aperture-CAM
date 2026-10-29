# T03 — Adapt trace approaches and finite-width paths
> **FUTURE PLANNING ONLY — NOT AUTHORIZED by the current T01 handoff. Requires separate owner approval after review of T01 results.**


**Operation stages:** 3 + 3.5  
**Prerequisite:** T02  
**Autonomy:** Implement, verify, record, and continue within the mandate. No routine human-review gate.


## Objective
Make attached or affected trace approaches respond to the enlarged lands, rather than merely widening the old centerlines.

## Implementation
Use all relevant qualified ORG trace chains in the crop, including chains not belonging to the old three-member correspondence. Preserve explicit branch and boundary ports and protected source paths. Starting inside a land is acceptable; do not require artificial recentering.

Construct a bounded set of local path/attachment alternatives from the updated land contours, fixed ports, intended width policy and current obstacles. Reuse existing local geometric operations before introducing a router. A candidate must be assessed as a **finite-width copper footprint**, including gap/error allowance, not just a collision-free line.

Plan and accept the complete affected local chain atomically so that a temporarily disconnected piece is not published. Keep a reservation for the subsequent width profile. A conflict may reopen optional earlier land growth through the one-pass reconciliation budget, with explicit rollback and a new receipt.

## Verify
- Fixed ports, intended local physical contacts and protected branches remain.
- Direct/elbow/limited-variation alternatives terminate after the declared finite budget.
- A centerline that fits but whose copper footprint collides is rejected.
- Paths use current neighbor geometry and the intended later width.
- No unintended connection to another original component, no scope leak, and no fake global-net claim from a local check.
- Every accepted path is source-linked; ambiguity in ORG decomposition triggers bounded abstention, not invented connectivity.

## Perceivable output
Show accepted land geometry with old and new trace approaches, their width envelopes, fixed ports and limiting neighbors. Display all changes in the full crop, with optional local detail.

## Complete and continue
Retain safe unchanged paths where no adjustment is needed or feasible, with reasons. Report actual changed-chain counts separately from implemented capability. Continue to T04; do not stop at a path-only drawing or a proposal for a general autorouter.

## Current consolidation pointer — 2026-10-29

For the current lane, the governing order is T01 → T03 if needed → T04 → T02.
The older prerequisite/order and land-reopening language above are historical,
not current permission. See the [T03 architecture consolidation](../t03_architecture_notes/T03_CODE_STRUCTURE.md)
and [decision](../t03_architecture_notes/T03_CONSOLIDATION_DECISION.md). No new route
execution or ABI implementation follows from this documentation slice.
