# C01 recovery through the local macOS adapter

The user authorized recovering the prior successful Local Code C01 route to
measure the effectiveness of the macOS adapter → native runner/contracts → T01
ABI. Session 300's geometry PASS remains frozen evidence of assisted transport;
session 304's setup PASS does not establish this extended workflow.

Start a fresh bounded session with:

```sh
.venv/bin/python -B tools/t01_macos_adapter.py --session out/<fresh>/run --profile c01
```

The source preparation, ABI and geometry algorithms are unchanged. The extension
`tools/t01_c01_route.py` only binds source operands, invokes one actual ABI
operation, checks its result, preserves receipts and applies the declared
technical gates in `contracts/t01/c01_route.json`. It does not use the one-shot
reproducer, precomputed target contours, MCP, network routes or other stages.
The default adapter profile remains setup only.

Local Code selects each operation using the same stdlib client:

```sh
python3 tools/t01_route_client.py --setup <descriptor> --agent LocalCode --operation t01_compile --attempt compile-01
```

Each response contains actual `facts`, a raw-response digest and an audit shape.
The operator reads that output, writes its observation audit under the fresh
session's `operator/`, and submits it:

```sh
python3 tools/t01_route_client.py --setup <descriptor> --agent LocalCode --operation native_route.audit --attempt compile-01 --audit-file <session>/operator/compile-audit.json
```

The audit must contain exactly `verdict`, `response_sha256`, `observed` and a
brief operator-authored `note`. The native runner independently compares it with
the actual native result; a failed check cannot be turned into a pass by an
operator's assertion. These audits establish observation consistency, not an
independent geometry review or general language understanding.

Only the next operation is available. Every slice requires native checks and an
operator audit. Codex has authored conditional technical acceptance for this
bounded recovery; it is applied by trusted runtime code without per-step Codex
transport or prompting. The exact plan receives run/verify authority only after
that plan's checks and observation audit pass. The operator cannot supply another
plan, policy, source case or authority. Owner acceptance stays pending.

The sequence is compile, discover, inspect, plan, run, verify, compare, read-only
review, and deliberate R14-negative compile. Each is a separate operator-selected
call followed by an observation audit. There is no full-workflow tool or client
loop. Any failure must remain preserved and stop the operator for assessment.

After completion, Codex separately checks the fresh contours and semantics
against the frozen C01 oracle, produces before/after visuals and measurements,
and audits immutable source/frozen custody. The oracle never generates the
candidate. Native reconstruction is not independent, electrical, manufacturing
or fresh KiCad-export qualification. No T02–T05 is executed.

Evaluate native correctness, actual operator behavior, transport/custody and time
to meaningful progress separately. The standard runner already retains raw
stdout/stderr/exits: do not ask the model to construct redundant shell wrappers
or machine receipts. Keep user-selected Low/1280 unchanged.

## Observed result — session 305

All nine operator-selected ABI operations and all nine Local Code observation
audits passed from one initiating instruction, with zero per-step coordinator
transport or continuation prompts. First ABI completion was 111.406 seconds
after the pre-submission marker; all nine audits passed at 579.265 seconds.
Fresh construction/reconstruction took 9.188/9.190 seconds. These times measure
different parts of the process; most elapsed time was outside native execution.

Post-construction comparison found all 51 contours / 53 aliases byte-identical
to frozen C01 and the entire candidate JSON identical to session300. All 34
neighbor control records and the S31 effect match. The minimum measured
unexempted addition gap is 0.020019165139488884 mm against 0.020000 mm policy.
Forty focused transport/custody/slice/authority tests passed.

Evidence, before/after visuals, raw calls, audits and measurements live at
`out/crop_dynamic_tasks/t01_c01_macos_recovery_20261031_305/index.html`.
This qualifies the observed bounded route and operating procedure, not arbitrary
English, independent geometry judgment, general ABI mastery or manufacturing.
No other stages ran and all accepted/frozen results remain unchanged.
