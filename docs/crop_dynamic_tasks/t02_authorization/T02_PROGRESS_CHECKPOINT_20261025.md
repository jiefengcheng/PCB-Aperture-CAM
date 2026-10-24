# T02 progress checkpoint — selected larger crop

**State:** `PARTIAL — T01_CROP_FROZEN; T02_EXPERIMENTAL_RUN_COMPLETE`
**Scope:** T02 only. A later addendum below supersedes the earlier blocked state; T03 remains unauthorized.
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

## Fail-closed T02 admission recheck — 2026-10-25

The T02 runner previously admitted the historical accepted T01 bundle even though its 51 dynamic contours did not intersect the selected crop; it then substituted the ORG copper union and labeled it as the accepted T01 input. That path was unsafe. The runner now binds the owner decision, registry profile, report, policy, selection, scene, fresh audit and publication receipt, and rejects an accepted T01 viewport that does not cover the full T02 crop. It no longer reads EDIT board geometry.

Fresh current-state parity qualification is retained in `out/crop_dynamic_tasks/t02_baseline_recheck_20261025_v4/`. It reports `PASS_REFACTOR_PARITY`: five compatibility-facade aliases match the new modules; pre/post and repeat algorithm replays match across 51 sites, 33 events and 330 geometry hashes; 527 accepted-bundle files and all 70 immutable asset hashes verify; the frozen accepted materialization is unchanged. This qualifies algorithmic compatibility and the historical scene only, not spatial fit to the selected crop.

The real-crop runner now exits with its intentional admission code `2` before target construction. Receipt `out/crop_dynamic_tasks/t02_baseline_admission_20261025_v2/baseline_admission.json` records `BLOCKED_ACCEPTED_T01_CROP_COVERAGE`: the accepted scene viewport is `[1.2858444444444446, -15.687077777777787, 4.508066666666666, -12.975966666666665]` mm and the selected crop is `[16.44342222222222, -16.556731666666664, 27.198977777777777, -8.645620555555553]` mm. `t02_geometry_generation` is `NOT_RUN`; historical T02 attempts remain untouched. The 31-test focused regression set passes, including baseline viewport rejection/acceptance controls, rectangle eligibility controls, T01 facade/recess tests, and T01-R1 tests.

The owner’s yellow annotations on the crop image identify round-outline losses to reject in the unaccepted crop-specific T01 candidate. They do not bind or accept a full-crop T01 scene, so they are not used to proceed with T02. There is no T02 after/delta review page because valid T02 geometry was not generated. The next prerequisite remains the complete owner-accepted T01 materialization for this crop; this is the exact input requirement in the handoff, not a new approval gate.

## Owner correction, T01 freeze, and T02 execution — 2026-10-25

The owner then explicitly directed Codex to fix the marked round-shape losses and freeze T01 so T02 could start. The corrected crop runner now enforces both boundaries without merging the two meanings:

- T01 local growth-envelope groups still control local competition.
- Only the four previously accepted whole-board physical F.Cu components are eligible for T01 changes. Circles outside them remain exact round ORG cores.
- Within an accepted component, existing largest-radius local round priorities remain round; at most one eligible non-priority circle may use non-round growth. The smallest eligible source-radius companion is the deterministic slot choice, with source ID tie-break. The 1.5× cap remains hard.
- The fresh run found no non-round growth that passed the local constraints: it produced one round-priority enlargement (0.0187362032 mm² added), with the other circles retaining round source geometry. All saved circles passed the fresh-process geometry audit.

The exact T01 scene is frozen in `out/crop_dynamic_tasks/t01_owner_corrected_20261025_v11/`. Owner decision `t01_marked_area_fix_freeze_20261025` and profile `t01_marked_area_fix_frozen` bind the ORG source, report, policy, selection, scene, fresh audit, receipt, and viewport. This is visual-crop acceptance; T01 behavior remains `PARTIAL_0_OF_3`, and engineering/manufacturing status remains `NOT_ESTABLISHED`. See the bundle `SHA256SUMS.txt`.

T02 then consumed that exact scene as its baseline and protected its additions while processing the 81 source-bound ORG rectangle targets. The reproducible result is `out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v1/`:

- All 81 targets received an additive `GROW` proposal; 12.8022489688 mm² of copper was added.
- All saved candidate geometry passed source-core preservation, the strict 1.5× per-axis ceiling, shape validity, and hard-gap checks against original copper, other accepted T02 candidates, and frozen T01 additions.
- 21 later decisions changed in counterfactuals when one actual earlier accepted T02 addition was reverted to its ORG geometry. This is shared-implementation causal evidence, not independent-kernel verification.
- A second clean run at `t02_rectangles_crop_20261025_v2/` produced byte-identical target decisions, disposition table, final WKB, and SVG views.
- The review page is `out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v1/index.html`; four views show ORG, accepted T01, T01+T02, and T02 additions.

The run did not read EDIT geometry for construction. EDIT was used only for the already registered viewport. Native export, electrical correctness, EDIT equivalence, manufacturing acceptance and T03 remain `NOT_ESTABLISHED` or unauthorized. A ChatGPT summary-only audit is requested for this corrected T01/T02 slice; its response and limitations will be recorded here before local commit.

## Crop-boundary correction and composed-output audit — 2026-10-25

The summary-only ChatGPT audit returned `CONDITIONALLY SUPPORTED`: it supports deterministic T02 kickoff against the owner-accepted crop, but says T02 construction acceptance needs evidence that the loaded prestate is the exact accepted T01 scene, that the composition preserves T01 shape constraints, and that all changes remain inside the authorized target scope. The audit did not inspect local files or rerun tools.

I checked those boundaries locally. That check found a real defect in the first T02 candidate: five of the 81 source-bound rectangles intersected the crop, but their complete 1.5× envelopes crossed its left edge. Their growth would change copper outside the reviewed crop by 0.1326827581 mm². The v1/v2 outputs are retained as superseded historical experiments. The T02 eligibility rule now withholds a rectangle unless its entire 1.5× per-axis envelope fits within the crop, preserving the whole boundary shape unchanged.

Fresh runs v3/v4 therefore treat 76 rectangles and hold the five edge-crossing shapes unchanged. All 76 receive nonzero growth, with 11.5638089808 mm² added. Their saved candidates reconstruct the addition WKB exactly, satisfy per-axis caps and required gaps, and the complete additions remain inside the crop. The composed result is exactly the accepted T01 scene union those additions: measured T01 area loss is 0 mm², and the reported added-area and final-union areas reconcile within 1e-8 mm². The minimum measured T02-to-protected gap is 0.0200192674 mm.

The fresh T01 round-shape check covers all 87 detected sites: 86 remain exact source circles and the single T01 priority growth is exactly round; no non-round circle growth exists in this frozen scene. The saved pre-T02 render also reconstructs the exact owner-bound T01 scene. The new receipt is `out/crop_dynamic_tasks/t02_composition_audit_20261025_v2/t02_composition_audit.json`, with its own SHA-256 manifest. It is a fresh-process Shapely audit using the same geometry library as construction, not an independent kernel or manufacturing qualification.

The review page is now `out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v3/index.html`. Its bundle manifest verifies, and the result/replay artifacts match the clean repeat at v4. Focused tests and the separate ChatGPT audit are recorded in the final handoff. T02 remains experimental; no EDIT equivalence, electrical/native export, engineering/manufacturing acceptance, or T03 authorization follows.

## Half-ORG trace-corridor run and audit reconciliation — 2026-10-25

The prior crop-specific T01 candidate is superseded for this task: the owner marked-area correction is now bound to `out/crop_dynamic_tasks/t01_owner_corrected_20261025_v11/`, decision `t01_marked_area_fix_freeze_20261025`, status `ACCEPTED_VISUAL_CROP`. Its receipt binds the exact owner annotation screenshot (SHA-256 `63fc6bae7e437c0bc384856bf3498a34e37931e5fe3d841b506f085fa08e4d8c`) and scene (`073361e8f26c0127a218b4dfacfe9577937641c1c85d5d684f46f63dc075141d`). The earlier statement that this later materialization awaited owner review is stale. Acceptance remains visual-crop-only; T01 dynamic behavior is `PARTIAL_0_OF_3` and engineering/manufacturing status is `NOT_ESTABLISHED`.

T02 used that exact T01 scene and the v2 ORG target inventory. Inventory v2 enumerated 18,614 source records, each classified `GEOMETRY_AVAILABLE`; 15,858 supported F.Cu segment/arc records were available across the board. The crop intersected 1,032 supported F.Cu records: 76 eligible standalone rectangles, 5 full-cap crop-edge rectangles withheld unchanged, and 956 other protected contributions. The run reserved 371 target-to-trace interactions. For each target, the reservation census compared the complete 1.5× envelope plus the construction gap against all enumerated F.Cu segments/arcs, including features extending beyond the displayed crop. Unsupported native geometry, omitted records, and independently verified parser completeness remain outside this same-parser result.

The frozen corridor policy for new rectangle additions is `max(0.02002 mm, 0.5 × ORG surface-to-surface gap)`. The ORG measurement uses filled source geometries, including native segment/arc widths, and is not recomputed from a candidate. This is a minimum reserved corridor for the new addition; it does not require consuming exactly half the gap, alter traces, or establish electrical connectivity. For originally touching/overlapping rectangle-trace pairs, the zero ORG gap falls back to the 0.02002 mm future-growth floor. This geometry-only policy is experimental, not a manufacturing clearance rule.

The summary-only ChatGPT audit returned `CONDITIONALLY SUPPORTED — DETERMINISTIC EXPERIMENTAL T02 REVIEW CANDIDATE`. It identified the apparent minimum-gap discrepancy and requested source coverage and independence limits. Local reconciliation found the minimum reported protected-source gap, `0.020019279656865313 mm`, between rectangle source span `[1914825, 1915006]` and F.Cu arc source span `[1826934, 1827055]`. The same pair is subject to a `0.02002 mm` trace-growth reservation. Its represented distance is lower by `0.000000720343135 mm` (0.72 nm), while the declared curve-approximation bound and comparison tolerance are each `0.00001 mm` (10 nm). The implementation predicate is `measured_gap + 0.00001 >= required_gap`; for this pair that evaluates true. The minimum is also above the separately declared `0.020 mm` hard experimental gap. Therefore the outputs pass the implemented tolerance-bounded verifier; they do not establish a mathematically strict 0.02002 mm minimum. The summary audit did not inspect files or independently run tools.

The local CAM Agent registry pin initially did not match the newly recorded accepted T01 registry and owner-decision files (`TRUSTED_REGISTRY_HASH_MISMATCH`). The integrity constants now bind the exact `registry.json` SHA-256 `f5e0cac1e46e0d88da8f4952ea931e557544c197dfc9de1d0a0f8c00a62e433c` and `owner_decisions.json` SHA-256 `da2ac4ebb3523ac4111e0e3f9593b29be90e6fd04c2d3938fd4186920cbb7aa5`. No T01 scene, geometry, or decision content changed during this correction.

Fresh run v5 and byte-identical replay v6 are retained at `out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v5/` and `..._v6/`. The v5 run grows 76/76 eligible rectangles and adds `11.011274198844877 mm²`; five edge-crossing rectangles stay unchanged. It keeps the 1.5× per-axis ceiling and 371 half-ORG reservations. Composition audit v3 reports the exact accepted T01 scene as prestate, zero T01 area loss, zero unexplained composition difference, exact candidate-addition reconstruction, 87 T01 circles (86 unchanged exact round circles and one exact round enlargement), and the measured minimum gap above. Its fresh-process geometry audit uses the same Shapely library as construction, so it is not an independent geometry kernel.

Relevant ABI, crop-specific T01 and T02 regression tests pass (`71 passed, 9 subtests passed`), `git diff --check` passes for authored source/docs, and v5 output hashes verify. These support deterministic experimental construction and composition under the stated representations and tolerances. They do not establish EDIT equivalence, electrical correctness, native export, engineering/manufacturing acceptance, or T03 readiness. The live visual review is the v5 `index.html`; earlier v1–v4 bundles remain historical evidence and are not current results.
