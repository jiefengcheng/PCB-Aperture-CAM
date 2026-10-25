# T02 code structure and accepted checkpoint

This is a documentation map of the implementation already used for the accepted crop. It does not split modules, create a public API, or change the saved result. Function and file boundaries below describe the current checkout.

## Checkpoint identity

The owner acceptance record is [T02_OWNER_ACCEPTANCE_20261025.md](../t02_authorization/T02_OWNER_ACCEPTANCE_20261025.md). It selects result directory v69. Keep these identities separate:

| Identity | Bound value |
|---|---|
| Result label | v69, a result-directory version |
| T02 policy | crop-rect-t02-policy/15, SHA-256 54c9542dd7c31fb8fb24698d97741dcc72a049b050bae6408c421f1b25174df8 |
| ORG source | SHA-256 850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0 |
| Accepted T01 decision | t01_marked_area_fix_freeze_20261025 |
| Accepted T01 scene | SHA-256 073361e8f26c0127a218b4dfacfe9577937641c1c85d5d684f46f63dc075141d |
| T02 constructor | src/crop_rect_t02.py, SHA-256 b33bcda1095d8941f5f24097ba8071c494810fe8122d63e3fbde6daf727d9499 |
| T02 runner | tools/run_crop_rect_t02.py, SHA-256 712be27794c3d3ae8d6520fb46c9ef2625ed0acefe7d5e01721679df4e9a1161 |
| Acceptance commit | 0b07025faa9c371ed331a153ded79c3a86a673bd |

The v69 bundle is in the local ignored out directory. Its 917-entry SHA256SUMS manifest and the code, runner and policy copies were checked against the acceptance receipt and current source. A clone that lacks out can report the recorded acceptance, but cannot claim it freshly inspected or reverified the geometry.

The generated result and audit retain owner_review=PENDING_USER because they predate the later acceptance. The acceptance record adds the owner decision; it does not rewrite the run-time receipt. Native export is NOT_RUN. EDIT equivalence, electrical intent, and manufacturing status are NOT_ESTABLISHED.

## Current responsibilities

| Stage | Existing implementation | Actual responsibility and boundary |
|---|---|---|
| Source and accepted-baseline admission | tools/run_crop_rect_t02.py; validate_accepted_t01_baseline in src/crop_rect_t02.py | The runner binds ORG bytes, registered crop bounds, and the exact accepted T01 owner decision, scene, policy, selection, audit and publication receipts. EDIT contributes crop-location registration only; EDIT geometry is not constructor input. |
| Inventory and source dispositions | Existing T02 ORG inventory under out; bind_source_dispositions and rectangular_feature in src/crop_rect_t02.py | Admits supported standalone filled F.Cu rectangles with source identities/spans. It binds the frozen disposition set and preserves withheld, protected, unsupported and already-covered contributions. The complete 1.25× per-axis envelope must fit the registered crop. |
| Policy interpretation | contracts/crop_rect_t02_policy_v15.json; RectGrowthPolicy | Holds the hard per-axis 1.25× cap, 0.02002 mm construction target, 0.02000 mm experimental surface-gap floor, 0.00001 mm geometry comparison tolerance, source-local rectangle rule, covered-circle palette, and trace interaction classes. The comparison tolerance is not a clearance waiver. |
| Interaction classification | is_side_by_side_trace, side_trace_copper_region, limiting_constraints, envelope_constraint_records | Uses actual finite-width trace copper surface spacing for side-by-side constraints. A narrowly identified pre-existing attachment port is distinguished from the remaining trace. Corner and endpoint findings use a separate topology-only guard and remain open when below the experimental floor. No centerline metric is part of current policy-v15 construction or checks; older centerline wording is superseded. |
| Deterministic rectangle construction | execute and its geometry helpers in src/crop_rect_t02.py | Uses frozen whole-board source-contact components and the current scene. Proposals retain complete rectangles, source-local orientation and fixed centers. Other copper and prior accepted additions constrain each proposal. New source contacts and component joins are prohibited. |
| Embedded covered circles | grow_covered_circles in src/crop_rect_t02.py, called by the T02 runner after rectangle growth | Selects the largest admitted shared diameter fully covered by that circle’s same final parent, at the original center and under the circle’s separate 1.5× radius cap. The latent round selection is reported separately; contained growth adds no visible copper. |
| Run orchestration and evidence writing | tools/run_crop_rect_t02.py | Reads the source, registration, inventory, policy and T01 registry; runs construction; writes per-target contours, decisions, component evidence, latent-circle evidence, combined WKB and SVG views. This file is procedural: the run is performed at module top level and there is no import-safe public run function. The output directory is configurable; the v69 label is not a policy version. |
| Saved-output audit and publication | audit in tools/audit_t02_owner_reopening.py; finalize in tools/finalize_crop_rect_t02.py | The audit reloads saved geometry and checks compositions, source contacts, component partitions, side constraints and issue ledgers using the existing parser and Shapely. Finalization checks byte-identical replay artifacts, records receipts and hashes, and renders the read-only review page. This is not an independent geometry kernel or an agent-facing verify operation. |

## Evidence flow

ORG and its bound inventory plus the exact accepted T01 scene enter baseline admission. The frozen policy and dispositions define eligible rectangle targets. The runner passes those targets, protected geometry, trace records and crop bounds to the T02 constructor. The covered-circle pass follows the rectangle scene. Saved candidates and decision records feed the audit; the repeat run feeds determinism comparison; finalization publishes the receipts and visual page.

The v69 receipt records 80 eligible rectangles, 76 GROW and 4 KEEP decisions, and 5.30840833767796 mm² of additions. It records 44 covered source circles, of which 27 advanced to a larger class with zero visible added copper. The audit preserves 275 original physical components and 121,425 original source contacts, with zero new component connections and zero new local source-contact pairs. These are source-geometry findings under the shared parser/kernel, not electrical-net proof.

The runner currently combines CLI argument handling, admission, source inventory consumption, construction orchestration, output writing and visual source rendering in one top-level script. The geometry module also contains policy structures, rectangle geometry, component validation, future-trace records and covered-circle construction. These are observed responsibilities, not a request to move them. Any later modularization needs separate authorization and parity checks against the accepted artifact.

## Slice audit

ChatGPT's documentation-scope audit checked the local acceptance record against v69's execution receipt, audit, result, copied implementation and policy; verified all 917 entries in the v69 hash manifest; and confirmed the current T02 source, runner and policy hashes match the run copies. It also checked the present T01 structure map and ABI source vocabulary. This is a same-assistant evidence review, not an independent model, parser or geometry-kernel audit.
