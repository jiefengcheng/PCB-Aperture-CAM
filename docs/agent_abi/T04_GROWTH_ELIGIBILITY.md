# Provisional T04 growth eligibility — 2026-11-22

## Current policy revision 6 and qualified checkpoint — 2026-11-24

Revision 6 additionally measures complete candidate routes against **other
stage-entry copper**, including overlapping native-stroke artwork omitted by
the earlier broad-fill image. All own route members and exact normalized
aliases are excluded. At least 80% coverage means KEEP before construction;
nominal 0.250 mm traces also remain unchanged. The connected-route exclusion
stays disabled. Saved older revisions retain their recorded semantics.

The six owner-flagged chains now retain all 24 source segments byte-identically
across four routes. The fresh full-board diagnostic after saved cleanup passed
1,465 connection and 3,205 endpoint checks, with zero unresolved corners.
See [native interface repair and evidence](T04_NATIVE_INTERFACE_REPAIR.md).
The older holds and revision descriptions below are historical checkpoints;
they do not supersede this current policy or result. No export or production
acceptance is implied.

## Owner update — 2026-11-24: 80% broad-fill coverage

Registry revision 4 adds `minimum_large_fill_coverage_fraction = 0.8`.
An entire native route stays at its exact cleaned input contours when at least
80% of the union of its input copper is covered by independently prepared broad
filled copper. This uses area, not occurrence counts. Remove all maintained
native trace sources and their exact geometric aliases before preparing the
fill operand. Qualify broad fill with the existing 0.125 mm inset and 1 mm²
core-area bounds. Preserve holes. Ordinary pad contact or an indirect chain
connection alone cannot establish this exclusion. Connected-route protection
remains disabled. This supersedes the width-only selection for new jobs only.

The nominal 0.250 mm cutoff is unchanged: 0.249935 mm rounds to nominal
0.250 mm at the adopted 0.001 mm resolution and remains KEEP. Older snapshots
retain their own policy. The policy ledger records route area, covered area,
fraction, supporting fill inventory and the source-bound KEEP reason.

When an explicit shared copper context is supplied, eligibility borrows its
exact revision owners and memberships. `CopperContext.prepared_subset` owns the
independent fill image, once per revision and ordered role inventory; restart
reuse authenticates the saved geometry. It creates no extra full-board tree.
Coverage is a stage preparation batch, never a per-corner search. Selection
does not replace the existing construction, clearance or preservation checks.

## Native-route continuity

Covered contributions remain in native topology although they are excluded
from growth. `fixed_continuation_sections` supplies their unchanged source-width
sections to adjoining mutable straight/curved profiles. Real source IDs remain
intact. A maximal member shares one field through internal occurrence seams;
only its real outer ends acquire the fixed continuation constraint. Independent
residual matching uses the same frozen endpoint section registry.

`joint_side_fields` coordinates physical sides at tangent straight joins.
A frozen asymmetric group supplies its exact edge positions; a free span
interpolates using the existing zero-derivative cubic and slope bound. Reversed
source directions reverse both normal and side order. Incompatible frozen
groups and insufficient transition length remain unresolved; no averaging,
neck-down, source refit, cap relaxation or clearance waiver is introduced.
Curved and corner joins retain their existing constructors and diagnostics.

Revision 5 additionally freezes `smooth_native_route_profiles = true`. Its
residual-chain constructor retains authenticated **original** source copper,
replacing preceding optional widening with the common C1 field. The earlier
union with the entire grown floor could preserve the shoulders the field was
intended to remove. Fixed straight/arc group members remain outside this
replacement. Existing positive-addition checks still verify every new surface;
differential pocket checks use the actual replaced route and fixed support.
Both straight and curved native occurrence seams restrict the same polynomial
pieces, including a reversed source or a source crossing the profile midpoint.

Internal endpoint sections superseded by an admitted shared chain are archived
as `superseded_chain_sections`. The endpoint audit uses the new field at those
internal seams. Real outer frozen group obligations are not weakened. A moving
native frame applies only where the actual shared-chain recipe supports it.
Historical snapshots without this flag retain the grown-floor matching path.

Cleanup preservation in the runner is a direct byte/inventory proof: every
changed contribution must be admitted, and fixed/terminal contributions stay
byte-identical. The informational previous-trim reentry measurement is marked
`NOT_RUN_INFORMATIONAL_ONLY`; it is not a keep-out or a safety predicate. The
ordinary constructed-route, reference, functional and pocket checks remain.
This avoids constructing two extra board images solely for accounting. A
discarded local-mask experiment and the initial capacity failure remain in the
evidence folder; neither is used as a qualified result.

Evidence for this change is under
`out/lacie_work/t04_eligibility_smoothness_20261124_01/`. Coverage statistics
there are saved-result audits, not a fresh full-board construction. The
six-route construction is separately identified as bounded. Do not promote
the previous full-board result or claim all corner/endpoint findings resolved.

## Current owner update: width threshold first

The owner disabled the connected-to-large-copper exclusion pending further
assessment. Registry revision 2 sets `preserve_routes_connected_to_large_fill`
to false. Ordinary native traces are not frozen through other traces or direct
fill attachment. The 0.25 mm source-width cutoff remains in effect. Exact
covered-copper KEEP, plotted-fill roles, existing growth caps, joints and
clearance checks remain separate requirements; eligibility does not guarantee
growth. Old revision-1 snapshots keep their recorded behavior.

Disabling this exclusion also removes ordinary maintained native trace members
from the large-fill fixed-source ledger. Otherwise the same exclusion could
silently persist through that second path. Non-trace plotted fill contributions
remain protected, and both emitted body maps are checked for covered-copper KEEP.

The owner separately requested removal of existing pad protrusions beyond fill
edges. The bounded original-source runner accepts explicit
`--trim-pad-ordinal` values for this source-pad-outline exception. It retains
source bytes, requires the pad center inside broad plotted fill, preserves all
actual positive copper contacts (including constructed trace contacts), rejects
disconnected candidates, and rechecks the combined material component count and
absence of added physical copper. This is separate from trace widening and
changes the selected original pad outlines in derived candidates. It is not a
claim that terminal intent, export/reparse or manufacturing is qualified.

Final full-board T04 remains on hold until the identified issues are resolved
in bounded original-source cases. Evidence and the hold record are in
`out/lacie_work/t04_large_fill_audit_20261122/`.

## Earlier revision-1 policy and retained evidence

Owner-selected global source-width limit: **0.25 mm**. Entire native routes
whose source width exceeds that limit remain unchanged. Equality is eligible;
factor, total-width, clearance and other existing checks still apply.

The shared registry is `contracts/t04/trace_eligibility.json`. New T04 job
snapshots use ladder snapshot version 2, binding both the original ladder limits
and these eligibility settings. Historical version-1 snapshots remain readable
with their recorded limits. No archived snapshot or verdict is edited.

Under the earlier revision-1 policy, large filled copper and all geometrically connected routes retain complete
T04-entry contours. The provisional large-fill classifier identifies source
components containing at least 1 mm² of broad interior after a 0.125 mm inset.
Both values are configurable in the same registry. This uses complete finite
copper geometry, including holes and actual gaps; it does not infer net intent.
Ordinary small terminals alone do not establish large fill. Native inventory
and source IDs stay intact; KEEP removes growth work, not copper records.

Group construction excludes these routes before allocation and removes their
fixed sources from editable bulk roles. Its final guard independently checks
both emitted body maps, so a second bulk record cannot override an unchanged
trace record and reintroduce a cut. The uniform ladder does not construct growth
proposals for excluded routes. Source-built profiles filter the same route
policy and keep protected bulk out of their editable set.

The earlier per-occurrence coverage classifier also now recognizes curved
boundaries built by repeated short original fill strokes. Exact original
centerline/interior witnesses distinguish that fill role from full finite-body
coverage. Partly exposed traces, ordinary pad entry, gaps and exact aliases do
not independently establish this role. An owner-requested KEEP is recorded
separately from geometric coverage.

The displayed saved-board correction uses
`tools/apply_t04_keep_policy.py --connection <live connection> --output <new LaCie directory>`.
It authenticates the committed source/geometry lineage, restores protected
predecessor bodies byte-for-byte, and retracts dependent whole-route growth that
would conflict with preserved foreign copper. It synthesizes no new growth or
rerouting. Every native-route connection is checked again, all terminal bytes
remain unchanged, and unrelated source bodies remain byte-identical. The
original diagnostic result and all failed/stopped attempts are retained.

This correction also restores T04-created bumps and recesses on protected
large-fill contours. Irregularities already in the T04 input remain source
geometry; this is not a general source-contour smoothing operation.

Evidence: `out/lacie_work/t04_bulk_boundary_fix_20261122/`. The corrected board is
a **diagnostic Preview**, not a fresh full-board optimization, export, completed
T04 qualification, or electrical/manufacturing approval. Operational T01/T02/
T03/T05 execution is outside this T04-only task.
