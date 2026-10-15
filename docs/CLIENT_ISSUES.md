# Client delivery issue consolidation — 2026-10-15

This maintenance pass follows local consolidation `20b64a9`; it introduces no new CAM operation, parser support or implementation stage. Earlier receipts, recorded video and frozen decisions remain historical and unchanged.

| Issue | Disposition | Evidence / remaining action |
|---|---|---|
| Generic verifier crashed on historical client receipts lacking `outputs` | Fixed | Explicit legacy format support verifies scene, HTML, inspection receipt, operation result and all referenced snapshots. Generation status remains NOT_RECORDED; byte verification does not invent a generation verdict. Unknown/incomplete receipts fail explicitly. |
| Future client bundles lacked the common receipt envelope | Fixed | Builder now emits explicit status and complete retained-output hashes. Fresh generated bundle verified with the common verifier. |
| Future bundles copied recordings and obsolete local review notes | Fixed | Operation-copy excludes `recording/` and `local_review.json`; original files remain untouched. Current review is referenced separately. |
| Working-tree status was hard-coded dirty | Fixed | Builder records actual `git status --porcelain` at generation; generation commit/source hashes remain separate. |
| Builder could combine stored PASS with changed source/candidate/control files | Fixed | Precomposition checks now bind the full client source inventory, contract, mask, controlled input, accepted candidate/validation and both control candidate/report hashes. Corruption tests reject changed source, candidate, validation and control evidence. |
| Strict asset inventory contained extra `assets/.DS_Store` | Resolved by explicit user instruction | Removed only the macOS metadata file. Strict inventory now passes for all 70 frozen assets; current full suite passes 114 tests. Earlier failure receipts remain historical. |
| Top copper has 304 zero-width interpolation warnings | Retained coverage limit | Display-only fallback remains labeled. No parser-support change; bottom copper is used for the operation. |
| Client data lacks native board and independent schematic intent | Retained evidence limit | No whole-board/cross-layer correctness claim. Internal layers, drill registration and manufacturing policy remain outside this case. |
| Cursor authenticated review channel unavailable | NOT_RUN: CHANNEL_UNAVAILABLE | Local review is explicitly not independent review. |
| Video is a montage of captured UI states | Delivered with explicit label | Original 2:17 video remains bound to its original bundle. Fresh packaging does not retroactively reseal that recording or represent it as live execution. |

## Reproduction and retained evidence

Focused checks: `.venv/bin/python -m unittest tests.test_client_replay_integrity tests.test_visual_bundle_verifier tests.test_visual_scene tests.test_visual_source_guard`.

Byte verification: `.venv/bin/python tools/verify_visual_bundle.py <bundle-directory>`. Legacy receipts report `receipt_format=legacy-client` and `generation_status=NOT_RECORDED`; new receipts report the common format and their explicit generation status. Both report only retained-byte integrity, not engineering acceptance, live source truth or independent authorship.

Maintenance evidence is retained under `out/client_consolidation/20261015_issues/`; the post-build register binds exact bundle/test/verifier hashes. Client source and frozen asset bytes are not changed. No uploads or new geometry experiment are part of this pass.

Fresh maintenance bundle: `out/visual/client_20261015T074543_446151Z`. The common verifier passes all 169 retained-output hashes; the legacy bundle also verifies without mutation. All geometry and stored state/check projections match the recorded delivery. Eighteen focused tests pass. Exact receipts are indexed in [CLIENT_ISSUES_EVIDENCE.json](CLIENT_ISSUES_EVIDENCE.json).

User-directed metadata cleanup: removed only `assets/.DS_Store` on 2026-10-15. All 70 frozen assets pass strict inventory; 114 full-suite tests pass. Fresh logs remain in `out/client_consolidation/20261015_metadata_cleanup/`. Earlier statements about preserving the metadata and incomplete full-suite verification describe prior checkpoints.
