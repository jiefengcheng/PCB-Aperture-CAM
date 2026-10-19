---
type: "Ingestion Baseline"
title: "Read-only dataset ingestion baseline"
description: "Retained source registration, provenance and bounded comparison before common catalogue design."
generated: {"by": "codex/ingestion-consolidation", "at": "2026-10-17T02:39:35.781952+08:00"}
status: "stable"
tags: ["pcb", "ingestion", "replay"]
sources: [{"id": "bindings", "resource": "/references/ingestion.json", "title": "Hash-bound registration and evidence"}]
---

This page retains the original ingestion checkpoint. The subsequently authorized bounded common catalogue is described in [the current catalogue result](../catalogue/minimum-slice.md); earlier deferral statements here are historical.

# Scope and provenance

Register the synthetic coupon, pinned GlowStitch, pinned HALPI2, retained Ucamco examples and client VME-WREN through one read-only workbench entry. Common object catalogue design and implementation remain deferred for user review. Registration does not execute a repair, extract a native object catalogue or establish engineering acceptance.

The user was told the KiCad board was automatically transformed from the client Gerbers. This is reported provenance, not verified conversion history. Conversion tool, recipe, intermediates and participation of a schematic or netlist are unknown. Native net assignments and Gerber X2 names remain source annotations; agreement from a shared origin is not independent electrical-intent confirmation.

# Qualification

Client source board SHA-256: f3d5d3e60f2a7fae25d9d1b1741335c8765409405833e32a0948a83c984b1b6d. Retained receipts and input hashes are in the [registration bindings](/references/ingestion.json). Each representation retains a separate content hash. Dataset packaging version 1.0.0 is not a design revision.

| Evidence | Recorded scope | Boundary |
|---|---|---|
| R140.1 | B.Cu/B.Mask symmetric difference zero in [115.8, -231.8, 118.1, -230.45] Gerber mm | Local correspondence only |
| Edge.Cuts | 0.00001722001200857463 mm² symmetric difference | Small difference retained, not exact byte/geometry equality |
| L2GND | 12 source-only 0.8 mm flashes; 5.975804925704194 mm² difference within [170.6, -294.3, 185.6, -290.7] | Cause unknown; confirmed divergence |
| Drills | 4,894 PTH hits, two slots, eight NPTH hits | 0.003 mm position/endpoints and 0.002 mm tool tolerance |

Incomplete textual full-layer claims are not promoted. Global revision equivalence, whole-board/cross-layer electrical correctness, schematic agreement and manufacturing acceptance remain NOT_ESTABLISHED. Registration can succeed with explicitly partial qualification. Historical engineering outcomes are REPLAY, not recomputed acceptance.

# Coordinates and identity

Derived records use millimetres. Native KiCad X right/Y down maps to Gerber X right/Y up with (x,y) → (x,-y), reversible with the same transform for these recorded exports. Both views use the same source origin; no best fitting, independent recentering or mirror is applied. Display flips Gerber Y again. Display paths simplify at 0.001 mm and round coordinates to five decimals; they are not measurement authority.

Source layer names are retained: Bottom Layer → B.Cu, Bottom Solder → B.Mask, Top Layer → F.Cu, Top Solder → F.Mask, Edge_Cuts → Edge.Cuts. L2GND remains the named internal comparison layer; no filename alone establishes net intent. Original Excellon files remain inch-based. Historical normalized drill receipts use 25.4 mm/inch and retain format warnings and stated tolerances; source bytes are never rewritten.

Dataset IDs, source content hashes, registration manifest hashes, immutable run identities and convenience URLs have different roles. Content revisions are not merged merely because a local correspondence is evidenced. This is preparation using existing contracts, not a new common object model.

# Component boundaries

The existing implemented contract retains SQLite ordered access, libspatialindex/Rtree candidate retrieval and GEOS exact predicates. DB0 remains SHADOW_ONLY. Six historical parity scopes do not qualify this client ingestion. Native nominal geometry, source intent, physical relations, permissions and independently validated exported results remain separate. Client native Processing/Storage ingestion is NOT_IMPLEMENTED; existing recorded Processing/Storage datasets remain available.

Failed verification/publication must retain the previous stable entry. Staging plus rename does not establish power-loss durability, full crash recovery or atomicity across databases and files. No database querying, parser support, dependency lock, source fixture or frozen acceptance changes are authorized here.

# Reproduction and review

Run from the checkout:

```sh
.venv/bin/python tools/ingestion.py
python3 -m http.server 8768 --bind 127.0.0.1 --directory out/ingestion/workbench
```

Open http://127.0.0.1:8768/index.html. Select Datasets / Ingestion and a dataset. Inspect provenance, qualification, source hashes and bound evidence. Client comparison panes show only their own historical source or native replot in shared coordinates. A separate difference-only pane uses pink for source-only geometry and green for native-only geometry. Use Inspect recorded case / controls to return to the established scene. The original is already aligned; +0.35 mm is an artificial challenge. Open-control shading represents missing copper, bridge-control shading added copper.

The builder prints its immutable run path. Verify it:

```sh
.venv/bin/python tools/ingestion.py --verify out/ingestion/workbench/RUN_DIRECTORY
.venv/bin/python -m unittest tests.test_ingestion_registry -v
```

RUN_DIRECTORY is the exact printed run name, not a literal directory. The v2 verifier requires a PASS receipt, complete output inventory, index/scene/registry, embedded-scene equality, registry/dataset bindings, bound evidence and receipt-derived qualification. Legacy v1 receipts are explicitly unqualified. These checks establish local consistency, not engineering acceptance or authenticity. Source verification occurs before and after the build. The local registration JSON and publication receipt are local OKF extensions, outside the sealed dataset. Existing runbooks and historical receipts remain retained. No independent Cursor channel is available: NOT_RUN: CHANNEL_UNAVAILABLE.

# Corrected completion audit

The previous completion claim for `out/ingestion/workbench/run-7d3e42070aee4089b2e4c5d10a553c82` was premature. Its [original audit](/references/completion-audit.json) and the reproduced failure evidence are preserved. Requirements 6, 7 and 9 were incomplete. The [new remediation audit](/references/completion-audit-v2.json) records the corrected run and finding-by-finding evidence.

| Finding | Correction | Verification |
|---|---|---|
| R1 false verification | Publication schema v2 requires PASS status, index/scene/registry, exact inventory, embedded scene equality, registry and evidence/measurement bindings; legacy v1 is unqualified | Actual CLI rejects both original empty controls, missing files/evidence, scene/registry mismatch and rehashed invented measurements |
| R2 unchecked render inputs | Render from registered sealed source copies and retained native plots matched by receipt hashes; verify before and after composition; record exact inputs per view | Removed flash, missing input and input drift during composition reject; full publication passes |
| R3 misleading overlays | Pure source and native panes, plus a separate difference-only pane | Browser/DOM and screenshot inspection; source-only paths occur only in delta |
| R4 literal measurements | Project each selected dataset's named verified receipts into structured qualification records and render their values with bound links | Changed receipt values propagate; missing presentation is NOT_AVAILABLE; five-dataset browser checks show no leakage |

Twenty Python methods pass: eleven ingestion methods (two existing plus nine new) and nine existing replay/verifier regressions. Two JavaScript DOM contract checks separately cover pane isolation and changed/absent measurements. This is focused verification, not a full project-suite or historical engineering re-execution claim.

The actual CLI fail-before-publication preserves the prior entry. Twelve HTTP evidence links and displayed receipt values verify. The sealed client intake, 70 frozen assets, 1,268 historical files, twelve prior seal bindings, rejected run outputs and original review artifacts remain intact. New publication verification is local consistency, not authorship, independent electrical intent or manufacturing acceptance. Independent Cursor review remains NOT_RUN: CHANNEL_UNAVAILABLE.

The 12 source-only L2GND flashes form six joined difference shapes after composition. They are visible in the source pane and separate pink delta; absent native copper stays absent in the native pane.

Corrected immutable run: `out/ingestion/workbench/run-05888c57424f4db48bd9821fc8324b36`. The v2 publication receipt records exact implementation/runtime hashes, render inputs and output hashes. Status: **corrected delivery locally verified**. Common catalogue design and implementation remain deferred for user review.
