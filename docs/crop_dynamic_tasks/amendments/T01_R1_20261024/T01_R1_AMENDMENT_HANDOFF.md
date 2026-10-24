# T01-R1 — Coverage, space-driven growth, and a preserved round priority shape

**Prepared:** 2026-10-24
**Task type:** One bounded amendment to T01 (stages 1 + 1.5), not permission to start T02–T07.
**Starting evidence:** Reported local commit `ee619a01be1f6b8d4088380b5234f06f7d33fefa`; inspect the actual checkout before making changes.
**Completion boundary:** Implement, verify, demonstrate, commit owned changes locally, and **STOP** for review.

> Improve the same crowded crop so supported circular targets are not missed, growth is decided by available neighborhood space rather than a fixed radius multiplier or uniform ring, and each admitted seed-bearing physical component has a designated round priority shape that companion growth respects.

This handoff is based on the owner's three annotated illustrations and the supplied T01 reports. It is not a fresh inspection of the implementation or a new PASS verdict. When supplied by the owner to Codex, it authorizes the bounded changes below.

## 1. Owner corrections and explicit changes to the previous task

| Owner observation | Required amendment | What must become visible |
|---|---|---|
| Highlighted areas contain missed legitimate candidates. | Reconcile the marked source occurrences, remove blanket small-circle/display-edge omissions, and safely extend computational support where needed. | Each marked target has a source-bound disposition; supported omissions are actually recovered, not hidden behind the old denominator. |
| Growth appears tied to original size rather than surrounding void space. | Use a bounded, space-responsive growth policy that can produce unequal, asymmetric growth and change relative final sizes. | Some locally roomy sites use more eligible space; tight sides stop at actual constraints. The result is not just uniform annuli. |
| A priority round shape within a component has not been preserved. | Nominate one round priority site per admitted seed-bearing physical component, reserve its selected circular outline, and adapt companion growth around it. | The priority outline remains round outside its original attachment ports; other land contours respond without fragmentation or new bridges. |

**Supersession:** The previous T01 card explicitly said not to impose a round anchor per entire physical component. For this bounded crop experiment, replace that instruction with the component-priority policy in Section 5. Historical documents and results remain unchanged. This is the owner's selected **demo policy**, not proof that every expert edit follows it or that the exact historical order is known.

The requirement is one **designated priority site** per admitted component, not a requirement to deform every other circular site artificially. Other sites may remain round where their available space permits.

The old `39 grew / 7 smaller kept / 7 edge abstentions` partition is historical evidence, not the revised eligibility definition. A priority site may legitimately KEEP. Maximizing the number of GROW labels is not the objective.

## 2. Preserve the baseline and keep the scope finite

Preserve the original ORG/EDIT files, frozen T01 run and WKB candidates, earlier verifier receipts, metadata-mismatch record, historical static comparator, audit supplement, unrelated worktree changes, and all prior stages. Do not amend old receipts or reset the checkout to the historical commit. Store new results in a new timestamped or versioned T01-R1 output directory.

Read the existing task code and policy first. Identify the actual causes of the omissions, the proposal growth law/cap, component handling, trace reservations, and shape clipping. The screenshots suggest defects in behavior; they do not by themselves prove the precise source-code cause.

**Allowed:** circular candidate selection, local source inventory/context expansion, per-component priority assignment, space-responsive circular-feature reshaping, bounded same-component attachment handling, current-scene updates, tests, diagnostics, and the existing local visual report.

**Not allowed:** noncircular target editing, trace relocation, general trace-width editing, general neck/teardrop processing, original-copper shaving, general parser expansion, a new family-recognition system, new storage/index infrastructure, gfs/pcb_Z changes, T02–T07 execution, or production release.

Land additions may overlap their own already connected trace **within a declared local attachment zone** when that is needed to avoid a self-obstacle artifact. Original trace centerlines, source widths, and geometry remain protected. This exception does not authorize filling the entire connection between distant lands or implementing T03–T05 under another name.

Use one main policy and, if useful, one bounded alternative priority/order diagnostic. Record parameter choices before the main run. No unconstrained contour search or per-site target tracing.

## 3. Correct candidate coverage without editing cropped fragments

### 3.1 Reconcile each marked location

Use `references/01_missed_candidates.png` as a review locator. Resolve every highlighted region against the existing source-to-view mapping and list all implicated native circle occurrences. Retain source revision, byte-span/object identity, center, radius, physical-component association, prior disposition, and revised disposition.

Do not treat a screenshot pixel, yellow outline, or an EDIT circle as an executable target identifier. If a marked region contains several possibilities, show them and the unresolved mapping. Do not guess an exact missed-target count from the image.

Distinguish at least:

- a supported circle omitted because of a size threshold;
- a supported circle omitted because it crosses the display boundary;
- an intentional priority KEEP;
- a genuinely protected or infeasible target with a concrete constraint;
- a noncircular/composite feature outside this circular-only stage;
- an unresolved source identity or unsupported influence.

Remove blanket rules that make every small circle ineligible. Size can be a descriptor, but cannot be the sole reason to omit a source-bound candidate identified in this review. The owner has requested consideration of these sites, not unconditional growth in violation of constraints.

### 3.2 Separate the display viewport from computational support

Keep the reported visual crop V fixed: `(1.2858444444444446, -15.687077777777787, 4.508066666666666, -12.975966666666665)` mm, subject to verification against the actual saved run.

The old inset write region and 0.075 mm halo must not remain accidental reasons to miss visible legitimate sites. For a boundary target, retrieve its full ORG geometry and the obstacles/contacts that can affect its bounded growth. Do not enlarge a clipped semicircle or truncate an accepted contour at the display edge.

This amendment authorizes a new explicit write domain W' only where needed to contain the **complete local envelope of selected edge circles**, plus a verified analysis halo H'. This may include small, declared additions outside V. It is not a whole-board editing permission. Plot outside-viewport writes in a separate audit view and verify no change outside W'.

Derive H' from the maximum admitted growth reach, separation buffer, attachment context, and any bounded contour smoothing—not from display convenience. Include crossing primitives even if their endpoints lie outside H'. Reuse full qualified source-component membership where already available. If safe influence cannot be bounded, abstain for that site with evidence; do not treat unknown exterior geometry as empty.

Publish a new reconciled denominator before running. Do not shrink the crop or eligibility set after seeing failures.

## 4. Make growth follow available space

A clipped constant-factor expansion can be dynamic with respect to neighbors yet still underuse most nearby space. T01-R1 must test and correct that distinction.

For each nonpriority circular target, use:

1. Its immutable original copper core and local original attachments.
2. A bounded ORG-derived influence region and maximum displacement/growth reach.
3. Current accepted neighboring copper, reserved round-priority outlines, protected original features, and trace corridors.
4. The actual admissible connected space remaining around the target.

The influence boundary and cap prevent runaway filling. They must not reproduce EDIT contours, be derived from the target's added/removed masks, or be chosen separately for every site to fit the answer. Prefer a shared physical-length/local-spacing policy over `final_radius = k × original_radius` as the controlling rule. Original radius may still describe the protected core.

A practical implementation can grow an optional local contour in bounded increments, allowing a blocked side to stop while another side continues. Reuse existing geometry tools; no particular optimizer is mandated. Retain only attributable growth connected to the target. Reject remote islands, slivers, and impermissible new contacts. Any smoothing or simplification must be followed by the same hard checks.

**Local objective:** use eligible space around selected lands, subject to reservations and smooth, bounded shape constraints. It is not “fill every black area” or “maximize total copper.” Trace-only open corridors outside the land influence regions remain unfilled.

At each site, retain the limiting reasons: foreign copper gap, priority-round reservation, protected connection, trace corridor, unsupported influence, write boundary, or growth cap. If most sites stop solely at a restrictive nominal cap, report that honestly rather than calling the result space-limited.

### Necessary demonstration

- A controlled same-seed open-versus-crowded neighborhood test must change the accepted growth while source core, growth policy, and numerical settings stay fixed. Pick a case where the outer cap is not the active bound.
- A controlled smaller-roomy versus larger-crowded example must show that original size does not enforce final size ordering. This proves capability, not that every real site must reverse ordering.
- Across the actual marked crop regions, show radius/area descriptors, available-space constraints, accepted contour, and stopping reason. Use actual source neighbors; do not fabricate a roomy region to improve the real-crop display.

## 5. Preserve one round priority shape per admitted component

### 5.1 What a component means here

Use **pinned ORG same-layer physical connectivity**, not visual proximity, family membership, or candidate-created connections. Carry the source component ID through every stage. Physical contact is not recovered net intent.

Retrieve existing complete component evidence when available. If only a crop fragment is qualified, retain fixed boundary ports and explicitly mark the claim as local-component scope. Do not silently cut a large component into convenient pieces to claim multiple “one-per-component” successes. Where priority ownership outside the admitted scope cannot be resolved, preserve that limitation.

For every admitted component containing supported circular targets, designate one priority site before companion growth. A singleton may be its own priority. Components with unsupported critical influence remain explicit exceptions rather than manufactured complete components.

### 5.2 Source-only selection and radius

Use one deterministic ORG-derived rule. An acceptable initial heuristic is: respect already qualified reference obligations, then prefer the largest original circular core whose outer contour can remain round with its existing ports; use a stable source identity to break ties. Record alternatives and why the selected site won. This is a demo hypothesis, not a recovered expert rule.

Default to preserving the priority site's original circle. A shared policy may instead permit a feasible **complete circular enlargement**, decided before companion growth. Record KEEP versus ROUND_GROW explicitly. “Priority shape keeping” requires preservation of the chosen round outline; it does not require every priority site to increase in size or every final radius to remain the original radius.

If a proposed circular enlargement is infeasible, keep the original supported round shape when possible. Do not clip it asymmetrically and retain a ROUND_PRESERVED label. If even that round-outline interpretation is unqualified, record an exception and keep the source unchanged.

No per-site priority assignment is taken from the annotated EDIT image. That image supplies the owner's desired pattern and later visual comparison, not a hidden target-identity lookup for the constructor.

### 5.3 Protect the visible outline, not just the center disk

Merely retaining the original circular area inside a larger irregular blob does **not** meet this requirement. Reserve the chosen circular boundary outside **ORG-derived attachment-port zones**. Other additions must not bury or distort that perimeter.

Port zones permit the existing trace to join the round site. They must be derived from original contact geometry and bounded by the contract. They cannot expand after the run to hide every deformed arc. Check roundness using the declared vector approximation/error budget, outside these port zones. Global circularity of the entire copper component is not the right test.

Reserve all selected priority outlines before companion growth, then let companions adapt to both those reservations and earlier accepted contours. Keep a meaningful crop-scale priority overlay and component legend. Exactly one designated priority site does not mean exactly one circular-looking feature may survive.

### 5.4 Do not use one obstacle rule for every trace or circle

Separate:

- other original physical components: hard separation applies;
- the selected site's existing attached trace: preserve its copper and required port; do not subtract a blanket foreign-object buffer that cuts an artificial moat into its own land addition;
- another feature/branch in the same original component: membership alone does not authorize a new shortcut, broad bridge, or loss of a protected priority perimeter;
- prospective future trace corridors: preserve their declared availability; do not fill them to improve appearance.

Admit land-to-own-trace overlap only inside the specific local port zone. Check outside that zone as protected context. No general trace/neck editing is authorized here.

## 6. Integration order and automatic verification

Use one evolving working scene over existing source objects and indexes:

```text
verify source and previous baseline
reconcile candidate coverage and complete edge-target support
freeze revised denominator, W', H', constraints and experiment policy
resolve original components and nominate/reserve round priority sites
for each remaining circle in a deterministic source-only schedule:
    retrieve current accepted geometry and component/port roles
    grow a bounded contour according to admissible local space
    verify core, priority boundary, port, gap, scope and geometry validity
    accept atomically or retain a documented KEEP/ABSTAIN/REJECT
    refresh affected index entries and retain the actual scene event
recheck the assembled scene, not just individual proposals
build effective-copper and diagnostic views; run comparisons and tests
commit owned files locally and STOP
```

If a candidate fails, reject it before publication. One bounded local retry/reconsideration is permitted; retain failures and previous accepted scene. Internal checkpoints do not require human approval. Do not continue to another task after this amendment.

### Numerical policy

Retain the reported **0.020 mm hard experimental separation threshold** and the **0.00001 mm numerical tolerance**, with the same documented predicate. Keep 0.025 mm as a nominal construction buffer unless a separately recorded experiment changes construction only; it is not a promised final gap. Do not loosen acceptance to obtain a result. Report raw minimum distances and the object/component pairs producing them.

Apply separation to the declared forbidden-contact pairs and growth/protected-obstacle relations. Do not apply an artificial 0.020 mm gap across an intentional original connection; equally, do not call every pair in a connected component automatically exempt. Existing source violations remain reported and may not be expanded without a separate policy.

Round-outline and reach approximations need explicit tolerances tied to existing geometry precision. No calibration of tolerances after observing a failure.

## 7. Required verification and honest comparisons

| Check | Required evidence |
|---|---|
| Coverage | Every marked source candidate accounted for; supported size/boundary omissions recovered, with complete geometry and sufficient context. Valid priority KEEP is distinct from a missed target. |
| Edge handling | Full-envelope calculation; a slightly expanded presentation viewport does not change decisions for the same already selected feature set and analysis domain; no changes outside W'. |
| Space response | Open/crowded and size-order controls; actual directional growth/stopping reasons in the owner's highlighted regions. |
| Priority roundness | One source-bound designated site per admitted component; original/full-round selected boundary survives outside fixed ports after all companion growth. A “core retained but outline buried” negative control fails. |
| Component distinctions | A valid local own-trace attachment is not treated as a foreign moat. A foreign trace/circle cannot be bypassed by giving it the same display label. No new prohibited bridges/shortcuts. |
| Dynamic causality | Retain three real-crop single-neighbor counterfactual examples where available, with other prior candidates fixed; shared-parser/kernel qualification remains explicit. |
| Assembled validity | Original cores and protected copper preserved; valid attributable additions; no detached islands, prohibited contacts, or hard-gap failures; final priority outlines and scope rechecked. |
| Reproducibility | Same inputs/order/policy yield identical canonical output; disabling EDIT access does not alter construction; stale scene/index is rejected or rebuilt. |
| Fair comparator | Static/frozen-neighbor diagnostic uses the same target set, component reservations, source trace/port policy, buffers, curve settings, caps and growth algorithm. Only evolving-neighbor updates differ. |
| Publication | Exact source/candidate/view bindings, correct units and revisions, clear limitations. Missing labels or geometry fail closed. |

Keep the original T01 baseline, a same-policy frozen-neighbor diagnostic, and T01-R1 separate. Cross-version improvement is not an isolated causal test because eligibility, priority, and growth policy all change.

For the static comparator, report union area as well as summed additions and assembled violations. A larger but infeasible area is not a better solution. A controlled no-priority or alternative-order diagnostic may help verify the priority policy, but preserve its deliberate changes and failures separately.

Do not carry forward “all 32 dynamic differences are causal” or “0.025 mm final clearance.” Separate recomputation using the same source parser and geometry kernel remains shared-implementation evidence, not an independent interpretation of PCB semantics.

## 8. Deliverables: three clearly closed owner observations

Reuse the existing report builder and viewer. Provide:

1. **Owner-issue closure table:** issue 1/2/3 → source locations → previous cause/rule → implementation change → focused tests → actual crop evidence → remaining exceptions.
2. **Selection and priority map:** all source-bound candidates, recovered omissions, KEEP/ABSTAIN/REJECT reasons, original component IDs, designated priority sites and fixed port zones.
3. **Three full-crop images at the same frame and scale:** ORG; frozen original T01; amended T01-R1. Use single-color effective copper for the main shape comparison, plus separate original/addition overlay. Green-only rings must not be mistaken for disconnected effective copper.
4. **Three issue-focused views:** the marked omissions; asymmetric, space-driven growth; and round priorities with companion contours. Reuse the supplied EDIT crop as a clearly labeled visual reference, not numerical ground truth from pixels.
5. **Machine-readable decisions and verification:** source/revision/policy hashes, target/priority IDs, scene versions, raw gap measurements, effect of controlled replays, final geometry, exact test commands and results. Compact append-only receipts, no duplicated historical archive.

Report per-site original and final land descriptors and added areas without double counting shared contributions. Do not force total new area to exceed the old run: newly preserved priorities and more complete obstacles can reduce permissible growth. Claim improvement through the three specific corrected behaviors, not an inflated area or test count.

## 9. Acceptance and mandatory stop

**PASS WITH SCOPE LIMITS** is justified only when all three owner concerns have concrete implementation and actual-crop evidence, required local geometry checks pass, and material highlighted supported sites are not still missing. The full-crop result must visibly show the new behavior, not merely have code that supports it on tiny fixtures.

**PARTIAL** if the mechanism is implemented but a material owner-highlighted case remains unresolved, the priority/space-driven behavior is not demonstrated in the real crop, or a required evidence dependency is missing. **BLOCKED** if reliable source/frame/geometry preconditions prevent execution. A documented omission is not automatically a closed issue.

No native-export acceptance, full electrical connectivity, engineering/manufacturing approval, expert-equivalence claim, or final EDIT-fit objective follows. T03–T05 remain responsible for later path/width/junction quality. T01-R1 must not claim to finish those stages, but obvious self-obstacle gaps caused by its own land-growth logic must be corrected here.

Record a new local commit containing only owned source/tests/docs. Preserve ignored evidence locally with its manifest and report paths. Do not push or publish remotely. Do not paste summaries, hashes, or PCB material into a browser/search field for automated review. Prepare a local review packet; external review remains NOT_RUN unless a verified, separately authorized channel exists.

**STOP after T01-R1**, whether PASS, PARTIAL, or BLOCKED. No automatic T02–T07 progression. Return the closure table, full-crop images, measurements, evidence paths, commit, exact working-tree status, and remaining limits.
