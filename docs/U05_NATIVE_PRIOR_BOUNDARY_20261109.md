# Qualified native prior boundaries — isolated correction

3020212868 stopped before T05 growth when a retained Gerber floor shifted a
T02 straight boundary by about 1.7 nm. The exact model predicate correctly
distinguished the boundaries, but this operand was already native Gerber
geometry. Its intake now uses the existing 2 nm final-reparse fidelity bound.
The default model predicate remains exact. Geometry construction, clearance,
protected pin separation, source copper cores, width decisions, the 20% remedy
budget and the registered 1% shared-gap matching setting are unchanged.

The retained-board diagnostic produces the identical scene artifact as the
failed worker, with all prior physical/channel checks preserved. 106 focused
regressions pass, including rejection beyond the existing fidelity bound and
unchanged strict-model rejection. All 47 fresh synthetic native operations pass;
their final Gerber and highlighted PNG are byte-identical to the predecessor.
This is scoped qualification, not completion of the client board.

Nested incremental qualification retains the current, separately verified T02
result and resolves reference/legacy evidence through verified prefix ancestry.
It verifies the original legacy producer before executing its frozen inspector.
Cycles and changed producer files reject; failed T05 records remain failed.
Fresh assembly and all T05/export/control/audit/render operations remain required.

Evidence: out/lacie_work/evidence/ordinary_hole_acceptance_20261108/
PRIOR_NATIVE_TESTS_04.log, PRIOR_NATIVE_QUALIFICATION_01.json,
actual_2868_prior_precision_02/job/RESULT_01.json and
prior_native_synthetic_01/STATUS.current.json. Diagnostic harness import/layout
failures and both original failed 2868 jobs remain preserved.

3020212849 separately passed T02 construction and both evaluations, then stopped
on a larger retained-prior/shared-gap conflict. It must not be passed by applying
the numerical correction to that distinct conflict. The normal app remains at
1f3d59b; this correction is unintegrated. New-board dispatch remains held.

.DS_Store: EXPLICIT_UNWAIVED_UNATTRIBUTED. Six broad-suite findings remain
DEFERRED_UNWAIVED; the performance target remains waived. No further full primary
3020212826 run. Owner PENDING_USER; independent NOT_RUN;
electrical/manufacturing NOT_ESTABLISHED.
