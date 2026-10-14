# V1 decision — 2026-10-14

Technical validation: **PASS for the frozen synthetic V1 coupon and qualified Gerber subset**. Independent Cursor review: **NOT_RUN / CHANNEL_UNAVAILABLE**. Manufacturing acceptance: **NOT_ESTABLISHED / OUT_OF_SCOPE**. Stop at V1; no V2 editing or V3 planning implemented.

- G0 PASS: all 70 immutable assets verified before exports and validation. Native footprint origin `(20,20)` plus P1 local X `0.35` / `0.05` confirms source X `20.35` / `20.05`; independently parsed native Gerber flashes confirm the same positions. Policy remains hash-frozen.
- G1 PASS: fresh paired native exports from pristine copies using supplied CLI, `KICAD_RUN_FROM_BUILD_DIR=1`, KiCad `10.99.0` (Gerber header `10.99.0-unknown`). Final run: `out/native_exports/20261014T140617_287308Z/`. Receipt contains CLI binary hash, environment, argv, source/output hashes and logs. Both DRC executions return 5: one missing Synthetic footprint-library warning, zero unconnected items; not clean DRC and not manufacturing acceptance.
- G2 PASS within explicit supported coverage: Gerbonara 1.6.3 parses X2 roles, attributes, absolute X4.6 millimeters, rectangular flashes, circular-aperture linear strokes and straight regions. Negative mask file is interpreted as opening geometry. Profile's absent file polarity is qualified explicitly as positive stroke geometry. Unknown operations, macros, transforms, clear polarity, arcs and alternate units are rejected as NOT_ESTABLISHED.
- G3 PASS: mask/profile unchanged; measured A1 exposure `1.19 mm²` before and `1.40 mm²` candidate; required expanded opening contained with `0.15 mm` rim; center offset `(0.05,0)` mm; physical N1/N2 remain separate and connected; minimum inter-net distance `1.55 mm`; protected objects unchanged; copper delta inside authorized rectangle.
- G4 PASS: 13 retained Gerber corruption controls fail the intended check, including all six required fault classes. Additional controls include clear polarity, inch units, unknown command, narrow neck and insufficient clearance.
- G5 local evidence PASS: schema-valid `out/v1_validation.json`, human report `out/v1_validation.md`, negative reports and mutation files retained. Eight unittest methods pass (including subtests for 13 negatives). Exact implementation commit and source hashes appear in the generated report and `out/cursor_review_packet.json`.

## Reproduction

Use this checkout's `.venv`, not the parent project's shared environment. Install `requirements.lock.txt` into a project-local venv. Tested Python 3.14.5, Gerbonara 1.6.3, Shapely 2.1.2 and jsonschema 4.25.1; `requirements.lock.txt` pins the complete tested environment. The authoritative Python version is recorded by the report.

```sh
python3 tools/preflight.py --output out/bootstrap.json
KICAD_RUN_FROM_BUILD_DIR=1 python3 tools/export_native.py --case both --cli /Users/geoffcheng/Projects/client/misc_repo/KiCAD_PCB_CAM/build/release/kicad/KiCad.app/Contents/MacOS/kicad-cli
.venv/bin/python tools/validate_native.py --run out/native_exports/20261014T140617_287308Z
.venv/bin/python -m unittest discover -s tests -v
```

For a new export, pass its printed run directory to validation. Tests require a native run selected by validation; missing native evidence is an error, never a skipped positive test. `out/` is locally retained and Git-ignored.

## Evidence limits

JSON fixture expectations, synthetic reference Gerbers, independently observed before Gerbers and freshly native-plotted paired Gerbers retain separate roles. Geometry acceptance uses the fresh pair; fixture JSON supplies policy and independent terminal intent only. X2 net names are not used to establish connectivity. Numerical tolerance is 0.001 mm; circular strokes use 128 chords per quadrant with an enforced error budget. Connectivity also requires survival of 0.099 mm copper erosion, bounding narrow-neck acceptance for this coupon. These are experimental constraints, not process specifications.

Available tool inventory exposes no authenticated direct Cursor agent channel. No global configuration or adjacent project was inspected to find one. A frozen read-only review packet is prepared under `out/`; no review occurred and no human relay is requested. No remote writes, account access, uploads, or V2/V3 work occurred.
