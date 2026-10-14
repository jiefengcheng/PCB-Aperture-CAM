# V1.5 read-only qualification decision — 2026-10-14

**Realistic design validation: NOT_ESTABLISHED.** Acquisition, provenance inventory and native no-edit CLI compatibility are established for the two selected boards. The frozen V1 checker does not generalize to these inputs. V1's synthetic coupon technical PASS at `36eab151a0bf00ea57eef09f1dc425c4b5603e50` remains unchanged. Independent Cursor review: NOT_RUN / CHANNEL_UNAVAILABLE. No V2/V3 or repair is authorized by this decision.

## Sources and selection

| Source | Frozen revision / origin | Declared license | Inventory / selection |
|---|---|---|---|
| GlowStitch | `1c5d867ece6a5c38ac5ad7067cac352a5734655a`; https://github.com/sjpiper145/GlowStitch | README declares CC BY-SA 4.0; no separate license file found | Seven ZIP archives contain seven native `.kicad_pcb` boards and render images. No native project, schematic, supplied Gerber or drill file found. Selected `x1 LED Strips Files.zip` → `x1 GlowStitch LED Panelised KiCAD Design File.kicad_pcb` |
| HALPI2-HDMI-FPC | `3bef1d94520db0c866a79009a69102241ccd8521`; https://github.com/hatlabs/HALPI2-HDMI-FPC | README declares CERN-OHL-S v2; no separate license file found | Native board, project, schematic, custom rules, footprint library and render images. No supplied Gerber/drill set found. Selected unpanelized `HALPI2-HDMI-FPC.kicad_pcb` |
| Ucamco | https://www.ucamco.com/en/gerber/downloads → official Gerber Layer Format Test Files ZIP; archive hash in custody manifest | No license declaration found in archive; rights beyond local authorized evaluation NOT_ESTABLISHED | 11 Gerber examples, eight PNG references and a brief readme. Compatibility only, not correct-repair examples |

The Git source checkouts and acquired ZIP remain unchanged. Complete byte inventories, archive member hashes, license declaration lines, selected-board hashes and exact CLI binary hash are retained in `contracts/public_sources.json` and `out/v1_5/*/qualification.json`. External inputs are Git-ignored; derived files remain under `out/v1_5/`. Upstream scripts were not executed. No external accounts, remote writes or uploads were used.

## Native compatibility and no-edit baseline

Both selected boards load and export Gerbers through the supplied **KiCad 10.99.0** CLI, with `KICAD_RUN_FROM_BUILD_DIR=1`. Nine layers were explicitly requested: F/B copper, mask, silkscreen and paste, plus Edge.Cuts. Empty layers are inventoried as empty, not evidence of physical features. Drill exports are retained as supplementary artifacts; drill semantics are outside frozen V1 acceptance.

Each copied native board was loaded/exported twice without editing. Source board bytes remained unchanged, and normalized plotting primitive fingerprints (including units, file role and file polarity, excluding timestamps/object attributes) matched across the exports. This establishes repeated no-edit CLI output, **not** native save/reload round-trip equivalence or independently verified geometry. GUI opening and native save/reload are NOT_RUN.

An initial fingerprint implementation mistakenly used Region repr memory addresses. A subsequent correction exposed Gerbonara 1.6.3's uninitialized Region.attrs field. The final fingerprint uses explicit plotting primitive fields; prior reports are preserved under each source's output folder. A regression test verifies stable fingerprints across independent Region parses. Attribute preservation is not claimed.

Supplementary native DRC receipts:

- GlowStitch: 680 violations (320 errors, 360 warnings), zero unconnected items. The selected board declares only the unnamed net. These tool diagnostics are not an independently established design-error list; footprint copper graphics and absent net intent require interpretation. No repairs were attempted.
- HALPI2: nine warnings, zero unconnected items. The schematic and named nets exist, but no independent electrical oracle was qualified. DRC does not establish impedance, bend reliability, registration or fabrication acceptance.

## Frozen V1 importer and parser coverage

| Input | Frozen V1 outcome | Limit |
|---|---|---|
| GlowStitch Edge.Cuts | Import subset PASS | Outline import only; no manufacturing or electrical acceptance |
| GlowStitch F.Cu | NOT_ESTABLISHED | First unsupported multiline extended construct; copper includes macros/graphics/regions and public identities beyond the coupon |
| GlowStitch F.Mask | NOT_ESTABLISHED | Region geometry fails the qualified polygon validity check; no geometry repair or assumption about coverlay semantics |
| HALPI2 F.Cu / F.Mask | NOT_ESTABLISHED | Multiline extended constructs outside frozen coverage |
| HALPI2 Edge.Cuts | NOT_ESTABLISHED | `G75` arc-mode operation outside frozen coverage |
| Ucamco official examples | Nine load/expand without warnings; two NOT_ESTABLISHED | `Block_with_different_orientations.gbr` and `Nested_blocks.gbr`: aperture-block commands ignored with warnings, then undefined apertures cause parse errors |

Raw Gerbonara parsing/primitive expansion of all nine exported native layers succeeds without warnings; that broader parser result does not qualify frozen V1 geometry operations. Official example PNGs are retained, but rendering/oracle comparison is NOT_RUN. All 11 official examples exceed the frozen lexical subset; none is promoted to V1 geometry acceptance.

GlowStitch's upstream README discusses soldermask/coverlay manufacturing, but no separate physical coverlay specification or registration policy was found in the acquired file inventory. KiCad F.Mask is not automatically a qualified flex-coverlay model. HALPI2's rules/schematic are available inputs, not independently verified authority for every acceptance claim. No coupon aperture, 0.15 mm rim, P1–P4 intent or 0.20 mm clearance rule was transplanted onto either public board.

## Gate decision and stop line

- A0: source custody PASS; license declarations recorded as found. Ucamco redistribution/license scope remains NOT_ESTABLISHED.
- A1: native CLI load/export and repeated primitive output PASS for selected boards. GUI/native-save round-trip NOT_RUN.
- A2: inventories established; full relevant frozen V1 geometry support NOT_ESTABLISHED.
- A3: realistic electrical, coverlay, registration, impedance and manufacturing correctness NOT_ESTABLISHED.
- A4: local evidence and frozen review packet prepared; independent Cursor review NOT_RUN / CHANNEL_UNAVAILABLE.

Close this V1.5 qualification pass with the above compatibility gaps. A future authorized compatibility milestone would need complete relevant Gerber geometry semantics and a qualified independent intent/policy for a selected public case before claiming realistic validation. Public asset loading does not trigger V2 automated editing or V3 planning.

## Reproduction and evidence

`tools/qualify_public.py` inventories pinned local Git sources, copies/extracts to `out/v1_5/`, performs no-edit exports, records DRC and applies the frozen V1 importer. `tools/probe_ucamco.py` inventories/probes the acquired official ZIP. Neither tool acquires network data or edits external sources. Qualification refuses to overwrite an existing frozen report. The review packet retains exact executed commands; the reports retain argv, exit codes, warnings, tool hashes and exported file hashes.

Run `.venv/bin/python -m unittest discover -s tests -v` against the retained acquisition and export evidence. Missing evidence fails the qualification tests; tests do not silently skip or fetch replacements. See `out/v1_5/unittest.log` and `out/v1_5/cursor_review_packet.json`.


## Charter alignment — 2026-10-14 (documentation only)

[PROJECT_CHARTER.md](PROJECT_CHARTER.md) is the reconciled proposed strategic reference. [CHARTER_INTEGRATION.md](CHARTER_INTEGRATION.md) records the conflicts and proposed corrections; [CHARTER_EVIDENCE_AUDIT.md](CHARTER_EVIDENCE_AUDIT.md) checks retained evidence and records current verification limits. Frozen V1/V1.5 results, operational isolation and acceptance contracts remain unchanged. Strategic CH-G1–CH-G6 labels are separate from existing milestone gates. [NEXT_GATE_PROPOSAL.md](NEXT_GATE_PROPOSAL.md) awaits explicit user approval; no implementation follows from this pointer. Cursor governance review remains NOT_RUN / CHANNEL_UNAVAILABLE unless a direct authenticated channel is verified.


## Bounded V1.5 completion evidence — 2026-10-14

The adopted completion handoff (DECISIONS D-012) supersedes prior intermediate stops for this task only. [V1_5_COMPLETION_DECISION.md](V1_5_COMPLETION_DECISION.md) records a working raw-Gerber geometry/preservation profile for both complete nine-layer selections and the qualified FC-1 example. Full required electrical acceptance remains NOT_ESTABLISHED because GlowStitch lacks qualified net intent. Historical V1/V1.5/FC-1 conclusions and contracts are unchanged; the new evidence extends them. Current authority is in AGENTS and DECISIONS; earlier FC-1-only text describes the earlier authorization. Cursor remains NOT_RUN / CHANNEL_UNAVAILABLE. No pcb_Z, V2/V3, manufacturing approval or remote publication.
