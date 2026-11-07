# Export preparation after qualified T05

Job `20261107T204212Z-b2dd9a585ece45c3bd133438f1b3b791` passed T05 construction
and both native evaluations. Their complete stage values and all four radius
checkpoints match. Construction took 3,541.257 seconds; evaluations took
3,600.042 and 3,600.040 seconds. All 13 protected pin slots and 20 shared-gap
spans / 40 boundaries passed. This is qualified T05, not a completed export.

Export construction then failed after 51.036 seconds in shared-gap restoration:
the same global GEOS union failed before the gap predicate ran. The failed job,
frozen source, logs, PASS / FAIL / NOT_RUN dispositions and accepted T05 evidence
remain immutable. No final Gerber or new final render was produced by that job.

The isolated correction opts export preparation into complete local gap checks.
For every protected slot, it selects every material contributor, intersects
those contributors with a window strictly enclosing the whole slot and its
expected walls, and applies the unchanged complete gap predicate. Intersection
distributes over union; clipping cannot manufacture a checked wall because all
checked linework lies strictly inside the window. Only zero-area tangencies
introduced at the remote clipping boundary are discarded. No copper operand,
coordinate, tolerance, width, remedy budget or growth decision is changed.
Policy-wide checks still run on the complete frozen gap inventory. In the
combined app version this includes the registered 1% shared-gap comparison.

The ordinary restoration default and every growth call remain unchanged. Only
the exporter opts in. The incremental dependency checks accept this exact AST
change and reject changes to defaults, predicates or source-state restoration.
Actual export/reparse, complete native gap and pin checks, eight corruption
controls, defect audit, rendering and delivery remain mandatory.

The retained scene contains 2,535 material parts. The original global overlay
reproduces its non-noded-intersection exception in 6.883 seconds. The local
checker passes all 20 spans and 40 boundaries in 0.034 seconds with every input
WKB unchanged and no source-store writes. This is a bounded diagnostic, not an
end-to-end performance claim. The first experimental test failures and initial
diagnostic harness failure remain preserved alongside their corrected results.

Evidence: `out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/shared_gap_projection_01/`.
The next job is an export-only continuation of the fully qualified T05, using
38 retained operations and nine fresh operations including source assembly.
No full 3020212826 restart or T01-through-T05 growth recomputation is authorized.
The correction remains isolated until qualification and final visual findings.

Other boards remain paused. Six deferred baseline failures remain unwaived.
Positive-only flattening remains a separate unfinished slice. `.DS_Store`
custody remains **EXPLICIT_UNWAIVED_UNATTRIBUTED**. Owner PENDING_USER;
independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.
