# Gerber viewer first implementation

The user authorized branch creation and implementation on 2026-11-21. Branch: `codex/gerber-viewer`. The functional authority is [the single canvas baseline](GERBER_VIEWER_LANE_BASELINE.md). This additive Mac slice does not change CAM stages, frozen assets or engineering acceptance.

## Launch and publish

From this checkout, run `tools/Start_Gerber_Viewer.command`. It prepares LaCie, builds and locally signs an app under `out/lacie_work/viewer/Gerber Viewer.app`, then opens it. All build caches, scratch, logs, sessions and screenshots remain under `out/lacie_work/viewer`. There is no internal fallback, installation, download, service or MCP connection.

Use **Open Gerber** for explicitly selected layers. The native host runs the existing project Python interpreter and this fixed publisher. Source files remain read-only. Unsupported imports retain their logs and leave the displayed revision intact.

A coding chat can publish actual slice export files without operating the UI:

```sh
.venv/bin/python -B tools/viewer_publish.py \
  --workspace "$PWD/out/lacie_work/viewer/session" \
  --gerber "/absolute/path/to/exported-copper.gbr" \
  --slice "slice description" --job "stable-job-identity"
```

Repeat `--gerber` for additional distinct X2 layers. Revisions and parents are managed automatically within a job. Changing job starts a separate revision lineage. The publisher always labels imports **Preview**.

## Canvas behavior

One SVG canvas provides drag pan, pointer-centered zoom, layer visibility, active-layer pick priority, direct filled-shape/stroke selection, overlap cycling, source record inspection, Previous/Current, Fit board and Fit change. Filled-shape picking respects holes. Inspector selections are published to `session/outbox/selection.json`, including job, revision, source identity, object and timestamp; the chat can read that file on its next tool call.

Incoming snapshots preserve the viewport unless Follow latest change is enabled. Added/removed **object artwork** is drawn in green/pink with a brief affected-bounds outline. This is not a computed boolean copper-area difference: an altered object can show its whole old and new outlines. Rendering is read-only; selection never edits copper.

## File ABI version 1

A session contains `current.json`, immutable content-addressed `snapshots/<sha256>.json`, and a latest-selection outbox. See `contracts/viewer/manifest_v1.schema.json` and `snapshot_v1.schema.json` for the wire fields.

Write and fsync the complete snapshot first, then atomically rename the manifest. The provided publisher serializes writers with an exclusive lock; a retained lock requires investigation rather than automatic takeover. It retains both current and previous payloads across reopening. Old snapshots and import failures remain available.

The native reader validates bounded payload sizes, SHA-256, revision/job parent linkage, unique IDs and layers, finite polygon paths, dimensions, board bounds and source-hash bindings. Paths are closed `M x y L x y ... Z` contours; multiple contours use even-odd fill. Coordinates are millimetres, X right and Y down. Source IDs begin with the matching source hash and a colon. A producer must retain stable object IDs for reliable comparison; the Gerber importer uses layer plus parser ordinal, which is not semantic identity across reordered commands.

The host polls the small manifest every 0.7 seconds; unchanged manifests do not trigger full parsing or redraw. New manifests are validated off the main thread. Last validated geometry stays displayed when an update fails. Hashes establish payload integrity, not independent engineering approval. `Verified` requires evidence references but remains the producer's scoped status; this viewer does not rerun or approve CAM gates. The web page has no network access or general filesystem/execution interface.

## Reuse and future models

ResearchWorkspace was inspected read-only. This implementation adapts its SwiftUI/native hosting pattern and its separation of provider identity from system-managed, helper-isolated or in-process execution. It imports no research content, stores, prompts, account data or model files. Its project-specific orchestration and research tools were not copied.

`ViewerCore` holds platform-independent snapshot validation. The current executable is Mac-only; an iOS app target and its document-transfer adapter remain future work. The Mac host uses SwiftUI/AppKit and a new WKWebView bridge. The package sets macOS 15 minimum for the renderer; actual builds were exercised only with the installed Swift 6.4 / macOS 27.2 SDK, not on macOS 15 hardware.

`ViewerModelProvider` provides a viewer-specific availability/explanation boundary. An Apple Foundation Models adapter is compiled conditionally and availability-checked on supported systems. Explanations use only the selected record and cannot issue edits. Model generation is not part of rendering or ABI publication. Local-model runtimes, acquisition, model capability routing and helper packaging are extension work, not implemented support. ResearchWorkspace's existing local-model routes should be individually verified before extraction.

## Supported input and limits

The importer reuses the existing maintained parser and geometry kernel without modifying them. The initial display profile requires explicit absolute millimetre 4.6 coordinates, X2 positive copper or negative-file-polarity soldermask openings, and positive plotting objects. Clear operations, ambiguous roles, duplicate layers, parser warnings and unsupported semantics reject the import. Missing parser-exposed object attributes stay empty; no pin/net meaning is inferred. Arcs and apertures become polygon display derivatives using the existing kernel; no new Gerber fidelity qualification is claimed.

Resource bounds: 64 MiB/source, 128 MiB/snapshot, 200,000 objects and 8,000,000 characters per path. The renderer currently redraws full snapshots, despite using affected bounds for navigation/highlighting; large-board spatial indexing, tiled/incremental drawing and performance qualification remain future work. Empty layers, board outlines, general clear-polarity composition and PDF import are not included in this slice.

## Verification and retained evidence

- `tools/Test_Gerber_Viewer.command` runs both scoped suites with external caches and retained logs. Its Python invocation uses the required `tools/Run_PCB_Tests.command` wrapper.
- `tools/Run_PCB_Tests.command -q tests/test_viewer_abi.py` exercises custody, holes, strict rejection, revision/affected bounds, corruption, writer locking and mask metadata.
- Swift tests exercise reader integrity, chains, source bindings, dimensions, malformed paths, holes, evidence requirements and symlink escape rejection.
- `--smoke-report <absolute LaCie directory>` on the launcher runs the native WebKit integration checks and writes `ui-smoke.json` and `viewer.png`. Use a dedicated session through `--workspace <absolute LaCie session>` for synthetic controls.
- External evidence root: `out/lacie_work/viewer/`. Initial failed build and test logs are retained. Observed-before preview source hashes were verified against the immutable asset manifest before import. Synthetic interaction controls are labeled separately and do not represent native PCB exports.

The first slice is a viewer and ABI implementation. Independent review is NOT_RUN: CHANNEL_UNAVAILABLE; owner review remains pending. Electrical/manufacturing acceptance is NOT_ESTABLISHED. iOS execution, model inference and large-board performance are not established by the current checks.
