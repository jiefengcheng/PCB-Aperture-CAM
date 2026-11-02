# T01 language-operator slices

Codex coordinates the work, prepares original source operands, registers profiles,
grants plan-bound authority and accepts each audited slice. Local Code authors
closed JSON requests, reads actual responses and audits each slice before waiting.
Neither role may replace an ABI operation with an external geometry constructor.

The Local Code native-CLI preflight failed: its tool host could not invoke the
project Python and rejected native Git flags. Native Codex can invoke the same
project Python and CLI. The alternative being tested is explicitly **assisted
transport**: Local Code writes the request file; Codex submits those exact bytes
to the real ABI without correcting the request. This is not a claim of autonomous
native CLI execution by Local Code. No installation or global configuration
change is involved.

The first literal-English request-authoring attempt was stopped after 8m22s with
no request file. Interface version `t01-interaction-abi/1.1` therefore adds two
content-addressed input forms: compilation accepts `english_ref` instead of
recopied English text, and inspection accepts the actual discovery `selection_ref`
instead of recopying a source-ID array. The ABI resolves and validates those exact
stored operands. Literal input forms remain available. These are transport and
selection conveniences; the English rules, numerical contract, discovery and
geometry algorithms are unchanged. Literal/reference equivalence and rejection
of wrong kinds, changed clauses and foreign selections are regression-tested.

`tools/t01_operator_host.py` is coordinator-only. Its prepare/register/grant actions
do not discover circles, allocate growth or construct geometry. Its transport
action preserves every operator request and actual response, the exact command,
exit code and input/output/registry hashes. Bad requests remain bad and their
rejections are retained. A `.view.json` file provides a bounded metadata projection
with the raw response hash; the complete response is always retained beside it.

## Request envelope

Every request has exactly these ten top-level fields:

```json
{
  "abi_version": "stage-agent-abi/1.0",
  "request_id": "unique-slice-request-id",
  "operation": "t01_OPERATION",
  "profile_id": null,
  "scene_ref": null,
  "policy_ref": null,
  "plan_ref": null,
  "authorization_ref": null,
  "idempotency_key": null,
  "payload": {}
}
```

Do not add filesystem paths, commands, authority strings or helper flags to the
payload. References are complete `{artifact_id, sha256}` objects copied from the
current host capsule or an actual preceding response. Do not invent hashes.

For compile, profile/scene/policy/plan/authorization/idempotency are all null.
For describe, scene/policy/plan/authorization/idempotency are null; the profile may
be the capsule profile. For other operations, profile/scene/policy come from the
current capsule. Only run and verify use plan/authorization and a nonempty
idempotency key. All remaining operations keep those three fields null.

## Operation payloads

| Operation | Exact payload fields and values |
|---|---|
| `t01_compile` | Recommended: `english_ref` and `binding_ref` from the capsule. The ABI loads the exact stored English and compiles all fifteen clauses. Alternatively use `english` with the complete specification text plus `binding_ref`. Never mix both input forms. |
| `t01_describe` | `requested_contract_version`: `stage-agent-abi/1.0`. |
| `t01_discover` | `bounds_ref`: capsule bounds. No precomputed source selection. |
| `t01_inspect` | Recommended: `selection_ref` from the actual discovery, `page_size`: `100`, `cursor`: `null`. The selection must belong to this T01 source scene. Alternatively provide `source_ids` with all canonical IDs, `finding_ids`: `[]`, `page_size`: `100`, `cursor`: `null`. |
| `t01_plan` | `inspection_ref`: preceding inspection; `selection_ref`: preceding discovery; `predecessor_qualification_ref`: capsule `qualification_ref`; `bounds_ref`: capsule bounds; `strategy`: `priority_companion_growth`. |
| `t01_run` | `output_scope_ref`: current authorized capsule output scope. |
| `t01_verify` | `candidate_ref`: actual run; `verifier_ref` and `proof_scope_ref`: authorized capsule. |
| `t01_compare` | `left_ref`: original capsule scene; `right_ref`: actual candidate output scene; `viewport_ref` and `evidence_selection_ref`: authorized capsule. |
| `t01_review` | `candidate_ref`: actual run; `verification_ref`: actual verification; `decision_filters`: `{"types":["owner","independent","local"],"page_size":100,"cursor":null}`. |

The one-shot reproduction runner must not be used for this operator experiment.
Do not import adapter, allocation or geometry code. File tools may write JSON
only in the explicitly authorized fresh slice directory. Host capsules, registry,
artifact store, source, contracts, assets and prior outputs are not operator-editable.

## Responses and audit gates

Compile, discovery, inspection and planning return artifacts under `result`.
Run and verify return job data under `result`, with completed operation artifacts
under `result.result`. A terminal job status alone does not prove a positive
geometry verdict. Read the actual candidate checks or verification verdict.

Use the `.view.json` metadata to avoid dumping a large response into chat. It is
bound to the raw response SHA256; read the raw response when a specific field
needs checking. Self-audits must separate observed output from expectations.

1. **0 / native preflight:** preserve failure if the tool host cannot run Python;
   never call that an ABI algorithm failure or claim Python is absent from the Mac.
2. **0B / file transport:** author and read back a small file, prove correct capsule
   values, acknowledge that no geometry ran. Wait for Codex's acceptance.
3. **1 / compile:** submit controlled English; audit OK, family, fifteen clauses,
   source binding, numerical contract and construction NOT_RUN. Wait.
4. **2 / discover and inspect:** audit 17,849 originals, 51 canonical sites, 53
   aliases, full inspected source set, cursor exhaustion, no construction. Wait.
5. **3 / plan:** audit the interaction strategy, complete 51-site allocation,
   34 groups, 25 round priorities, one source-bound exception, and NOT_RUN. Wait
   for Codex to authorize this exact accepted plan.
6. **4 / run:** audit actual checks, all 51 decisions / 53 aliases, 34 controls
   affecting 18 sites, S31 recess effect and unchanged acceptance limitations. Wait.
7. **5 / verify:** audit fresh source reconstruction, 51/53 coverage, final assembled
   checks and actual PASS; no owner/independent/manufacturing promotion. Wait.
8. **6 / compare and full C01 check:** inspect ABI deltas plus coordinator's exact
   51-site and full semantic comparison against the frozen C01 reference, opened
   only as a post-construction oracle. Wait.
9. **7 / falsification and final audit:** submit a separately authorized negative
   request; audit its actual rejection reason, then audit preserved freezes and
   the full operator/transport transcript. Do not silently fix a rejected request.

Codex accepts or rejects each audited slice based on actual artifacts. Failure
requires two assessments: whether ABI code/contract/packaging was ineffective,
and whether the language operator misunderstood or misused the suite. Neither a
successful host-assisted run nor a self-audit establishes independent geometry,
native-export, electrical or manufacturing qualification. T02–T05 are never run.
