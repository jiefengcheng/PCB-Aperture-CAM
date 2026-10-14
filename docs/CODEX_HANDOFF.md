# Technical handoff — V1 / 2026-10-14

## Purpose

Build a reproducible independent validator that reads **KiCad-exported Gerber copper and soldermask** to decide whether a precisely bounded, engineer-defined change preserves an aperture reference and electrical/copper constraints. This is an experimental covered-rim aperture case, not a universal mask or flex-coverlay process specification.

**Canonical source**: `assets/starter/reference/` and `assets/starter/fixtures/before` & `assets/starter/fixtures/candidate`. The deterministic solver selected P1 **20.05 mm** using minimum movement from X=20.35 constrained by opening A1 centered at X=20.00. The intended footprint/pad geometry and routing were already generated in the provided KiCad fixtures. V1 only reads and evaluates exports; it does not implement a new editor.

## Data tiers / provenance

A. Original `assets/starter/fixtures/*/geometry.json`: analytic source and expected intent; only for independent assertions, not a replacement for reading Gerber.
B. `assets/starter/fixtures/*/reference_gerbers`: synthetic generator output, **NOT KiCad exports**; useful parser smoke checks and negative testing.
C. `assets/observed_before`: user-observed **before** export from KiCad 10.99.0-unknown, three clean layers and job metadata; no matching observed candidate is included.
D. **Required new output**: generate both before and candidate Gerbers from the untouched native coupon boards via `python3 tools/export_native.py --case both` in a version-controlled local KiCad environment. Record source hashes, CLI version, commands and DRC diagnostics. Use these new paired outputs for the authoritative V1 acceptance tests.

Important: importing Gerber into PCB-native objects is NOT part of V1. This route uses native KiCad sources only to establish the experiment and real Gerber files as the validator's inputs.

## Synthetic geometry and rule contract

- A1 center: `(20.00,20.00)` mm, opening `1.00 × 1.40` mm.
- P1: `(20.35,20.00)` before; `(20.05,20.00)` generated candidate; pad size `1.40 × 1.80` mm.
- Intended P1 move: `-0.30 mm` X, unchanged pad size, net N1. Local T1/T2/T3 may change; P2/P3/P4, T4/T5, all apertures and Edge.Cuts are fixed.
- Opening coverage: opening expanded by `0.10 mm` remaining copper overlap + `0.05 mm` per-axis registration uncertainty must lie inside P1 copper; equivalently nominal rim `≥0.15 mm`. Nominal center tolerance X/Y is separately stated in policy; report both.
- Min different-net copper clearance `0.20 mm`; min trace width `0.20 mm`; max target movement `0.50 mm`.
- Net intent P1↔P2 = N1, P3↔P4 = N2, N1/N2 must not be physically merged.
- The source fixture expected opening exposure before is `1.19/1.40 mm²`; candidate `1.40/1.40 mm²`. These numbers MUST be independently recomputed from exported copper/openings and not copied into results.
- All rules invented for this experiment; never call it factory certification.

## Implementation milestones

**G0 / source custody:** manifest, paths and native source coordinates confirmed, clean workdir and stable commit. Bootstrap tests run.

**G1 / export baseline:** KiCad CLI runnable, before/candidate generated from copies of pristine native files; output organized in `out/`, exact command and version retained. Compare the `observed_before` export to newly exported before by geometry (not byte equality) as cross-check. If KiCad unavailable, report `NOT_RUN` and stay in parser/fixture research, not full V1 PASS.

**G2 / independent Gerber import:** use a third-party Gerber library where practical (e.g. Gerbonara), document exact version. Read X2 file roles, X4.6 mm units, negative-mask file polarity, flashed rectangular pads, circular-aperture stroked tracks, G36/G37 opening regions, and profile. Define GUI↔Gerber transformation (in this fixture, GUI Y positive down; observed Gerber coordinates have negative Y). Inventories and unsupported coverage must be explicit. No regex parser as general engine.

**G3 / deterministic acceptance:** compare fixed opening and profile geometry; compute area/shape exposure; verify registration containment with required uncertainty; reconstruct physical N1 and N2 copper connectivity from copper footprints plus tracks, compare against supplied independent terminal intent; ensure no different-net shorts and clearance ≥min; verify protected geometry unchanged and delta limited by authorized region / objects. Explicit tolerances and numerical uncertainty.

**G4 / falsification:** use actual parsed Gerber data, not JSON-only substitutes, to show that a shifted aperture, disconnected N1, N1–N2 bridge, changed protected P3, bad exposure, unexpected file polarity or unsupported operation are rejected or marked NOT_ESTABLISHED. Negative cases must each fail for the intended reason; reports trace evidence to source file/object.

**G5 / evidence + independent review:** write `out/v1_validation.json` following `contracts/report.schema.json` and `out/v1_validation.md` with exact inputs, tools, checks, coverage, limitations; execute tests and freeze commit. Codex may request Cursor read-only review via an authenticated direct channel, then record its actual independent findings. If unavailable, report review `NOT_RUN` and separate it from technical validation.

Stop after G5. Do not implement or claim V2 automatic KiCad modification, LLM planning, process-approved CAM repair, manufacturing sign-off, multilayer connectivity, impedance or mechanical flex reliability.

## Engineering caveats

- `%TF.FilePolarity,Negative*%` on F.Mask is NOT a license to treat the opening as copper or to ignore polarity. Interpret Gerber image semantics correctly; report supported semantics and coverage.
- Aperture definition (`D10`, etc.) in Gerber means plotting tool, not a physical window. The rectangle regions in mask are openings by file role + polarity.
- Actual native test input uses board geometry and explicit nets, while Gerber copper X2 object attributes may also include names. **Observed physical connectivity must be checked independently of those names**.
- Geometric touching at a single point is not a robust manufacturing joint. Assess contact area/neck width and report limitation on this simple coupon.
- Preserve immutable byte hashes and geometric comparisons separately; timestamp changes don't indicate geometric changes.
- Capture layer role, units, polarity, clipping, transform and unsupported constructs; don't infer factory rules.
