# U03 separator-conditioned local computation — 2026-11-04

Implemented on `codex/u03-dependency-graph-dp`, using the current branch's existing
group assembler, dependency certificates and bounded source-union prefetch as the
reference. No raw-directory operator, managed U03 job, native export or renderer
was run. All measurements below are retained-evidence REPLAY, not fresh qualification.

## Changes and invariants

`GroupCandidateAssembly` now returns immutable `CandidateSnapshot` / `CandidateTrace`
objects. Failed constructors still publish no partial update. A snapshot owns a
stable tuple of frozen rows and immutable Shapely geometry; subsequent trials cannot
change prior snapshots. The checker derives row changes by identity, rather than
trusting a caller-supplied delta. Every new row receives geometry, source-core hash,
identity and original-width validation. Unchanged immutable rows retain those facts.
Ordinary mutable sequences retain the full reference validation path.

`SeparatorWidthScene` builds its partition from the actual newly loaded source
context. It does not load historical graph files or hardcode crop/whole-board IDs.
It uses the conservative maximum-envelope **AABB report-dependency graph**, because
passing-pair distance fields may vary even when the tighter feasibility-only graph
can prove that the pair will never violate clearance. Current and previous bounds
are filtered exactly, retaining all fixed objects. Out-of-domain candidates fall
back to the existing complete index.

The full retained whole-board context produces 209 regions: 161 leaf regions with
at most 64 groups, and separator regions containing 175 groups in total. Individual
separator sizes are at most seven; accumulated leaf boundary size is at most 17.
The AABB graph has the same 22,058 edges as the earlier study. The C03 context is
partitioned independently (23 leaves, at most 57 groups per leaf).

Trial geometry, row bindings, bounds and hashes live in immutable copy-on-write
region maps. Rejections advance only the assembled trial state, while the last
passing state remains a separate immutable authority. Failed-state rollback and
final-neighbor proof vectors are compared against that authority. Changed regions
copy their own maps; unrelated regions retain their data. Local index views query
the existing maximum-envelope tree and inspect only actual candidate bounds in
that query, avoiding full current/previous array assembly for supported snapshots.

Local route certificates are conditioned on the region and boundary geometry
versions, whole source/policy/partition binding, and the original exact pointwise
context. That pointwise context additionally includes every queried variable/fixed
neighbor and dynamic visibility token. Certificates are SHA-256 checked, byte
bounded and evictable. An unavailable certificate recomputes the original predicate;
corrupt certificates reject. Final full nominal/envelope checks clear local proofs
and still execute the unchanged `PreparedWidthScene` path. Worker failures and
preparation exceptions close/drain the existing source-union workers.

The scalar solver is unchanged: same group order, ceiling-first proposals,
brackets, 1e-6 tolerance, 1..1.5 domain, final-neighbor upper proofs and complete
ledger. Geometry constructors, GEOS union operand order, finite-copper thresholds,
native write/reopen/export/reparse, audits and corruption gates remain unchanged.
No dense DP table, width discretization, new objective or source clipping is added.

## Validation

114 selected tests pass; three tests that start actual native U03 commands/exports
were explicitly deselected. The selected tests include synthetic in-process stage
ABI reconstruction, source/crop coverage, the original dependency and source-union
controls, and new immutable-state, rejection/rollback, out-of-domain index, policy,
source-width, certificate-corruption and exact full-solver parity controls.

Complete retained C03 replay: all **1,486** report hashes, the entire solver ledger
(including factors, order, decisions and upper proofs), and full final nominal and
envelope reports are exactly equal to retained evidence. This was repeated in
reference/new/new/reference order with independent checker caches.

Whole-board windows cover prefix, the largest group/root-boundary proposal,
mid-board proposals and final-neighbor upper proofs. The largest-group and boundary
windows coincide: there are **24 unique recorded trial indices**, repeated in ABBA
order. All geometry/report fields match exactly; only passing-state chain hashes
are excluded for explicitly seeded windows. This is bounded checking, not a replay
of all 27,293 whole-board evaluations.

A warm experiment first executes actual whole-board trials 0..11, preserves the
actually checked accepted state after trial 7, then repeats actual trials 8..11
32 times. Every complete report and hash must still match retained evidence. This
isolates hot-cache local updates; its repeated trial pattern is not representative
of the full search distribution. Priming and worker drainage are separately recorded.

## Timings

Medians of two runs per implementation in alternating ABBA order, seconds:

| Retained computation | Pre-change branch | Separator implementation | Interpretation |
|---|---:|---:|---|
| Complete C03 scalar solver | 18.7108 | 16.6144 | 11.2% less time / 1.126x |
| C03 setup + solver + final checks | 29.1622 | 26.8651 | 7.9% less time / 1.086x |
| Warm whole-board kernel, 128 proposals | 0.6364 | 0.2928 | 2.174x; hot repeated-window experiment |
| Warm priming, actual first 12 proposals | 31.1733 | 31.2892 | Essentially unchanged |
| Cold whole-board prefix, 12 proposals | 31.6326 | 31.3826 | Essentially unchanged |
| Cold largest group, 4 proposals | 63.2024 | 63.5811 | Essentially unchanged |
| Cold middle, 4 proposals | 97.2476 | 96.0056 | Essentially unchanged |
| Cold upper proofs, 4 proposals | 92.7388 | 93.6470 | Essentially unchanged |

C03 search validates 1,843 new immutable rows and carries 276,039 unchanged row
bindings, versus 277,882 complete-row visits in the reference preparation. The
same geometric checks/report payloads are retained. The cold windows show that
expensive source-union/geometry work still dominates. These measurements do not
establish an hours-to-minutes whole-board improvement or a new command runtime.

Parity comparisons and retained report I/O are excluded from evaluation timing;
setup and final worker drainage are explicit. Concurrent union work can overlap
parity intervals, so these are bounded diagnostics. No test/gate/threshold was
removed to improve timing. The two complete C03 reference timings also show
ordinary run variation; no statistical population claim is made from two samples.

## Reproduction and evidence

All outputs/reference snapshots must be fresh files under `out/lacie_work`.
First run `tools/Prepare_LaCie_Workspace.command`. Freeze the pre-change Git versions
of `assembly.py`, `checker.py`, `dependency.py`, `source_union.py` in a separate
reference package with `__init__.py`, using commit `ffa7618` for this study.

- `tools/benchmark_u03_separators.py --case <retained native directory> --reference <frozen package> --output <fresh external JSON>`: bounded windows.
- Add `--full-solver` for the complete retained C03 solver replay.
- `tools/benchmark_u03_separator_warm.py` accepts the same paths and `--cycles 32`.
- `tools/Run_PCB_Tests.command tests/test_u03_separators.py tests/test_u03_assembly.py tests/test_u03_dependency.py tests/test_u03_source_union.py tests/test_u03_dependency_graph.py tests/test_u03_board.py tests/test_u03_crops.py -q -k 'not actual_terminal_route_closes_all_33_gates_and_exports and not absolute_image_command_completes_35_native_gates_and_protects_outside and not actual_native_width_write_reopen_export_and_corruption_controls'`.

Local evidence: `out/lacie_work/evidence/u03_separator_implementation_20261104/`.
Contains frozen reference and implementation snapshots, raw ABBA samples, complete
parity flags, diagnostics, test logs (including corrected engineering failures),
versions, implementation SHA-256, preservation checks and the visual report.

Fresh U03 qualification NOT_RUN. Owner PENDING_USER; independent review
NOT_RUN: CHANNEL_UNAVAILABLE; electrical/manufacturing NOT_ESTABLISHED.
