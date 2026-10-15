# Client Gerber demonstration consolidation — 2026-10-15

Decision: **PASS for the declared local demonstration and evidence-linked visual delivery**. This extends the project from its synthetic coupon to one bounded operation on real supplied Gerber artwork. It does not change frozen V1/V1.5/V2 acceptance.

## Delivered behavior

The source is already aligned. A separately labeled +0.35 mm challenge moves R140.1 and its permitted trace endpoint; the executor restores alignment to the fixed solder-mask opening, writes a candidate Gerber and reparses it. All nine local checks pass. The accepted candidate equals the supplied original bytes; this is a controlled transformation demonstration, not a discovered client defect.

The open control fails connection. The bridge control fails protected-object preservation and separation. The movement-limit admission control refuses staging. Rejected attempts preserve the accepted candidate. The contract's movement, clearance and connection-width limits are explicit demonstration values, not manufacturing requirements.

`src/client_gerber.py` supplies qualified source-preserving coordinate edits and local composition; `src/client_operation.py` generates the candidate; `src/client_validation.py` checks it separately. `tools/client_operation_run.py` retains execution, controls and rollback. `tools/client_visual_demo.py` binds the result into the existing workbench. No pcb_Z or SQLite client-object import is involved.

## Canonical retained delivery

- Operation: `out/client_operation/run_20261015T050705_750904Z/`.
- Workbench: `out/visual/client_20261015T053027_782777Z/index.html`.
- Current pointers: `out/client_operation/current.txt` and `out/client_demo/current.txt`; these are conveniences, not frozen identities.
- Video: the operation run's `recording/workbench_project_goal_walkthrough.mp4`; 137.484 seconds, H.264/AAC, 1280×720. Nine captured read-only UI states with local narration; recorded execution replay, not continuous live execution.
- Current presentation review: the workbench's `ui_review.json`. The earlier operation `local_review.json` refers to an earlier bundle and remains historical.
- Consolidation: `out/client_consolidation/20261015_closeout/audit.json` and its repeatable `audit.py`.
- Tracked hash register: [CLIENT_OPERATION_EVIDENCE.json](CLIENT_OPERATION_EVIDENCE.json). Reproduction and demonstration script: [CLIENT_DATA_DEMO.md](CLIENT_DATA_DEMO.md).

## Verification and unresolved limits

Read-only consolidation verifies all 42 client-source hashes, all 70 frozen asset hashes, 66 copied visual snapshots, embedded-scene equality, current implementation hashes, candidate/control reports, rollback receipts and recording/frame hashes. Focused JavaScript checks pass (syntax plus two tests); 14 Python visual tests pass. The nine walkthrough states were inspected in the browser, with expected PASS/FAIL/NOT_EVALUATED distinctions and verified integrity banners.

**A clean full-suite result is not established for this checkpoint.** The retained earlier local review records 98 discovered tests with two failures and two setup errors caused by extra `assets/.DS_Store`. Its presence is reproduced by consolidation: all 70 expected file hashes match, but strict asset inventory fails. The extra file is preserved under the immutable-assets rule. Earlier historical full-suite results are not relabeled as current results.

The generic `tools/verify_visual_bundle.py` expects `status` and `outputs` fields absent from this client's custom build receipt. The additive consolidation audit checks the actual receipt format and all 66 snapshots; the generic verifier is not claimed to have passed. No historical receipt is rewritten to disguise this difference.

The top copper's 304 zero-width interpolation warnings keep that view display-only. The operation uses qualified bottom copper. The ten internal copper layers, cross-layer connectivity, schematic agreement, whole-board electrical correctness and manufacturing approval remain NOT_ESTABLISHED. Cursor review remains NOT_RUN: CHANNEL_UNAVAILABLE; local review is not independent third-party review.

## Closeout boundary

The user requested consolidation after accepting the implementation and replay delivery. Commit only project-local source and documentation; keep client artwork, generated outputs and recordings local and Git-ignored. No remote upload or new implementation stage follows from this closeout. Frozen decisions and historical evidence remain intact.


## Subsequent issue consolidation — 2026-10-15

[CLIENT_ISSUES.md](CLIENT_ISSUES.md) tracks maintenance after this historical closeout. The generic-receipt incompatibility is now fixed with explicit legacy support, while future bundles use the common receipt format. Builder provenance, output copying and operation-input integrity are tightened. The original bundle/video receipts remain unchanged; strict asset inventory and engineering coverage limits remain explicit.


## Inventory blocker resolved — 2026-10-15

Following explicit user instruction, removed only `assets/.DS_Store`. Strict inventory now passes all 70 frozen assets, and a fresh full-suite run passes 114 tests. Earlier incomplete-suite statements remain historical; evidence is retained under `out/client_consolidation/20261015_metadata_cleanup/`. Engineering and independent-review limits are unchanged.
