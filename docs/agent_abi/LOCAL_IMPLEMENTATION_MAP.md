# CAM Agent ABI v0.1 local implementation map

This map records the implementation present at local commit `838b2d5`
(`Split T01 sizing, recess, and owner policy modules`) plus the worktree state
captured in
[`local_worktree_snapshot.json`](../../out/agent_abi_v0_1/abi_v0_1/local_worktree_snapshot.json).
The snapshot records the full commit ID, `git diff --binary HEAD` hash,
`git diff --cached --binary` hash, and SHA-256 for every path returned by
`git status --porcelain=v1 -z` (expanding untracked directories to files).
Run-level reports also retain code hashes for the modules used when each saved
result was produced. The worktree snapshot, run code hashes, registered policy
hashes, and artifact hashes identify different things; none substitutes for the
others. They are local integrity records, not signatures or authorization.

## T01 capability boundary

| Responsibility | Actual code | Boundary |
|---|---|---|
| ORG source and target identity | `src/crop_circle_sources.py:source_scene` | Reads the bound source and policy; discovers unique sites and source occurrences. |
| Size-class choice | `src/crop_diameter_selection.py:admissible_diameters`, `select_targets`, `promote_round_priorities` | Selects discrete physical diameter targets and records blocked next classes before geometry construction. |
| Square-guided shaping | `src/crop_square_recess.py:square_guided_recess` | Removes optional growth in response to selected real copper; preserves the source core and hard-gap checks. |
| Owner-directed target changes | `src/crop_owner_review.py:select_owner_review_targets` | Verifies prior report hashes and applies only named owner edits. |
| Mutable scene and geometry execution | `src/crop_balanced_t01.py:WorkingScene`, `execute` | Revision-checks obstacles and commits candidates into the local working scene. |
| Historical spacing-driven candidate | `src/crop_dynamic_t01_r1.py:run` | Separate historical experiment; its owner decision remains rejected. It is not the accepted crop constructor. |
| Run orchestration | CLI module `tools.run_crop_diameter_classes_t01` selects a pinned policy, then calls `tools.run_crop_balanced_t01.main(out, *, policy_path, policy_sha)` | Writes a new run under `out/`; this is an execution entry point, not an ABI adapter. The CLI module has no `main()` function of its own. |
| Underlying run function | `tools.run_crop_balanced_t01.main(out, *, policy_path=POLICY, policy_sha=POLICY_SHA)` | Orchestrates the run, audit inputs, and saved artifacts for a selected policy. |
| Saved-output audit | `tools.audit_crop_balanced_t01.main(out)` | Executes bounded checks in a fresh process using the project's shared parser/kernel. This local script is distinct from ABI `cam_verify`. |
| Review rendering | `tools.render_crop_balanced_t01.publish(out)` | Publishes a local read-only view from saved, audited artifacts. The browser does not run geometry. |

`src/crop_diameter_classes.py` remains a compatibility facade re-exporting the
sizing, recess, and owner-review functions. The refactor in commit `838b2d5`
established these module boundaries without changing the accepted saved crop.
See [T01_CODE_STRUCTURE.md](../crop_dynamic_tasks/T01_CODE_STRUCTURE.md).

The principal callable signatures at this checkout are:

```text
source_scene(source, policy)
admissible_diameters(radius, palette)
select_targets(sites, groups, priorities, scene, settings, palette)
promote_round_priorities(sites, groups, priorities, scene, settings, targets, records)
square_guided_recess(site, radius, obstacles, settings)
select_owner_review_targets(root, policy, sites)
WorkingScene(source, rows, shapes, sites, settings=CropSettings())
execute(source, rows, shapes, sites, groups, priorities, *, dynamic=True, settings=CropSettings(), counterfactuals=True, targets=None, square_guided_ids=())
tools.run_crop_balanced_t01.main(out, *, policy_path=POLICY, policy_sha=POLICY_SHA)
tools.audit_crop_balanced_t01.main(out)
tools.render_crop_balanced_t01.publish(out)
```

`tools.run_crop_diameter_classes_t01` is a CLI module rather than a Python
`main()` function: its `__main__` block parses flags, selects a pinned policy,
and calls the imported `tools.run_crop_balanced_t01.main`.

## ABI operation mapping

| ABI operation | Implementation | Current effect |
|---|---|---|
| `cam_describe` | `src/agent_abi/service.py:_describe`; `registry.load_registry` | Describes registered profiles and adapter availability. Read-only. |
| `cam_inspect` | `service._inspect`; `registry.load_profile`; `registry.site_record` | Reads hash-bound saved source/run/site evidence, including recorded next-class blockers. It does not call the T01 constructors. |
| `cam_plan` | `service._plan`; closed request validation in `models.validate_request` | Returns a content-addressed, zero-write plan for an existing registered recipe. Overrides are rejected; no geometry runs. |
| `cam_run` | `src/agent_abi/ports.py:RUN_PORT` | `NOT_RUN / ADAPTER_NOT_QUALIFIED`; no fallback to a runner. |
| `cam_verify` | `src/agent_abi/ports.py:VERIFY_PORT` | `NOT_RUN / ADAPTER_NOT_QUALIFIED`; the ABI may read a saved audit as evidence, but cannot invoke `tools.audit_crop_balanced_t01.main` as a verification adapter. |
| `cam_compare` | `service._compare` | Compares compatible saved reports by source occurrence identity and candidate hashes. Read-only. |
| `cam_review` | `service.dispatch` review branch | Returns saved review, receipt, audit, and owner-decision references. Read-only. |

The ABI service deliberately has no imports from the T01 constructor or runner
modules. It binds to registered outputs in `contracts/agent_abi/v0_1/registry.json`
and verifies their hashes before returning them. This is the intended v0.1
read/plan/evidence skeleton; execution adapters remain unavailable until their
separate qualification gate.

## Registered policy and status references

The hash-pinned registry identifies three different records:

- `t01_visual_crop_accepted`: `ACCEPTED_VISUAL_CROP`, using policy SHA-256
  `1b084cb2366a08e356841ebe5b8890248ba0f75656280e174dee23af1f1fcf5f`.
- `t01_round_priority_promotion`: `PENDING_OWNER_REVIEW`, using policy SHA-256
  `b74681cec401ba54ca2e92fc0dc6d265a1373d21892be0e200993f7ca44d47be`.
- `t01_r1_spacing_rejected`: `NOT_ACCEPTED_BY_OWNER`, using policy SHA-256
  `85157972dfddfd9cd7c56ccf41fe97e173803838b6f22964e0dc1f979fa86861`.

The crop audit remains scoped; the evolving-neighbor objective remains partial
(0/3 credited sites); engineering and manufacturing remain
`NOT_ESTABLISHED`. The accepted visual decision does not change those statuses.

## Reproduction

From the repository root:

```bash
.venv/bin/python -m unittest tests.test_agent_abi_v0_1 tests.test_crop_diameter_classes tests.test_crop_square_bound_growth -v
printf '%s\n' '{"abi_version":"0.1","operation":"cam_describe","profile_id":null,"site_id":null,"left_profile_id":null,"right_profile_id":null,"overrides":null}' \
  | .venv/bin/python tools/cam_agent_abi.py
```

These checks exercise the ABI and the refactored selection boundary. They do
not execute a new crop geometry run or elevate any acceptance status.
