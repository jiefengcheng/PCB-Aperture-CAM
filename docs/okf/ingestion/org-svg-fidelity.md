---
type: "Geometry Fidelity Qualification"
title: "ORG WKB to SVG geometry fidelity"
description: "Measured round-trip evidence for stored and simplified ORG geometry paths in the read-only review."
generated: {"by":"codex/org-svg-g3-fidelity","at":"2026-10-23T03:02:08+00:00"}
status: "stable"
tags: ["pcb","ingestion","geometry","visual-review"]
sources: [{"id":"implementation","resource":"/references/sources.json","title":"Current implementation bindings"}, {"id":"evidence","resource":"/references/experiments.json","title":"Bound publication and G3 geometry evidence"}]
---

# Scope

G3 checks whether the browser's ORG display paths depict the pinned native geometry at the stated precision. It tests the actual publication's simplified and stored SVG path strings against the corresponding content-addressed WKB. This does not establish candidate-member identity, PCB electrical meaning, copper-enhancement correctness, or engineering/manufacturing acceptance.

# Current result

The final pinned publication is `out/ingestion/audits/20261023_org_svg_geometry_fidelity_g3/publication_reviewed/run-11082f016d4143b7bf04ee8edb820778/`. Its verification receipt covers 2,416 outputs, six datasets and three comparisons. The separate audit measured every 8,476 WKB/path identities for the SZU-Comm ORG family map.

Stored paths at nine decimal places passed for all 8,476 geometries. Maximum measured Hausdorff distance was `7.0562e-10 mm`, below the coordinate rounding bound `7.0711e-10 mm`; all feature bounds match the catalogue bounds exactly at recorded precision.

Simplified paths now use a `0.00005 mm` parameter and five-decimal coordinates. All 8,476 emitted paths are valid, preserve the polygon-component and interior-ring counts, and remain within the measured `0.0000570711 mm` envelope. Maximum measured Hausdorff distance is `0.0000549402 mm`. This is measured evidence for this pinned publication; it is not a general simplifier guarantee. Aggregate symmetric-difference area is reported in the audit JSONL but is not an acceptance limit.

The viewer sets SVG `fill-rule="evenodd"` explicitly so hole rendering does not depend on source ring winding. Coordinates remain in the source WKB X/Y millimetre frame with identity transform. A browser DOM test checks the largest `COMPLETE` group: all 44/44 source geometries draw, all path coordinates fit the padded viewport, and the highlighted seed resolves to the pinned source path.

# Reproduction

From the project root:

```sh
.venv/bin/python tools/ingestion.py --verify out/ingestion/audits/20261023_org_svg_geometry_fidelity_g3/publication_reviewed/run-11082f016d4143b7bf04ee8edb820778
.venv/bin/python tools/audit_org_svg_geometry_fidelity.py --run out/ingestion/audits/20261023_org_svg_geometry_fidelity_g3/publication_reviewed/run-11082f016d4143b7bf04ee8edb820778 --dataset-id 'client:szu-comm:3020301113b:intake-20261021:v1' --output out/ingestion/audits/20261023_org_svg_geometry_fidelity_g3/reproduction
.venv/bin/python -m unittest tests.test_org_svg_geometry_fidelity tests.test_org_family_review_integrity -v
```

The focused browser check is `tests/js/org_family_review_publication.test.cjs`, executed in the connected Node REPL because this shell has no `node` executable. It asserts 44/44 completeness, explicit even-odd fill, viewport containment, and source-bound seed highlighting.

The full audit pack, including preserved failed measurements for initial `0.0002 mm` and `0.0001 mm` candidates, is at `out/ingestion/audits/20261023_org_svg_geometry_fidelity_g3/`. See its README, final `roundtrip_bound/summary.json`, per-geometry JSONL and checksums.

# External static audit

The user's existing PCB AI CAM conversation returned **PASS — bounded, measured fidelity** for this pinned publication. The reviewer assessed only the supplied summary and did not inspect the checkout, artifacts, WKB, SVGs or hashes, and did not run commands; this is a static assessment of reported evidence, not an independent verification. The reviewer specifically cautioned that the measured simplification envelope is not a predeclared acceptance tolerance unless policy was frozen before measurement, and that matching component/hole counts do not prove exact contact or narrow-gap topology. DOM/geometric checks do not establish pixel-level browser rasterization. The response is preserved at `out/ingestion/audits/20261023_org_svg_geometry_fidelity_g3/chatgpt_static_audit.md`.

# Remaining gates

This is G3 display geometry evidence for one pinned ORG map publication. The simplification parameter remains a requested approximation setting, not a promise for future files. Each future publication must be re-audited if it changes source WKB, coordinate precision, simplification algorithm, renderer, or fill semantics. The source package's strict inventory failure and the user's G22 human review remain independent open items.
