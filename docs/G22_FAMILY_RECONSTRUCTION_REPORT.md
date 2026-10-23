# G22 family reconstruction experiment

**Run:** `run_20261023T195309_750772Z` (fresh Slice C export/readback); Slice D binds this run into the current workbench publication.
**Scope:** Three registered ORG copper neighborhoods and corresponding EDIT artwork in the fixed ORG coordinate frame.
**Result:** The ORG-derived experiment is reproducible and locally checkable, but it does not explain the observed enhancement well enough to claim family reconstruction.

## What was executed

The experiment retained the previously identified three-member ORG family and its source identities. A compact `selective_land_neck` recipe was calibrated on member A and transferred without member-specific parameter changes to B and C. It increased the selected circular feature radius by `0.00953 mm` and the attached selected trace widths by `0.05 mm`; no junction blend was used. Candidate geometry came from ORG source occurrences, not EDIT contours or EDIT masks.

The frozen search evaluated 63 of 64 permitted candidates across `selective_land_neck` (9), `junction_blended` (36) and `neighbor_constrained` (18); none was marked rejected or unobservable. The selection rule was frozen before scoring: eligible candidates were ranked lexicographically by the measured A terminal-radius error, uniquely matched attached-trace width error, supported-window symmetric difference and boundary discrepancy, then by model simplicity and parameter size. The selected A trial (`selective_land_neck-006`) exactly matches the measured `0.13450 mm` terminal radius and has `0.00004 mm` unique trace-width error. It does not use a junction blend. This is target-informed geometric fitting, not recovery of an expert process rule.

The same selected recipe was transferred to B and C without parameter retuning. Each candidate was generated from that member's ORG source occurrences; EDIT was a calibration/measurement target and was never supplied to the geometry constructor. Candidate boards were plotted by pinned KiCad CLI `10.99.0` on F.Cu, F.Mask, F.Paste and Edge.Cuts. The generated Gerbers were independently reread and compared in the frozen windows plus `0.075 mm` halo. Candidate local native-to-Gerber fidelity and bounded local neighbor-contact/fragmentation checks passed. Candidate reference-layer plots matched ORG after removal of the KiCad CreationDate header. These are bounded geometric checks, not electrical connectivity or full-board clearance checks.

| Member | ORG vs EDIT Δ-area | Candidate vs EDIT Δ-area | Candidate-added vs ORG | Boundary discrepancy, ORG → candidate vs EDIT | Target / transfer result |
| --- | ---: | ---: | ---: | ---: | --- |
| A | `0.142758 mm²` | `0.126467 mm²` | `0.023614 mm²` | `0.025116 mm` vs `0.194177 mm` | Target geometry measured in the fixed window; A calibration case. |
| B | `0.208376 mm²` | `0.200730 mm²` | `0.021444 mm²` | `0.025118 mm` vs `0.194173 mm` | Non-retuned transfer; two same-center EDIT circle records remain alternative identities. |
| C | `0.212870 mm²`* | `0.195755 mm²`* | `0.023614 mm²` | `0.025116 mm` vs `0.200841 mm`* | Non-retuned transfer; partial comparison only; unsupported EDIT arcs leave complete target fit `NOT_ESTABLISHED`. |

`Δ-area` is the fixed-window symmetric-difference area. Each candidate improves this measured quantity only modestly: about `0.016291 mm²` for A and `0.007646 mm²` for B. C's `0.017115 mm²` change is partial and cannot establish a complete fit. The large remaining boundary discrepancies show why the smaller area differences do not amount to successful reconstruction. `*` C's ORG/EDIT and candidate/EDIT values are partial plotted-image results, not complete-target residuals. Window 1/2 and 2/3 overlap by `0.1008 mm²`; per-member values are non-additive, and this report makes no summed family-area claim.

The numeric residuals are windowed plotted-image comparisons. They are not normalized quality scores and do not establish expert intent. A/B local geometry is measurable, but the family result is not fully qualified because C has unsupported EDIT arc geometry; the complete EDIT F.Cu native inventory contains 84 unsupported arcs, and C's local unsupported influence prevents complete target composition. C's partial residual must not be read as a complete fit. Each candidate's bounded local contact/fragmentation predicate passed. The actual export-level out-of-scope-copper mutation was detected and rejected (`PASS_DETECTED_AND_REJECTED`). A synthetic topology test also detects a newly introduced geometric bridge. These controls do not establish whole-board connectivity or prove every listed fault class; DRC was `NOT_RUN`.

No neighbor constraint forced a cutback in the selected candidates. The current operator family supports bounded positive growth and local interaction checks; a negative cutback operator is not implemented or claimed as tested. No whole-family copper-area sum is reported because the fixed windows overlap.

## Custody and decision boundaries

The pinned source identities are ORG `850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0` and EDIT `ec141305a9d93db87709124ba5aa9378135485a019e47a342d099496a5`. The intake package aggregate remains `MISMATCH`; this experiment did not rewrite or requalify it. Native candidate board hashes and source occurrence spans are recorded in the Slice B fit report and Slice C receipt.

`SUPPORTED` refers only to the owner's bounded G22 crop-neighborhood visual review. It is not algorithm approval, electrical acceptance, manufacturing/factory approval, or authorization to fabricate. Region/process meaning and electrical net identity remain `UNKNOWN` where the inputs do not establish them. ChatGPT's review was summary-only and did not verify local files or execution. Cursor review is `NOT_RUN: CHANNEL_UNAVAILABLE`.

## Reproduction and browser review

Run the full bounded experiment and publication with:

```bash
.venv/bin/python tools/run_g22_reconstruction.py
```

This deterministically verifies/reuses the Slice A contract and Slice B fit/candidates, performs a fresh Slice C KiCad export and Gerber readback into a new immutable run directory, rebuilds the source-bound visual payload from that receipt, and publishes a new read-only workbench run. Any failed export/readback stops publication. The independently recorded slice commands and evidence are:

- Slice A contract: `out/g22_family_reconstruction/slice_a/experiment_contract_a0622519d0ef8c9b.json` (`a0622519d0ef8c9b2d01fe55d6659916ebfcf034292a3fa3913952e2c39dcfbd`)
- Slice B fit: `out/g22_family_reconstruction/slice_b/run-d135c1387f58e549/fit_report.json` (`e8a1d1dcaeb29e6ef0ba411cfcd668b227573b6d5b1414d3ddd88b996137fe48`)
- Slice C export and evaluation receipt: `out/g22_family_reconstruction/slice_c/run_20261023T195309_750772Z/run_receipt.json` (`928866b1d8fc414541f8934c053631f292ae8637a7edc293859681f7f582c150`)
- Slice D visual payload: `out/g22_family_reconstruction/slice_d/presentation.json` (`619778095ff802374cff2838c84253b61352e4e404332bd08360f9b1d7b155d7`)
- Summary-only ChatGPT review record: `out/g22_family_reconstruction/slice_c/chatgpt_audit_receipt.md`

The current read-only workbench is [open at the verified publication](http://127.0.0.1:8769/run-8931c8d2ddd643c1b4ad9a603cc9f8f8/index.html). It is left on **Storage & indexes → ORG family hypotheses → 3020301113B → G22 · ORG to experimental candidate to EDIT**. Member controls switch among all three synchronized windows; recipe provenance is expandable. The view distinguishes local execution checks from EDIT similarity and keeps the B/C qualifications visible. The publication verifier passed with 2,418 outputs, six datasets and three comparisons. Its receipt is `out/ingestion/workbench/run-8931c8d2ddd643c1b4ad9a603cc9f8f8/receipt.json` (`004c99a7beebb385bb914b09493db4e12747e8d894d4d4067d451e209e45cc7a`).

The Slice D source-to-display regression now binds each member’s seven SVG panels to the correct ORG, EDIT and candidate Gerber cases. The builder records panel-content SHA-256 values; publication checks those values, the member identity, the fixed/analysis windows and the exact source Gerber hashes against Slice C. Negative cases reject a swapped member binding, candidate panel substitution and changed source hash. Slice D’s focused tests pass (6); the full G22/ingestion/family-map suite passes (56). `py_compile` and `git diff --check` pass. Current browser inspection confirmed A/B/C member selection, B’s retained ambiguity, and C’s `NOT_ESTABLISHED` target status.

The detailed Slice C receipt retains export commands, actual Gerber hashes, measurements, fault controls and limitations. It records ORG, EDIT and all three generated candidate F.Cu exports, plus the reference layers; candidate construction receipts bind generated board hashes to the exact ORG occurrence spans and operations. A preserved out-of-scope fault was rejected. Slice D also retains earlier failed publication attempts and their corrections. ChatGPT’s final summary-only disposition (`ACCEPT — Binding Condition Closed`) and its stated limits are recorded in `out/g22_family_reconstruction/slice_d/chatgpt_audit_receipt.md`; the consolidated Slice D audit receipt is `out/g22_family_reconstruction/slice_d/run-8931c8d2ddd643c1b4ad9a603cc9f8f8/audit_receipt.json`. Cursor review was `NOT_RUN: CHANNEL_UNAVAILABLE`. No electrical, manufacturing, factory or owner-engineering acceptance is claimed.
