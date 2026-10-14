# V1.5 completion decision — 2026-10-14

**The raw-Gerber geometry/preservation path is working: PASS for the declared two-board, nine-layer profile. Overall required V1.5 electrical validation remains NOT_ESTABLISHED.** The remaining GlowStitch net-reference gap is a data/intent blocker, not another parser-implementation stop. No manufacturing approval, cross-layer acceptance or independent review is inferred.

Authorizing instruction: `CODEX_V1_5_COMPLETION_HANDOFF.md`, adopted in DECISIONS D-012. The finite required set was frozen before implementation in [V1_5_COMPLETION_MATRIX.md](V1_5_COMPLETION_MATRIX.md); its SHA is bound into the run and the original freeze record is mirrored in `contracts/v1_5_completion_profile.json`. Original V1, V1.5 qualification and FC-1 history remain unchanged. This task extends their evidence; it does not retroactively turn the earlier NOT_ESTABLISHED results into passes.

Authoritative end-to-end run: `out/v15_completion/run_20261014T154443_263864Z/`. `final_report.json`, `decision.md`, full regression log, native command logs, native source copies, complete exported files, composed WKB images and fault copies are retained there. Raw reports and earlier failed attempts remain intact. The one-command execution receipt is `out/v15_completion/execution_007.log`.

## Acceptance results

| Dimension | Result | Evidence / exact meaning |
|---|---|---|
| Frozen synthetic V1 regression | PASS | Original positive, schema, observed-before comparison and 13 deliberate-corruption expectations rerun against retained native paired exports; P1 stays 20.05 mm |
| Frozen FC-1 oracle regression | PASS | Original eight oracle tests and source/hash obligations preserved |
| Production reader/compositor vs FC-1 | PASS | Actual raw official Gerber bytes; shape difference 0.0000247202084551 mm², boundary distance 0.000000998469 mm, zero analytic-grid mismatches; 12 components/four holes |
| GlowStitch whole declared layer set | PASS | All nine layers accounted for, including empty B layers; fresh repeat and historical composed geometry preserved; all 80 native pads associated and shape/location checked |
| HALPI2 whole declared layer set | PASS | All nine layers accounted for; fresh repeat/historical geometry preserved; all 64 native pads checked, 32 per copper layer |
| Nominal exposure | PASS | Complete front copper/opening intersection shape preserved. Areas: GlowStitch 2959.597613702491 mm², HALPI2 38.38676541881919 mm². No coupon rim rule or coverlay process rule applied |
| Physical source conductor continuity | PASS | Source-declared straight-conductor endpoint relations preserved: GlowStitch 80 front; HALPI2 89 front/41 back. Empty source sets are explicitly inventoried |
| Scoped named electrical intent | HALPI2 PASS; GlowStitch NOT_ESTABLISHED | HALPI2: 120 source-justified same-layer GND terminal pairs per layer and no merge of source-labelled different nets. This is not full-job/cross-layer connectivity. GlowStitch has only unnamed net 0 and no schematic in the acquired inventory |
| Clearance | Measurements established where named intent is qualified; process acceptance NOT_ESTABLISHED | HALPI2 minimum spacing between source-labelled different-net components: 0.1004428167 mm front / 0.100499 mm back. One component per HAL layer remains unlabelled. GlowStitch different-net spacing cannot be assigned without net intent. No factory threshold is invented |
| Scope and challenge fixtures | PASS within declared preservation checks | Five valid-but-faulty Gerbers per board fail their intended fixed-opening/exposure, physical connection, bridge, protected-geometry or polarity/order check. One unknown-syntax file per board is refused; refusal is NOT_ESTABLISHED geometry, not successful interpretation |
| New semantics / false acceptance | PASS for tested profile | Raw-byte AB/transform/scale/reset/overlap controls, equivalent encodings, rounded rectangle macro, local-clear/global-clear order, legal cut-ins and invalid winding/crossing rejection; independent source mapping controls |
| Original source/history integrity | PASS | 70/70 immutable assets, pinned external inventories/commits, native source-copy hashes, unchanged pinned KiCad binary, frozen code/contracts and 289 pre-task local evidence files verified |
| Complete regression suite | PASS | 31 unittest methods, including existing V1/public qualification/FC-1 tests and 12 new reader/reference tests; no skipped successful input substituted |
| Cursor review | NOT_RUN / CHANNEL_UNAVAILABLE | No verified authenticated direct channel; frozen packet prepared. No human relay |
| Factory/manufacturing acceptance | NOT_ESTABLISHED | No process approval, impedance, bend reliability, coverlay/material, plating or production signoff |

**Overall is NOT_ESTABLISHED because required named-net evidence is missing for GlowStitch; it is not reduced to a geometry-only PASS after evaluation.** The geometry subprofile is separately named and its constituent checks are explicit. Read [V1_5_REFERENCE_QUALIFICATION.md](V1_5_REFERENCE_QUALIFICATION.md) for independent-reference boundaries. Shared GEOS and same-compositor replay are not described as independent engines. Semantic analytic controls and native source data are separate references.

## Implemented capability and limits

`src/gerber_image.py` extends pinned Gerbonara 1.6.3 locally, without modifying the installed library or frozen V1 parser. It composes raw graphical objects in order, handles non-nested aperture blocks and aperture mirror/rotation/scale, macro-local transparency, circular strokes/arcs, and valid cut-in contours. Unknown commands, unconsumed bytes, missing units/formats, unsupported transforms and invalid contours are rejected. No `make_valid` or `buffer(0)` geometry repair is used.

Profile: explicit millimeters, absolute 2.6/4.6 coordinates, rotations within ±360°, uniform scale in `(0,1]`, supported plotting primitives and non-nested AB. SAG is bounded at 1e-6 mm; the predeclared geometric budget remains 1e-5 mm. FC-1's original tolerances remain unchanged. No expected polygons, sample filenames or known-file hashes enter the implementation under test. They appear only in references/custody and test drivers.

`native_reference.py` reads independently supplied native coordinates, pad shapes, nets, tracks/arcs and stored filled zones through sexpdata. Repeated blank GlowStitch references and HALPI2's optional third X2 pin-function field are handled explicitly. Matching does not best-fit copper/mask or infer intended nets from candidate components. Physical baseline separation challenges are kept distinct from electrical short checks.

Other Ucamco cases are optional and do not block the declared boards. Of ten remaining examples, five compose under the restricted profile, with independent exact conformance/rendering still unestablished. Five remain unsupported: nested blocks, two other coordinate formats and two step-repeat macro examples. The report preserves these statuses; it does not report 11/11 correctly interpreted.

Fresh native DRC diagnostics remain visible: GlowStitch reports 320 errors and 360 warnings; HALPI2 reports nine warnings; both report zero unconnected items. These are supplementary diagnostics, not project-defect labels or factory acceptance.

Additive project-local dependencies: sexpdata 1.0.2 for native source references and pypdf 6.1.1 for specification text inspection. Existing lock/dependencies and KiCad build were not upgraded. The first explicit specification pin is Ucamco 2026.05, URL/hash recorded in `contracts/completion_format_reference.json`; no prior pinned PDF was present. The PDF is local evidence, not published.

## Reproduction and actual stop

With this checkout's pinned external sources, retained oracle/regression evidence and project-local venv (the command does not acquire replacements):

```sh
.venv/bin/python -m pip install -r requirements-completion.txt
.venv/bin/python -u -m src.completion_run
```

The local pre-implementation freeze receipt is required at `out/v15_completion/required_matrix_freeze.json`. If restoring the retained environment elsewhere, copy the identical tracked `contracts/v1_5_completion_profile.json` there; do not generate a new hash after evaluation.

The command checks custody and the frozen matrix, creates a new timestamped run, exports both selected boards twice with the pinned KiCad CLI, composes all declared layers, evaluates native anchors/exposure/physical and scoped net checks, creates fault files, runs the complete regression suite, probes optional examples and emits `report.json`, `final_report.json` and `decision.md`. Failed native exports are fatal to that run; no stale successful output is reused. Prior run directories and reports are not overwritten.

The completion matrix, source/manifest/reference hashes, tool versions, exact argv/stdout/stderr, native board copies, output hashes and test receipts bind the result. Full raw evidence stays Git-ignored/local. Process completion/exit 0 does not itself establish technical PASS; read the machine-readable overall and profile statuses. No remote write/upload occurred.

Remaining external datum: a qualified GlowStitch terminal-to-net intent map or schematic for the exact pinned board's 80 pads, identifying expected same-layer connections and separations. The exact source IDs, pad numbers and nominal coordinates are in the report's `boards.GlowStitch.source_terminals`; that makes a future reference map reviewable without guessing nets. A source net-0 table, physical connected components or pcb_Z grouping cannot supply this missing intended electrical truth by themselves.

Stop substantive work here at the evidenced geometry/preservation endpoint and reproduced intent blocker. Continue electrical qualification when that datum is supplied under the existing bounded scope; do not invent it, remove its required obligation, start V2/V3 or inspect/integrate pcb_Z. Cursor and manufacturing approval remain separate.

## Final frozen evidence identifiers

| Record | SHA-256 |
|---|---|
| `out/v15_completion/run_20261014T154443_263864Z/final_report.json` | `55a2d402af1b75b27e0aac6831e4f04203ced5f021bbead2853a24e4faf5af71` |
| `out/v15_completion/run_20261014T154443_263864Z/regressions.log` | `dba9c2629738259b36a21fe41b1928f7b75eadbac6581964c1bda72176ec986d` |
| `docs/V1_5_COMPLETION_MATRIX.md` | `4fa1573323307c41c78737c522268561e6f91f6a5bfd2f67c2153a8c5067ff72` |
| `contracts/v1_5_completion_profile.json` | `f5f69891d52d5da7d93c4ec60078b01803acc0ce3218d1f0d35b1b754f449527` |

The source/hash audit also verifies the two supplied/native references, all 106 bound run outputs and the complete source/tool hashes. `front_geometry_preview.svg` files are computed front copper/mask/profile visualizations only, not independent reference images or nine-layer previews.
