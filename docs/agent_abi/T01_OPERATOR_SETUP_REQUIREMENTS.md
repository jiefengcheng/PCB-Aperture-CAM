# T01 autonomous operator setup requirements

The user adopted native execution and trustworthy result custody as first-class
setup requirements, alongside the ABI. They are prerequisites to an autonomous
operator experiment, not optional coordinator conveniences. The earlier
coordinator-watchdog direction is **not adopted**.

Machine-readable gate: `contracts/t01/operator_setup_gate.json`.
Current status: **local macOS setup probe PASS** for Local Code through the
file adapter in session 304. The earlier direct-executable failure is retained
below as history. Full S02 qualification and the S03 autonomous C01 workflow
remain separate; this document alone is not execution evidence.

## S01 — real native execution from the operator

The operator must invoke the existing project-local T01 implementation through
an actual supported tool binding, without Codex transporting its requests.

The binding must identify and verify the project interpreter, dependency/kernel
versions, source/runtime fingerprint and trusted registry. A positive read-only
ABI probe and a deliberate semantic-negative probe must return actual native
responses with their real exit status. A syntactically correct request, a file
written by the model, a shell's claim, or a coordinator-run result is insufficient.

The supported route must be established using the app's authorized extension/tool
mechanism. Do not escape its sandbox, substitute an unqualified interpreter,
install software, expand permissions, or change global settings to manufacture a
pass. If invocation is unavailable, stop with NATIVE_CHANNEL_UNAVAILABLE. That is
a setup failure, not proof that the ABI algorithm or Mac Python is missing.

Expose typed T01 tools and compact state to the operator. Trusted runtime code
should supply repeated envelope context, validate source/plan-bound authority,
and preserve results. The model chooses and interprets operations; it should not
spend most of its generation budget copying paths, hashes and transport scripts.
Do not hide the experiment inside a predetermined one-shot reproduction script.

## S02 — native result custody

Custody belongs in the trusted execution path, not in a model's discretionary
post-processing. Each attempt gets a unique ID and fresh immutable output scope.
Preserve the exact request, actual stdout, actual stderr, actual exit status,
command/operation, interpreter/runtime identity, registry digest and input/output
hashes. Record an empty stdout or error as observed; never replace it with a
model-written success response.

Retries must allocate new attempt scopes. Reject overwriting an existing attempt.
Keep failed evidence. Hash checks must detect changed requests or responses; a
subsequent successful attempt cannot silently reseal the earlier failure.
Publish progress from completed native operations or actual backend events,
correlated with attempt IDs, rather than from token activity or guessed stages.

Required controls: existing-attempt overwrite rejected, tampered request rejected,
tampered response detected, registry/runtime mismatch rejected, unavailable native
route reported, and a failure retained unchanged across a subsequent attempt.
The existing content-addressed store and verbatim host transport provide useful
foundations; they have not been bound to Local Code as autonomous tools.

## S03 — genuinely autonomous bounded C01 trial

Only after S01/S02 pass: one user instruction starts the source-bound C01 T01
workflow, the operator chooses the next ABI operation from actual results,
technical checks govern continuation, and it finishes or reports a concrete
blocker without Codex re-prompting/transporting each step. Source and authority
are bounded up front; the model cannot mint authority. Human owner acceptance
and independent/manufacturing qualification remain separate.

Measure time to first completed ABI operation, meaningful progress intervals,
total completion time, thinking/output tokens, actual native execution time,
coordinator interventions, instruction compliance and receipt integrity. Preserve
51-contour/53-alias correctness and controls; fast but incorrect is not a pass.
No T02–T05 or frozen-result changes are authorized by this trial.

The user selected Low reasoning effort and 1,280 thinking tokens. Treat that as a
test configuration, not a proven latency or correctness guarantee. Direct typed
tools, compact context and machine verification are the intended route to smooth
autonomy. Repeated coordinator timeouts are not a substitute.

## Evidence behind the present status

The guided C01 run in session 300 reproduced all 51 contours exactly, with 53
aliases; construction/reconstruction took 8.686s/8.796s. This proves the bounded
geometry backend, not an autonomous Local Code loop.

In session 303, under user-selected Low/1280, Local Code produced a direct
read-only describe request. Its tool host returned command-not-found/OILS-ERR-100
for the project interpreter, with empty stdout. The executable exists and works
in the Codex host. Local Code's receipt reports NATIVE_CHANNEL_UNAVAILABLE and
exit 127. Its explanation that a particular sandbox/symlink rule caused the
failure is a hypothesis, not established by the raw error alone.

The same stderr filename was reused for absolute and relative invocation errors;
Codex preserved both observations separately. This independently demonstrates the
need for trusted per-attempt custody. The operator did not successfully execute
the ABI in this preflight. The coordinator also attempted to stop at the failure
boundary, so this is not a zero-intervention autonomous-completion qualification.

The next engineering problem is a supported native T01 tool binding plus
write-once receipts. Its availability in Local Code remains NOT_ESTABLISHED;
reducing thinking alone does not supply it.

## Adopted local setup architecture

The user explicitly excluded MCP. Keep the native runner and contracts, with a
system-specific adapter above them. The current implementation slice is a local
macOS file mailbox; see `T01_MACOS_NATIVE_ADAPTER.md` and
`contracts/t01/macos_adapter.json`. It opens no network listener and changes no
global configuration. Other systems and Apple Intelligence adapters are deferred.
Implementation and actual agent qualification remain separate. Earlier failed
Local Code direct-executable evidence stays valid for that earlier route.

## Session 304 scoped setup proof

The local macOS file adapter passed 23 focused custody/transport controls and
three live setup attempts through one descriptor, including an actual Local Code
invocation under unchanged Low/1280. Positive compile exited 0, deliberate R14
negative exited 2 with T01_ENGLISH_UNSUPPORTED, native describe identified the
unchanged implementation, and the client verified receipt hashes. Local Code
read the actual stdout/stderr and reported the bounded setup pass. There were no
per-step coordinator transports during its call. The foreground adapter was
stopped after testing; no installed service or live network route remains.

Evidence: `out/crop_dynamic_tasks/t01_macos_native_adapter_20261031_304/`.
This proves that local setup route, not general agent independence, free-form
English interpretation, complete S02 qualification or an autonomous C01 loop.
The two coordinator-hosted client labels are repeatability probes, not two
independent agents. No geometry or later stages were run.

## Session 305 bounded recovery

The user next authorized recovering the prior C01 route through the adapter.
Local Code completed nine separate operations and nine observation audits from
one instruction, with no per-step coordinator transport/prompts. Post-construction
checks match all 51 frozen C01 contours / 53 aliases and the full earlier
candidate data. This is observed bounded-workflow evidence; the broader setup
gates and general agent mastery are not silently promoted by it. See
`T01_C01_MACOS_RECOVERY.md` and session305's evidence index.
