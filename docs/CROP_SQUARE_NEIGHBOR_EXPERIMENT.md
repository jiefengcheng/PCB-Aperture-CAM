# Square-guided neighbor recession: one-pair mechanism experiment

## Current owner correction: shared scale and unconditional 1.5× ceiling

The owner requested similar enlargement scale for both sites and clarified that
the **1.5× radius ceiling must never be violated**. The intervening over-cap
proposal below is rejected under this rule; it remains historical evidence only.
The current review at `http://127.0.0.1:8783/` serves
`out/crop_dynamic_tasks/balanced_capped_pair_20261024/`.

The new predeclared policy chooses one factor for both sites:

`k = min(1.5, source-feasible round-A factor, coupled A-square/B-envelope gap factor)`.

Each proposed radius equals `k × its own source radius`. A hard guard rejects any
radius above `1.5 × source radius` before construction, regardless of available
space. Equal scale means equal proposed radius multiplier; final areas may
differ because surrounding source copper differs and B can require recession.

Both source radii are approximately 0.14999 mm. The shared factor is
**1.437986984×**, giving **0.215683668 mm** for both proposed radii, below the
**0.224985 mm** hard ceiling. A stays completely round. Its unchanged source
neighbour limits the shared factor; the square-pair bound is looser and inactive.
The proposed circles do not overlap, and the final pair gap is 0.021409971 mm.
No square-mediated interaction event is claimed. The hard copper minimum remains
0.020 mm; the labelled construction buffer is 0.02002 mm.

All 30 focused tests pass, including exact cap-boundary rejection, shared-factor
selection and different-source-size scaling. A fresh-process saved-geometry
auditor scans all 17,849 F.Cu records for each of three safe variants, verifies
the radius cap on both envelopes and every accepted contour, source cores,
derived squares, source-bound attachment ports and hard gaps. A separate 2×
diagnostic circle is explicitly rejected by the cap guard and is never accepted
copper. The constructor and runner are not imported by the auditor; this remains
same-author verification with a shared parser/kernel.
The existing ChatGPT thread returned a summary-only conditional pass, ready for
owner review. It did not inspect local evidence or independently recompute
geometry. Equal final dimensions and square-mediated adaptation remain unclaimed.

```sh
.venv/bin/python -m unittest tests.test_crop_balanced_capped_growth tests.test_crop_square_bound_growth tests.test_crop_square_neighbor_experiment tests.test_crop_square_neighbor_publication tests.test_crop_square_rotated_priority tests.test_crop_square_rotated_publication -v
.venv/bin/python tools/run_crop_balanced_capped_pair.py --output out/crop_dynamic_tasks/balanced_capped_replay_01
.venv/bin/python -m http.server 8783 --bind 127.0.0.1 --directory out/crop_dynamic_tasks/balanced_capped_pair_20261024
```

Sizing and owner review remain pending, and original T01 event credit is zero.
No prior evidence or frozen T01 record is rewritten.

## Rejected over-cap proposal: A's square side facing B

The owner specified **A's square side facing B**, and requested
further growth with overlapping circular envelopes. The separate saved proposal
`out/crop_dynamic_tasks/earlier_square_bound_review_20261024_v2/`.

Its original execution status was `PROPOSED_INTERPRETATION_PENDING_OWNER_REVIEW`;
the subsequent owner hard-cap correction rejects its above-1.5× geometry.
It does not confirm that the owner intended this exact operator. A's inscribed square side lies inside its
retained round copper. Consequently it cannot directly be B's final stop edge
at the experimental gap without colliding with A. The proposal uses that side
to bound **B's proposed circular envelope**, then recesses B against **actual
round A** and all other source copper. The earlier B-own-square lobe operation
is not used in this proposal.

The radius bound is the signed distance from B's center to the supporting line
of A's square side facing B, minus the construction gap and a 0.00002 mm safety
margin. A's square derives from A's selected enlarged round radius at 45 degrees.
The old 1.5× ceiling is no longer a growth limit; its source-derived attachment
port extents remain fixed. No EDIT geometry supplies the construction.

The previous 0.025 mm construction buffer prevented A from growing further
because of the unchanged grey source circle below-right. This separate policy
explicitly reduces that buffer to 0.02002 mm, retaining the 0.020 mm hard minimum.
Thus both the envelope-bound rule **and** the numerical construction margin
change; the additional growth is not attributed to the square alone.

| Measurement | Proposal |
| --- | ---: |
| A complete-round radius | 0.215683668 mm, previously 0.210703575 mm |
| B proposed circular radius | 0.279996956 mm, previously 0.224985000 mm |
| Proposed-envelope overlap | 0.005767053 mm² |
| B envelope to A square side gap | 0.020040000 mm |
| Final A–B copper gap | 0.020019623 mm |
| Minimum unexempted final B gap in local audit | 0.020019611 mm |
| Final copper overlap | 0 mm² |

The six panels show ORG, overlapping envelopes, actual-copper recession, A's
external limiting obstacle, a rejected direct-square-stop control and final
copper. A fixed-scene control bounds B by the whole round A envelope rather
than its inscribed square; final B changes by 0.053522895 mm². This compares
growth-bound selection, not the earlier fixed-radius lobe causal experiment.
The unsafe direct-stop control overlaps A by 0.005767053 mm² and is rejected.

All 26 focused tests pass. A separate fresh-process auditor scans all 17,849
F.Cu records for each of four saved variants, expecting the three safe variants
to pass and the unsafe control to fail. It also recomputes A's square and its
radius-bound relationship. The first conservative coverage audit failed because
the retrieval band was narrower than its checking band; that execution is
retained. A fresh execution widens retrieval only. Copper geometries are exactly
topologically equal (zero symmetric-difference area and Hausdorff distance),
although two serialized WKB hashes differ due to representation ordering.

Reproduce with a fresh output directory:

```sh
.venv/bin/python -m unittest tests.test_crop_square_bound_growth tests.test_crop_square_neighbor_experiment tests.test_crop_square_neighbor_publication tests.test_crop_square_rotated_priority tests.test_crop_square_rotated_publication -v
.venv/bin/python tools/run_crop_earlier_square_bound.py --output out/crop_dynamic_tasks/earlier_square_bound_replay_01
.venv/bin/python -m http.server 8783 --bind 127.0.0.1 --directory out/crop_dynamic_tasks/earlier_square_bound_review_20261024_v2
```

All earlier source/evidence remains preserved. Sizing and the proposed
interpretation await owner review; original T01 acceptance credit is zero.

## Preserved owner-requested revision: 45 degrees and round A

The current six-case review is saved under
`out/crop_dynamic_tasks/square_neighbor_rot45_round_priority_20261024_v2/`.
The local review service was deliberately retargeted
to this revision after its fresh-process audit, before the later clarification above. The original directory below
remains historical evidence, unchanged.

Both squares rotate 45 degrees clockwise. Lower-left A keeps a complete round
outline: its radius is reduced from the provisional 0.224985 mm ceiling to
0.210703575 mm so it fits the source-derived constraints without asymmetric
clipping. Upper-right B retains its proposed 0.224985 mm circular envelope,
derives its rotated square from that envelope and yields at the actual square
side facing A. This is B's own square side; A's displayed square does not supply
B's stopping line. The original ORG cores and surrounding source records remain
unchanged. A's square derives from its selected complete-round envelope, not
from the unused ceiling. Neither square is derived from EDIT.

Cases 2 and 3 show the revised construction. Cases 4 and 5 recompute the causal
controls with the same round A and 45-degree setting; case 6 shows assembled
copper. Case 3 includes a recorded 0-degree comparison with exactly the same
round A, B radius, source-derived attachment zones and other obstacles.

Rotation redistributes B's retained copper: it gains 0.009393859 mm² and loses
0.009192159 mm², a net gain of 0.000201699 mm². The contour's symmetric difference
is 0.018586018 mm². This small net gain is not evidence that a larger radius is
qualified. The resulting A–B gap is 0.082756346 mm. One square-mediated event
remains mechanism-only evidence; sizing is `SIZE_NOT_QUALIFIED`, original T01
event credit is zero and the revised owner judgment is `PENDING_USER_REVISED_VIEW`.

The frozen revision policy is
`contracts/crop_square_rot45_round_priority_policy.json`. The new runner uses
the existing source inventory and preserves a fixed port reference based on the
1.5× ceiling for both angle comparisons. A separate fresh process scans all
17,849 F.Cu records for each of seven saved variants, including the 0-degree
control; it checks roundness, both rotated squares, source cores, obstacle
coverage, attachment ports and the hard experimental gap without calling the
constructor. This remains same-author verification with a shared parser/kernel.
The positive review page requires the exact eleven-check revision contract,
strict integer event count, bound saved geometries and a matching seven-case audit.
All 22 focused tests pass. The existing ChatGPT thread returned
`CONDITIONAL_PASS_READY_FOR_OWNER_REVIEW` in a summary-only desk audit; it did
not inspect or recompute local evidence. Its two wording clarifications are
recorded in `construction_clarification.json`: identify B as the stopping-square
owner and describe A's radius as a source-feasible search result, not a proven
mathematical maximum.

Reproduce in a fresh directory:

```sh
.venv/bin/python -m unittest tests.test_crop_square_neighbor_experiment tests.test_crop_square_neighbor_publication tests.test_crop_square_rotated_priority tests.test_crop_square_rotated_publication -v
.venv/bin/python tools/run_crop_square_rotated_priority.py --output out/crop_dynamic_tasks/square_rot45_replay_01
.venv/bin/python -m http.server 8783 --bind 127.0.0.1 --directory out/crop_dynamic_tasks/square_neighbor_rot45_round_priority_20261024_v2
```

## Preserved original 0-degree experiment

This separate experiment makes the derived square participate in an actual
neighbor-facing editing decision. A grows first; B derives its square from its
own proposed enlarged circle and removes the facing optional lobe when A's
accepted copper creates a clearance conflict. Ordinary surrounding-copper
constraints still apply afterward. The original ORG cores remain intact.

**Status: `MECHANISM_DEMONSTRATION — SIZE_NOT_QUALIFIED`.** Owner review remains
`PENDING_USER`. This establishes one exercised provisional mechanism, with zero
credit toward frozen T01 acceptance. The three-event objective, accepted sizing,
EDIT equivalence, original round-priority policy, native export, electrical intent
and manufacturing qualification are not established by this result.

## Inspect the result

Serve `out/crop_dynamic_tasks/square_neighbor_mechanism_20261024/` and open
`http://127.0.0.1:8783/`. The six panels show the ORG pair, proposed envelopes and
clearance conflict, square-side recession, both causal controls and final copper.
Gold in panel 3 identifies optional copper removed by B's square supporting line.

Both selected ORG circles have radius approximately 0.14999 mm. The experimental
envelope radius is 0.224985 mm under a predeclared ORG-only 1.5× ceiling. This
fixed ceiling demonstrates the mechanism; it is not an inferred expert sizing
rule. The square is axis-aligned by experimental convention. Neither radius nor
orientation uses EDIT. Selected A is centered at `(1.359, -14.737)` mm; B at
`(1.689, -14.427)` mm. Exact source identities and byte bindings are in the report.

| Condition compared | B symmetric-difference area |
| --- | ---: |
| Remove only A's accepted addition, square enabled | 0.0156116243 mm² |
| Disable square, with accepted A present | 0.0134813410 mm² |
| Disable square, with A restored to source | 0 mm² |
| Remove A's addition, square disabled | 0.0021302833 mm² |

Thus A's addition affects B, and the square contributes specifically when that
addition creates the conflict. The final pair gap is 0.0249995294 mm. The hard
experimental requirement is 0.020 mm; 0.025 mm is the nominal construction
buffer, not an exact final-clearance claim.

## Construction and eligibility

[`inscribed_square`](../src/crop_square_neighbor_experiment.py) constructs the
square from the enlarged analytic radius. `square_facing_lobe` consumes the
square's supporting line; `construct` removes the optional lobe before ordinary
clipping and acceptance. The source core is excluded from removal. Gold square
geometry is therefore consumed independently of the SVG renderer.

The policy is saved before execution. The 51 unique source circles are retained
in the inventory. Pair eligibility uses the two most populous ORG radius classes
and different original physical-contact groups. Source-clear B versus A and
potential clearance competition identify candidates. A deterministic source
coordinate/identity order selects the first whose accepted A addition reaches B's
proposed envelope, before B's square or either causal outcome is evaluated. This
is deliberate interaction enrichment for an existence demonstration, not an
estimate of event prevalence.

The selected pair is growth-eligible in this experiment even where historical
KEEP/priority labels existed. All unselected source objects remain fixed. No
historical priority-policy compliance is claimed. The frozen T01-R1 engine,
receipts and acceptance records are not rewritten by this experiment.

## Verification and attachment scope

Seven focused geometry tests exercise the mechanism, no-conflict behavior, enlarged-square
scaling, source preservation and deliberate clearance/scope/geometry corruptions.
A separate same-author auditor scans all 17,849 original F.Cu objects for each of
six live/control/assembled cases without invoking the constructor or spatial
index. It checks obstacle coverage, hard-gap exclusions, preserved cores,
envelope bounds, all four saved geometries and source-bound trace ports.

The port exemption allows new land copper to join its already attached original
trace inside a fixed, bounded source-derived zone. It is not limited to inherited
overlap. Each matching trace retains its source geometry, original core contact
and source width. New copper cannot contact it outside that port, and all other
objects remain subject to their own clearance checks within the port. These are
geometric constraints; physical-contact groups are not verified electrical nets.

Summary-only ChatGPT review is recorded separately in the output directory;
it is not independent local recomputation. Cursor review remains
`NOT_RUN: CHANNEL_UNAVAILABLE`.

The positive page additionally requires the complete twelve-check execution
contract, an established mechanism status and exactly one recorded source event.
Failed, empty or incomplete results render an explicit not-established page;
the no-pair execution exits nonzero. Seven publication tests cover these failures,
unbound positive reports, interrupted atomic replacement, stale success pages,
exact historical source bindings and preservation of saved executions. Before
positive rendering, displayed contours must match the receipt's saved WKB hashes,
source and policy; linked audits must reference the same receipt. Missing audits
remain `NOT_RUN` at page generation. This guard does not independently validate
geometry.

## Reproduce

From the repository root, using the existing frozen policy and source package:

```sh
.venv/bin/python -m unittest tests.test_crop_square_neighbor_experiment tests.test_crop_square_neighbor_publication -v
.venv/bin/python tools/run_crop_square_neighbor_experiment.py --output out/crop_dynamic_tasks/square_neighbor_replay_01
.venv/bin/python tools/audit_crop_square_neighbor_experiment.py --bundle out/crop_dynamic_tasks/square_neighbor_replay_01
.venv/bin/python -m http.server 8783 --bind 127.0.0.1 --directory out/crop_dynamic_tasks/square_neighbor_mechanism_20261024
```

Use a new replay directory for each execution; the runner refuses to overwrite
existing evidence. The server command above shows the original reviewed pair.
To recheck that preserved bundle with later code, the auditor verifies its exact
execution hashes against `review_source/` snapshots and can write a separate
audit using `--output out/crop_dynamic_tasks/frozen_pair_reaudit.json`.
That original server command serves the fixed historical bundle. The owner's
later explicit six-case revision now uses the new directory described above;
fresh replay runs do not automatically retarget the service. Atomic page replacement prevents partial HTML, while run and
receipt identities establish which execution a complete page represents.

The directory retains `owner_handoff.md`, `policy.json`, `selection.json`,
`report.json`, `obstacle_bindings.json`, all WKB variants, SVG stages, audit
records, test logs and `SHA256SUMS`. Source fixtures remain immutable.
