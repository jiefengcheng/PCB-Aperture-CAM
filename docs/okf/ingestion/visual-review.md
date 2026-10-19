---
type: "review-guide"
title: "Dataset review layout"
summary: "Workbench navigation: Datasets / Ingestion, Storage & indexes, Cases; shared dataset views with explicit evidence availability."
generated: {"by": "codex/workbench-navigation", "at": "2026-10-17T23:15:51.605028+08:00"}
status: "stable"
tags: ["pcb", "ingestion", "visual-review"]
sources: [{"id": "navigation", "resource": "/references/navigation-layout.json", "title": "Workbench navigation publication and checks"}, {"id": "evidence", "resource": "/references/common-layout.json", "title": "Prior shared dataset layout publication and checks"}]
---

This page retains the original ingestion checkpoint. The subsequently authorized bounded common catalogue is described in [the current catalogue result](../catalogue/minimum-slice.md); earlier deferral statements here are historical.

# Follow the workbench

Use the **+** beside Registered dataset to [restore a known sealed dataset directory](/ingestion/directory-intake.md) through the local ingestion server. This preserves the same review layout.

The top navigation follows **Datasets / Ingestion → Storage & indexes → Cases**. Datasets / Ingestion is the default landing view. There is no separate Processing tab.

- **Datasets / Ingestion:** preserved inputs, registration, recorded input stages and input findings. Under Stored on disk, expand **Recorded input stages · custody and extraction** for actual source-custody and inventory receipts linked by exact source hash. Missing links remain explicit.
- **Storage & indexes:** select a retained native source revision to inspect indexing, exact relationships, persistence, catalog queries and operation-context receipts, followed by saved query examples and stored objects. The initial receipt is persistence. These are recorded results. The browser does not execute a new pipeline or board query. Historical native revisions without a direct dataset-registration hash link retain their input-stage receipts in a collapsed disclosure here.
- **Cases:** inspect the recorded operation, correction and rejection controls.

The [navigation delivery evidence](/references/navigation-layout.json) records the current publication and checks. The historical receipts and source bindings are unchanged. Dataset registration availability and retained native revision availability remain distinct.

# Read the dataset screen

Every registered dataset uses the same two primary tabs: **Stored on disk** and **Input findings**. The first identifies the durable artifacts. The second shows that dataset's recorded qualification, comparisons and unknowns at the level actually available. Forward/back buttons connect the views and bring the new context into view. This is a presentation convention, not the deferred common object catalogue.

Open **Datasets / Ingestion → Client VME-WREN**. The preceding shared-layout publication remains in the [shared-layout evidence summary](/references/common-layout.json); the current publication is in the navigation delivery evidence above. The [prior client narrative evidence](/references/narrative-review.json) remains preserved. A direct link can use `index.html#dataset=client%3Avme-wren%3A20261016%3Av1` inside that run. Older open tabs remain pinned to older publications.

**Stored on disk** uses the same five layers and artifact inspectors across datasets. The client retains its sealed-package details and explicit unimplemented board/query statuses. Other datasets show verified registered file references, file registration and saved review records. Package metadata is not invented when no package seal is linked. Native materializations are displayed only when a registered source hash matches a retained pipeline source hash. Historical query samples are distinguished from an unlinked reopen receipt.

Archive members and similarly named datasets are not automatically equated. In particular, the file-level GlowStitch registration contains source archives; it does not directly hash-match the historical extracted native board. Its native rows therefore say **Not linked**, not **Not implemented**. This does not negate the separately retained native pipeline run, inspectable under Storage & indexes. Ucamco remains a parser-fixture collection, not a qualified board.

All datasets retain both tabs when comparison geometry, drill results or native links are absent. **Not available / Not recorded / Not linked** describe evidence availability. They are not geometry failures, zero measurements or engineering acceptance.

**Input findings** adapts to the selected dataset. Without comparison views, it shows the registered qualification, intent/provenance and bound evidence links; no empty comparison panes or zero differences are fabricated. Recorded native inventory coverage is available only for source-hash-matched revisions. For the client, the same view retains:

- **Matches and discrepancies:** inspect the selected R140.1 copper/mask match or L2GND mismatch. The latter has twelve source-only flashes. These compare supplied Gerbers with a replot from the supplied KiCad board. Source and replot stay separate; differences occupy a third pane.
- **Drill correspondence:** a collapsed detail retains measured positions, tools, slots and tolerances.
- **Qualification & unknowns:** expand the input conclusions and unresolved conversion history, schematic/netlist participation, whole-board equivalence and independent electrical intent.

Correction and pad-move visualizations remain in **Cases**. They are not duplicated inside Input findings. Their recorded geometry and outcomes are unchanged.

Receipts, exact values, source hashes, scope, provenance and generation review metadata remain under **Evidence & technical details**, collapsed by default. All comparison outcomes are historical REPLAY, not a new engineering acceptance.

# What this delivery means

The completed registration preserves and verifies files, registers five dataset groups, and brings their retained evidence into one read-only workbench. Stored on disk identifies the persisted artifacts; Input findings qualifies the correspondence between the supplied client representations. General client native object ingestion and the common catalogue remain unimplemented/deferred. The existing operation replay remains separately available in Cases.

The shared interface changes no source datasets, geometry, measured results, engineering verdicts or recorded pipeline runs. Its scene and registry remain byte-identical to the previous publication. Display measurements continue to come from bound receipts.

# Check and reproduce

From the project checkout:

```sh
.venv/bin/python tools/ingestion.py
```

This publishes a new presentation revision using verified registered inputs and historical receipts. It does not run a new CAM operation. Run the focused presentation checks in an existing Node runtime with `tests/js/ingestion_views.test.cjs` and `tests/js/pipeline_navigation.test.cjs`; no installation is required by this guide. The [manual execution guide](/ingestion/manual-review.md) explains how actual pipeline and operation executions differ.

The current presentation checks cover both tabs on all five registered datasets, missing-data states without cross-dataset leakage, source-hash matching instead of name matching, forward/back navigation with the new context visible, three comparison choices, drill and qualification disclosures, retained Cases access, dataset selection, actual HTTP artifact links and publication verification. A prior Cursor audit applies to its own frozen source/run; it is not an independent audit of this presentation change. The client layout and its reuse across all five datasets are preserved. The current delivery reorders the top navigation, removes Processing and places its stage receipts in the relevant views. Navigation, all five dataset groups, all five retained native revisions, twenty-one storage-stage inspectors and the source-bound case-to-storage link were checked in the browser. Eighteen focused JavaScript checks and publication verification pass.
