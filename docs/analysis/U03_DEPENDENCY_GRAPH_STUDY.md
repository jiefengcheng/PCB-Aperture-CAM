# Retained U03 whole-board dependency study — 2026-11-04

User scope: create a research branch containing the latest working codebase;
build and measure a conservative dependency graph from retained whole-board
U03 evidence; assess dynamic programming without rerunning U03.

Branch: `codex/u03-dependency-graph-dp`. Commit `2865aa0` checkpoints the then-current
source/tests/contracts/docs, including inherited U04/U05 work, as-is. This study
adds analysis code only; that checkpoint is not a new qualification of U04/U05.
Personal notes/images remain untracked. Raw client inputs and graph artifacts
remain local on LaCie; only code and this aggregate report are published.

## Inputs and graph meaning

Retained job:
`out/lacie_work/operator_routes/u03_board/managed/jobs/20261102T181757Z-db296df8190b4e4cb7f5419b82c207c6`.
Source SHA-256: `850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0`.
The complete 33-operation export checkpoint, machine proofs, read scene/geometry
artifacts and retained constructor/predicate source hashes are verified. Every
read operand is rehashed after analysis. No U03/native operation is executed.

A node is a source-qualified common-width group: 2,931 nodes / 3,123 complete
routes. The imported scene also retains 7,209 fixed objects, representing the
complete source accounting already qualified by U03. Fixed obstacles, original
contact masks and original-copper visibility masks are immutable. They create
unary restrictions; sharing a fixed obstacle does not itself create coupling.

For original route core A with width w, every supported 1..1.5 offset-checking
envelope lies within distance `r = .25*w + .00001 mm` of A. Two moving routes
can violate the existing finite-copper guard only if

```
distance(A, B) <= r_A + r_B + .02010 mm + 1e-12 mm
```

The analysis adds a 1e-8 mm positive numerical reserve, retaining uncertain
near-boundary edges. It changes no operational clearance threshold. An initial
expanded-AABB graph is refined by this necessary Euclidean-distance condition.
Edges collapse to their source groups; internal group predicates stay local.
Original masks can make retained edges harmless, so this is a conservative
supergraph, not the minimal semantic dependence graph. Conservativeness rests
on the pinned source-offset family and existing finite-geometry kernel; no
formal interval-arithmetic certification is claimed.

## Measured structure

| Measurement | AABB broadphase | Distance-refined conservative graph |
|---|---:|---:|
| Nodes | 2,931 | 2,931 |
| Edges | 22,058 | 15,903 |
| Components | 4 | 84 |
| Largest component | 2,928 | 2,831 (96.59% of nodes) |
| Treewidth, largest component | lower 16 / upper 18 | **14**, matching certified bounds |
| Validated balanced separator, largest component | 4 | **2, minimum for the 2/3 balance rule** |

The refined component sizes are 2,831, 9, 7, three of size 2, and 78 isolated
nodes. Global articulation count is 23; there are 30 bridges. The largest
biconnected block has 2,216 nodes, so articulation points alone do not reduce
everything to tiny pieces.

Removing/conditioning the two-group root separator leaves 42 components, the
largest of sizes **1,190, 1,111, 226 and 87**. The maximum remainder is below
2/3 of 2,831. All 20 articulation vertices within that giant component were
exhausted and none gives a balanced size-one cut, establishing minimum size 2.
"Conditioning" means retaining those variables and their constraints at the
subproblem boundary, never deleting their copper or fixing arbitrary widths.

Recursive decomposition with a leaf-size limit of 64 uses 42 separators,
with individual sizes **1..9** and 144 distinct separator variables. It yields
230 leaves (including the 83 originally separate small components), largest
leaf size **63**. Accumulated boundary sizes are 0..15. Of the 147 leaves within
the giant component, 96 have at most three boundary variables. These are valid
partitions, not claims of globally minimum recursive cuts.

Treewidth upper bounds use explicit elimination bags with original-edge coverage
and running-intersection checks. Minor-contraction sequences supply lower bounds
and are replay-verified. Their equality establishes treewidth 14 for this
constructed graph, not necessarily for a tighter semantic graph.

All **27,293** retained width-evaluation reports were read. Every one of the
**10,105 cross-group rejection witnesses**, on 944 distinct group edges, is
included in the refined graph. This supplements the domain-bound derivation;
observed failures alone would not establish complete dependencies.

## DP decision

There is meaningful weak coupling through small separators, despite the giant
connected component. Separator-conditioned local computation and selective
memoization are justified research directions.

Generic finite-table DP is not a practical drop-in replacement for U03's current
continuous, stable-order width search at its 1e-6 scale tolerance. In the verified
width-14 decomposition, the largest bag has 15 variables and the largest message
boundary has 14. The following are structural assignment counts, not benchmarked
solver timings or mandatory memory allocations:

| Choices per group | Largest bag assignments | Largest message entries |
|---|---:|---:|
| 2 | 32,768 | 16,384 |
| 4 | 1,073,741,824 | 268,435,456 |
| 8 | 35,184,372,088,832 | 4,398,046,511,104 |

For two choices the largest component sums to 1,532,914 bag assignments across
this decomposition: structurally tractable for a coarse binary experiment.
Four choices already require up to two GiB for one dense 8-byte message, before
geometry, other messages or transition costs. Fine width precision is much more
expensive. A coarse two-choice domain would change the current width problem
and is not implemented or authorized as an equivalent replacement by this study.
Specialized symbolic/monotone messages or lazy boundary conditioning may avoid
full tables, but require a separate exact formulation and measurement.

Recommended next algorithmic direction: incremental group assembly with local
constraint dependencies; use the measured separator hierarchy for conditional
reuse. Preserve the existing scalar search, final global reconstruction, upper
proofs and export checks until equivalence is established. No speedup is claimed
from this graph-only study.

## Reproduction and local evidence

```
tools/Prepare_LaCie_Workspace.command
.venv/bin/python -B tools/analyze_u03_dependencies.py \
  --job "$PWD/out/lacie_work/operator_routes/u03_board/managed/jobs/20261102T181757Z-db296df8190b4e4cb7f5419b82c207c6" \
  --output "$PWD/out/lacie_work/evidence/<fresh-graph-directory>"
.venv/bin/python -B tools/measure_u03_decomposition.py \
  --study "$PWD/out/lacie_work/evidence/<fresh-graph-directory>" \
  --output "$PWD/out/lacie_work/evidence/<fresh-decomposition-directory>"
tools/Run_PCB_Tests.command tests/test_u03_dependency_graph.py -q
```

Final graph evidence: `out/lacie_work/evidence/u03_dependency_graph_20261104_final/`.
Final decomposition evidence: `out/lacie_work/evidence/u03_dependency_decomposition_20261104_final/`.
The local report links graph edges, route witnesses, full bag/minor certificates,
separator memberships, retained rejection coverage and SHA-256 provenance.
Intermediate analysis evidence and the initial historical-schema error are kept.

Validation: 14 focused tests, including known graph families, balanced separators,
forged lower-bound rejection, a universal-hub case where BFS separators are poor,
sampled factor-pair geometry coverage, boundary reserve and nonfinite-bound rejection.
No new dependency was installed. No production geometry/solver policy was edited.
Owner remains PENDING_USER; independent NOT_RUN: CHANNEL_UNAVAILABLE;
electrical/manufacturing NOT_ESTABLISHED. This is retained-evidence research,
not fresh U03 qualification or DP implementation.
