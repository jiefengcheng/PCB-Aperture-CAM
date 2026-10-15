# V1 decision — 2026-10-14

Technical validation: **PASS for the frozen synthetic V1 coupon and qualified Gerber subset**. Independent Cursor review: **NOT_RUN / CHANNEL_UNAVAILABLE**. Manufacturing acceptance: **NOT_ESTABLISHED / OUT_OF_SCOPE**. Stop at V1; no V2 editing or V3 planning implemented.

- G0 PASS: all 70 immutable assets verified before exports and validation. Native footprint origin `(20,20)` plus P1 local X `0.35` / `0.05` confirms source X `20.35` / `20.05`; independently parsed native Gerber flashes confirm the same positions. Policy remains hash-frozen.
- G1 PASS: fresh paired native exports from pristine copies using supplied CLI, `KICAD_RUN_FROM_BUILD_DIR=1`, KiCad `10.99.0` (Gerber header `10.99.0-unknown`). Final run: `out/native_exports/20261014T140617_287308Z/`. Receipt contains CLI binary hash, environment, argv, source/output hashes and logs. Both DRC executions return 5: one missing Synthetic footprint-library warning, zero unconnected items; not clean DRC and not manufacturing acceptance.
- G2 PASS within explicit supported coverage: Gerbonara 1.6.3 parses X2 roles, attributes, absolute X4.6 millimeters, rectangular flashes, circular-aperture linear strokes and straight regions. Negative mask file is interpreted as opening geometry. Profile's absent file polarity is qualified explicitly as positive stroke geometry. Unknown operations, macros, transforms, clear polarity, arcs and alternate units are rejected as NOT_ESTABLISHED.
- G3 PASS: mask/profile unchanged; measured A1 exposure `1.19 mm²` before and `1.40 mm²` candidate; required expanded opening contained with `0.15 mm` rim; center offset `(0.05,0)` mm; physical N1/N2 remain separate and connected; minimum inter-net distance `1.55 mm`; protected objects unchanged; copper delta inside authorized rectangle.
- G4 PASS: 13 retained Gerber corruption controls fail the intended check, including all six required fault classes. Additional controls include clear polarity, inch units, unknown command, narrow neck and insufficient clearance.
- G5 local evidence PASS: schema-valid `out/v1_validation.json`, human report `out/v1_validation.md`, negative reports and mutation files retained. Eight unittest methods pass (including subtests for 13 negatives). Exact implementation commit and source hashes appear in the generated report and `out/cursor_review_packet.json`.

## Reproduction

Use this checkout's `.venv`, not the parent project's shared environment. Install `requirements.lock.txt` into a project-local venv. Tested Python 3.14.5, Gerbonara 1.6.3, Shapely 2.1.2 and jsonschema 4.25.1; `requirements.lock.txt` pins the complete tested environment. The authoritative Python version is recorded by the report.

```sh
python3 tools/preflight.py --output out/bootstrap.json
KICAD_RUN_FROM_BUILD_DIR=1 python3 tools/export_native.py --case both --cli /Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli
.venv/bin/python tools/validate_native.py --run out/native_exports/20261014T140617_287308Z
.venv/bin/python -m unittest discover -s tests -v
```

For a new export, pass its printed run directory to validation. Tests require a native run selected by validation; missing native evidence is an error, never a skipped positive test. `out/` is locally retained and Git-ignored.

## Evidence limits

JSON fixture expectations, synthetic reference Gerbers, independently observed before Gerbers and freshly native-plotted paired Gerbers retain separate roles. Geometry acceptance uses the fresh pair; fixture JSON supplies policy and independent terminal intent only. X2 net names are not used to establish connectivity. Numerical tolerance is 0.001 mm; circular strokes use 128 chords per quadrant with an enforced error budget. Connectivity also requires survival of 0.099 mm copper erosion, bounding narrow-neck acceptance for this coupon. These are experimental constraints, not process specifications.

Available tool inventory exposes no authenticated direct Cursor agent channel. No global configuration or adjacent project was inspected to find one. A frozen read-only review packet is prepared under `out/`; no review occurred and no human relay is requested. No remote writes, account access, uploads, or V2/V3 work occurred.


# V1.5 decision — 2026-10-14

Authorized public acquisition and initial read-only qualification completed. Native CLI compatibility established for selected GlowStitch and HALPI2 boards; realistic design validation remains **NOT_ESTABLISHED** because the frozen V1 geometry subset and independent intent/policies do not cover these designs. Ucamco parser probe: 9/11 load/expand without warnings, two aperture-block examples not established. Cursor review remains NOT_RUN / CHANNEL_UNAVAILABLE. See `docs/ROADMAP.md`, `docs/V1_5_DECISION.md`, `contracts/public_sources.json` and `out/v1_5/`. Preserve the historical V1 decision above; the previously stated V1 stop line is superseded only by the explicitly authorized V1.5 phase. Stop here; no V2/V3 started.


## Charter alignment — 2026-10-14

Documentation-only alignment of the supplied proposed charter is prepared in `docs/PROJECT_CHARTER.md`, `CHARTER_INTEGRATION.md`, `TRACEABILITY.md`, `DECISIONS.md`, `CHARTER_EVIDENCE_AUDIT.md` and `NEXT_GATE_PROPOSAL.md`. Read-only custody/receipt checks support the historical bounded V1 PASS and V1.5 realistic NOT_ESTABLISHED; 70/70 assets and four current bootstrap tests pass. Historical full-suite logs were inspected, not rerun. Charter reconciliations and FC-1 (one independent aperture-block oracle and support decision) are proposed for approval. No parser, V2/V3, manufacturing-rule or acceptance changes. Cursor governance review NOT_RUN / CHANNEL_UNAVAILABLE. Stop after the documentation commit and request user approval.


## FC-1 authorization and decision — 2026-10-14

The user approved the reconciliations and FC-1 only (DECISIONS D-009); earlier proposal/approval-stop text is retained as history. [FC1_DECISION.md](FC1_DECISION.md) records oracle qualification PASS for one exact Ucamco source, with [FC1_ORACLE_DERIVATION.md](FC1_ORACLE_DERIVATION.md) defining the independent expectations and numerical limits. Extended parser support and realistic PCB validation remain NOT_ESTABLISHED; Cursor review NOT_RUN / CHANNEL_UNAVAILABLE. MC-1 and FC-2A are not authorized, and no V2/V3 begins. Stop at this gate.


## Bounded V1.5 completion evidence — 2026-10-14

The adopted completion handoff (DECISIONS D-012) supersedes prior intermediate stops for this task only. [V1_5_COMPLETION_DECISION.md](V1_5_COMPLETION_DECISION.md) records a working raw-Gerber geometry/preservation profile for both complete nine-layer selections and the qualified FC-1 example. Full required electrical acceptance remains NOT_ESTABLISHED because GlowStitch lacks qualified net intent. Historical V1/V1.5/FC-1 conclusions and contracts are unchanged; the new evidence extends them. Current authority is in AGENTS and DECISIONS; earlier FC-1-only text describes the earlier authorization. Cursor remains NOT_RUN / CHANNEL_UNAVAILABLE. No pcb_Z, V2/V3, manufacturing approval or remote publication.


## Source-aware profile decision — 2026-10-15

The separately authorized source-aware technical profile v1 passes its declared responsibilities; original V1.5 remains NOT_ESTABLISHED. See [SOURCE_AWARE_V1_DECISION.md](SOURCE_AWARE_V1_DECISION.md). No V2/V3 or pcb_Z authorization is inferred; bounded work stopped.


## HALPI2 electrical evidence consolidation — 2026-10-15

[HALPI2_ELECTRICAL_CASE.md](HALPI2_ELECTRICAL_CASE.md) records a PASS for the existing bounded native-intent same-layer case: 240 GND pairs, all 64 named terminals mapped/separation-checked, plus named-open and short controls. Original V1.5 remains NOT_ESTABLISHED and source-aware profile PASS remains preserved. No whole-board/cross-layer or manufacturing claim. Task complete; stopped.


## V1.5 closure and bounded V2 execution — 2026-10-15

The user closed V1.5 as bounded engineering qualification and explicitly granted standing authorization for the synthetic MovePadWithConnections slice plus limited read-only pcb_Z discovery. [V2_DECISION.md](V2_DECISION.md) records technical PASS: computed candidate, actual native export, frozen validation, rejection/rollback and 48 regressions. Original V1.5 aggregate remains NOT_ESTABLISHED; source-aware and HALPI2 case PASS preserved. No HALPI2 automatic edits, V3, full legacy merger or manufacturing approval. Slice complete.


## Evidence-linked visual delivery — 2026-10-15

[VISUAL_WORKBENCH.md](VISUAL_WORKBENCH.md) records the implemented local HTML/SVG case workbench for actual synthetic V2, HALPI2 open/bridge and GlowStitch information-boundary evidence. Shared comparison/delta, layers, roles, findings, provenance and recorded execution replay are delivered; 56 tests and 30 final-bundle UI combinations pass. Visual case delivery is now an additive normal-workflow requirement, not another strategic gate or authorization. Prior acceptance decisions remain unchanged.


## Bounded consolidation closeout — 2026-10-15

See consolidation/CONSOLIDATION_DECISION.md, CONSOLIDATION_ACCEPTANCE_AUDIT.md
and FINAL_EVIDENCE.json. Source/catalog/context → the same approved V2 operation
→ independent exported validation → Processing/Cases/Storage replay is established
in the recorded scope. Final clean source: 6396170; 110 tests, six native parity
scopes, 70 assets and 1,268 preserved historical files. Native graph remains
SHADOW_ONLY; custom C++ B/R-tree and general native reassembly remain explicit
gaps. Original aggregate V1.5, GlowStitch electrical intent, Cursor review and
manufacturing limitations retain their prior statuses. No next feature gate is
started.


## Client Gerber demonstration consolidated — 2026-10-15

[CLIENT_OPERATION_DECISION.md](CLIENT_OPERATION_DECISION.md) records the bounded real-data result, nine-step walkthrough and 2:17 narrated replay. Nine local checks pass; open/bridge/admission controls reject and preserve accepted output. All 42 client source hashes, 70 expected asset hashes and 66 visual snapshots verify. Strict asset inventory still fails on preserved `assets/.DS_Store`; no clean current full-suite result is claimed. The custom bundle receipt is checked by an additive audit, not the generic verifier. [CLIENT_OPERATION_EVIDENCE.json](CLIENT_OPERATION_EVIDENCE.json) freezes receipt hashes. Historical decisions remain unchanged; no new stage or publication begins.


## Client delivery maintenance — 2026-10-15

[CLIENT_ISSUES.md](CLIENT_ISSUES.md) records resolved verifier/build/provenance issues and remaining limits. Historical client receipts now verify through explicit legacy handling; new bundles use the common receipt envelope. Replay generation rejects stale operation evidence and omits recordings/obsolete reviews from copied operation artifacts. Strict asset inventory still reports extra `assets/.DS_Store`; no clean current full-suite claim or expanded CAM scope.
