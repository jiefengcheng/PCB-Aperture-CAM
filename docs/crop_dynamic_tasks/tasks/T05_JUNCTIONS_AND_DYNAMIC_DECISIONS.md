# T05 — Finish junctions and necks against the current scene
> **FUTURE PLANNING ONLY — NOT AUTHORIZED by the current T01 handoff. Requires separate owner approval after review of T01 results.**


**Operation stages:** 5 + 5.5  
**Prerequisite:** T04  
**Autonomy:** Implement, verify, record, and continue within the mandate. No routine human-review gate.


## Objective
Create coherent land–trace and qualified width-transition junctions after the main shapes and routes have been established.

## Implementation
Find eligible junctions from source-linked contacts and the actual accepted geometry, not merely circular primitive IDs. Propose bounded taper/fillet/blend shapes using the smallest existing suitable operators and a shared parameter set.

Limit the proposal by current neighbors, protected reference geometry and allowed scope. Keep its attached core/trace path continuous and avoid skinny appendages, detached islands or unintended shortcuts. Optional growth may be reduced; any deletion needs explicit editable-source permission and complete-patch checking.

Apply the last local reconciliation opportunity only when still available under the fixed budget. Do not restart whole-crop optimization because one neck cannot fit.

## Verify
- Actual neck/transition width is checked at declared stations or with a qualified local method, not visual smoothness alone.
- Separate original components are not bridged; required local ports and robust connectivity remain.
- The final shape stays in W and does not silently alter reference or protected contributions.
- Transition geometry has reproducible input/current-scene/output binding.
- Deliberate overlarge blend, disconnected blend and too-thin neck controls fail for the intended reasons.

## Perceivable output
ORG / pre-junction / final candidate at the same scale, including the whole crop and a selectable transition detail. Explain the limiting neighbor or reason for an unchanged junction.

## Complete and continue
Run the declared final in-memory checks and preserve the accepted scene plus rejected patches. A final geometry candidate is not yet an exported acceptance result. Continue directly to T06.
