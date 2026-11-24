# Deploy and run large-copper trimming

Start here to install the code, run a supplied Gerber, find its results, and
reopen a saved review. Docker is optional development tooling, documented
separately in the [reproduction guide](../reproduction/large_copper_0.2.0/README.md).
These instructions concern the large-copper trimming operation, not the separate
T01–T05 growth pipelines or a web-server deployment.

## 1. Choose the deployment

| Deployment | Prerequisites | Current capability |
|---|---|---|
| Existing Mac app or DMG | Apple silicon, macOS 15+, writable APFS work folder with at least 5 GiB free | Viewer and CLI trimming; Python and libraries are bundled |
| Build the app from source on Mac | Above, Git, Xcode/Swift tools, framework CPython 3.14 (recorded version 3.14.5), network for dependency setup | Build a standalone app folder; DMG creation is optional |
| Native Ubuntu/Linux source environment | Git, CPython 3.14.5, writable data folder, network for dependency setup | Baseline verification and source parsing; full trimming requires the documented Linux adapters |

The Mac application can operate offline after deployment. Keep the source
Gerber, installed app and writable work folder separate. Input files are read
without editing them; each execution stores its own source copy and evidence.
The complete tested baseline is versioned in Git; no old local dataset or job is
required. The DMG binary itself is not hosted in this repository.

## 2. Obtain and verify the code and baseline

Existing app/DMG users can go directly to step 4 with their supplied Gerber;
Git and a separately installed Python are not required to operate the app.
Clone the repository for source deployment or to obtain the versioned baseline.

Run these commands in a new directory for the clone:

```sh
git clone --branch codex/large-copper-trimming-portable-20261123 \
  https://github.com/jiefengcheng/PCB-Aperture-CAM.git
cd PCB-Aperture-CAM
git rev-parse HEAD
git status --short
python3 -B tools/check_large_copper_baseline.py
```

Record the commit and start from a clean tree. The final command needs only the
Python standard library. Expected: `PASS_SOURCE_BYTES_ONLY`, 70 verified immutable
assets, and the source SHA-256
`207a51318f103190a4d61e76f4a0457fcfd11fd3db560c9439dd2f5f460f9b90`.
The input is `baselines/large_copper_0.2.0/source.gbr` (the actual extension is
`.gbr`). This check establishes input identity, not successful trimming.

If you already have the qualified Mac app/DMG, continue at step 4. Otherwise
build the app with step 3. Ubuntu users continue at step 8.

## 3. Deploy from source on a Mac, without requiring a DMG

Install the prerequisites in step 1 first. The packaging implementation expects
a Python framework layout; a Homebrew/non-framework Python layout is different.
The recorded [Python 3.14.5 release](https://www.python.org/downloads/release/python-3145/)
and [package inventory](../reproduction/large_copper_0.2.0/macos-packages.txt)
identify the tested environment. Use the framework interpreter's actual path if
it differs from the example below.

From the clone root, in one Terminal session, replace the build-root placeholder
with a separate APFS directory you explicitly choose:

```sh
export COPPER_REPO_ROOT="$PWD"
export COPPER_BUILD_ROOT='/ABSOLUTE/APFS/CopperBuild'
mkdir -p "$COPPER_BUILD_ROOT/tmp" "$COPPER_BUILD_ROOT/cache"
export TMPDIR="$COPPER_BUILD_ROOT/tmp" TMP="$COPPER_BUILD_ROOT/tmp" TEMP="$COPPER_BUILD_ROOT/tmp"
export PIP_CACHE_DIR="$COPPER_BUILD_ROOT/cache/pip" PYTHONDONTWRITEBYTECODE=1
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 -B -m venv "$COPPER_BUILD_ROOT/venv"
"$COPPER_BUILD_ROOT/venv/bin/python" -B -m pip install --only-binary=:all: \
  -r reproduction/large_copper_0.2.0/macos-packages.txt
"$COPPER_BUILD_ROOT/venv/bin/python" -B tools/check_large_copper_baseline.py --parse
"$COPPER_BUILD_ROOT/venv/bin/python" -B tools/build_large_copper_dmg.py \
  --build-workspace "$COPPER_BUILD_ROOT" \
  --output-dir "$COPPER_BUILD_ROOT/release-01"
```

Expected: `PASS_SOURCE_INTAKE_ONLY` and 17,849 occurrences from the parser check;
then successful app construction and bundled runtime checks. The output folder
must be new. Keep `BUILD.json`, `native-dependencies.json`, `swift-build.log` and
the `qa/` receipts. The deployed folder is:

```text
release-01/image/
  Copper Trimming.app
  Run Trimming.command
  READ ME.txt
```

Open the app directly from this folder, or copy these three entries together to
your chosen installation folder. The resulting app includes Python and its
libraries; running it no longer depends on the clone's virtual environment.
The wrapper expects `Copper Trimming.app` beside it. To distribute a DMG, add
`--seal-dmg` to a build with a new output directory; see the reproduction guide.

The original development checkout retains its required LaCie workflow. Its
developers must run `tools/Prepare_LaCie_Workspace.command` and keep new build,
test, cache and job data under `out/lacie_work/`. The explicit standalone build
option above supplies another Mac's build location; it does not change the
ordinary checkout runner's storage requirements or create a silent fallback.

## 4. Run through the Mac viewer

1. If using a DMG, open it and copy the app and command wrapper together to your
   chosen folder, or open the app from the mounted image. For a source build,
   open `release-01/image/Copper Trimming.app`.
2. Choose a writable **APFS work folder**, separate from the installed app, with
   at least 5 GiB free. Jobs, caches and saved reviews stay there. Reuse this
   folder when inspecting earlier jobs; keep it at its original absolute path.
3. Click **Run large copper trimming…** and select one supported copper Gerber.
   For the reference run, select the cloned
   `baselines/large_copper_0.2.0/source.gbr`.
4. Wait for the saved trimming result to open. Progress/failure evidence is
   written in the work folder. No general-source runtime estimate is established.
5. Inspect **Original**, **Corrected** and **Comparison**. Copper under treatment
   stays grey; optional pink ghosts show removals. Previous/next, fit, object,
   status and rule filters, and Play inspect the saved result. They never execute
   treatment or change which defect families are considered.

One fixed policy considers all supported families. Unresolved findings remain
unchanged and visible; rectangular bumps are ignored. Ordinary Gerber import is
a read-only preview and does not replace the explicit **Run** action.

The app is ad-hoc signed, not Developer ID notarized. A signature/security error
must be investigated against the build receipts; these instructions do not
require disabling macOS security settings.

## 5. Run the same operation from the packaged CLI

In Terminal, change to the installed folder containing both the app and wrapper.
Use real absolute paths; the run folder must already exist on APFS:

```sh
export COPPER_WORK_ROOT='/ABSOLUTE/APFS/CopperRuns'
mkdir -p "$COPPER_WORK_ROOT"
"./Run Trimming.command" --workspace "$COPPER_WORK_ROOT" init
"./Run Trimming.command" --workspace "$COPPER_WORK_ROOT" self-check
"./Run Trimming.command" --workspace "$COPPER_WORK_ROOT" run \
  --source '/ABSOLUTE/CLONE/baselines/large_copper_0.2.0/source.gbr' --prepare-display
```

`self-check` should return `PASS_BUNDLED_RUNTIME` with exact distance 1.0 mm.
The `run` command emits progress on stderr and a JSON result on stdout. Record
its `job` and `display.workspace` fields. CLI and viewer call the same execution
implementation. `--prepare-display` saves a display derivative; it does not
launch the viewer or prove native display acknowledgement.

To use another supported source, supply that file's absolute path instead. The
baseline, its counts and the old reviewed cases are not execution inputs for an
arbitrary source. Unsupported source semantics halt with retained evidence.

## 6. Find results and reopen a saved review

By default, jobs are under the selected work folder's `large_copper_jobs/`; viewer logs are
named `large-copper-*.log` in the work folder. Use the returned job path rather
than assuming a particular UUID or selecting the newest directory.

| Saved item | Purpose |
|---|---|
| `PROGRESS.json` | Current/terminal progress and process custody |
| `source.gbr`, `source.json`, `runtime/artifacts/` | Exact source copy, source binding, content-addressed original evidence |
| `DISCOVERY.json`, `PROPOSALS.json` | Surveyed findings and proposed treatments |
| `construction.json.gz`, `RESULT.json` | Saved validated construction, verdicts, counts, policy/implementation bindings and timings |
| `DISPLAY.json`, `DISPLAY_CURRENT.json`, job-local viewer directory | Saved presentation receipts and native review data, when requested |
| `FAILED.json`, `FAILED_DISCOVERY.json`, `DISPLAY_FAILED*.json` | Retained failure evidence, when applicable |

From the installed app/wrapper folder, use the **same** work root:

```sh
export COPPER_JOB='/ABSOLUTE/APFS/CopperRuns/large_copper_jobs/RETURNED_JOB'
"./Run Trimming.command" --workspace "$COPPER_WORK_ROOT" status --job "$COPPER_JOB"
```

If a display was not requested, prepare it from the saved result:

```sh
"./Run Trimming.command" --workspace "$COPPER_WORK_ROOT" prepare-display --job "$COPPER_JOB"
```

Copy the returned `workspace` path (or `display.workspace` from `run`/`status`)
into the following variable. Do not assume it is always `JOB/viewer`:

```sh
export COPPER_DISPLAY='/ABSOLUTE/RETURNED/DISPLAY/WORKSPACE'
open -n './Copper Trimming.app' --args \
  --work-root "$COPPER_WORK_ROOT" --workspace "$COPPER_DISPLAY"
"./Run Trimming.command" --workspace "$COPPER_WORK_ROOT" status --job "$COPPER_JOB"
```

The app reads this saved session without executing trimming. After it loads,
poll `status` again if necessary: `NATIVE_DISPLAY_ACKNOWLEDGED` confirms the
native viewer acknowledged the authenticated snapshot. `PENDING_NATIVE_ACK`
means that display confirmation is still missing. Merely preparing files is not
a display PASS. Keep the full job and workspace identity marker; individual
JSON files are not a self-contained transferable job. Moving a workspace is not
a supported migration procedure because retained references are absolute.

For the supplied baseline, the recorded Mac result is **356 corrected,
77 unresolved, 24 ignored**, with 895 changed contributions, zero added copper,
275 components and 114 holes. See the [reference record](../baselines/large_copper_0.2.0/reference.json).
Counts alone do not prove geometry parity. `COMPLETED_WITH_UNRESOLVED` and
`treatment_complete=false` are expected for that reference; they do not mean all
defects were treated. The older bounded 46-case snapshot is a different result.

## 7. Handle stops and repeat requests

| Observation | Next step |
|---|---|
| Missing work folder, APFS/UUID mismatch, low free space | Restore the explicitly selected storage and inspect the error; do not substitute another directory or edit identity markers. |
| `PINNED_GEOS_*`, payload or artifact changed | Preserve the failing evidence; verify installed package/source/dependency receipts before correcting the deployment. |
| Unsupported source/ambiguous defect | Read the retained source identity and finding. Unsupported semantics are not a successful treatment; ambiguous defects remain unresolved. |
| Duplicate request returns an existing job | Inspect that retained job. Source, policy and implementation bind deduplication; another output path is not a fresh-run switch. |
| `FAILED_RETAINED` or `INTERRUPTED_RETAINED_NO_AUTOMATIC_RETRY` | Preserve the job and logs. Failed jobs are not resumed, deleted or repeatedly retried to obtain PASS. |
| Validated result but pending/failed display | Inspect display receipts and the actual native session separately. Do not rerun geometry to repair presentation. |

For diagnosis, retain the commit/build receipts, source SHA-256, full job path,
exact error, `RESULT.json` or failure files, progress and display receipts/logs.
Jobs and logs can contain source artwork and absolute paths; choose what to share
explicitly. Updating code changes implementation identity; keep prior jobs and
use a new build output directory. No export, growth or manufacturing approval is
part of this trimming workflow.

## 8. Deploy the source environment on Ubuntu/Linux, without Docker

Full Linux trimming is not implemented/qualified in this handoff. These steps
install the code dependencies and run the maintained source intake directly.
They do not depend on a Mac or Docker. Have CPython **3.14.5** available first;
point `COPPER_PYTHON` at that interpreter, then run from the clone root:

```sh
export COPPER_PYTHON='/ABSOLUTE/CPYTHON_3_14_5/bin/python3.14'
export COPPER_WORK_ROOT='/ABSOLUTE/DATA/VOLUME/CopperDev'
mkdir -p "$COPPER_WORK_ROOT/tmp" "$COPPER_WORK_ROOT/cache"
export TMPDIR="$COPPER_WORK_ROOT/tmp" TMP="$COPPER_WORK_ROOT/tmp" TEMP="$COPPER_WORK_ROOT/tmp"
export PIP_CACHE_DIR="$COPPER_WORK_ROOT/cache/pip" PYTHONDONTWRITEBYTECODE=1
"$COPPER_PYTHON" -B -m venv "$COPPER_WORK_ROOT/venv"
"$COPPER_WORK_ROOT/venv/bin/python" -B -m pip install --only-binary=:all: \
  -r requirements.lock.txt -r requirements-completion.txt
"$COPPER_WORK_ROOT/venv/bin/python" -B tools/check_large_copper_baseline.py --parse
```

Expected intake: `PASS_SOURCE_INTAKE_ONLY`, 17,849 occurrences, trimming and
native display `NOT_RUN`. Linux wheel downloads have been checked; actual native
Ubuntu execution of these steps remains NOT_RUN here. Do not present this intake
success as a full trimming run. The current full runner calls Mac workspace and
compression tools and loads a Mac-specific pinned GEOS library. The
[Linux adapter checklist](../reproduction/large_copper_0.2.0/README.md#work-needed-before-linux-can-execute-trimming)
identifies the exact files and qualification work required to proceed. There is
no supported Linux full-trimming command to substitute at this point.
