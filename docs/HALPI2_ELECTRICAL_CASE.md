# HALPI2 named electrical case — 2026-10-15

Case: **HALPI2-native-intent-same-layer-v1**. This consolidates the existing realistic electrical experiment and adds only its missing named-net open control. It creates no new acceptance profile and does not change any prior result.

## Reference, scope and terminals

Pinned source revision: `3bef1d94520db0c866a79009a69102241ccd8521`. Native board SHA-256: `1d2c4ff9504c84b8deda14e4b38ca4dfb2778852924842ca307ee465720425ba`. Complete declared case: [halpi2_electrical_case_v1.json](../contracts/halpi2_electrical_case_v1.json). It lists all 64 source terminals, source UUID/pin, reference, position, layer, named net and all 240 required same-layer pairs.

Expected net labels and same-layer paths come from immutable native board pad assignments and native tracks/arcs/stored fills, independently of the Gerber copper under test. This is **native-source intent**, not independently established schematic/PCB agreement. The acquired schematic exists but is not required for this already declared native-intent case, and no schematic parity claim is made. Native and Gerber routes share GEOS; this is independent input data, not independent geometry engines.

Connectivity responsibility: each layer has a 16-terminal source-justified GND cluster, with all 120 unordered pairs required. Front: J22.1, J3.1, J13.1, J18.1, J6.1, J14.1, J26.1, J25.1, J17.1, J9.1, J1.9, J1.12, J1.18, J1.20, J21.1, J10.1. Back: J15.1, J4.1, J8.1, J24.1, J2.9, J2.12, J2.18, J2.20, J7.1, J12.1, J11.1, J20.1, J5.1, J23.1, J16.1, J19.1.

Separation responsibility: all 64 named pads, 32 per layer, must map to nominal source positions and exported `.P` attributes. No composed component containing these terminals may merge different native-source net labels. The manifest accounts for every terminal; repeated pin numbers are distinguished by source UUID and layer/position.

## Explicit boundaries for other terminals

Each layer has 18 GND pads, not 16. J1.2/J1.5 on F.Cu and J2.2/J2.5 on B.Cu have GND assignments but no source-justified path into the declared same-layer cluster. They remain mapped and participate in different-net separation checks; their GND continuity is **NOT_ESTABLISHED** by this case. No claim that they should be electrically isolated is made.

Each of the 14 non-GND nets has one terminal per layer, on J1 and J2 respectively: /HDMI.D2+, /HDMI.D2-, /HDMI.D1+, /HDMI.D1-, /HDMI.D0+, /HDMI.D0-, /HDMI.CLK+, /HDMI.CLK-, /HDMI.CEC, /HDMI.SCL, /UTILITY, /HDMI.SDA, /+5V_HDMI and /HDMI.HPD. Their cross-layer terminal-to-terminal connectivity remains NOT_ESTABLISHED. The exact pin-to-net records are in the manifest; no cross-layer path is silently counted as a passed same-layer pair. One unlabelled copper component on each layer also remains outside named-terminal electrical acceptance. Full-board electrical correctness, plating, process clearance and factory approval are not established.

## Positive and deliberate corruption evidence

The retained positive source exports already pass all 240 required pairs and different-net separation checks. Their original run is `out/v15_completion/run_20261014T154443_263864Z/`, final report SHA-256 `55a2d402af1b75b27e0aac6831e4f04203ced5f021bbead2853a24e4faf5af71`. Its native command logs, byte hashes and 64 terminal-to-export mappings are retained. This task verifies their bindings and reuses the exports; no fresh KiCad export is claimed.

The existing `new_bridge.gbr` is rechecked against native named intent and must report an electrical short. The previous `connection_cut.gbr` tested physical conductor continuity, so it is not substituted for a named terminal-to-terminal open test. The new targeted control clears a rectangular annulus around J22.1's native pad bounds, preserving its pad and nominal mapping while severing its GND connection. The expected 15 J22.1-to-cluster pairs must fail, and other GND pairs must stay intact; no new short may be introduced.

Reproduce within the pinned retained environment:

```sh
.venv/bin/python tools/halpi2_case.py
```

The script checks source custody, original report/code/reference/output hashes and source intent, recomposes only the two required copper layers, checks all positive mappings/pairs, writes the targeted fault to a new output directory, checks the original bridge and verifies all pre-task evidence hashes. It fails on any unmet obligation. It does not touch source assets or change parser support, tolerances or original acceptance gates.

## Actual decision and evidence

**Named HALPI2 case: PASS** within the responsibilities above. Both layers: 120/120 required GND pairs, 32/32 anchors and labelled terminal mappings, and no different-net merges. Named-open control: 15/15 expected J22.1 pair failures, all other 105 front-layer required pairs remain PASS, pad shape and all 32 anchors retained, no short. Existing bridge: FAIL as intended, merging source-labelled /HDMI.D2+, /HDMI.D2- and GND.

Authoritative consolidated result: `out/halpi2_case/run_20261014T163123_842427Z/result.json`. SHA-256 `66a7754d60ab64d53faca870cbdcf3d564164ec97688a56099b9cfbbe6a0a785`. Manifest SHA-256 `141338fd165f9b48f24a11373405aad7356988c0dce7095c812d3351c7a64102`. Execution log: `out/halpi2_case/execution_001.log`. Full regression log: `out/halpi2_case/regressions.log` (37 tests PASS, no tests changed). All 922 pre-task evidence files are unchanged, including the original 289; all original 106 output bindings and code/reference hashes verified. Complete anchors, nominal identities, positive pairs, bridge diagnostics and 15 failed named-open pairs appear in the consolidated result.

| Separate decision | Result |
|---|---|
| Original GlowStitch electrical obligation | NOT_ESTABLISHED; settled missing intent, not reinvestigated |
| Original aggregate V1.5 | NOT_ESTABLISHED; unchanged |
| Source-aware technical profile | PASS; preserved from 2e004b1, not replaced |
| HALPI2-native-intent-same-layer-v1 | PASS; complete declared 240-pair and 64-terminal separation/mapping case |
| Schematic agreement, cross-layer paths and whole-board electrical approval | NOT_ESTABLISHED |
| Independent Cursor review | NOT_RUN: CHANNEL_UNAVAILABLE |
| Manufacturing approval | NOT_ESTABLISHED |

No missing prerequisite remains inside this bounded case. For the affected connections outside it, a qualified cross-layer topology/plating check and/or schematic parity proof would be needed; they are not claimed as passed. No acquisition, parser expansion, pcb_Z, V2/V3, remote publication or unrelated lane was performed. Stop here.
