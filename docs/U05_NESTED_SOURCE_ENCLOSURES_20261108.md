# U05 nested source enclosures — isolated qualification

Code `c4260cf` is isolated and unintegrated. The normal app remains at `5c44b45`
(code `62664ee`), and the active 3020212849 job keeps its immutable 62664ee source.
The prepared `U05_20261108_c4260cf` release is inactive until between-jobs app
integration, an installed-path check and a separate activation receipt.

## Defect and correction

3020213110 contains a large four-stroke drawing rectangle around an 80-stroke
PCB enclosure. Preparation removed the first perimeter and stopped. Its existing
integral-source guard would reject the remaining enclosing trace before growth.
The defect was detected in source-only preflight; no full 3110 U05 job was started.

Preparation now reapplies the existing enclosure predicate after each certified
removal. Each candidate must remain a uniform closed original-stroke perimeter
around the complete remaining source, with the existing physical-component and
numerical checks. Ambiguity still halts. No inner computation region is inferred.
Every iteration consumes previously unremoved original occurrences, so the
original occurrence count bounds the process. No combination or width search is
introduced. The parser, predicate, geometry kernel and growth policies are unchanged.

Only certified positive D01 draws become D02 moves in a separate derived input.
Native source spans retain their original byte offsets. The final native atom
comparison checks all retained objects against the untouched original. Nested
receipts additionally bind each intermediate source hash and the terminal
absence of another certifiable enclosure. Single-frame and no-frame receipts
retain their existing format and exact values.

## Evidence

Evidence root:
`out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/export_inclusive_identity_01/remaining_boards_01/nested_enclosure_01/`.

- 806 focused tests pass, including nested two/three-frame cases, exact frozen
  single/no-frame receipt hashes, unaffected outside artwork, integral joints,
  channel separation, tampered receipts and mandatory removal progress.
- Three distinct native workers reconstruct actual 3110 preparation and agree.
  Exactly 84 bytes change from draw to move; all other bytes and all 4,668 retained
  native objects are unchanged. Raw source SHA is
  `8793e22ba56a798d3dfa1584ea8065891f8bfd5979d44ae895490edd204ca9e8`;
  prepared SHA is
  `5b009ef7ac1914e32309c2cc495caac81b92201e5ab952a27228ada29f0ebdd1`.
- The complete nested-frame inclusive-fill synthetic route passes all 47 fresh
  native operations: actual export/reparse, eight actual corrupted-file
  rejections, defect audit and rendering included. Its generated SHA is
  `80594c00c5e58743d31d05c83087d3326e6fbadf53b5328b0666a0141e8121a6`.
- The actual source-preparation image was inspected. Amber marks removed
  enclosures; the other source copper is unchanged. Added physical area is zero.
  This is a preparation view, not a 3110 U05 growth result.
- All 3,143 frozen source files remain unchanged. All other `src` Python files
  are byte-identical to the 62664ee release; every other source-assembly function
  is AST-identical. The failed first comparison harness is retained separately;
  the corrected harness has its own script, log and results.

Exact preparation bytes and complete receipts match on eight other source cases:

| Board | Removed strokes, old and candidate | Bytes and receipt |
| --- | ---: | --- |
| 3020212826 | 47 | Identical to retained native result |
| 3020212849 | 81 | Identical to active native job |
| 3020212868 | 48 | Identical |
| 3020212922 | 80 | Identical |
| 3020212955 | 0 | Identical |
| 3020212956 | 77 | Identical |
| 3020212960 | 78 | Identical |
| 3020213043 | 22 | Identical |

These comparisons repeat no growth stage. They establish preparation parity;
queued boards still require complete U05 processing and final two-file delivery.
No further full 3020212826 run is authorized or performed.

Authoritative receipts: `QUALIFICATION_01.json`,
`ACTUAL_3110_NATIVE_QUALIFICATION_01.json`, `source_parity_02/RESULT.json`,
`VISUAL_INSPECTION_01.json`, and the nested synthetic job's original native proofs.
Timing observations were contended diagnostics, not performance benchmarks.

## Preserved boundaries

All growth parameters, source cores, integral joints, pin slots, clear operations,
width caps, shared-gap policy, checks and budgets remain unchanged. This is not
positive-only flattening and does not fill holes or repair bridges. The 3020212866
drawing-sheet scope and the listed historical generated 3020212826 directory
remain separately pending user clarification; neither is silently dropped.

Six deferred broad-suite failures remain unwaived; the broad suite is not rerun.
`.DS_Store` custody remains **EXPLICIT_UNWAIVED_UNATTRIBUTED**. Owner PENDING_USER;
independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.
