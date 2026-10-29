# CAM Agent ABI v0.1

This is a project-local JSON boundary around the current CAM evidence. It gives a future coordinator a small, typed vocabulary for describing available capabilities, inspecting hash-bound records, composing a deterministic plan, comparing registered runs, and retrieving saved review evidence.

See the [local implementation map](LOCAL_IMPLEMENTATION_MAP.md) for the exact
T01 modules, runner/audit/render entry points, ABI operation mapping, pinned
policy identities, and current worktree snapshot.

It does not call a geometry constructor, write a board, rerun verification, contact a service, or publish a result. `cam_run` and `cam_verify` are declared so callers can discover the intended operations; both return `NOT_RUN / ADAPTER_NOT_QUALIFIED`.

## Current profiles and status dimensions

- `t01_visual_crop_accepted` records the user's visual acceptance of the crop bundle. That decision is bound to the ORG source, scene, policy, report, and fresh audit. Visual review acceptance does not change the saved report or receipt.
- `t01_round_priority_promotion` is a separate registered promotion experiment with owner review still pending. It cannot borrow the first profile's owner acceptance.
- `t01_r1_spacing_rejected` preserves the owner's rejection of historical T01-R1. Its local `PASS_WITH_SCOPE_LIMITS` technical result remains evidence about bounded geometry checks only.

The accepted crop's fresh audit says `PASS_SCOPED_FRESH_CROP_AUDIT`; the behavior objective remains `PARTIAL_INSUFFICIENT_ACTUAL_DYNAMIC_EVENTS` (0 of 3 required evolving-neighbor sites). Engineering and manufacturing statuses remain `NOT_ESTABLISHED`. These are independent fields, not a single roll-up boolean.

The trusted registry and owner-decision files have pinned SHA-256 values in `src/agent_abi/registry.py`. A profile is usable only when its source bytes and every registered local artifact match those bindings and the report, audit, receipt, scene, selection, each saved site contour, diagnostic WKB, and owner decision cross-reference one another. Every site PASS requires the report's mandatory checks to be present and literally true. Missing or mismatched evidence never defaults to PASS. These local pins detect accidental or unreviewed file changes; they are not digital signatures or an external authorization system.

## Local JSON invocation

Every request has the same closed top-level shape. All keys are required, even when unused; extra keys are rejected. Each operation also has a fixed selector scope: irrelevant profile/site selectors must be null, site-specific selectors are inspection-only, and `cam_compare` requires both profile IDs. Runtime validation and the operation-specific tool projections enforce the same rules.

```json
{
  "abi_version": "0.1",
  "operation": "cam_inspect",
  "profile_id": "t01_visual_crop_accepted",
  "site_id": "S14",
  "left_profile_id": null,
  "right_profile_id": null,
  "overrides": null
}
```

Run from the repository root:

```bash
printf '%s\n' '{"abi_version":"0.1","operation":"cam_describe","profile_id":null,"site_id":null,"left_profile_id":null,"right_profile_id":null,"overrides":null}' \
  | .venv/bin/python tools/cam_agent_abi.py
```

Use [request.schema.json](../../contracts/agent_abi/v0_1/request.schema.json) and [response.schema.json](../../contracts/agent_abi/v0_1/response.schema.json) as the shared closed contracts. The response schema checks status/error relationships and required operation-specific result fields. [tool_projection.json](../../contracts/agent_abi/v0_1/tool_projection.json) expands those into seven operation-specific, closed input schemas with unused selectors fixed to null. These are host-neutral projections, not connected tools. The adapter itself reads one JSON value from stdin (or `--input FILE`) and writes exactly one JSON value to stdout.

## Operation meanings

- `cam_describe`: lists the seven operations, profile IDs, and which adapters are currently available.
- `cam_inspect`: retrieves source/run status and, for crop runs, one site keyed by site ID or source identity. A site candidate must hash-match its own report record. For the promotion profile, next-class rejection includes its blocker identity and saved diagnostic geometry references, after checking their paths, existence, and hashes.
- `cam_plan`: returns a deterministic, content-addressed whole-selection plan with source, scene, policy, selection, report, and owner-decision status bindings. Caller overrides are rejected. Execution and verification remain `NOT_RUN`; a plan has no filesystem write effect or execution authority.
- `cam_run`, `cam_verify`: declared unavailable, with no candidate creation or verification rerun.
- `cam_compare`: compares candidate hashes by canonical source occurrence identity only when both runs share source and scene identity. Policy differences are surfaced and prevent an equivalence claim; display site keys are reported as labels, not identity.
- `cam_review`: returns exact saved review/receipt/audit references and the separately pinned owner decision.

The historical T01-R1 profile preserves its rejection independently of its technical checks. Its old format does not contain an exact digest link from the fresh verification file back to the run receipt, so the ABI reports that limitation instead of inventing one. The CLI intentionally accepts only local files and contains no network or plugin transport. The ABI is not yet a production tool server, execution adapter, authorization system, or engineering decision engine.

## Verification

Run the ABI tests with:

```bash
.venv/bin/python -m unittest tests.test_agent_abi_v0_1 -v
```

The tests cover strict request shape and per-operation selector scope, response-schema relationships, exact boolean/count types, report-to-selection identity, per-site PASS consistency, candidate and diagnostic geometry integrity, source-identity comparisons, historical T01-R1 status reconciliation, owner-review separation, and explicit unavailable run/verify ports.

## T03 architecture proposal — 2026-10-29

The [T03 suite proposal](../crop_dynamic_tasks/t03_architecture_notes/T03_AGENT_ABI_PROPOSAL.md)
and [source implementation map](../crop_dynamic_tasks/t03_architecture_notes/T03_CODE_STRUCTURE.md)
are documentation only. No T03 functions, schemas, registry entries or adapters
are added; existing v0.1 run/verify availability is unchanged.
