# Why the original C03 coverage does not survive unchanged

This read-only diagnosis follows the owner's 2026-11-04 request to investigate
T0–T5 coverage during new-stage development. It changes no treatment or eligibility.
T04 repair remains deferred. Evidence is in
`out/lacie_work/evidence/stage_c_c03_spatial_20261104T043912Z/`:
`STAGE_COVERAGE_AUDIT.json`, `COVERAGE_CAUSES.json` and the visual comparison.

The earlier and current cases share source SHA-256
`850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0`.
Source IDs include original byte spans. The earlier C03 proposal/status records
and subsequent owner-review history remain unchanged. They are functional
references, not automatic native, electrical or manufacturing acceptance.

## Main finding

The loss is primarily a mismatch between **the earlier stage's intended target
and shape contract** and **the generic native adapter's admitted objects and
policy**. It occurs before spatial-query optimization. Complete source accounting,
successful reconstruction and actual export can all pass under the new rules
without establishing that the earlier intended treatments were retained.

The earlier U04 reconciliation report acknowledged different policies and counts.
This audit adds per-source joins and positive-extent comparisons; aggregate counts
such as 221 versus 153 circles or 47 versus 46 rectangles hid individual losses.

| Stage | Source-bound finding | First cause/boundary |
|---|---|---|
| T0, interpreted here as source intake | All 17,849 source occurrences remain; no C03 occurrence loss found | No separate T00 treatment contract found. Qualified layers and byte-preserved excluded companions remain distinct. |
| T01 | Of 121 formerly positive circles, 110 still grow and 11 do not. 56 of the 110 grown targets do not contain the full earlier target extent. | Different crop, palette, priority/companion shape family, grouping/selected pool and clearance semantics. |
| T02 | Of 45 formerly positive rectangles, 43 still grow; two are excluded by current crop-envelope admission. All six old inclusive merges have identical WKB. | Fresh inset crop plus whole 1.25× maximum-envelope admission, before search. |
| T03 | Both old C03 and current native C03 move zero traces. Current checks cover all 15,858 trace occurrences and 1,332 trace/land pairs. | No case-specific loss demonstrated. General route movement remains unsupported and halts, so retention is not a router capability claim. |
| T04 | Of 94 formerly positive local route records, 80 are held and 14 widen. All 14 current width groups are singletons. | Local visible runs were replaced by complete native parents/groups; protections and whole-group crop checks exclude them before width search. |
| T05 | Earlier rejected native result grew nine of 11 selected routes; the corrected result restores 85/85 reference-positive clusters and 162/162 required attachments. | Earlier inheritance of T04 admission, complete-window exclusion and covered-land omission. Independent source-bound local attachment obligations now address this. |

These denominators are deliberately different: source occurrences, selected
lands, local route records, complete native parents/groups and attachments must
not be substituted for one another. More additions elsewhere do not compensate
for a missing required treatment.

## T01: a different algorithmic contract

The earlier `tools/run_c03_round_class_stage.py` constructs full round circles
from the supported target palette, visits them in source centroid Y/X/ID order,
and checks the complete visible-surface scene. Its stored result says all round
shapes were retained.

The current `ImageCropAdapter` delegates to the generic `CropAdapter` and
`crop_balanced_t01.execute`. That implementation chooses source-component round
priorities, constructs clipped companions, uses source attachment ports, reserves
priority geometry first and applies the A-square/follower-envelope bound. These
rules are intentional in that family, but they are not the earlier C03 round-only
contract. `GROW_COMPANION` does not mean a complete circle at its recorded radius.

Among the 121 old positives:

- One is excluded at `KEEP_CROP_BOUNDARY` (C028).
- Nine are `KEEP_PRIORITY`: eight have recorded round-clearance/demotion reasons;
  C130 has no admissible current diameter class.
- One is `KEEP_CONSTRAINED` (C202), with `A_SQUARE_ENVELOPE_BOUND` recorded.
- Of the targets that grow, 51 companions and five round priorities lack some
  earlier target extent. The other 54 contain it within the measured comparison.

The current palette is **0.038, 0.0761, 0.2749, 0.2999, 0.3374, 0.3749, 0.4499 mm**.
C130's original diameter is 0.50012 mm. The old C03 target admits 0.6251 and
0.7501 mm and selected growth; the generic palette admits none above its core.
This is a concrete palette-coverage gap, not a failed clearance optimization.

The 67 old-positive records with a missing per-target extent include the 11
non-growing records and 56 growing records. Six differences are below 1e-6 mm²;
their exact areas remain recorded without any tolerance waiver. This comparison
is **per-target stage-model geometry**, not a claim that all 67 create visible
missing copper in the final board union or that all are equally important.
Sampling/phase and shape-family differences require separate interpretation.

## T02: larger aggregate coverage concealed two omissions

R304 and R305 were previously positive but now have `KEEP_CROP_BOUNDARY`. The
current code requires the **entire 1.25× rectangle cap** to fit the current inset
window before the solver runs. A smaller feasible growth is not searched after
that exclusion. The earlier provisional window and fresh located window differ;
the latter also has a 0.01719377162629758 mm edge uncertainty inset.

Of the other 43 old positives, 35 have exact candidate WKB and eight contain the
earlier rectangle with additional growth. All six inclusive member sets and
resulting WKB match exactly. The current 47 grown total includes other records
and does not prove retention of all 45 earlier positive rectangles.

T02 also consumes the altered T01/T04 predecessor. Its larger extents cannot be
attributed solely to T02 optimization: changed upstream copper changes clearance
opportunities. No counterfactual stage rerun was performed to isolate those effects.

## T04: admission and identity granularity

The 97 historical local route records map unambiguously to 91 complete native
parents. Of the 94 positive local records, 38 are now held by reviewed bulk roles,
30 by complete parallel-group crop admission, and 12 by complete-path crop
admission. Only 14 remain admitted. All these exclusions precede width search.

Preserving existing bulk copper was propagated to an entire complete parent or
group when any member is protected. A historical local view may therefore have
been growable while its longer parent is not admitted under today's uniform
whole-path rule. This explains the grouped parallel traces and round-terminal
approaches that stayed thin. The 1.5× scalar ceiling is not the cause of their
missing growth: most never reach a width trial.

These observations do not authorize splitting a path, overriding bulk protection
or broadening crop permissions. Reconcile identity and permission requirements
first. The existing 80-record held set and all old failed/rejected jobs stay intact.

## T05: an example of the needed separation

The earlier native materialization used T04's admitted trace objects, reclassified
other traces as fixed, and required complete paths/windows to fit the crop.
It also removed covered lands from junction membership. Preserving a source
contribution was thereby conflated with denying local additive treatment.

The adopted attachment contract separates complete-path width authority from
source-bound local junction views, preserves covered lands in radius/window
construction, and freezes an independent 162-attachment positive denominator.
Its native export checks verify each required attachment's approved extent.
That restores the stated functional coverage, without asserting equality to all
historical patch shapes or fixing upstream T01/T02/T04 differences.

## Why the checks did not stop these differences

Existing source coverage counts account for every occurrence, including protected
and excluded ones. Existing reconstruction verifies the candidate against the
current admitted plan. Native correspondence verifies that this candidate was
actually written/exported. Those are necessary checks, but none alone compares
each original design obligation with the new plan's admitted treatment set.

T05 now has that independent denominator and per-attachment requirement. Equivalent
stage-specific coverage obligations have not yet been reconciled for T01/T02/T04.
The present audit is diagnostic, not a newly implemented operator gate. A future
fix must preserve existing guards while explicitly addressing every omitted or
changed reference obligation. It must not relabel a narrower plan as full original
coverage merely because all its own checks pass.

Stage C leaves **COVERAGE_RECONCILIATION_REQUIRED** explicit. Its exact parity with
Stage B is performance-refactor evidence only. No geometry/eligibility fix, new
native job or acceptance promotion was performed. Stage A's `.DS_Store` custody
FAIL remains; owner PENDING_USER, independent NOT_RUN, electrical/manufacturing
NOT_ESTABLISHED.
