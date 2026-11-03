# U03 incremental search assembly

The later authorized checker/index/proof layer is described in
[U03_DEPENDENCY_GRAPH.md](U03_DEPENDENCY_GRAPH.md). Statements below that the
checker/indexes are unchanged describe this earlier assembly-only slice.

User authorization, 2026-11-03: implement group-level candidate updates with the
current solver and every check unchanged, then benchmark retained cases before
another whole-board run.

`src/u03_board/assembly.py` keeps a sorted route table and the last assembled
factor vector. It validates the complete requested vector, reconstructs only
members of changed groups using the existing source constructor/cache, and
publishes replacements atomically after construction succeeds. Returned lists
remain stable across subsequent trials. The state follows the last assembled
trial, including rejected proposals; comparing the complete next vector handles
rollback, changes to multiple groups and final-neighbor upper proofs.

Only the search evaluator in `src/u03_board/width.py` uses this table. The solver,
scale brackets/order/tolerance, source constructor, clearance checker, spatial
indexes, evidence/checkpoint writes, full final materialization, fresh native
reconstruction, final-neighbor proofs, native exports and negative controls are
unchanged. No index-update or constraint-elision optimization is included.

The assembler is per-model/per-run: it cannot share geometry across source or
policy bindings. Cache entries retain exact factors without quantization. This
is a representation optimization, not a change to the coordinate-wise maximum
contract or an electrical/manufacturing qualification.

Use `tools/Run_PCB_Tests.command tests/test_u03_assembly.py tests/test_u03_board.py
tests/test_u03_crops.py tests/test_crop_data_roi.py -q -k
'not actual_terminal_route_closes_all_33_gates_and_exports'` for the focused suite.
The synthetic 35-gate native crop command is included; the real whole-board
pipeline is not launched by this selection.

`tools/benchmark_u03_assembly.py --case <retained-native-directory> --output
<absolute-LaCie-result.json> [--solver-replay]` reads retained source-bound model
and artifact references through a store that rejects writes. Prepare LaCie first
and use the existing project `.venv/bin/python -B`. Output must be in
`out/lacie_work`. The microbenchmark compares 256 retained prefix vectors with
identical precomputed actual geometry supplied as cache hits, alternates timing
order over four rounds, and verifies trace WKB equality outside the timed region.
It measures assembly only; construction, checking and I/O are excluded.

The optional solver replay executes the unchanged solver and all existing search
checks on the retained case, requiring every check hash, complete solver ledger,
final nominal check and final envelope check to equal the retained outputs.
It is read-only REPLAY, not a resumed native job, fresh export or new acceptance.
Do not use it to launch a multi-hour whole-board solver benchmark implicitly.

Evidence and timing limitations for this change are retained under
`out/lacie_work/evidence/u03_incremental_assembly_20261103T052627Z/`.
No new whole-board pipeline is authorized by this document.
