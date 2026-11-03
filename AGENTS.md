## Required LaCie storage policy — 2026-11-02

All new test artifacts, temporary files, caches, engineering intermediates and
T01 operational jobs must use `out/lacie_work/`, an APFS volume backed by
`/Volumes/LaCie/PCB_Aperture_CAM_Workspace/PCB_CAM_Work.sparsebundle`.
Run `tools/Prepare_LaCie_Workspace.command` before engineering writes.
Use `tools/Run_PCB_Tests.command <pytest arguments>` for tests. Root conftest
also redirects pytest temporary files/cache and rejects internal --basetemp.
Use the existing Run_T01_Board.command for Terminal work; it prepares storage.
Local Code requires reopening Start_T01_Native_Launcher.command after this change.
Never create fallback directories on internal storage when LaCie is missing.
Do not use an internal --state-dir. Keep all new audit reports/logs under the
external workspace too. Historical sealed/frozen files stay in place and remain
read-only; no automatic migration, cleanup or acceptance change is authorized.
The only internal writes in this work are source code and small documentation.
No global environment or OS storage settings are changed by this policy.

# Repository-scoped instructions for Codex

## Single-command Terminal raw-directory T01 — deterministic machine audits

When the user requests unattended Terminal execution, use
`tools/Run_T01_Board.command --input-dir "<explicit raw directory>"`.
This native-only entry owns its macOS adapter/runner lifecycle and requires no
pre-opened launcher or agent. It executes the same 18 source/T01/export slices.
Every gate requires a separate, hash-bound deterministic machine predicate proof
from actual native evidence, re-evaluated by the route before advancement. The
original verification, pagination, reconstruction and corruption checks remain.
Do not invent human/agent observations, feed generic success strings to review,
or label machine predicates as independent/owner review. Final output states
18 machine audits and zero human/agent observations; owner remains pending.
On any failed/missing/altered predicate or native check, stop with retained
failure evidence and remaining operations NOT_RUN; no retries or substitutions.
No rendering, later stages, shared-clearance changes, MCP or global settings.
Contract: contracts/operator/t01_board_auto.json. Recipe:
docs/agent_abi/T01_SINGLE_COMMAND.md. The existing English/stepped review route
below is unchanged; never silently switch its audit mode.

## Fresh whole-board T01 from an explicit raw-input directory — no rendering

For fresh whole-board T01 using one supplied directory of KiCad/Gerber inputs and
no rendering, use `python3 tools/pcb_t01_board_export_operator.py start --input-dir "<supplied directory>"`.
The directory is required: if absent, request it; never use loaded-project defaults,
a crop, remembered file, prior job or previously constructed candidate. Native
input discovery belongs to the PCB data ABI and stays inside that explicit root.
Use the existing project-local macOS launcher once per session; no per-directory
coordinator setup, MCP, installation or global settings. Every
participating Gerber layer must match fresh native source plotting. The embedded
client sends only the explicit directory path; intake runs in the native launcher.
Do not list, stat, search or read the external directory in Local Code. An old
launcher reports NATIVE_LAUNCHER_UPDATE_REQUIRED; ask the user to close its Terminal
and reopen tools/Start_T01_Native_Launcher.command once. Do not suggest broad OS
permissions from EPERM alone. Native access failures retain errno/path and evidence.
Legacy Gerber layer identity uses source geometry, never filenames. Unmatched
Gerbers are retained byte-identically as explicitly excluded companions with
layer/geometry NOT_ESTABLISHED, under the user-adopted companion policy. They do
not qualify as verified layers or regenerated exports. Missing/ambiguous F.Cu,
unsupported participating geometry or non-PCB inputs halt; never pick a first match.
Read each REVIEW_REQUIRED result and submit one distinct observation with
`python3 tools/pcb_t01_board_export_operator.py review "one observation"`.
Continue all 18 native slices and observations autonomously, polling existing
commands as needed. All source/port/inspection/comparison pages, fresh construction
and reconstruction, native write/reread, actual export/reparse and corruption
controls remain mandatory. No render operations, tile budgets, SVG/PNG/PDFs,
renderer calls, later stages or shared clearance changes. Inputs and frozen
results stay read-only; candidates/receipts/reports are separate. HALTED preserves
the error and stops; no retries, substitutions, probes or acceptance promotion.
On REPORT_AND_STOP return ready_markdown and its absolute file links unchanged,
then stop. Rendering NOT_REQUESTED; owner PENDING_USER; independent NOT_RUN;
electrical/manufacturing NOT_ESTABLISHED. Contract: contracts/operator/t01_board_export.json.
Recipe: docs/agent_abi/RAW_DIRECTORY_T01_EXPORT.md.

## Finishing a retained whole-board run without rendering

When asked to finish an existing whole-board pipeline with rendering violations
reported as failed findings and no new renders, use
`python3 tools/pcb_t01_board_operator.py finalize` (or `finalize --job "<supplied retained job>"`).
This is a report-only action requiring no launcher. It verifies the complete
19-slice source/growth/export/display-production audit prefix and the retained
pixel-tolerance rejection, then writes a separate COMPLETED_WITH_FAILED_FINDINGS
completion outside the original job. Keep native render FAIL and subsequent
NOT_RUN dispositions; never claim all 21 native checks passed or mark the renderer
qualified. Source/export/integrity/observation failures still halt. No native
operations, rendering, geometry/export work, audit submission, retry or edits to
old evidence are allowed during finalization. Return supplied ready_markdown at
REPORT_AND_STOP. Frozen results, shared clearance and T02–T05 stay unchanged.

## Whole-board ordinary-English T01 requests

When asked to apply/run T01 across the entire board using the loaded KiCad/Gerber
pair, use `python3 tools/pcb_t01_board_operator.py start` as the first execution
command. No crop, screenshot, coordinates or named-C01 reproduction is required.
Optional replacement input attachments use --kicad-attachment and
--gerber-attachment with the current app-staged filenames. The same project-local
Start_T01_Native_Launcher.command must be open once per working session; there is
no per-board setup, MCP, installation or global configuration.
Read each REVIEW_REQUIRED result and submit one distinct observation with
`python3 tools/pcb_t01_board_operator.py review "one observation"` until terminal.
Continue through the native slices and observations autonomously; all 21 planned
slices must have an explicit PASS, FAIL or NOT_RUN disposition. A retained
render_verify pixel-tolerance failure after the 19 accepted prefix slices closes
as COMPLETED_WITH_FAILED_FINDINGS through report-only finalization. It does not
re-run pixels or controls or turn their FAIL/NOT_RUN status into PASS. The PCB data ABI
proves complete original F.Cu source and eligible circle occurrence coverage;
T01 uses the full source pool and unchanged interaction/clearance rules. All
source, port, inspection and comparison pages must be covered. All native display
tiles and their pixels must be audited for render qualification; report-only
completion retains FAIL/NOT_RUN for incomplete checks. The board overview is navigation only.
Only start, review and completion polls are needed. Do not probe, search folders,
author audit JSON, invoke later stages, edit sources/settings or retry failures.
Long operations report actual native tile progress; let the existing command
finish. If a setup, unsupported-source, resource, geometry or audit gate fails,
report HALTED with the retained evidence and stop without substituting a crop.
The supported retained pixel-tolerance finding alone can complete the report
under the report-only path above; other failed gates remain HALTED.
On REPORT_AND_STOP deliver the supplied complete Markdown unchanged and make no
further tool call. Keep frozen results, shared clearance and T02–T05 unchanged.
Owner PENDING_USER; independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.
Contract: contracts/operator/t01_board.json. Details:
docs/agent_abi/FULL_BOARD_T01_OPERATOR.md.

## Crop-driven ordinary-English T01 requests

When the user attaches a crop and asks to apply/run T01, use the crop-driven
route, not a named C01 reproduction. Use the current attachment's filename from
app-provided metadata. Local Code's native Attach action stages the actual file
in the project root. First execution command:
`python3 tools/pcb_t01_operator.py start --attachment "<attached filename>"`.
The adapter reads that app-staged copy, never its original Desktop pathname.
It performs no directory search. It accepts canonical Unicode spelling and the
macOS narrow-space/ordinary-space timestamp difference; conflicting bytes halt.
If the user attached KiCad/Gerber replacements, pass their attachment names using
--kicad-attachment and --gerber-attachment; otherwise use the loaded input pair.
The project native launch bridge must be running: the user opens
`tools/Start_T01_Native_Launcher.command` once per working session and leaves its
Terminal window open. Local Code's embedded Python cannot spawn OS processes.
Start checks that bridge first, then automatically creates a fresh job and asks
the native bridge to launch its runner through project-local files. No per-crop
coordinator setup is needed. If NATIVE_LAUNCHER_REQUIRED is returned, stop and
report that single setup action; do not probe, spawn, bypass or retry. One job is active per checkout. New crops get separate jobs after the
previous job terminates; unfinished jobs cannot be replaced. Prior results remain
read-only. Same inputs and implementation cannot retry a failed managed job.
Read each REVIEW_REQUIRED result and call
`python3 tools/pcb_t01_operator.py review "one observation"` until terminal.
There are 21 native slices and 21 distinct observations, including three PCB
data ABI location gates. No user coordinates, crop name, expected candidate or
manual audit JSON is needed. Continue without per-step permission prompts.
Source/inspection/comparison inventories are completely paginated at 100 records
per page. This is not a 100-target cap; there is no fixed 20,000-object limit.
Read the returned page counts and full-coverage facts. All 21 observation gates
remain mandatory; no first-page-only audit, missing record or shortened crop may
substitute for complete source/selection coverage.
Only start, review and their completion polls are needed. No existence/list/pwd/
file/git/environment probes, wrappers, retries, no-op commands or source/settings
edits. If the attachment name or app-staged bytes are unavailable, report
ATTACHMENT_BYTES_UNAVAILABLE and stop; never inspect Desktop, search for files,
substitute a remembered image or reconstruct screenshot pixels from vision. Location ambiguity or unsupported data must halt.
On REPORT_AND_STOP deliver the supplied complete markdown unchanged, including
absolute image and file links. The two panels are candidate KiCad versus
candidate Gerber, not before versus after. Do not make another tool call.
ROI location and source-pair qualification belong to the PCB data ABI suite;
T01 uses its verified binding and source geometry, not screenshot pixels.
Frozen results, shared clearance and T02-T05 stay unchanged; no later stages.
Contract: contracts/operator/t01_crop.json. No MCP or global configuration.


## Ordinary-English full C01 reproduction requests

When asked to reproduce C01 through T01, export KiCad/Gerber and show/check the
result side by side, use the prepared full C01 route. First tool action:
`python3 tools/pcb_c01_full_operator.py start`. Read the compact native facts,
then use `python3 tools/pcb_c01_full_operator.py review "one observation"` for
each REVIEW_REQUIRED result. Continue autonomously through all 18 distinct
observations; only the next audited slice executes. Do not ask for per-step
continuation or author audit JSON. The launcher must already be prepared.
Only start, the 18 review commands and their completion polls are needed. No
existence/list/pwd/file/git/environment probes, wrappers, retries, extra terminal
commands or no-op commands (including true). On REPORT_AND_STOP, embed the
returned PNG directly, link the supplied KiCad, Gerber folder and HTML, give the
concise returned report and stop without another tool call. On HALTED, report
the failure and stop; no partial success claim or workaround.
This freshly constructs only the pinned C01 T01 policy, then exports separate
candidates from that result. EDIT is a representation reference. All original
native checks and observation gates remain; frozen C01/C02/C03, shared clearance
and T02-T05 are unchanged. Owner review stays pending. No independent,
electrical or manufacturing approval. Other crops/policies require separate
scope. Contract: `contracts/operator/c01_full.json`. No MCP or global changes.
For a display-only request about existing exports, use the separate route below.

## Ordinary-English C01 display requests — project-local operator route

When a user asks to show/check the existing exported C01 KiCad and Gerber files
side by side, use `python3 tools/pcb_c01_operator.py start` through the existing
supported Python tool. The local native launcher must already be running.
For this prepared task, the first tool action is that exact start command. Do
not check that the script exists, list directories, run pwd, or inspect the
environment before starting. The permitted execution commands for the entire
task are only start and the three review calls below; poll their running tool
sessions if necessary. No ls, file, pwd, git, shell wrappers, directory searches,
or output-existence probes before or after any slice. The facade checks setup,
source files and output existence itself and returns absolute display paths.
Read each compact result. For `REVIEW_REQUIRED`, submit one short observation
with `python3 tools/pcb_c01_operator.py review "your observation"`. That reviews
the current native slice and runs only the next permitted slice. Three native
checks and three distinct observation audits remain mandatory; the client carries
verified digests/facts automatically. Do not author audit JSON or copy parameters.
On `REPORT_AND_STOP` or `HALTED`, report the returned result and stop. Final paths,
formats, byte counts, dimensions and hashes are supplied: do not run ls, file,
git, environment probes or extra verification commands. No retries/workarounds.
Deliver the returned comparison PNG using its absolute path, followed by the
returned concise report text. Keep the full evidence in the returned HTML link;
do not repeat its hashes, tables and audit details in the chat unless requested.
Observations concern native facts; do not
claim visual inspection or cross-file geometry/aperture approval from raster JSON.
This route is read-only rendering of one fixed C01 file pair; it grants no T01
construction, frozen-result, T02-T05 or manufacturing authority. Other requests
need their own scope. No global settings, installation, network service or MCP.
See `contracts/operator/c01_render.json` for the bounded contract.

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


## Active standing V2 authorization — 2026-10-15

The user explicitly granted standing authorization for the proposed bounded synthetic MovePadWithConnections vertical slice and limited read-only pcb_Z inspection/helper integration at /Users/geoffcheng/Projects/client/PCB/aperture_align_demo/pcb_Z. This supersedes preceding stop clauses and checkout-only reading solely for that package and the already pinned KiCad CLI. Do not ask again for routine steps within that scope. Preserve immutable assets, frozen V1/V1.5 decisions/contracts and all historical evidence. All authored code/derived outputs remain in this checkout. No HALPI2 automatic modification, full legacy/SQLite merger, V3, remote publication, global changes or unrelated lanes. The completed bounded result is documented in docs/V2_DECISION.md; technical acceptance is distinct from manufacturing and Cursor review.


## Evidence-linked visual delivery — standing project-local requirement, 2026-10-15

The user adopted docs/CODEX_PCB_CAM_VISUAL_HANDOFF.md and requested the working read-only visual outcome. Every meaningful engineering checkpoint must also deliver an applicable reproducible visual case bundle: principal positive result, relevant failure/control, remaining limitations, exact run/input hashes, scoped stored verdicts and evidence links. Reuse tools/visual_report.py and the existing scene/viewer; do not create separate presentation gates or imply new implementation authority. Preserve status distinctions, common coordinates, immutable evidence and read-only browser controls. The preview is interface reference only; use actual qualified exports/results, never its archived internal JSON checks as current evidence. Label recorded execution REPLAY. This task authorizes presentation only, not additional V2/V3 execution, parser changes, pcb_Z merger, other lanes, uploads or global settings. See docs/VISUAL_WORKBENCH.md for actual delivery and coverage.


## Active consolidation authorization — 2026-10-15

The user adopted docs/consolidation/CODEX_CONSOLIDATION_HANDOFF.md with docs/consolidation/DASHBOARD_AND_DATA_CONTRACT.md. This supersedes prior stops solely for the connected consolidation work packages, including read-only access to the specified pcb_Z package and /Users/geoffcheng/Projects/context/gfs/gfs_l0 source; pinned copies/builds/materializations stay in this checkout. Preserve frozen acceptance/assets/evidence, no shared-core/global writes, no new repair families/public-board edits/V3/remote publication. Routine in-scope work needs no renewed approval. Detailed requirements and completion audit live in the handoff, not duplicated here.

## Active client Gerber operation authorization — 2026-10-15

The user accepted the detailed one-region client-board plan and requested its full implementation, review, and preparation for video recording. This authorizes a bounded Gerber MovePadWithConnections demonstration on a qualified bottom-copper surface pad, an explicit demonstration contract, actual candidate export/reparse, independent local checks, disconnected/bridge controls, rollback evidence, and the existing workbench's guided replay. A controlled offset of real supplied geometry is authorized when the original already meets the objective; label it separately from the original. Source checkouts/assets/history remain immutable; derived geometry, files and recordings stay under out/. No whole-board electrical/manufacturing claim, HALPI2 editing, V3, external publication, unrelated lanes or wholesale pcb_Z integration. Cursor review only through a verified direct channel; otherwise report NOT_RUN: CHANNEL_UNAVAILABLE and perform local review without claiming independence.

## Fresh U02 raw-directory operation — 2026-11-02

For ordinary-English fresh U02 (T01 → T03, no rendering) use
`python3 tools/pcb_u02_board_operator.py start --input-dir "<explicit absolute raw directory>"`.
Use the existing project-native launcher once per session; an old launcher must
be reopened to load U02 support. The embedded client sends only that path; native
intake owns all external-directory discovery. Read and review each of the 25
native gates with one distinct factual observation using
`python3 tools/pcb_u02_board_operator.py review "one observation"`.
Continue autonomously until terminal; no manual audit JSON or per-step prompts.
For automatic Terminal operation use
`tools/Run_U02_Board.command --input-dir "<explicit absolute raw directory>"`.
This route owns its adapter/process lifecycle and records 25 deterministic machine
audits, zero human/agent observations and no rendering. Never substitute audit modes.

U02's supported T03 family retains valid native paths after exact verified fresh
T01. It inventories every source trace/arc/graphic stroke, regenerates source ports,
checks all applicable growth/trace finite-copper interactions, reconstructs and
compares complete pages, and retains deliberate negative controls. NO_CHANGE_REQUIRED
means zero moved traces, not a demonstrated whole-board router. Any required route
movement halts as U02_T03_MOVEMENT_NOT_QUALIFIED with retained evidence and remaining
operations NOT_RUN. No retry, substitute, historical route, inferred electrical
intent, later U stage, shared-clearance edit or T02/T04/T05 authority is granted.
All new jobs/exports/reports/temp/test data use out/lacie_work exclusively. U02 has
its own namespace/contract/checkpoints; frozen results and T01 behavior remain.
On HALTED report the retained failure and stop; on REPORT_AND_STOP return supplied
ready_markdown unchanged. Owner PENDING_USER; independent NOT_RUN unless a genuine
channel exists; electrical/manufacturing NOT_ESTABLISHED. Details:
`docs/agent_abi/U02_SINGLE_COMMAND.md`, `contracts/operator/u02_board.json`.

## Local Code project cache — LaCie relocation, 2026-11-02

The checkout `.localc` entry is a symbolic link to the project-specific cache on
`out/lacie_work/local_code/PCB_Aperture_CAM_V1_Codex_Handoff/.localc`.
Open Local Code with `tools/Start_Local_Code.command` to prepare/verify storage.
Never replace a broken `.localc` link with an internal directory. The unmounted
workspace directory is guarded against writes; mount through the preparation
command. Keep `/.localc` ignored by Git, including when it is a symbolic link.
Do not unmount LaCie/APFS workspace while Local Code or native jobs are active.

## Fresh U03 raw-directory operation — 2026-11-02

The user authorized full U03 implementation after committing/pushing the existing
U02/cache checkpoint. For fresh U03 (T01 → T03 → T04, no rendering), use
`python3 tools/pcb_u03_board_operator.py start --input-dir "<explicit absolute raw directory>"`.
Read every REVIEW_REQUIRED result and submit one distinct factual observation
with `python3 tools/pcb_u03_board_operator.py review "one observation"` until
terminal. No per-step user prompts. The embedded client sends only the path;
native intake owns external-directory discovery. Reopen the existing project
native launcher once if it lacks U03 support. The owner performs the manual
Local Code trial; do not operate their app for them.

For automatic Terminal execution use `tools/Run_U03_Board.command --input-dir
"<explicit absolute raw directory>"`. It owns the native process lifecycle and
uses the same operations/policy with separate deterministic machine proofs and
zero human/agent observations. Never substitute audit modes. The implemented
sequence has 33 operations, derived from the U03 contract; a failed run must
retain FAIL and subsequent NOT_RUN dispositions rather than claim all passed.

T03 retains qualified native paths after exact fresh T01; required movement
halts. T04 admits complete source-bound uniform native junction paths and
geometrically evidenced parallel groups/singletons. Every source occurrence and
protected current-scene contribution must be accounted for. Exact fully covered
paths remain KEEP; partial coverage is not a skip. Unqualified source families
halt with retained identities. Keep the existing T04 1..1.5 factor, scalar and
finite-copper policies. No land edits, rerouting, neck-down, global optimum claim,
rendering, T02/T05 or later U stage. Candidate trace copper is serialized as
source-bound filled contours and audited by actual native export/reparse.

All new operational/test/audit data use out/lacie_work only. Preserve prior
jobs, frozen C01/C02/C03 and T01/U02 behavior. Stop on failed/missing/altered
native checks or predicates; no retry, resume, substitution, resealing or
acceptance promotion. On REPORT_AND_STOP return supplied ready_markdown
unchanged. Owner PENDING_USER; independent NOT_RUN absent a genuine channel;
electrical/manufacturing NOT_ESTABLISHED. See
`docs/agent_abi/U03_SINGLE_COMMAND.md`, `contracts/operator/u03_board.json`.

## U03 implementation continuation — 2026-11-02

After the first U03 qualification halted at T04 inspection, the user requested
that Codex keep going to finish U03 without requiring owner operation. This
authorizes implementation corrections, regression tests and fresh independent
qualification jobs on the corrected implementation within the existing U03
scope. Preserve each failed job unchanged; never resume it, bypass the same-input
and same-implementation failure latch, or promote its dispositions. A failed
native run still stops its pipeline with remaining operations NOT_RUN. Further
engineering corrections do not change that historical outcome. Keep all earlier
storage, isolation, audit, no-rendering and acceptance boundaries.

## U03 runtime priority — 2026-11-03

The user prioritized optimizing the whole-board runtime before another costly
ORG qualification. Measure retained native cases, preserve failed evidence and
complete the authorized U03 implementation. No source coverage, native gate,
machine predicate, scalar bound, clearance threshold or fresh verification may
be removed to improve timing. Report bounded benchmark timing separately from a
fresh whole-board run; retained-result regression is not fresh qualification.


## U03 crop-image extension — 2026-11-03

The user requested crop processing and corrected the interface: `--crop` takes
an explicit absolute **image-file path**, not a name such as C01/C02/C03. Use
`tools/Run_U03_Board.command --input-dir "<absolute raw directory>" --crop
"<absolute crop image>"`, or the same flags on `pcb_u03_board_operator.py start`.
Omitting crop keeps the existing whole-board default; `--whole-board` is the
explicit Terminal alternative. Native intake alone reads/stages the external
image, retaining its exact bytes/hash. No remembered crop, alias or saved result.

Crop runs preserve the original 33 gates and add two separately audited PCB-data
location/verification gates (35 total). Reuse unchanged ROI matching, boundary,
landmark and corruption predicates; an unsupported or ambiguous crop halts.
NPY masks are internal location evidence, not board/candidate rendering.
Complete growth envelopes and complete native paths/parallel groups must fit
inside the verified window after edge uncertainty. Crossing/outside features
stay unchanged. Full-board copper remains obstacle context; full candidate
native write/reopen, nine-layer export/reparse and controls remain mandatory.
No primitive trimming, threshold changes, historical candidate reuse, T02/T05,
new render, retry of a failed/stopped job, acceptance promotion or publication.
Keep LaCie-only outputs and all stopped/frozen evidence. Local Code requires
reopening its existing launcher once for the new crop-image capability.
