# U03 route templates and immutable hash reuse — 2026-11-04

Implemented on `codex/u03-dependency-graph-dp`, parent `b9517d64c76b1b03735e01707bd2d815d96658cb`.
All results are retained-evidence **REPLAY**. No managed U03 job, raw-directory intake,
native operation, export or renderer was run.

## Implementation and preserved checks

`src/u03_board/templates.py` prepares a route template from the original, fully
source-bound factor-1 constructor. It owns immutable source/WKB bytes, copied
route membership and manifest rows, serialized baseline records and immutable
Shapely core geometry. Each public construction call compares the current source,
chain, metadata and geometry bytes with these operands **before** any LRU hit.
Changed operands reject with `U03_ROUTE_TEMPLATE_OPERANDS_CHANGED`.

Every factor still executes the original offset algorithm: identical per-primitive
buffer operands, resolution, union order, validity, core retention, envelope
containment and area differences. The scalar domain, group assignment, search
order, width decisions, upper proofs, thresholds and final full checks are unchanged.
The original independent verifier continues to invoke `construct_source_offset_width`
directly for every selected route. No persisted artifact read/hash validation is
replaced by a template or in-memory hash hit. The implementation fingerprint
naturally includes the new module.

Operation-local geometry hashes reuse only the exact same immutable Shapely
object, retaining it to prevent identity reuse. Hash bytes remain default `to_wkb`
with SHA-256, without normalization or rounding. The new template hash memo has an
8 MiB weighted budget (twice WKB size plus entry allowance), a 4096-entry limit and
LRU eviction. This is a cache accounting bound, not a measured process-RSS bound.
The checker also reuses its existing identity memo for unchanged source-port hashes.

## Validation

**131 tests passed, 3 native tests deselected** in 12.58 seconds. The selected suite
covers source offsets, source/crop partitioning, assembly, dependency certificates,
source unions, separators and the graph. Fourteen new tests cover exact constructor
records/WKB, invalid scalars, source/chain/width/WKB mutation on cache hits, returned
record isolation, exact hash values and bounded cache eviction. The three excluded
tests start native commands or exports; they were not run. Shared geometry kernels
and all selected existing tests match the research parent byte for byte.

The publishable benchmark ran reference/candidate/candidate/reference with fresh
models/checkers. Every sample exactly matches all **1,486 retained search reports
and SHA-256 values**, the complete solver ledger, final construction records,
full nominal/envelope reports and every final primitive nominal/envelope WKB hash.
Additionally every route was compared directly with the original constructor at
factors 1, 1.125, 1.5 and its actual final factor; the mutation control rejects.

## Matched C03 measurements

Medians of two samples per mode, seconds. Assembly/check rows are solver sub-times.

| Computation | Parent branch | Templates | Time reduction |
|---|---:|---:|---:|
| Model preparation | 7.1445 | 7.4035 | -3.6% |
| Scalar solver | 17.1032 | 11.8843 | 30.5% |
| Candidate assembly within solver | 5.0088 | 1.5085 | 69.9% |
| Checks within solver | 11.8707 | 10.1535 | 14.5% |
| Full final checks and parity assertions | 7.9580 | 7.5831 | 4.7% |
| Model preparation + solver + final | 32.2057 | 26.8709 | 16.6% |

Search is 1.439x faster; the full measured
computation is 1.199x faster. Preparation is
slightly more expensive; expensive final geometry operations remain. This is a
roughly 5.3-second measured saving in this retained computation, not a claim that
the approximately 25-minute C03 command is 16.6% faster.

Unlike the previous separator study's 26.8651-second total, these totals include
**full `_model` preparation**, not only checker setup. Compare only the matched
columns here. Retained JSON loading, explicit constructor parity controls and
search-report parity/hash comparisons are outside timing; final comparisons are
inside final timing. Source-union threads may overlap untimed parity comparisons.
There are two samples per mode on one machine, without a fresh process per sample.
No whole-board or full-command speedup is established.

## Reproduction and evidence

Run from the repository root on the research branch, after
`tools/Prepare_LaCie_Workspace.command`. Freeze the parent's private package on
LaCie, then invoke the new read-only benchmark with a fresh LaCie output path:

```sh
.venv/bin/python -B tools/benchmark_u03_templates.py \
  --case "$PWD/out/lacie_work/operator_routes/u03_board/managed/jobs/20261103T044515Z-236f432853b34529bfcf931c709d828b/native" \
  --reference "$PWD/out/lacie_work/evidence/u03_route_templates_20261104/reference" \
  --output "$PWD/out/lacie_work/evidence/u03_route_templates_20261104/RESULTS_NEW.json"
```

The retained reference/candidate package snapshots, executed scripts, logs and
hash-bound results are in `out/lacie_work/evidence/u03_route_templates_20261104/`.
`--candidate-code` optionally selects an isolated private package; the default is
this checkout's `src/u03_board`. The artifact store rejects writes. Failed replay
assertions produce a separate failure receipt and do not change retained jobs.

- Results: `RESULTS_PUBLISHED.json`, SHA-256 `46748bf5cbce07aa1b4765df4a23067c3dab48ea7d4fcaac89f0b4900453ae49`.
- Published benchmark: `benchmark_u03_templates.py`, SHA-256 `ee416de1cfdf771c8b254f918bf73ded0e8a42c7d35febf8c5ea592ce1e63e25`.
- Logs: `replay_published.log`, `regression.log`, `tests_final.log`.
- Visual timing/evidence summary: `REPORT.html` (performance data only; no PCB rendering).
- `PRESERVATION.json` checks retained files, the shared index, HEAD and working files.

Python 3.14.5; Shapely 2.1.2; GEOS 3.13.1.
All 70 manifest-listed assets pass. No frozen evidence or acceptance is changed.
Owner remains `PENDING_USER`; independent `NOT_RUN: CHANNEL_UNAVAILABLE`;
electrical/manufacturing `NOT_ESTABLISHED`.
