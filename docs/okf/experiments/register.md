---
type: "Experiment Register"
title: "Experiments behind the runbooks"
description: "Durable procedures are tied to completed experiments and scoped historical evidence."
generated: {"by": "codex/pcb-cam-runbooks-v1", "at": "2026-10-16T14:43:36.762882+00:00"}
status: "stable"
tags: ["pcb", "cam", "runbook", "project-local"]
sources: [{"id": "implementation", "resource": "/references/sources.json", "title": "Version-bound implementation and source register"}, {"id": "source-1", "resource": "/references/source_text/docs--CLIENT_DATA_DEMO.txt", "title": "docs/CLIENT_DATA_DEMO.md"}, {"id": "source-2", "resource": "/references/source_text/docs--CLIENT_OPERATION_DECISION.txt", "title": "docs/CLIENT_OPERATION_DECISION.md"}, {"id": "source-3", "resource": "/references/source_text/docs--consolidation--CONSOLIDATION_DECISION.txt", "title": "docs/consolidation/CONSOLIDATION_DECISION.md"}]
---

# Promoted recipes

| Procedure | Existing experiment/evidence | Durable lesson |
| --- | --- | --- |
| Frozen asset preflight | `tools/preflight.py`, 70-entry manifest | Verify bytes and strict inventory before a baseline; preflight is bootstrap-only. |
| Combined dataset intake | Registration and offline verification receipt | Preserve distinct native/Gerber revisions, archive equality and unresolved differences. |
| Recorded workbench | Current client and consolidated visual receipts | Verify the actual pointed-to bundle; UI replay is not live execution. |
| Bounded client correction | R140.1 positive, open/bridge and rollback records | Artificial challenge is labelled; missing and added copper can fail for different reasons. |
| Native plotting | Coupon tool and prior client board export | Keep exact source hashes, CLI version/options and fresh output custody. |
| Native discovery/storage | Consolidation decision and receipts | Source objects, layer instances, physical components, permissions and persisted queries are distinct. |

[Exact evidence bindings](/references/experiments.json) contain current observed hashes of the retained receipts. The records are historical evidence, not results recomputed by this documentation task. [Source bindings](/references/sources.json) identify the code and documentation supporting each recipe.

# Instructions intentionally not promoted

- Ad hoc whole-board high-precision composition and fixed-output comparison scripts: expensive or overwrite-prone; no durable full-stack equivalence recipe established.
- One-off video-capture/voice/ffmpeg probes: the presentation narrative is durable, but these probes are not an established portable recording pipeline.
- Source labels as independent schematic truth, or parsing/loading as manufacturing correctness.
- Automatically copying historical seals, silently normalizing originals, merging pcb_Z wholesale, or routing VME-WREN through an importer that lacks an input option.

# Reconciliation with older prose

The older client demo document says native source is absent and some workbench docs hardcode older bundle paths. Those statements describe their historical checkpoints. Native source is now registered separately, and the runbooks resolve current pointers; the client operation itself still consumes original Gerbers. Older documents remain byte-preserved rather than rewritten as if they had used the new native source.
