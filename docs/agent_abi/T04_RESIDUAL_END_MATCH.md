# Independent residual-end matching: bounded prototype

This document retains the earlier nominal-only reference and its historical
measurements. The later [residual-chain ABI](T04_RESIDUAL_CHAINS.md) includes
already-grown sources and input budgets; see its [agent handoff](T04_RESIDUAL_CHAIN_HANDOFF.md)
for the current bounded consolidation. The old and chain flags remain separate.

Enable only for a bounded experiment with
`group_stage.run(..., rule={..., "residual_end_matching": True,
"residual_end_deviation": 0.1})`. The ordinary caller remains unchanged by
default. This is not a full-board readiness or completed-T04 qualification.

## Rule and module boundaries

Each residual end independently selects a width between 90% and 100% of its
adjoining treated section, intersected with nominal/source growth caps. An end
without a registered treated section retains nominal width. The two ends need
not be equal; there is no 10% band over the entire route.

`ribbon_profile.match_ends` reuses the existing integer face allocator and cubic
ribbon materializer. It retracts optional side growth rather than symmetrically
cutting nominal copper. The selected faces obey the existing side-slope limits
(0.25 ordinarily, 1.0 for the existing short straight-connector family). One
full-span cubic gives zero width derivatives at its ends. Scalar allocation
provides an upper proposal; final slope limiting may reduce it. No maximum
growth or global optimum is claimed for this recovery rule.

`residual_corridor.Corridors` compiles fixed-operand bounds once and reserves all
prospective residual envelopes. Polygon boundary projection into a longitudinal
slab supplies conservative normal intervals. Separating intervals reserve the
unchanged clearance and construction margins. The new phase makes no R-tree
queries, GEOS distance calls or candidate clearance-verifier calls. Polygon
materialization and exact nominal-floor unions still use the existing geometry
kernel; this is not a claim of zero geometry processing.

`residual_end_match.run` applies the rule only to ungrouped sources whose default
growth decision remained nominal. Covered sources and constructed straight/arc
interiors are excluded. A failed corridor bound is inconclusive, not proof of
physical infeasibility. Such a proposal retains its previous result and reason.
The existing bounded nominal-skin stitch can retry an exact-floor union, with
its width reserved first and its complete added footprint included in the
corridor certificate. Clearance/caps are not waived to admit that retry.

For qualification, this recovery phase runs **after the existing default growth
phase and before joint finishing**. It therefore does not replace or save the
old search cost. Existing final connection, pocket and functional checks remain.
Raw constructed contours and frozen straight-body hashes remain byte-identical;
adjacent joint supplements can change. Constructed-group audit count stays zero.

## Actual-caller qualification

All arms start from the same accepted T03, using a frozen T04-only source
snapshot, the existing preparation artifacts and the unchanged seven-pass
schedule. Stage wall time includes setup inside the caller, growth, recovery
and existing final checks. These are single paired measurements.

| Cohort | Baseline stage, s | Matching stage, s | New residual profiles | Matching phase, s |
|---|---:|---:|---:|---:|
| 41 hard routes | 267.29 | 266.05 | 3 | 0.56 |
| Five marked cases | 95.55 | 94.64 | 0 | 0.37 |
| 64 requested entries | 149.43 | 165.57 | 0 | 0.43 |

All existing checks passed: 41, 30 and 62 applicable native trace-route
connections respectively. The 64-entry cohort has 62 applicable trace routes.
All constructed group contours, frozen straight-body hashes, covered copper
and schedule comparisons passed. The disabled five/64 arms retain exact
baseline copper and non-timing report/proof-field parity. Enabled five/64
serialized copper is also exact; compared execution fields are identical after
removing the declared new extension and its phase record.

The hard cohort had 56 eligible sources: three accepted, 50 lacked a proven
corridor and three required a longer continuation under the retained transition
bounds. The three recoveries are arcs on those routes, not repairs of all the
original flagged connectors. Five-case proposals numbered 26 of 28 eligible;
all 26 were deferred by the corridor bound. The 64-entry cohort proposed 42 of
44 eligible; all 42 were similarly deferred. Remaining cases failed scalar
transition construction. Width-only matching has not closed the hard joints.

The unchanged five/64 geometry also means the observed 64-entry slowdown cannot
be attributed entirely to the 0.43-second new phase. Existing corner processing
alone varied from 68.80 to 75.50 seconds. These measurements establish no stage
runtime saving. The six-arm harness, including shared initialization, saved-site
probe, artifact writes and comparisons, took 1168.24 seconds (19 min 28 s);
the shared initialization/probe portion was 35.21 seconds.

Regressions: 1060 passed, 16 skips. Source snapshots,
failed experiments and exact input/output bindings are retained under
`out/lacie_work/t04_residual_end_match_20261121`. Its separate saved post-joint
probe preserved full retained bodies and is diagnostic only; it must not be used
to infer that a pre-joint residual profile is impossible.

## Disposition

Keep this path opt-in. It demonstrates a cheap, separated profile constructor
and conditional construction certificate, but not the requested general repair
of residual growth and joint transitions. More complete route-continuation and
joint-corridor budgets are needed before replacing default search or enabling
this path broadly. Do not relax source caps, clearance or discard obstacles to
improve admission counts.

The evidence directory contains SUMMARY.json, BENCHMARK.json, COMPARISONS.json,
the per-arm CASE.json/construction files, FIVE_COMPARISON.png,
HARD_RECOVERIES.png and VISUAL_METRICS.json. Owned pytest temporary directories
and plotting caches were removed; shared caches and retained evidence remain.
No full-board run, replay, export, remote publication or acceptance promotion.
