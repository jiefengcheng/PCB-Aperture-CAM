# PCB-Aperture-CAM-V1 — isolated Codex handoff

## Copper Trimming 0.2.0 reproduction

The [Mac rebuild and Ubuntu/Docker development guide](reproduction/large_copper_0.2.0/README.md)
includes the tested [source.gbr baseline](baselines/large_copper_0.2.0/source.gbr),
reference results, package versions and the app/DMG builder. A bit-identical DMG
is not required. The native viewer is macOS-only; Linux source intake and the
remaining runtime-porting boundaries are documented separately and do not imply
qualified end-to-end Linux trimming.

## Current T01 rules

Use the maintained [plain-language T01 rulebook](docs/T01_RULES.md) for current
user-directed rules, precedence and parameter sources. It includes the **58%
exposed-circumference** threshold, separate paired/single/BGA cases, integral
source joints and protected pin separation. Qualification and app integration
are listed separately; historical crop guides below retain their original scope.

## First intake gate: profile a received directory

For a new dataset with no existing qualified package recipe, start with the [general directory profiler](docs/okf/ingestion/general-profiling.md). It preserves regular files, records source-relative paths and SHA-256 identities, and writes a sealed draft profile. Use `out/` for temporary review or `dataset/` for a durable local intake package:

```bash
.venv/bin/python tools/profile_dataset.py \
  --source /path/to/received/directory \
  --dataset-id client:project:revision:v1 \
  --output dataset/project-revision-v1
```

This gate establishes file custody and identity only. It does not parse or qualify dataset contents or extract board objects. It seals a registration recipe so **+** can add the profile to the workbench; qualification remains a separate step and stays `NOT_RUN` until actually performed. Follow the [profiling-to-workbench steps](docs/okf/ingestion/general-profiling.md#continue-into-the-workbench) to verify the package, run the local server, and add the generated directory.

## T01 implementation map

The accepted crop pipeline now has a concise [code structure map](docs/crop_dynamic_tasks/T01_CODE_STRUCTURE.md), separating source discovery, target selection, recess construction, owner edits, orchestration, audit, and replay presentation.

## Local CAM Agent boundary

The first [CAM Agent ABI v0.1](docs/agent_abi/README.md) is a strict, hash-bound local JSON interface for describing capabilities, inspecting and comparing registered results, composing an immutable plan, and retrieving review evidence. `cam_run` and `cam_verify` are explicitly unavailable; this boundary does not execute geometry or elevate T01's partial behavior status.

## Current T01 review: owner corrections

The [owner-correction guide](docs/crop_dynamic_tasks/T01_OWNER_CORRECTIONS.md)
records the exact undo of S38/S22 and the larger S08 envelope with a recess toward
S12. Other target radii remain frozen. Geometry checks pass; T01 remains
**PARTIAL** on evolving-companion behavior (0 of 3 required events). The owner
accepted the saved crop visually; this does not establish engineering or
manufacturing acceptance.

```bash
.venv/bin/python tools/run_crop_diameter_classes_t01.py --apply-owner-review --output out/crop_dynamic_tasks/t01_owner_review_replay_01
.venv/bin/python -m http.server 8783 --bind 127.0.0.1 --directory out/crop_dynamic_tasks/t01_owner_review_20261024_v2
```

## Earlier T01 review: recover growth while keeping priorities round

The [full-round growth review](docs/crop_dynamic_tasks/T01_FULL_ROUND_GROWTH_REVIEW.md)
implements the owner's latest choice to keep all eight newly marked priorities
fully round. A discrete promotion pass recovers free size-band capacity: three
marks grow further, five retain reproduced next-band blockers. The UI shows
rejected next-round proposals as diagnostics. The 1.5× cap and protections hold;
T01 remains **PARTIAL**, with zero evolving-companion events.

```bash
.venv/bin/python tools/run_crop_diameter_classes_t01.py --round-priority-promotion --output out/crop_dynamic_tasks/t01_round_priority_promotion_replay_01
.venv/bin/python -m http.server 8783 --bind 127.0.0.1 --directory out/crop_dynamic_tasks/t01_round_priority_promotion_20261024_v3
```

## Earlier T01 review: common physical diameters

The [shared-diameter trial and review guide](docs/crop_dynamic_tasks/T01_DIAMETER_CLASS_REVIEW.md)
adds discrete envelope sizes and the owner's case-6 square-guided recess. Six of
eight marked sites gain more copper; marks 1 and 2 remain open. Hard 1.5× caps and
local geometry checks pass. T01 remains **PARTIAL** (zero evolving-companion effects).
That earlier replay is `out/crop_dynamic_tasks/t01_diameter_classes_20261024_v3/`;
the continuous-factor trial below is retained historical context.

```bash
.venv/bin/python tools/run_crop_diameter_classes_t01.py --output out/crop_dynamic_tasks/t01_diameter_classes_replay_01
.venv/bin/python -m http.server 8783 --bind 127.0.0.1 --directory out/crop_dynamic_tasks/t01_diameter_classes_20261024_v3
```

## T01 crop trial: balanced growth with a hard 1.5× ceiling

The owner's tentative two-site approval is applied to all 51 circle sites in the
frozen client crop, balancing small neighbouring groups and retaining one round
priority per original physical component. The [frozen trial policy](contracts/crop_balanced_t01_policy.json)
sets the unconditional radius ceiling; existing T01/R1 evidence is preserved.
This is a local review experiment, not accepted CAM or manufacturing output.

```bash
.venv/bin/python -m unittest tests.test_crop_balanced_t01 tests.test_crop_balanced_t01_publication tests.test_crop_balanced_capped_growth tests.test_crop_square_neighbor_experiment -v
.venv/bin/python tools/run_crop_balanced_t01.py --output out/crop_dynamic_tasks/t01_balanced_capped_replay_01
.venv/bin/python -m http.server 8783 --bind 127.0.0.1 --directory out/crop_dynamic_tasks/t01_balanced_capped_20261024_v4
```

Use a fresh output directory for each execution. The saved review shows the full
ORG crop, accepted effective copper, additions, component priorities, the fair
static-neighbour comparator and all individual sites. That earlier trial grows
45 sites and preserves 26 round priorities. Fifteen companions respond to grown
priority reservations, but **zero** respond to evolving companion updates; the
fair static comparator is identical. Local geometry passes, while T01 remains
**PARTIAL** pending the missing dynamic behaviour and owner crop review. Receipts,
counterfactuals, failed runs and ignored visual artifacts remain under `out/`.

**Current delivery: a bounded client-Gerber operation, nine-step workbench walkthrough, and narrated replay.**

Start with [Client demonstration](docs/CLIENT_DATA_DEMO.md) and [consolidated decision](docs/CLIENT_OPERATION_DECISION.md). The source artwork is already aligned; a labeled controlled offset exercises automatic candidate generation, local validation and rejection/rollback. Strict asset inventory now passes for all 70 frozen assets, and the full suite passes 114 tests; [delivery issues](docs/CLIENT_ISSUES.md) records maintenance fixes. Client data, evidence and video remain local under ignored directories. Cursor review is NOT_RUN; manufacturing approval is NOT_ESTABLISHED.

The original V1 handoff below is retained as historical bootstrap context.

See `docs/STATUS.md` for tested coverage, evidence, commands and limitations. Implementation is in `src/`; actual exported baseline and negative controls are retained under `out/`.

This is an independent experiment to validate a bounded copper-pad-and-trace adjustment relative to a frozen solder-mask aperture. The original synthetic coupon includes a generated **before** state (P1 X=20.35 mm) and a generated **candidate** state (P1 X=20.05 mm). The aperture remains centered at X=20.00 mm. All dimensions and tolerances are synthetic examples, **not** factory specifications.

## Exactly what is bundled

- `assets/starter/`: the original, untouched synthetic fixture suite, its generated KiCad source boards, reference Gerbers (marked synthetic), negative examples, policies, and internal geometry tests.
- `assets/observed_before/`: **one real KiCad-exported before baseline**, `F.Cu`, `F.Mask`, `Edge.Cuts`, and `.gbrjob`. There is **no actual KiCad-exported candidate** bundled: generate it with `tools/export_native.py` before claiming exported-result acceptance.
- `assets/source_archive/`: the original synthetic starter archive; no remote cloned datasets.
- `contracts/asset_manifest.sha256`: all assets frozen by hash.
- `tools/preflight.py`: stdlib-only source integrity and fixed-fixture sanity checks; **not** a general Gerber parser or validator.
- `tools/export_native.py`: optional reproducible KiCad CLI exports of source copies, producing outputs under `out/` only. KiCad isn't bundled.
- `tests/test_bootstrap.py`: runnable bootstrap tests. `docs/` contains Codex handoff, Cursor review contract, validation requirements, provenance and status.

## Quick start on your Mac (new directory / workspace)

```bash
unzip PCB_Aperture_CAM_V1_Codex_Handoff.zip
cd PCB_Aperture_CAM_V1_Codex_Handoff
python3 tools/preflight.py --output out/bootstrap.json
python3 -m unittest discover -s tests -v
# Optional: create a *new* local git repository, not a subfolder in another repo:
git init
git add .
git commit -m 'baseline: isolate synthetic PCB CAM V1 and Codex contracts'
```

Open this folder as a **NEW Codex project/task**, not inside the user's existing research repository. Paste `docs/PASTE_TO_CODEX.md` into a new Codex chat. The repository `AGENTS.md` provides mandatory scope limits.

To export both native fixtures with local KiCad:

```bash
python3 tools/export_native.py --case both
# Optional if CLI isn't on PATH:
python3 tools/export_native.py --case both --cli /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
```

Exports are written into a timestamped subdirectory of `out/native_exports/`, leaving original `assets` untouched. KiCad must be installed locally. A valid exported Gerber file is **not** automatically an acceptable PCB modification.

The intended V1 implementation may use Python 3.12+ with Shapely and Gerbonara (see `requirements-dev.txt`). Install these only into this project's virtual environment, record exact versions and licenses, and run all work inside this checkout. If Codex is cloud-only and cannot access your Mac's KiCad, do not claim native exports occurred: mark that step `NOT_RUN` and use a local Codex environment or bring back the exact native-export artifacts later.

## Ownership and boundaries

**Codex alone** coordinates planning, implementation, Cursor delegation (if an actual authenticated channel exists), commits, and acceptance. Cursor is an independent *read-only reviewer* after a frozen commit. No global Codex/Cursor config changes, no touching C7/C8/LPA/Viewer lanes, and no unrelated worktrees. If Cursor is inaccessible, record `NOT_RUN/CHANNEL_UNAVAILABLE`; do not ask a human to transfer messages between the agents.

The V1 stop line is independent geometric validation of *actual exported data*. Do not begin an autonomous KiCad editor, AI/GNN training, a PCB-to-Gerber reconstruction stack, or manufacturing sign-off.


## Public asset qualification amendment

The authorized V1.5 pass is complete with realistic validation **NOT_ESTABLISHED**. Selected GlowStitch and HALPI2 native boards export in the pinned CLI, while their geometry exceeds frozen V1 coverage. Official Ucamco examples reveal two aperture-block parser gaps. See `docs/ROADMAP.md` and `docs/V1_5_DECISION.md`; source revisions/hashes are in `contracts/public_sources.json`. Public checkouts are immutable local inputs in `external/sources/`, separate from synthetic `assets/`.


## Proposed long-term charter

See [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md) for the proposed strategic reference and [docs/CHARTER_INTEGRATION.md](docs/CHARTER_INTEGRATION.md) for reconciliation with frozen evidence and operational rules. [docs/NEXT_GATE_PROPOSAL.md](docs/NEXT_GATE_PROPOSAL.md) awaits user approval. This alignment authorizes no new implementation.


## FC-1 oracle qualification

The adopted charter reconciliations and FC-1 were approved on 2026-10-14. [FC1_DECISION.md](docs/FC1_DECISION.md) records one exact Ucamco mathematical-oracle qualification PASS. The original parser still rejects aperture blocks; realistic validation remains NOT_ESTABLISHED. No parser implementation, MC-1 or V2/V3 began.


## Working V1.5 reader/compositor path

[Completion decision](docs/V1_5_COMPLETION_DECISION.md): both declared nine-layer public-board geometry/preservation profiles pass, with raw FC-1 oracle agreement and source-anchored fault detection. Overall named electrical acceptance remains NOT_ESTABLISHED for GlowStitch because its net intent is absent. Reproduce with `.venv/bin/python -u -m src.completion_run`; new timestamped evidence is retained under `out/v15_completion/`. Frozen V1/FC-1 paths remain unchanged.


## Bounded automatic execution

The authorized synthetic MovePadWithConnections V2 slice is complete. See [V2 decision](docs/V2_DECISION.md). Reproduce with `.venv/bin/python tools/v2_run.py`; the executor computes the candidate from the immutable before source and frozen policy, exports through KiCad, validates independently and only then publishes a local accepted bundle. Public-board automatic editing and manufacturing approval are outside this result.


## Visual case workbench

[Visual delivery and guided replay](docs/VISUAL_WORKBENCH.md) connects the synthetic aperture, HALPI2 electrical controls and GlowStitch information boundary to actual local geometry/evidence. Generate a self-contained HTML/SVG bundle with `.venv/bin/python tools/visual_report.py`. Output location is printed and recorded in out/visual/current.txt. No server, cloud upload, board editor or new acceptance decision is required.


## G22 family reconstruction experiment

The bounded G22 experiment applies a compact ORG-derived copper-area treatment to three registered family members, exports the candidates through KiCad, rereads the Gerbers, and compares the results with EDIT in the existing workbench. The scope, measurements, remaining uncertainty and replay command are in the [G22 reconstruction report](docs/G22_FAMILY_RECONSTRUCTION_REPORT.md); the experiment rules are in the [handoff](docs/G22_FAMILY_RECONSTRUCTION_HANDOFF.md). This is experimental local geometry evidence only, not electrical or manufacturing acceptance.
