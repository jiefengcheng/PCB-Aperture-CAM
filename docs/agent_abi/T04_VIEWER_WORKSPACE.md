# Dedicated saved T04 workspace

## Current full-board checkpoint — 2026-11-24

The dedicated grey T04 view now displays the fresh result described in
[T04_NATIVE_INTERFACE_REPAIR.md](T04_NATIVE_INTERFACE_REPAIR.md): 1,465 connection
checks, 3,205 endpoint checks, zero unresolved corners, and 23 passed native
UI workflow checks with zero treatment requests. The six owner-flagged chains
are excluded before growth; their 24 source segments remain byte-identical.
The policy text now refers to independent input copper, including overlapping
native-stroke artwork. Earlier bounded results and finding counts below remain
historical evidence. This is a full-board engineering diagnostic, without
export or production acceptance.

Select **T04 trace growth** in Gerber Viewer. It has its own T04 input,
T04 result and Comparison states; fit-board/fit-growth controls; corner and
endpoint filters; previous/next finding navigation; playback; and saved growth
limits. Source inspection and large-copper cleanup keep separate controls and
camera state. The trimming execution button is hidden in T04.

T04 comparisons begin at the authenticated cleaned input scene, not the raw
Gerber before cleanup. Therefore earlier trimming is not presented as a T04
removal. Copper stays grey; the Added edges toggle shows green outlines in both T04 result and Comparison views, with optional
removals use pink. Navigation never invokes treatment or changes policy.

Prepare an already committed full-board diagnostic using:

```sh
.venv/bin/python -B tools/viewer_t04.py --connection out/lacie_work/<connection>
```

The preparer authenticates the committed report/construction, current output
fingerprints, cleaned input scene and changed geometry bytes, then atomically
adds a separate `t04` display record to that revision's presentation envelope.
It does not modify construction, report, source artwork or acceptance. Existing
raw-source comparison and cleanup records remain separate.

Implementation: `src/viewer_abi/t04_workspace.py`, the typed `T04Workspace`
reader in `viewer/Sources/ViewerCore/BoardGrowth.swift`, and dedicated controls
in `viewer/Sources/GerberViewer/Resources/t04.js`. The canvas renderer and native
source inspection remain shared infrastructure.

Qualification: `out/lacie_work/t04_dedicated_view_20261124_01/`: 18 focused Python
tests, 20 native reader tests, and 21 actual viewer workflow checks pass. The
native checks include all three display states, grey copper, mode isolation,
complete finding coverage, playback advancement, preserved saved data and zero
treatment requests. Native UI evidence and screenshots are in `ui_final/`.

The current saved result retains 104 corner records and 22 endpoint records.
This viewer does not resolve them or promote the diagnostic to T04 acceptance.

## Bounded eligibility and continuity review — 2026-11-24

The same dedicated T04 workspace can display authenticated bounded T04
construction. Both the heading and status explicitly say **bounded**. The
saved 80% independent-broad-fill threshold appears with the nominal width
cutoff. Place filters separate unresolved corners/endpoints, kept routes and
admitted smoothed chains. A kept-route entry shows its measured coverage;
a smoothed-chain entry refers to the saved common profile and passed local
checks. These review entries do not count as unresolved findings.

New evidence: `out/lacie_work/t04_eligibility_smoothness_20261124_01/` and
`out/lacie_work/t04_eligibility_smoothness_bounded_20261124_03/`. The six-route
construction has 24 passed endpoint checks and zero unresolved corners. It is
bounded evidence only. Copper remains grey in original, corrected and
comparison states. Preparation computes display differences once; interaction
only navigates saved records and invokes no geometry treatment.
