# Reproduction handoff checks — 2026-11-24

The public handoff is documentation, source baseline, environment recipe and
packaging support. It does not change discovery, geometry, cleanup policies,
shared copper budgets, native viewer behavior or historical acceptance.

Executed on the authoring Mac:

- Original baseline source SHA-256 verified; source bytes remain identical.
- Existing source parser/coordinate oracle covers all 17,849 source occurrences.
  All 70 immutable asset files pass their manifest check.
- 32 focused Python tests pass, including deliberate baseline corruption,
  runner custody/publication, workspace identity and evidence encoding checks.
  The same 32 tests pass from an isolated export of the staged source, excluding
  unrelated dirty T02/T05 work. Its test harness retains the owning checkout's
  verified LaCie mount authority and uses the owning internal checkout for the
  internal-output negative test.
- The revised builder stages a new app from that isolated source export, using
  the explicit APFS build-root option. Native dependency audit, deep/strict
  ad-hoc signature, offline bundled runtime and exact native-distance smoke
  check pass. `--seal-dmg` creates a new image that passes hdiutil verification.
  This is a packaging check, not another viewer/treatment qualification.
- The 41 recorded Mac package versions resolve to downloadable binary wheels;
  the Mac Shapely wheel's GEOS C hash matches the existing hard pin.
- Linux CPython 3.14 x86_64 dependency wheel resolution succeeds (27 wheels).
  The official Python 3.14.5 slim-bookworm image manifest is available for
  amd64/arm64. Linux Shapely wheel/library hashes are recorded for both.

Docker build/run, Linux trimming, Linux restart/corruption/publication parity,
and a Linux reviewer are **NOT_RUN / NOT_QUALIFIED**. This Mac has no running
Docker daemon. Downloaded wheels and manifest inspection are not Linux execution.
No platform adapter has been bypassed to turn that status into PASS.

The original 0.2.0 DMG and physical two-Mac viewer evidence remain unchanged.
This handoff's new package is not promoted over that delivery and its DMG hash
need not match. No new full-board trimming or growth is claimed here. Refer to
`baselines/large_copper_0.2.0/reference.json` for the previously qualified Mac
geometry result and its explicit unresolved/acceptance limitations.

Retained local logs/builds/tests:
`out/lacie_work/large_copper_reproduction_20261124_01/`. Generated artifacts and
the DMG binary are not committed. Only the requested baseline, small reference
metadata, source, tests and documentation are versioned.
