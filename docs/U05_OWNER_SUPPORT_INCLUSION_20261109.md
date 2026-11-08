# T05 existing-owner serialization support

This correction is separate from growth, pin separation and polarity flattening.
It does not modify the accepted T02 predecessor or a T05 growth decision.

The failed 3020212868 job is retained at
`out/lacie_work/operator_routes/gerber_u05_incremental/20261108T184410Z-5049626d3726486882ac5ed718e83832`.
Its T05 completion halted at `SOURCE_COMPONENT_MERGED_OR_UNBOUND`.
The retained diagnostic found 139 original components and 182 native components:
43 additional positive faces all touched one existing channel at zero-area
contacts. There was no cross-source-component bridge in this diagnostic.

All 43 faces overlap the same T05 addition, for route `JR-420025e616b1449d`.
The accepted stage-entry native owner is one component. The bare addition's
native encoding yields 44 components for that owner. Existing bounded owner
support produces one component, using only copper already present in that owner.
The old separately re-unioned physical-image comparison nevertheless reports
`4.5494645188415776e-10 mm²` of difference. Direct set inclusion finds exactly
zero added material outside the owner, with missing qualified material only
`2.740953079800262e-15 mm²`, below the unchanged `1e-12 mm²` epsilon.

The verifier now also proves the same equality through its two inclusions:
qualified region R is retained in candidate C; every C-minus-R face is already
in owner O. These imply O union C equals O union R. The old overlay measurement
remains in the receipt. No buffer, snapping, face deletion, new tolerance or
physical growth allowance is introduced by this proof. The unchanged validity,
domain, support containment, component reduction and complete qualified-region
checks remain required. Final native fidelity, connectivity, clearance, pin
separation, shared gaps, budgets and corruption checks remain required.

Evidence is under
`out/lacie_work/evidence/ordinary_hole_acceptance_20261108/actual_2868_topology_diagnosis_02/`:
`RESULT_01.json`, `ISLAND_ORIGIN_01.json`, `POINT_CONTACT_01.json`,
`EXPORT_ENCODING_01.json`, and `BOUNDED_SUPPORT_01.json`.
Thirty-five focused export/support tests passed, including deliberate foreign
bridge, removed-growth and filled-cutout rejections. The first test invocation
named a nonexistent test file and ran no tests; its log is preserved separately.
Scoped actual export/reparse passed: all twelve emitted regions were reparsed,
with zero symmetric material difference and a boundary difference of
`5.329070518200751e-15 mm`. The actual channel remains one component.
`ENCODING_REPARSE_01.json` and `owner_support_01.gbr` retain that evidence.
Full native board qualification remains a separate gate; the scoped result is
not a board PASS.

The normal app remains unchanged pending integration qualification. All failed
evidence is immutable. The `.DS_Store` custody finding remains explicit,
unwaived and unattributed. Six broad-suite findings remain deferred/unwaived;
owner acceptance is pending and manufacturing acceptance is not established.

## Single combined error allowance

The two direct inclusions share one `1e-12 mm²` material-error budget. Their
missing-region and outside-owner areas are added before comparison; they cannot
each spend the full allowance. A negative control with two `0.75e-12 mm²` errors
exposed the earlier helper's separate comparisons, and is now rejected because
their combined error is `1.5e-12 mm²`. No tolerance is increased.

Forty-one focused tests passed. The retained actual 2868 candidate remains
byte-identical under the tighter predicate: its combined error is
`2.740953079800262e-15 mm²`. Evidence is `OWNER_SINGLE_EPSILON_TESTS_01.log`,
`OWNER_SINGLE_EPSILON_OLD_NEGATIVE_01.json` and
`OWNER_SINGLE_EPSILON_ACTUAL_01.json` in the same external evidence directory.
Active source snapshots and historical qualification remain unchanged. Before
counting an older completed export under this stronger predicate, check every
fallback-support receipt against the single combined budget; do not merely
reinterpret the older proof as a fresh native evaluation.
