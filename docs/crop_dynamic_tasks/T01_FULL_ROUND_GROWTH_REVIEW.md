# T01 full-round growth recovery — PARTIAL, owner review

Current replay: http://127.0.0.1:8783/

Bundle: `out/crop_dynamic_tasks/t01_round_priority_promotion_20261024_v3/`

The owner explicitly chose **Keep these priorities fully round** for the eight new marks. All eight retain complete round contours. No new recess exception, size-band change, source-port widening, clearance relaxation or cap increase was introduced. S31 retains only its earlier separately requested square-guided exception; it is not mark 6 in this new annotation set.

## What changed

The previous allocator reduced both competing round reservations at once. After that safe allocation, some circles could advance to another existing size band without changing any other target. The new pass recovers those opportunities: it considers the next band, checks original copper and fixed ports, other round reservations and the retained A-square/B-envelope bounds, then selects the feasible step with the largest round-area gain and a stable source-ID tie break. It repeats until no such step remains.

This is a **maximal greedy allocation with other targets held fixed**, not a global optimum. It does not prove that jointly reallocating or shrinking other features could never satisfy a different preference. Desired shared physical diameters, the strict individual 1.5× ceiling and every original core remain protected. Companion contours are reprocessed against the larger round reservations, so some optional companion growth decreases.

## Your new marks

| Mark | Source site | Previous Ø mm | Current Ø mm | Why the next class is blocked |
|---|---|---:|---:|---|
| 1 | S08 | 0.2749 | 0.2749 | S12 full-round reservation |
| 2 | S49 | 0.29998 | 0.29998 | Another round reservation and auxiliary square-side bound |
| 3 | S47 | 0.2749 | **0.2999** | Next 0.3374 conflicts with original copper / round reservation |
| 4 | S48 | 0.2999 | **0.3374** | Next 0.3749 conflicts with original copper / round reservation |
| 5 | S50 | 0.29998 | 0.29998 | Current round reservation and square bound on its companion |
| 6 | S41 | 0.2749 | 0.2749 | Next 0.2999 approaches original nonattached copper within about 0.011707 mm |
| 7 | S12 | 0.29998 | **0.3374** | Next 0.3749 conflicts with source copper / round reservation / square bound |
| 8 | S10 | 0.29998 | 0.29998 | Next 0.3374 approaches an original nonattached arc within about 0.005561 mm; square bound also applies |

The hard experimental gap is 0.020 mm. **Three marked sites improve; the other five concerns remain open.** All marked priorities stay fully round. Globally six priority circles gain more copper, four companions lose some optional growth, and 41 sites are unchanged relative to the previous trial. Actual added-copper union increases from 1.283577 to 1.378447 mm². Forty-two of 51 sites have additions, with nine unchanged from source.

## How to review

Open each marked card. It contains the previous and current result and **Why the next round size stops**. That last image is a rejected diagnostic: blue is the next circle, green the selected contour, and pink its intrusion into the protected gap. Its context uses current round reservations and original companion copper, matching the target-sizing decision, not an unrelated historical scene. A square-side bound can block a class even without a visible copper collision; that is labeled separately. Source identities, raw gaps and bound groups remain in the receipts.

The fixed display crop remains unchanged. Complete edge circles, including the partly visible S49/S50, are processed from full source geometry. Outside-display-V additions are 0.070456 mm² within the declared complete selected 1.5× cap union; the separate outside-frame view shows them.

## Evidence and acceptance limits

All 70 immutable assets and the bound ORG source verify. Thirty-two focused tests pass. The fresh-process same-author verifier checks all 51 accepted sites / 53 aliases against 17,849 F.Cu records, all 25 round priorities, original cores, fixed ports, caps, gaps, the prior S31 square control and 24 rejected next-round-class controls. Every remaining next class has a reproduced source, reservation or square-bound blocker. Missing next-class proof prevents publication. Parser and Shapely are shared, so this is not independent interpretation of PCB semantics.

The same-policy replay reproduces all site hashes. The fair static comparator is identical, with zero assembled violations. Eighteen companions respond to round reservations in 34 counterfactual pairs; **zero evolving-companion effects** are established against the target of at least three. Overall T01 remains **PARTIAL**, with owner judgment pending. No expert-equivalence, native export, electrical, DRC, manufacturing, T02+ or independent Cursor acceptance follows.

Exact code/policy/selection/geometry identities are in `report.json` and `review_source/`; new negative diagnostic geometry and hashes are bound by `fresh_audit.json`. The UI is bound by `publication_receipt.json`. Other evidence includes `tests.log`, `retained_attempts.json`, the same-thread summary-only ChatGPT review when completed, and `SHA256SUMS`. Earlier failed/incomplete diagnostic attempts are retained; accepted geometry in all three attempts is identical.

```bash
.venv/bin/python -m unittest tests.test_crop_diameter_classes tests.test_crop_balanced_t01 tests.test_crop_balanced_t01_publication tests.test_crop_balanced_capped_growth tests.test_crop_square_neighbor_experiment -v
.venv/bin/python tools/run_crop_diameter_classes_t01.py --round-priority-promotion --output out/crop_dynamic_tasks/t01_round_priority_promotion_replay_01
.venv/bin/python -m http.server 8783 --bind 127.0.0.1 --directory out/crop_dynamic_tasks/t01_round_priority_promotion_20261024_v3
```

Use a fresh output directory. The comparison requires the preserved, hash-bound previous shared-diameter bundle. No historical result is rewritten or accepted retroactively. Stop here for owner review; no new policy choice or human acceptance is prefilled.
