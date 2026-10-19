# Consolidation decision — bounded result established

The existing executor, maintained source/catalog pipeline, native graph shadow
and three-view workbench now form one inspectable, reproducible path. This closes
the consolidation mandate within its declared scopes. It is not universal PCB
validation, manufacturing approval, full pcb_Z integration, or native replacement
of all storage/index components.

Implementation commits: 6a66857357476de2b1321f8da7d1b63cbec76a23 and
6396170aed607d3dab73b740849f51b46f9af384. The latter changes source trace labels
and retained raw-code metadata only. The final demonstration was generated from
clean 6396170 source. The later documentation seal is separate; see the
append-only consolidation_seal.json in the bundle. Historical dirty builds and
frozen execution revision 500d070 retain their original metadata.

## Authoritative result

- Aggregate: `out/consolidation/demo_20261014T203427_875185Z/result.json`; SHA-256 `e9013ef9222ba2f4c23c3f28fe8ada7fb160928f6ad929966adba24aed78ca87`.
- Pipeline receipt: `out/consolidation/pipeline_20261014T203542_446846Z/receipt.json`.
- Catalog-admitted actual V2 execution: `out/v2/catalog_20261014T203534_954553Z/result.json`;
  SHA-256 `b08ed73abbcaa4b3d8de66a11b8bc8d4c27ecfc6254dadb3b2f7388cdfc9b1eb`.
- Workbench: `out/visual/run_20261014T203700_885147Z/index.html`.
- Scene SHA-256: `e4fc6a676aa0a359f55da0ef0f4c3d339ff34aad3416b59294b7157f60b2218f`.
- Benchmark report: `out/consolidation/bench_20261014T203734_660667Z/result.json`.
- Exact path/hash inventory: FINAL_EVIDENCE.json.

All 15 aggregate stages exited 0. The final regression run passed 110 methods;
the initial frozen baseline passed 56. Six actual native layer/materialization
comparisons report PARITY_PASS. All 70 immutable asset files and all 1,268
pre-consolidation evidence files match their baseline hashes. The accepted native
candidate is byte-identical to the original qualified V2 candidate and replay:
`e09c7459d49ad7499c824ee2ea840189153593f2f9777207b150e602631e6ca9`.
Fresh pinned KiCad exports and unchanged independent validators passed; deliberate
Gerber corruptions, executor failures and pre-publication rollback controls remain
retained. No public board is modified.

The browser evidence covers 30 case/state/mode combinations, nine replay events
with 82 control-cycle checks, 18 resizes with verified actual dimensions and nine
synchronized pointer pans. These bind the 6a66857 bundle; unchanged replay/drawing
logic is identified in the audit. Final 6396170 targeted checks bind corrected
N1/raw-code-1 labels, PLANNED stability, context/permissions, spatial witnesses,
native/reference switching, public terminal retrieval and source-to-case links.
All 66 finding pages were checked against their bound JSON-pointer excerpts;
30 trace occurrences retain their source names and raw codes.

## Discovery and engineering scope

| Dataset | Source objects | Layer instances | Geometry available | Queried native pads |
|---|---:|---:|---:|---:|
| synthetic_before | 17 | 17 | 14 | 4 |
| legacy_scale | 26026 | 25840 | 23225 | 0 |
| synthetic_candidate | 17 | 17 | 14 | 4 |
| GlowStitch | 8571 | 8729 | 8082 | 80 |
| HALPI2-HDMI-FPC | 673 | 929 | 490 | 64 |

Unsupported records retain exact source locators and typed reasons; available
geometry is not complete engineering coverage. Native back-footprint transforms,
custom primitives and unqualified/degenerate shapes remain explicit. Source
containers, layer instances, physical components and PCB_GROUP are separate.
P1's N1 physical context contains six objects; only P1/T1–T3 are writable. P2/T4
remain protected, and container dependencies grant no permission.

Recorded diagnostic queries include identity/ordered/property/layer lookup,
exact regions, a 2-mm proximity halo, component bbox-area/width-height-aspect
filtering, reopened contexts, all 80 GlowStitch pads and HALPI2 J22.1. GlowStitch's
80 assignments remain unknown. J22.1 links to its 15 bounded expected
relationships; the retained open control breaks all 15. General selective native
reassembly remains unsupported; diagnostic bundles preserve original artifacts.

## Component decisions and measurements

Artifact/revision catalog: ADOPT. SQLite ordered queries, native libspatialindex
Rtree candidates and GEOS predicates: KEEP_REFERENCE. Actual pinned gfs DB0
reads: SHADOW_ONLY. Custom C++ B-tree/R-tree: DEFER because no separate usable
implementation was established in the admitted source. Full reuse details and
API/build/lifetime qualifications are in REUSE_AND_COMPONENT_DECISIONS.md and
NATIVE_QUALIFICATION.md.

| Graph workload / layer | Seeds | Reference median ms | Native API median ms |
|---|---:|---:|---:|
| synthetic_before / F.Cu | 9 | 0.098 | 5.751 |
| legacy_scale / F.Cu | 16 | 0.272 | 68.109 |
| synthetic_candidate / F.Cu | 9 | 0.090 | 5.673 |
| GlowStitch / F.Cu | 16 | 0.125 | 5.797 |
| HALPI2-HDMI-FPC / B.Cu | 16 | 0.133 | 6.028 |
| HALPI2-HDMI-FPC / F.Cu | 16 | 0.153 | 6.117 |

Measurements use Apple M5 Max / 18 logical CPUs / arm64 macOS 27.2, three
repetitions and uncontrolled OS caches. Native API measurements include manifest,
process/reopen, translation and transfer costs; reference reads use a built
in-memory adjacency. They do not establish a C++ speed advantage. Extraction,
geometry, bulk build, persistence, queries, serialization, storage and isolated
child memory are separately retained in the full report. Browser DOM timing is
recorded separately and is not GPU paint performance. The measured overhead
supports keeping DB0 in shadow mode.

## Preserved limits and stop line

Original aggregate V1.5 and GlowStitch electrical intent remain NOT_ESTABLISHED;
the source-aware and bounded HALPI2 positive results keep their existing scope.
Directory/transaction publication does not establish power-loss durability,
full crash recovery or shared-core concurrent snapshot guarantees. Native license
qualification remains NOT_ESTABLISHED for redistribution. Cursor review remains
NOT_RUN: CHANNEL_UNAVAILABLE; CURSOR_REVIEW_PACKET.md prepares a frozen read-only
review without simulating one or requesting a relay.

No unresolved conflict requires changing frozen acceptance. The mandate permits
explicit native/export capability gaps, and those fallbacks are used honestly.
The current gate closes here. No V3, new repair family, public-board automatic
editing, manufacturing release, remote publication, shared-core mutation or
historical-store migration begins from this decision.

Run `.venv/bin/python tools/consolidation_demo.py` from this checkout to produce a
new demonstration. See RUN_CONSOLIDATED_DEMO.md and the requirement-by-requirement
CONSOLIDATION_ACCEPTANCE_AUDIT.md. A producer success is evidence for inspection;
new runs do not inherit this bundle's seal or acceptance automatically.

Offline artifact scope: scene/viewer are embedded with no external resource
loaders. Runtime checks used localhost; direct-file launch is NOT_RUN because
the browser URL security policy blocked file://. No bypass was attempted.
