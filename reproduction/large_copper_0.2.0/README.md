# Reproducing and learning from Copper Trimming 0.2.0

For general installation and day-to-day operation, start with
[Deploy and run large-copper trimming](../../docs/LARGE_COPPER_DEPLOY_AND_RUN.md).
It covers source deployment, viewer/CLI execution, saved results and reopening,
including a native Ubuntu setup path without Docker. This document supplies the
additional package-rebuild and Docker-development details.

This handoff includes the complete committed implementation, the tested
[`source.gbr`](../../baselines/large_copper_0.2.0/source.gbr), recorded
[reference results](../../baselines/large_copper_0.2.0/reference.json), package
versions, the Mac app/DMG build script, and a Linux Docker development recipe.
Bit-identical DMG reproduction is not required. The native viewer and DMG builder
are macOS software. **End-to-end Linux trimming is not yet qualified**: the
Docker recipe below exercises source intake and supplies a starting environment;
the platform adapter work is listed explicitly below.

See [QUALIFICATION.md](QUALIFICATION.md) for checks actually executed for this
handoff and the separate checks that remain NOT_RUN.

## Get the source

```sh
git clone --branch codex/large-copper-trimming-portable-20261123 \
  https://github.com/jiefengcheng/PCB-Aperture-CAM.git
cd PCB-Aperture-CAM
git rev-parse HEAD
git status --short
python3 -B tools/check_large_copper_baseline.py
```

Build from a clean checkout and record its commit. The builder copies the current
source tree, so local modifications enter the payload. The original source
delivery was `ebb898638d8f644051da416db952aaa74249c42b`; this branch also carries
later scoped work and these reproduction materials. No local `dataset/`, `out/`,
hidden environment, previous job, live viewer connection or untracked module is
required to obtain the baseline. No Git LFS or DMG download is needed.

## Ubuntu / Linux: Docker development and source intake

Use an existing Docker installation on the Ubuntu host. The container uses a
Debian-based official Python image; an Ubuntu host does not require an Ubuntu
base image. The [Python image](https://hub.docker.com/_/python) and
[Dockerfile documentation](https://docs.docker.com/reference/dockerfile/) describe
the base and build mechanism. The recipe pins CPython 3.14.5 and the repository's
Python package versions; it does not freeze Debian apt repositories or promise
identical image bytes. Adjusting dependencies creates a new environment to test.

Run from the repository root; choose an existing writable data volume with space
for the eventual jobs. This example creates a new work namespace there:

```sh
docker build -f reproduction/large_copper_0.2.0/Dockerfile \
  -t pcb-copper-dev:0.2.0 .
mkdir -p /ABSOLUTE/DATA/VOLUME/copper-work/tmp /ABSOLUTE/DATA/VOLUME/copper-work/cache
docker run --rm --read-only --network none \
  --user "$(id -u):$(id -g)" \
  --mount type=bind,src=/ABSOLUTE/DATA/VOLUME/copper-work,dst=/work \
  pcb-copper-dev:0.2.0
```

The default command is `tools/check_large_copper_baseline.py --parse`. Expected:
`PASS_SOURCE_INTAKE_ONLY`, source SHA-256 ending `f9b90`, and 17,849 occurrences.
It uses the existing source parser and coordinate oracle. It does **not** execute
trimming, create a qualified result, or run the Mac viewer. The Docker build
requires network access; the shown source-intake run has networking disabled.
`Dockerfile.dockerignore` and selective COPY statements exclude datasets, jobs,
local environments and user files. Clone cleanly to avoid copying local source
edits. A Docker daemon was unavailable on the authoring Mac; a successful native
intake check is recorded, but the container build itself remains **NOT_RUN**.

An interactive development shell uses the same explicit writable mount:

```sh
docker run --rm -it --read-only --network none \
  --user "$(id -u):$(id -g)" \
  --mount type=bind,src=/ABSOLUTE/DATA/VOLUME/copper-work,dst=/work \
  pcb-copper-dev:0.2.0 /bin/sh
```

### Work needed before Linux can execute trimming

The geometry/discovery/cleanup implementation is Python, but the 0.2.0 runtime
is deliberately fail-closed around its Mac platform. Installing dependencies
alone does not make `tools/run_large_copper.py` a Linux command.

| Boundary | Current implementation | Required Linux adaptation |
|---|---|---|
| Workspace identity | `src/cleanup_runtime.py`, `src/gerber_u05/workspace.py`: sealed Mac package/APFS UUID or verified LaCie image using diskutil/hdiutil | Add a separate explicit container profile and persistent workspace identity, reject missing/substituted storage, and retain free-space checks. Never silently fall back to `/tmp` or internal storage. |
| Native distance kernel | `src/indexed_polygon_distance.py`: exact Mac wheel GEOS C dylib path and SHA-256 | Select and hash-pin the matching Linux wheel's bundled ELF GEOS libraries per architecture. Record Shapely/GEOS versions and binary hashes; no generic system-library fallback. |
| Evidence encoding | `src/gerber_u05/storage_encoding.py`: APFS compression via ditto | Declare POSIX file encoding for the explicit Linux profile. Preserve exact logical-byte verification, reserve checks, fsync, immutable publication and byte budgets. |
| Process ownership | `src/stage_abi/store.py`: fcntl locks and ps process-start identity | Validate Linux process ownership/restart behavior; procps is installed in the development image. Preserve duplicate-job and retained-failure rules. |
| Memory reporting | `src/large_copper_runner.py`: macOS ru_maxrss reported in bytes | Linux ru_maxrss is KiB; convert the diagnostic and label the platform. Do not increase existing context budgets. |
| Display | Swift/AppKit/WebKit native viewer, `viewer/Package.swift` targets macOS 15+ | Keep native display `NOT_RUN` on Linux. Saved results can inform a future Linux reviewer, but no web snapshot or CLI success is a genuine native display ACK. |

Keep adapters at these boundaries and route CLI execution through the same
`src/large_copper_runner.py` implementation. Bind native platform/library identity
into any new persisted cache format; authenticate reopen and reject corruption.
Do not bypass guards by inventing a Mac package marker or changing the hardcoded
GEOS hash to accept an arbitrary system library. The Docker recipe is a learning
environment, not an implemented substitute for those adapters.

[native-wheel-reference.json](native-wheel-reference.json) supplies the observed
Mac arm64 and Linux amd64/arm64 Shapely wheel/library hashes. Wheel hashes were
checked against PyPI metadata, and the Mac GEOS C bytes match the existing
runtime pin. Linux hashes are porting references only; no Linux library was
loaded or approved by that check.

After porting, run the supplied baseline through fresh intake, preparation,
discovery, construction and assembled validation. Retain source/revision/policy
bindings, all source contributions, exact witnesses, KEEP cases and unresolved
findings. Compare geometry and per-source changes; matching the counts alone is
insufficient. Compare cross-platform WKB byte equality separately from geometric
equivalence at the existing tolerances. Preserve failed jobs, test duplicate
execution, restart, corrupt artifact/cache rejection, publication and memory
boundaries. No tolerance relaxation or acceptance promotion is implied here.

## Mac: build a new app and DMG

Requirements: Apple silicon, macOS 15+, Xcode/Swift tools, and a **framework build
of CPython 3.14**. The recorded app used CPython **3.14.5**, NumPy **2.5.4**,
gerbonara **1.6.3**, Shapely **2.1.2**, and bundled GEOS **3.13.1**. The original
app's installed distribution inventory is [macos-packages.txt](macos-packages.txt).
The [official Python release](https://www.python.org/downloads/release/python-3145/)
supplies the Mac installer. The builder expects `sys.base_prefix` to contain the
Python framework binary, stdlib and Resources; a Homebrew/non-framework Python
layout is not interchangeable with this packaging implementation.

On another Mac, explicitly create a separate APFS build directory, then use it
for the environment, pip cache, temporary files and outputs. Substitute actual
absolute paths below. No global settings or LaCie UUID edits are necessary:

```sh
export COPPER_BUILD_ROOT='/ABSOLUTE/APFS/BUILD/FOLDER'
mkdir -p "$COPPER_BUILD_ROOT/tmp" "$COPPER_BUILD_ROOT/cache"
export TMPDIR="$COPPER_BUILD_ROOT/tmp" TMP="$COPPER_BUILD_ROOT/tmp" TEMP="$COPPER_BUILD_ROOT/tmp"
export PIP_CACHE_DIR="$COPPER_BUILD_ROOT/cache/pip" PYTHONDONTWRITEBYTECODE=1
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 -B -m venv "$COPPER_BUILD_ROOT/venv"
"$COPPER_BUILD_ROOT/venv/bin/python" -B -m pip install --only-binary=:all: \
  -r reproduction/large_copper_0.2.0/macos-packages.txt
"$COPPER_BUILD_ROOT/venv/bin/python" -B tools/check_large_copper_baseline.py --parse
"$COPPER_BUILD_ROOT/venv/bin/python" -B tools/build_large_copper_dmg.py \
  --build-workspace "$COPPER_BUILD_ROOT" \
  --output-dir "$COPPER_BUILD_ROOT/rebuild-01" --seal-dmg
```

The build root must already exist, be a writable APFS directory separate from
the checkout, and have at least 5 GiB free. An existing output directory is never
overwritten; choose a new one for a changed implementation. The explicit build
adapter applies to packaging only. Ordinary checkout execution and tests retain
their LaCie requirements. On the original development checkout, prepare storage
with `tools/Prepare_LaCie_Workspace.command` and use an output under
`out/lacie_work/`; no internal fallback is authorized.

The script verifies all 70 immutable asset files, seals the code payload,
relocates framework dependencies, keeps pinned GEOS bytes intact, audits native
dependencies, ad-hoc signs the app, checks its bundled runtime offline, and (with
`--seal-dmg`) creates and verifies the read-only compressed image. It creates
fresh Swift cache directories, including on a clean clone.

Retain `BUILD.json`, `native-dependencies.json`, `swift-build.log`,
`qa/INIT.json`, `qa/SELF_CHECK.json`, `dmg-create.log`, `dmg-verify.log` and
`DMG.json`. The image is not Developer ID notarized. The synthetic integrity
assets are bundled; the client baseline stays in the cloned source and is
selected explicitly in the viewer. No historical job or client source is
silently embedded into the app.

Open the new DMG, open **Copper Trimming.app**, select an APFS work folder, click
**Run large copper trimming…**, and choose the versioned `source.gbr`. The
viewer and CLI call one execution implementation. Inspect saved grey
Original/Corrected/Comparison views; filters and Play only navigate saved results.
Wait for the actual native display ACK. App construction/runtime checks and DMG
checksum verification do not substitute for this viewer baseline run.

The corresponding packaged CLI, from the mounted image folder:

```sh
"./Run Trimming.command" --workspace /ABSOLUTE/APFS/RUN/FOLDER init
"./Run Trimming.command" --workspace /ABSOLUTE/APFS/RUN/FOLDER run \
  --source /ABSOLUTE/CLONE/baselines/large_copper_0.2.0/source.gbr --prepare-display
"./Run Trimming.command" --workspace /ABSOLUTE/APFS/RUN/FOLDER status --job /ABSOLUTE/SAVED/JOB
```

Keep the run folder in place: saved references are absolute. An identical
source/policy/implementation request returns its retained job, including a
failure; choosing another output path must not bypass duplicate-job protection.

## Reference result and scope

The recorded Mac result has 356 corrected, 77 unresolved, 24 ignored findings,
895 changed contributions, zero added copper, and 0.15143175658548183 mm² removed.
It preserves 275 connected components and 114 holes. All 17,849 final contribution
bytes matched the tested source runner and both physical Macs' packaged viewer
runs. All 46 earlier reviewed removal witnesses were covered; three reviewed
KEEP windows and the ignored rectangle were preserved. The larger generic result
is not whole-result byte equality to the older bounded 46-case snapshot.

Trimming considers every supported family deterministically. No execution family
switches: family/rule filters are viewing controls only. Preserve the strict
whole-physical-protrusion area limit below 10% of the **original causing pad or
trace**, aggregate overlapping contributions, and retain the separate shallow
trace-edge rule. Depth is bounded by 0.100 mm and circular fitting by 0.004 mm;
existing tolerances, contacts, centres/paths, protected domains and topology stay
binding. Rectangular bumps remain ignored. No growth, recess filling, rerouting
or Gerber export is part of this operation. Unsupported source families must fail
or remain explicitly unresolved.

The source baseline is intended for developing the production process; it does
not establish electrical or manufacturing approval. `treatment_complete=false`,
general defect completeness is NOT_ESTABLISHED, and new generic owner review
remains pending. Native viewer qualification on Mac does not qualify Linux.

Historical DMG SHA-256:
`7bbf5b36ed0f8071fc842642edf598033f579532d9aa56bf2823a02f0a599e3f`.
That hash identifies the original 105,059,385-byte delivery, which is not stored
in Git. Rebuilds can differ in code inventory, compiler, package metadata,
signatures and image layout. Compare behavior and retained geometry evidence;
do not require matching a DMG hash or construction hash containing another
implementation's bindings. See the [source checkpoint](../../docs/agent_abi/LARGE_COPPER_DELIVERY_CHECKPOINT.md)
and [portable delivery evidence](../../docs/agent_abi/PORTABLE_LARGE_COPPER_DMG.md)
for the distinction between the scoped commit and the historical package payload.
