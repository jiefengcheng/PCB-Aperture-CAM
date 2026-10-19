# Client Gerber operation demonstration

This bounded case uses one supplied bottom-copper region around R140.1. The native source model is absent; the operation works directly on a hash-bound Gerber file and preserves every unselected parsed object.

## Reproduce

From this checkout:

```sh
.venv/bin/python tools/client_operation_run.py
.venv/bin/python tools/client_visual_demo.py
```

The first command creates a new operation run under `out/client_operation/` and records it in `out/client_operation/current.txt`. The second binds that run into the existing workbench and records the bundle path in `out/client_demo/current.txt`. Serve `out/visual` locally and open the generated bundle's `index.html`. The source Gerbers remain in `external/sources/12_copper_layers_pcb_gbr`; outputs, modified candidates and receipts remain under `out/`.

## Guided project story and video recording

The workbench now includes a nine-step guided story. Each step selects an existing case and stored state, relevant layers, and display mode; it never edits source files or changes a verdict. Use the guide as the canonical order for a 5–7 minute live walkthrough or the included 2:17 narrated replay: **synthetic baseline → supplied bottom copper → top-copper limitation → bounded contract → deliberate challenge → accepted candidate → open control → bridge control → evidence boundary**. The video is a replay of retained execution evidence, not live editing or whole-board CAM sign-off.

### Before recording

1. From this checkout, run `.venv/bin/python tools/client_operation_run.py` and then `.venv/bin/python tools/client_visual_demo.py`. The first generates a fresh run; the second binds its evidence into a fresh workbench bundle. Do not record if either command fails or the workbench integrity banner is not green.
2. Serve `out/visual` locally and open the `index.html` inside the path written to `out/client_demo/current.txt`. In the browser select **Client region · contract-driven copper move** and **Generated candidate · accepted**. The current bundle path is also in that pointer file.
3. Maximize the browser and hide unrelated windows/notifications. Begin with **Aperture coupon · automatic V2** selected. Then switch to **Client region · contract-driven copper move**, choose **Generated candidate · accepted**, and turn on **B.Cu**, **B.Mask openings**, **Operation roles**, **Selected expected links**, and **Permitted region**. Click **Focus R140.1**. Confirm the right side says **PASS**, and the evidence integrity banner says the embedded scene checksum is verified. Do not read version/hash details aloud unless the audience asks; they are available under **Case provenance · hashes · evidence snapshots**.

### On-camera sequence and narration

| Step | Show | Say |
| --- | --- | --- |
| 1 · Controlled starting point | **1 · Coupon**: computed candidate and stored PASS checks | “We start with a synthetic coupon where the opening, movement and expected connection are controlled. It introduces the operation and acceptance pattern; it is deliberately simple.” |
| 2 · Supplied bottom copper | **2 · Client B.Cu**: bottom copper, B.Mask opening and board outline; inspect a labelled flash | “This is the client’s supplied manufacturing artwork in millimetres. Here we can measure geometry against a mask opening, but a Gerber label is not an independent schematic.” |
| 3 · Other outer copper | **3 · Client F.Cu**: top copper and F.Mask; pause on the warning | “The other outer copper layer is present too. Its 304 zero-width interpolation warnings make this view display-only, so our operation uses the cleanly parsed bottom-copper file.” |
| 4 · Locate and constrain | **4 · Bounded operation**: outline locator, focused R140.1 region, target/dependent/protected roles and fixed mask | “The locator shows where this small region sits on the board outline. The contract names one pad, its dependent trace, a fixed opening, nearby protected copper, and a permitted edit region. These are demo limits, not client manufacturing rules.” |
| 5 · Challenge input | **5 · Challenge input**: deliberate +0.35 mm offset, compare view | “The source is already aligned. We introduce a separate, labelled 0.35 millimetre offset so there is a meaningful correction to demonstrate; this is not a defect found in the supplied board.” |
| 6 · Generated candidate | **6 · Candidate**: layer delta and all nine PASS findings; click Alignment, Connection, Separation and Change Scope | “The recorded executor moves the selected pad and permitted trace endpoint, writes and reparses a candidate Gerber, then checks this region. All nine declared local checks pass. The output returns to bytes identical to the already-aligned source.” |
| 7 · Open control | **7 · Open control**: failed connection finding and broken local path | “When the target path is interrupted, the checker identifies the required local connection failure and rejects that candidate.” |
| 8 · Bridge control | **8 · Bridge control**: protected-object and separation findings | “When copper is added toward protected geometry, the checker rejects the bridge for local separation and unpermitted geometry change.” |
| 9 · Evidence boundary | **9 · Evidence boundary**: return to accepted candidate; show stored run and limitations | “This is a bounded same-layer demonstration on supplied Gerber artwork. It does not establish whole-board or cross-layer electrical correctness, production rules, or manufacturing approval.” |
Pause briefly on each state so the audience can read PASS/FAIL. If showing the detailed source evidence link, open `result.json` and `rollback.json` in a separate browser tab before recording; avoid navigating away from the guided case during the take. The run folder is identified by `out/client_operation/current.txt`. Save the final narrated walkthrough as `out/client_operation/<run-id>/recording/workbench_project_goal_walkthrough.mp4`; retain its voiceover script and capture receipts beside it, and preserve the original evidence JSON files unchanged.

### Evidence to retain with the recording

- The screen recording, labeled **workbench replay of recorded execution**.
- `contract.json`, `result.json`, and each candidate/control `validation.json` from the exact run folder.
- `rollback.json`, which records the rejected staged candidate, prior accepted SHA-256, and unchanged accepted artifact.
- `build_receipt.json` and `scene.json` from the visual bundle, so the replay’s scene hash and code/input provenance remain reviewable.
- A note of any presentation-only changes made during recording (selected state, toggles, zoom). They do not alter the stored geometry or verdicts.

## Contract and evidence

The demo contract records exact source/mask hashes, target label `/io_drivers_fp/bank0/EN7`, fixed opening, dependent straight trace, protected R140.2, editable rectangle, maximum movement (0.40 mm), center tolerance (0.005 mm), minimum local connection width (0.18 mm), explicit local clearance (0.10 mm), and numeric area tolerance. These values define this demonstration only; they are not client requirements or production design rules.

The executor changes only the uniquely matched target D03 coordinate and the permitted trace endpoint in a copy of the Gerber source. It reparses the produced candidate. A separate validation module checks target identity/alignment/label, unchanged mask bytes, edited-feature bounds, all unselected parsed plotting objects, local connection width, local separation and movement. Region composition filters by conservative source-object bounds; this keeps whole-board Boolean geometry out of the one-region calculation without skipping source-object preservation comparisons.

Recorded results in the selected run show: supplied original aligned; controlled input rejected; generated candidate passes all nine local checks; disconnected control rejected for connection; bridge rejected for separation and additional unpermitted plot geometry; over-limit operation rejected before staging. Rejected attempts do not replace the accepted candidate. Source hashes for all 42 client files are rechecked after the run.

## Scope limits

This demonstrates one local, same-layer transformation against an explicit demo contract. Gerber X2 labels are export metadata, not independent schematic intent. Whole-board connectivity, cross-layer continuity, the ten internal copper layers, the full drill stack, production constraints and manufacturing approval remain NOT_ESTABLISHED. The top copper layer's 304 zero-width D01 warnings affect its inspection rendering; this operation uses bottom copper, which passes the strict parser/compositor. No pcb_Z or SQLite client-object import is used.

The visual bundle includes this operation and the earlier client-inspection and synthetic/HALPI2/GlowStitch cases. The historical consolidation seal is copied only as historical context; it does not seal the new client operation bundle. The generated bundle is locally inspectable and replayable. A 2:17 narrated replay was captured from nine verified read-only UI states at `out/client_operation/run_20261015T050705_750904Z/recording/workbench_project_goal_walkthrough.mp4`. It is a state-based replay, not a continuous live screen recording. Its `recording_manifest.json` records hashes, versions, commands, test results and capture details; `out/visual/client_20261015T053027_782777Z/ui_review.json` records the local presentation review. Cursor review remains `NOT_RUN: CHANNEL_UNAVAILABLE`.


Maintenance after the original recording is tracked in [CLIENT_ISSUES.md](CLIENT_ISSUES.md). New bundles use the common receipt verifier and exclude recordings/obsolete operation review notes. The original recorded video stays bound to its original bundle; `out/client_demo/current.txt` may select a newer equivalent visual delivery.
