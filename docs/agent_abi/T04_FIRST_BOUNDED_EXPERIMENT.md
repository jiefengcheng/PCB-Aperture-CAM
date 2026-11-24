# Explicit bounded T04-first experiment

## Original-source issue resolution — 2026-11-22

The owner explicitly requires T04 directly over original source and all
identified issues resolved before the final full-board run. Use the bounded
T04-only runner with `--context original`; no upstream or later construction
is invoked. The connected-fill route exclusion is temporarily disabled by
eligibility registry revision 2; the width cutoff is still 0.25 mm. The runner
freezes the current eligibility policy in a separate job-local snapshot in
addition to the retained ladder settings.

For an explicitly identified existing source-pad bump, the owner authorized
`--trim-pad-ordinal <ordinal>` (repeatable). Cleanup occurs as a separate
pad-only subtraction after T04 construction, with actual output contacts and
combined material topology rechecked. Unselected terminals stay byte-identical;
changed terminals must match the explicit cleanup records exactly. Original
Gerber bytes and historic jobs remain immutable. No general pad resizing,
terminal growth or later-stage construction follows from this option.

The viewer's `init --context original` independently authenticates original
source lineage, rejects inherited grown geometry or fabricated T03 acceptance,
and reconstructs every baseline object from original source bytes. A retained
post-T01 display template cannot contaminate unselected source objects.
The gray/green legend uses the bound presentation's actual predecessor label.

Bounded checks, pending endpoint/corner diagnostics and a completed whole-board
T04 result remain distinct. The final full-board run is NOT_RUN while the
owner's issue-resolution hold remains open. Current evidence:
`out/lacie_work/t04_large_fill_audit_20261122/`.

## Current execution scope: T04 only

The user's 2026-11-21 instruction, "t04 only for the moment", pauses the
terminal-order comparison. The running T02 calculation was stopped and its
partial evidence retained. No further T01/T02/T03/T05 construction is authorized
by the current experiment scope.

Use `tools/t04_trace_priority_experiment.py` with an explicit source job,
cohort scope, fresh LaCie output and `--context original|retained_t03`.
The original arm reads source/policies without reading or inheriting T03
acceptance. The reference arm verifies and reuses the retained T03 predecessor;
it does not rerun its upstream stages. Both construct only bounded T04, retain
existing diagnostics, assemble separate diagnostic contours and verify unchanged
terminal context. Complete T04-only wall time includes preparation, assembly,
checks and report writes. Terminal-growth tradeoffs remain unmeasured.

The earlier multi-stage prototype below is retained as implementation history
and is not the currently authorized execution recipe.

## Paused multi-stage prototype

This is an opt-in experiment, separate from `pipeline.stage`, accepted-T03
custody, completed T04, replay and export. The default stage order is unchanged.
Use `tools/t04_order_experiment.py` only from a frozen source snapshot with
committed T01/T02 dependencies. The runner requires an explicit source job,
cohort scope, fresh LaCie output directory and `--order current|trace_first`.

Both arms begin at the identical original Gerber occurrence scene. The retained
job supplies immutable original source artifacts and policy snapshots, not its
T01/T03/T04 acceptance or previously grown copper. Source-role preparation binds
that original scene. Mutable stage-entry admission and covered-copper selection
are freshly reconstructed when terminal growth changes the scene. No accepted
T03 record is fabricated for the alternate arm.

The current-order arm executes bounded T01, the existing unchanged-original T03
checks, existing bounded group/residual T04, contour assembly and bounded T02.
The alternate arm executes existing bounded T04, assembly, bounded T01, bounded
T02 and explicit trace-floor/connection reconciliation. Both arms retain all
original context, caps, clearance policy, seven-pass schedule, source noise
handling and independent 10% residual-end matching. Both residual flags are on.
No T05, full-board construction, export or replay is invoked.

Terminal scope is fixed before either arm from the original native-route
neighborhood (0.5 mm), with complete canonical circle competition groups and
applicable round priorities. Canonical circle allocation is freshly computed
on the complete original source; construction is restricted to the explicit
terminal IDs. Unselected circles and rectangles remain fixed. This is a bounded
stage-order comparison, not a new whole-board pipeline result.

`bounded_order.assemble` materializes exactly the existing serialized source
contours and changed bulk operands into a separate experiment scene. It invokes
existing diagnostic checks; it does not add group-interior geometry auditing or
promote the stage to completed T04. Existing endpoint/corner findings remain
reported. Later terminal stages must preserve constructed trace bytes, original
terminal cores, source identities/pose metadata and route/terminal connections.
Land construction and independent T02 reconstruction retain their existing
checks. Reconciliation is not electrical intent or manufacturing approval.

Complete wall time includes source reads/validation, original context and
canonical allocation construction, all invoked stages, assembly, checks and
report writes. Phase timing is separate. Preparation caches are owned and fresh
per arm. The final tiny wall-time receipt's own write is necessarily excluded;
its larger result receipt write is included. Single paired measurements do not
establish a statistical speedup. Source, input and scope hashes bind the result.

Evidence: `out/lacie_work/t04_first_20261121/`. Failed attempts are retained
separately; fixes require a new frozen snapshot and fresh output directory.
