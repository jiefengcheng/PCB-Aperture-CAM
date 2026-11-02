# Report-only completion — 2026-11-02

The user authorized completing the whole-board workflow with retained render
violations as failed findings, without further rendering. Use
`python3 tools/pcb_t01_board_operator.py finalize` for the current whole-board
job, or add `--job "<retained job evidence path>"`. No launcher is needed.
The normal board facade also closes an eligible pixel rejection this way.

`COMPLETED_WITH_FAILED_FINDINGS` means the operational report has finished.
It does not mean the original renderer passed. Every source/export integrity and
observation prerequisite is verified, the original native attempt stays HALTED,
and a separate completion is written outside the source job. The current record
accounts for 19 PASS native slices/observations, one FAIL pixel check, and final
controls NOT_RUN. Sixteen tiles passed, one is failed/partial, 143 are NOT_RUN.
No failed/native audit is overwritten or invented. Tolerances remain 1/5 µm.
Process exit 0 means report completion; `render_qualification: FAIL` is retained.
All other source/export/integrity/audit errors still halt. The current new
Local Code UI trial and owner acceptance remain pending.

See [the English/CLI recipe](WHOLE_BOARD_T01_RECIPE.md). The protocol below
continues to describe the full qualification path when separately authorized;
report finalization never executes its unrun operations.

# Whole-board ordinary-English T01

Say: “Apply T01 to all eligible round terminals across the entire board’s F.Cu
layer, using the loaded KiCad and Gerber inputs. Export separate candidates and
show them side by side. Retain all audits and keep frozen results, shared
clearance and T02–T05 unchanged.” No crop or user coordinates are needed.

Open `tools/Start_T01_Native_Launcher.command` once per working session and keep
its Terminal open. The existing native launcher dispatches a new explicitly
whole-board job through the worker entry script on disk, so no new setup, service,
MCP, global configuration or per-board coordinator preparation is required.
Local Code's embedded client performs file I/O only. The native runner owns the
project Python environment, actual source geometry, KiCad and ABI execution.

The agent's first command is:

```
python3 tools/pcb_t01_board_operator.py start
```

Optional replacement files use current native app-staged attachment labels via
`--kicad-attachment` and `--gerber-attachment`. No folder/desktop searches.
For every REVIEW_REQUIRED result, read the facts and submit one distinct concise
observation with:

```
python3 tools/pcb_t01_board_operator.py review "one observation"
```

Continue all 21 native slices and 21 observations without per-step permission.
Only start, review and completion polls are required. Long native operations
report elapsed waiting and actual append-only tile progress. Do not issue a
second command while one is running. On a failed gate, preserve and report the
error and stop. No retry, shortened region, changed policy, source edit or
acceptance promotion. The client returns complete final Markdown and absolute
file links; deliver it unchanged at REPORT_AND_STOP.

## Complete source and scope ownership

The PCB data ABI freshly inventories all supported F.Cu source objects, hashes
every geometry contribution and verifies correspondence to a fresh native plot
and the supplied Gerber. It derives the source bounds plus maximum T01 growth
padding directly from original geometry. It independently checks every source
identity, every eligible circle occurrence, exact alias membership and covered
concentric circles. Missing source/occurrence and shortened-window controls must
all reject. No image registration or invented screenshot qualification exists.

The supported profile is filled zero-stroke native **graphic circles** on F.Cu,
using the existing qualified graphic copper source model. Pads/vias/footprint
semantics outside that model are not silently reinterpreted as graphic circles.
Unsupported source geometry halts qualification. Other source geometry is context
and remains protected. This is complete coverage within the declared F.Cu profile,
not multilayer or electrical qualification.

The T01 whole-board dialect changes only source-selection clauses R01/R16 from
the crop dialect. Diameter classes, priorities, source-specific reviewed pairs
and recesses, neighbor interaction, strictly nested concentric handling, source
ports, numeric settings and final geometry predicates stay unchanged. The entire
eligible source pool is selected: priorities can differ from a smaller crop pool;
no frozen crop is overwritten or used as the whole-board construction oracle.
The board binding and full source pages are checked again on each native context.

## Audited pipeline

1. Source KiCad/Gerber verification.
2. Entire-board source scope derivation.
3. Complete source/occurrence scope verification and three deliberate controls.
4–12. Compile, discover, complete paginated inspection, plan, fresh run, fresh
reconstruction, complete paginated comparison, pending review and unsupported-
English negative compilation.
13. Source coverage and verified-candidate handoff, without historical oracle.
14–18. KiCad write, separate reread, native nine-layer Gerber export, reparse and
three export controls.
19–21. Complete native tile rendering, every-pixel verification and four render
controls.

All source, inspection and comparison pages contain at most 100 records. All
pages and records must be present, unique, bound and exhausted before use; there
is no fixed source/target count cap. Native execution and memory/byte/time budgets
remain finite and fail closed. Checkpoints hash-bind attempts, observations and
producer outputs; no later stage or owner decision can be injected.

## Whole-board display

`contracts/render/board.json` derives an exact rectangular tile partition from
the complete source/growth window. Tiles span at most 6 mm per axis; pixels retain
the crop physical pitch of at most 0.002 mm, at least 1280 wide, with 16 million
pixels per tile. A total two-billion-pixels-per-panel resource budget is checked
before T01 construction. Exceeding it halts rather than dropping tiles or lowering
fidelity. These are display resource limits, not target-count limits.

A native KiCad SVG is plotted once. SIPS rasterizes each source-coordinate tile;
the maintained Gerbonara parser emits true Gerber SVG curves and native SIPS
rasterizes the same tile. Both SVG viewports are checked. The original exported
Gerber stays unchanged; the parsed vector derivative is retained and hash-bound. Every pixel
of every tile is checked against geometry separately parsed from the exported
files. The existing KiCad/Gerber 0.001/0.005 mm boundary bands remain. A uniformly
empty/solid tile is admitted only when the analytic copper proves the entire
window empty/covered; a blank image of mixed copper still rejects. Tile frame,
source hash, output hashes, partition coverage and cumulative pixel counts are
all checked. Mirroring, blank image, wrong SVG viewport and altered input hash
controls remain mandatory on an analytically asymmetric mixed-copper tile.

The side-by-side board overview is downsampled navigation only. The complete tile
index opens linked pan/zoom candidate KiCad versus candidate Gerber detail panels;
no overview image is represented as a micron-resolution clearance audit.

Ordinary and vanishing-hole contours reuse the crop subgrid adapter unchanged.
The board-only exporter additionally unwraps a grid-normalized MultiPolygon only
when exactly one component remains, and preserves resolvable holes through legal
axial out-and-back cut-ins in one EDIT-compatible filled polygon. It never drops
another resolvable component or fills a real hole. Its dedicated writer/rereader
keeps one native node per original occurrence, protecting every other node.
Raw verified geometry is retained, normalization proofs are recomputed, and the
same 0.000001 mm grid, area bounds and 0.000002 mm polygon fidelity tolerance are
used. The shared/crop quantizer, native writer, parser and clearance stay unchanged.
An actual native probe of all 1408 sites/1541 occurrences verified the 13 additional
contours, including the retained hole; final fresh pipeline audits remain required.

## Acceptance and custody

The crop and board facades share one managed job slot and one native launch
bridge. A current job cannot be replaced while incomplete. Completed and failed
jobs remain read-only; failed identical inputs/code cannot retry through a rename.
Using the wrong facade for a current job reports the correct route without
marking that other job failed. No coordinator job setup per trial is needed.

A successful route is technical engineering evidence. Owner PENDING_USER,
independent NOT_RUN: CHANNEL_UNAVAILABLE, electrical/manufacturing NOT_ESTABLISHED.
The existing shared clearance predicate is area-based with fixed source ports;
passing it is not a universal strict 0.020 mm minimum-distance guarantee. Record
measured numerical limitations rather than silently strengthening that claim.

## Whole-board port evidence storage

The first actual full-board attempt stopped at the unchanged 200 MB execution
output guard: its 171 MB plan embedded 169 MB of source-port WKB as hex, then
repeated it in execution records. That failed job is retained. Board allocation
now stores every exact port geometry as a deduplicated content-addressed artifact
and every site-to-port binding in complete 100-site pages. The plan and execution
records carry the bound index. Both fresh allocation and fresh reconstruction
regenerate all port bytes from original source, exhaust all pages, verify all
geometry hashes/bytes and compare the complete allocation. This changes storage
only: no port size, exemption, clearance predicate, source selection or audit is
removed. The 200 MB attempt-output limit remains enforced by the shared runtime.

The next development run passed whole-board source construction but was explicitly
rejected before reconstruction/export after a new audit-negative exposed an empty-
reference edge case. The board-only pixel audit now rejects any foreground when
no finite-area copper exists, avoiding undefined empty-boundary distances. It
retains nearby geometry outside each tile for the unchanged physical error band;
artificial context edges are farther away than that band. The original crop audit
is unchanged. Uniform blank windows require analytic disjointness, and a blank
image of mixed copper still rejects. Regression negatives cover empty and zero-
area references with unexpected foreground. Both incomplete jobs remain retained.

The representation preflight found 12 raw multipart contours that become a single
component on the existing grid and one resolvable-hole contour. These are explicit
representation cases, not source omissions or raw geometry edits. Axial cut-ins
are re-read by the existing qualified contour interpreter, then freshly plotted
by native KiCad and reparsed from Gerber. The hole case measured 0.000000200534 mm
native Gerber Hausdorff error in the probe, below the unchanged 0.000002 mm file
polygon tolerance. Other truly separate grid components still reject. The third
incomplete development job was explicitly rejected before construction while this
representation was implemented; all failed evidence remains retained.

A fourth incomplete run passed source construction, reconstruction, native KiCad
write/read and nine-layer export, then stopped on a missing LAYERS import in the
new board-only non-copper verification loop. The import was corrected, regression
tests now visit every protected layer and reject a changed layer, and a read-only
reparse of the actual retained exports passed all 1408 sites/1541 occurrences and
eight protected layers. That replay did not write into or accept the failed job.
The final full native pipeline is executed fresh after these corrections.

Final agent-facing output is bounded: all per-file hashes remain in the full
immutable operator_ui/terminal.json custody manifest. The stdout projection
returns its verified path/hash and file count, plus the complete report Markdown
and display/export links. Nonterminal facts are unchanged. This avoids flooding
the agent with thousands of tile-file parameters while retaining all custody.

The fifth development run rendered all 160 tiles, but a new mixed-dimension
reference test exposed undefined GeometryCollection boundary distances. It was
explicitly rejected before pixel-audit acceptance. The board-only auditor now
regularizes a mixed clipping context to its exact finite-area polygon set, proves
zero area change, and audits finite polygon boundaries. Zero-area tangencies can
no longer turn NaN distances into a false pass. Correct-polygon and deliberately
wrong-foreground regressions cover this case; no source/export geometry, shared
raster module or error band changes. That incomplete job remains retained.

A sixth development run reached the full pixel audit and correctly rejected
native KiCad Gerber PNG faceting: the first tile contained 16 pixels beyond the
unchanged 0.005 mm boundary band, maximum 0.005362499 mm. DPI, antialias and higher
bitmap resolution did not fix the native curve approximation. The board-only
Gerber display now uses the qualified maintained parser's SVG curves plus native
SIPS, independently checked against separately parsed finite-width geometry.
The same tile measured 0.000781352 mm maximum mismatch. This is explicitly a new
Gerber display backend, not a change to the exported file, tolerance or clearance.
The existing crop renderer remains unchanged. Lightweight geometry previews should
precede expensive full rendering, which runs only after verified growth and files.
