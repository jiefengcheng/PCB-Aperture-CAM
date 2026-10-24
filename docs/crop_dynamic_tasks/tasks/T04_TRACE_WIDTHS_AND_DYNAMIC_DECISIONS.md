# T04 — Fit trace widths and local contours to the remaining space
> **FUTURE PLANNING ONLY — NOT AUTHORIZED by the current T01 handoff. Requires separate owner approval after review of T01 results.**


**Operation stages:** 4 + 4.5  
**Prerequisite:** T03  
**Autonomy:** Implement, verify, record, and continue within the mandate. No routine human-review gate.


## Objective
Construct actual conductor width profiles that fit the updated paths and neighbor contours while visibly accounting for the broadening observed in the owner example.

## Implementation
Consider supported traces within the frozen crop scope, including neighboring traces not directly attached to a selected round seed. Assign KEEP, width change, contour adjustment or ABSTAIN from the policy. Do not widen every trace by default.

Generate constant or piecewise smooth width/contour proposals using a compact shared parameterization. Evaluate distance on effective copper. Fit within the reservations and current neighbor constraints while respecting experimental minimum widths and protected endpoints. Local neck-down/removal is allowed only in explicitly writable trace regions, never by silently shaving a land core or another feature.

If the profile cannot fit, use the remaining local reconciliation budget to reconsider the path or optional growth. Preserve the earlier state and reject/abstain when infeasible. Do not use EDIT-shaped masks as a corridor.

## Verify
- Source-bound cross-section stations and conservative width/gap measurements are retained.
- A too-narrow profile, new bridge, broken path or protected-object change is rejected.
- A width-compatible centerline/footprint pair remains consistent after serialization and re-composition.
- Stage 3 and 4 share the same current scene and reservations; no stale corridor use.
- Width changes and path changes have separate deltas/metrics, even when they interact.

## Perceivable output
Full crop showing width/contour changes on accepted paths, with selected cross-sections and a reason for each limit or local narrowing. Nonchanged trace-only void remains visible; the stage must not become a generic flood fill.

## Complete and continue
Record incremental coverage, constraints and target measurements, but do not demand every prefix improve target fit. Continue automatically to T05 with the current accepted scene and retained failures.
