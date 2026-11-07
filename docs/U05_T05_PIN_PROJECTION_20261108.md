# Complete T05 pin checking without an unrelated global overlay

The isolated `c5a4e6f` client tail halted after all four remedy radius rounds
and joint smoothing, before its final pin predicate could run. GEOS failed to
union the complete scene's 2,535 overlapping material surfaces. Every individual
surface is valid. The failed run, its logs and four completed-round checkpoints
are retained unchanged; this is not a pin-bridge verdict or a native T05 pass.

The source-bound pin rule already has a streaming complete-domain checker.
It projects every intersecting material part onto every complete protected slot
domain, unions those local parts, then applies the same branch, transition,
spacing, source-retention and attachment predicates. Restriction to these domains
commutes with union. The change uses this existing checker only at T05's final
pin gate. It does not snap coordinates, change geometry, omit protected slots,
weaken spacing, alter rejection state or skip any later native-file check.
Other stages retain their exact prior code path.

On the actual retained final scene, the old global union reproduces its GEOS
failure. The existing complete-domain check passes all 13 protected slots in
about 0.11 seconds, with all material WKB bytes unchanged. The implemented helper
reproduces that full proof exactly. This diagnostic is separately evidenced and
does not promote the failed native job.

Regressions cover normal widening at multiple orientations, unchanged integral
joints, spacing rejection, missing branches and bridges made from separately
stored fragments, including the end of the protected transition. Prefix checks
permit only the exact T05 conditional and evidence captures; changes to another
stage, scope or material operand remain rejected. All 606 focused Gerber U05 and
shared-gap checks pass; the six deferred broad-suite failures are not rerun or
waived.

The worker also stores the complete constructed T05 value, including radius
reports and smoothing evidence, before final pin verification. It is explicitly
a pre-verification checkpoint, not an accepted result. A failure keeps its FAIL
and subsequent NOT_RUN dispositions. The failed historical worker did not save
this complete return value, so its geometry checkpoints cannot silently stand
in for a complete native T05 construction proof.

Qualification remains isolated. Reuse the accepted T01-through-T02 prefix from
`20261107T163654Z-ab5d273c176a4dd08a7e60db32c0ca59`, preserve the later failed
tail `20261107T193222Z-7b6707757bd046578fd002ace6bcadb0`, and require the fresh
T05/export/reparse/controls/render tail. Do not restart full U05 or earlier growth.
Both frozen deployment candidates remain inactive. Evidence is under
`out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/pin_projection_union_01/`.

Other boards remain paused. All checks, budgets and failed evidence remain;
`.DS_Store` custody is EXPLICIT_UNWAIVED_UNATTRIBUTED. Owner acceptance is pending,
independent review NOT_RUN and electrical/manufacturing NOT_ESTABLISHED.
