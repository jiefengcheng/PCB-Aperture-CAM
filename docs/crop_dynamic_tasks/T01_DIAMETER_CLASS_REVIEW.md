# T01 shared-diameter trial — owner review, PARTIAL

Open http://127.0.0.1:8783/ for the current local replay. The delivered bundle is `out/crop_dynamic_tasks/t01_diameter_classes_20261024_v3/`. Original inputs, historical T01/R1 and the earlier continuous-factor trial are preserved.

## Mental model and review controls

Choose a common physical **envelope diameter** for nearby sites, bounded by each site's strict 1.5× original-radius ceiling. A round priority must fit completely; a companion may recess optional growth against actual copper. A tight priority no longer transmits a small growth factor to its roomy companion. A clipped contour is not itself a circle of the nominal diameter.

Use **Previous result** to compare the preceding trial at the same source coordinates; **Size classes** shows the class colours, with the numerical legend below. Grey contours made no additions. Seven provisional bands are declared: 0.0380, 0.0761, 0.2749, 0.2999, 0.3374, 0.3749, 0.4499 mm. The last band is unused in this crop. These are ORG-derived experimental bands, not manufacturing standards or EDIT-fitted sizes. Forty-one sites receive class proposals: 39 grow and two tiny proposals remain unchanged after clipping. Ten sites KEEP their exact source target, for 12 final unchanged sites.

The eight marked-location cards carry the original circle identity/center from the bound source. Screenshot markers are locators, not executable IDs. The case-6 card is expanded by default.

## What changed and what remains open

| Owner mark | Site | Previous envelope Ø mm | New envelope Ø mm | Added-area change mm² |
|---|---|---:|---:|---:|
| 1 | S41 | 0.283235 | 0.2749 | −0.003654 |
| 2 | S47 | 0.288686 | 0.2749 | −0.006102 |
| 3 | S46 | 0.276901 | 0.3749 | +0.043788 |
| 4 | S42 | 0.300472 | 0.3374 | +0.017498 |
| 5 | S45 | 0.307008 | 0.3749 | +0.036360 |
| 6 | S31 | 0.277592 | 0.3374 | +0.017350 |
| 7 | S04 | 0.249940 | 0.3749 | +0.052022 |
| 8 | S07 | 0.256992 | 0.3749 | +0.050817 |

Six marks improve. **Marks 1 and 2 remain OPEN**: their full-round requirements and discrete bands lead to smaller contours. This is not full satisfaction of the growth request. Overall actual added-copper union is 1.045489 → 1.283577 mm² (+22.8%); 25 sites gain more and 21 less than the preceding trial. More total copper does not establish better expert equivalence.

Case 6 uses the enlarged-circle square to guide one recess, not replace copper with a square. The primary actual conflict is selected by greatest overlap with optional-envelope growth; a stable source identity breaks ties. Its nearest applicable point selects the facing side of the −45° inscribed square. Only optional copper in that outward lobe is removed; all ordinary obstacle clipping follows. Core, 1.5× cap, source traces and fixed attachment zones remain protected.

S31 is the only selected circle in its original physical component. Its requested recess is an explicit exception to the prior full-round component rule: **25 round reservations plus one recess exception**, not a claim that the previous 26/26 rule passes. The square-disabled control holds target size, input scene revision, ports and ordinary clipping fixed; enabling the square changes 0.003454510 mm². This demonstrates an operator effect, not expert equivalence or an evolving-companion event.

## Verification and audit boundaries

All 51 unique sites / 53 source aliases are accounted for. The fresh-process verifier reopens saved geometry and all 17,849 F.Cu source objects; it verifies original cores, caps, inscribed vertices, priority contours/exception, fixed source ports, assembled 0.020 mm hard-gap checks, counterfactuals and the square-enabled/disabled supporting-half-plane construction. It shares the native parser and Shapely kernel and is same-author verification. All 29 focused tests pass, including mandatory-control rejection and class/cap mutations. All 70 immutable assets verify. Same-policy replay yields equal hashes at every site.

There are 17 reservation-responsive sites / 30 counterfactual pairs, but **zero evolving-companion effects against the target of at least three**. The fair static comparator is identical and has zero assembled violations. Do not count reservation responses as those missing events. Outside-display-V additions are 0.054669 mm², within complete selected 1.5× cap envelopes; the separate outside-frame view discloses them.

ChatGPT's original **PCB CAM Handoff Review** thread gave `CONDITIONAL — READY for owner review with open concerns`. This is a **summary-only desk audit**, with no local file/visual inspection or tests. It leaves S41/S47, the case-6 exception and missing evolving effects explicit. Cursor remains `NOT_RUN: CHANNEL_UNAVAILABLE`. No native board export, electrical, DRC, manufacturing or final owner acceptance is established. No T02+ work was run.

## Reproduce and inspect

```bash
.venv/bin/python -m unittest tests.test_crop_diameter_classes tests.test_crop_balanced_t01 tests.test_crop_balanced_t01_publication tests.test_crop_balanced_capped_growth tests.test_crop_square_neighbor_experiment -v
.venv/bin/python tools/run_crop_diameter_classes_t01.py --output out/crop_dynamic_tasks/t01_diameter_classes_replay_01
.venv/bin/python tools/audit_crop_balanced_t01.py out/crop_dynamic_tasks/t01_diameter_classes_replay_01
.venv/bin/python -m http.server 8783 --bind 127.0.0.1 --directory out/crop_dynamic_tasks/t01_diameter_classes_20261024_v3
```

The output directory must be fresh. Construction/presentation require the existing hash-bound previous v4 bundle for comparison and fail if absent or changed. This is a bounded crop experiment, not a general-board tool. `src/crop_diameter_classes.py` contains sizing/recess logic; the existing execution, audit and renderer are reused. Policy: `contracts/crop_diameter_classes_t01_policy.json`.

Evidence within the delivered directory: `report.json`, `selection.json`, `policy.json`, `fresh_audit.json`, `publication_receipt.json`, `chatgpt_audit_prompt.txt`, `chatgpt_audit_raw.txt`, `chatgpt_desk_audit.json`, `tests.log`, `SHA256SUMS`. Execution source snapshots are retained in `review_source/`; later audit/presentation/legacy-factor reporting changes have exact snapshots and hashes in `post_execution_source/` and `post_execution_changes.json`. No final geometry was changed by those post-execution edits. Earlier attempts are retained and described in `retained_attempts.json`.

The owner can now review the common-size result, especially case 6 and the two unresolved round sites. No accepted outcome or next-stage authorization is prefilled.
