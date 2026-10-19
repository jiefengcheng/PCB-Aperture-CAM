---
type: "Playbook"
title: "Export native artwork into a fresh output directory"
description: "Reproduce native KiCad plotting while retaining source hashes and export options."
generated: {"by": "codex/pcb-cam-runbooks-v1", "at": "2026-10-16T14:43:36.762882+00:00"}
status: "stable"
tags: ["pcb", "cam", "runbook", "project-local"]
sources: [{"id": "implementation", "resource": "/references/sources.json", "title": "Version-bound implementation and source register"}, {"id": "source-1", "resource": "/references/source_text/docs--V2_DECISION.txt", "title": "docs/V2_DECISION.md"}]
historical_client_comparison: "references/experiments.json"
---

# Coupon baseline

After [asset preflight](/runbooks/start.md), the existing coupon tool copies frozen native sources into a new timestamped output directory and records CLI commands, DRC diagnostics and hashes:

```sh
export KICAD_RUN_FROM_BUILD_DIR=1
.venv/bin/python tools/export_native.py --case both \
  --cli /Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli
```

Inspect `out/native_exports/<new-run>/run_receipt.json`; success is EXPORT_COMPLETED_GEOMETRY_UNVALIDATED. DRC is supplementary. Plotting alone is not independent CAM acceptance.

# Registered client board export

First [verify the registered input](/runbooks/dataset.md). Use a fresh output directory and the same development-build environment. This is a durable native-export recipe, not a full native-versus-Gerber equivalence verdict:

```sh
(
set -eu
export KICAD_RUN_FROM_BUILD_DIR=1
PCB_CAM_KICAD_CLI=/Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli
mkdir -p out/native_exports
pcb_cam_export_dir="$(mktemp -d "$PWD/out/native_exports/client_XXXXXXXX")"
"$PCB_CAM_KICAD_CLI" version > "$pcb_cam_export_dir/version.txt"
"$PCB_CAM_KICAD_CLI" pcb export gerbers --board-plot-params \
  --output "$pcb_cam_export_dir/gerbers" \
  dataset/vme-wren_20261016_v1/raw/kicad/vme-wren.kicad_pcb \
  > "$pcb_cam_export_dir/gerbers.log" 2>&1
"$PCB_CAM_KICAD_CLI" pcb export drill --excellon-separate-th \
  --output "$pcb_cam_export_dir/drill" \
  dataset/vme-wren_20261016_v1/raw/kicad/vme-wren.kicad_pcb \
  > "$pcb_cam_export_dir/drill.log" 2>&1
printf '%s\n' "$pcb_cam_export_dir"
)
```

Retain source/CLI/output hashes, the exact command arguments, version, logs and source hash after execution in a new receipt under that output directory. Never overwrite or re-label the earlier October 16 comparison outputs.

# Findings that affect interpretation

The prior default export reproduced R140.1 B.Cu/mask locally and exposed an L2GND divergence. `--check-zones` creates a different filled-zone diagnostic; it did not reconcile L2GND and must be separately named and hashed. Do not add it to a baseline export silently.

The current detailed compositor is qualified for bounded regions; a whole internal-pour comparison became impractically slow. The ad hoc prior audit scripts have fixed paths/outputs and are not promoted as durable rerun entry points. Reproduction of geometry measurements requires explicit new parameters and fresh output custody, rather than invoking those scripts blindly. Existing [dataset evidence](/runbooks/dataset.md) remains readable without a new native export.
