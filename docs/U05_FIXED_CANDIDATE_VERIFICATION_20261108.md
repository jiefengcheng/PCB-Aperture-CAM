# U05 fixed-candidate verification

Status: isolated T02 implementation; not installed in the normal app. The
current 3020212826 full run keeps its frozen source unchanged. The owner has
required that it be the last full run of that board. Remaining boards stay
paused until the reusable route is qualified.

## Problem and change

The native worker previously called the T02 sizing search during construction
and again in each of the two evaluation workers. The retained 78-rectangle
case made 10,496 sizing attempts plus 168 inclusive-fill proposals per search.
The existing land verifier already reconstructs selected geometry and checks
the whole resulting scene. Repeating optimization before that verifier is
unnecessary for validating the constructed result.

Construction remains unchanged. T02 evaluations now require its successful
construction receipt, matched to the complete candidate, producer binding and
source hash. They rebuild the source and stage-entry scene, recreate the plan,
and reconstruct each rectangle from the original source and recorded bounded
factors. They then perform the ordinary complete land verification.

The fixed-candidate path freshly checks all target identities, protected source
contributions, exposure/containment decisions, factor bounds, original cores,
shared-neighbor projection, complete simultaneous finite-copper predicates,
pin slots, width attribution and every complete inclusive-fill proposal.
The original merge entry/exit handling and sticky pin rejection history remain.
The existing verifier independently replays the complete fill ledger. Changed
plans, geometry, gaps, source references, failed receipts or missing proofs stop
the evaluation.

The complete stage value must reconstruct identically. The only diagnostic
excluded when comparing the first fresh whole-scene predicate with the stored
construction predicate is the count of reevaluated pin-cache slots; all slot
identities, geometry predicates, total coverage and safety results stay compared.
The final worker comparison and construction/evaluation proof equality remain.

Sizing-attempt records and their evaluation count remain hash-bound construction
evidence. The evaluators do not claim to have rerun those optimizer attempts or
established a new optimum. Their recorded count must equal the preserved sizing
attempt count plus complete inclusive-fill proposals, within the existing budget.
Actual export/reparse, negative controls and final rendering remain separate,
mandatory native operations.

## Qualification and limits

Nineteen new tests cover identical reconstruction without optimizer calls,
changed plans/targets/factors/geometry/gaps/counts, protected contributions,
changed complete-scene proofs and construction-receipt binding. A focused suite
of 194 tests passes, including existing gap, pin, rectangle exposure, terminal,
empty-inventory and export cases. The six historical broad-suite findings are
deferred by the owner; they have not been relabeled PASS.

A separate fixed-output qualification uses the retained 78-rectangle checkpoint;
optimizer and trial-search entry points are forbidden in that process. It is
not a new full-board growth run. The first diagnostic clone omitted the existing
T04 audit directory and stopped at the unchanged missing-proof guard. That
failed setup is retained. A new complete clone includes the original audits;
its result and timing remain pending.

Evidence: `out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/fixed_candidate_verification_01/`.
The T01/T04/T05 evaluation paths and the two preparation/final-construction roles
are not claimed to be simplified by this T02 change. Further route cleanup must
use focused/incremental qualification rather than another full 3020212826 run.
Historical `.DS_Store` custody remains EXPLICIT_UNWAIVED_UNATTRIBUTED. Owner
acceptance is pending; independent review is NOT_RUN and electrical/manufacturing
acceptance is NOT_ESTABLISHED.
