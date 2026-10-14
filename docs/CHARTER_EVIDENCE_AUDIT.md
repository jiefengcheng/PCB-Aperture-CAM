# Charter evidence audit — 2026-10-14

Scope: documentation adoption, read-only review of retained local evidence, commit/source/schema comparison and hash custody. **No new Gerber export, parser/geometry run, native-save round trip or full test suite is executed.** The current four bootstrap tests are separately reported below. This audit checks consistency and provenance of recorded results, not independent algorithm correctness or manufacturing acceptance.

Detailed audit: `out/charter_adoption/audit.json` (29 recorded checks, all consistent). Prior evidence snapshot: `out/charter_adoption/prior_evidence_hashes.json`. The audit's aggregate PASS concerns custody/record consistency only; the partner-evidence row explicitly records NOT_ESTABLISHED and is not a partner qualification pass. All original `out/` artifacts are preserved. These outputs are Git-ignored/local; this documentation commit contains the durable scope/results and their hashes, not the raw historical reports.

## Verified retained claims

| Claim | Local evidence inspected / verification | Finding and limit |
|---|---|---|
| Frozen V1/V1.5 history | Git objects `36eab151a0bf00ea57eef09f1dc425c4b5603e50`, `cb0377cbdcdac25ee9b89c01aca6901b3ae48d0d`; ancestry verified | Both exist unchanged; V1 is ancestor of V1.5 |
| V1 implementation and contract frozen | SHA comparison to V1 Git blobs for validator/falsification, original bootstrap/native tests, export/validation tools, report schema, asset manifest and lock file | All match; no criteria/tolerance/schema changes |
| Assets immutable | `contracts/asset_manifest.sha256`, `tools/preflight.py` | 70/70 hashes match; no additional or missing asset |
| Actual paired KiCad export | `out/native_exports/20261014T140617_287308Z/run_receipt.json`, native copies, Gerbers and DRC JSON | Source/copy/output hashes match; receipt records CLI version 10.99.0, binary hash, environment and successful native exports. CLI was not invoked or its adjacent build inspected now |
| V1 measured result | Schema-valid `out/v1_validation.json`, policy and independent intent hash checks | Recorded overall PASS, implementation commit V1; exposure 1.19→1.40 mm², gap 1.55 mm, fixed mask/outline, connectivity and scope PASS. Measurements not recomputed now |
| Coupon DRC | Both retained `drc.json` files | One library warning each, zero unconnected items; not manufacturing approval |
| Deliberate corruption controls | `out/negative_controls.json`, mutation file hashes | 13 records match their intended expected FAIL/NOT_ESTABLISHED check statuses; control-success PASS is not candidate PASS |
| V1 historical tests | `out/unittest.log`; static test-method count at V1 commit | Retained eight-test OK receipt; not rerun in this governance pass |
| Public source custody | `contracts/public_sources.json`, complete local file/ZIP-member hashes, external Git HEAD/clean status | GlowStitch `1c5d867ece6a5c38ac5ad7067cac352a5734655a`, HALPI2 `3bef1d94520db0c866a79009a69102241ccd8521` match manifests/reports and remain unchanged |
| Public native no-edit evidence | `out/v1_5/{GlowStitch,HALPI2-HDMI-FPC}/qualification.json`, copied board and both export sets | Output hashes match; nine retained parser fingerprints match per board. This checks stored receipts, not fresh parsing, attribute preservation or independently composed geometry |
| V1.5 result and DRC | Qualification reports and retained DRC | Realistic validation NOT_ESTABLISHED; GlowStitch 320 errors/360 warnings, HALPI2 nine warnings, zero reported unconnected items. These are tool diagnostics, not approved project-defect labels |
| Ucamco custody/compatibility | Official ZIP, all extracted member hashes, `out/v1_5/Ucamco/compatibility.json` | 11 Gerbers: nine warning-free parse/expand records; two AB examples warn/fail. Render-oracle comparison remains NOT_RUN; no parser conformance PASS |
| V1.5 historical tests | `out/v1_5/unittest.log`; static test-method count at V1.5 | Retained 11-test OK receipt; not rerun now |
| Independent review / partner acceptance | Existing review packets, available tool metadata, supplied charter, `docs/CONTEXT.md` | Cursor NOT_RUN / CHANNEL_UNAVAILABLE. Partner code/approved case/process rules not established by inspected records |

## Relevant format-coverage matrix

Native filename labels below refer to the actual names recorded in the qualification JSON: GlowStitch's `x1 GlowStitch LED Panelised KiCAD Design File-*.gbr`; HALPI2's `HALPI2-HDMI-FPC-*.gbr`. Source paths are under `out/v1_5/<source>/export_1/`; official examples are under `out/v1_5/Ucamco/extracted/2026_03_24_Gerber_Layer_Format_Test_Files/`.

| Source / feature | Actual source or retained parser behavior | Frozen composed-geometry confidence / usable checks | NOT_ESTABLISHED boundary |
|---|---|---|---|
| Coupon F.Cu / F.Mask / Edge.Cuts | Absolute 4.6 mm, rectangular terminal flashes, circular linear strokes, straight mask regions; negative mask openings | Recorded V1 PASS for this exact supported subset; defined exposure, reference, connectivity, clearance and scope | Generic geometry or manufacturing validity not established |
| GlowStitch F.Cu | `%AMRoundRect*` starts line 15; macro aperture at line 39; retained Gerbonara parse/expand succeeds, frozen import stops at multiline extended operation | Full copper composition NOT_ESTABLISHED; no public connectivity/clearance/scope acceptance | Macro support, copper graphics/regions, public terminal identities and independent net intent |
| GlowStitch F.Mask | Straight region input; retained parser expands 160 Region objects, frozen geometry import reports `invalid region` | Opening composition/containment NOT_ESTABLISHED | No region repair, alternate contour interpretation or factory coverlay meaning inferred; first rejection is not a complete diagnosis |
| GlowStitch Edge.Cuts | Linear stroke profile; frozen import subset PASS | Profile import only; no copper or production acceptance | No full independent public-board preservation test |
| HALPI2 F.Cu / F.Mask | `%AMRoundRect*` line 15; rounded-rectangle macro aperture definitions; retained parser expansion succeeds, frozen importer rejects multiline operation | Required copper/mask checks NOT_ESTABLISHED | Macros/rotated artwork, region composition and public identity/intent outside coupon scope |
| HALPI2 Edge.Cuts | `G75*` line 25, `G02*` line 26, further arcs | Frozen importer rejects arc-mode operation; outline equivalence NOT_ESTABLISHED | No qualified arc interpolation or tolerance composition |
| Native B layers, paste, silkscreen and drills | Nine requested Gerber layers retained per board; some empty; drill export files retained | Warning-free raw primitive expansion/reproducibility receipts only | Frozen acceptance covers three coupon roles; complete output-job semantics/empty-layer intent and drill/multilayer electrical checks unqualified |
| Ucamco non-nested block example | `ABD12`/`AB`, local dark/clear, G75/G03, LM/LR/LS transforms and resets | Gerbonara 1.6.3 warnings ignore block definition, then undefined aperture 12 causes failure | Full composed block image NOT_ESTABLISHED; bundled PNG not evaluated |
| Ucamco nested block example | `ABD100`, `ABD101`, `ABD102` operations | Warnings ignore block definitions; undefined aperture 100 causes failure | Nested hierarchy/composition NOT_ESTABLISHED |
| All official examples under frozen V1 guard | Each is lexically rejected; selected block file has FSLAX26Y26, outside V1's 4.6 format before AB handling | Frozen acceptance NOT_ESTABLISHED | Do not claim the frozen guard specifically diagnoses AB; detailed AB failure comes from the separate retained library probe |
| Other nine official examples | Retained library parse/primitive expansion PASS without warnings | Source-loading indication only | No independent precision geometry/render oracle or full standards conformance |

Observed first-rejection reasons are coverage evidence, not proof that all later constructs are known. Fixing AB alone would not qualify the public boards, whose first gaps are rounded-rectangle macros, mask regions and arcs plus missing qualified intent. The selected official block also bundles multiple semantics; [NEXT_GATE_PROPOSAL.md](NEXT_GATE_PROPOSAL.md) keeps oracle qualification separate from implementation.

## Checks executed for this alignment

- `python3 tools/preflight.py --output out/charter_adoption/bootstrap.json`: PASS_BOOTSTRAP_ONLY; 70 immutable assets, expected before/candidate/aperture positions and observed-before syntax. Preflight's NOT_RUN fields describe its own scope, not a reversal of historical V1 evidence.
- `.venv/bin/python -m unittest discover -s tests -p test_bootstrap.py -v`: four tests, OK; retained at `out/charter_adoption/bootstrap_tests.log`.
- One-off read-only audit: Git blobs/ancestry, local SHA-256 inventories, source Git status, archive members, retained report schema and receipts; no committed implementation script added.
- Documentation scope, links, source-copy hashes and preservation checks: recorded in `out/charter_adoption/documentation_checks.json` before commit.

The full eight/11-test suites, all parser/oracle checks and native export are **NOT_RUN in this alignment**. Their historical successful receipts remain intact. Current independent Cursor review is NOT_RUN. Manufacturing acceptance and business usefulness remain NOT_ESTABLISHED.

## Evidence identifiers at alignment

These SHA-256 identifiers bind the inspected local records; a hash does not independently prove their conclusions.

| Artifact | SHA-256 |
|---|---|
| `PCB_CAM_North_Star_Charter_Pack/PCB_CAM_PROJECT_CHARTER.md` | `e087df7de4a74b994ca6f69f73e5c44404092ec19e5f1669260502852692a0ef` |
| `PCB_CAM_North_Star_Charter_Pack/CODEX_CHARTER_ADOPTION.md` | `9ee9db82c6861e2ad22f3abe8c8f970226a8a9020ae1d393e72ac2be3fd70b87` |
| `out/charter_adoption/audit.json` | `ce046021192e5f1fac6150d75eca167d3e297ca3d91784999450a09040127544` |
| `out/v1_validation.json` | `4c7fabf81feb37e0c899d6ba6bd569c5049d1ff5a6f7a2d8e55769a0ceebcdf0` |
| `out/negative_controls.json` | `7dbce582b5f8ad86cce48393f16df65ef0fba37969b0eb6d21e6b08d97151b5b` |
| `out/v1_5/GlowStitch/qualification.json` | `537cb115f4239b5a3541532aeeb7c3896e44eacc2e4307f31c6a8db115f84c01` |
| `out/v1_5/HALPI2-HDMI-FPC/qualification.json` | `8ccd46869705463caf91ed128487d9bdb995edf4a315c6e678f9ca9d25f29e70` |
| `out/v1_5/Ucamco/compatibility.json` | `f546fbf4673e8a31b30bf954ee6417b23134eff3aafac00a691364ee99fbf10b` |
| `out/unittest.log` | `9d7a06c341d4f3af821ccd46d6ab3257f66242e99f15f4d2dd225cb119bab0de` |
| `out/v1_5/unittest.log` | `f9459b040aae749d4f3fb9f974f9d53b561ecb55d339788fa4b507370c78fa49` |
| `out/charter_adoption/bootstrap_tests.log` | `3f0419895b4b337d4b0601e81384ad6741f12d071be30353e8d16f8161f8c5b3` |
