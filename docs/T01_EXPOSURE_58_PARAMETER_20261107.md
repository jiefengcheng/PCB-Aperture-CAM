# Provisional exposed-circumference threshold: 58%

The owner changed the provisional parameter from 70%, through 60%, to 58%.
The only operational policy change is the registered minimum exposed original
circumference fraction: contracts/t01_circle_exposure/settings.json now contains
0.58. The area selector remains removed. Full-containment KEEP, original source
measurement, clearance, caps, ports, pin constraints and all other checks remain.

Reclassifying the retained qualified source measurements gives 97 eligible and
275 KEEP circles among all 372 sites. This admits 53 more than 70%, and two more
than 60%. The previously displayed 59.8% terminal is now eligible. Eligibility
does not establish that new growth passes the remaining geometry checks.

673 scoped regressions pass, including the 58%, 60% and 70% numerical boundary
cases, prior circle rules, T04, source/export and pin controls. Evidence, captured
source and classification views are under
out/lacie_work/evidence/t01_circle_exposure_58_20261107/. The intermediate 60%
comparison and registry bytes are preserved separately. Older qualification and
failed evidence are unchanged.

This is an immediate parameter/eligibility update in isolation. No new growth,
native export or U05 qualification was started at 58%; the earlier 70% native
proofs are not promoted to 58% geometry qualification. The classification preview
shows E (eligible) and K (KEEP), not newly added copper. The app and delivered
Gerbers remain unchanged, other boards remain paused, and this revision is
unintegrated. Historical .DS_Store custody FAIL remains explicit and unwaived.
