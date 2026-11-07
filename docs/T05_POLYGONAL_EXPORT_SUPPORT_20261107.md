# Isolated T05 export-support correction

The Master07 whole-board job stopped at T05 construction after the raw T05
growth checkpoint had passed its geometry reconstruction. Export preparation
for `route:JR-041c410fb8a61f5b` returned a valid GeometryCollection containing
one copper polygon and a zero-area LineString about 0.000028016 mm long.
The strict absorption boundary correctly rejected that mixed container with
`VALID_POLYGONAL_COPPER_REQUIRED`. The failed job remains HALTED; its status,
logs, raw checkpoint and failed evidence are unchanged.

The correction retains every exact positive polygon face of local T05 export
support, including holes and microscopic islands. Only supported zero-area
points/lines from clipping are excluded from the material container. There is
no union, buffer, grid adjustment, positive-area cutoff, smoothing change or
repair of invalid geometry. Invalid, empty, nonmaterial and overlapping invalid
multipart results still halt. All existing support, physical-union, domain,
pin, width, absorption, clearance and actual-file checks remain in force.

The exact failed polygon is byte-identical after normalization. Its local
export/reparse passes with zero native-reference geometry difference and one
positive region. The existing physical-union predicate measures
8.43507093999314e-18 mm², below its unchanged 1e-12 mm² epsilon. No new copper
is introduced by the normalization, and no absorption is needed for that case.

The corrected isolated snapshot passes 513 scoped tests across gerber_u05 and
the T04 ladder/settings/cache suites. The first broad test failed an existing
source-delta guard because of statement layout; its source and log are retained.
The original Boolean statement was restored as a separate statement, followed
by normalization; no guard or test assertion was weakened.

Evidence lives under `out/lacie_work/evidence/t04_t05_integration_20261107/`:

- `MASTER07_T05_FAILURE_01.json` binds the original failed job and logs.
- `t05_polygonal_support_diagnostic_01/REPRODUCTION.json` binds exact operands.
- `t05_polygonal_support_diagnostic_01/FIXED_LOCAL_VERIFICATION_01.json` records
  the local positive-only support-region export/reparse, not a whole-board result.
- `POLYGONAL_SUPPORT_BROAD_FAILURE_01.json` preserves the first broad test failure.
- `POLYGONAL_SUPPORT_BROAD_02.log` records 513 passing scoped tests.

Master07 retained 17 verified legacy operations and passed 21 fresh operations,
including all three T04 and T02 proofs and the 968-piece prior-width compatibility
gate. T05 construction failed; eight later operations remain NOT_RUN. A new
corrected qualification must preserve those dispositions and explicitly bind any
unchanged retained prefix before running fresh T05, both evaluations, actual
export/reparse, corruption controls, defect audit and final render.

The app remains unchanged and unintegrated; other boards remain paused. Coverage
recovery is independent and unchanged. This local support-container correction
does not perform the separate source positive/negative flattening slice.
Historical `.DS_Store` custody FAIL remains EXPLICIT_UNWAIVED_UNATTRIBUTED.
Owner PENDING_USER; independent NOT_RUN: CHANNEL_UNAVAILABLE;
electrical/manufacturing NOT_ESTABLISHED.

## Incremental qualification support

The existing `src.gerber_u05.incremental` route now supports the captured
ten-step ladder, inherited legacy process evidence, source assembly, pin policy,
checking envelopes, reference-channel state and mandatory prior-width proof.
It retains 35 completed heavy native operations. The three inexpensive source
assembly operations run freshly in the new job, followed by all nine T05 and
final-file operations. No failed operation is resumed or promoted.

The complete deterministic ladder arithmetic is replayed against every retained
geometry report and the captured settings. This also rechecks cap-rejected
attempts, which correctly have no geometry evaluation. Exact complete-solution
equality is required; this is validation of retained evidence, not a geometry
search or fresh geometry qualification claim. On the real retained board, all
3,930 attempts and 2,591 geometry reports across 393 routes validate.

Only the exact qualified export-support normalization delta is allowed through
the new dependency exception. Its helper AST and three added calls are bound;
every other statement and original geometry predicate remains unchanged.
Every retained legacy T05 raw support must additionally prove that normalization
is identity. The real prefix has 103 distinct such operands. Its source,
candidate, native process, separate-evaluation, actual reference-file and
supplemental proofs remain mandatory and hash-bound.

The extension passes 528 scoped regressions. A small native qualification passes
with 35 explicitly retained operations and 12 fresh operations, including fresh
source assembly, T05 construction and both evaluations, export construction and
both reparse evaluations, corruption controls, defect audit and rendering.
The resulting synthetic Gerber remains byte-identical to its qualified
predecessor. Logs and receipts are `INCREMENTAL_LADDER_BROAD_04.log` and
`INCREMENTAL_LADDER_SYNTHETIC_JOB_02.json` in the evidence directory above.

Earlier fixture/test-message failures and the first native prefix-adoption
failure remain recorded separately. No original assertion, immutable-write
guard, geometry predicate, tolerance, remedy allowance or budget was removed.
The actual whole-board T05 and final output still require the corrected native
qualification. App integration and other boards remain pending.
