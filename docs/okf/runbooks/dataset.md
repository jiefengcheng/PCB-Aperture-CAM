---
type: "Playbook"
title: "Verify the combined client dataset"
description: "Use the original intake seal to verify both native and manufacturing sources offline."
generated: {"by": "codex/pcb-cam-runbooks-v1", "at": "2026-10-16T14:43:36.762882+00:00"}
status: "stable"
tags: ["pcb", "cam", "runbook", "project-local"]
sources: [{"id": "implementation", "resource": "/references/sources.json", "title": "Version-bound implementation and source register"}]
dataset_id: "client:vme-wren:20261016:v1"
dataset_seal: "7b1374e5eeb4cac943f3d7512a19da8a65a93212bd6bfa80c006930c85bc9e0e"
---

# Input

The registered intake is `dataset/vme-wren_20261016_v1/`. Its entry point is `index.md`, with source identities and provenance in `metadata/`. It contains one native board, all 42 supplied Gerber/drill/layer files, and the original ZIP. Packaging version 1.0.0 is separate from an unknown client CAD revision.

```sh
.venv/bin/python dataset/vme-wren_20261016_v1/scripts/verify.py \
  --expected-seal 7b1374e5eeb4cac943f3d7512a19da8a65a93212bd6bfa80c006930c85bc9e0e
```

This is offline and standard-library-only, and uses the project `.venv/bin/python`. Optional `--receipt` must point outside the sealed dataset, normally to a fresh `out/dataset_registration/` path. Exit 0/PASS covers byte hashes, strict inventory, emitted OKF metadata and links, archive equality and source bindings. It does not recompute geometry.

**Current revalidation note (2026-10-23):** the original external `SHA256SUMS` seal still matches, but the strict verifier currently reports `FAIL` because `.DS_Store` and `raw/.DS_Store` are unlisted. A read-only hard-link view of exactly the 70 signed entries passes the complete verifier, showing that the declared payload is intact while the original directory still fails exact inventory. Keep the stored directory unchanged and do not call the original package verified until its exact inventory is reconciled. See the [handoff revalidation record](/references/handoff-revalidation-20261023.json).

# Intake policy

The native and Gerber representations keep separate content identities. Preserve all original filenames and bytes, including duplicate files; a future deduplicated/normalized view is a separate derived artifact. Gerbers are in millimetres; original drill files remain inch-based. The metadata records coordinate frames and mapping requirements.

The prior R140.1 bottom-copper/mask ROI matches exactly. The prior L2GND ROI has twelve source-only flashes and roughly 5.98 mm² symmetric difference. Same-revision and whole-board equivalence remain NOT_ESTABLISHED. The mismatch is managed as data; neither representation is silently substituted for the other.

# Lifecycle

Keep `dataset/` Git-ignored. New raw revisions get new dedicated intake directories, manifests and external seals. Derived objects, databases, indexes, candidates and receipts go under `out/`, linked to the dataset ID and raw hashes. Existing client tools still read `external/sources/12_copper_layers_pcb_gbr`; registration did not redirect them or implement native client ingestion.
