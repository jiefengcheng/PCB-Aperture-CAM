---
type: "Implementation Maintenance"
title: "Ingestion structure and publication safety maintenance"
description: "Refactored ingestion components, corrected generation review metadata and publication safety fixes with a new immutable replay."
generated: {"by": "codex/ingestion-maintenance", "at": "2026-10-17T20:18:17.722519+08:00"}
status: "stable"
tags: ["pcb", "ingestion", "maintenance"]
sources: [{"id": "implementation", "resource": "/references/sources.json", "title": "Current implementation bindings"}]
---

This page retains the original ingestion checkpoint. The subsequently authorized bounded common catalogue is described in [the current catalogue result](../catalogue/minimum-slice.md); earlier deferral statements here are historical.

# Changes and scope

The ingestion publisher and verifier now use independent file-binding and contract helpers, eliminating their circular import dependency. Publication orchestration and browser rendering are decomposed into smaller functions. Gerber parser support, pinned dependencies, frozen engineering contracts and common catalogue scope are unchanged.

| Component | Responsibility |
|---|---|
| `src/ingestion_files.py` | Contained paths, streaming hashes, file verification and JSON writing |
| `src/ingestion_contracts.py` | Registration schema, publication metadata and generation-time review status |
| `src/ingestion_registry.py` | Capture sources, stage declared replay/evidence, generate, verify and replace entry |
| `src/ingestion_verification.py` | Separate output/embedded-scene/dataset/ingestion consistency checks |
| `src/ingestion_visuals.py` | Receipt projection and hash-bound bounded display composition |
| `web/ingestion_views.js` | Separate measurements, receipt links, comparison panes, dataset navigation and review display |

# Fixed issues

The prior Cursor advisory is fixed for new ingestion publications. Generation metadata now says `NOT_RUN / NO_REVIEW_ATTACHED_TO_THIS_PUBLICATION / AT_GENERATION`; it makes no claim about channel availability. The ingestion view displays this structured value, and the verifier requires scene/receipt agreement. Later independent audit addenda remain separate; old frozen publications and historical case-review fields retain their recorded metadata.

A newly discovered publication hazard is also fixed: an output directory containing immutable bundle artifacts cannot be reused as the convenience-entry directory. An actual CLI control against the previous reviewed run rejects before changing its index. The producer captures and rechecks every declared implementation source so a changing renderer cannot receive a misleading final source hash. Failed entry replacement now removes temporary redirect files while preserving the prior entry.

# Execution evidence

New immutable publication: `out/ingestion/workbench/run-397f4c7683d24d44ae43537e5ad8dd28`. Its cases, geometry, native pipeline and dataset qualification records are identical to the previous reviewed publication; only presentation code/publication metadata changed. The new entry is available at http://127.0.0.1:8768/index.html while the local server is running.

25 focused Python methods pass (16 ingestion and nine replay/verifier regressions). Three JavaScript DOM checks pass. Added regressions cover explicit review status, rejection of invented review status, immutable destination protection, implementation drift and redirect replacement failure cleanup. The browser's five selections, case return, new status text and twelve bound HTTP evidence links verify. The source manifest, sealed intake, previous publication and 1,268 historical files verify. Exact previous reviewed sources were preserved as hash-matched snapshots from retained audit output and unchanged files.

Detailed artifacts are under `out/ingestion/maintenance/`: `build.json`, `publication.json`, `tests.log`, `js_checks.json`, `browser.json`, `links.json`, `immutable_destination_control.json`, `preservation.json`, `intake.json`, `source_snapshot.json` and the actual source snapshot directory.

# Independent review

The [new Cursor report](/references/maintenance-cursor.txt) returns **QUALIFIED_IN_DECLARED_SCOPE** with no actionable regressions. Cursor independently verified all 19 packet files, 18 source snapshots, new/prior publication verification and expected rejection of the original invalid controls. It independently confirmed unchanged case/geometry/pipeline/qualification data and matching generation review metadata. Cursor did not rerun tests that write temporary files or the browser UI. The [maintenance evidence summary](/references/maintenance.json) binds the actual run, report and verification artifacts. Common catalogue design and implementation remain deferred for user review.
