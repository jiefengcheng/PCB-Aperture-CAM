---
type: "Playbook"
title: "Start with source custody and the tested runtime"
description: "Check recipe applicability, Python dependencies and immutable assets before running a baseline."
generated: {"by": "codex/pcb-cam-runbooks-v1", "at": "2026-10-16T14:43:36.762882+00:00"}
status: "stable"
tags: ["pcb", "cam", "runbook", "project-local"]
sources: [{"id": "implementation", "resource": "/references/sources.json", "title": "Version-bound implementation and source register"}, {"id": "source-1", "resource": "/references/source_text/docs--V2_DECISION.txt", "title": "docs/V2_DECISION.md"}]
---

# Applicability

All commands below run from the project root. First read the current `AGENTS.md`; the runbook documents existing capabilities and does not grant new scope. Client registration, synthetic execution, native discovery, validation and visual replay have different evidentiary roles.

```sh
.venv/bin/python docs/okf/references/verify_runbooks.py
.venv/bin/python tools/preflight.py
.venv/bin/python -c "import sys, gerbonara, shapely; print(sys.version); print(gerbonara.__version__, shapely.__version__)"
```

The preflight performs strict manifest inventory, including unexpected files, and verifies frozen coupon coordinates. Its success is **PASS_BOOTSTRAP_ONLY**, with 70 expected assets at this snapshot. Fields such as `native_candidate_export: NOT_RUN` describe this preflight's scope; they do not overwrite historical V1/V2 decisions. No baseline run should proceed after an asset mismatch.

# Runtime

Use the checkout's existing `.venv/bin/python` for project tools and its pinned `requirements.lock.txt`. Dataset hash verification uses plain Python 3.9+ instead. Report missing dependencies; don't silently substitute another environment or install/upgrade packages as part of a replay.

The offline dataset verifier is standard-library-only and can also be run with the project `.venv/bin/python`; keep all repository Python commands in this runbook on that environment.

The tested local development CLI is:

```sh
export KICAD_RUN_FROM_BUILD_DIR=1
PCB_CAM_KICAD_CLI=/Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli
"$PCB_CAM_KICAD_CLI" version
```

Last confirmed CLI version is 10.99.0. Capture the actual version in every fresh native export. A different build requires a new comparison receipt; version text alone does not prove identical plotting behavior.

# Optional regression reproduction

When an implementation change or explicit verification task calls for the established suite, retain a fresh log under `out/`:

```sh
mkdir -p out/runbook_checks
pcb_cam_checks_dir="$(mktemp -d "$PWD/out/runbook_checks/regressions_XXXXXXXX")"
.venv/bin/python -m unittest discover -s tests -v > "$pcb_cam_checks_dir/regressions.log" 2>&1
```

Use a fresh log name for subsequent runs. The last historical 114-test result is evidence for its own code revision, not a current result from this documentation task.
