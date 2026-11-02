# T01-COMPILE-01 — English-to-policy compilation gate

This reusable test applies to any language agent operating the T01 ABI. It tests
one step: submitting the supported controlled English and obtaining its precise
typed policy. It does not discover sites, plan, construct copper, qualify C01
reproduction or authorize a later step. The machine-readable definition is
[`compile_gate.json`](../../contracts/t01/compile_gate.json).

## Bound contract and supported language

Use the original C01 binding and all fifteen ordered clauses in
`contracts/t01/c01.english.txt`, interface `t01-interaction-abi/1.1` and the closed
`t01_compile` envelope. The gate definition pins the input/schema hashes and the
expected C01 policy hash. This is controlled English, not arbitrary prose or
unrestricted paraphrase. Altered semantics must be rejected, never normalized
silently or accommodated by changing shared clearance rules.

The coordinator prepares a fresh project-local source-only session using
`tools/t01_operator_host.py`; records agent/model/version, transport mode,
implementation/runtime, asset and frozen-evidence hashes; and supplies its
immutable capsule plus the compile schema. Reuse the current slice protocol in
`T01_OPERATOR_SLICES.md`. No source or frozen-result edits are part of this gate.
Do not copy a prior agent's request and label it new authorship.

## One gate, four checks

1. **Author:** the tested agent writes and reads back its own `t01_compile` request
   in a fresh `out/` directory. Use either exact literal English or its immutable
   `english-spec` reference, plus the authorized binding reference. All six
   context/authority fields are null. Do not mix the two English forms.
2. **Compile and audit:** submit those exact bytes through the real JSON CLI.
   Retain request, raw response, stderr, command, exit code, registry/input/output
   hashes and unchanged-byte receipt. The agent audits the actual response:
   `OK`, null error, correct request/operation, `t01-priority-companion/1`, ordered
   R01–R15 trace and typed rules, source binding, canonical English/hash, complete
   numerical model and expected policy/hash, `construction_status=NOT_RUN`.
   A metadata view is allowed, but missing fields require the raw response.
3. **Falsify:** from an out-of-place copy change exactly one R14 semantic value,
   e.g. `hard gap 0.020 mm` to `hard gap 0.001 mm`. Preserve the original file.
   The coordinator may store that copy as a separate `english-spec`; the agent
   authors its negative compile request. The real ABI must return a semantic
   compilation rejection identifying unsupported/changed rules, with no policy
   result. A malformed envelope or missing-artifact rejection does not satisfy
   this check. The agent audits the observed reason and stops.
4. **Accept:** the coordinator independently checks the actual artifacts,
   transport hashes and audits, then records `PASS_COMPILATION_ONLY`, `FAIL`,
   `NOT_RUN` or `NOT_ESTABLISHED`. Missing or incomplete evidence cannot pass.
   The agent's self-audit alone is not coordinator acceptance.

Native and coordinator-assisted transport are both allowed and must be reported
separately. With assisted transport the coordinator must not repair the agent's
request. Retain rejected requests and start another explicit attempt if needed.
Do not count a native compiler regression as evidence that an agent mastered it.

## Compiler regression prerequisite

Run only the exact test node IDs listed in `compile_gate.json`, for example:

```python
# Run from the checkout with its existing project Python. Output stays in out/.
import json, subprocess
from pathlib import Path
gate = json.loads(Path('contracts/t01/compile_gate.json').read_text())
subprocess.run(['.venv/bin/python', '-B', '-m', 'pytest', '-q',
                '-p', 'no:cacheprovider', *gate['regression_test_nodes']], check=True)
```

These tests cover all mandatory clauses, typed derivation, changed semantics,
literal/reference policy equality, artifact kinds, mixed input rejection and
delivered schema identity. They do not execute discovery or geometry. Keep their
log and tested code hashes with the fresh gate record. A changed implementation,
contract or model needs a new gate run; historical passes do not transfer.

## Failure assessment and limits

For a failed or stalled attempt, record separately: (a) ABI implementation,
contract and packaging effectiveness; (b) agent comprehension and correct use;
(c) host/transport limitations. Distinguish observations from hypotheses. No ABI
invocation means no evidence of an algorithm failure, but poor ergonomics may
still be a delivered API defect. Do not blame either side by default or silently
change the contract to make a test pass.

Session `t01_local_code_c01_ref_20261031_300/slice_1` is a preserved positive
example: Local Code authored the request, Codex transported it unchanged, and
compilation was accepted. It is not a completed future-agent gate: that positive
slice alone has no agent-authored semantic-negative audit. Earlier failed native
transport and literal-authoring attempts remain preserved in session 299.

Passing establishes only supported-English compilation and the tested agent's
ability to use that operation in the recorded transport mode. It grants no
geometry, owner, independent, native-export, electrical or manufacturing verdict,
and never starts T02–T05 or another T01 operation automatically.
