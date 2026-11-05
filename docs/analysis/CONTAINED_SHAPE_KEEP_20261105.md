# Contained shapes stay unchanged

Owner rule: “no change for any contained shape, be it circle or rectangle.”

The shared `contained-shape-keep/1` predicate uses the complete copper at stage entry. A source is contained when its area outside the union of other copper is at most the existing 1e-12 mm² coverage epsilon. It excludes itself and every exact geometric alias. Partial overlap is not containment; touching alone is not containment. T01 uses complete original source copper. T02 uses its verified predecessor, with containment decisions fixed before any trial growth. Clearance, contact ports, numeric caps and export tolerances are unchanged.

Contained sources retain exact predecessor geometry references. T01 removes them from priority/group growth allocation and square/recess treatment while keeping every occurrence in discovery, obstacles, reconstruction and coverage inventories. T02's ordinary and optimized adapters record COVERED_SKIP and exclude contained targets from inclusive-fill membership. Verification reconstructs the containment classification and rejects either edited contained geometry or altered containment records, including prepared-context reuse. A separate permission KEEP, including C028's full-circle block, remains independently recorded.

Canonical T01 is revision `t01-priority-companion/3`; land policies are revision 2. The prior contracts are archived byte-for-byte. The U04 operator's land-policy operand was updated; its operation sequence and trace-width policy are unchanged. The historical T02 script that enlarged covered circles now refuses new execution before accessing or creating artifacts. Historical algorithms and frozen results remain available as read-only evidence.

Validation: 121 focused tests pass, including circle-in-rectangle, rectangle-in-circle, union coverage, alias exclusion, partial coverage, exact reference preservation, no contained inclusive fills, forged growth, changed containment records and legacy-writer rejection. A complete original-source audit covers 17,849 objects, 1,408 canonical circle sites / 1,541 occurrences and 450 rectangles: 1,034 circles and 79 rectangles are contained. C028 is contained; R304/R305 are not. This classification audit is not a new growth result or native qualification.

Evidence and visual bundle: `out/lacie_work/evidence/contained_shape_keep_20261104T171106Z/`.

The initial test selection mistakenly included two actual Terminal U04 integration tests. One executed T04 on a synthetic seven-object fixture and stopped at its T02 land-policy mismatch; the other stopped at a crop-host gate. Both stopped runs and the initial failed test log are retained. No original-board T04 was executed. Subsequent validation excluded these Terminal tests; the changed operator land-policy binding is checked directly, without rerunning T04. New native qualification of this rule revision remains NOT_RUN. No previous qualification is automatically transferred to it.

Frozen predecessors, the scoped R304/R305 native exports and their stopped attempts remain unchanged. C028's full-circle obligation stays BLOCKED. Owner/independent/electrical/manufacturing acceptance remains separate. T04 work on the original board remains deferred to the new chat.
