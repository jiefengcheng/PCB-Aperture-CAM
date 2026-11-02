# Fresh whole-board T01 from one raw-input directory — no rendering

Supply **one directory explicitly**. This route has no loaded-project default,
previous-job lookup, crop, screenshot, cached candidate or rendering step.
It starts fresh from the supplied KiCad/Gerber bytes and produces audited native
candidate files. Existing frozen results and T02–T05 remain unchanged.

## English, for Local Code or another agent

> Run fresh whole-board T01 using only the raw KiCad/Gerber files in “/absolute/path/to/raw-inputs”. Audit and export separate candidate KiCad and Gerber files. Do not render images or run later stages. Keep frozen results and shared clearance unchanged.

The agent reads AGENTS.md and uses the export-only facade below. If no directory
is supplied, request its path; never substitute remembered/project inputs. No
coordinator-prepared job, identifiers, bounds, policy JSON or prior result path
is required. The client supplies exact operands mechanically and the agent reads
and records each native observation, without per-step user continuation prompts.

## CLI

From this checkout, open the existing project-local native launcher once per
working session and leave its Terminal open:

```sh
open tools/Start_T01_Native_Launcher.command
```

Then start with your directory:

```sh
python3 tools/pcb_t01_board_export_operator.py start --input-dir "/absolute/path/to/raw-inputs"
```

For each REVIEW_REQUIRED result, read its actual facts and submit one observation:

```sh
python3 tools/pcb_t01_board_export_operator.py review "One observation of the returned facts"
```

There are **18 distinct observation gates**. Each review accepts only the current
technical observation and executes the next permitted slice. Poll an existing
running command until it finishes; do not launch another command concurrently.
Do not use a shell loop to invent or prefill successful observations. Long native
construction/reconstruction operations report elapsed waiting. At REPORT_AND_STOP,
return the supplied Markdown and links and stop. A failed gate halts and retains
its evidence; no retries, shortened source, alternate input or policy workaround.

After successful completion, the same review command returns the verified cached
report without reconstruction, export or rendering. An unfinished or failed job
cannot be replaced silently. All T01 facades share one managed job slot and lock;
use the facade matching the active profile. No MCP, network service, global
configuration or dependency installation is introduced.

## Directory contents

Example only; actual filenames are arbitrary and nested folders are allowed:

```text
raw-inputs/
  board.kicad_pcb
  Gerbers/
    front.gbr
    back.gbr
    front-mask.gbr
    ...
```

Exactly one `.kicad_pcb` and a uniquely geometry-qualified F.Cu Gerber are required.
The client sends only the supplied directory path through the file mailbox. It
never searches or opens the external input directory. The native macOS launcher
performs all inventory, qualification and staging with its OS access. Native
access denials retain the exact errno, failing path and a request/response receipt;
EPERM is not automatically diagnosed as TCC. The operator cannot grant OS access.
After this launcher update, close its existing Terminal and reopen
`tools/Start_T01_Native_Launcher.command` once; later directories need no setup.

The exact-X2 profile remains supported unchanged. Legacy 3.3/4.6 absolute-mm
Gerbers are identified against fresh native plots of the supplied KiCad source.
The bounded flat-import model uses original object counts to select candidate
layers, then complete ordered vector image comparison in the original coordinates.
Rectangular-aperture line draws use their exact swept rectangle, including
diagonal segments; the generic circular equivalent-width approximation is rejected.
No filename guessing, registration fitting, screenshots or raster rendering is
used. Both directed containments include islands and holes. Obsolete positive
`IPPOS` and non-semantic `LN` declarations are recorded explicitly and normalized
only in memory. Arc endpoint projection is bounded by the supplied coordinate
grid; input-correspondence tolerance, tessellation and one-nanometre Boolean
precision are recorded separately from unchanged copper-clearance policy.
Duplicate/ambiguous matches or an unqualified F.Cu pair halt.

Under the user-adopted companion policy, every unmatched Gerber is snapshotted,
hash-bound and explicitly excluded from T01 and geometry qualification. Its layer
identity remains NOT_ESTABLISHED. Byte-identical companion copies are returned
separately at completion; they are not claimed as qualified/regenerated layers.
All files are accounted for. Non-PCB files and symlinks reject; `.DS_Store` is
listed as ignored metadata. Only the explicit supplied root is traversed.

The actual files are copied byte-for-byte into a fresh immutable job snapshot,
with a full relative-path/role/size/SHA-256 manifest. The source directory remains
read-only. Native source plotting uses a separate byte-identical work copy,
keeping KiCad-generated preference files outside the immutable input snapshot. Snapshot file-set, role and hash changes reject. Renaming the same
bytes cannot bypass a retained failed-job latch. “Raw” means the explicit supplied
inputs, with no implicit use of old candidates; it does not certify the original
authoring history of user-provided bytes.

## Audits and outputs

1–3: Independent fresh KiCad/Gerber correspondence for every participating layer,
explicit companion accounting and three additional source-correspondence controls, geometry-derived
whole-board F.Cu scope, complete source/alias coverage and three omission/window
negative controls. No image location or rendering budget is involved.

4–13: Supported 16-clause T01 compilation, complete paginated discovery and
inspection, source-bound allocation/port/concentric proofs, fresh construction,
separate fresh source reconstruction, complete paginated comparison, pending owner
review, unsupported-English negative control and verified-candidate handoff.

14–18: Native KiCad write, separate reread, actual nine-layer Gerber export,
reparse of every target/protected layer and three deliberate export corruptions.

The profile exposes only those 18 operations plus submit/info/receipt/observation
tools. No rendering operation or T02–T05 call is available. Successful completion
creates candidate KiCad, all nine candidate Gerbers, raw-input manifest,
export checkpoint/receipt and a text/HTML audit report. **Rendering is NOT_REQUESTED**;
there is no render directory, tile allocation, SVG/PNG/PDF export, renderer call
or retained-view substitution. Native Gerber export is data output, not rendering.

## Scope and acceptance

This reuses the whole-board T01 policy/kernel, source-specific directives,
concentric handling, exact port pages, shared clearance and qualified file-grid
representation unchanged. Complete source coverage is within the supported flat
native **graphic-circle F.Cu** model; unsupported pads/vias/footprints or copper
semantics halt. Other native source contributions and eight exported layers are
protected. No fixed source/target-count cap or silently omitted pages are added.

The existing area-based clearance predicate remains distinct from a universal
strict 0.020 mm minimum-distance guarantee. File-grid normalization retains its
reported tolerances and limitations; no manufacturing or electrical approval is
implied. Owner PENDING_USER; independent NOT_RUN: CHANNEL_UNAVAILABLE;
electrical/manufacturing NOT_ESTABLISHED. Keep all frozen predecessors intact.

Contract: `contracts/operator/t01_board_export.json`.

## Automatic Terminal execution

For unattended completion, use `tools/Run_T01_Board.command --input-dir "<directory>"`.
This separately named mode replaces prose observations with explicit, evidence-derived
machine predicate audits while retaining all eighteen native gates and checkpoints.
It does not invent human/agent observations or approvals. No pre-opened launcher is
needed. See [T01_SINGLE_COMMAND.md](T01_SINGLE_COMMAND.md).
