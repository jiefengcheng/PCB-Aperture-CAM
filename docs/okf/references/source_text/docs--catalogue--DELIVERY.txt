# Common catalogue: bounded R140 delivery

Step 2 implements the minimum slice defined in [MINIMUM_SLICE.md](MINIMUM_SLICE.md). The original design and definition-review evidence remain historical. The 128 MiB payload ceiling applies to both CAS writes and reads; the 72,514,570-byte original client board is retained whole.

## What is persisted

The existing `RevisionCatalog` owns SQLite revisions, source occurrences and geometry payloads. An immutable dataset envelope binds six original artifacts: the native board, bottom copper, bottom mask, top artwork, L2 source and L2 native replot. Only the first three have extracted objects in this slice. Two additional immutable report artifact revisions bind the complete L2 report and strict parser-execution report to their original input revisions, paths and byte occurrences. Qualifications cannot silently replace either report. Cross-artifact matches, qualifications and same-layer relationship witnesses are separate CAS sidecars; existing same-source foreign keys are preserved.

Eight extracted occurrences are stored: R140 footprint, two native pads, one native segment, their three Gerber copper counterparts and one Gerber mask opening. Original bytes and offsets remain the identities. Named nets are retained as annotations, including their null numeric code. Millimetre geometry uses X right and Y down. The exact R140 back-side rectangular-pad pose has a separate bounded adapter; the general inventory's earlier unsupported status is preserved for other poses.

All four object-level matches qualify at 0.001 mm tolerance, including the composition error budget. The trace Hausdorff distance is approximately 0.000009835 mm; other selected shapes coincide. These are geometry correspondences, not independent electrical intent. The mask association uses unique anchor/shape and the explicit resolved zero mask margin; no native mask UUID or Gerber pin attribute is invented.

R140.1 and the trace form one measured B.Cu contact group. R140.2 remains a separate nearby object, approximately 0.36 mm away. Footprint ownership, computed contact and mask association remain distinct. Every selection is read-only.

Qualification is retained data: the historical L2GND ROI mismatch retains its complete report and original input hashes; a fresh strict parse of top artwork preserves the first zero-width interpolation rejection and its source-command span. Top derived geometry remains unavailable. Neither discrepancy blocks the unaffected R140 query. This slice does not claim a complete top warning inventory, complete nearby-board inventory, full-board reconstruction/equivalence, independent net intent or manufacturing acceptance.

## Real execution and manual reproduction

The final pre-audit execution is `out/common_catalogue/execution_20261018_f/acceptance.json`. It pins dataset revision `687c863c124fd6b3f00c8a1db95b680c84bd03dd2d14481b759da63ed12a0ab5` and result digest `93da1f185dbe5c98bc959bf65f34347b75c7ba44c993d2a14395f5c0aa6f6d50`.

The writer (PID 92019), first reader (92042) and exported-bundle reader (92048) ran as distinct processes. Both readers returned the same selection digest. `reopened.json` and `export_reopened.json` retain the full results. The diagnostic export is `out/common_catalogue/execution_20261018_f/selection/`; it contains the selected record store, source artifacts, WKB, sidecars, dataset manifest and exact output inventory. It is selective in records, not a source-file size reduction or a standalone editable KiCad board.

From this checkout, reopen the exported store without writes:

```sh
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/common_catalogue.py retrieve \
  --bundle out/common_catalogue/execution_20261018_f/selection \
  --revision 687c863c124fd6b3f00c8a1db95b680c84bd03dd2d14481b759da63ed12a0ab5
```

Create a new execution (choose a previously unused output directory):

```sh
.venv/bin/python tools/common_catalogue.py acceptance --output out/common_catalogue/my_review_execution
```

`build` stages the store, verifies it, rechecks input and implementation hashes, then replaces only `current.json`. Failed/empty receipts, changed CAS, mixed revisions, incomplete results and partial publication reject. This is committed local persistence and atomic publication; crash/power-loss durability is not established.

## Workbench and verification

Storage & indexes uses **Find records → Relationships → Reopen → Export**. Four selectable rows show stored Gerber geometry, source annotations, object-level witnesses and qualification records. Technical records are collapsed. Old native/public/synthetic inspectors remain in the source dropdown. Cases retains correction replay. Datasets / Ingestion describes this as a bounded R140 materialization, with separate fresh-process evidence.

The browser is explicitly **REPLAY**. It does not perform live SQL queries. The publication copies the exported store, independently reopens it, derives display paths from stored WKB and verifies its projection against the copied acceptance/result. The original input dropdown +/− behavior remains intact.

Verification evidence: `out/common_catalogue/verification_20261018_final/python_tests.log` (155 tests pass), preflight (70 assets), adapter/storage/selection failure controls and JavaScript navigation tests. A frozen read-only control runner is `out/common_catalogue/verification_20261018_final/audit_controls.py`.

The initial independent Cursor audit was UNQUALIFIED because qualification semantics were not fully validated. The correction derives per-code status, scope, source/revision owners, geometry availability, measurements, message and locator from retained reports, and rejects altered projections. Thirteen semantic mutation subcases and a coherent warning-report rebinding test now reject. The CLI verify action executes full retrieval/qualification/match validation. The original audit and pre-audit executions remain immutable. The second audit also identified coherent report-path and warning-occurrence rebinding; those findings are corrected by immutable report artifact revisions, exact source-line checking and new frozen controls. Its publication check ran while the new publication was still building, observed the earlier provisional entry and correctly rejected it. The final audit will start only after the corrected publication completes. Completion belongs in the additive completion audit.
