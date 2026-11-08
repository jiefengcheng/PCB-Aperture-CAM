# Complete indexed boundary checks in reference export

3020212849's reference T05 constructor and both native evaluations passed with
identical proofs. The reference exporter then spent 732.163 seconds constructing
its Gerber. A one-second sample put all 770 main-thread samples in the direct
GEOS Hausdorff calculation. The two evaluations repeat construction before
reparse. They were deliberately stopped with their FAIL statuses retained;
the successful constructed file remains a byte baseline, not an accepted export.
The stopped job accounts for 21 PASS, 2 FAIL and 24 NOT_RUN operations.

The final exporter already uses `src.native_boundary_metric.distance` for its
normalization check. This isolated correction uses the same qualified service
for reference normalization, native board contour quantization/fidelity,
point-contact support comparisons and retained source-atom comparisons. All
vertices, holes, islands and both directions remain. Small inputs retain the
original native call; larger inputs use bounded target-segment indexes and
native GEOS point/segment probes. The existing 256 MiB index budget and every
geometry, grid, scalar, clearance and numerical threshold remain unchanged.
No coordinates, normalization mode, contour, support decision or Gerber encoder
are changed. An index resource failure still halts rather than substituting a
result. This is verification computation only, separate from PCB source scope.

On the three largest actual retained export parents (122,094, 81,932 and 59,035
vertices), the indexed metric produces exactly the original double values.
Measured metric-only times are 0.624, 0.357 and 0.249 seconds. These are scoped
diagnostics, not an end-to-end benchmark against the 732-second construction.
The largest measured distance is about 0.956 nm: this existing isolated-support
metric was already recorded by the old exporter. It is not a new permission for
physical error; complete physical-union and actual reparse checks retain their
existing tighter bounds and all original-copper preservation requirements.

Incremental continuation retains all 17 completed reference geometry operations
through T05. Source assembly still runs freshly in three separate workers and
must reproduce the identical prepared source and native build. A strict AST
guard allows only substitution of the existing metric call in the shared
native export module; grid, tolerances, predicates and geometry changes reject.

Inspection also exposed a third-generation prefix bookkeeping defect: an old
T01 proof was compared with its immediate parent's producer instead of the
producer that actually constructed that stage. The corrected inspector derives
each stage's producer from the recursively revalidated chain and checks all
three proofs against that producer. It does not relabel a proof or trust a new
claimed producer. A three-generation regression retains the different original
T01 and T05 producers; altered metric policy/geometry still rejects.

The final focused run passes 638 tests, including board hole/contour controls,
actual metric parity, bounded metric use and prefix ancestry. All 47 native
synthetic operations subsequently passed, including actual export/reparse,
corruption controls, defect auditing and rendering. That fixture does not
establish whole-board qualification.

Fresh 3020212849 reference construction passed in 505.285 seconds and produced
79,876,839 bytes, exactly matching the preserved construction's SHA-256
`dcaad0fa7f9df1a6022b9c2d8df73c3c1e98d89820e7a91f91ed9a50ba270331`.
The old file was not an input to generation: a separate validator compared it
after construction. The observed construction time is about 31% lower than
732.163 seconds, with different prefix ancestry and background work; this is
not an uncontended end-to-end benchmark. Both native whole-board export
evaluations subsequently passed with exactly identical proofs, each taking
1,414.72 seconds. They preserve 3,278 source objects and both clear operations,
check all 11,738 appended regions, pass stage clearance, 441 attachment
obligations, 245 junction checks and functional-channel checks. The physical
floor remains 0.040 mm. Reference remedy, connected stages and final
export/reparse, corruption, defect and rendering checks remain required before
delivery. Byte equality did not substitute for the paired native checks.

3020212866 is qualifying in a second isolated lane using the same frozen code,
following the user's PCB-artwork-only scope confirmation. All three fresh
source assembly operations passed before T01 began. The two-lane plan leaves
all per-job checks and budgets unchanged; the consolidated release remains
inactive. No new full 3020212826 run is authorized.

Evidence is under `out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/`
`export_inclusive_identity_01/remaining_boards_01/shared_gap_entry_contour_01/`
`legacy_export_metric_01/`: `actual_metric_parity_01/RESULT.json`,
`PREFIX_INSPECTION_02.json`, `FAILED_EXPORT_EVIDENCE_CUSTODY_01.json`,
`CONTROLLED_EXPORT_STOP_02.json`, `FOCUSED_METRIC_02.log`,
`SYNTHETIC_QUALIFICATION_01.json`, `FRESH_REFERENCE_BYTE_PARITY_01.json` and
`LIVE_JOB_03.json`. The parent
`t05_memory_01/LEGACY_EXPORT_SAMPLE_01.txt` retains the original native profile.
Record01 was an unexecuted constructor stop intent: that constructor had
already passed and was never signaled. Record02 identifies the two evaluations
actually stopped. Both records and all failed evidence remain preserved.

The normal app now also includes this correction, fast-forwarded from 5233e77
after the actual reference checks passed. Installed-path qualification passes
72 focused regressions and all 47 native synthetic operations, with unchanged
synthetic Gerber SHA-256
`80594c00c5e58743d31d05c83087d3326e6fbadf53b5328b0666a0141e8121a6`.
The four user-owned untracked files, source metadata backup and rollback branch
are preserved. This is source integration and scoped qualification, not
completion of either unfinished client board. Evidence is
`ACTUAL_REFERENCE_QUALIFICATION_01.json` and
`app_integration_01/QUALIFICATION_01.json` in the same evidence directory.
Primary 3020212826 must not
receive another full run. Six broad-suite findings remain deferred and unwaived;
the 10% performance target is waived. Prior `.DS_Store` custody remains
EXPLICIT_UNWAIVED_UNATTRIBUTED. Owner PENDING_USER, independent NOT_RUN,
electrical/manufacturing NOT_ESTABLISHED. Positive-only flattening remains a
separate unfinished slice.
