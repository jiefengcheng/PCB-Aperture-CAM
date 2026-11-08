# Retained T05 export input copy correction

The fresh 3020212849 export-only job
`20261108T223114Z-dae2aeda9e1649ca8084a771e474f5bd` halted before export because
the tail driver omitted `HOLE_ACCEPTANCE_SNAPSHOT.json` from its input copy list.
The original T05 construction and both separate evaluations remain PASS;
the failed tail remains HALTED and is never resumed or relabelled.

The correction copies that policy snapshot alongside the other sealed inputs.
The original input hash checks, source/code binding, all export/reparse and
corruption checks remain unchanged. No geometry or policy decision changes.
Ten tail reuse regressions pass in isolated external source_33. A fresh native
export-only qualification is required; this document does not claim it passed.

Evidence is retained under
`out/lacie_work/evidence/ordinary_hole_acceptance_20261108/`, including the
original failed tail, TAIL_HOLE_SNAPSHOT_TESTS_01.log (storage setup rejection,
no tests ran) and TAIL_HOLE_SNAPSHOT_TESTS_02.log (10 PASS).

Ordinary holes retain the user-adopted acceptance policy. Protected separation,
clearance and all budgets remain mandatory. Prior .DS_Store custody findings
remain EXPLICIT_UNWAIVED_UNATTRIBUTED. Owner PENDING_USER; independent NOT_RUN;
electrical/manufacturing NOT_ESTABLISHED.
