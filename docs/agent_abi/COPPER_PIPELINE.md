# Joined large-copper trimming and T04, with separate workspaces

The coordinator is `tools/run_copper_pipeline.py`. It runs the existing large
copper worker, seals its completed output, then starts the existing T04 worker
with that exact input. It contains no geometry treatment. The phases keep their
own job directories, settings, reports, failure evidence and viewer heads.
All engineering storage stays on the prepared LaCie workspace.
The standalone package uses its existing explicitly selected, volume-verified
APFS work folder instead; it never selects an implicit fallback.

## Viewer execution

In the trimming workspace, **Open GBR · Trim → T04…** opens the native file
picker. Selecting a supported source starts this same coordinator once, with
`--prepare-display`. It runs trimming and T04 in separate worker processes,
then prepares both saved views. The current view stays visible while processing;
the status reports the active phase. A failed job retains its evidence and the
current view. No later stage runs after a failed predecessor.

On success, the window shows the new trimming result. **Open T04 result →**
and **← Back to trimming** switch between its saved phase workspaces. The file
picker button remains available in trimming for another source; it is hidden in
the dedicated T04 workspace. Navigation and saved view controls never execute
treatment. A new pipeline clears the preceding pair's camera/selection cache.

Duplicate completed executions reopen authenticated saved results; failed or
interrupted attempts remain blocked without automatic retry or resume. T04 uses
the existing eligibility, width, shoulder and verification policies. This UI
connector grants no new source support or manufacturing acceptance.

Standalone CLI equivalent:

```sh
"./Run Trimming.command" --workspace /ABSOLUTE/APFS_WORK run-pipeline \
  --source /ABSOLUTE/source.gbr --prepare-display
```

The interface contract is `contracts/agent_abi/copper_pipeline_v1.json`.
The seal format is `pcb-copper-phase-seal/2`, implemented in
`src/copper_phase_seal.py`. Earlier development seals of format 1 are not accepted.

## Errors and finishing findings — 2026-11-26

Stopping denotes erroneous output or missing validity evidence. The classifier
in `src/gerber_u05/output_disposition.py` separates that from finishing targets:
known optional endpoint-section mismatches and remaining sharp points are
review findings. A declined source-baseline pocket-filling proposal is also
retained for review when the existing receipts identify it and prove that
original holes and constructed groups were preserved; the rejected filling
copper is never emitted. Unknown failures remain errors.

Connection, foreign-copper spacing, source/protected-copper preservation,
nonnegative growth budgets, newly introduced bridge pockets, source custody,
kernel/resource failures and missing evidence still stop. The assembled checks
and sealed handoffs remain required. No failed check is rewritten to PASS.

The execution protocol keeps `status: COMPLETED`, with a separate `completion`
of `COMPLETED_WITH_REVIEW_FINDINGS` when applicable. The T04 result, phase seal,
coordinator result and saved grey presentation retain this outcome and the
review places. `output_valid` records the scoped validity checks; it does not
grant electrical/manufacturing acceptance, export authority or completed T05.
Historical failed jobs remain unchanged and cannot be resumed or resealed.

Positive growth excludes unchanged copper from the authenticated trimmed entry,
as well as fixed reference construction. The already assembled entry-owner
floor is reused for this distinction, without a second union/index, geometry
rounding, area exemption or spacing change. Actual new copper keeps the same
guard. Operand iteration is ordered for reproducible numerical witnesses.

## Commands

Prepare the mounted workspace first:

```sh
tools/Prepare_LaCie_Workspace.command
```

For a new, explicitly selected positive-copper source:

```sh
.venv/bin/python -B tools/run_copper_pipeline.py run \
  --source '/ABSOLUTE/source.gbr' \
  --output "$PWD/out/lacie_work/UNIQUE_JOINED_JOB"
```

To reuse an authenticated saved cleanup without executing trimming again:

```sh
.venv/bin/python -B tools/run_copper_pipeline.py run \
  --cleanup-job '/ABSOLUTE/COMPLETED_CLEANUP_JOB' \
  --output "$PWD/out/lacie_work/UNIQUE_JOINED_JOB"
```

Both commands execute T04. Add `--scope '/ABSOLUTE/scope.json'` for an explicit
bounded T04 cohort. Its `requested_routes` must be a nonempty array of unique
source-bound route IDs. Omitting scope requests a full-board diagnostic. Source
parser and treatment-family limitations still apply; this connector does not
qualify an unsupported source or complete unresolved cleanup findings.

For an independent T04 consumer, first create a cleanup output seal:

```sh
.venv/bin/python -B tools/run_copper_pipeline.py seal-cleanup \
  --job '/ABSOLUTE/COMPLETED_CLEANUP_JOB' \
  --output "$PWD/out/lacie_work/UNIQUE_HANDOFF/large_copper.output.json"
```

Pass the returned path **and its returned SHA-256**:

```sh
.venv/bin/python -B tools/run_t04_after_cleanup.py \
  --cleanup-seal '/ABSOLUTE/large_copper.output.json' \
  --cleanup-seal-sha256 'RETURNED_SHA256' \
  --output "$PWD/out/lacie_work/UNIQUE_T04_JOB"
```

Sealed mode derives its source job from the pinned producer. It excludes
`--source-job`, `--cleanup-result` and non-trimmed control arms. The earlier
explicit unsealed engineering interface remains available unchanged.

```sh
.venv/bin/python -B tools/run_copper_pipeline.py status --job '/ABSOLUTE/JOINED_JOB'
.venv/bin/python -B tools/run_copper_pipeline.py verify \
  --seal '/ABSOLUTE/JOINED_JOB/handoffs/t04.output.json' --sha256 'RETURNED_SHA256'
```

Status and verification authenticate saved bytes; neither reruns treatment nor
converts a saved producer verdict into new acceptance.

## Ownership and sealed data

A new job normally contains:

```text
JOINED_JOB/
  intake/source.gbr                 exact selected source bytes
  large_copper/                     cleanup-owned job, or explicit retained job elsewhere
  handoffs/large_copper.output.json  immutable producer seal / T04 input
  t04/                              T04-owned job
  handoffs/t04.output.json           immutable T04 output / parent cleanup seal
  PLAN.json, STATE.json, RESULT.json coordinator evidence
  *.stdout.log, *.stderr.log        separate worker execution logs
```

Seals reference bytes in producer-owned jobs; they do not duplicate native
geometry preparation into consumer scratch directories. They pin source bytes,
source binding, coordinate frame/oracle, complete source order, original and
output geometry identities, construction bytes, effective settings, reachable
catalogue/width/scene artifacts and explicit policy-file presence/absence.
The complete original occurrence inventory includes removed contributions;
zero-contribution tombstones are retained, never replaced with raw copper.
T04's input scene must match the cleanup output geometry ledger **in order**.
Its output seal pins the exact parent seal. Any altered/missing dependency,
changed policy inventory, link/escape or mismatched parent stops consumption.

The producer publishes a complete seal atomically without replacing an existing
seal. Interrupted partial files remain evidence and are never valid inputs.
The consumer checks its pin before execution and reauthenticates input custody
before writing its successful result. The source/code/policy/scope execution key
prevents another output path from bypassing a completed, failed or interrupted
attempt. A changed implementation creates a new attempt; old evidence is retained.

`out/lacie_work/shared_copper_context/` remains the single logical preparation
system, including the existing exact T02/T05 ordered boundary machinery. The
cleanup and T04 workers open that authenticated preparation with their own
native handles. Source bytes/order, precision, frame and kernel dependencies
remain owned and checked by `CopperContext`; seals do not serialize pointers or
grant cache-derived treatment acceptance. Each worker retains its native indexes
until exit. No index budget, geometry threshold or original verifier is enlarged.

The typed trim-only handoff also prevents a legacy integration error: a sealed
subtractive entry is not an additive predecessor requiring an unrelated generated
reference Gerber. The exact sealed phase type and ordered scene ledger determine
that distinction. Other predecessor families still follow their existing prior
reservation path. Source, functional, native connection, endpoint, width, pocket
and assembled-outline checks remain active.

## Separate grey viewer workspaces

Before large-copper preparation, the cleanup producer calls the existing
`gerber_u05.source_assembly.reconstruct` confirmed outer-enclosure removal.
It keeps `original.gbr` byte-identical and prepares `source.gbr` separately.
The source binding carries the original input and exact retained-atom proof
as authenticated artifacts. Only confirmed enclosing source strokes are
removed; open or inner loops remain. T04 receives the assembled source through
the usual phase seal. Pipeline locking/duplicate identity stays bound to the
original input; the result and viewer identify the assembled working source.
Existing historical cleanup jobs without this preprocessing remain readable.

```sh
.venv/bin/python -B tools/run_copper_pipeline.py prepare-display --job '/ABSOLUTE/JOINED_JOB'
```

If a display preparation failed, preserve it and prepare a separate derivative
after correcting the display implementation:

```sh
.venv/bin/python -B tools/run_copper_pipeline.py prepare-display --job '/ABSOLUTE/JOINED_JOB' --output '/ABSOLUTE/FRESH_DISPLAY_DIRECTORY'
```

The destination must be new and inside the verified workspace. The completed
phase seals are authenticated again; neither worker is executed. The failed
presentation and treatment receipts remain unchanged. Zero-area overlay wires
are omitted from display copper; every positive-area polygon is retained.

This saved-only operation returns two different `workspaces` paths. Cleanup keeps
its producer's existing dedicated large-copper view. T04 gets a new dedicated
viewer connection and compares the sealed trimmed input with its saved output;
it does not include earlier trimming in its growth difference. The T04 view uses
saved assembled images when available rather than building an extra raw-source
board comparison. Source-level identities/inspection remain available.

The same window can navigate between these saved workspaces. After display
preparation, the cleanup window's centre button reads **Open T04 result →**.
A click loads only its linked, completed T04 result; **← Back to trimming**
returns to cleanup. Each phase retains its camera, saved-place selection and
filters. Neither phase opens automatically and neither button executes treatment.
The two workspace directories and phase seals remain separate.

`phase-navigation.json` in each workspace binds the pair to the sealed pipeline
result, source SHA-256, snapshot digests and presentation-file digests. Native
navigation reads saved display bytes once and validates the target pins, source
and phase kind before changing the window. A missing or changed target retains
the current display and reports the error. No Python worker, clearance service,
geometry preparation or full-board verification runs when switching.

The returned paths can also be opened independently:

```sh
tools/Start_Gerber_Viewer.command --workspace '/RETURNED/large_copper/workspace'
tools/Start_Gerber_Viewer.command --workspace '/RETURNED/t04/workspace' --t04-only
```

Copper remains grey in both. Saved navigation, selection and Play do not execute
either phase. Display preparation reports `PENDING_NATIVE_ACK`; it never invents
a native observation. No current user viewer workspace is overwritten. A failed
presentation is retained separately and cannot resume a geometry job.

## Qualification and limits

The integration tests execute real cleanup and T04 workers on a small supported
source, reopen both seals, check exact handoff identities/shared context key,
prepare both independent viewer payloads, and block treatment calls during saved
presentation. Negative controls cover changed reports/construction/artifacts,
source order, policy injection, wrong digest/type, publication interruption,
links, invalid entries, downstream failure and duplicate attempts. The empty-arc
catalogue now records no arc coverage percentage when no arcs exist, rather
than issuing an invalid spatial query or dividing by zero.

This is execution/custody integration. T04 policy revision 4 now selects the
flexible-end shoulder constructor after its marked saved-predecessor checks;
fresh bounded qualification and a fresh client full-board run remain separate
execution gates. The coordinator does not itself qualify those geometry results,
export Gerber, finish T05 teardrops, infer net intent or promote any acceptance.
The current geometry/profile qualification and unresolved findings remain scoped
to their exact saved revisions. Independent review is NOT_RUN absent an actual
channel; electrical/manufacturing acceptance is NOT_ESTABLISHED.


## Client full-board diagnostic — 2026-11-26

`out/lacie_work/t04_shoulders_joined_20261125_01/full_board_04/` completed using
the authenticated full-board cleanup producer in `full_board_01/large_copper`.
Trimming was reused, not rerun. Source SHA-256:
`207a51318f103190a4d61e76f4a0457fcfd11fd3db560c9439dd2f5f460f9b90`.
Cleanup retained 356 corrected, 77 unresolved and 24 ignored places, without
additions. Fresh T04 passed 1,465 connection checks, 3,199 endpoint sections and
all nine marked groups. It added net 0.059648862 mm² versus the prior qualified
full-board result; final differential outline checks found zero additional
shoulders or new pockets. Genuine original terminal attachments remain for T05.

Coordinator wall was 1,532.123 seconds. Shared source and large-copper boundary
indexes were each built once. Geometry retention was 165,658,673 bytes under
the unchanged 192 MiB budget. The complete sealed result SHA-256 is
`df657d2f30b4d94043939caa216437204c90dcbc98b202150507a726567b8b63`.
Exact timings, native display acknowledgements, unresolved records and saved
comparisons are retained in that job's DELIVERY_REPORT.md and DELIVERY_RECEIPT.json.

Both separate grey native windows were displayed. T04 passed 38 native UI checks
and captured nine marked Original/Corrected viewport pairs with no treatment
requests. Cleanup passed 508 display/navigation checks; its final no-message
assertion rejected the normal `displayed` acknowledgement emitted by
`workspaceChanged`. That failure remains recorded, not promoted to PASS.
No export, T05 execution or manufacturing acceptance is implied. Owner review
remains pending and independent review was not run.
