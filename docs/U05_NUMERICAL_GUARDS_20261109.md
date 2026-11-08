# Numerical checking and optional encoding — isolated correction

## Connected T01 positive material

3020212866 halted at the final connected T01 owner check with a reported gap
0.04009978780572731 mm. Read-only replay of the retained native operands reproduced
that number from the large owner re-union, while the only changed source circle
has 0.1214112478464867 mm clearance to the same foreign constraint.

The checking operand now uses the existing exact identity
(A union B1 union ...) minus A = union(Bi minus A), already qualified for T04.
Only the final connected T01 checker opts in. Candidate geometry, allocations,
source cores, growth limits, pin/channel rules and the 0.0401 mm construction
guard are unchanged. Every positive-area proposal piece remains, including
pieces smaller than 1e-12 mm2. No buffer, snapping, area cutoff or tolerance waiver
is introduced. The legacy T01 branch and all other stage bodies are unchanged.
An exact hash-bound AST proof admits only this factory/checker delta for retained
PASS predecessors; arbitrary source or threshold changes still fail.

## Optional owner overlap in T05 encoding

Actual 2849 and 2868 T05 now reach encoding preparation beyond the former shared-
gap conflict, then halt at EXPORT_OWNER_OVERLAP_CHANGES_QUALIFIED_COPPER. Retained
2849 operands reproduce optional support physical_delta_mm2=1.4730573062680286e-12
against the unchanged 1e-12 limit. The original qualified addition is still valid
and inside its domain. The failed support proposal must not replace that addition.

Reject the whole optional support proposal and retain the original addition byte-
identically. This is not a clipped fragment, a replacement growth decision, a
hole fill or a larger epsilon. Invalid or out-of-domain original geometry still
halts. Native encoding budgets, actual export/reparse, complete physical/source/
predecessor retention, protected pin/channel separation and corruption controls
remain mandatory. Existing successful owner-overlap encoding is unchanged.
The actual retained failing region passes byte-identity verification under this
selection; final client-board export qualification is still required.

## Reuse only verified work

A reference boundary retains exactly 23 source/legacy/export/reference operations
and no connected stage. All connected T01/T03/T04/T02/T05 construction and paired
evaluations are fresh, with three fresh source-assembly checks and all final
native export/reparse/control/audit/render operations. This permits correction of
the failed 2866 T01 without redoing its already verified reference generation.
It cannot promote or resume the failed T01 job. Original native proofs, paired
worker identities, geometry artifacts, custody hashes and logs remain checked.

The owner-authorized ordinary-hole policy transition may also occur before fresh
T01 at this boundary. Only that captured policy label changes; all non-hole
settings must match exactly. No connected geometry is inherited at this boundary.
The old T01/T03 boundary and its checks remain available unchanged.

## Evidence and acceptance limits

Evidence root: out/lacie_work/evidence/ordinary_hole_acceptance_20261108.
- 2866_SET_DIFFERENCE_IDENTITY_03.json: original false checking operand replay.
- T01_LAND_DELTA_TESTS_02.log: 76 focused tests PASS.
- ACTUAL_OPTIONAL_OVERLAP_REJECTION_01.json: original qualified region unchanged.
- OPTIONAL_OVERLAP_TESTS_02.log: 63 encoding/pin tests PASS.
- COMBINED_NUMERIC_TESTS_01.log: 194 focused tests PASS.
- combined_numeric_synthetic_01: all 47 native operations and delivery PASS.
- REFERENCE_BOUNDARY_TESTS_01.log: 199 focused tests PASS.
- reference_boundary_baseline_01: all 47 native operations and delivery PASS.
- REFERENCE_BOUNDARY_NATIVE_01.log: PASS with 23 verified retained operations,
  24 fresh native operations, successful delivery and byte-identical synthetic
  Gerber SHA256 a5a80445a3dd3b1e246856c88d4e5d2f5b454a059d913dd052526b4c3ec6eeda.

Source_22's initial test import-cycle failure and OPTIONAL_OVERLAP_TESTS_01's
missing-file harness failure are preserved separately. Neither is a native board
PASS. Both actual failed T05 jobs remain HALTED, with downstream operations NOT_RUN.
Other ordinary-hole, pin-separation and positive-only flattening evidence remains
separate; flattening receives no credit for this correction. Normal app integration
is not claimed by this document. Owner remains pending; no independent, electrical
or manufacturing acceptance. .DS_Store custody stays EXPLICIT_UNWAIVED_UNATTRIBUTED;
six deferred broad-suite findings stay DEFERRED_UNWAIVED; 10% timing target waived.
