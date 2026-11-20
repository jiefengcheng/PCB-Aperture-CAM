# Direct parallel-group construction: bounded increment

## Standing EDIT direction

EDIT is the standing visual/behavioral reference, including details the owner
has not individually enumerated. Use the common-coordinate EDIT panels in
`out/lacie_work/t04_25_incremental_20261119/FIVE_incremental.png` throughout
development. Observations from those retained panels:

- Case 1: sustained growth along the long straight runs and continuous bends;
  short separated growth islands do not represent the intended treatment.
- Case 2: growth carries along the vertical runs into the curved fanout. A short
  band at the bottom does not represent the intended full-length profile.
- Case 3: diagonal runs retain continuity into bends and terminal/bulk shoulders.
- Case 4: the simple parallel corridor is a reference for consistent widths and
  gap use without unnecessary positional disturbance.
- Case 5: growth continues through broad curves and meets reshaped bulk with
  smooth transitions, rather than stopping at category boundaries.

Investigate material departures proactively. Use source-bound caps, construction
constraints and the applicable default-case decisions to explain departures;
visual resemblance alone is not a clearance proof. EDIT does not set numerical
clearance or authorize changing immutable source data.

Comparisons must identify assembled candidate copper versus a partial diagnostic
overlay. A partial overlay cannot establish that full-length growth is achieved.
The currently retained short-island joint overlay does not meet Cases 1/2's
intended outcome. Full-length continuous materialization remains pending.

The 2026-11-20 increment replaces the allocation step only. It reuses accepted
T03 intake, original owner preparation, source-role classification, native route
projection, the source-wide parallel catalogue, artifact storage and attempt
latches. Historical checked 25%/side-growth studies remain immutable references.
The ordinary pipeline and the old explicit checked-profile entry remain intact.

## Implemented boundary

`profile_job construct-groups` dispatches through `profile_stage` to `group_stage`.
It produces group-interior recipes and residual work items, **not a completed
T04 scene**. Its result has `output_scene_ref: null`, `publication_ready: false`
and `GROUP_INTERIORS_CONSTRUCTED; HYBRID_ASSEMBLY_PENDING`. No existing full-board
qualification can enable this command. Replay/export and full-board execution
are unavailable.

The algorithm uses these existing and narrow new pieces:

1. `source_roles.prepare_or_load/project` and `limiting_growth_v2.catalogue`:
   immutable source membership, bulk roles and parallel relationships.
2. `group_boundaries.SourceBoundaries`: compile conservative source supports
   once into scalar face limits. Native chord tubes include approximation
   margins. Other mutable source occurrences reserve their possible growth and
   displacement. Source-framing memo eviction recomputes; it never removes work.
3. `group_allocation.maximum_faces`: integer bounded max-flow. Trace nodes supply
   width budgets; gap nodes share capacity between facing edges. Lower bounds
   preserve source width even when an edge retreats. A matching generalized
   minimum cut certifies maximum summed growth **within the supplied position
   and face bounds**. Proportional fairness is not an objective.
4. `group_profile.solve_band`: plot new ideal straight boundaries from the solved
   coordinates. Angularly approximate catalogue entries are not promoted to an
   exact parallel construction scheme. Their treatment remains residual.
5. `route_join_plan/consecutive_widths`: propagate the 25% limit through actual
   source endpoint adjacency only. A route may span more than 25% overall.
   These bounds feed the same group solver; there is no route-wide minimum cap.

Source junction windows partition long groups before allocation. They do not
discard the unaffected interior. No candidate polygons, binary-search widths,
dense normal-section probes or final native geometry audit run in this entry.
Numerical certificate and immutable-input verification remain engineering tests.

## Remaining assembly work

### Maximal members and smooth fields — 2026-11-20 continuation

`group_membership` extends consecutive native straight runs before selecting
parallel cohorts. Each member retains its full, potentially unequal length and
the original reference points. The provisional 1% direction parameter means
`abs(sin(direction difference)) <= 0.01` (about 0.573 degrees). It applies to the
whole member's direction span, preventing a chain of small turns from admitting
a substantial bend. Breaks and actual direction changes stop extension; a
catalogue membership event does not. Existing primary-cohort selection prefers
larger summed full-member lengths; this is deterministic selection, not a proof
of a globally optimal partition. All nonprimary relationship witnesses remain.

Curve members retain their whole native arc identities and the existing 1%
fit witnesses. A witness does not certify an extrapolated fit outside its
recorded domain. No individual centerline is rotated or refitted.

`continuous_profile` shares one width/side field across exact-collinear,
equal-source-width constituents of a maximal member. Original source IDs remain
custody boundaries, not new taper endpoints. Polynomial restriction preserves
both values and tangents across those boundaries, including reversed native
source directions. Approximate polylines, source-width changes and explicit
default decisions retain separate construction obligations; they are not
silently straightened or overwritten.

Transitions use all available free length between constraints. Cubic side
fields have zero endpoint derivatives at their true transition boundaries.
The provisional maximum side slope is 0.25 mm/mm. Insufficient length or
conflicting group fields remain unresolved; the coherent path does not clip
them into irregular shapes or fall back to short widening islands. The
Bernstein control-budget helper certifies a supplied paired affine corridor
algebraically. Independent source-field smoothness alone does not certify a
cross-route corridor or a curved joint.

This continuation is integrated into the bounded diagnostic caller. The older
strip allocator still certifies local overlap interiors; the new membership
catalogue does not retroactively certify all their extended portions. Coupled
group allocation, common-route reference feasibility and cross-source curved
joins remain publication gates. No constructed-group geometry audit is added.
Evidence: `out/lacie_work/t04_maximal_members_20261120/`.

The 2026-11-20 component continuation is available through
`construct-groups --components`. It reuses the existing quad materializer for
joint collars, `preserve_connections` for bulk cuts/recovery, and
`verify_width_scene` for joint/residual physical checks. Group strips are fixed
operands, never checked trace candidates. Residual offsets always start from
source copper, and retain the captured seven-pass increments. OriginalOwners
checks connectivity across assembled route interfaces using the fixed strips
as support. Failed joint checks and bulk restoration conflicts remain failures.

This is component diagnostic execution. It does not publish a completed scene:
functional/source-void verification and final width-band reconciliation are
still required. Joint candidates rejected by physical checking require further
construction treatment. Both saved cohorts may exercise zero actual bulk cuts;
separate positive-cut and disconnect/recovery controls test that mechanism.

Evidence for this continuation is `out/lacie_work/t04_components_20261120/`.
The remaining paragraphs describe the group-interior increment's boundary.

Group-only mode publishes a width plan; component mode now materializes and tests
joint candidates, bulk cuts/recovery and residual growth. Whole-scene publication,
shared route poses, functional/source-void checks and final width reconciliation
remain pending. Interface boundaries and bulk changes do not receive an invented
construction guarantee from the group solver.

The provisional transition outlier parameter is computed as
`2 * (maximum_total_width_increase + maximum_translation)` = 0.11 mm with the
current inputs. It is a future transition extent guard, not a clearance proof or
another width-band restriction. No transition shape is claimed by this increment.

## Explicit bounded invocation

```sh
tools/Run_T04_Profile.command prepare \
  --accepted-t03 "<accepted T03 job>" --output "<new LaCie job>" \
  --algorithm parallel-groups
tools/Run_T04_Profile.command construct-groups \
  --job "<new job>" --route-ids "<bounded native route IDs JSON>"
```

The existing `run` command requires a checked-profile job. Switching the prepared
algorithm or resuming an attempted job is rejected. Saved source-only preparation
may be copied into a new job; all existing scene, source, algorithm, owner and
content bindings are revalidated before use. Saved T04 copper/proofs are not
inputs to this constructor.

Evidence: `out/lacie_work/t04_group_execution_20261120/`. Its report distinguishes
numerical allocation time, source preparation and actual caller wall time from
the **unmeasured, incomplete full hybrid stage**.

Machine-readable boundary:
[`t04_group_construction.json`](../../contracts/agent_abi/t04_group_construction.json).

## Bounded native joint continuation — 2026-11-20

The hybrid caller now adds joint copper after the frozen straight and maximal
arc bodies and the existing default growth. It reads the actual frozen skins,
retains native normals at artificial taper cutoffs, and transports a convex
endpoint-section blend through the native frame. A face can use the full
member length when the opposite end does not compete. Gentle endpoint-step
slopes of 0.25 are preferred; crowded joints may use a shorter blend up to 1.0.
This slope parameter is separate from consecutive-segment width deviation.
The 0.11 mm reach guard and the joined input-face envelope remain binding.

Equal widths at a native endpoint can hide a notch on its neighboring arc
shoulders. A second local pass reuses `junction_spindle_blend.spindle_addition`
on the two adjacent native members and their own route's accepted joint
additions. Other routes on the same electrical owner cannot supply support.
Its provisional rolling radius is 0.05 mm and maximum added skin depth 0.005 mm.
The longitudinal shoulder is at least 0.015 mm and at least the joined input-face
radius, covering the whole noisy plotted end-cap footprint. Alignment reuses the
catalogue's interior tangent rather than the rounded final source chord.
The mask is restricted to the source-path
input-face envelope. Changes smaller than the existing 10 nm file uncertainty
are omitted. Existing source holes/copper are never replaced by the closing.

Both passes retain supported overlap instead of storing a tangent-only delta.
Only positive new joint copper is checked against foreign copper and pin
domains, through one shared local scene index. Crowded proposals can reuse the
existing conservative obstacle mask; these are reported separately as
`FILLED_TO_CLEARANCE_LIMIT`, not as fully resolved endpoint obligations.
Constructed group bodies and the durable membership are unchanged and receive
no geometry audit. Covered source occurrences remain KEEP.

The joint assembler also uses the existing void kernel to identify pockets
newly enclosed by overlapping joint additions. It excludes all preexisting
route holes and fills a new pocket only if the entire pocket is inside the
admitted joint envelopes and passes the existing foreign-copper and pin-domain
checks. It does not partially seal a rejected pocket or alter a group body.
This preserves the approved growth while preventing a small enclosed slit
between overlapping corner fields.

These paths remain bounded component diagnostics, with source-scene publication,
unresolved interfaces and complete-stage acceptance still explicit. No native
export, full-board run or pipeline replay is implied. Current continuation
evidence is under `out/lacie_work/t04_corner_smoothing_20261120/`.
