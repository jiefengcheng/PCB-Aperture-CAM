# Revised ladder: freeze only a valid cumulative stage

The user-supplied goal of 2026-10-28 supersedes the historical permission to pass
T02 corner/endpoint shortfalls to a future trace session. Historical geometry,
receipts and ledger dispositions remain preserved. Their review history does
not qualify them as predecessors under this revised contract.

Each stage discharges every applicable F.Cu geometric obligation introduced or
worsened by its own changes before freezing. Downstream stages improve a valid
predecessor. They do not legalize invalid predecessor growth.

| Stage | Writable geometry | Freeze conditions |
|---|---|---|
| T01 | Selected eligible circle growth | Source core, required source contacts, roundness where required, radius cap, and applicable surface gaps pass. Covered or uncertain circles remain unchanged. |
| T02 | Selected eligible rectangle growth | T01 stays fixed. Complete rectangular contour, fixed center, per-axis ceiling 1.25, and **all** side/corner/endpoint surface interactions pass. |
| T03 | Bounded authorized anchors and intervening trace route | Original width fixed; complete finite-width route, contacts, fixed lands and unrelated copper pass. A failed proposal retains the valid predecessor. |
| T04 | One uniform width for each defined eligible complete trace | Route geometry fixed; maximum feasible uniform width bounded by 1.5 times verified original width. The ceiling is optional, never mandatory. |

## Geometric interactions

- The agreed hard F.Cu copper-surface floor is 0.02000 mm. This revision uses
  0.02010 mm as a conservative construction guard for changed copper. It exceeds
  the existing 0.02002 mm construction target; it does not weaken it. The larger
  margin avoids repeating the earlier near-zero uncertainty margin experiment.
- Sides, corners, endpoints and oblique approaches use the same rule. A source
  component label grants no clearance exemption or new contact permission.
- The whole unchanged source core is retained. A disjoint original source pair
  cannot acquire a new point or positive-area contact through growth.
- An explicitly identified original source intersection defines a local
  attachment port. Its geometry is the exact original intersection buffered by
  the original trace width plus 0.02002 mm (or 0.02002 mm for a non-trace source).
  Preserve the original overlap. Added copper outside that port must pass the
  construction guard against the neighbor. This finite local exception is
  recorded per source pair; it does not exempt the rest of the trace.
- An original below-floor gap may remain unchanged under the growth-only scope.
  It cannot be reduced, and new copper outside a local attachment port must
  independently pass the construction guard. This does not authorize repairs
  to unrelated original copper or require an electrical-record recovery campaign.
- Comparison epsilon is 1e-12 mm and area epsilon is 1e-12 mm². Neither waives
  the hard floor. The model retains the inventory's declared curve approximation
  bounds. Native serialization, electrical applicability and manufacturing
  qualification remain separate and are not asserted here.

## Focused C02 demonstration

The new demonstration starts from the exact ORG source hash
`850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0`
and the established complete C02 viewport. Its selected set is:

1. C013, the sole actually grown circle in historical C02 T01, rebuilt as a round
   source-centered proposal up to the historical 0.1687 mm radius, bounded by
   1.5 times the original radius. This is an explicit T01 positive-example site.
2. The 11 exact source rectangles behind the 15 historical growth-introduced or
   growth-worsened witnesses in the complete 19-row causality packet. Selection
   comes from exact source IDs, not approximate markers.

All other original source copper stays fixed. Covered circles receive no
independent growth. No old T03 route candidate is included in this revised
predecessor. The old 19-row comparison remains evidence, without changed ledger
dispositions or an inferred mandatory electrical repair count.

For each target, propose safe positive growth within the existing ceiling.
Rectangle axes may grow differently and the outline remains a complete
rectangle. The bounded search uses two fixed axis orders with fixed iteration
counts; it does not claim globally maximal area. A target with no safe positive
growth is **NOT_COMPLETED**. Retaining it unchanged protects the scene but is
not credited as successful growth. A scene-validity result and target-objective
completion are reported separately. No stage is labeled frozen while its
required target objectives or designated slice audit are unresolved.

## Evidence and transition

Save the actual full-source viewport, T01 result, cumulative T02 result, exact
added copper, source-object identities/hashes, all proposal checks and separate
rejected-proposal evidence. Use identical coordinates and scale. Recheck every
replacement against the complete resulting scene after assembly, including
growth-growth interactions. Keep original trace widths and geometry unchanged.

The designated Safari ChatGPT audit conversation reviews each meaningful slice.
No new audit chat, parallel reviewer, ABI suite or presentation milestone is
introduced. A model-space pass is not electrical or manufacturing acceptance.
Construction of a T03 anchor experiment waits for a compliant frozen predecessor
under this revised contract and the applicable slice verdict.

## Coverage continuation and proposed local attachment correction — 2026-10-29

The user resumed work and requested complete focused candidate coverage. REV05
therefore accounts for all 80 historical eligible sources and reconstructs all
74 rectangle sources referenced by the saved trace-work records; six remain
unchanged context. Record membership selects a candidate, not a genuine defect.
The designated audit accepted this coverage checkpoint: 69 positive exposed
growth outcomes, five unchanged objectives, and complete model-space checks.
This does not freeze T02 or qualify all 80 sources for growth.

That audit admitted an R080-only correction and regression slice. The proposed
opt-in checker binds the exact original rectangle, adjacent arc and overlapping
feed by original source hash and byte spans, native endpoint equality, equal
original width and original feed coverage of the raw nearest-gap segment. The
port remains the original rectangle/feed intersection buffered by the verified
width plus 0.02002 mm. It cannot be supplied or enlarged by the caller.

For that qualified local relationship, the filled raw primitive-pair distance
is distinguished from an exposed conductor gap. The proposed checker retains
the no-new-source-contact rule, the outside-port hard floor, the ordinary
outside-port added-copper guard, and the guard from actual exposed addition to
the full adjacent arc. No component/net label is used. Default checks without
this explicit source-bound support retain their previous behavior.

REV06 proposes only the 1.01-by-1.01 R080 positive control; all other 74
replacements remain byte-identical. Fifteen regressions and full-scene replay
pass author-side. This proposal requires the separately requested designated
audit before completion credit or stage freezing. The other four unchanged
rectangles and six context sources are not reopened by this slice.

## Conditional T03 deferral — user direction, 2026-10-29

For the revised scene, T03 accommodates clearance problems introduced or worsened
by authorized T01/T02 growth. If the completed, frozen predecessor has none,
retain prior T03 results unchanged and record `NOT_NEEDED_FOR_THIS_SCENE` for this
lane. Do not invent route changes to repair unchanged original relationships.
This condition does not waive any unresolved T02 target or slice audit, nor
claim native/electrical/manufacturing clearance. T04 remains `NOT_RUN` until its
predecessor and transition gate are satisfied; proposed uniform full-trace
width growth must pass finite-width copper-surface checks at no more than 1.5×.
If a later proposal cannot fit, reject or limit that proposal and record the
constraint rather than implicitly authorizing route changes or width reduction.

## Collective parallel-trace width growth — user direction, 2026-10-29

T04 must primarily determine growth collectively for immediately neighboring
parallel traces. Use a shared growth scale for each qualified neighboring group,
so its member traces grow together rather than consuming each other's corridor
through sequential greedy widening. Each member retains one uniform width over
its defined complete trace and its fixed route. Its proposed width is the common
scale times its own verified original width, never more than 1.5 times that width.
The limiting constraint can be any member-to-member spacing, fixed surrounding
copper, required original attachment, or the ceiling. A complete trace's remote
sections also constrain that common scale; local bundle clearance alone is not
sufficient. Shared members between groups must have one consistent full-trace
width; do not silently apply conflicting local widths or expand writable scope.

This records the user's intended T04 behavior; it does not claim T04 execution
or qualification. Finish the valid land-stage freeze and applicable audit gate
first. Preserve ambiguity explicitly where source evidence cannot establish a
complete trace, parallel membership, original width or attachment. Do not change
routes, narrow source traces or shrink accepted lands to manufacture a pass.

## Current sequence and documentation consolidation — 2026-10-29

The current explicit owner order is T01 → T03 if needed → T04 → T02 → validation.
Earlier T02-before-T03 prerequisites and T04-NOT_RUN text above describe historical
checkpoints. Current C02 result232 contains T04 then T02 growth, no T03 route
changes, and recorded human visual acceptance. Independent packet234 audit is
still in progress, not passed. The stage-owned-validity rule remains in force.
See [T03 architecture](t03_architecture_notes/T03_CODE_STRUCTURE.md) and
[proposed ABI](t03_architecture_notes/T03_AGENT_ABI_PROPOSAL.md); no new ABI
functions or route execution are implemented by the consolidation.
