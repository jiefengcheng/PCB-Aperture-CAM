# Legacy T05 owner-support encoding — isolated correction

3020212868 passed all legacy T01–T05 geometry operations, then stopped during
reference export at `EXPORT_JUNCTION_COMPONENT_NOT_FILE_GRID_POINT_CONTACT`.
The failed job's 33,216 files remain unchanged and hash-revalidated.

Route `route:JR-353a2fe0a1e5597c` uses the exact-addition support fallback.
Its nearest-grid representation leaves a long, thin 5.85e-10 mm² fragment at
zero distance from its existing owner. The component is larger than the unchanged
one-grid-component allowance. It must not be discarded, waved through, or joined
to foreign copper by weakening that guard.

The isolated change reuses `compact_supported_region`, already shared by connected
T05 export. It serializes the complete physical owner/addition surface inside a
fixed local support window, retaining the complete addition and duplicating only
existing owner copper. All four original support predicates and their 1e-12 mm²
epsilon remain. Both legacy construction and independent native-model reference
use that recipe. No growth decision, smoothing, grid tolerance, source core,
hole policy, pin separation, clearance or point-contact size gate changes.

The captured operand trial reduces 216 raw export components to 12. The native
material is a valid single Polygon without adding a point-contact cap. Its
physical-union area difference is 4.67e-14 mm²; boundary difference is about
1.35e-10 mm, below the unchanged 2e-6 mm export tolerance. These are local
diagnostics, not final native board qualification. The alternative direct owner
overlap trial failed its strict support predicates and remains retained.

The legacy-prefix inspector additionally permits only the exact e10fce9 source
hash pairs for width positive-operand subtraction and rejection-report retention.
Every retained legacy stage must already have passed under the original checker;
all candidate operands and proofs remain unchanged. Failed connected T04 is never
retained by this allowance. Connected width construction still runs fresh.
The changed connected-prefix coordinator/verifier are downstream infrastructure
for this legacy scope, and do not generate its retained geometry.

Evidence: `out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/`
`export_inclusive_identity_01/remaining_boards_01/shared_gap_entry_contour_01/`
`junction_encoding_2868_01/`, including `FINDINGS_01.json`, captured operands,
failed diagnostic/trial receipts, `FAILED_JOB_REVALIDATION_01.json`,
`BOUNDED_REPRESENTATION_TRIAL_01.json` and `visual_01/`.

Focused regressions pass 99 tests (`FOCUSED_OWNER_ENCODING_01.log`), including
the unchanged rejection of a large disconnected/point-contact contribution,
positive owner-support export/reparse with its original hole, forbidden-domain
rejection, pin/foreign-channel controls and stage-producer guards. Actual frozen
3020212868 prefix inspection passes all 17 retained legacy operations
(`LEGACY_PREFIX_PREFLIGHT_01.json`, 5.68 seconds). This does not qualify its new
reference export or downstream route.

Keep this correction isolated until focused regressions and full fresh native
reference export/reparse pass. Then connected stages, final export, corruption
controls, defect audit and highlighted rendering remain mandatory. Do not restart
successful legacy geometry or the primary 3020212826 board. New-client dispatch
remains held. Six deferred findings, explicit unwaived/unattributed `.DS_Store`
custody and separate unfinished positive-only flattening remain unchanged.
Owner PENDING_USER; independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.
