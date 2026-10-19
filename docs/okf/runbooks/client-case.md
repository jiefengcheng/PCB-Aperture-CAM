---
type: "Playbook"
title: "Reproduce the bounded R140.1 client case"
description: "Create a fresh local operation with controls, then bind it into the existing workbench."
generated: {"by": "codex/pcb-cam-runbooks-v1", "at": "2026-10-16T14:43:36.762882+00:00"}
status: "stable"
tags: ["pcb", "cam", "runbook", "project-local"]
sources: [{"id": "implementation", "resource": "/references/sources.json", "title": "Version-bound implementation and source register"}, {"id": "source-1", "resource": "/references/source_text/docs--CLIENT_DATA_DEMO.txt", "title": "docs/CLIENT_DATA_DEMO.md"}, {"id": "source-2", "resource": "/references/source_text/docs--CLIENT_OPERATION_DECISION.txt", "title": "docs/CLIENT_OPERATION_DECISION.md"}]
---

# Preconditions and effects

Use [start and custody](/runbooks/start.md) first. This recipe creates new derived candidates, controls, receipts and visual output under `out/`, and updates `out/client_operation/current.txt` and `out/client_demo/current.txt`. Existing frozen inputs and historical results remain their own evidence.

Actual source inputs are the 42 files in `external/sources/12_copper_layers_pcb_gbr`; the new registered dataset has not replaced that tool input. Before reproduction, compare those source hashes to the registered manufacturing inventory. The operation uses qualified bottom copper and mask only, with an explicit demo policy.

The visual builder also requires a sealed consolidated base and a prior operation result:

```sh
python3 - <<'PYCODE'
from pathlib import Path
import hashlib, json, subprocess
manifest = json.loads(Path('dataset/vme-wren_20261016_v1/metadata/manifest.json').read_text())
for row in manifest['files']:
    if row['path'].startswith('raw/gerber/'):
        original = Path('external/sources/12_copper_layers_pcb_gbr') / row['path'][len('raw/gerber/'):]
        assert hashlib.sha256(original.read_bytes()).hexdigest() == row['sha256'], 'client source mismatch'
base = Path(Path('out/consolidation/current_visual.txt').read_text().strip())
assert (base/'scene.json').is_file(), 'base scene missing'
assert (base/'consolidation_seal.json').is_file(), 'client builder requires a retained sealed base'
subprocess.run(['.venv/bin/python', 'tools/verify_visual_bundle.py', str(base)], check=True)
print(base)
PYCODE
```

A new consolidated demo updates that pointer to a new unsealed bundle. Do not manufacture/copy a historical seal to satisfy this prerequisite; retain the valid prior base identity or stop client visual regeneration until an applicable base is supplied.

# Execute and build the replay

```sh
.venv/bin/python tools/client_operation_run.py
.venv/bin/python tools/client_visual_demo.py
```

Inspect each command's exit status before continuing. The first creates a new `out/client_operation/run_*/`; the second creates `out/visual/client_*/`. Visual generation may take over a minute and substantial memory; missing/stale inputs should stop it. Then use [workbench verification](/runbooks/workbench.md).

# Expected engineering record

Read the exact run's `contract.json`, `result.json`, `accepted/validation.json`, control reports and `rollback.json`. The original is aligned; the +0.35 mm challenge is deliberate. Nine local candidate checks pass. Open control fails connection; bridge control fails separation and protected-object preservation; over-limit admission rejects before staging. Rejected attempts preserve accepted bytes.

The client visual builder hash-checks all source files, the contract, candidate and control evidence before displaying them. New generated output must earn its own verification; historical acceptance does not transfer by naming it current. Manufacturing rules, whole-board/cross-layer connectivity and independent Cursor review remain outside the recorded result.
