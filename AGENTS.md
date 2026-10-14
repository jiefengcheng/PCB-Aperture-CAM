# Repository-scoped instructions for Codex

You are implementing **PCB Aperture CAM V1**, a newly isolated project. This file is authoritative for every agent acting within this checkout.

1. Operate **only** under this checkout; do not inspect, open, reset, commit, or modify any adjacent repository, user research project, C7/C8, LPA/Viewer lane, iPhone lane, NAS mirror, or global Codex/Cursor configuration. No cross-project coupling.
2. Codex is the **sole coordinator, author, integrator and decision owner**. Cursor (if available through a genuine authenticated agent/tool channel to Codex) receives a frozen read-only review packet on this checkout; Cursor must never take over integration. If no direct channel, mark independent review `NOT_RUN: CHANNEL_UNAVAILABLE` and stop without pretending it happened or asking the user to relay messages.
3. `assets/` is **immutable**. Verify manifest hashes before every baseline run. All builds, candidate exports, negative mutations and reports go under `out/` or the separate source code `src/` + `tests/`. Do not edit or regenerate source fixtures in place.
4. Baseline is **generated candidate P1 center X=20.05 mm**, with before X=20.35 mm, aperture X=20.00 mm. Treat `assets/starter/fixtures/candidate` as the authoritative target. `assets/observed_before/` contains only an independently plotted before export. **No KiCad-exported candidate is supplied**. Before a claim about actual KiCad candidate Gerber, execute native export from source and record its tool/version/commands.
5. Do not confuse (a) synthetic JSON internal checker results, (b) generated reference Gerbers, (c) user-observed before Gerbers, or (d) freshly KiCad-plotted candidate Gerbers. Report their different evidentiary roles and limitations.
6. V1 only: use a maintained Gerber parser and an explicit, tolerance-bounded geometry kernel to validate mask stability, exposure/registration, geometry of copper, connectivity vs independent net intent, clearance and change scope. Unsupported semantics, units or polarity cannot be silent passes. `PASS`, `FAIL`, `NOT_ESTABLISHED` and `NOT_RUN` must be distinct.
7. Keep scripts and tests deterministic; pin tested versions, retain source hashes, record tool versions and execution evidence. Tests must include deliberate corrupted Gerber cases that fail for the correct reason. Native DRC is supplementary, not final acceptance; manufacturing/DFM approval remains outside this experiment.
8. No GitHub remote write, upload, plugin installation, external account access, network data exposure, or other cross-service action without explicit authorization. Install *project-local* Python dependencies only if required by the current milestone. Do not clone third-party PCB designs for V1. The user authorized the separate V1.5 phase on 2026-10-14: acquire GlowStitch, then HALPI2-HDMI-FPC and official Ucamco test fixtures for read-only qualification inside this checkout only. Keep external/sources immutable; store copies, exports and reports under out/v1_5/.
9. Preserve the frozen V1 decision and gates. Proceed through the separately authorized V1.5 asset qualification, reporting realistic-design compatibility separately from synthetic correctness. Stop after the V1.5 decision. The user must explicitly authorize V2 automatic editing or V3 AI planning.

Read `docs/CODEX_HANDOFF.md`, `docs/ACCEPTANCE.md`, `docs/CURSOR_PROTOCOL.md`, `docs/PROVENANCE.md` and `docs/STATUS.md` before changing code.


## Proposed strategic reference — documentation alignment 2026-10-14

Use `docs/PROJECT_CHARTER.md` as the proposed long-term strategic reference, reconciled in `docs/CHARTER_INTEGRATION.md` and `docs/DECISIONS.md`. All operational rules above remain effective; strategic text grants no implementation, delegation, network or manufacturing authority. Frozen V1/V1.5 acceptance and evidence are preserved. The current authorization is documentation-only alignment and a local commit, followed by a stop for user approval. `docs/NEXT_GATE_PROPOSAL.md` is a proposal; do not begin V2/V3, additional parser implementation, or any new gate without explicit authorization.


## Active gate authorization — 2026-10-14

The user approved the charter reconciliations and FC-1 only after commit `1b1b843`. The aligned charter is now the adopted strategic reference. This supersedes the prior documentation-only stop and V1.5 stop solely for FC-1: one hash-bound non-nested Ucamco mathematical oracle, explicit negative controls, existing-parser coverage comparison and support decision. Allowed new work is the oracle/reference model, tests, evidence under `out/fc1/` and gate documentation. Do not implement or change Gerber parser support, dependency locks, V1/V1.5 contracts, MC-1, V2/V3, public downloads or partner contact. Preserve all existing operational rules and prior evidence; stop after the FC-1 decision. See `docs/FC1_DECISION.md`.


## Active V1.5 completion authorization — 2026-10-14

The user supplied/adopted `docs/CODEX_V1_5_COMPLETION_HANDOFF.md` to complete the bounded real-Gerber validation path. Its parser/adapter/compositor, required references, tests, fresh native export and reporting work is authorized inside this checkout. Earlier proposal-only, stop-before-parser, stop-after-FC-1 and Cursor-availability stops are superseded for this task only; FC-2A is an internal checkpoint. Preserve all frozen source/acceptance/history and isolation rules. No V2/V3, pcb_Z access/integration, broad acquisition, global changes, service integration, remote writes/uploads or manufacturing approval. Continue until the frozen completion matrix is evidenced or a concrete unresolved blocker is reproduced.


## Source-aware decision authorization — 2026-10-15

The user authorized the bounded source-aware profile described in docs/SOURCE_AWARE_V1_DECISION.md when existing pinned sources lack intent. This supersedes the preceding stop only for that separate profile, its tests and decision. Preserve the original aggregate V1.5 NOT_ESTABLISHED and all frozen evidence; no general parser development, acquisition, pcb_Z, V2/V3 or remote publication. The bounded decision is complete; stop.


## HALPI2 consolidation authorization — 2026-10-15

User authorized the focused case in docs/HALPI2_ELECTRICAL_CASE.md, superseding the prior stop only to reuse existing pinned HALPI2 electrical evidence and complete the missing named-open control. No new profile, GlowStitch investigation, parser expansion, acquisition, pcb_Z, V2/V3 or remote publication. Case completed; stop.
