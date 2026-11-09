# Native inherited-copper gap comparison

3020212849 export-only job `20261108T223549Z-e270243abd91462f8c2f9ec5f0c4b73f`
passed construction and failed both separate final evaluations on two shared
gap zones. The failed job, proof logs and generated file remain unchanged.

Scoped diagnosis in `2849_shared_gap_export_diagnosis_01/RESULT.json` identifies
three inherited T04 contributions, each with approximately 8.2724e-9 mm2 outside
the exact stored inherited footprint. Parsed and declared native contributions
have identical measured intrusions. All such material lies inside the existing
2e-6 mm native contour tolerance of the inherited footprint. Original source
copper contributes zero intrusion. This is a native contour comparison issue,
not authority for T05 to restore superseded T02 copper.

The exporter now applies that same existing tolerance to inherited footprints,
as it already did to complete gap walls. It compares a private copy of the
proof; the frozen nominal proof and all nominal growth/remedy predicates remain
exact. Native per-region fidelity, complete reconstruction, shared gap matching,
full wall preservation, clearance, pin separation and corruption checks remain.
No tolerance constant or geometry is changed. A native contour outside the
existing tolerance is still rejected. This correction is export-only.

60 focused tests pass, including inherited attachment rounding without Shapely
precision metadata, immutable proof, exact nominal rejection, larger native
intrusion rejection and prior shared-gap/remedy/reuse controls. Earlier fixture
failures remain in NATIVE_INHERITED_GAP_FIDELITY_TESTS_01/02.log; corrected results
are in NATIVE_INHERITED_GAP_FIDELITY_TESTS_03.log. Fresh whole-board export/reparse,
controls and rendering remain required; this document does not claim completion.

Evidence root: `out/lacie_work/evidence/ordinary_hole_acceptance_20261108/`.
Prior .DS_Store custody remains EXPLICIT_UNWAIVED_UNATTRIBUTED. Owner PENDING_USER;
independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.
