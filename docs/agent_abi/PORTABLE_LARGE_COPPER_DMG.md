# Standalone large-copper trimming for another Mac

Start with the [general deployment and run guide](../LARGE_COPPER_DEPLOY_AND_RUN.md)
for installation, viewer/CLI steps, saved-result reopening and troubleshooting.

For a clean clone, package versions, the versioned client source baseline,
one-command DMG sealing and Ubuntu/Docker development instructions, use the
[0.2.0 reproduction guide](../../reproduction/large_copper_0.2.0/README.md).
Linux trimming is not yet qualified; that guide lists the required adapters.

Current delivery: **0.2.0**, 2026-11-23. Apple silicon, macOS 15 or newer.
The fixed Run action considers all agreed supported families. Saved object,
status, rule and circular-edge filters affect viewing only. Python 3.14.5,
gerbonara 1.6.3, Shapely 2.1.2, pinned GEOS and the native viewer are bundled.
No source checkout, Python/Xcode/KiCad installation or network is needed.

DMG: `out/lacie_work/large_copper_dmg_20261123_08/Copper_Trimming_0.2.0.dmg`.
SHA-256: `7bbf5b36ed0f8071fc842642edf598033f579532d9aa56bf2823a02f0a599e3f`.
105,059,385 bytes; image CRC verified; deep/strict ad-hoc signature verified.
The image contains no client source, historical jobs or caches. It is locally
ad-hoc signed, not Developer ID notarized. No security settings were disabled.

Fresh source execution, the local packaged viewer and a fresh viewer-only run
from the mounted DMG on the owner's MacBook Neo reproduce **all 17,849 final
source contribution bytes exactly**, including all 895 changed contributions.
The separate second-Mac read verifies all 17,514 unique original geometry blobs
against their content hashes; each saved artifact, source/scene/policy binding,
published snapshot/presentation and genuine native display ACK is authenticated.
The physical second Mac is arm64, macOS 27.0.1. Older supported macOS releases
and other physical Macs have not been tested.

Result: 356 corrected, 77 unresolved, 24 ignored; zero additions; 275 components
and 114 holes retained. The generic result covers all 46 exact reviewed removal
witnesses, preserving three reviewed KEEP windows and the ignored rectangle.
It includes additional generic discoveries, so it is **not whole-result byte
parity with the old bounded 46-case checkpoint**. That checkpoint is unchanged.
General defect completeness remains NOT_ESTABLISHED; unresolved findings remain
untreated and `treatment_complete=false`. No growth, recess filling or export.

Evidence: `out/lacie_work/large_copper_parity_fix_20261123_02/`, including
`LOCAL_PACKAGED_PARITY.json`, `SECOND_MAC_PARITY.json`,
`reviewed_parity_05/PARITY.json`, `FINAL_CODE_PARITY.json`, `tests_final.log`,
and `remote_020/reviewed_circular_comparison.png` (actual target screenshot).
See [LARGE_COPPER_EXECUTION.md](LARGE_COPPER_EXECUTION.md) for source-independent
reference selection and exact path/contact/area safeguards.

## Operate through the viewer

1. Open `Copper_Trimming_0.2.0.dmg`, then **Copper Trimming.app**.
2. Choose an APFS work folder with at least 5 GiB free. Jobs, caches and saved
   results stay there. Keep this folder at its original path; references are
   absolute and no fallback or automatic migration is allowed.
3. Click **Run large copper trimming…** and select the copper Gerber source.
4. Inspect the saved grey Original / Corrected / Comparison views. Pink ghosts
   show removals. Previous/next/fit, filters and Play inspect saved results only.

On the tested second Mac, the DMG is in `/Users/geoff/`, the source is
`/Users/geoff/Copper_Reproduction_20261123/source.gbr`, and the new work folder
is `/Users/geoff/Copper_Viewer_Work_020_20261123`. Earlier files are preserved.

A further fresh execution after closing/reopening the app in another selected
APFS workspace reproduced the same original-scene binding and changed geometry
bytes, with another genuine native display ACK. This is a fresh reexecution
test, not physical saved-result deduplication/reuse; the latter is covered by
regressions. See `remote_020/REOPEN_PARITY.json`. The local saved-navigation
receipt verifies unchanged result/construction bytes and job count after modes,
filters, fit and Play (`NAVIGATION_RECEIPT.json`).

## Historical 0.1.1 failure

The owner correctly rejected 0.1.1 because the original marked bumps were
missing. Its 246 corrected / 28 unresolved / 6 ignored second-Mac comparison
proved only parity with the partial straight-flank implementation. It is not
reviewed-bump parity. Historical package/evidence remain under
`large_copper_dmg_20261123_07/` and `remote_reproduction_20261123_01/`.
The first physical trial also exposed Foundation APFS group UUID versus diskutil
volume UUID differences. The native guard now authenticates the same diskutil
volume identity as Python, then retains native UUID/mount/device/marker bytes.
Changed/missing storage or marker substitution still stops with evidence.

## Storage isolation

The ordinary checkout retains its existing LaCie-only policy. The portable
adapter is activated by the sealed package's `PORTABLE_PACKAGE.json`, together
with an explicit workspace. An environment variable alone cannot enable it.
The selected APFS volume UUID and a workspace marker are authenticated on reopen.
The existing 128 MiB indexed and 192 MiB snapshot budgets remain; they are not
process RSS caps. All development/build/test data for this delivery stays under
the prepared `out/lacie_work/` workspace.

The package runs the same `tools/run_large_copper.py` through
`tools/portable_cleanup.py`; the adapter changes storage/bootstrap only. The
native viewer passes its selected workspace and bundled Python home explicitly.
Original source bytes, ordered polarity/holes, policy checks, retained failures,
duplicate-job protection and native display acknowledgement remain mandatory.

## Rebuild and CLI

```sh
tools/Prepare_LaCie_Workspace.command
.venv/bin/python -B tools/build_large_copper_dmg.py --output-dir out/lacie_work/UNIQUE_PACKAGE
```

The builder stages an app, command-line wrapper and README, seals the payload,
relocates CPython's framework references, verifies native dependencies/signatures
and runs an offline runtime check. The pinned GEOS binary stays byte-identical.
Seal the tested `image/` directory into a new read-only DMG using macOS disk-image
tools; retain verification and mounted-runtime checks separately. No download,
remote signing service or account access is part of this build.

From the mounted image folder:

```sh
"./Run Trimming.command" --workspace '/ABSOLUTE/WORK/FOLDER' init
"./Run Trimming.command" --workspace '/ABSOLUTE/WORK/FOLDER' run --source '/ABSOLUTE/source.gbr' --prepare-display
"./Run Trimming.command" --workspace '/ABSOLUTE/WORK/FOLDER' status --job '/ABSOLUTE/JOB'
```

The original reviewed 50-place checkpoint is preserved separately. Packaging is
not a new manufacturing, electrical, independent-review or owner acceptance.
