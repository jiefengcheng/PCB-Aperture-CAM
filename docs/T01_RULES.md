# Current T01 rules

Updated 7 November 2026. This is the maintained plain-language rulebook for the
user-directed T01 policy in this checkout. **The current provisional circle
eligibility threshold is 58% exposed circumference. The partial-area percentage
rule is retired.** Eligible means that growth may be attempted; it does not mean
that growth has passed the remaining checks.

The latest isolated implementation checkpoint is `000a604`. The Region-contact,
BGA-single and circumference revisions remain unintegrated into the normal app.
The 58% update has passed 673 scoped regressions and source reclassification;
fresh 58% growth/export qualification has not been run. Earlier native proofs
retain their original parameters and scope.

## Rule precedence

Apply source custody and assembly first, then immutable permissions and full
containment KEEP, then exposed-circumference eligibility, then source case
recognition, allocation and live-scene construction. Every resulting proposal
must pass all applicable clearance, source-core, joint and pin-separation checks.
A later growth or remedy stage cannot create a new exemption from the original
source constraints. A historical exception applies only to its registered source.

## Source and eligibility

**T01-01 Preserve the input.** Keep original client files, source hashes, frozen
results and failed evidence unchanged. Work on separately recorded candidates.
Where assembly has certified the client's illustrative enclosing outer trace,
remove only those certified plotting occurrences from the derived working
artwork and final generated artwork. Preserve every other source atom and record
the original-to-assembled mapping. Proximity to the board edge alone does not
authorize deletion. Channels joined only through the illustrative end frame
must remain separate for growth.

**T01-02 Respect source representation.** Use a verified native source pair when
one exists, or the supported Gerber-only route when no KiCad source is supplied.
Resolve Gerber objects in original drawing order: dark adds, clear subtracts
earlier copper, and later dark can restore it. Preserve resolved holes, channels
and disconnected islands. Keep object provenance and pin/joint constraints.
Positive-only flattening is a separate representation slice; it does not repair
a bridge, enlarge a pad or authorize filling an original clear footprint.

**T01-03 Inventory the complete source.** Account for every supported filled
zero-stroke source circle and occurrence, including nested and covered circles.
Merge exact aliases for decisions while retaining their identities. Verify source
spans. Keep unsupported families and missing source intent explicit. Presentation
crops, screenshots, pixel colors and a first inventory page cannot select the
construction pool or hide complete-board obstacles.

**T01-04 Preserve exact cores.** Keep every circle's original copper core and all
its aliases. Retain unrelated source contributions unchanged. Use the exact
source polygon centroid as computational center and one quarter of the sum of
its bounding-box width and height as computational radius. Current growth cannot
redefine the original circle, ownership, attachment or exposure measurement.

**T01-05 Keep fully contained shapes unchanged.** When the union of other
original stage-entry copper fully covers a circle, retain its exact predecessor
geometry and references. Exclude self and exact aliases from this measurement.
The shared rule also covers rectangles in their own stage. Its existing
containment epsilon is unchanged; partial coverage is not full containment.

**T01-06 Use exposed circumference only for partial-circle eligibility.** Divide
the total length of original circle arcs not buried in the union of other
original copper by the full original circumference. Use the original analytic
circle and finite source geometry, not image pixels or trial-grown neighbors.
Exclude self and exact geometric aliases, count overlapping contributors once,
respect holes, and give tangencies zero buried arc length.

Allow ordinary growth checks when this exposed fraction is **at least 0.58**.
Exactly 58% qualifies; below 58% is exact KEEP. Do not add a percentage tolerance.
Remove KEEP sites from growth-priority nomination and competition, while keeping
them in the source inventory and obstacle context. Do not also apply the retired
70% covered-area rule. The earlier 70% and intermediate 60% exposed-circumference
values are superseded, not additional conditions.

## Circle cases and existing joints

**T01-07 Keep three cases distinct.** A supported local two-pad component, an
ordinary single round terminal on a long feed, and an isolated BGA array island
are different source cases. A distant circle or main-copper contact reached
through a long trace does not establish a local paired-pad case. Physical
connectivity and local size-competition grouping have different purposes.
Do not introduce a global distance heuristic or assume electrical intent.

**T01-08 Nominate the supported round priority.** After KEEP exclusions, use the
existing source-qualified largest-round priority policy, with stable source-ID
tie breaks. In the supported two-pad case this can nominate the larger
trace-connected round pad. An ordinary single terminal may be its own priority
and attempt safe full-round growth. Neither case is an unconditional growth
requirement. A remote connection cannot manufacture a local partner or a
clearance exemption.

**T01-09 Recognize integral original pad-to-trace joints.** Treat a genuine
original local joint as connected copper, without an artificial internal
clearance slit. Recognize native line/arc contacts, source-bound positive filled
Gerber Region contacts and supported local circle-to-Region-to-trace chains.
For the Region family, require positive-area original contact and matching source
identity and geometry hashes; touching, proximity or a newly grown contact is
insufficient. Derive permissions only inside the existing local attachment
corridor. Another local arm joined remotely remains a barrier. Reconstruct these
permissions for allocation, construction and actual-file checking.

**T01-10 Apply the separate BGA single-circle case.** The current supported source
pattern is a complete axis-aligned equal-pitch array of identical circular
flashes, with at least three positions on each axis, on the native coordinate
grid. Each flash must restore material actually removed by an earlier clear
operation. Only an original isolated circle component, apart from exact aliases,
qualifies; a trace, Region or other-pad attachment keeps its ordinary case.
Incomplete, rotated or irregular arrays retain ordinary policy.

After the same KEEP and exposure gates, give each qualified island its own size
allocation, without an artificial nearby partner or paired-square size ceiling.
It may use a clipped optional-growth contour within the existing palette and cap.
All actual neighbors, source cores, gaps and protected pins still constrain it.
The negative source footprint establishes provenance; it is neither a permanent
mask against all growth nor permission to fill the whole footprint.

## Allocation and construction

**T01-11 Grow from the original size.** Preserve the original center and core.
Use the existing discrete diameter palette and a strict maximum factor of 1.5
on original radius/diameter. Do not compound earlier offsets. A nominal envelope
diameter is not the resulting diameter of an irregular clipped contour. T04's
ten-step trace ladder and 30 micrometre total trace-width cap do not become T01
pad rules through this document.

**T01-12 Retain ordinary competition rules.** Honor registered source-identity
reviewed pairs; form remaining ordinary competition pairs deterministically.
Prefer the largest shared admissible physical diameter, or individual classes
where needed. Demote constrained round reservations by whole classes; do not
automatically shrink a roomy companion with its constrained priority.

Retain the directional A-square/B-envelope rule at minus 45 degrees. Strictly
nested source circles whose centers differ by no more than the existing
concentric epsilon keep their separate cores and identities without inventing a
facing direction or that directional bound. All other constraints still apply.
The independently allocated BGA case is not an ordinary paired-square case.

**T01-13 Preserve full-round obligations and scoped exceptions.** A nominated
round priority must remain complete, or stay at its safe predecessor size.
Do not silently clip it into a companion. Optional companion growth may adapt
against actual neighbors and must remain attached to its source core. Only
registered recess directives and the separately qualified BGA-single case have
their stated exceptions. Preserve the source-specific C01 recess behavior;
do not generalize it to every single circle. C028's full-circle recovery
obligation remains blocked under its recorded source permission.

**T01-14 Recover feasible discrete opportunities deterministically.** Retain
safe next-class round promotions with other targets fixed, greatest feasible
area gain and stable source-ID tie breaks. Recompute affected square bounds and
record next-class blockers. This is a bounded greedy allocation, not a claim of
continuous or global optimality.

**T01-15 Use the current scene.** Construct round priorities first in stable
source-ID order, then ordinary companions in centroid Y, X and source-ID order.
Each accepted contour atomically replaces its aliases and updates or invalidates
affected spatial dependencies. Later proposals must see earlier accepted copper.
Reject stale scene/index revisions and stale cached verdicts. Keep complete
final validation; caching does not remove any dependency or check.

## Spacing and protected separation

**T01-16 Keep real clearance and integral joints distinct.** Apply the captured
production clearance and all retained construction guards to applicable exposed
new copper and foreign/local-channel neighbors. Existing source joints use only
their bounded original permissions. Same-net or connected-component membership
alone cannot authorize a new bridge. Never acquire an ownership exemption from
a contact created by the current growth.

**T01-17 Preserve source-bound pin separation.** Bind distinct pin branches,
intentional inter-pin slots and existing pad-to-trace attachments to the original
source. Preserve required separation for the complete protected finger length
and transition, including retained-prior copper. If source pin intent is absent
or unsupported, report that coverage as not established instead of inventing it.
Recheck after absorption/encoding and in the actual reparsed Gerber.

**T01-18 Carry separation through every later remedy.** Protected pin slots are
excluded from notch/pocket filling, microscopic-hole absorption, inclusive
rectangle filling and smooth-rim treatment across T01/T03/T04/T02/T05. Check a
complete logical fill before clipping or splitting. If any part violates
protected separation, reject that entire proposal; unrelated repairs may proceed.
Do not recover rejected fragments through another radius, stage or representation.
Neither same-net ownership, clearance allowance nor the downstream cumulative
20% pocket-remedy budget overrides protected separation. The 20% allowance is
not a T01 circle-size or copper-area growth allowance.

## Current parameter sources

Values below are the current registered defaults, not values to copy over
captured historical jobs. Change a provisional value at its owning registry,
capture its raw bytes/hash and resolved value in the next job, and reject stale
policies or altered job snapshots. Keep numerical recognition, geometry fidelity,
clearance and percentage thresholds separate.

| Parameter | Current value | Owner |
|---|---|---|
| Minimum exposed circumference | **0.58**, inclusive | [Exposure registry](../contracts/t01_circle_exposure/settings.json) |
| Maximum T01 radius/diameter factor | 1.5 | [Canonical contract](../contracts/t01_canonical/contract.json) |
| Diameter palette in mm | 0.038, 0.0761, 0.2749, 0.2999, 0.3374, 0.3749, 0.4499 | Canonical contract |
| Nominal production clearance | 0.040 mm | [Production clearance](../contracts/clearance/production.json) |
| Full-surface construction gap | 0.04010 mm | Canonical contract |
| Additional construction reserve | 0.00002 mm; full-surface reservation is 0.04012 mm | Canonical contract |
| Legacy T01 construction gap and safety | 0.04002 mm plus 0.00002 mm | Canonical contract |
| Original contact buffer | 0.04002 mm; original Region ports use the full guard plus reserve within their bounded corridor | Production clearance and canonical contract |
| Registered finished-clearance tolerance | 1%; nominal-minus-allowance is 0.0396 mm | [Clearance settings](../contracts/clearance/settings.json) |
| Circle construction tessellation | 128 quadrant segments | Canonical contract |
| Construction area / event epsilon | 1e-10 / 1e-8 mm² | Canonical contract |
| Full-containment area epsilon | 1e-12 mm² | Canonical contract |
| Full-surface distance comparison epsilon | 1e-12 mm | Canonical contract |
| Core containment reserve | 1e-10 mm | Canonical contract |
| Minimum BGA array positions per axis | 3 | [BGA registry](../contracts/t01_bga_single/settings.json) |
| Native export fidelity in the retained bounded Gerber profile | 0.000002 mm, with separate declared source/output grids | Captured native export/reparse proof |

The registered 1% allowance applies only to finished-clearance comparisons that
explicitly adopt the captured tolerance policy. It does not change construction,
58% exposure, source recognition, export fidelity or protected pin rules. Retained
T01 land/pin verifiers that require 0.040 mm continue to require it. Registration
is not evidence that every route has migrated to the allowance, and this
rulebook does not weaken any of those checks.

## Verification and evidence

**T01-19 Check the complete result.** Reconstruct every saved contour from bound
source and policy, check complete assembled legacy and visible surfaces, and
verify caps, cores, identities, ports, references and protected slots. Retain
neighbor-restoration, square-disabled, stale-cache/source/policy and deliberate
geometry/export corruption controls. Reparse the actual generated Gerber and
check effective copper, source holes, components, required separation and scope.
More or simpler positive regions are acceptable only when the actual decoded
material passes the same geometry/connectivity requirements; raw object count
alone is not geometric equivalence.

**T01-20 Report decisions and show the result.** Keep every site's KEEP/GROW/
blocked disposition, original and proposed sizes, nominal and actual contours,
source case, exposure percentage and blocker. Show source and actual result in
common coordinates, with actual new copper highlighted. Clearly label a source
classification, rejected proposal, replay or preview; it is not new growth or
fresh export qualification. Preserve the requested before/after and control
views. Report measured dynamic interactions and timing honestly; test counts do
not establish missing geometric behavior or an optimum.

**T01-21 Preserve checks, budgets and custody.** Stop a failed managed run with
its failed check and later NOT_RUN dispositions. Do not resume, overwrite,
reseal or promote it. A corrected implementation requires a separately recorded
job. Preserve old parameter snapshots, accepted predecessors, failed hypotheses,
both required evaluations and explicit unwaived .DS_Store custody findings.
All new engineering artifacts, logs, caches and jobs use the prepared LaCie
workspace without an internal fallback. Source code and small documentation may
remain in the checkout.

**T01-22 Keep acceptance levels separate.** A user-approved rule, implemented
rule, scoped test pass, native qualification, visual approval and integrated app
are different states. Do not manufacture human/independent observations from
machine predicates. Independent review requires a genuine channel; otherwise it
is NOT_RUN: CHANNEL_UNAVAILABLE. Electrical/manufacturing remains not established
without its own evidence. Show isolated findings before integration when requested.

## Which revisions are evidenced

| Revision | Recorded status | Evidence |
|---|---|---|
| Original Region joint recognition | 618 tests and bounded native construction/reconstruction/export checks; unintegrated | [Recognition findings](T01_ORIGINAL_REGION_CONTACTS_20261107.md) |
| Separate BGA single islands | 650 tests and bounded five-island native/export qualification; unintegrated | [BGA findings](T01_BGA_SINGLE_CIRCLE_20261107.md) |
| Circumference replaces partial area eligibility | 667 tests; native qualification of 114 partial KEEP cases plus five BGA cases at 70%; unintegrated | [Circumference findings](T01_CIRCUMFERENCE_ELIGIBILITY_20261107.md) |
| Current 58% parameter | 673 scoped tests; retained-source reclassification, 97 eligible / 275 KEEP; no fresh 58% growth/export qualification; unintegrated | [58% findings](T01_EXPOSURE_58_PARAMETER_20261107.md) |

These statuses describe this isolated checkout and its retained receipts. They
are not a live audit of the separate normal-app checkout. Do not infer that the
app currently runs 58% or that all 97 eligible circles have grown.

## Maintenance and precedence over older prose

Update this file after each subsequent user-approved T01 rule or parameter change.
Keep the stable T01 rule IDs, record the current registry value and source, and
update the qualification/integration row without rewriting earlier run evidence.
When a rule is replaced, state which behavior is retired; do not leave both
selectors described as active. Add the source-backed positive and negative
regressions required for the implementation slice before claiming qualification.

The older [controlled English input](../contracts/t01_board/english.txt) is a
byte-pinned compiler dialect, not this consolidated rulebook. Its prose still
omits later refinements; some historical JSON authority fields also retain old
area/70% wording. Current partial-circle behavior comes from the canonical
allocator's exposure registry, not an additional old area gate. Do not edit a
pinned dialect or claim this file is directly compilable without a separately
versioned compiler/contract alignment. This documentation update changes no
geometry algorithm, numeric registry, executable contract or app integration.

Historic C01 S08/S31 recess and S38/S22 undo instructions stay bound to their
[saved owner-correction case](crop_dynamic_tasks/T01_OWNER_CORRECTIONS.md).
Only currently registered [source directives](../contracts/t01_crop/source_features.json)
and [permissions](../contracts/t01_canonical/scoped_recovery_authority.json)
may affect a new source run; screenshot labels are not general authorizations.

Outside T01, trace widening, rectangle growth, 20% pocket remedies and junction
spindles remain their own stages. This file carries their shared source/pin
preservation obligations without moving those operations into T01.
