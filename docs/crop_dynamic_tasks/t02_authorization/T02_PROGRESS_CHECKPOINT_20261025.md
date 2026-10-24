# T02 progress checkpoint — selected larger crop

**State:** `PARTIAL — ORG_INVENTORY_PASS; T02_PROPOSALS_BLOCKED`
**Scope:** T02 only. No T02 geometry was generated in this checkpoint.
**Checkout:** `main` at `838b2d5c4de5e687960f7f4b0b1ea8f3dac61dd5` when rechecked.

## Baseline qualification

The T01 structure map, refactor audit, source, tests, and owner-bound receipts were inspected. Refactor/parity evidence was rerun in `out/crop_dynamic_tasks/t02_baseline_recheck_20261025_v3/` against the exact historical owner-accepted materialization:

- Owner decision: `t01_visual_crop_acceptance_20261024`, `ACCEPTED_VISUAL_CROP`.
- Frozen scene: `out/crop_dynamic_tasks/t01_owner_review_20261024_v2/context.wkb`, SHA-256 `08f8db9d4177b2a53eeec1ece64d1e1efd562c32c32fc42916682224aadf8ef0`.
- ORG source SHA-256: `850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0`.
- Result: `PASS_REFACTOR_PARITY`; pre/post algorithmic replay and repeat replay matched. The frozen owner materialization comparison found no geometry differences. 51 sites, 33 events, 330 geometry artifacts and 527 bundle files were checked; all 70 immutable asset hashes passed.
- Focused T01/T02 regression run: 56 tests passed. The inventory/rectangle subset was rerun separately: 7 tests passed.

This qualifies the refactor path and the historical T01 artifact only. The accepted materialization viewport is `[1.2858444444444446, -15.687077777777787, 4.508066666666666, -12.975966666666665]` mm. The selected T02 viewport is `[16.44342222222222, -16.556731666666664, 27.198977777777777, -8.645620555555553]` mm; their X ranges are disjoint. Historical T01 acceptance cannot bind the selected larger crop.

The newest larger-crop T01 output found is `out/crop_dynamic_tasks/t01_corrected_review_20261025_v8/`. Its report and policy retain `NEW_EXPERIMENTAL_CROP_CANDIDATE_PENDING_OWNER_REVIEW`. It predates the later shape allowance correction: at most one non-round construction in each of the four owner-accepted physical F.Cu components, with the other sites remaining round. The four component findings are recorded separately from acceptance of a constructed T01 scene. No current owner decision binds a full-crop T01 materialization implementing that correction. The latest T01 priority response also does not identify an executable selector in the current saved policy.

This is a missing required input artifact, not a request to add a second approval gate to baseline parity. The task requires the actual latest owner-accepted T01 scene on this crop; neither the historical disjoint scene nor an unaccepted candidate can be relabeled to satisfy it. The accepted scene must be supplied or generated and accepted through the owner’s existing workflow before T02 proposals can use it. No T02 changes were made against a mismatched scene.

## T02 ORG inventory slice

The frozen ORG-only inventory is `out/crop_dynamic_tasks/t02_org_inventory_20261025/`:

- ORG source: `850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0`.
- Fixed viewport: `[16.44342222222222, -16.556731666666664, 27.198977777777777, -8.645620555555553]` mm.
- 1,032 supported intersecting F.Cu records: 81 provisional source-bound filled rectangle candidates (`TREAT`) and 951 protected records (`KEEP_PROTECTED`). Two other polygon contours remain protected.
- Candidate target-set SHA-256: `029573c16449275b3a812880967d62209b5bfcec2311737f76e098eba44981e3`.
- `fresh_org_source_audit.json`: `PASS_ORG_SOURCE_RECTANGLE_AUDIT`; native source-span checks verify all 81 candidate records as filled F.Cu rectangles and preserve the two nonrectangle polygons.
- Inventory manifest hashes were recomputed and match the recorded files.
- No EDIT geometry was used for candidate construction; no T02 proposals were generated.

`TREAT` remains provisional geometric eligibility, not final T02 admission or proof of independent editability. The native-span check verifies selected rectangles, while exhaustive source enumeration and viewport-intersection coverage still rely on `native_inventory/2`. Electrical identity, semantic pad identity, complete overlap ownership and clearance against a newly admitted T01 scene remain unestablished.

## Summary audit and limits

The owner-designated ChatGPT thread returned **“PASS REPORTED for provisional ORG-source rectangle eligibility; BLOCKED for T02 proposal generation against the selected larger crop.”** It found no material contradiction between those two statuses. This was a summary-only audit: ChatGPT did not inspect the repository, source, receipts, or rerun tools. It independently highlighted that the selected rectangle checks do not prove the inventory is exhaustive, and that a qualified full-crop T01 scene is needed to reconcile positive and protected geometry before T02 construction.

## Result

- Historical T01 refactor/parity prerequisite: `PASS_REPORTED_HISTORICAL_BASELINE_ONLY`.
- Selected-crop ORG rectangle inventory: `PASS_REPORTED_PROVISIONAL_ELIGIBILITY`.
- Selected-crop T01 baseline admission: `NOT_ESTABLISHED`.
- T02 proposal generation and current-neighborhood adaptation: `NOT_RUN`.
- Native export, electrical correctness, manufacturing approval and final EDIT fit: `NOT_ESTABLISHED`.
- T03–T07: not authorized.

Reproduction of the focused inventory checks:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_t02_org_inventory_audit tests.test_crop_rect_t02 -v
```

The ignored `out/` artifacts retain full reports and hashes. Unrelated dirty and untracked work was left untouched.
