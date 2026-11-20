# T04 wider-end trimming: bounded opt-in

This is a separate opt-in treatment with historical measurements. The
[residual-chain handoff](T04_RESIDUAL_CHAIN_HANDOFF.md) describes the later
budgeted growth path; enabling it does not implicitly enable this cutter.

`group_stage.run(..., rule={..., "wide_end_trimming": True})` enables the
existing face-wise tangent cutter on optional wider-end copper. This option
does not use the old larger endpoint width as an admission predicate. Nominal
source cores, covered copper and group interiors outside the native end window
remain protected. The radius remains 0.05 mm and the finishing depth remains
0.005 mm. Source centerlines and the seven-pass schedule are unchanged.

The subtraction mask acts on all same-route aliases, including shared maximal
arc bodies. Native connection, pocket and functional checks consume the refined
output. Raw catalogue/group operands remain immutable construction evidence;
the explicit output subtraction ledger describes their refined end contours.
The old larger-end obligation list remains historical data, not a trimming gate.
Constructed groups are not submitted to clearance audits.

This is not enabled by default or qualified for a full-board launch. The failed
reverse-field experiment was withdrawn after visual review found new seams.
Its source snapshots and results remain in the external evidence directory.

Bounded results under `out/lacie_work/t04_wider_end_rule_20261120`:

| Actual caller cohort | Comparison stage, s | Trimming enabled, s | Trimmed joints |
|---|---:|---:|---:|
| Five cases, 30 native routes | 91.28 | 104.15 | 30 |
| 64 entries, 62 native routes | 138.46 | 163.80 | 59 |

Existing checks passed in both enabled cohorts. Disabled comparison paths
retained exact copper and non-timing report/proof parity with the accepted
baseline. Enabled outputs deliberately change end copper; their subtraction
ledgers account for those changes. No enabled-versus-baseline exact copper
parity is claimed. The five-case comparison arm was retained from the preceding
bounded revision; the 64-entry comparison arm was run on the final snapshot.

Of the 53 saved problem sites, five accepted a tangent cut, ten had no eligible
protrusion and 38 retained numerical construction limits. Thirty-seven of those
38 failed exact containment of a finite subtraction result in its input; one
encountered a GEOS topology exception. These are not 38 proven physical defects
or failures of the user's narrower-continuation principle. They remain explicit
limitations of this implementation. No tolerance or old-width waiver converts
them to success. Trimming a site does not prove all its former shape records
are reconciled.

Focused regressions: 72 passed, three skipped. Failed experiments, source/input
bindings, local before/after visuals, caller artifacts and timing are retained.
Owned plotting-cache files were removed. No full-board run, replay, export or
acceptance promotion was performed.
