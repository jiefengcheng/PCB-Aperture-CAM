# Stage ABI/1.0 — independent batch audit

**Scoped verdict: PASS_FOR_NEXT_SLICE — implementation/model only.**

Packet integrity 20,340/20,340; outer SHA `50705fb6db97ebc2c2c4b03edab91884c34526872530b2832d9b787faa33a449`.

313/313 distinct tests and 2 subtests passed when unchanged test list was partitioned across fresh invocations; single monolithic run timed out. All 35 operations covered by five real-factory wire tests.

Exact-hash sexpdata 1.0.2 module obtained from retained REV10 (sha ceaa3bb54b53f159359e33d1d65bb3918614289b2c78e8f46b6e9e1f96673e3c). Supplement transport archive NOT ACCESSIBLE, so supplement outer sha/manifest NOT VERIFIED. Original dependency lock omission confirmed.

Six actual-board saved-case VERIFY attempts: NOT_RUN_ENVIRONMENT_MISMATCH, per unmodified guard (Python 3.13.5 Linux vs author 3.14.5 macOS). No recorded PASS promoted.

Per-suite: T01/T03/T04/T02/T05 model/contract tests PASS for supported families only. Cross-stage model composition PASS; no native whole-board proof. C01/C02/C03 unchanged. Historical C02 REV234 REVISE and C03 provisional issues OPEN.

8 supplied frozen subset files independently rehashed via packet checks; full 19,990 frozen files not supplied.

Findings and exact file/line evidence are in JSON. Next bounded action: fix dependency packaging and reproduce saved source VERIFY only under exact runtime; no native construction or geometry edits.
