# C01 T05 — EDIT spindle correction, 2026-10-30

The owner reported that the first T05 result treated only a small fraction of the expected necks and requested comparison with EDIT's merged circle–neck–trace spindle patterns. Direct inspection of `out/crop_dynamic_tasks/t03_t04_s1_registration_20261025/C1_edit_reference.png` confirms that short trace-width-capped tapers are insufficient. The first implementation's 1.5× local flare and two-trace-width approach were implementation choices, not the full visual objective. The earlier bounded-operator completion record does not establish completion of this broader T05 treatment.

## Corrective trial

`src/junction_spindle_blend.py` adds a land-sized rolling-disc closing operator. The source-qualified connected trace plus its directly contacted circle operands form one owner. The closing fills concave shoulders to blend a circle–trace–circle pattern, preserving every original owner contribution. Growth is confined to circle-local windows (two land radii outward from the contacted lands) and the C01 viewport. The radius derives from the smaller land half-size rather than the T04 width ceiling. This is junction copper added to the scene; the T04 nominal source widths/routes and frozen T01 parts stay byte-identical.

Foreign copper is protected by conservative 0.02011 mm buffered barriers applied only to added copper; final checks require 0.02010 mm. No original copper is clipped or narrowed. Original positive-area trace/circle contact qualifies ownership. Shared component labels do not exempt foreign copper. Disconnected owners reject. Branch/mixed-width source components remain excluded pending a local split; this trial does not silently authorize all copper of a shared label.

The new trial starts from the same T01+T04 predecessor as the first T05, preserving the earlier result separately. EDIT is a directional visual reference, not authoritative copied geometry or a claim of exact registration equality.

## Result 260

Path: `out/crop_dynamic_tasks/c01_t05_spindle_trial_20261030_260/`.

- 57 source endpoint components accounted for.
- 23 trace components blended, involving 43 source-qualified circle contacts. These are incidence counts, not 43 independently proved neck repairs.
- 28 components have no source-qualified circle contact; five branched/mixed components require a local split; one contacted component has no accepted bounded blend.
- Added area: 0.19900711150961453 mm², versus 0.02277093484042142 mm² in the first short-taper result.
- After SHA-256: `587d10f5855c4b7afe2f37130277d3c0bdc711b84b74c0dd8c69f6d4ff932966`.
- Saved-source owner and cumulative-scene reconstruction, patch/window hash checks and final surrounding-copper checks pass for all 23 additions. Minimum checked added-to-foreign surface gap: 0.020108464650033457 mm.
- All 266 T01 file hashes and all 126 T04 source parts remain unchanged. No T02 applied.
- 38 focused tests pass, including circle-pair broadening, disconnected-owner rejection, foreign collision, writable-window and deletion controls.

Run 259 preserves a failed presentation-finalization attempt (reference file hash was given a Path instead of bytes). Geometry checks completed, but that run is not the delivery. Run 260 fixes that presentation error and completes successfully with the same geometry.

## Delivery and limits

Review `index.html` in result 260: EDIT, before, clean after and actual added copper. The current visualization hub links this trial while retaining the first T05 result and its history. Full growth and clean-after images were inspected. All links and image files are checked.

This is a broader experimental result, not final or independent T05 acceptance. The five branching/mixed components and one unaccepted contacted component remain explicit. Constructor replay, differential width verification of the new blend, and electrical/native/export qualification are not claimed by the saved-trial recheck. The prior original-stage-order comparison requirement remains effective: preserve the first result, and later compare T01 → T03 → T04 → T02 → T05, especially on C02.
