# ORG family-map contract v0.1

Status: bounded ORG-only candidate-member, physical-group, and provisional family-hypothesis records are implemented and freshly reopened. G1 and G2 passed reported-evidence static audits. The first recognition review passed the bounded implementation but required stronger full-reference closure before manual/UI review; those checks are now implemented and included in the v2 audit pack. Engineering and manufacturing acceptance remain `NOT_ESTABLISHED`.

## 1. Scope and record boundary

Input is one hash-verified, immutable ORG source revision. EDIT, Gerber comparisons, and previous copper groups are downstream and cannot participate in candidate generation, association, arrangement, family membership, or the result digest. The output is descriptive and confers no edit authority, manufacturing interpretation, or process order.

Keep four classifications distinct:

- **Source object:** an occurrence in the ORG KiCad source, with the existing `<source_sha256>:bytes:<start>:<end>` identity.
- **Physical group:** a connected component under a declared same-layer geometric contact predicate. It may include several member sites; it does not define one member.
- **Candidate member:** a revision/map-scoped hypothesis for a local land site. It points to existing source objects and may point to explicit derived subregions. It is not asserted to be a KiCad pad or electrical terminal.
- **Family:** two or more candidate members supported by repeated shape/spacing/arrangement evidence. Family membership does not imply physical connection.

Store arrangement evidence, physical-contact evidence, and geometric-interaction evidence as separate typed records. Reference-feature association is a measured geometric link to a KiCad-declared layer feature; `F.Mask`/`F.Paste` names alone do not prove manufacturing purpose.

## 2. Bounded v0 geometry subset

The sealed ORG materialization contains 1,541 F.Cu filled `gr_circle` occurrences and 450 filled `gr_poly` occurrences. `native_inventory.geometry()` recognizes both `yes` and `solid`; the fresh ORG-only materialization persists the recovered geometry. The restricted recognizer accepts 1,541 filled circles and 243 valid axis-aligned filled rectangles as seed candidates. The other 207 filled F.Cu polygons remain inventoried but are not candidates under this rule. This is not a complete land-site universe and does not establish reference-feature function.

For v0, supported seed candidates are limited to:

1. A source `gr_circle` on F.Cu with `fill yes` or `solid`, positive radius, finite coordinates, and valid polygonal approximation under the declared geometry error budget.
2. A source `gr_poly` on F.Cu with `fill yes` or `solid` that is a valid, explicitly recognized axis-aligned rectangle. Other filled polygons stay inventoried but are not land seeds until their semantics and geometry are separately specified.
3. F.Cu `segment`/`arc` shapes may be attached-trace candidates when the declared exact geometry predicate establishes contact with a seed. They remain separate source objects. Zero-distance touch, positive-area overlap, and within-distance context are distinct statuses.
4. Same-center F.Mask/F.Paste `gr_circle` or supported filled rectangle features may be retained as reference-feature candidates. Record uniqueness, ambiguity, or no match. Do not name them “opening,” “terminal,” or “paste function” as an established role without independent evidence.

A candidate's initial local-land geometry is exactly its seed primitive geometry; it is not the union of its physical component. If a future candidate requires a subregion or multiple source primitives, its record must retain all parent source IDs, deterministic construction steps, resulting WKB hash, mm coordinate frame, and error bound. Do not split or rewrite source records.

The bounded scope is not the full ORG. All unparsed/unsupported layer instances remain in the coverage table with reason and source locator. No complete-board geometry, electrical connectivity, pad semantics, or manufacturing intent is claimed.

## 3. Recognition and association rules

A candidate member is emitted only when the supported source feature and all referenced geometry are hash-bound and valid. Its evidence records:

- seed object ref(s) and `local_land_candidate` role;
- attached segment/arc refs with the exact predicate, distance/contact witness, layer, geometry revisions, and approximation error;
- candidate F.Mask/F.Paste feature refs with predicate, cardinality and status (`UNIQUE_GEOMETRIC_CANDIDATE`, `AMBIGUOUS`, `UNMATCHED`, `UNSUPPORTED`);
- physical-group reference only when the relevant topology query is complete for the declared supported geometry scope;
- alternatives and omissions; no forced association and no calibrated probability/confidence number.

Family evidence uses shape class/dimensions at 0.00001 mm precision, the same nominal incident-trace count, local seed arrangements within a 1.0 mm locality radius, and a repeated nonzero center-displacement bucket of 0.005 mm. A provisional family requires at least three distinct seeds and two distinct supporting member pairs. Fixed-width vector buckets are conservative and do not bridge bins. A family record retains its pairs, vector rule, locality, alternatives, and member keys. This is a pattern hypothesis; it does not assign editing sequence or physical/electrical identity. If a candidate participates in multiple possible families, preserve each alternative rather than silently merging them.

The initial association key uses the exact ORG source locator plus role. For derived subregions, include the source parent IDs and deterministic subregion ordinal. A `member_id` is scoped to an immutable family-map snapshot; it is never a cross-revision identity. Any cross-map continuity requires a separate explicit, evidenced correspondence. Shape fingerprints, coordinate bins, row/column labels, and reference names are descriptors, not sole identities.

## 4. Persistence and publication seam

The existing generic profile store already uses `RevisionCatalog` for immutable artifact revisions, source bytes, object rows, typed relation occurrences and CAS geometry. It can retain a map without a new SQL table: store a canonical family-map JSON artifact as a new derived `RevisionCatalog` revision, with ORG source revision, extractor/geometry materialization digest, recognizer/code version, config digest, predicate versions and coverage in the revision config. Represent candidate-member/family records as rows of that derived artifact revision, with byte spans into its canonical JSON bytes; store their ORG object references as typed fields that a verifier resolves against the pinned ORG revision. Internal family-to-member and arrangement occurrences may use existing typed relation rows within that derived revision. Geometry stays referenced by CAS WKB; it is not copied into source rows.

This is distinct from `common_context/1`: that envelope is a fixed R140 presentation profile and is not the general client ingestion manifest. Do not extend it to carry SZU-comm family data. The generic `pcb-profile-record-materialization/1` manifest currently lists source artifact revisions and the profile package, but does not list derived maps. Therefore, adding a family map needs an additive versioned materialization manifest/receipt field and a verifier/reopen path that validates its ORG revision and every referenced source object. Preserve the current `/1` run unchanged; publish a new versioned run. The old reader may continue reading `/1`; no SQL schema migration is part of this contract.

Keep three identifiers separate:

- `input_snapshot_id`: hash of ORG source revision, existing catalogue source revision, geometry-materialization digest, extractor/parser identity, recognizer implementation digest, canonical config, and relationship-predicate versions.
- `family_map_content_sha256`: hash of canonical semantic output (families, members, typed witnesses, alternatives, coverage), independent of unrelated catalogue activity.
- `family_map_catalogue_revision`: the `RevisionCatalog` revision that persists map bytes/rows/relations/config. The publication receipt binds this revision to the input snapshot and content digest.

A config/code/source/geometry/predicate change creates a new input snapshot ID. If the semantic content happens to remain equal, retain the same semantic content digest while recording the changed provenance and publishing a distinct catalogue revision as needed. Identical input/config/code reruns must produce identical canonical content and revision digests. Never mutate an existing family-map revision.

Build in a fresh staging run, validate all references and payload hashes, reopen in a fresh read-only process, then publish a new run pointer. On any failure, retain the previous pointer and all prior immutable runs. This proves application-level publication only; power-loss durability remains `NOT_ESTABLISHED`.

## 5. Required tests before v0 implementation is accepted

Use small source fixtures with independently authored expected memberships; never generate expected output by running the recognizer itself.

1. Filled `gr_circle fill yes` and filled axis-aligned `gr_poly fill yes`, both at zero stroke width, yield valid geometry and exact source locators; non-filled zero-width counterparts remain unsupported with reasons.
2. One candidate land with touching traces reports its exact object refs and witness; a near-but-disconnected trace appears only as geometric interaction. Touch-only and positive-area overlap are distinct.
3. Two separate land seeds in one connected physical group remain two members. One member built from multiple primitives preserves all source refs.
4. Unique, ambiguous, unmatched and unsupported F.Mask/F.Paste candidates retain the correct status; no manufacturing-purpose label is inferred.
5. Repeated synthetic members produce expected arrangement/family evidence; a singleton or nonrepeating pattern does not become a family; overlapping possible families remain alternatives.
6. Dangling, cross-revision, wrong-layer and malformed subregion references fail closed. Missing geometry appears in coverage rather than disappearing from the candidate universe.
7. Identical ORG/config/code reruns produce identical canonical map bytes and digest. Changing or deleting EDIT leaves the bytes and digest unchanged; the producer must work when EDIT is inaccessible.
8. A changed ORG hash, geometry interpretation, config, parser, code, or predicate changes provenance identity; semantic content digest is checked separately.
9. Interrupted publication leaves the previous run pointer intact; a fresh reader returns all map records and exact ORG references from the published revision.
10. Existing source-object, physical-group, source-selection and R140 query tests remain behaviorally unchanged.

## 6. Audit status and implementation gate

The 2026-10-22 ChatGPT static audit judged catalogue/object identity reuse and typed relation separation `SUPPORTED`; it judged sidecar compatibility, member/local-land predicates, and implementation readiness `UNPROVEN`; it judged reuse of current ORG↔EDIT groups as ORG family boundaries `CONTRADICTED`; manufacturing inference/edit policy `OUT OF SCOPE`. The audit accepted the architecture direction and requested this contract-only step before recognition implementation. It did not independently inspect the checkout or verify test execution.

Before implementation, review this contract for the derived-artifact publication seam and the bounded circle/rectangle candidate rules. The recognition algorithm, UI family selection, EDIT correspondence, copper modification, and recipe inference remain unimplemented here.

## 7. Revised details from the second static audit

The second audit classified the derived-revision approach `SUPPORTED, conditional`, the R140 boundary and versioned profile receipt `SUPPORTED`, but “no SQL migration” remains `UNPROVEN` until the in-repository contract is exercised. The audit permits a bounded persistence/geometry implementation stage, followed by recognition only after that stage passes. Its review used the supplied summary, not independent code execution.

### Derived record identity and cross-revision references

A derived-map revision is not an ORG source revision. Its source bytes are the canonical map document; its rows use byte locators in those map bytes and `representation=derived_family_map`. A row's catalogue object ID is therefore in the derived map's own namespace. The `member_id` is that derived-row ID, scoped to this exact immutable map revision. It never reuses or impersonates an ORG source-object ID.

Each derived row stores typed `source_refs` values containing `{source_revision, object_id, role}`. These are external references validated by a family-map verifier against the pinned ORG snapshot before publication and on reopen. Do not insert them into `RevisionCatalog.relations`, whose SQL foreign keys require same-revision endpoints. Any family-to-member relation rows stay within the derived map revision. A source object can be referenced by multiple members without copying or splitting it. The v0 recognizer may emit one-seed members only; a multi-source member is a schema-capacity fixture, not a recognition claim.

### Exact bounded geometry policy

- Circle seed: source kind `gr_circle`; layer exactly F.Cu; fill token `yes` or `solid`; finite center/end coordinates; radius `> 0`. Interpret fill as a solid disk independent of stroke width. The stored polygonal approximation must record its construction algorithm/version and maximum radial error (the current native kernel target is 0.00001 mm). Zero-width, unfilled, nonpositive-radius, or malformed circles are excluded with typed reasons.
- Rectangle seed: source kind `gr_poly`; layer exactly F.Cu; fill token `yes` or `solid`; after removing a repeated closing vertex, exactly four distinct vertices; positive X/Y extent; every vertex is one of the four bounding-box corners; polygon is valid, non-self-intersecting, and its area equals the bounding-box area within the declared geometry area tolerance. Vertex order may be either winding and any starting corner. Other polygons are unsupported for this seed rule; do not simplify them into rectangles.
- Contact: use the existing Shapely/GEOS exact `intersects` predicate on the qualified, buffered shape geometry. Persist geometry approximation errors for both operands and the measured distance/intersection witness. Label the result `NOMINAL_CONTACT` when the stored shapes intersect; distinguish boundary-only touch from positive-area overlap. If a measured gap/overlap is within the sum of geometry error bounds, retain `CONTACT_STATUS_UNCERTAIN` as an alternative rather than presenting robust contact. Segment/arc endpoint distances are recorded separately from interior intersections; neither geometric contact nor net annotations establishes electrical connectivity.
- Same-center reference candidates: use the same supported circle/rectangle class and a declared center quantization of 0.00001 mm. Collect all matching features per layer. Exactly one produces `UNIQUE_GEOMETRIC_CANDIDATE`, multiple produce `AMBIGUOUS` with every candidate retained, zero produces `UNMATCHED`, and any relevant unsupported geometry produces an explicit coverage/association limitation. Do not silently choose the nearest candidate or infer mask/paste purpose.
- Arrangement: compare exact shape class/dimensions in millimetres and canonicalized center-displacement vectors at the declared coordinate precision. The family threshold rule in §3 is provisional and its tolerance/config must be explicit in every run. If perturbation can flip membership within the declared coordinate/geometry error, record alternatives; do not claim stable family membership.

This is a deliberately incomplete candidate universe. It cannot establish that every physical land is present or that the seed equals its complete physical boundary. Multi-primitive land recognition, arbitrary filled copper, vias, zones, pad reconstruction, net connectivity, and whole-board completeness are out of v0 recognition scope.

### Persistence and fault checks

The first implementation stage must prove `RevisionCatalog.import_revision()` accepts derived map row kinds and same-map relation rows without changing source revision identities or weakening foreign keys. Cross-revision `source_refs` are validated in the derived payload. A negative control must show that placing an ORG reference in a same-revision SQL relation fails; a declared cross-revision payload reference succeeds only after checking it exists in ORG.

The family-map manifest stores canonical map bytes or their catalog revision, input snapshot ID, content digest, catalogue revision, and coverage. The acceptance receipt binds the manifest and catalog database. Build in a new staging directory; validate serialization, source references and geometry CAS; close the writer; reopen read-only in a fresh process; only then rename/publish the new immutable run pointer. Reopen rejects changed map bytes even if the surrounding manifest looks valid. Injected failures before publication leave the old pointer and previous runs unchanged. This is application-level consistency, not power-loss durability.

## 8. Revised implementation gate

**Conditional GO for Stage 1 only:** persistence compatibility, canonical serialization, zero-stroke filled-geometry recovery, publication/reopen and their negative tests. Do not implement family grouping in Stage 1.

Stage 1 passes only when all of the following are demonstrated:

1. The existing SQLite catalog accepts a derived-map artifact revision/row kind and same-revision relations without a migration; same-revision SQL relations still reject ORG IDs from another revision.
2. ORG object refs in derived payload fields are validated against an explicitly bound ORG revision, and the exact source revision is recovered after a new-process reopen.
3. The geometry kernel yields deterministic filled-circle and axis-aligned-rectangle geometry from exact source spans, recognizes fill `yes`, and retains excluded geometry reasons. Tests cover unfilled/degenerate circles and nonrectangular/self-intersecting polygons.
4. Canonical input, semantic-content and publication identities are distinct and deterministic. Changing provenance without changing semantics preserves the semantic content digest but changes the input/publication identity.
5. A run with EDIT unavailable yields the same ORG-only geometry/materialization result. No EDIT artifact is a declared input to Stage 1.
6. Corrupt payload, dangling/cross-revision reference, and interrupted publication fail closed; prior published artifacts remain available and complete.
7. Fresh-process verification checks the full derived-to-ORG reference closure and exact payload hashes.

After Stage 1 passes, request the next static audit before Stage 2. Stage 2 may then implement only restricted one-seed ORG candidate members and explicit associations. Any extension to multi-primitive recognition or family boundaries needs new evidence and remains unimplemented by this contract.


## 9. Current execution status (2026-10-22)

- **G1 corrected ORG geometry durability: PASS, bounded.** The ORG-only materialization freshly reopens all 18,614 source records and 17,809 content-addressed geometry payloads. EDIT is absent. Static review accepted the reported evidence; payload hashes establish storage integrity, not independent geometry equivalence or engineering correctness. See `out/ingestion/audits/20261022_org_geometry_durability/`.
- **G2 derived-map persistence: PASS, bounded.** The derived-revision probe stores three validated ORG references and passed fresh-process verification. Eight focused persistence tests and the 184-test suite passed at that gate. Static review authorized ORG-only candidate and family recognition, while explicitly noting that the probe was not a real member/family map. See `out/ingestion/audits/20261022_org_family_map_persistence/`.
- **Recognition implementation: PASS, descriptive scope.** The current immutable v2 run is `out/ingestion/org_family_map_materializations/szu-comm_20261022_org_recognition_v1/run-32cecd4cc6cd4ff1a7e3dd869366aacb/`. It contains 1,784 one-source-primitive candidate members, 590 overlapping provisional family hypotheses, 275 persisted physical-contact groups, 4,129 family-member links, and 1,784 candidate-to-group links. The derived map stores 2,649 records and 5,913 relations. It also retains 12,046 nominal trace contacts, 2 near-contact uncertain associations, 389 unique and 1,395 unmatched F.Mask candidates, 318 unique and 1,466 unmatched F.Paste candidates, and four unsupported F.Mask features in coverage.
- **ORG topology is persisted separately from member/family classification.** Nominal F.Cu geometry topology is complete for 17,849 source-layer geometry objects with 121,425 contact relations in 275 components. Each component is a separate `physical_group` derived row with exact ORG source-member refs. Candidate members link to those records through same-map typed relations; connected components are not lands, families, or electrical nets.
- **Full reference closure: PASS, bounded.** The v2 verifier checks every nested seed, trace, F.Mask/F.Paste and unsupported-feature reference against the pinned ORG revision, expected source kind and layer, source geometry hash, and exact top-level source-ref set. It also validates physical-group source partitions, candidate-to-group links, family support pairs, member family backlinks, and exact family-member relation closure after fresh-process reopen. Corrupt/dangling member, family, and group references fail closed in focused tests.
- **Determinism and EDIT independence: PASS, bounded.** Three real-ORG recognition invocations produced identical input snapshot ID `13dc1b667f39688c3f95c28f38ae9b256a6b9fb54d899b521ca7d2773412b67d` and semantic digest `8fbb5b3bdcfe5417946d2b89a994a13e5bca62ee0d083394e87411668f14083d` while an unrelated synthetic EDIT marker was absent, present, and changed. The recognizer API accepts no EDIT argument. This demonstrates independence for this implementation and source revision, not arbitrary future changes.
- **Tests and audit status at this 2026-10-22 checkpoint.** Focused recognition/storage tests passed (17 tests); full unittest discovery passed (193 tests), as did compileall and `git diff --check`. At that point the first static recognition review had accepted the bounded implementation but required stronger closure checks. The updated v2 evidence later added those checks; its follow-up audit accepted structural closure and authorized read-only manual/UI inspection. Subsequent G10/G11/G3 projection and fidelity results are recorded below. The 2026-10-22 statement that the audit remained the next gate is historical, not the current status.

All recognition rows remain hypotheses. F.Mask/F.Paste layer labels are not interpreted as manufacturing purpose. No native pad/net identity, whole-board land completeness, electrical acceptance, engineering acceptance, manufacturing approval, or copper-edit authority is established. The 1.0 mm locality and equal nominal trace-count family context are explicit uncalibrated recognition parameters and require manual review before downstream use. The designated static audit accepted structural closure based on reported evidence and authorized read-only manual/UI inspection. UI correctness and recognition semantics remain unqualified; see `out/ingestion/audits/20261022_org_family_recognition_v2/audit_disposition.md`.

## 10. G10 group-projection reference integrity (2026-10-23)

The ORG physical-group inspection projection is hardened independently of recognition. A group marked `COMPLETE` must resolve unique member IDs to matching object identities in the pinned ORG revision and source hash; source spans, layer membership, finite bounds, and geometry paths must be present. The browser repeats these checks and omits the complete drawing on failure. The publication writer and verifier cap the exact final review and stored-geometry files independently at 64 MiB; the browser loader rejects oversized declared/streamed resources.

The fresh publication `out/ingestion/workbench/run-3c9c91242bf54bea8f2742cff0ee7256/` verifies 2,416 outputs, six datasets, and three comparisons. Its two ORG review resources are 27,375,166 and 40,345,503 bytes. The focused G10 Python and JavaScript checks pass; full Python unittest discovery passes 241 tests. Full JavaScript test entrypoint results include two failures outside this path and are listed in `out/ingestion/audits/20261023_org_family_group_integrity_g10/evidence/test_results.md`.

The result remains bounded to source-ID and group-completeness integrity plus read-only projection behavior. A summary-only static review accepted G10 within this stated scope; it did not independently inspect the checkout or rerun tests. It does not qualify visual fidelity for every group, semantic identity, electrical correctness, copper-enhancement correctness, or manufacturing acceptance. The reviewer identified geometry-content binding as the next integrity risk: a valid source reference does not by itself prove the selected path contains the correct geometry bytes. G11 should bind every loaded path to pinned ORG geometry content or a declared derivation; reject missing, substituted, corrupt, or mismatched geometry; cover absent/misleading content lengths and streamed/fallback size limits; and inspect a large group for silent omissions. Keep this separate from visual-fidelity qualification. Full disposition: `out/ingestion/audits/20261023_org_family_group_integrity_g10/evidence/chatgpt_static_audit.md`.

## 11. G11 geometry-path integrity and browser limits (2026-10-23)

The ORG family review projection is now schema `/3`. Each geometry key (the pinned ORG WKB SHA-256) has a path-binding record naming the `pcb-org-svg-path/v1` derivation and separate SHA-256 values for simplified and stored SVG path strings. The projection builder reads content-addressed WKB through `RevisionCatalog.read_payload`, derives both paths from that verified payload, and records the digests. The publisher binds the entire projection and separate stored-path resource into the immutable publication receipt. The browser verifies every simplified path after loading the receipt-bound projection and verifies every stored path after checking the stored resource hash; missing keys, wrong source geometry identities, or substituted/corrupt path strings fail closed before drawing.

The 64 MiB resource check now has negative coverage for missing `Content-Length`, a misleading small header with an oversized streamed body, and an oversized fallback body. Declared over-limit resources still reject before reading. The largest real physical group marked `COMPLETE` in the fresh publication has 44 members; a browser-render test selected it and confirmed exactly 44 SVG object paths. A synthetic maximum-size (100-member) group also resolves in full. Components larger than the 100-object drawing limit remain explicitly summary-only; the largest observed group in this publication contains 13,666 source objects and is not drawn as a complete group.

The fresh publication and verifier status are recorded under `out/ingestion/audits/20261023_org_family_geometry_integrity_g11/`. The summary-only G11 audit accepted this scope as **PASS — bounded, reported evidence**; it did not inspect or execute local artifacts. The reviewer recommended three additional integrity negatives for wrong WKB identity, cross-member path substitution, and truncated/aborted streams. This closes path-byte identity within the declared projection derivation and member-render limit; it does not prove maximum geometric fidelity, semantic/electrical identity, copper-enhancement correctness, or engineering/manufacturing acceptance. Simplified paths retain a simplification parameter rather than a maximum-error guarantee, so visual fidelity remains a separate open qualification. See `evidence/chatgpt_static_audit.md` in the G11 audit pack.

### 11.1 G11 integrity hardening follow-up

The three reviewer-suggested negative cases are now covered. A WKB identity mismatch is rejected even when both path digests are valid. A cross-member SVG swap with refreshed per-path digests still fails the frozen projection receipt checksum before any `COMPLETE` group is drawn. A response stream that errors after returning partial bytes remains `NOT_AVAILABLE`; no group view is emitted. Focused integrity tests now total 11 and full Python discovery passes 244 tests. A summary-only follow-up audit accepted these tests as **PASS — bounded follow-up closure**, while noting that a newly and legitimately republished but incorrectly derived path remains unproven. This closes the G11 integrity follow-up; it does not expand it to geometric correctness. The next gate is G3: compare actual stored and simplified SVG geometry against the pinned source WKB, including coordinate frame, units, fill, clipping, and highlighting. See `out/ingestion/audits/20261023_org_family_geometry_integrity_g11/evidence/followup_static_audit.md`.

## 12. G3 WKB-to-SVG geometric fidelity (2026-10-23)

The G3 audit independently parsed the published M/L/Z SVG dialect and reconstructed its even-odd filled polygons, then compared them with the content-addressed ORG WKB. The initial `0.0002 mm` simplification candidate exceeded its measured envelope for 172/8,476 paths; `0.0001 mm` still exceeded it for 3 paths. Those failed reports are preserved. At `0.00005 mm`, all 8,476 simplified paths were valid, retained polygon-component and hole counts, and measured at or below `0.0000570711 mm` Hausdorff distance (maximum observed `0.0000549402 mm`). All 8,476 stored paths passed the nine-decimal coordinate-rounding bound (maximum observed `7.0562e-10 mm` against `7.0711e-10 mm`). This measured bound applies to the pinned publication only; the parameter is not a general simplifier guarantee.

The browser now explicitly uses SVG even-odd fill for every ORG geometry layer, so hole display does not depend on ring winding. Coordinates use the source WKB X/Y millimetre frame without transform. The updated published DOM check verifies 44/44 geometry paths in the largest `COMPLETE` group, padded-viewBox containment and source-bound seed highlighting. The fresh publication verifies 2,416 outputs, six datasets and three comparisons. Detailed per-path metrics and preserved candidate failures are in `out/ingestion/audits/20261023_org_svg_geometry_fidelity_g3/`; the current OKF entry is `docs/okf/ingestion/org-svg-fidelity.md`.

Disposition: **PASS - bounded, measured display fidelity for this pinned ORG map publication.** A summary-only static audit in the existing PCB AI CAM conversation supports this disposition while explicitly not independently inspecting files or rerunning commands; it cautions that the measured simplification envelope is publication-specific, component/hole counts do not prove exact narrow-gap topology, and pixel-level rasterization was not tested. The response is preserved in `out/ingestion/audits/20261023_org_svg_geometry_fidelity_g3/chatgpt_static_audit.md`. This result does not establish source identities as semantic lands/pads/nets, electrical correctness, copper-enhancement correctness, engineering acceptance, or manufacturing approval. The user's G22 visual decision and the VME-WREN package inventory reconciliation remain separate and pending.
