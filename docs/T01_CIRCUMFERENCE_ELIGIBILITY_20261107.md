# T01 circumference-only circle eligibility — isolated revision

The owner replaced the partial-area overlap rule: a circle is eligible for
ordinary growth checks only when **at least 70% of its original circumference is
exposed**. This is not a requirement for 70% buried circumference, and the area
test is not retained alongside it. Existing full-containment KEEP remains a
separate unchanged source-preservation rule.

## Measurement and policy

contracts/t01_circle_exposure/settings.json registers the provisional
minimum_exposed_circumference_fraction_for_growth parameter at 0.70. The raw
registry, hash, comparison direction and value are captured in each canonical
job marker and allocation. Changing this parameter changes new job policies;
stale policies reject. No percentage tolerance is added: exactly 70% is eligible,
and a value below it is KEEP. Eligibility is permission to attempt growth, not
a guarantee that a larger contour fits all other checks.

The source circle's original analytic center and radius define its circumference.
Intersections with the complete original finite-copper union split it into
angular intervals. Midpoint classification integrates the exposed open arcs.
Tangencies contribute zero buried arc length; holes and disconnected contributors
are retained. Source self/aliases and exact geometric duplicates are excluded,
overlapping other contributors count once, and current grown geometry never
changes eligibility. Screenshots and pixel colors are not measurement operands.

The canonical allocator and marker no longer read or evaluate the historical
area-threshold registry. The old area module and strict-area unit cases remain
for preserved historical evidence only. Area-versus-circumference comparisons
are separate diagnostic artifacts. The existing output field
circle_overlap_keep_source_ids remains solely as a compatibility alias of the
new circle_exposure_keep_source_ids; it does not apply another area gate.

Circles failing the exposure rule are removed from growth competition and
priority nomination and retain exact source geometry. Full original inventory,
caps, palette, numeric clearances, construction reserves, ports, round-priority
obligations, pin separation, downstream remedies and export/corruption checks are
unchanged. The separate original-Region attachment fix and isolated BGA island
case remain in this branch's ancestry.

## Source comparison and qualification scope

The complete 3020212826 source contains 372 circle sites. The historical area
screen held 284; the requested circumference screen holds 328 and leaves 44
eligible for ordinary T01 checks. Of these 328, 214 retain the separate original
full-containment KEEP; the other 114 fail exposed circumference. All five newly
qualified BGA isolated islands measure 100% exposed. No claim is made that all
44 eligible circles will grow or that historical growth is automatically restored.

Evidence is under out/lacie_work/evidence/t01_circle_exposure_20261107/. The first
failed focused test and the earlier diagnostic interpretation are retained.
OWNER_CLARIFICATION_01.json records that the owner requested replacement of the
area selector, rather than adding a terminal exemption. The completed BGA slice
remains separate at commit 7ca3c3a. No unrequested terminal-role exception is added.

Qualification uses all 114 partially exposed KEEP circles plus the five BGA
growth cases in complete original board context. Three fresh workers must
reconstruct identical decisions and actual Gerber output, verify exact KEEP
geometry, all source objects and clear operations, components, source holes,
protected pins, full construction/actual land checks and deliberate corruptions.
This is a bounded T01 qualification; no new full-board U05 result or downstream
T03/T04/T02/T05 rerun is claimed. Other boards remain paused. Show highlighted
source classifications and actual BGA nonregression before integration.

Owner review is pending. Independent review is NOT_RUN: CHANNEL_UNAVAILABLE;
electrical/manufacturing is NOT_ESTABLISHED. Historical .DS_Store custody FAIL
remains EXPLICIT_UNWAIVED_UNATTRIBUTED. The app and delivered Gerbers remain
unchanged until integration is explicitly authorized.

## Completed bounded evidence

BROAD_02.log reports 667 scoped tests PASS. Qualification_01 passes construction
and two fresh sequential reconstruction workers in 77.95, 78.79 and 78.33 seconds.
All three produce the same candidate and Gerber hashes. The 114 partially exposed
KEEP circles retain exact source geometry; all five BGA islands retain their
previous clipped growth. The bounded Gerber is byte-identical to the preceding
BGA slice (SHA256 0e2b32d5a027abd1b4116e3c50ad35c4b9cc8dfbb9b85da12e9793733c8d2285).

Complete construction and actual-file checks cover all 119 selected lands in
full original context. All 1,921 original objects, three clear operations,
126 components, 128 source holes and 13 pin checks survive. Native-grid boundary
and area differences are zero under the existing tolerance. Both actual-file
corruptions reject for the intended reason. Full T01/U05 and downstream stages
remain NOT_RUN; this evidence does not qualify new growth for every one of the
44 eligible source circles.

Final qualified findings are FINDINGS_02.md/.json in the evidence directory.
The earlier FINDINGS_01.md and UNQUALIFIED_FILTER_FINDING_01.json preserve the
diagnostic before the owner's replacement-only clarification. They are not
rewritten or promoted; OWNER_CLARIFICATION_01.json and the new fresh qualification
make the final rule and evidence explicit. Marked-circle views label exposed arc
percentages; they do not promise restoration of every historical grown terminal.
