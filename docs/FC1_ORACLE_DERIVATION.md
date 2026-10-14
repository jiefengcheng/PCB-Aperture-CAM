# FC-1 independent mathematical oracle — derivation v1

Scope: one hash-bound Ucamco non-nested aperture-block example. This is a hand-authored reference, not a Gerber parser, production checker or repair operator. Source and expected-result hashes are retained in `out/fc1/run_001/report.json`; the independent literal ledger is `tests/fc1_expected.json`.

Original source: `2026_03_24_Gerber_Layer_Format_Test_Files/Block_with_different_orientations.gbr`, SHA-256 `192b7e2198e895bd17ad75b6bd163a5929d05f0a627287f942b98e7e2f61a7d0`, inside the already acquired official archive. Nothing in this module parses its text or consumes Gerbonara primitives. The following interpretation was read directly from the supplied commands and cross-checked against the bundled official PNG.

## Source-derived local image

`FSLAX26Y26`, absolute coordinates, and `MOMM` give millimeters and coordinate resolution 0.000001 mm. Omitted coordinates inherit modal values. D10 is a diameter-1 circle. D11 is a diameter-0.5 circle and the stroke tool. The aperture block D12 contains:

| Operation | Manually resolved local geometry |
|---|---|
| Dark D10 flashes at `X-2500000Y-1000000`, then `Y1000000` | Two radius-0.5 disks centered at (-2.5,-1) and (-2.5,1) |
| Clear D11 flash at `X-2500000Y-1000000` | Remove radius-0.25 disk from the lower disk, leaving a ring |
| Dark D11 stroke from `X-500000Y-1000000` to `X2500000` | Round-ended width-0.5 segment from (-0.5,-1) to (2.5,-1) |
| `G75` / `G03`, end `X500000Y1000000`, offset `I-2000000J0` | Counterclockwise quarter-circle centerline: center (0.5,-1), radius 2, start (2.5,-1), end (0.5,1), width 0.5 |

After local composition the block has three disjoint copper components and one hole. Its local transparent hole must not clear pre-existing global copper when the dark block is flashed. The original four placements do not overlap; that global-image distinction needs a separate scene probe.

Let `D(c,r)` be a disk, `S` the segment centerline and `A` the quarter-arc centerline. The local set is:

`B = [D((-2.5,-1),0.5) \ D((-2.5,-1),0.25)] ∪ D((-2.5,1),0.5) ∪ (S ⊕ D(0,0.25)) ∪ (A ⊕ D(0,0.25))`.

The coordinate frame stays Gerber X right/Y up. No KiCad Y inversion is applied to oracle geometry. PNG comparison alone uses image Y down.

## Independent exact area

The ring and solid disk contribute `0.1875π + 0.25π`. The length-3 segment capsule contributes `1.5 + 0.0625π`. The radius-2 quarter-circle stroke contributes `0.5625π`.

The two strokes meet at a right-angle junction and overlap by **more** than their common endpoint disk. Counting only that disk would overestimate the union. With tube radius `r=0.25`, centerline radius `R=2`, and `a=R-r`:

`I = ∫₀ʳ sqrt(a²-y²) dy = ½[r sqrt(a²-r²) + a² asin(r/a)]`.

The overlap equals the endpoint disk plus the additional interior-junction sliver:

`overlap = πr² + ∫₀ʳ [R - sqrt(r²-y²) - sqrt((R-r)²-y²)] dy = ¾πr² + Rr - I`.

Therefore:

`area(B) = 1.5 + 1.0625π - overlap = 4.626687354634584 mm²`.

The fourth placement has scale 0.8, hence area factor 0.64. All four placements are disjoint; total expected area is `3.64 × area(B) = 16.841141970869888 mm²`. Local bounds are `[-3,-1.5,2.75,1.5]` mm.

## Four manually resolved transforms

For column-vector point `p`, apply **mirror, then counterclockwise rotation, then uniform scale, then placement translation**: `world = t + s R M p`. A placement is not multiplied by its aperture scale. The numeric matrices are written independently from the polygon-builder transform calls.

| Placement | Translation t | Mirror M | Rotation | Scale | Linear matrix |
|---|---|---|---|---|---|
| 0 | (0,0) | identity | 0° | 1 | `[[1,0],[0,1]]` |
| 1 | (10,0) | X | 0° | 1 | `[[-1,0],[0,1]]` |
| 2 | (0,8) | Y | 30° | 1 | `[[√3/2,1/2],[1/2,-√3/2]]` |
| 3 | (10,8) | X and Y | 45° | 0.8 | `0.8/√2 × [[-1,1],[-1,-1]]` |

Analytic bounds use directional extrema, not transformed corners of an enclosing rectangle. A disk contributes transformed-center ± scaled radius. Segment extrema occur at endpoints ± stroke radius. Quarter-arc extrema evaluate angular endpoints and stationary directions of `u cosθ + v sinθ` within `0≤θ≤π/2`, then add stroke radius. Expected bounds and hole/solid centers are recorded literally in `tests/fc1_expected.json`.

Eight named local landmarks per placement check both copper and void: hole center, ring metal, solid center, straight stroke, arc midpoint, inner arc void, absent major-arc location and arc endpoint. Transforming these with the separate matrices gives the world-space obligations. Area and bounds alone are insufficient; topology and landmarks are also required.

## Two mathematical routes and approximation limits

1. **Analytic expectation:** closed-form area, directional bounds, exact point-set equations and fixed landmark/topology obligations. Distance to the finite segment and quarter-arc is computed directly; no polygon or parser supplies truth.
2. **Polygon witness:** Shapely disks/segment buffers plus a sampled arc; local Boolean composition; sequential mirror/rotate/scale/translate calls. Its area/bounds/landmarks/topology are compared to the independent expectation and literal ledger. A finer witness is checked for convergence against the analytic area.

This separation avoids using a parser's own output as truth. Both routes were authored by the same coordinator; no independent engineer or Cursor review is claimed.

Numerical contract, distinct from the coupon's 0.001 mm tolerance:

- Source coordinate resolution: `1e-6 mm`; these example coordinates resolve exactly at that precision.
- Circle buffers: 512 chords per quadrant. Maximum radius-0.5 disk sag `0.5(1-cos(π/2048)) ≈ 5.883e-7 mm`.
- Arc centerline: 2048 segments over a quarter turn, sag `2(1-cos(π/8192)) ≈ 1.471e-7 mm`; radius-0.25 cap sag is smaller than the flash-disk sag.
- Linear comparison budget: `1e-5 mm`, with a `2e-5 mm` conservative boundary exclusion for point-grid comparison. Floating transforms are far smaller at this scale.
- Area comparison budget: `1e-4 mm²`. Base perimeter is about 21.582 mm; the approximation displacement budget times perimeter remains below the area allowance. Observed base area error is about `1.936e-6 mm²`; finer discretization reduces it.
- The independent analytic-vs-polygon grid has 0.025 mm spacing, 352,995 stable samples and zero mismatches; 605 samples near primitive boundaries are excluded. Finite samples alone do not prove continuous geometry equality.

These are numerical approximation allowances, not approved process, clearance, registration or manufacturing rules.

## Secondary official PNG cross-check

The original 789×605 RGB8 PNG is decoded with CRC verification by a bounded PNG reader, without editing it. There are 12 orange connected components. Two isolated unrotated solid pads calibrate one global scale and origin: 36 pixels/mm; `(px,py)=(208+36x,448-36y)`. There is no per-placement adjustment or arbitrary warp.

The analytic set agrees with all **465,084 pixels** outside a conservative two-pixel boundary band; **12,261 pixels** are excluded and zero tested interior pixels disagree. The source PNG was also visually inspected: lower identity/X-mirror motifs, upper rotated/mirrored motifs, rings, disks and joined strokes agree qualitatively. Raster edge differences remain unqualified. This confirms broad orientation/placement consistency, not precision geometry, metadata preservation or standards conformance.

`out/fc1/run_001/oracle_preview.svg` is the polygon witness rendered in the same coordinate frame. It is generated reference geometry, not a Gerber export or a freshly accepted production image.

## Negative controls and evidence boundaries

Seven altered polygon witnesses deliberately introduce wrong mirror axis, reversed mirror/rotation order, wrong fourth scale, clear-as-dark hole fill, major clockwise arc, wrong arc center and inch-unit scaling. Each fails its named landmark, area or bound obligation.

Two additional probes are **synthetic scene extensions**, not content of the official example:

- Pre-existing radius-0.1 copper at the local hole center survives a correct dark block flash; a deliberately global clear erases it and is rejected.
- A hypothetical fifth block placement at `(0,-5)` after LMN/LR0/LS1 must use identity transform. Retaining the previous mirror/45°/0.8 transform misses a named copper landmark. The original ends after reset; it cannot prove this behavior from its own image.

Five derived Gerber files cover undefined aperture, recursive block, nested block, missing units and unknown command scenarios. They are rejected as **outside the one-file hash-bound oracle**, with NOT_ESTABLISHED. This is custody/scope guarding, not newly implemented semantic diagnosis. No generic Gerber mutation validator or parser support is claimed.
