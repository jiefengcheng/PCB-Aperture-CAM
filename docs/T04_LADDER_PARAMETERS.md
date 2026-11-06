# Provisional T04 ladder parameters

The project registry is `contracts/t04/settings.json`. Current values are the
existing **1.5x maximum factor**, **10 rungs**, and a provisional **0.030mm maximum
total width increase**. The latter is 30um across the complete width, hence
15um per side for a centred uniform widening. Both limits apply simultaneously.
Finished-file clearance tolerance does not enlarge the width-growth cap.

For source width `w`, rung `r` proposes:

```
factor = 1 + (maximum_factor - 1) * r / step_count
width = w * factor
total increase = w * (factor - 1)
```

The provisional ladder is 1.05x, 1.10x, ..., 1.50x. An absolute-cap violation
rejects the complete rung; it is not clamped to an intermediate width. A 0.050mm
route can reach 1.50x (25um increase). A 0.065mm route can reach 1.45x (29.25um)
but not 1.50x (32.5um). A 0.300mm route may reach 1.10x (exactly 30um).
These are parameter limits, not claims that scene checks permit those rungs.

`src/t04_settings.py` reads the registry once and supplies an immutable policy.
`capture_job` writes an exclusive `T04_SETTINGS_SNAPSHOT.json` containing exact
registry bytes, their SHA256 and resolved parameters. Changing the registry
affects subsequent captures; reading a job uses its snapshot without rereading
defaults. A worker must bind the snapshot in its producer/job-input seal before
using it. No environment override or global OS setting is involved.

The isolated Gerber U05 T04 path now consumes the job snapshot and executes the
prescribed route ladder. Its two audit workers freshly replay every attempt,
complete nominal/envelope checks, existing smoothing and actual export/reparse.
Historical native KiCad adapters retain their old acceptance contracts in this
slice; their migration and a fresh full U05 run remain before global rollout.
This implementation is unintegrated. The thirteen-route findings are under
`out/lacie_work/evidence/t04_ladder_20261107_slice_01/FINDINGS.md` in the main
checkout. Old search was not rerun as a performance baseline. Historical failed
evidence and the explicit unwaived `.DS_Store` custody finding remain unchanged.
