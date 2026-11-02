# U02 — fresh T01 → T03 → native exports, no rendering

T01 was committed and pushed first as `e460edb237253b1e75c863cf58c041a0fc834bf1`
on `codex/t01-c01-english-contract-abi`. U02 is a separate incremental pipeline,
not a continuation/replay of that run or of any historical crop candidate.

From any Terminal working directory:

```sh
"/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/tools/Run_U02_Board.command" --input-dir "/Users/geoffcheng/Projects/client/PCB/szu_comm/manual-test-3020301113B/ORG"
```

Use another explicit absolute directory in the same command for another board.
It prepares the required LaCie APFS workspace and owns native intake, the macOS
file adapter, native subprocesses, deterministic machine audits and shutdown.
No pre-opened launcher, Local Code, MCP, rendering or global setting is required.
All job/evidence/export/temp/cache data stays under `out/lacie_work/`; missing
LaCie halts without internal fallback. U02 storage preflight checks its external
output filesystem, rather than requiring working space on the internal disk.

## Local Code manual trial

Reopen `tools/Start_T01_Native_Launcher.command` once to load U02 capability, then
leave its Terminal window open. No per-directory setup is needed. Suggested prompt:

> Run fresh U02 (T01 → T03), without rendering, from the raw KiCad/Gerber directory
> `/Users/geoffcheng/Projects/client/PCB/szu_comm/manual-test-3020301113B/ORG`.
> Use the U02 operator, review every returned native gate with a distinct factual
> observation, and return the audited candidate KiCad/Gerber files and evidence.
> Stop on any failure; keep owner review pending.

First execution command:

```sh
python3 tools/pcb_u02_board_operator.py start --input-dir "/absolute/raw-directory"
```

Read each REVIEW_REQUIRED response and submit one distinct observation:

```sh
python3 tools/pcb_u02_board_operator.py review "one factual observation"
```

The facade sends only the directory path to the native launcher: do not list,
stat, search or read that external directory in Local Code. Missing explicit
input or an outdated/unavailable launcher halts before input discovery. On
HALTED, preserve evidence and stop without retries/substitutions. On REPORT_AND_STOP,
return ready_markdown and its absolute links unchanged, then stop. Completed report
retrieval verifies retained custody; it does not execute native work again.
The coordinator has not operated Local Code for the owner.

## Actual support and the T03 gap

Source inspection covered `src/stage_abi/routes.py`, its policy and the historical
T03 reconciliation/architecture documents. The existing executable bundle router
requires exact constant-width polyline footprints, a shared reference bundle,
explicit ports/corridors, obstacle identities and finite movement bounds. Its
historical qualification cannot establish these operands for arbitrary raw boards.
Native source curves, graphic strokes, branched/mixed-width routes and bundle
inference cannot silently be coerced into that router.

U02 implements a separate **native-whole-board-retain-valid-paths/1** T03 adapter.
It supports required remediation of actual T01 growth by retaining original valid
paths when no remediation is needed. It does not search for optional additional
land growth, reopen T01, widen traces or infer electrical net intent.

Every F.Cu segment, arc, graphic line and graphic arc is source-bound and covered,
including untouched/distant occurrences. Original widths and source spans/hashes
are retained. The entire T01 scene must match the exact freshly verified candidate,
with complete source/alias coverage. Freshly reconstructed native source ports must
match all saved T01 port pages exactly. Spatial queries conservatively select every
trace/land pair within the hard-gap band; finite copper is checked with the existing
T01 0.020 mm gap, 128 quadrant segments and 1e-10 mm² area threshold. Stored ports
remain explicit exemptions. Inherited narrow gaps are not universal clearance
approval. Unchanged native geometry preserves existing trace/trace relationships.

When all affected paths pass, T03 emits **NO_CHANGE_REQUIRED**, with zero moved
traces. Its output geometry is exactly its T01 predecessor; a separate U02 lineage
and verification receipt records this identity. Export then executes fresh native
KiCad write/reread and Gerber export/reparse after T03. Equal geometry or export
hashes are expected for this disposition, and do not imply route movement occurred.

If movement or lost attachment is detected, the paginated inspection remains and
planning halts with **U02_T03_MOVEMENT_NOT_QUALIFIED**. No candidate export is
published, no old C01/C02/C03 route is reused, and no success/no-improvement fallback
is substituted. General automatic whole-board displacement remains unqualified.

## Gates, custody and outcomes

The contract is `contracts/operator/u02_board.json`: **25** actual native gates,
comprising 13 original source/T01 gates (through board_candidate_check), seven
T03 inspect/plan/search/verify/compare/review/controls gates, then five native
export gates. Source/T01 construction, separate reconstruction, full pagination,
correspondence negatives, unsupported-English control and export corruptions remain.
T03 adds wrong-predecessor, hidden-route-change and real finite-copper-intrusion
controls, retained separately with their exact expected rejection reasons.

Terminal runs create 25 hash-bound machine proofs and zero human/agent observation
records. The route independently recalculates each proof before advancement.
Local Code runs require 25 distinct agent observations; neither mode is independent
review or owner acceptance. The legacy wire token PASS_SLICE_OBSERVATION_AUDIT is
preserved for checkpoint compatibility, with the audit mode recorded separately.
The T03 review gate reads pending acceptance; it does not create an owner decision.

U02 uses `out/lacie_work/operator_routes/u02_board/managed/`; T01 retains its existing
namespace/behavior. Each run has fresh job identity, separate T01, U02 and export
checkpoints, native process receipts/output and retained negative controls. Jobs
cannot replace an in-progress predecessor or retry identical failed content/code.
The Terminal client preserves adapter-death polling, traceback/errno reporting,
owned-process termination and visible evidence-write failures from T01.

The supplied raw-directory accounting policy is preserved: uniquely verified F.Cu
and any other participating layers must match fresh native source plots. Unmatched
Gerbers remain byte-identical excluded companions with layer/geometry NOT_ESTABLISHED,
not verified layers or regenerated exports. The final nine-layer native export
comes from the supplied source board; excluded companions have separate paths.

All later U stages, T02/T04/T05, rendering and shared-clearance changes are outside
this route. Frozen results stay unchanged. Owner PENDING_USER; independent
NOT_RUN: CHANNEL_UNAVAILABLE; electrical/manufacturing NOT_ESTABLISHED.

## Qualification status — 2026-11-02

The implementation snapshot passed 205 focused/regression tests (21 U02, 184
preservation checks). Fresh ORG native qualification **HALTED** after three
successful source gates/machine audits: a concurrent Local Code cache-relocation
addition changed AGENTS.md during the run, and the existing custody guard rejected
`T01_DELIVERY_CODE_CHANGED:AGENTS.md` before T01 compile. The remaining 21 operations
are NOT_RUN; no real-board U02 candidate exports were created. No retry occurred.
Concurrent storage/cache edits remain intact. The source tree is not yet qualified
for owner operation. Complete status, source snapshots, exact hashes/diff and
failure evidence: `out/lacie_work/evidence/u02_implementation_20261102/U02_HANDOFF.md`.
The original T01 result's 1,709 delivery files verified unchanged without reexecution.

## Null rejection summary repair — 2026-11-02

The user's subsequent job `20261102T100747Z-870de7e68c724890a3ec0d59b93c9357`
passed T01 construction/reconstruction and eleven machine audits. The deliberate
unsupported-English native check correctly returned exit 2, T01_ENGLISH_UNSUPPORTED
and result:null. U02's summary projection then raised TypeError before that
control's machine audit. T03 and exports remain NOT_RUN.

The projection now permits this intentional null result. Four regression cases
cover the complete client offer path in Local Code/machine modes and successful
control summaries. The current focused/preservation suite passes 211 tests.
All 70,705 retained job files matched their pre-fix hashes; no native retry,
resume or audit promotion occurred. Fresh whole-board native qualification remains
pending. Evidence: `out/lacie_work/evidence/u02_null_summary_fix_20261102/REPORT.md`
and `FIX_AUDIT.json` in the same directory.

## Completed fresh ORG qualification — 2026-11-02

The later fresh job `20261102T104731Z-11aa3662e57c4e559fcb169f069ab53a`
completed 25 native gates and 25 machine audits (422 predicates), with zero
human/agent observations. Its retained completion audit verified 1,785 delivery
files and 25,188 machine-evidence files without native reexecution or producer
drift. T03 assessed 15,858 trace occurrences, 159 trace pages and 19,527 affected
pairs; the result is NO_CHANGE_REQUIRED, zero moved traces. This establishes the
retain-valid-paths family on that input, not general whole-board rerouting.
Nine candidate Gerbers and 14 byte-identical excluded companions were verified;
participating raw layers are F.Cu, F.Mask and F.Paste. Rendering NOT_REQUESTED;
owner PENDING_USER; independent NOT_RUN: CHANNEL_UNAVAILABLE;
electrical/manufacturing NOT_ESTABLISHED. Earlier failed jobs remain immutable.

Read-only audit:
`out/lacie_work/evidence/u02_completion_audit_20261102T104731Z/COMPLETION_AUDIT.json`.
The precommit check passed 139 focused U02/storage/T01/export tests; log:
`out/lacie_work/evidence/u02_precommit_20261102.log`.
