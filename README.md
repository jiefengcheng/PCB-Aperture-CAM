# PCB-Aperture-CAM-V1 — isolated Codex handoff

**Status: V1 coupon technical validation PASS / Cursor review NOT_RUN / NOT FOR FABRICATION.**

See `docs/STATUS.md` for tested coverage, evidence, commands and limitations. Implementation is in `src/`; actual exported baseline and negative controls are retained under `out/`.

This is an independent experiment to validate a bounded copper-pad-and-trace adjustment relative to a frozen solder-mask aperture. The original synthetic coupon includes a generated **before** state (P1 X=20.35 mm) and a generated **candidate** state (P1 X=20.05 mm). The aperture remains centered at X=20.00 mm. All dimensions and tolerances are synthetic examples, **not** factory specifications.

## Exactly what is bundled

- `assets/starter/`: the original, untouched synthetic fixture suite, its generated KiCad source boards, reference Gerbers (marked synthetic), negative examples, policies, and internal geometry tests.
- `assets/observed_before/`: **one real KiCad-exported before baseline**, `F.Cu`, `F.Mask`, `Edge.Cuts`, and `.gbrjob`. There is **no actual KiCad-exported candidate** bundled: generate it with `tools/export_native.py` before claiming exported-result acceptance.
- `assets/source_archive/`: the original synthetic starter archive; no remote cloned datasets.
- `contracts/asset_manifest.sha256`: all assets frozen by hash.
- `tools/preflight.py`: stdlib-only source integrity and fixed-fixture sanity checks; **not** a general Gerber parser or validator.
- `tools/export_native.py`: optional reproducible KiCad CLI exports of source copies, producing outputs under `out/` only. KiCad isn't bundled.
- `tests/test_bootstrap.py`: runnable bootstrap tests. `docs/` contains Codex handoff, Cursor review contract, validation requirements, provenance and status.

## Quick start on your Mac (new directory / workspace)

```bash
unzip PCB_Aperture_CAM_V1_Codex_Handoff.zip
cd PCB_Aperture_CAM_V1_Codex_Handoff
python3 tools/preflight.py --output out/bootstrap.json
python3 -m unittest discover -s tests -v
# Optional: create a *new* local git repository, not a subfolder in another repo:
git init
git add .
git commit -m 'baseline: isolate synthetic PCB CAM V1 and Codex contracts'
```

Open this folder as a **NEW Codex project/task**, not inside the user's existing research repository. Paste `docs/PASTE_TO_CODEX.md` into a new Codex chat. The repository `AGENTS.md` provides mandatory scope limits.

To export both native fixtures with local KiCad:

```bash
python3 tools/export_native.py --case both
# Optional if CLI isn't on PATH:
python3 tools/export_native.py --case both --cli /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
```

Exports are written into a timestamped subdirectory of `out/native_exports/`, leaving original `assets` untouched. KiCad must be installed locally. A valid exported Gerber file is **not** automatically an acceptable PCB modification.

The intended V1 implementation may use Python 3.12+ with Shapely and Gerbonara (see `requirements-dev.txt`). Install these only into this project's virtual environment, record exact versions and licenses, and run all work inside this checkout. If Codex is cloud-only and cannot access your Mac's KiCad, do not claim native exports occurred: mark that step `NOT_RUN` and use a local Codex environment or bring back the exact native-export artifacts later.

## Ownership and boundaries

**Codex alone** coordinates planning, implementation, Cursor delegation (if an actual authenticated channel exists), commits, and acceptance. Cursor is an independent *read-only reviewer* after a frozen commit. No global Codex/Cursor config changes, no touching C7/C8/LPA/Viewer lanes, and no unrelated worktrees. If Cursor is inaccessible, record `NOT_RUN/CHANNEL_UNAVAILABLE`; do not ask a human to transfer messages between the agents.

The V1 stop line is independent geometric validation of *actual exported data*. Do not begin an autonomous KiCad editor, AI/GNN training, a PCB-to-Gerber reconstruction stack, or manufacturing sign-off.


## Public asset qualification amendment

The authorized V1.5 pass is complete with realistic validation **NOT_ESTABLISHED**. Selected GlowStitch and HALPI2 native boards export in the pinned CLI, while their geometry exceeds frozen V1 coverage. Official Ucamco examples reveal two aperture-block parser gaps. See `docs/ROADMAP.md` and `docs/V1_5_DECISION.md`; source revisions/hashes are in `contracts/public_sources.json`. Public checkouts are immutable local inputs in `external/sources/`, separate from synthetic `assets/`.


## Proposed long-term charter

See [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md) for the proposed strategic reference and [docs/CHARTER_INTEGRATION.md](docs/CHARTER_INTEGRATION.md) for reconciliation with frozen evidence and operational rules. [docs/NEXT_GATE_PROPOSAL.md](docs/NEXT_GATE_PROPOSAL.md) awaits user approval. This alignment authorizes no new implementation.


## FC-1 oracle qualification

The adopted charter reconciliations and FC-1 were approved on 2026-10-14. [FC1_DECISION.md](docs/FC1_DECISION.md) records one exact Ucamco mathematical-oracle qualification PASS. The original parser still rejects aperture blocks; realistic validation remains NOT_ESTABLISHED. No parser implementation, MC-1 or V2/V3 began.
