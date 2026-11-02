# Whole-board T01 recipe: agent or CLI

## Finish retained outputs without more rendering

The current whole-board workflow is **COMPLETED_WITH_FAILED_FINDINGS**.
Rendering qualification stays **FAIL**: tile-001-006 reports a 1.089077 µm
sample against the unchanged KiCad 1 µm band. Sixteen tiles passed, one is
failed/partial, 143 pixel checks and final controls are NOT_RUN. All 21 planned
slices have explicit dispositions: 19 PASS, one FAIL, one NOT_RUN. The original
native attempt remains HALTED and read-only; only its additive report is closed.

English for Local Code or another agent:

> Finish the retained whole-board T01 pipeline as completed with failed findings. Use existing candidates and views only. Keep the failed render audit and all unrun checks explicit. Do not render, construct or export again. Keep frozen results, shared clearance and T02–T05 unchanged.

CLI, for the current managed whole-board job:

```sh
python3 tools/pcb_t01_board_operator.py finalize
```

For a supplied retained job outside the current slot:

```sh
python3 tools/pcb_t01_board_operator.py finalize --job "/absolute/project/out/path/to/retained-job"
```

No launcher, MCP, dependency installation or native process is needed for this
file-only action. It validates the complete accepted prefix, original failed
attempt, observations, source/export checkpoint, file hashes and tile coverage.
It creates a separate report, status-labelled tile pages and machine-readable
completion; it never edits the old job, changes bands or fabricates controls.
Repeated finalization verifies and returns the same report. Current crop jobs,
active/unclosed jobs, changed source/exports, missing observations and non-pixel
failures reject. Exit 0 means report complete, **not** render qualification PASS.
Native failure and qualification remain machine-readable. Return supplied
`ready_markdown` unchanged at REPORT_AND_STOP.

Current retained review: /Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/operator_routes/t01_board/completions/cb798416ec772379d1a0c3eef2f00824d7eaba3bc3067031f147504748d9db87/index.html

The rest of this recipe describes a fresh full run only when separately requested.
Do not invoke `start` to finish retained outputs or to inspect the current result.

## Common setup, once per working session

Use this checkout:
`/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff`.

Open the existing `tools/Start_T01_Native_Launcher.command` in Finder, and keep
its Terminal open. Alternatively, from a Terminal in this checkout:

```sh
open tools/Start_T01_Native_Launcher.command
```

The adapter uses project Python, pinned KiCad and local contracts. No MCP, server,
global configuration, install or per-board coordinator preparation is required.
The native launcher is shared with the crop route: run one job at a time. Preserve
any existing incomplete job; do not start a replacement or rename failed inputs.

## Local Code or another agent

Open this checkout as the agent's project. Give this ordinary-English request:

> Apply T01 to all eligible round terminals across the entire board’s F.Cu layer, using the loaded KiCad and Gerber inputs. Export separate candidates and show them side by side. Retain all audits and keep frozen results, shared clearance and T02–T05 unchanged.

An agent that reads AGENTS.md gets the route automatically. For another agent
without repository-instruction discovery, add this execution instruction:

> Follow docs/agent_abi/WHOLE_BOARD_T01_RECIPE.md and contracts/operator/t01_board.json. Use tools/pcb_t01_board_operator.py start, read each returned native result, and submit one distinct factual observation with review for each REVIEW_REQUIRED gate. Complete all 21 gates without asking me to continue. Poll an already-running command until it finishes. Do not launch a second command, perform probes or retry a failed gate. On REPORT_AND_STOP return its complete Markdown, images and file links, then stop. Do not claim owner or independent acceptance.

No manual copying of source identifiers, bounds, hashes, native parameters or
JSON audit packets is required. The agent supplies observations of returned
facts; the runner carries the exact operands, receipts and complete manifests.

## CLI, using the same route

From a Terminal already in the checkout, with the launcher open:

```sh
python3 tools/pcb_t01_board_operator.py start
```

Wait for completion. A native operation may report NATIVE_WORK_IN_PROGRESS and
actual tile counts. Do not run the next command while the current one is running.

When the result says REVIEW_REQUIRED, read its `operation`, `facts`, any
`measurements` and `controls`. Submit your own one-sentence observation:

```sh
python3 tools/pcb_t01_board_operator.py review "Your observation of the result just returned"
```

Repeat for all 21 gates. Each review records the current gate and executes only
the next slice. A review observation is a technical record, not owner approval.
Do not paste a prewritten success assertion before checking the actual result.
A shell-only unattended loop must not invent observations or auto-approve them;
a human or agent reads each result and supplies the observation.

For local replacement input files, specify exact paths once at start:

```sh
python3 tools/pcb_t01_board_operator.py start --kicad "/absolute/path/input.kicad_pcb" --gerber "/absolute/path/input-F_Cu.gbr"
```

For native app-staged attachments, the corresponding options are
`--kicad-attachment "uploaded board label"` and
`--gerber-attachment "uploaded F.Cu label"`. Attachment ingestion resolves the
staged label; no Desktop path search or Unicode filename reconstruction is needed.
Omitting both input options uses the loaded project pair. Never rebind inputs
mid-job. New inputs still must qualify within the supported native profile.

## Gate checklist

| Gate | Native operation | What the observation must assess |
|---|---|---|
| 1 | pcb_inputs_verify | Complete original F.Cu inventory and source Gerber correspondence |
| 2 | pcb_board_scope | Geometry-derived whole source/growth window; every occurrence |
| 3 | pcb_board_verify | Exact source/alias completeness and three omission/window controls |
| 4 | t01_compile | Sixteen supported clauses and retained numerical settings |
| 5 | t01_discover | All source pages, canonical sites and aliases |
| 6 | t01_inspect | All inspection pages exhausted |
| 7 | t01_plan | Full source pool, groups, concentric proofs and exact port pages |
| 8 | t01_run | Fresh construction, all assembled checks and neighbor controls |
| 9 | t01_verify | Separate fresh reconstruction from source, all targets |
| 10 | t01_compare | All comparison pages and actual added/removed measurements |
| 11 | t01_review | No owner decision injected; review remains pending |
| 12 | t01_negative_compile | Deliberately unsupported English rejected without construction |
| 13 | board_candidate_check | Complete verified source handoff, no historical candidate input |
| 14 | pcb_kicad_write | All occurrences written, representation proofs retained |
| 15 | pcb_kicad_verify | Separate target reread; protected nodes equal |
| 16 | pcb_gerber_export | Native actual nine-layer export, tool/version/precision |
| 17 | pcb_gerber_verify | Actual reparse, all targets, protected F.Cu and eight other layers |
| 18 | pcb_export_controls | Three deliberate export corruptions reject for intended reasons |
| 19 | render_compare | Complete paired F.Cu tile coverage; actual renderer identified |
| 20 | render_verify | Both viewports and every pixel in every tile, original error bands |
| 21 | render_controls | Mirrored, blank, wrong-viewport and altered-hash controls reject |

The eight other layers are exported/checked for preservation; they are not rendered
in the F.Cu tile workload. The whole-board overview is navigation only. The detail
pages have linked zoom/pan. Gerber curves use qualified Gerbonara SVG and native
SIPS; KiCad uses its native SVG export and SIPS. All pixels are checked against
separately parsed exported-file geometry. No tolerance is increased to pass a view.

## Finish, reuse and failures

REPORT_AND_STOP supplies absolute paths to the KiCad candidate, Gerbers, PNG,
HTML tile index and full evidence. Return its complete Markdown and stop. Owner
PENDING_USER; independent NOT_RUN: CHANNEL_UNAVAILABLE; electrical/manufacturing
NOT_ESTABLISHED. Visual display and successful technical checks are distinct from
owner approval or universal minimum-distance clearance qualification.

To retrieve the **already completed current job** without reconstructing or
rendering again:

```sh
python3 tools/pcb_t01_board_operator.py review "Show the retained completed report"
```

This uses the completed-job branch and verifies its retained manifest. It is not
an instruction to advance an incomplete gate. To hand off an incomplete run,
include the exact last REVIEW_REQUIRED result so the next operator can assess it;
do not submit an observation blindly. `start` requests a fresh job, not a cached
view. Reuse completed views when inputs, growth, exports and render settings are
unchanged. Use geometry previews while revising growth; full rendering belongs
after successful construction/reconstruction and export checks.

An eligible retained pixel-tolerance rejection after the complete 19-slice prefix
is finalized report-only as COMPLETED_WITH_FAILED_FINDINGS. Preserve FAIL and
NOT_RUN; do not run the remaining renderer controls or repeat any operation.
On other HALTED outcomes, preserve and report the error and evidence path, then stop. Do not
retry, shrink the source window, substitute inputs, change settings or promote
partial success. Resolving a reproduced code defect requires a separate authored
revision and fresh qualification; it is not an operator workaround. Do not run
T02–T05, overwrite frozen results or change shared clearance.
