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
