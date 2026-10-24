# Owner review — not accepted

**Date:** 2026-10-24  
**Reviewed commit:** `0172c7d7d633adef60daf3b9f47afbac8de6e293`  
**Status:** `NOT_ACCEPTED_BY_OWNER`

The owner rejected the delivered T01-R1 slice because its copper enlargement exceeded the size range implied by EDIT. The earlier `PASS_WITH_SCOPE_LIMITS` result records internal geometry checks only; it is superseded as a delivery/acceptance status.

The first source-bound ORG/EDIT center audit found 46 unique exact-center circle correspondences in the fixed viewport. For ORG radius classes 0.12497 mm and 0.14999 mm, the paired EDIT radii range respectively from 0.12918–0.14506 mm and 0.15000–0.17012 mm. Their observed maximum radial increases are 0.02009 mm and 0.02013 mm. The previous construction allowed 0.20 mm, roughly ten times the observed upper range. Five remaining smaller ORG circles lack a unique exact-center EDIT counterpart and therefore have no evidence-based enlargement range.

These figures are a same-job calibration observation, not a recovered universal PCB rule. The next bounded correction must freeze this observed range separately, withhold EDIT geometry from construction, constrain eligible ORG-derived growth to the calibrated radius classes, and leave unpaired targets unchanged. The prior R1 output and verification remain preserved as history; the corrected run must use a new output directory.

## Corrected range-bounded run

The corrected constructor now receives only two class-level maximum final radii derived from the separate calibration receipt: 0.14506 mm for ORG radius class 0.12497 mm, and 0.17012 mm for ORG radius class 0.14999 mm. The maximum resulting radial reach is 0.02013 mm. All five unpaired ORG shapes have zero reach and remain unchanged. The constructor does not receive EDIT contours or per-site EDIT dimensions.

The reproducible candidate and evidence are written separately at `out/crop_dynamic_tasks/t01_r1_edit_calibrated/`. The same-job calibration matches 46 of 51 unique ORG shapes by unique center, with five unmatched and zero ambiguous. Twenty sites grow; 26 round-priority sites and five unmatched sites remain unchanged. This is a same-job calibration, not blind transfer or a universal design rule.

The constrained run reports zero dynamic-neighbor adaptation events; the previously requested dynamic effect is therefore not demonstrated under this range. This does not establish owner acceptance. Review the saved overlay and measurements before changing acceptance state.
