# Evidence-linked visual workbench — delivery, 2026-10-15

**Implemented: a working, read-only visual case bundle backed by actual local Gerber geometry and stored validator evidence.** This is an additive delivery surface, not a new acceptance profile, parser, editor or strategic gate.

[Open interactive workbench](http://127.0.0.1:8765/run_20261014T171718_143371Z/index.html) while the optional loopback preview server is running. [Standalone HTML](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/visual/run_20261014T171718_143371Z/index.html) opens directly in a Mac browser without any server, upload or CDN. [Static overview PNG](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/visual/run_20261014T171718_143371Z/overview.png) and [canonical SVG overview](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/visual/run_20261014T171718_143371Z/overview.svg) provide quick review.

## Reproduce the complete canonical bundle

From this checkout:

```sh
.venv/bin/python tools/visual_report.py
```

The command checks the frozen source manifest and input/report/output hashes, creates a new timestamped out/visual/run_… directory, copies bound evidence snapshots and emits index.html, scene.json, overview.svg and build_receipt.json. It records the new location in out/visual/current.txt. It does not rerun native modification/export or replace any earlier evidence. An unavailable/mismatched input emits an explicit UNVERIFIED report and a nonzero exit, never a successful substitute case.

No new dependencies were installed. The optional PNG convenience renderer uses already available Pillow in the bundled document runtime; tools/visual_overview_png.py can rasterize the same constrained scene paths. The canonical command works without Pillow and includes the SVG image. A localhost server was used only for browser checks, bound to 127.0.0.1:8765 and serving out/visual; the standalone file remains the portable deliverable.

## Three guided case stories

1. **Synthetic aperture / V2:** select Computed candidate, Layer delta and Focus P1. The actual exported P1 is at X=20.05 mm. Opening outlines stay fixed while copper is added/removed around P1 and T1–T3. Toggle Operation roles versus Recorded source group: connected P2/T4 remain protected. Switch to Open control and select Connectivity: exposure remains PASS while required connectivity FAILS. Bridge, shifted-opening and protected-P3 controls are also available. Replay controls show the stored PLANNED/STAGED/EXPORTED/VALIDATED events and recorded COMMITTED outcome; the open transaction shows REJECTED and preserved source/previous-acceptance status. No animation executes an edit.
2. **HALPI2:** the default complete front layer has no 240-edge graph overlay. Select Open control and Expected same-layer GND pairs, or Focus J22.1. The pad remains visible within the clear annulus; its exact 15 expected failed GND relationships are listed. Each relationship can frame the terminal pair. Bridge control + Different-net separation highlights the actual added copper and reports /HDMI.D2+, /HDMI.D2- and GND from the stored short finding. All 64 terminal identities and both copper layers remain inspectable. Scope remains native-source same-layer, not schematic or whole-board agreement.
3. **GlowStitch:** inspect complete source artwork and its geometry preservation finding; then select Electrical intent is unavailable. The scene lists 80 unknown assignments, source-aware profile PASS, electrical NOT_ESTABLISHED and original aggregate V1.5 NOT_ESTABLISHED separately. Unknown never means a common net or documented no-connect.

## Scene, provenance and safety

Manifest: [visual_inputs_v1.json](../contracts/visual_inputs_v1.json). Authoritative visual bundle: `/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/visual/run_20261014T171718_143371Z`. Scene SHA-256 `0c00891594487154366757599fdc885353fd39cf8c4169e4b6aef9e13a6ccddb`; HTML SHA-256 `6e33c0cafdc0cca1d06888a36c43ecc59486be51cc9ba01cdfc100aeb4ea44be`. There are ten named states, 55 deduplicated display paths and 48 copied/bound evidence references. Primary input reports are the exact V2 500d070, HALPI2 a5c5af7, completion c0f997c and source-aware 2e004b1 results pinned by path and SHA-256 in that manifest.

Public-layer images come from the prior hash-qualified composed WKB artifacts. Fault images use the existing qualified Gerber compositor. Synthetic images use the unchanged V1 reader on actual V2 plots; the open state uses the real rejected transaction's staging Gerber and validation.json. The other deliberate synthetic controls reuse their frozen run's exported fault files. Native-source expected track/role annotations and terminal markers are labelled separately from observed copper. The supplied preview's archived JSON geometry and internal results are never used as acceptance evidence or production scene data.

One transform, Gerber (x,y) → display (x,−y), mm with KiCad Y down, is shared by both revisions, highlights and links. No independent best fitting occurs. Complete composed images, including holes, regions, local/global polarity semantics already qualified, are simplified **for display only** by 0.001 mm with topology preservation; SVG coordinates round to five decimals (at most 0.000005 mm per axis additional rounding). Stored measurements and decisions retain their original geometry/tolerances. Screen geometry is not a new metric or acceptance engine.

Paths are generated from constrained numeric polygons; external SVG/scripts are not imported. Source labels render as escaped text, and inline JSON escapes script-closing text. Content Security Policy denies external resources; all displayed data are embedded. Browser state is deep-frozen; pan, zoom, layers, selected findings and replay indices are separate presentation state. No Execute/Approve/Accept, board save, native edit or upload endpoint exists.

Generation checks source/report/artifact hashes. Browser startup checks the embedded scene checksum. Missing input, report mismatch or scene tampering produces STALE/UNVERIFIED and disables inspection controls rather than showing accepted geometry. This is an identified snapshot, not a live monitor of the repository: opening an old bundle does not claim a newer board is validated. Rerun the command to check current inputs. Checksums are integrity receipts, not signatures; deliberate coordinated alteration of HTML and its checksum is outside this viewer's authentication claim. Linked evidence snapshots are verified/copied at generation; no filesystem security bypass or live polling is attempted.

Case code_commit identifies the evidence-producing revision. Build metadata records its Git base, dirty flag and exact adapter/HTML/JS source hashes (the viewer was generated before its local implementation commit); the final local commit/review packet binds those same sources. A renderer failure never rewrites a backend decision.

## Checks actually run

| Check | Result |
|---|---|
| Existing 48 regressions + eight new scene/report tests | 56 PASS; out/visual/regressions_003.log |
| Case × state × compare/overlay/delta | 30 combinations PASS on final bundle |
| Shared viewBox, actual drag pan, zoom and layer toggles | PASS; evidence fingerprint unchanged |
| Synthetic correct exposure / broken connectivity | PASS presentation of distinct stored findings |
| HAL J22.1 exact 15 failed relationships and localized geometry | PASS |
| HAL named bridge and scoped statuses | PASS |
| Glow electrical unknown / aggregate / profile distinctions | PASS |
| Recorded COMMITTED and REJECTED replay outcomes | PASS; no live execution |
| Missing input / input hash mismatch / scene checksum corruption | Three expected UNVERIFIED UI outcomes, controls disabled |
| All pre-task local evidence | 1,078/1,078 SHA-256 unchanged, including every previously frozen set |
| Immutable assets and frozen code/contracts/tests | 70 assets verified; all pre-existing tracked implementation/acceptance files unchanged |

Detailed browser observations: `/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/visual/run_20261014T171718_143371Z/ui_checks.json`. New tests: tests/test_visual_scene.py. The first full-suite attempt exposed a test-driver naming collision (a Path named TestCase.run); it was fixed, its failed log is retained, and the final 56-test run passes. Initial visual iterations and explicit negative-generation artifacts remain separate and preserved.

**Browser coverage:** the final bundle was exercised through the Codex in-app browser using documented CUA DOM/native controls. Native Safari successfully opened the standalone second bundle, verified its embedded checksum and displayed the focused copper delta; the subsequent third bundle adds recorded transaction outcomes and was fully exercised in-app. Later Safari automation was interrupted by active user changes, so no final Safari-wide automated suite is claimed. Chromium and standalone WebKit automation executables were unavailable; none were installed. Reusable 30-combination locator sequence: web/ui_checks.js. Narrow-view operation was checked; the in-app viewport override did not yield a reliable desktop screenshot and was reset. Safari provided the desktop visual smoke check. No accessibility-compliance or all-browser certification is claimed.

## Continuation rule and boundary

AGENTS.md now requires an applicable visual case bundle with each meaningful engineering checkpoint: principal positive case, relevant failure, exact evidence/identity, scoped decision and remaining unknowns. Extend this same scene/viewer path for later authorized work rather than starting another frontend project or approval gate.

The viewer consumes the already recorded pcb_Z source-group and operation plan from V2; its adapter does not inspect/import pcb_Z. The existing V2 regression tests still exercise their previously authorized read-only helper adapter; no new legacy qualification, merger or SQLite work occurred. No new V2/V3 execution, parser support, dataset acquisition, other research lane, global configuration or remote publication occurred. Cursor stays NOT_RUN: CHANNEL_UNAVAILABLE. Manufacturing remains NOT_ESTABLISHED. Original V1.5 aggregate and all prior scoped results remain unchanged.


## Current client delivery — 2026-10-15

The earlier workbench described above remains historical. The current client bundle is `out/visual/client_20261015T053027_782777Z`, selected by `out/client_demo/current.txt`. It adds a nine-step project walkthrough over real client inspection and one bounded operation, alongside the existing coupon/public cases. The exact delivery, video, review status and verification limits are consolidated in [CLIENT_OPERATION_DECISION.md](CLIENT_OPERATION_DECISION.md); use [CLIENT_DATA_DEMO.md](CLIENT_DATA_DEMO.md) to run and present it.
