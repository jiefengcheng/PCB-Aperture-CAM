---
type: "Implementation Handoff"
title: "Complete ingestion consolidation before common catalogue design"
description: "Carry the agreed client and public dataset consolidation into a new chat, preserving frozen evidence and deferring the next catalogue implementation stage."
generated: {"by": "codex/pcb-cam-ingestion-handoff", "at": "2026-10-16T18:25:07+00:00"}
status: "draft"
tags: ["pcb", "cam", "ingestion", "handoff", "okf"]
sources: [{"id": "existing-contract", "resource": "/references/source_text/docs--consolidation--IMPLEMENTED_DATA_CONTRACT.txt", "title": "Existing implemented data contract snapshot"}, {"id": "recorded-evidence", "resource": "/references/experiments.json", "title": "Historical evidence bindings"}]
---

This page retains the original ingestion checkpoint. The subsequently authorized bounded common catalogue is described in [the current catalogue result](../catalogue/minimum-slice.md); earlier deferral statements here are historical.

# User objective and authorization

On 2026-10-17 Asia/Singapore, the user requested: "Nice. let start a new thread and finish all above discussed tasks. I will based on the results to further clarify step 2 Define the common catalogue and to engage in its implementation afterward."

Finish the ingestion baseline, adopted Google Open Knowledge Format organization, and connected review in the existing workbench. Register the previously experimented datasets through the same entry. The user will review these results before defining and implementing the common object catalogue. Do not turn this task into that deferred implementation stage.

Codex remains sole coordinator. Routine authorized local work does not require repeated permission. Preserve checkout isolation, immutable assets and external sources, all historical evidence and frozen V1/V1.5/V2 decisions. No uploads, remote writes, new public acquisitions, parser expansion, new repair family, full pcb_Z merger, shared-core changes or V3. Independent Cursor review requires a verified direct channel; otherwise record NOT_RUN: CHANNEL_UNAVAILABLE and continue the authorized local work without claiming independent review.

# Current checkout and custody

Project: `/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff`.

At handoff, HEAD is `19ff47204d429b93fdac21d3b1a94ed3462b3629`. Pending files include `.gitignore`, `docs/DATASETS.md`, `docs/okf/` and user file `chatgpt_memo.md`. Preserve unrelated user changes; do not add that memo to task commits without inspecting applicability and authorization. This handoff and its navigation updates are new documentation only.

Read current `AGENTS.md`, `docs/CODEX_HANDOFF.md`, `docs/ACCEPTANCE.md`, `docs/CURSOR_PROTOCOL.md`, `docs/PROVENANCE.md` and `docs/STATUS.md` before changing code. Recheck actual files, pointers and hashes; this document identifies evidence locations and is not a substitute for current verification.

# Required completion

1. **Provenance and authority:** Record that the user was told the KiCad board was automatically transformed from the client Gerbers. This is reported provenance, not a verified conversion history. The tool, recipe, intermediate inputs and participation of any schematic or netlist remain unknown. Do not assert that the board was independently designed or that conversion definitely did or did not occur. Native net assignments and Gerber X2 labels require explicit provenance; agreement between representations sharing an origin is not independent electrical-intent confirmation.
2. **Qualification:** Consolidate hash-bound local matches, drill correspondence, L2GND discrepancy, scope, tolerances and unknowns in a short readable record plus machine-readable evidence references. Do not promote textual or incomplete whole-layer claims into established equivalence. Full-board equivalence is not a prerequisite for read-only registration.
3. **Coordinate and identity conventions:** Document the conventions already used: millimetres for derived records, native and Gerber origins/Y directions, reversible coordinate mapping, layer mapping and display transforms. Original drills retain inch units; normalized derivatives record their conversion. Preserve distinct source content revisions and evidenced correspondence links. This is preparation using existing contracts, not implementation of a new common object catalogue.
4. **Reuse boundaries:** Reconcile with `docs/consolidation/IMPLEMENTED_DATA_CONTRACT.md`, `CONSOLIDATION_DECISION.md`, `NATIVE_QUALIFICATION.md` and `docs/V2_DECISION.md`. SQLite ordered queries, libspatialindex/Rtree candidates and GEOS predicates remain reference paths. DB0 remains SHADOW_ONLY; six historical parity receipts do not qualify this client's ingestion. Preserve independent exported-result acceptance. Failed import/index publication must retain the previous published revision; directory rename does not establish power-loss durability or full crash recovery.
5. **OKF closeout:** Extend the existing `docs/okf/` bundle with one ingestion baseline entry linking provenance, qualification, conventions, component decisions, durable runbooks, visual cases and evidence. Follow the existing Google OKF v0.2 profile. Machine manifests, hashes and runners are documented local extensions. Put updates outside the sealed dataset rather than modifying its existing seal. Record current limitations and a requirement-by-requirement completion audit.
6. **Stable ingestion entry:** Provide one durable, local entry to register/select datasets, verify sources and inspect their provenance, qualification and evidence. Reuse the existing workbench with a permanent Datasets / Ingestion entry and reproducible entry command/URL. Keep the browser read-only; commands may produce new project-local derived bundles. Distinguish a stable convenience entry from immutable run/revision identities. Use staging and preserve the prior published entry on failure. Do not add autonomous database querying or object-catalogue implementation under the name of registration.
7. **Visual review:** Connect the new ingestion records to the existing scene/viewer, rather than a separate application. The review must identify the dataset, show verified correspondence, show discrepancies and explain unknowns. Include the client native/Gerber comparison within its recorded scope, relevant existing operation/control links, source hashes and evidence. Existing client Cases works; client native Processing/Storage ingestion is not implemented and must not be implied. New bundles should preserve prior recorded views and clearly label REPLAY. Verify the rendered page and its evidence links, not only producer exit codes.
8. **Previously experimented datasets:** The same registration/navigation contract must support the synthetic coupon, pinned GlowStitch, pinned HALPI2, existing Ucamco examples and the client intake. Reuse their actual retained sources/results and scopes. Native boards, Gerbers and electrical intent are optional capabilities, never fabricated to fill a schema. Preserve GlowStitch unknown intent and original aggregate V1.5 NOT_ESTABLISHED, bounded HALPI2 qualification, Ucamco parser-compatibility purpose, and synthetic independent policy/intent. Do not copy large public source checkouts into new bundles or acquire new sources.
9. **Durable reproduction and completion:** Provide the stable entry path, exact commands, versions, hashes, concise walkthrough, results and limits. Exercise missing/stale evidence and failed publication where applicable. Verify immutable input/history custody and all new registration/visual bindings. Run only checks appropriate to this work; no unrelated experiments or new repair executions. A source-consistency check does not reconfirm historical engineering acceptance. Stop after this consolidation result for the user's common-catalogue clarification.

# Evidence locations to inspect

The existing combined intake is `dataset/vme-wren_20261016_v1/`, ID `client:vme-wren:20261016:v1`, packaging version `1.0.0`. It contains one KiCad board, 39 Gerbers, two drill files, `layerfunction.txt`, original ZIP, metadata and copied prior comparison receipts. `dataset/` is Git-ignored. Dataset registration has not redirected the current operation tools from `external/sources/12_copper_layers_pcb_gbr`.

- Dataset external seal, SHA-256 of `SHA256SUMS`: `7b1374e5eeb4cac943f3d7512a19da8a65a93212bd6bfa80c006930c85bc9e0e`.
- Native board SHA-256: `f3d5d3e60f2a7fae25d9d1b1741335c8765409405833e32a0948a83c984b1b6d`.
- Prior local R140.1 comparison ROI: `[115.8, -231.8, 118.1, -230.45]` Gerber mm; recorded B.Cu and B.Mask symmetric difference is zero.
- Prior L2GND comparison ROI: `[170.6, -294.3, 185.6, -290.7]`; twelve source-only 0.8-mm flashes and approximately 5.975805 mm² symmetric difference. Cause remains unknown.
- Drill receipt: 4,894 PTH hits, two PTH slots and eight NPTH hits within recorded tolerances.
- Prior native replot artifacts and comparison tools: `out/native_gerber_crosscheck/vme-wren_kicad-10.99.0/`. Ad hoc scripts have fixed historical paths and may overwrite outputs; do not blindly rerun them as durable recipes.
- Existing architecture/decisions: `docs/consolidation/IMPLEMENTED_DATA_CONTRACT.md`, `CONSOLIDATION_DECISION.md`, `NATIVE_QUALIFICATION.md`, `FINAL_EVIDENCE.json`, `docs/V2_DECISION.md`, `docs/CLIENT_OPERATION_DECISION.md`.
- Current client and consolidation bundles: resolve `out/client_demo/current.txt` and `out/consolidation/current_visual.txt`. Inspect actual contents before reuse.
- Existing viewer/build path: `tools/visual_report.py`, `tools/client_visual_demo.py`, `src/pipeline_scene.py`, `web/workbench.html`, `web/workbench.js`, `web/pipeline_views.js`.
- Existing inventory/persistence: `src/source_locators.py`, `src/native_inventory.py`, `src/revision_catalog.py`, `src/catalog_selection.py`, `src/spatial_context.py`, `src/native_graph_adapter.py`, `tools/consolidation_pipeline.py`. Reuse these boundaries without defining a new client object catalogue yet.
- Source and evidence bindings: [project source register](/references/sources.json), [experiment register](/references/experiments.json), [durable recipes](/runbooks/index.md).

# Important existing presentation constraints

The client visual builder reads the consolidated-base pointer and copies `consolidation_seal.json` as historical context. A new full consolidated demo changes that pointer to an unsealed bundle; do not fabricate or copy an old seal to satisfy a new bundle. Inspect the existing [client reproduction recipe](/runbooks/client-case.md) before generating a new visual.

The original client bottom-copper region was already aligned. The +0.35-mm offset is an artificial challenge, not a genuine client defect. The accepted local candidate restores the original bytes. Open-control red shading is missing copper; bridge-control highlighting marks added offending copper. The top's 304 zero-width interpolation warnings retain strict-import limitations. Client native object ingestion, full-stack electrical correctness, schematic agreement and manufacturing acceptance remain unestablished.

# Starting checks

These existing checks verify recorded structure and custody, not engineering outcomes:

```sh
.venv/bin/python docs/okf/references/verify_runbooks.py
.venv/bin/python dataset/vme-wren_20261016_v1/scripts/verify.py \
  --expected-seal 7b1374e5eeb4cac943f3d7512a19da8a65a93212bd6bfa80c006930c85bc9e0e
```

# Status and continuation context

The preceding paragraph records the original 2026-10-16 handoff status. The nine ingestion requirements were subsequently addressed in the local OKF baseline and corrected completion audit; common-catalogue work was later explicitly authorized and is linked from [the catalogue result](../catalogue/minimum-slice.md). The ORG-map G3 display-path fidelity result is documented in [the current geometry fidelity entry](org-svg-fidelity.md). Current source applicability and package integrity must be rechecked before relying on any historical PASS: see [the latest revalidation](../references/handoff-revalidation-20261023.json). The current review also has a separate pending human visual judgment in the G22 record; do not fill it in for the user.

In a new chat attached to this checkout, use: "Read docs/okf/ingestion/handoff.md and complete its agreed ingestion consolidation scope end to end. Keep Define the common catalogue and its implementation deferred for my review afterward."
