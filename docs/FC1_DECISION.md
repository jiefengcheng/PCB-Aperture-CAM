# FC-1 decision — 2026-10-14

**Oracle qualification: PASS within the exact one-file mathematical contract.** Extended Gerber parser support and realistic public PCB validation remain **NOT_ESTABLISHED**. Cursor review: **NOT_RUN / CHANNEL_UNAVAILABLE**. Stop after this gate; no FC-2, MC-1, V2/V3, new downloads, partner contact or manufacturing-rule changes are authorized.

The user approved the reconciliations and FC-1 with “Sure. go ahead” after the charter-alignment commit `1b1b843452f2ee86a944a5b8fb1f856268608bbd`. Codex remains sole coordinator. [FC1_ORACLE_DERIVATION.md](FC1_ORACLE_DERIVATION.md) records the source interpretation, exact area formula, independent matrices/landmarks, tolerances and evidence roles.

## Results

| Obligation | Outcome / evidence |
|---|---|
| Source custody | Archive and member hashes match `contracts/public_sources.json`; all 70 coupon assets remain unchanged; GlowStitch/HALPI2 inventories also match |
| Positive mathematical oracle | Four placements satisfy analytic area, bounds, three components/one hole each and eight copper/void landmarks each; base area 4.626687354634584 mm²; disjoint total area 16.841141970869888 mm² |
| Independent numerical check | Explicit analytic point sets and polygon witness agree at 352,995 stable grid samples; zero mismatches |
| Secondary reference PNG | 12 components; 465,084 tested interior pixels agree, zero mismatches; two-pixel boundary band excludes 12,261 pixels. Precision rendering/oracle conformance not established |
| Geometry falsification | Seven altered witnesses fail their intended area/bound/landmark obligations |
| Reset / global clearing | Two synthetic scene probes distinguish these faults. Original fixture has no post-reset draw or overlapping scene context; no such original-image proof is claimed |
| Unsupported inputs | Five derived files return NOT_ESTABLISHED by exact-source scope guard. No semantic parser coverage is inferred |
| Current parser route | Fresh read-only Gerbonara 1.6.3 probe still ignores aperture-block commands with warnings and fails on undefined aperture 12. Frozen parser source/contract remains unchanged |
| Tests | Eight dedicated FC-1 unittest methods pass, including negative subtests, convergence and preservation; four bootstrap tests pass. Historical full suites are not rerun |
| Preservation | All pre-FC-1 local evidence files match the saved snapshot; frozen parser/falsification/validation tools, report schema, asset manifest and dependency lock match V1 Git blobs |
| Independent review | Packet prepared; no verified direct Cursor channel, no independent review performed |

The PASS means this hand-authored oracle is numerically consistent, matches the source PNG within explicit raster limits and differentiates the chosen faults. It is not independent third-party review, a universal oracle, manufacturing signoff or proof of new Gerber parsing.

## Support-route decision

**Use this oracle as a prerequisite; do not change the frozen V1 parser to accept the file.** Gerbonara 1.6.3 cannot supply the selected aperture-block image. No alternate maintained-parser version has been evaluated or installed, so an implementation route is **NOT_ESTABLISHED**, rather than presumed viable.

A separately approved **FC-2A** could qualify one non-nested block-composition route against this oracle. Prefer a maintained parser that demonstrably exposes block definitions and transform/polarity state. If unavailable, propose a narrowly reviewed standards adapter around a maintained parser, with an explicit support grammar/coverage contract; no general regex parser and no silent unknown-command dropping. FC-2A is a proposed refinement of the format-coverage options in [NEXT_GATE_PROPOSAL.md](NEXT_GATE_PROPOSAL.md), not authorization for them.

Any FC-2A contract would require:

1. Absolute 2.6 mm input, circular apertures, dark/clear image composition, non-nested AB definitions/flashes, finite straight and multi-quadrant quarter arcs, LM/LR/LS state and resets.
2. Explicit immutable source hashes, unit/role/polarity records, full operation inventory and a numerical error budget. Missing layer/file-role authority stays unknown for this official example; it is not relabeled as PCB copper by assumption.
3. Correct local clear transparency versus global clearing; transform order and scaled widths; isolated block-definition state versus output state. Compare independently against FC-1 area/bounds/topology/landmarks and a full composed-image metric, with the secondary PNG kept separate.
4. Actual Gerber-level positive/negative tests, including post-reset and overlap-scene extensions. FC-1's hash guard and altered mathematical witnesses do not substitute for these implementation tests.
5. Undefined, cyclic/nested unsupported blocks, missing units and unknown commands must remain NOT_ESTABLISHED without false PASS. Recursion/resource limits and unsupported operations must be explicit.
6. Preserve frozen V1/V1.5 modules and policy. Version any new parser adapter, coverage contract and dependency changes separately. Qualifying this example does not qualify rounded-rectangle macros, public mask contours, native identities, drills or electrical/process intent.

Estimated subsequent cost remains uncertain: parser-route evaluation plus a restricted adapter could take several engineer days; if no maintained-parser route is viable within that boundary, close FC-2A as NOT_ESTABLISHED rather than widen it silently. There is no approved FC-2A dependency or implementation plan yet. MC-1 passive operation-case modeling remains a separate alternative and must precede any future V2 executor; it was not implemented in FC-1.

## Reproduction / receipts

Run `.venv/bin/python -m src.fc1_run` once in a fresh checkout with the pinned local source inventory. It writes `out/fc1/run_001/` and refuses to overwrite an existing run. It requires `out/fc1/prior_evidence_hashes.json`, the pre-gate SHA-256 snapshot of local `out/` files excluding `out/fc1/`, so that historical evidence cannot be silently replaced. The retained snapshot and runner/report are available locally. For reproduction elsewhere, create a new snapshot from that checkout's retained historical evidence before the run; it does not assert custody of artifacts absent from that checkout.

Tests:

```sh
.venv/bin/python -m unittest discover -s tests -p test_fc1_oracle.py -v
.venv/bin/python -m unittest discover -s tests -p test_bootstrap.py -v
```

Primary receipts: `out/fc1/run_001/report.json`, `tests.log`, `bootstrap_tests.log`, `unsupported_controls/` and `oracle_preview.svg`. The frozen review packet binds the commit and artifact hashes. Old receipts are retained without regeneration. No remote push occurs in this gate.
