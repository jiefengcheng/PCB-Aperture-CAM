---
type: "Playbook"
title: "Run the existing discovery and storage pipeline"
description: "Reproduce native inventory, persistence and context queries on the previously qualified workloads."
generated: {"by": "codex/pcb-cam-runbooks-v1", "at": "2026-10-16T14:43:36.762882+00:00"}
status: "stable"
tags: ["pcb", "cam", "runbook", "project-local"]
sources: [{"id": "implementation", "resource": "/references/sources.json", "title": "Version-bound implementation and source register"}, {"id": "source-1", "resource": "/references/source_text/docs--consolidation--RUN_CONSOLIDATED_DEMO.txt", "title": "docs/consolidation/RUN_CONSOLIDATED_DEMO.md"}, {"id": "source-2", "resource": "/references/source_text/docs--consolidation--CONSOLIDATION_DECISION.txt", "title": "docs/consolidation/CONSOLIDATION_DECISION.md"}, {"id": "source-3", "resource": "/references/source_text/docs--consolidation--IMPLEMENTED_DATA_CONTRACT.txt", "title": "docs/consolidation/IMPLEMENTED_DATA_CONTRACT.md"}]
---

# Discovery and storage only

After [preflight](/runbooks/start.md), the existing producer can create source-bound native inventory, layer geometry, physical relationships, a persisted catalogue and query/context receipts:

```sh
.venv/bin/python tools/consolidation_pipeline.py
```

The default uses the frozen synthetic-before board. Previously exercised optional inputs are:

```sh
.venv/bin/python tools/consolidation_pipeline.py --legacy --public
```

`--legacy` reads the authorized pcb_Z package's pinned native test board; `--public` uses already acquired GlowStitch/HALPI2 sources. It does not download new datasets. Inputs are read-only; a new `out/consolidation/pipeline_*/` contains `catalog/`, dataset records and `receipt.json`. Inspect completeness/unsupported records and source identities, not just process exit.

The client VME-WREN native board is **not** wired into this producer. Registering it in `dataset/` does not make these commands ingest it. No client database/import success is claimed by this runbook.

An optional `--v2-result /absolute/path/to/result.json` attaches an already accepted synthetic candidate after its source/result hash check. That option does not authorize arbitrary candidate promotion.

# Broader consolidated reproduction

The established full demonstration includes discovery/persistence, approved synthetic execution, KiCad export, independent validation, native graph shadow comparisons, regressions, benchmarks and visual generation:

```sh
.venv/bin/python tools/consolidation_demo.py
```

It takes several minutes and requires the pinned PCB-owned native shadow binary or records its unavailability, existing public/legacy inputs, prior-history custody file, KiCad and the Node runtime. Read the actual producer result and per-stage logs under the new `out/consolidation/demo_*/` directory. Success is RECORDED_FOR_INSPECTION, distinct from reviewed acceptance. Actual native comparisons retain SHADOW_ONLY status.

This full command creates a new synthetic operation and updates `out/consolidation/current_visual.txt`. Its new visual bundle does not inherit the prior consolidation seal. This affects the [client replay builder's base prerequisite](/runbooks/client-case.md); don't run the two recipes as an unchecked chain.

# Review and boundaries

Open the named visual through [workbench review](/runbooks/workbench.md). Processing explains source inventory and omissions. Storage explains revision-bound records, persistence and query witnesses. Cases explains the synthetic/public recorded outcomes. SQLite/reference and native shadow results keep their recorded roles; general native reassembly and full legacy merger remain unestablished.

A producer run is not a new engineering acceptance decision. Preserve exact receipts, unsupported status, source hashes and historical stores. The original aggregate V1.5/GlowStitch intent, whole-board manufacturing acceptance and independent Cursor review keep their existing limitations.
