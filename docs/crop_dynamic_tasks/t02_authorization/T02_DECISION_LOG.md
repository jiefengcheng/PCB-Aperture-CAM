# T02 authorization and crop amendment

**State:** Active bounded work, T02 only. Commit locally and stop before T03.
**Authorization source:** [`T02_ONLY_HANDOFF.md`](T02_ONLY_HANDOFF.md), supplied by the owner on 2026-10-24.
**Checkout at entry:** `838b2d5c4de5e687960f7f4b0b1ea8f3dac61dd5` (`main`).

## Owner sequence correction — 2026-10-25

The owner directed that **T01 must be applied to the newly selected crop before T02** and clarified: keep circles that are unique in a local circle-growth component exactly round; apply T01 growth only in components with multiple circles. This supersedes the earlier statement below that the accepted old T01 crop would be the T02 starting geometry in the new viewport. The previously accepted T01 run remains unchanged and bound to its original crop.

The initial direct-ORG T02 experiment is retained as history but **superseded for this sequence**; it is not the current result and must not be used as a T02 baseline. The new T01 crop candidate and review image are in [`out/crop_dynamic_tasks/t01_multicircle_new_crop_20261025/`](../../../out/crop_dynamic_tasks/t01_multicircle_new_crop_20261025/), with the review note at [`T01_NEW_CROP_REVIEW.md`](T01_NEW_CROP_REVIEW.md). T02 is held until the owner reviews this candidate.

## Owner correction — contained circles are not independent T01 sites — 2026-10-25

The owner clarified that circles inside rectangular or other copper shapes must not be treated as multi-circle component members: no independent shape edit is applied to those enclosed circles. The crop-specific policy excludes a source circle before grouping when its complete ORG geometry is covered by any different ORG F.Cu primitive; the circle remains exactly unchanged and is excluded from group multiplicity. Same-site aliases are not treated as enclosing objects. Circles with only a tiny uncovered area (at most `1e-12 mm²`) against an intersecting primitive are also held unchanged and omitted from multiplicity, but marked `containment-uncertain` rather than reported as fully contained. That conservative handling is provisional pending owner confirmation; it is not part of the explicitly stated fully-contained rule. Multiple primitives collectively covering a circle are not merged for this rule. The decision is derived from ORG geometry only. The prior new-crop candidates and pages remain historical and are not silently rewritten. The current candidate is `out/crop_dynamic_tasks/t01_containment_exclusion_20261025_v4/`; T02 remains held until the refreshed T01 scene is reviewed.

## Crop choice

The initial handoff referred to the T01 crop. The owner then supplied a larger image on 2026-10-24 and said it came from EDIT, asking to use a better crop. The owner requested the corresponding ORG crop. This later crop choice governs T02's full view while the T01 acceptance remains bound to its original reviewed crop.

- EDIT source: `dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/EDIT/top_layer.kicad_pcb`
- EDIT source SHA-256: `ec141305a9d93db87709124ba5aa9378135485ae5458f019e47a342d099496a5`
- ORG source: `dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top.kicad_pcb`
- ORG source SHA-256: `850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0`
- Owner image SHA-256: `cb1d008e1d6cb5e0271b3aeef035133c7cc192da422b5f257a683fde90df764f`
- Registered ORG viewport, mm: `[16.44342222222222, -16.556731666666664, 27.198977777777777, -8.645620555555553]`
- F.Mask-only fit: 219 unique board-wide inliers, 58 inside the crop, zero fitted rotation/translation, zero maximum residual at 0.001 mm matching tolerance. The screenshot locator itself has at least 0.0223 mm pixel uncertainty plus crop-edge effects.

The screenshot is used only to locate the display viewport. Constructor inputs are ORG source geometry, the reviewed new-crop T01 candidate once owner-reviewed, and the declared T02 policy. The `registration.json`, source crop views, local landmark pairs and screenshots are retained in `out/crop_dynamic_tasks/t02_crop_registration_20261024/`.

## Accepted T01 input

The historical owner decision is `t01_visual_crop_acceptance_20261024`, status `ACCEPTED_VISUAL_CROP`, source hash as above. Its exact run remains `out/crop_dynamic_tasks/t01_owner_review_20261024_v2/`; the owner decision binds the report, policy, scene, and audit. The measured T01 dynamic status remains `PARTIAL`. Its 51 saved final contours are outside this viewport, so that historical run alone leaves the selected crop unchanged. The newly computed crop T01 candidate is separate evidence and awaits review.

## Frozen feature boundary and experimental policy

The ORG native inventory found 1,032 supported F.Cu occurrences intersecting this viewport: 631 segments, 222 arcs, 96 circles, and 83 filled polygon objects. Of those polygons, 81 are source-bound rectangles by their vertex geometry and two are other contours. The ORG source has no native footprint pad records, net labels, or reference identities for these shapes. T02 therefore calls the 81 objects **geometric rectangular copper features** and preserves their exact source spans. It does not claim they are electrical pads or identify nets. The other source contributions remain protected; unsupported or ambiguous records remain separate dispositions.

`contracts/crop_rect_t02_policy.json` freezes an experimental 1.5x per-axis cap, 0.02002 mm construction buffer and 0.020 mm hard experimental gap, using the accepted T01 numerical values. The factor is a safety bound for this experiment, not a manufacturing rule. Targets are ordered by source center Y, then X, then source identity. Each proposal sees all original F.Cu and additions accepted earlier in this pass. Existing copper is additive-only: original contributions and overlap supports stay intact.

## Execution log

- Refactor parity prerequisite: `out/crop_dynamic_tasks/t02_prerequisites_20261024/baseline_qualification.json`, `PASS_REFACTOR_PARITY` (330 geometry hashes, 51 site decisions; algorithmic replay kept distinct from frozen owner materialization).
- Read-only crop registration: `out/crop_dynamic_tasks/t02_crop_registration_20261024/comparison_report.json`.
- Initial proposal attempt: all 81 candidate contours were generated and written, but the saved-output audit was interrupted after a full-board union per target proved too costly. Its output files and interruption details are retained under `retained_attempts/attempt_01_interrupted_during_saved_output_audit/`. It is not acceptance evidence.
- Superseded direct-ORG T02 run: retained in `out/crop_dynamic_tasks/t02_crop_registration_20261024/`; do not use as the current baseline.
- Prior new-crop T01 candidate: `out/crop_dynamic_tasks/t01_multicircle_new_crop_20261025/`; superseded by the owner containment correction and preserved as history.
- Containment-corrected T01 candidate: `out/crop_dynamic_tasks/t01_containment_exclusion_20261025_v4/`; 44 topologically contained circles and three uncertainty-held circles are excluded before grouping; the remaining 40 comprise 22 singletons and six groups with 18 members. Fresh-process saved-geometry audit passes. Candidate visual review and the policy disposition for three uncertain sites remain pending.
- T02 execution: **held pending owner feedback on the new-crop T01 image**.

## Status limits

No native export, net or electrical correctness, manufacturing approval, or equivalence to EDIT has been established. T01 owner acceptance remains visual-crop acceptance only. This decision log records the explicit T02 scope and later crop selection; it does not accept the new T02 result.

## T02 checkpoint update — 2026-10-25

See [`T02_PROGRESS_CHECKPOINT_20261025.md`](T02_PROGRESS_CHECKPOINT_20261025.md) for the evidence record. The refactor/parity prerequisite passes for the historical owner-accepted T01 materialization only. The selected-crop ORG inventory passes provisional native rectangle eligibility checks (81 candidates; 951 protected records), and seven focused T02 tests pass. The exact source, target-set, and output-manifest bindings are recorded there and in `out/crop_dynamic_tasks/t02_org_inventory_20261025/`.

The required T01 input for T02 remains unavailable: the historical accepted scene is spatially disjoint from the selected larger crop, and no accepted T01 materialization for that crop is bound to the current shape allowance. The four accepted physical-component findings do not accept a constructed crop result. This is an input-artifact qualification failure, not a new human approval gate for the parity work. T02 proposals were not run. The summary-only ChatGPT audit supports these distinct inventory-PASS and proposal-BLOCKED statuses, with an explicit limitation that it did not inspect or rerun local evidence.

## Fail-closed admission guard — 2026-10-25

The runner now rejects the known disjoint accepted-scene/crop pairing before any target construction. It binds the owner decision, profile, report, policy, selection, scene, audit and publication receipt. Recheck receipt: `out/crop_dynamic_tasks/t02_baseline_admission_20261025_v2/baseline_admission.json`. Current pre/post refactor parity is independently re-executed at `out/crop_dynamic_tasks/t02_baseline_recheck_20261025_v4/` and remains `PASS_REFACTOR_PARITY`; the selected-crop baseline itself is `BLOCKED_ACCEPTED_T01_CROP_COVERAGE`. See the progress checkpoint for exact viewport bounds, hashes, test commands and the absence of a T02 result page.

## Owner-marked T01 correction and T02 execution — 2026-10-25

The owner asked to fix marked round-shape losses and freeze T01 for a deterministic T02 kickoff. The crop policy and runner now preserve exact round source cores outside the four accepted whole-board physical components, retain largest-radius T01 round priorities, and allow at most one eligible non-priority circle per accepted component to use non-round growth. T01 envelope groups remain the independent local-competition relation. No non-round candidate survived as an accepted growth in the frozen scene; one round-priority circle grew. The final T01 scene is hash-bound in owner decision `t01_marked_area_fix_freeze_20261025` and profile `t01_marked_area_fix_frozen`, at `out/crop_dynamic_tasks/t01_owner_corrected_20261025_v11/`.

The runner now admits that exact scene and adds its positive geometry to T02's protected neighborhood. Run `out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v1/` contains all 81 source-bound rectangle decisions, 21 current-neighbor counterfactual pairs, four crop views, saved-output checks, and a byte-identical replay receipt against `v2`. The full state, hashes, limitations, and review page are recorded in [`T02_PROGRESS_CHECKPOINT_20261025.md`](T02_PROGRESS_CHECKPOINT_20261025.md).

This closes the crop-input blocker and starts T02 only. T01 behavior remains partial; T02 is an experimental geometric result. No native export, electrical/manufacturing qualification, or T03 authorization follows.

## Crop-boundary and composition correction — 2026-10-25

The summary-only ChatGPT audit supports deterministic T02 kickoff conditionally and recommends local proof that the accepted T01 scene is actually the T02 prestate, protected T01 geometry survives composition, and T02 edits stay within the reviewed crop and authorized rectangles. The audit explicitly disclaims repository inspection or independent verification.

Fresh local verification found five of the initial 81 provisional rectangles had 1.5× envelopes crossing the crop boundary. That candidate’s additions extended 0.1326827581 mm² outside the reviewed viewport, so v1/v2 are superseded experiments and remain preserved. Policy and classifier changes withhold those five entire rectangles unchanged; no crop-edge clipping or external edit is performed.

The corrected fresh run v3 admits 76 rectangles; repeat v4 is byte-identical on the receipt-listed artifacts. A fresh-process composition audit passes exact T01 prestate/render binding, all 87 T01 circle shape classes (86 unchanged round cores; one exact round priority enlargement; zero non-round growth), exact reconstruction of all T02 additions from saved target candidates, crop containment, T01 preservation, area reconciliation, caps, and minimum protected gap. Detailed measurements and qualifications are in the progress checkpoint and `out/crop_dynamic_tasks/t02_composition_audit_20261025_v2/`. This same-library geometry audit does not establish an independent kernel, EDIT equivalence, electrical/manufacturing acceptance, or T03 readiness.

## Current authorized slice — 2026-10-25

The checkpoint section “Post-commit v7/v8 replay” supersedes the preceding run status. The owner-marked T01 round-loss correction is accepted and frozen at `out/crop_dynamic_tasks/t01_owner_corrected_20261025_v11/`; T02 v7/v8 apply the frozen 1.5× rectangle cap and tolerance-bounded `max(0.02002 mm, 0.5 × ORG surface gap)` growth reservations beside native traces. The checkpoint records the summary-only ChatGPT verdict, exact 0.72 nm gap-floor reconciliation, parser census, review path, test evidence, and limits. T02 remains an experimental review candidate; no owner acceptance, engineering/manufacturing approval, or T03 authorization is claimed.
