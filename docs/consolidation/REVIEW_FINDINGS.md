# Review findings — submitted visual workbench and V2

## 1. Basis and evidence hierarchy

Reviewed input files:

| Input | SHA-256 |
|---|---|
| run_20261014T171718_143371Z_review.zip | `3c288229874c2bde385474134a830091ed7a982fe9209f2a28876e9e582ab483` |
| V2_DECISION.md | `cb1c96e420ff9ecb3b9ca13eb4d31a1428e555b03523c621dcf7932e2b303083` |
| pcb_Z.zip | `f612f84e1cbbfa4a755156d10488b1c4d86a4dde4599ef5ffda7fa86731c3df8` |

The visual archive contains 56 files, including 48 evidence snapshots, scene/HTML, an overview, and receipts. `evidence/integrity_review.json` records the verification details.

Evidence classes in this review:
- **Direct byte inspection:** supplied artifacts and hashes.
- **Executed UI probe:** original application JavaScript in a disclosed offline DOM harness.
- **Controlled source probe:** selected legacy function AST or literal SQL, with mocked geometry/index interfaces where stated.
- **Static finding:** code path inspected, not a full native reproduction.
- **Reported historical result:** statements from V2_DECISION.md or supplied build/closure receipts.
- **Proposed design:** future behavior specified in the companion handoff.

Do not combine those categories into an overall independent engineering PASS.

## 2. V2 execution is established in the supplied evidence, not a prepared comparison

`V2_DECISION.md`, lines 3, 13–26, and 36–58, describes original + fixed contract → computed native candidate → fresh KiCad exports → frozen acceptance. The bundled `evidence/9581e32962df_result.json` hashes to:

`0e03355d2772f5baf78ffda27be962dc290caa7f78fa63e99208d5ea9cd70d3a`

This is exactly the authoritative result hash in the decision. It records computed P1 (20.05,20.00), not the discarded manual edit. The visual scene points to that snapshot for the actual committed and rejected attempts. This supports the user's correction: actual V2 execution is being replayed.

What this does NOT establish: a fresh executor run in this review environment; universal routing; public-board automatic modification; full independent numeric-engine redundancy; power-loss durability; manufacturing acceptance.

The decision expressly notes shared GEOS beneath the V1 and V1.5 composition paths, one native footprint-library warning, and directory-rename publication rather than proven crash recovery. Preserve all three qualifications.

## 3. Positive workbench findings

- All 51 outputs listed by build_receipt.json matched their hashes.
- All 48 scene provenance snapshots matched their individual hashes.
- Embedded scene bytes match scene.json exactly.
- overview.png and ui_checks.json match closure_audit.json; the closure itself matches the Cursor review packet's hash.
- 30 state/mode combinations (10 states × 3 modes) were exercised. Both views retained the same viewBox. Tested zoom and pan remained synchronized.
- Scene data remained unchanged after view manipulation.
- HALPI2 J22.1 open case displayed 15 failed expected relationships, Candidate FAIL separately from Fault-control test PASS.
- HALPI2 bridge evidence names /HDMI.D2+, /HDMI.D2- and GND in the joined component.
- GlowStitch separates geometry/profile success from electrical NOT_ESTABLISHED and unknown assignments.
- No external network requests or page JavaScript errors occurred in the offline probe.
- The sampled viewport widths did not produce page-wide horizontal overflow. This is a layout check, not a complete accessibility/mobile acceptance suite.

The original scene explicitly says evidence was verified at generation, not that a live board is being checked. That is a useful and honest boundary.

## 4. Findings to address before dashboard expansion

### RPL-01 — Replay geometry is not consistently derived from the selected event

**Priority:** high for visual truth; does not invalidate backend V2 acceptance.

**Reproduction:** synthetic case → computed candidate → Next recorded event → Previous event to PLANNED.

At this point the right title says `REPLAY · source before candidate creation` and shows original geometry. The measurements and object details still show candidate P1 X=20.05, exposure 1.40 mm², and Candidate PASS. Click Zoom in: the candidate copper path replaces the original, while title and event remain PLANNED.

The attached `browser_review.json` records original/candidate path presence. `replay_planned.png` shows the mixed-state display. The delivered inline JavaScript's event handler draws the original directly at event zero, but ordinary drawAll() always redraws the selected final state; details/metrics are also final-state based.

**Fix contract:** one explicit selected-event projection must drive every render path. Track event_id, displayed_revision, available_artifacts, and decision_available_at_event. Keep final run outcome in a separately labeled panel. Pan, zoom, layers, finding selection, object inspection and resize must not change the selected revision or event. Do not invent intermediate geometry: label only the snapshots actually recorded. Preserve existing backend decisions.

**Tests:** traverse every recorded event in accepted and rejected runs; at each event exercise all view controls; assert geometry identity, header, object coordinates and event-scoped metrics agree. If final metrics remain visible, label them explicitly as final outcome rather than current event.

### UI-02 — Requirement prose can read like a factual success in failed cases

HALPI2 open finding displays `All declared 120 GND pairs on each layer remain connected.` above a FAIL JSON result. Bridge finding similarly states `No component joins different qualified source nets.` above the observed short.

These are expected predicates, not observed results. Label **Requirement** and **Observed result** explicitly. Lead with `15 expected relationships broken` or the named-net short, with the formal predicate underneath. This is a presentation fix, not a new validation calculation.

### UI-03 — Finding evidence needs exact record navigation

The current links open whole JSON snapshots. Add a stable JSON Pointer or existing backend finding identifier and show the corresponding source object and geometric focus. Preserve the full original receipt as the authority. A dashboard click should resolve all the way to an object/query/stage record, not merely a large report file.

### PROV-04 — Show build, execution and seal identities separately

scene.build records code commit `500d070...` and `working_tree_dirty=true`; cursor_review_packet records sealing through `5d91db9...`. Source hashes match the receipts, so this is not evidence of tampering. It is a provenance-clarity issue.

Expose execution source revision, visual generator/source digest, and seal/review commit separately. Do not label the snapshot as generated from a clean `5d91db9` checkout when its recorded build says otherwise. New releases may use a clean tracked-source build or a fully recorded source digest; do not rewrite old receipts.

### VIS-05 — Preserve case inspector; add upstream observability rather than more verdict badges

The current workbench presents outcomes effectively. It does not yet expose raw object inventory → candidate search → exact predicates → groups → persistence → selection/extraction. Add those stages as a separate processing dashboard sharing scene/object/revision references with the existing case inspector.

Performance has not been benchmarked here. The HTML embeds about 4 MB of scene data and also retains scene.json; these are scale-planning observations, not proof of a bottleneck. The offline harness's digest bridge distorts load time, so its timing must NOT be used to justify a frontend rewrite.

## 5. pcb_Z: useful code, partial integration, important boundaries

The supplied archive has **seven** Python source files, one 5,722,336-byte native test board, and seven cached bytecode files. Do not count cached bytecode as additional source modules or execute it.

V2 already reused four import expression helpers plus get_layer_items/find_connected_components through hash-pinned ASTs and project adapters. The decision records that the native pcbnew grouping/SQLite/import/export paths were not executed. Therefore neither “pcb_Z unused” nor “pcb_Z fully integrated” is accurate.

### LZ-01 — Discovery omits important object classes

`group.py:19–28` reads tracks and board drawings; footprint pads and filled zones are not explicitly enumerated. V2's adapter adds four pads. `GetLayer()==layer` also needs specific via/multilayer tests before general layer coverage is claimed.

`import_pcb.py:100–112` indexes top-level graphical expressions, while `iter_all_items` later enumerates nested pads/zones for metrics. A nested pad can be retained as part of a footprint in the header yet absent as a separately queryable graphics record. Raw retention is not complete semantic indexing.

### LZ-02 — Clearance broad phase is incomplete for proximity queries

`group.py:51–69` inserts and queries unexpanded bounding boxes before invoking Collide(clearance). Two objects separated by 0.05 with clearance=0.10 never reach the exact predicate when their boxes do not intersect. The controlled AST probe reproduces this with ordinary AABB semantics; native pcbnew and real Rtree were not executed here.

Keep physical grouping at zero physical contact semantics. Add a separately named within-distance relation using a conservative expanded query and exact distance predicate. Do not repair candidate recall by calling nearby objects electrically connected.

### LZ-03 — UUID-only operations can cross board/revision boundaries

`import_pcb.py:245–246` updates graphics by UUID without board scope. An in-memory test with two boards sharing a UUID updated both records. `export_pcb.py:49–54` likewise selects by UUID alone and fetches one row. The schema does not provide a composite source-revision identity.

Use revision-bound object keys; test duplicate legacy IDs and same UUID in two revisions. Never use a gfs internal VID or group label as the external identity.

### LZ-04 — Selective export is not yet a safe operation-context exporter

`export_pcb.py:24–27`: falsy group_indexs means all groups. Thus supplying only graphic UUIDs without explicit groups can select the entire board first. Explicit graphic selection is appended after group selection without a deduplication step. Missing IDs and group rows also require error handling.

Define selection semantics explicitly: empty is empty, all requires an explicit request, overlapping selectors are deduplicated, missing/ambiguous objects are errors, and any dependency/context expansion is listed. Export retained source dependencies without granting modification permission. Test exported/reopened results; do not upgrade local extraction to manufacturing acceptance.

### LZ-05 — Storage metadata and source preservation need clearer contracts

- Header/sexpr construction uses sexpdata.dumps, not byte-slice retention of original source text (`import_pcb.py:103–123`).
- `uuid_to_sexpr` is a single-value dictionary; repeated identifiers need rejection or an explicit composite locator, not silent overwrite.
- Schema comments describe width/height while metric code computes height/width (`init_db.py:27,40`; `import_pcb.py:230,241`). Preserve old fields and add an explicitly versioned definition rather than silently reversing old values.
- Bbox area is not filled copper area; name both separately and include units. Zero-width shapes need an explicit ratio policy.
- Foreign key enforcement must be enabled/verified on every relevant SQLite connection. The supplied delete helper does so; the importer does not. The probe connection reported foreign_keys=0.
- `sql_opr.py:101–103` returns [] for query errors, which cannot be treated as “no objects found” by an engineering consumer.
- Computed component count includes singleton components, while native PCB_GROUP creation excludes them (`group.py:groups` versus len>1). The dashboard must reconcile these different counts, not treat them as inconsistency-free equivalents.

## 6. gfs: historical evidence, not a current implementation audit

The user's Library contains `C7a_GFS_L0_EXECUTION_ALGEBRA.md`, an investigation of gfs_l0 at `020e18d...`, dated 2026-08-31. It supports graph-local identity translation and directed read kernels, but also records local VID identity, relation-tag, visibility, cancellation, eager-result and ABI projection limitations.

This review has not inspected today's gfs checkout or the exact C++ B-tree/R-tree implementations. Do not claim those old limitations still exist; convert them into current adapter qualification tests. Do not assume every proposed storage/index behavior is already supplied by gfs.

## 7. Review conclusion

The V2 evidence is coherent with an actual bounded execution, and the workbench is a useful foundation. Fix replay state coherence and evidence wording first. Then consolidate upstream discovery, persisted identity/context, and query observability. Integrate native capabilities behind qualified adapters, in shadow mode before promoting them. Keep all original validation and manufacturing boundaries intact.
