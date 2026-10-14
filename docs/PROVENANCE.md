# Source register and immutability

| Asset | Origin | Actual status |
|---|---|---|
| `assets/starter/` | Original supplied `aperture_cam_starter_v0_1.zip`, unpacked without alteration | Author-generated synthetic source fixtures + reference Gerbers, NOT KiCad-executed output |
| `assets/source_archive/aperture_cam_starter_v0_1.zip` | Original starter archive, retained byte-identically | Audit source |
| `assets/observed_before/coupon-F_Cu.gbr` | The user's real KiCad F.Cu **before** plot, isolated from an earlier local export | Independent observed source, not a fully validated Gerber geometry result |
| `assets/observed_before/coupon-F_Mask.gbr` | Same, F.Mask before plot | X2 soldermask, negative file polarity, four opening regions |
| `assets/observed_before/coupon-Edge_Cuts.gbr` | Same, profile before plot | Board outline |
| `assets/observed_before/coupon-job.gbrjob` | Same, job metadata | Not a netlist or authority for process acceptance |

There is **no real candidate KiCad plot in these assets**. For V1, Codex must produce and retain both exports from the untouched original `assets/starter` native before/candidate board source. Do not substitute authored JSON geometry or the generator's reference Gerbers for the native plotting result. Do not silently normalize and rewrite immutable inputs. The `contracts/asset_manifest.sha256` file is the input-integrity contract.

The Mac-observed baseline headers identify `KiCad Pcbnew 10.99.0-unknown`, coordinate format X4.6/Y4.6, millimeters, and F.Mask negative image polarity. KiCad 10.99 is a development build; G1 should record exactly which version newly generated the fresh pair.

The user's two PPTs and historical discussions are not re-distributed in this minimal handoff. The business context is summarized in `docs/CONTEXT.md`. No customer manufacturing data and no externally cloned PCB designs are included.


## Authorized V1.5 amendment — 2026-10-14

The user authorized public reference acquisition and read-only realistic-design qualification after frozen V1. See `docs/ROADMAP.md` for the binding sequence, separate gates and stop line. Preserve V1 source assets, policy, implementation and acceptance result. External inputs belong in immutable `external/sources/`; derived evidence belongs in `out/v1_5/`. GlowStitch precedes HALPI2-HDMI-FPC and official Ucamco parser fixtures. Public compatibility does not establish electrical/manufacturing correctness or authorize V2/V3. Cursor review requires an actual authenticated channel; none has been verified.
