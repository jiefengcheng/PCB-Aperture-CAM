---
type: "Playbook"
title: "Manual review and execution of the ingestion delivery"
description: "One entry for delivered results, evidence, manual checks, isolated replay rebuilding and optional existing engineering runs before Step 2."
generated: {"by": "codex/manual-review-consolidation", "at": "2026-10-17T20:09:55.621310+08:00"}
status: "stable"
tags: ["pcb", "ingestion", "manual-review", "execution"]
sources: [{"id": "evidence", "resource": "/references/manual-review-evidence.json", "title": "Current review artifacts and hashes"}, {"id": "implementation", "resource": "/references/sources.json", "title": "Source applicability bindings"}, {"id": "cursor", "resource": "/references/cursor-audit.txt", "title": "Independent Cursor final addendum"}]
---

This page retains the original ingestion checkpoint. The subsequently authorized bounded common catalogue is described in [the current catalogue result](../catalogue/minimum-slice.md); earlier deferral statements here are historical.

# Delivery and review boundary

For the shortest visual walkthrough, start with [Visual client review](/ingestion/visual-review.md). The client screen now separates correspondence, the pad-move demonstration, and unfinished work; technical receipts are collapsed.

The ingestion implementation has since been refactored and the hard-coded Cursor channel status corrected. The pinned publication below remains the earlier independent-review reference. Follow the latest [maintenance addendum](/ingestion/maintenance.md) for the new run and its separate verification status.

Review the corrected ingestion delivery and reproduce its checks before deciding Step 2, the common object catalogue. This guide consolidates what exists, where evidence lives, what each command executes, and what to record. Common catalogue design and implementation remain deferred.

The reviewed publication is `out/ingestion/workbench/run-05888c57424f4db48bd9821fc8324b36/`. It contains 351 verified outputs, five dataset groups and three client correspondence views. The current implementation is an uncommitted working-tree snapshot over HEAD `19ff47204d429b93fdac21d3b1a94ed3462b3629`; the reviewed file hashes identify it more precisely than HEAD alone. Local retained data and `out/` are required; a source checkout alone is not a complete reproducible package.

| Delivered result | What you can review | Current evidence |
|---|---|---|
| Registered source and evidence entry | Synthetic coupon, GlowStitch, HALPI2, Ucamco examples and client intake; provenance, hashes and separate qualification scopes | `contracts/ingestion_registry_v1.json`; reviewed publication `registry.json` |
| Client correspondence review | Pure source/native panes and separate delta; R140.1 local match, L2GND divergence and drill correspondence | Reviewed `scene.json`, copied receipts under `ingestion_evidence/`, per-view input hashes in `receipt.json` |
| Strict publication verification | Schema/status, required files, exact inventory, embedded scene, registry, evidence and measurement bindings | `src/ingestion_verification.py`; reviewed `receipt.json` |
| Failure controls | Empty/failed bundles reject; changed/missing render inputs reject; failure before publication retains the prior entry | Remediation tests and `out/ingestion/remediation/actual_cli_publication_failure.json` |
| Existing native pipeline and operation replay | Processing, Storage and Cases on their recorded workloads | `out/consolidation/pipeline_20261014T203542_446846Z/receipt.json`; retained case receipts |
| Remediation and independent review | Original R1–R4 failures, their corrections, scoped Cursor verdict and unrun checks | [Remediation audit](/references/completion-audit-v2.json); [Cursor addendum](/ingestion/cursor-audit.md) |
| Reproduction instructions | Intake, replay, native pipeline, bounded client operation and export recipes | [Runbook index](/runbooks/index.md) |

The [evidence inventory](/references/manual-review-evidence.json) records exact paths and hashes. Original failed review artifacts and the rejected earlier publication remain preserved. The corrected publication supersedes the earlier completion claim.

# What executes and what replays

| Action | Actually happens now | Meaning of the result |
|---|---|---|
| Verify sealed intake | Check source/package hashes, strict inventory, archive equality and historical bindings | Custody; not a new geometry or electrical experiment |
| Verify reviewed publication | Check retained files, embedded scene, registry and evidence-derived fields | Publication consistency; not manufacturing acceptance |
| Click through the browser | Select stored datasets, records, geometry and event snapshots | Read-only REPLAY; no new import/query/repair |
| Rebuild ingestion workbench | Verify registered inputs, recompose the bounded display geometry, load bound historical measurements, stage and publish a new bundle | Fresh presentation build; historical CAM decisions remain historical |
| Run native pipeline | Extract inventory, build context, persist/reopen a revision and record queries for selected native inputs | Fresh source/context execution; no candidate operation by itself |
| Run client operation | Create the explicit artificial offset, compute/export/reparse the bounded candidate, run controls and retain rollback evidence | Fresh bounded Gerber execution under its demonstration contract |

Registration is currently a configured local command plus read-only browser selection. It is not a general browser import flow. Client VME-WREN native Processing/Storage ingestion is not implemented. Existing client operation tools still read `external/sources/12_copper_layers_pcb_gbr`; the comparison renderer now reads registered sealed copies matched to receipt hashes.

# Prepare a manual review session

Run commands from this checkout. Keep the same terminal for the variable below. Use the existing project-local runtime and pinned dependencies; this guide does not install or upgrade anything.

```sh
cd /Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff
mkdir -p out/ingestion/manual_review_runs
pcb_cam_review_dir="$(mktemp -d "$PWD/out/ingestion/manual_review_runs/review_XXXXXXXX")"
echo "$pcb_cam_review_dir"
```

Record that printed directory in your review notes. Each new manual session gets its own directory. For ordinary commands, stop at an unexpected nonzero exit or stale/missing evidence. The negative controls below explicitly expect rejection.

# Check the existing result before rebuilding

```sh
python3 docs/okf/references/verify_runbooks.py
.venv/bin/python tools/preflight.py --output "$pcb_cam_review_dir/preflight.json"
python3 dataset/vme-wren_20261016_v1/scripts/verify.py   --expected-seal 7b1374e5eeb4cac943f3d7512a19da8a65a93212bd6bfa80c006930c85bc9e0e   --receipt "$pcb_cam_review_dir/intake.json"
.venv/bin/python tools/ingestion.py --verify   out/ingestion/workbench/run-05888c57424f4db48bd9821fc8324b36
```

Expected: runbooks `PASS`; preflight `PASS_BOOTSTRAP_ONLY` with 70 assets; sealed intake `PASS`; publication `PASS` with 351 outputs, five datasets and three comparisons. Preflight NOT_RUN fields describe that check's scope, not a revision of historical engineering results.

The following read-only check verifies that the original false-positive controls now reject. Its wrapper exits successfully only if both controls are rejected as expected; it does not alter them.

```sh
.venv/bin/python - <<'PYCODE'
import json, subprocess, sys
from pathlib import Path
base = Path('out/review/ingestion_assessment_20261016T184844_296975Z')
for name in ('empty_failed', 'empty_unknown'):
    result = subprocess.run(
        [sys.executable, 'tools/ingestion.py', '--verify', str(base/name)],
        capture_output=True, text=True)
    report = json.loads(result.stdout)
    assert result.returncode == 1 and report['status'] == 'FAIL', (name, result.stdout)
    print(name, 'EXPECTED_REJECTION', report['error'])
PYCODE
```

# Review the frozen workbench

Use the existing server if it is available. Otherwise, in a second terminal from the checkout, start:

```sh
python3 -m http.server 8768 --bind 127.0.0.1 --directory out/ingestion/workbench
```

Keep that terminal open. Open the exact [Cursor-reviewed publication](http://127.0.0.1:8768/run-05888c57424f4db48bd9821fc8324b36/index.html). The convenience entry is [index.html](http://127.0.0.1:8768/index.html), which may point to a different run after future publication. If port 8768 is occupied by another service, use an unused loopback port and adjust the URLs; do not stop an unrelated process.

| Order | Select or inspect | Expected observation | Record for Step 2 |
|---|---|---|---|
| 1 | Datasets / Ingestion → client VME-WREN | Native and Gerber source identities remain separate; conversion history is reported and unverified | What must an identity and provenance record contain? |
| 2 | R140.1 correspondence panes and local receipt | B.Cu/B.Mask zero recorded symmetric difference within the stated ROI; Edge.Cuts retains its own small difference | How should bounded correspondence be represented? |
| 3 | L2GND source/native/delta and discrepancy receipt | 12 source-only flashes; six joined delta shapes after composition; 5.975804925704194 mm² recorded difference; native pane does not acquire source-only copper | How should disagreement remain discoverable without merging sources? |
| 4 | Drill receipt and displayed values | 4,894 PTH hits, two slots, eight NPTH hits; 0.003 mm position/endpoints and 0.002 mm tool tolerances where recorded | Which units, tolerances and evidence must accompany a measurement? |
| 5 | Processing → `synthetic_before` | 17 source objects, 14 with geometry; unsupported/container records remain explicit | Which object kinds and coverage states do you need? |
| 6 | Storage & indexes → same source | Exact source bytes, revision identity, ordered/region/nearby query receipts | How will a selected object be traced and retrieved? |
| 7 | Physical component, spatial witnesses and modification permissions | Connected, nearby and writable sets have different meanings | Which relation types and permission boundaries must stay separate? |
| 8 | Cases → synthetic coupon | P1 20.35 → 20.05 mm against opening 20.00 mm; open/bridge/protected-object controls reject | What must selection supply to an existing operation? |
| 9 | Cases → client local operation | Supplied original already aligned; +0.35 mm is a deliberate challenge; accepted candidate restores original bytes; open/bridge controls reject | What counts as source, challenge, candidate and acceptance? |
| 10 | GlowStitch, HALPI2 and Ucamco registrations/cases | Unknown intent, bounded named electrical qualification and parser examples keep distinct scopes | Which capabilities must be optional or unavailable? |

Processing/Storage source selection is its own recorded native workload selector. Selecting the client in Datasets does not import it into those views. Open an evidence link and confirm it corresponds to the measurement/finding you selected. The browser is read-only; a replay click does not run a live database query or CAM operation.

# Rebuild ingestion replay in a separate directory

This is the current delivery's fresh producer path. It preserves the Cursor-reviewed entry by using an explicit output directory. It can take a few minutes. Run it only after the custody checks above pass.

```sh
.venv/bin/python tools/ingestion.py   --output "$pcb_cam_review_dir/workbench" > "$pcb_cam_review_dir/rebuild.json"
cat "$pcb_cam_review_dir/rebuild.json"
```

Expect `status: PASS` and a newly printed immutable run path. This build verifies sources and generates display derivatives; it does not execute a new CAM move or recompute the historical comparison/drill acceptance receipts. If the command fails, inspect its error instead of treating a retained entry as a new success.

Verify the exact newly generated bundle:

```sh
.venv/bin/python - "$pcb_cam_review_dir/rebuild.json" <<'PYCODE'
import json, subprocess, sys
from pathlib import Path
record = json.loads(Path(sys.argv[1]).read_text())
assert record['status'] == 'PASS'
run = Path(record['run'])
subprocess.run([sys.executable, 'tools/ingestion.py', '--verify', str(run)], check=True)
print('Generated run:', run)
print('Receipt:', run/'receipt.json')
PYCODE
```

In a terminal with `pcb_cam_review_dir` set to the exact directory printed earlier, serve this separate output on an unused port. A new terminal does not inherit that shell variable; set it there first. The guard below rejects an unset variable.

```sh
python3 -m http.server 8769 --bind 127.0.0.1 \
  --directory "${pcb_cam_review_dir:?Set pcb_cam_review_dir to your printed review directory}/workbench"
```
 Open [the separate replay entry](http://127.0.0.1:8769/index.html). Keep its new receipt/run identity in your notes. The earlier Cursor verdict does not automatically review this new build.

# Exercise publication failure and focused tests

The failure check below uses only your separate output. It deliberately fails after staging and asserts that your previous entry remains byte-identical. Expect `EXPECTED_FAILURE_WITH_PRIOR_ENTRY_PRESERVED`; it may take as long as another build.

```sh
.venv/bin/python - "$pcb_cam_review_dir/workbench" <<'PYCODE'
import json, subprocess, sys
from pathlib import Path
output = Path(sys.argv[1]).resolve()
entry = output/'index.html'
before = entry.read_bytes()
result = subprocess.run(
    [sys.executable, 'tools/ingestion.py', '--output', str(output), '--fail-before-publish'],
    capture_output=True, text=True)
report = json.loads(result.stdout)
assert result.returncode == 1 and 'Injected failure' in report.get('error', ''), result.stdout
assert entry.read_bytes() == before
print('EXPECTED_FAILURE_WITH_PRIOR_ENTRY_PRESERVED')
PYCODE
```

Run the focused Python regressions in a fresh log:

```sh
.venv/bin/python -m unittest   tests.test_ingestion_registry   tests.test_client_replay_integrity   tests.test_visual_bundle_verifier -v > "$pcb_cam_review_dir/tests.log" 2>&1
cat "$pcb_cam_review_dir/tests.log"
```

Expected current result after the maintenance refactor: 25 methods pass, consisting of 16 ingestion methods and nine existing replay/verifier methods. This is not the full project suite. The three current JavaScript DOM contract checks run through the bundled Node REPL, including generation-time review status. If Node is already on your PATH, they can also be run as:

```sh
node tests/js/ingestion_views.test.cjs
```

Expect JSON `status: PASS` with three checks. Node is not on PATH in the last checked shell; if unavailable in your shell, record this optional rerun as NOT_RUN rather than installing a global runtime.

# Optional existing engineering executions

These are separate from rebuilding the ingestion entry. They are available for manual examination when you want to distinguish new computation from replay. This consolidation did not rerun them on your behalf.

| Purpose | Existing command or recipe | Effects and expected inspection |
|---|---|---|
| Fresh synthetic native inventory, persistence and queries | `.venv/bin/python tools/consolidation_pipeline.py` | New `out/consolidation/pipeline_*/`; inspect `synthetic_before.json`, `catalog/`, query/reopen evidence and `receipt.json`. Expected producer status `GENERATED_NOT_ACCEPTANCE`. No move/export execution; no client native ingestion. |
| Fresh bounded client Gerber operation and controls | Follow [client reproduction prerequisites and commands](/runbooks/client-case.md) | Reads original external Gerbers; creates candidate/control/rollback evidence and updates client operation/demo convenience pointers. Check source correspondence and sealed-base prerequisites first. |
| Fresh native plotting | Follow [native export recipe](/runbooks/native-export.md) | Uses pinned CLI and source copies; new tool/version/command/output evidence. Separate from comparison replay. |

A fresh client operation is not automatically rebound into the fixed ingestion registry. A newly generated client visual is a separate output; do not assume the combined ingestion page now shows the new operation. Likewise, do not run the broader consolidated demo as a replay shortcut: it executes a fresh synthetic operation and changes a visual-base pointer used by client reproduction. No historical seal should be copied to qualify a new run.

# Audit outcome and remaining limits

The first delivery's completion claim was premature. R1–R4 were corrected: strict verification, bound actual render inputs, pure comparison panes, and receipt-driven dataset-specific values. Codex retained 20 passing focused Python methods, two JS checks, browser/evidence-link checks, publication-failure evidence and custody receipts.

Authenticated Cursor's final verdict was **QUALIFIED_IN_DECLARED_SCOPE** for independent static review plus non-mutating runtime checks. Cursor verified HEAD, all 14 packet hashes, the 351-output publication and rejection of two retained invalid controls. It did not rerun live browser inspection, the Python/JS suites or adversarial mutation tests. See [the Cursor addendum](/ingestion/cursor-audit.md). Frozen older NOT_RUN: CHANNEL_UNAVAILABLE metadata remains generation-time history; the addendum is the current review status. Avoid hardcoding that status in future builds remains an advisory.

Whole-board equivalence/electrical correctness, schematic agreement, manufacturing acceptance and full crash/power-loss durability are not established. DB0 remains SHADOW_ONLY; ordered SQLite access, Rtree candidates and GEOS predicates retain their reference roles. Client native Processing/Storage ingestion and common catalogue design/implementation remain outside this delivered registration scope.

# Your review record and Step 2 recommendation

Copy this table into your own notes; keep observations and proposed changes separate from measured acceptance.

| Review item | Exact source or run | Your observation | Expected behavior | Proposed Step 2 requirement |
|---|---|---|---|---|
| Dataset/revision identity | | | | |
| Native/Gerber correspondence or disagreement | | | | |
| Object/source-byte retrieval | | | | |
| Physical/electrical/spatial relation | | | | |
| Writable/protected distinction | | | | |
| Unknown/unsupported state | | | | |
| Candidate/check/evidence tracing | | | | |
| Manual run, failure and publication | | | | |

Bring back one concrete task, such as selecting a pad/opening and retrieving its source occurrences, relevant copper, nearby constraints and permission boundaries. Use your observations to decide which identities, correspondence links, typed relations and evidence the common catalogue must provide first. This guide prepares that review; it does not adopt or implement a Step 2 design.
