# Real client T04 viewer demonstration

The 2026-11-21 demonstration uses the board from the active chat **T04 category-based pass optimization**: `3020301113B`, original `ORG/top_layer.gdo.gbr`. Its SHA-256 is `207a51318f103190a4d61e76f4a0457fcfd11fd3db560c9439dd2f5f460f9b90`.

The viewer loaded all 17,849 original source occurrences, then accepted a retained T03 context snapshot and a one-occurrence T04 trace-widening update through its file ABI. Green/pink artwork comparison was enabled, the affected region was focused, and an actual click selected source span `490969:490986`. This chat read the same source ID and revision from the selection outbox.

This is a **REPLAY** of one stored T04 body from `t04_board_recovery_20261120/attempt_04/full_board/construction.json.gz`, over complete T03 context. It is not the active chat's unfinished residual experiment, a whole-board T04 completion, a fresh Gerber export, or new engineering acceptance. The original input is legacy MM L3.3 with X2 stack identity NOT_ESTABLISHED. Existing source-bound geometry is used through the generic viewer ABI; the strict X2 raw importer is unchanged.

## Reopen and publish

All demo files are under the checkout's `out/lacie_work/viewer/client_t04_demo_20261121/`. Reopen the retained session with:

```sh
tools/Start_Gerber_Viewer.command \
  --workspace "$PWD/out/lacie_work/viewer/client_t04_demo_20261121/session"
```

The exact producer script is retained in that external directory. It hashes input artifacts, creates display derivatives and publishes content-addressed snapshots with an atomic `current.json`. The completed demonstration used these chat-executed commands:

```sh
.venv/bin/python -B out/lacie_work/viewer/client_t04_demo_20261121/demo.py source
.venv/bin/python -B out/lacie_work/viewer/client_t04_demo_20261121/demo.py baseline
.venv/bin/python -B out/lacie_work/viewer/client_t04_demo_20261121/demo.py trace-slice
```

They publish already prepared visualization snapshots, not T04 operations. The viewer's **Show changes**, **Fit change** and **Previous/Current** controls expose the update; click its diagonal trace to populate the inspector. Selection returns to `session/outbox/selection.json` for the chat's next read.

## Evidence and limits

- `RESULT.json`: exact revisions, selected identity, one changed object, and unchanged-input verification.
- `INPUTS.json`: 17,631 bound input hashes, rechecked unchanged after the demonstration.
- `TRACE_SLICE.json`: stored trace body and before/after measurements, with artifact hash.
- `01-original-board.png`, `03-selected-trace.png`: actual native viewer captures.
- `INITIAL_SELECTION_STALL.json`: retained initial full-scene selection stall. Viewport culling corrected the displayed-path redraw; scene coverage and payloads are retained.
- `culling-ui-check-02/ui-smoke.json`: 15 passing WebKit checks, including offscreen culling, selection, overlap cycling and holes. The scoped regression runner also passed 8 publisher and 7 native-reader tests.

Display-only simplification has a measured maximum Hausdorff error of 0.000373458 mm across prepared geometry; the selected widened trace derivative measures 0.000167215 mm. Source files and engineering WKB artifacts were not modified. This one board demonstration is not a general large-board performance qualification. Owner remains PENDING_USER; independent review NOT_RUN; electrical/manufacturing acceptance NOT_ESTABLISHED.
