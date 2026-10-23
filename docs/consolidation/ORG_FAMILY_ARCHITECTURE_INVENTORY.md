# ORG family-map architecture inventory

Status (2026-10-23): **The bounded ORG-only family-map prototype is implemented and its pinned v2 run freshly verifies.** This supersedes the proposal-only status recorded below. The map contains geometric candidate and provisional family hypotheses; it does not establish semantic pads/terminals/nets, a complete land universe, electrical intent, copper-edit rules, or manufacturing acceptance. See [the current contract and execution record](ORG_FAMILY_MAP_CONTRACT.md).

The architecture table and requirements below preserve the original proposal and review history. Where they say a capability is still proposed or unimplemented, use the dated current status at the end of this document and in the contract instead.

## Scope

The next descriptive slice is an ORG-only map of recurring land-site candidates. ORG is the sole recognition input. EDIT remains downstream evidence for a later correspondence/change analysis. This map grants no edit permission and defines no processing order. Preserve the six current ORG↔EDIT copper comparison groups unchanged as downstream evidence.

## Existing implementation: reuse / extend / gap

| Area | What exists now | Decision for the family map |
|---|---|---|
| Source objects and identity | `RevisionCatalog` stores immutable source revisions, source-byte locators, object rows, parent references, native IDs, and geometry payload hashes. Object identity is revision-scoped as `<source sha>:bytes:<start>:<end>`. The generic profile materialization binds 44 source files and reopens 358,989 records from a fresh reader process. | Reuse these source object identities and payloads. Do not clone source geometry or make a shape fingerprint the member ID. |
| Native feature extraction | The sealed ORG probe is bound to its source hash and reports 18,614 rows. It contains board primitives (`segment`, `arc`, `gr_circle`, `gr_poly`, `gr_line`, `gr_arc`) and layer instances on F.Cu, F.Mask and F.Paste. It has zero pad records, no footprint references, and no net names. It records 2,708 `NON_POSITIVE_STROKE` unsupported items. | Extend only the necessary geometry/role coverage for the described land-site features. Preserve parser warnings and unsupported status. Do not label a `gr_circle` as a semantic pad. |
| Filled terminal and shape rendering | `tools/build_copper_group_review.py` reparses original source spans to recover filled zero-width `gr_circle` geometry, and can pair same-center circles/filled rectangles across ORG and EDIT. This builder is comparison-oriented and reads both revisions. | Reuse its source-span parsing/math only after separating an ORG-only extraction path. Do not use EDIT-derived matches or group boundaries to seed ORG families. |
| Physical relations | `SpatialContext` uses Rtree/libspatialindex for candidates and GEOS for exact same-layer intersection or requested distance. `topology()` recomputes connected components (including singletons) from its available geometry. | Reuse the declared contact predicate and component IDs where geometry coverage is adequate. A connected component is not a land member or family. Current unsupported ORG filled circles mean topology cannot silently be called complete for this artwork. |
| Durable relations | `RevisionCatalog` supports typed relation occurrences between records within one revision. The common-catalogue envelope binds hash-addressed relationship/qualification sidecars, but it is a fixed R140 case. The generic profile materialization lists source artifact revisions and currently has no derived-map reference. | Persist a versioned family-map as a derived artifact revision in the same `RevisionCatalog`, then bind it from a versioned generic profile manifest/receipt. Keep ORG source rows unchanged; do not repurpose the R140 envelope. No SQL table migration is proposed. |
| Selection and UI | Catalogue selection resolves source records and dependencies. The current catalogue view demonstrates one fixed R140 case and distinguishes ownership, copper contact, proximity, and opening association. | Extend the existing selector/inspector later to choose family → member → linked ORG objects, groups, neighbors, evidence and ambiguity. No second frontend or generic “group” concept. |
| Cross-revision comparison | The current identity map has 1,688 exact coordinate-anchored links and 333 mutual-unique 5 µm candidates. Six visual copper groups are ORG↔EDIT comparison output and marked `UNREVIEWED`. | Preserve as downstream evidence. Neither artifact may affect ORG family membership. |

## Minimum proposed records (for audit before implementation)

Keep the existing source-object and physical-group records intact. Add only two derived classifications inside the existing catalogue:

- A **candidate member** represents a proposed land site. It references source objects or an explicitly described derived subregion by role (reference-feature candidate, local copper candidate, attached neck/trace, physical-group reference). It carries source revision, family-map version, geometric/arrangement descriptors, recognition method and parameters, supporting evidence, association status and alternatives.
- A **family** relates candidate members through an observed repetition or arrangement. Family membership does not imply physical connectivity.

Store arrangement relations, physical-contact references, and geometric-interaction relations as separately typed evidence. Reuse existing object relations and topology witnesses where their scope is complete; do not conflate proximity with contact. Ambiguous feature associations remain alternatives with evidence and status. IDs are stable only within a pinned ORG revision and map version; geometry fingerprints and row/column labels are descriptors, not sole identities.

The audit found the generic profile store can retain a derived catalogue revision but has no current derived-map pointer in its `/1` materialization manifest. The R140 `common_context/1` envelope is case-specific and must not be repurposed. The revised proposal is an immutable derived artifact revision plus a versioned profile-manifest/receipt reference; details and validation obligations are in [ORG_FAMILY_MAP_CONTRACT.md](ORG_FAMILY_MAP_CONTRACT.md).

## Required ORG-only invariants for the next slice

1. The producer accepts one sealed ORG source revision and has no EDIT input parameter or file read.
2. Re-running on identical ORG bytes, parser/tool version and config yields the same family-map digest.
3. Removing, renaming, or replacing EDIT does not change the ORG family-map bytes or digest.
4. Every member association resolves to an ORG source identity or a fully described derived subregion; ambiguous associations are retained rather than forced.
5. Arrangement, physical contact, and geometric interaction are separately typed. Candidate family membership does not merge physical components.
6. Every omitted or unsupported source feature has a reason and source locator; no incomplete geometry scope is displayed as a complete map.
7. Existing six ORG↔EDIT groups remain available and are visibly labeled downstream comparison evidence.

## Evidence and limits

The current materialization is `out/ingestion/profile_materializations/szu-comm_before_after_20261021_02/`; its acceptance records fresh-process retrieval of all 358,989 records with 41 warning groups, but qualification is `NOT_RUN` and engineering acceptance is `NOT_ESTABLISHED`. The generic native probe itself does not identify pads, footprint references or nets. The ORG/EDIT comparison builder supplies useful visible geometry correspondences, but its output is not an ORG-only land-site family map. No independent PCB electrical intent or manufacturing-purpose association is established.

Relevant implementation: `src/revision_catalog.py`, `src/native_inventory.py`, `src/spatial_context.py`, `src/common_catalogue.py`, `src/catalogue_scene.py`, `src/catalogue_selection.py`, `web/catalogue_views.js`, `web/catalogue_themes.js`, `tools/build_identity_review.py`, and `tools/build_copper_group_review.py`. Source and derived artifacts remain local; raw client boards are not copied into this document.


## Review outcome

The ChatGPT auditor accepted reuse of revision-bound source identities, physical groups, and typed relationships, while marking implementation readiness and the exact persistence reference `UNPROVEN`. It rejected using comparison-derived ORG↔EDIT groups to define ORG families and placed manufacturing-purpose/edit-policy claims out of scope. Its next requested work was contract-only: verify the persistence seam, define identity/provenance/invalidation and bounded land/reference predicates, and specify falsifiable EDIT-independence and omission tests. This is a requested static audit, not Cursor review and not independent checkout verification.

## Current implementation and evidence (2026-10-23)

The ORG-only producer consumes the hash-verified ORG geometry revision. It has no EDIT input parameter; the existing ORG↔EDIT comparisons remain downstream. For the pinned ORG source SHA-256 `850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0` and revision `a6456452a162db04b776fcd4e3b9da2813f5d2a491125d5b4e6ad9976054cfd8`, the immutable family-map run is:

`out/ingestion/org_family_map_materializations/szu-comm_20261022_org_recognition_v1/run-32cecd4cc6cd4ff1a7e3dd869366aacb/`

Fresh read-only verification returned **PASS** for map revision `2e3a279a5f0db97937d3a2374806910d02eeb8d4aa1df522cde232ff8cb1300c`, semantic content digest `8fbb5b3bdcfe5417946d2b89a994a13e5bca62ee0d083394e87411668f14083d`, and 2,649 persisted records. Its input snapshot is `13dc1b667f39688c3f95c28f38ae9b256a6b9fb54d899b521ca7d2773412b67d`; the manifest's implementation digest `26f0531d63a4bd253862a973aaead0ddf1ce72f1406cd9dc468b34e1902d7591` matches `src/org_family_recognition.py`. This binds the reported map to the recognizer file, config, predicate versions, geometry materialization and ORG revision recorded in that snapshot; it does not qualify the entire dirty worktree. The map's own qualification status is `NOT_RUN`, and its descriptive coverage status is `DESCRIPTIVE_HYPOTHESES_ONLY`.

The declared subset has 1,784 one-source-primitive candidate members, 590 provisional overlapping family hypotheses, and 275 geometric physical-contact groups. Circle/rectangle seed rules, trace contacts, uncertain near contacts, mask/paste geometric candidates, unsupported cases and alternatives remain typed and source-referenced. The 590 families are not disjoint board partitions. `qualification: NOT_RUN` means semantic qualification of the map was not performed; it does not mean persistence verification or focused regression tests were skipped.

The read-only workbench projection is schema `/3`. Its integrity checks bind SVG paths to source WKB digests and source-object identities; the separate G3 audit measured stored and simplified geometry for its pinned publication. A `COMPLETE` drawing is limited to at most 100 explicitly resolved members, so larger groups remain summary-only. These checks establish bounded persistence/projection integrity and measured path fidelity for the pinned publication, not semantic identity or rendering correctness for every future input.

Current focused verification from the repository `.venv`:

```sh
.venv/bin/python -c 'from pathlib import Path; from src.family_map_storage import verify_bundle; root=Path.cwd(); print(verify_bundle(root, root/"out/ingestion/org_family_map_materializations/szu-comm_20261022_org_recognition_v1/run-32cecd4cc6cd4ff1a7e3dd869366aacb"))'
.venv/bin/python -m unittest tests.test_org_family_recognition tests.test_family_map_storage tests.test_org_family_review_integrity tests.test_org_svg_geometry_fidelity -v
```

The current verification returned **PASS** for the reopened map and **31 tests passed** across recognition, durable storage, projection integrity, and SVG geometry fidelity. The test count is test-execution evidence, not semantic qualification. The complete current ORG/family-map boundaries and earlier failed attempts are retained in `out/ingestion/audits/20261022_org_family_recognition_v2/`, `out/ingestion/audits/20261023_org_family_geometry_integrity_g11/`, `out/ingestion/audits/20261023_org_svg_geometry_fidelity_g3/`, and `out/ingestion/audits/20261024_org_and_screenshot_mapping_v1/`.

### Remaining review boundary

The frozen G22 page at `http://127.0.0.1:8780/g22_human_review/index.html` is ready for the user's local-neighborhood judgment; `out/ingestion/audits/20261024_org_and_screenshot_mapping_v1/g22_human_review/G22_REVIEW_RECORD.md` remains blank. G22 shows before/after crops, leading and competing local overlays, and the corrected holdout-mask evidence. Its summary-only ChatGPT audit accepted presentation readiness but explicitly did not inspect the rendered page or decide for the user. This manual choice does not determine electrical identity, complete ORG↔EDIT correspondence, an enhancement rule, or engineering/manufacturing acceptance.
