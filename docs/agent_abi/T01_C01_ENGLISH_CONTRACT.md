# C01 T01: English → precise contract → ABI-only execution

The dedicated branch `codex/t01-c01-english-contract-abi` adds complete C01
priority/companion semantics through `tools/t01_agent_abi.py`. The original
five-suite ABI and its round-only T01 profile are unchanged. The two profiles
are explicitly different; passing one does not qualify the other.

Interface revision `t01-interaction-abi/1.1` adds source-bound English and selection
references for language operators, while retaining literal request forms. The
same canonical English compiles to the identical policy through either form;
all C01 geometry methods and the English semantic compiler remain unchanged.
See [T01_OPERATOR_SLICES.md](T01_OPERATOR_SLICES.md) for the failed literal-input
operator experiment, assisted transport and subsequent slice gates. Run 298 below
is the preserved pre-extension native reproduction; new operator runs require
their own receipts and cannot inherit that verdict automatically.

The operational summary is:

> Allocate neighboring circles together using admissible physical diameters.
> Reserve source-qualified round priorities first. Use enlarged A's inscribed
> square to bound B's envelope. Construct companions against the current scene,
> clipping only optional copper while retaining original cores, fixed source
> attachment ports and clearance. Each accepted contour becomes the context for
> subsequent construction. Apply the S31 recess only to its bound source identity.

This summary is supported by the exact, versioned controlled English in
[`contracts/t01/c01.english.txt`](../../contracts/t01/c01.english.txt). It is an
executable input vocabulary, not unrestricted natural-language interpretation.
All fifteen ordered clauses are mandatory. Only outer blank lines and CRLF/LF
differences are normalized. Missing, reordered, duplicated or paraphrased clauses,
including a changed clearance, are rejected. Extending the vocabulary requires a
new reviewed dialect or version; no LLM guesses or fallback implementation runs.

## Contract and source identity

`src/t01_abi/contract.py` compiles every clause into a named typed rule and records
its English wording, rule value and clause ID. The compiled policy carries the
canonical English SHA256, exact numerical settings, palette and a trusted
source-binding artifact reference. The complete policy is rederived and compared
before discovery/planning/execution/verification; modifying JSON fields without
the corresponding supported English cannot change the semantics.

The closed machine contracts are:

- `contracts/t01/policy.schema.json`: compiled semantic policy.
- `contracts/t01/request.schema.json`: T01-only wire requests.
- `contracts/t01/response.schema.json`: T01-only wire responses.
- `contracts/t01/c01.binding.json`: original source/cache/crop/seed/exception
  identities, with no saved target radius, group, priority or candidate contour.

The host imports the original board and full hash-bound F.Cu cache into the local
artifact store. Its source manifest is
`0c3e75925053a649a3c14e0449555a2faa7a814c061beb26ef1fc29a96605101`.
The native board is
`850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0`.
There are 17,849 source objects. Discovery finds 51 canonical circles and 53
occurrences in the C01 viewport, including covered and complete edge circles.
Duplicate occurrences are aliases, not separate growth decisions.

The original cache is the qualified geometry input for this reproduction. A raw
filled-circle source-span scan independently cross-checks occurrence coverage.
This does not claim a fresh KiCad export or independent parser qualification.

## Exact interpretation of the interaction

These definitions disambiguate the concise English and preserve the actual C01
computational model rather than replacing it with a superficially similar rule.

| Clauses | Precise interpretation | Implementation |
|---|---|---|
| R01–R03 | Original mm/F.Cu source/cache only. Discover filled zero-stroke circles intersecting the bound crop, without a covered-circle or nearby-trace exclusion. Merge identical WKB aliases. Computational center is the cached polygon centroid; radius is `(width + height) / 4`. Preserve those exact floats and the exact original core. | `src/t01_abi/source.py` |
| R04 | Traverse exact original surface intersections across the whole board. Hash the sorted component source identities. This physical contact relation is neither a net label nor a growth competition group. | `source.discover` |
| R05 | Preserve the reviewed pair first. A remaining pair competes if `center_distance - 1.5*(rA+rB) <= construction_gap`. Sort by `distance/(rA+rB)` then the two sorted source identities; greedily take disjoint pairs, then singletons in site order. | `crop_balanced_t01.local_groups` |
| R06 | Within each physical component, try descending source radius then ascending identity. Qualification requires source-boundary radial residual at most `0.00002 mm` and no non-port obstacle intersecting more than `0.00001 mm` of its exposed boundary. Remove the explicitly bound S31 priority without selecting a replacement. | `choose_priorities` and `InteractionAdapter._allocate` |
| R07–R08 | An admissible class strictly exceeds original diameter and does not exceed `1.5×` original diameter. Prefer the largest common class per pair, otherwise individual classes. Source-infeasible priorities descend classes. When grown priorities conflict, demote every growable priority participating in a conflict by one class simultaneously. KEEP is exact source. Never transmit a priority reduction as a common scale factor to its companion. | `crop_diameter_selection.select_targets` |
| R09 | Choose the smallest-identity priority in the pair as A, otherwise the first pair member. Derive its square at −45°. Select the outward normal with greatest alignment toward B; ties use square-local `+X,+Y,-X,-Y`. Set `boundB = dot(normal, centerB-centerA) - construction_gap - safety - radiusA/sqrt(2)`. Descend B's classes until `radiusB <= max(original_radiusB, boundB)`. | `select_targets`, `facing_square_side` |
| R10 | Consider each priority's next class up to its desired target. Require source/port feasibility, all other round reservations and every affected square bound. Promote the feasible option with greatest round-area gain, then identity tie-break. Repeat to a maximal discrete allocation; do not claim a global optimum. Recompute square bounds using final radii and retain every next-class stopping explanation. | `promote_round_priorities` |
| R11–R12 | Round priorities first by identity, then companions by centroid Y,X,identity. Query the live alias-aware scene; apply fixed original ports, never a whole-component exemption. A round priority uses its source core union enlarged polygonal circle. Companions clip optional growth against every applicable current obstacle; retain only additions attached to the original core. Atomically replace all aliases and rebuild the spatial index after each accepted contribution. | `crop_balanced_t01.execute`, `WorkingScene`, `construct` |
| R13 | Only the bound S31 source identity may use the extra square recess. Select the greatest optional-envelope overlap with an applicable buffered obstacle, then identity tie-break. The nearest applicable point determines the square-facing lobe. Remove that optional lobe, retain the source core, then apply every ordinary obstacle constraint. The square never replaces source copper. | `crop_square_recess.square_guided_recess` |
| R14 | Original per-site cap `1.5×`; palette `[0.038,0.0761,0.2749,0.2999,0.3374,0.3749,0.4499] mm`; construction gap `0.02002 mm`, hard gap `0.020 mm`, safety `0.00002 mm`; 128 segments per quadrant; area epsilon `1e-10 mm²`, event epsilon `1e-8 mm²`. | Compiled policy settings |
| R15 | Recompute source discovery, allocation, all contours, events and controls from original operands. Compare exact saved geometry references and semantic ledgers, then all source contributions and output lineage. Separately check each candidate against the final assembled scene. A modified radius, priority, contour, group or protected contribution cannot verify. | `InteractionAdapter.verify`, `check_output` |

The fixed original trace-contact port is derived only from an original segment or
arc intersecting `core.buffer(1e-7 mm)`. Its zone is the original trace surface
buffered by `max(0.005 mm, source_width/2 + 0.005 mm)`, intersected with
`core.buffer(0.5 * original_radius)`. Source/live neighbors are queried over the
complete `1.5×` cap plus a `0.031 mm` influence band. New contacts outside these
ports are not authorized. Finite copper surfaces, not centerlines, determine gaps.
Inherited core geometry is retained; every new optional intrusion into a hard-gap
buffer above the bound area epsilon rejects the proposal. Optional disconnected
parts farther than `1e-9 mm` from the core are discarded.

These are the original C01 profile's explicit numerical and port rules. The
shared `PreparedLandScene`, `PreparedWidthScene`, `trace_width_clearance`,
`crop_stage_growth` and `stage_abi/lands.py` remain byte-identical. No shared
clearance rule was relaxed to obtain the reproduction.

## ABI-only program

The new entry point exposes only T01:

1. `t01_compile`: controlled English + registered source binding → policy and
   clause-by-clause derivation.
2. `t01_discover`: bound original scene + policy + registered bounds → complete
   source discovery and selection artifacts. No host-generated target set.
3. `t01_inspect`: inspect the discovered identities.
4. `t01_plan`: derive groups, priorities, diameter targets and ports under the
   explicit strategy `priority_companion_growth`.
5. `t01_run`: generate actual contours and neighbor/recess controls.
6. `t01_verify`: reconstruct all 51 source decisions and check the assembled scene.
7. `t01_compare` / `t01_review`: source-bound deltas, images and recorded status.

`t01_describe` reports the registered family and exact implementation digest.
The original stage envelope, artifact store, journal, authorization and immutable
output-scene machinery are reused without changes. The T01 facade validates the
new strategy; the old round-only strategy is rejected at this entry point. T02–T05
requests are rejected. The five-suite command remains unchanged and does not
silently gain a different T01 adapter.

The host imports source operands, registers the compiled profile, binds the plan
to authority and supplies finite budgets. Those are explicit coordinator duties.
It never calls discovery, allocation or a geometry constructor directly. The
reproduction runner invokes each operation in a separate JSON CLI subprocess and
retains request, response, registry snapshot, command, exit status and hashes.
Only after construction and verification does it compare decoded candidate
geometry against the frozen C01 target.

```sh
.venv/bin/python -B tools/reproduce_c01_t01_abi.py \
  --output out/crop_dynamic_tasks/t01_c01_english_abi_FRESH_NAME
.venv/bin/python -B tools/render_t01_abi_reproduction.py \
  out/crop_dynamic_tasks/t01_c01_english_abi_FRESH_NAME
```

The output path must be fresh. No accepted artifact is overwritten. The runner
checks assets before the run and compares all protected C01/C02/C03 freezes and
all 484 original code-baseline hashes before/after. It also checks idempotent
reuse of the exact successful construction request.

## Evidence and boundaries

The delivered final run is
`out/crop_dynamic_tasks/t01_c01_english_abi_20261031_298/`.
Its `RECEIPT.json`, `C01_SOURCE_MATCHES.json`, `TRANSCRIPT.json` and `wire/` establish
the execution path and full C01 scope. `visuals/index.html` contains aligned
source / earlier C03 round-only / new ABI views, C01 reference comparison, full
and detail views, actual neighbor-restoration and S31 recess-disabled controls,
exact source hashes, measurements and rejected wire cases.

The preceding run `..._297/` is preserved as an implementation checkpoint. Small
subsequent validation hardening changed its adapter identity; use run 298 for the
final implementation, never relabel the earlier receipt as current.

All 51 canonical contours match frozen C01 byte for byte, including complete edge
circles; all 53 aliases are updated correctly. The decision, priority and radius
at every site and all local groups match. The common visible crop is compared
geometrically with `1e-10 mm²` tolerance for Boolean-union roundoff; this is kept
separate from exact per-source byte equality.

Thirty-four neighbor-restoration controls affect 18 companion sites. They are
responses to reserved round priorities. Zero evolving-companion effects are
demonstrated in C01; this reproduction does not claim otherwise. S31's square-only
disabled control changes `0.0034545096992934193 mm²` at fixed source, target radius
and scene revision.

Changed English clearance, duplicated clauses, unregistered execution authority
and a tampered candidate radius are rejected on the actual wire. Unit regressions
also challenge omitted clauses, changed typed rules, changed original operands,
missing source records, alias updates, malformed requests, old-profile strategy,
cross-stage requests, changed priority/geometry and budgets. These checks support
this specific contract and source case; they do not claim general-board T01
qualification or that an English paraphrase has the same meaning.

All new outputs remain separate candidates. Owner acceptance for the new run is
not granted. Cursor independent review is `NOT_RUN: CHANNEL_UNAVAILABLE` because
no direct authenticated agent channel is available. Verification shares the
source cache, parser family and Shapely kernel; it is not independent native,
electrical or manufacturing qualification. No later-stage construction campaign,
commit, push, upload or external service action is part of this delivery.
