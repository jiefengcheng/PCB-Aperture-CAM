# C01 circle-interaction coverage review — 2026-11-04

> **Correction to the explanation:** Cross-crop comparison exposed this defect;
> it is not the production acceptance mechanism. The root defect is substitution
> of a different construction policy under the T01 stage name. See
> [T01 contract divergence](../../out/lacie_work/evidence/circle_interaction_review_20261104T132805Z/T01_CONTRACT_DIVERGENCE_CORRECTION.md).

**FAIL_C01_INTERACTION_COVERAGE_REVIEW.** This is a new functional review finding,
not a rewrite of any historical native receipt. Geometry repair is outstanding.
No source, geometry, acceptance or frozen evidence was changed for this review.
C028/R304/R305 remain blocked. Branch: `codex/c03-coverage-recovery`.

## Verified findings

The supplied `after.png` exactly matches the retained
`out/crop_dynamic_tasks/c01_t05_spindle_trial_20261030_260/after.png`:
SHA-256 `e4878b65435da38119e36333ba1bce328cc2ac99b6a40295274eb320851d6802`.
Its retained WKB, source memberships and predecessor records provide the
comparison; screenshot pixels were not reconstructed into copper.
All compared cases bind the same original native source SHA-256
`850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0`.
The common C01 viewport is [1.2858444444, -15.6870777778, 4.5080666667,
-12.9759666667] mm, within the retained C03 window.

| Question | Evidence |
|---|---|
| Are earlier T01 circle shapes preserved? | 35 of 51 C01 source-bound circle shapes have missing extents already in current C03 T01 and in the final native result. |
| Which earlier behaviors are affected? | 23 GROW_COMPANION and 12 ROUND_GROW_PRIORITY records. |
| Was the old C01 inventory fully represented? | No. Six C01 sites are absent from the C03 obligation list, including aliases: S01, S02, S21, S31, S36, S39. Four had prior GROW_COMPANION decisions; two were KEEP. Absence from the list is distinct from visible copper loss. |
| Did later stages delete current T01 circles? | No. All 51 current source-circle contributions are contained in the final native copper under the recorded diagnostic comparison. The functional gap starts in the substituted T01 result. |
| Did matching contact identities prove shape coverage? | No. All 43 C01 positive circle-contact identities match current C03 T05 records, while 22 of 23 C01 positive spindle patches still have missing copper. |

The missing frozen-C01 circle-union area in the final native copper is
0.5965768942 mm². The missing C01 spindle-addition union is 0.0939792478 mm².
The missing complete C01 supplied-reference union is 0.7034296326 mm²; it also
includes upstream width/other geometry differences. These are diagnostic
measurements using a 0.00001 mm display deadband, not new native qualification
or clearance tolerances. The complete current T01 context has a residual
6.07e-11 mm² diagnostic sliver against native copper; this is not included in
or used to excuse the 35 large circle-extent gaps. Per-circle later-stage
missing counts are zero.

The attachment's retained record labels the wider closing as T05 experimental
spindle treatment over frozen T01/T04, with T02 not applied. That distinction
does not dismiss the user's observation: the separate frozen C01 T01 predecessor
independently proves the 35 circle-shape coverage regressions.

## Root cause in implementation

1. `src/c03_round_adapter.py:34` explicitly selects a C03 **round-only** family
   that excludes generic priority/companion clipping and C01 square/recess
   directives. Lines 221–229 return empty interaction events and zero neighbor
   and evolving-companion response sites. This is a functional policy change,
   not merely a native input/contact-binding adjustment.
2. `src/c03_recovery.py:109` validates a pinned C03-only inventory of 153 circle
   records / 121 positives. `required_rounds` at line 184 rebuilds full circles
   from those diameter parameters. The coverage assessment checks those shapes;
   it does not test preservation of the C01 interaction-aware shapes. Six C01
   sites are outside that denominator.
3. `tests/test_c03_recovery.py:66` explicitly rejects clipped companion geometry
   as insufficient for the new full-round contract. That test is coherent for
   the narrower contract, but there is no C01-overlap regression requiring the
   earlier interaction geometry to survive. The tests therefore did not expose
   this incompatible substitution.
4. U05's required-contact identities are derived from the C03 reference in
   `src/u05_board/reference.py:37`. `src/u05_board/audit.py:27` requires 162
   attachments, but this inventory and its current-scene treatment predicates
   do not require the complete historical C01 patch extents. Finding all 43
   overlapping C01 contacts therefore does not establish their shape coverage.
5. Native reconstruction/export and downstream preservation correctly establish
   correspondence to the newly generated candidate and retained predecessor.
   They cannot establish retention of earlier geometry omitted before that
   predecessor was created. Two fresh evaluations of the same narrow contract
   do not supply the missing independent functional acceptance oracle.

## Why my coverage review missed it

I accepted the C03-specific diameter/width/attachment inventories as the working
coverage universe. I did not reconcile the overlapping frozen C01 interaction
requirements against that universe. I then concentrated the next recovery on
the 80 held width obligations and failed to carry the non-width regressions into
the completion assessment. This repeats the same underlying error as the width
issue: verifying a narrowed supported family without proving that it retains
all of the intended historical treatment.

The source and numeric/native integrity checks were real, but I gave their
passing counts more weight than the missing functional comparison. This was an
implementation-contract and review failure, not missing user instructions and
not a limitation established by the three blocked boundary targets. The earlier
120/121 C03 round-positive count remains a narrow stored result; it does not
establish C01 circle-interaction preservation. The 67/94 width result remains
separate and does not close this new functional failure.

## Required correction to acceptance evidence

Restore one canonical, immutable T01 construction contract and complete native
source-derived target/interaction discovery for every operational route. Crops
may select a view or constrain write permission; they must not select a different
construction algorithm or sizing/interaction rules. Downstream stages must bind
and preserve that canonical T01 output. Unsupported cases must halt rather than
substitute a case-specific T01 implementation. New implementation hashes and
self-consistent reconstruction do not establish equivalence to approved behavior.

Production acceptance must verify canonical per-source geometry, policy identity,
complete source/interaction accounting and unchanged downstream contributions
without requiring any historical crop. Existing C01/C03 examples are useful
regression evidence only. Preserve all existing clearance, source, reconstruction,
corruption and actual-export checks and the blocked C028/R304/R305 obligations.
Restoration and native requalification remain outstanding.

## Evidence

- [Comparison figure](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/evidence/circle_interaction_review_20261104T132805Z/C01_circle_interaction_review.png)
- [Full per-circle and per-contact measurements](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/evidence/circle_interaction_review_20261104T132805Z/REVIEW.json)
- [Functional failure decision and omitted sites](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/evidence/circle_interaction_review_20261104T132805Z/FUNCTIONAL_REVIEW_DECISION.json)
- [Compact metrics](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/evidence/circle_interaction_review_20261104T132805Z/SUMMARY.json)

Owner PENDING_USER; independent NOT_RUN: CHANNEL_UNAVAILABLE;
electrical/manufacturing NOT_ESTABLISHED. Native jobs run for this review: zero.
