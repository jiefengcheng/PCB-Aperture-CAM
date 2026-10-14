# V1 gate and acceptance contract

## Mandatory evidence, not mere indicators

| Gate | PASS only when | Otherwise |
|---|---|---|
| G0 | Assets hash verified; before/candidate native baseline P1 =20.35/20.05; policy frozen | FAIL / NOT_ESTABLISHED |
| G1 | Both native boards exported with KiCad CLI, tool version and reports recorded | NOT_RUN (tool unavailable) |
| G2 | Independent Gerber reader resolves *all relevant* primitives, file polarity, units and layer role | NOT_ESTABLISHED for unknown constructs |
| Fixed reference | Exported mask openings + board outline geometrically equivalent | FAIL on moved or edited reference |
| Exposure | Target aperture is fully supported by copper, with required margin/uncertainty | FAIL on missing copper |
| Connectivity | P1-P2 remain connected and P3-P4 remain connected by actual copper; N1 and N2 distinct | FAIL on break/short; NOT_ESTABLISHED if intent/geometry unknown |
| Clearance | Entire different-net copper geometries respect required 0.20 mm spacing | FAIL on insufficient space |
| Scope | Only P1/T1/T2/T3 within region altered; P2,P3,P4,T4,T5 unchanged | FAIL on unauthorized edits |
| Negative controls | Deliberate faults rejected for the intended check, including unsupported semantic case | FAIL if silently accepted |
| Evidence | JSON with sources, hashes, actual measurements, tolerances, coverage, limitations and reproducible commands | NOT_ESTABLISHED if data missing |

**Overall result**: `PASS` only if every required check has independent evidence from the actual paired Gerber exports. Any mandatory `FAIL` => overall FAIL; any mandatory `NOT_ESTABLISHED` or `NOT_RUN` => overall not established. Cursor review status must be reported separately from geometry/checker acceptance; it cannot be silently substituted.

This is NOT a DFM, assembly, flex-coverlay, drilling, soldering, signal integrity or production certification. No schematic exists; independent net intent is synthetic and supplied out-of-band.

## Golden and falsification fixtures

- Positive: the pristine generated candidate, P1 center `(20.05,20.00)` mm, all invariants checked on freshly plotted Gerbers.
- Negative 1: move fixed `F.Mask` opening (must fail reference invariant).
- Negative 2: remove a connecting N1 copper segment (must fail connectivity).
- Negative 3: add copper bridge between N1 and N2 (must fail short/clearance).
- Negative 4: move P3 without authorization (must fail scope).
- Negative 5: insufficient copper overlap (must fail exposure/registration).
- Negative 6: introduce unsupported gerber macro/mirroring/polarity handling (must become `NOT_ESTABLISHED`, not PASS).

Prefer corruptions of exported Gerber made in `out/` or fixture-local temp directories so these tests exercise the parser and geometry logic, not a JSON-derived surrogate. `assets/starter/fixtures/reject_*` are additional synthetic expectations and cannot replace Gerber-level falsification.


## Authorized V1.5 amendment — 2026-10-14

The user authorized public reference acquisition and read-only realistic-design qualification after frozen V1. See `docs/ROADMAP.md` for the binding sequence, separate gates and stop line. Preserve V1 source assets, policy, implementation and acceptance result. External inputs belong in immutable `external/sources/`; derived evidence belongs in `out/v1_5/`. GlowStitch precedes HALPI2-HDMI-FPC and official Ucamco parser fixtures. Public compatibility does not establish electrical/manufacturing correctness or authorize V2/V3. Cursor review requires an actual authenticated channel; none has been verified.
