# Run the consolidated demonstration

From this checkout, run:

```bash
.venv/bin/python tools/consolidation_demo.py
```

The command records a fresh source inventory/catalog, executes the already
approved synthetic MovePadWithConnections contract, exports with the pinned
KiCad CLI, invokes the frozen independent validators, builds candidate context,
compares six actual native graph scopes, runs regressions, generates the same
workbench, verifies its snapshot files and measures the query workloads.
It takes several minutes. It neither publishes remotely nor modifies public
boards, shared native source, frozen fixtures or historical evidence.

Read the resulting `out/consolidation/demo_*/result.json`. Its `pipeline`,
`catalog_v2_result`, `native_shadows`, `benchmark` and `visual` entries identify
actual outputs; use those entries rather than guessing timestamps.
`out/consolidation/current_visual.txt` names the latest generated bundle.
The historical `out/visual/current.txt` pointer is preserved.

Open the named bundle's `index.html` directly. It includes its scene and viewer
code for offline inspection. Keep the entire directory when archiving it so
finding pages and original evidence links remain available. Verify a bundle:

```bash
.venv/bin/python tools/verify_visual_bundle.py /absolute/path/to/bundle
```

The verifier establishes current snapshot-file consistency. It does not verify
live source, authorship, manufacturing safety or independent review.

A short walkthrough uses the three existing views:

1. **Processing:** select synthetic_before, then P1. Enable Physical component
   and Modification permissions: six physically connected copper objects,
   four writable objects, P2/T4 protected. Select stages to inspect actual
   receipts, omissions and timings.
2. **Storage & indexes:** inspect P1's revision-bound record, exact source
   bytes, query and relation witnesses. Switch the recorded reference/native
   query mode; a matching recorded sample reports MATCH. Missing samples and
   unsupported scope remain explicit.
3. **Cases:** follow the synthetic execution, inspect PLANNED and the final
   retained state, and open the exact validation finding. Intermediate geometry
   that was not retained remains unavailable. Then inspect HALPI2 open/bridge
   failures and GlowStitch's unknown electrical intent.

The native adapter is SHADOW_ONLY. Source-bound query parity is not edit
permission or electrical acceptance. General selective native reassembly is
unsupported; diagnostic selections retain source artifacts and byte locators.
The original aggregate V1.5 remains NOT_ESTABLISHED. Cursor review remains
NOT_RUN: CHANNEL_UNAVAILABLE.

Native rebuild, when needed:

```bash
.venv/bin/python tools/build_native_shadow.py
```

This builds the admitted pinned copy inside the PCB output tree. The current
binary pointer supplies the default aggregate binary; `--native-binary` permits
an explicit PCB-owned binary. The binary's build receipt, input hashes and
materialization manifests remain inspectable. No shared-core changes or
power-loss durability guarantee are implied.
