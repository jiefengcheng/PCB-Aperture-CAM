# KiCad playbook

## 1. Install and pin

Use a stable KiCad 10.x build. The official site announced 10.0.7 on 2026-10-07.
Record the actual installed version, OS and CLI help. This suite has not been run inside
KiCad. Use the official documentation listed in PUBLIC_ASSETS.md rather than assuming
all development-branch APIs are available in the installed release.

```sh
kicad-cli --version
kicad-cli pcb drc --help
kicad-cli pcb export gerbers --help
```

On a standard macOS installation, the CLI is commonly under
`/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`; confirm the path exists.
The export wrapper accepts `--cli` for nonstandard installations.

## 2. Open an isolated copy and inspect the schema

Copy a fixture project directory to a working folder. Open coupon.kicad_pro and its PCB.
Confirm that the four pads, five tracks, four openings and outline are present.
Inspect CPN1's pad numbers/nets and the coordinates against geometry.json.
The synthetic board uses one populated copper layer and no holes. B.Cu exists as an empty
board layer; this is not a multilayer demonstration.

The four pads intentionally have F.Cu ONLY. No pad-derived F.Mask or F.Paste is enabled.
The openings are independent board-level filled F.Mask rectangles, line width 0, locked.
A nonzero graphical outline width would expand their effective boundaries.

In a new GUI-built equivalent, create a project-local contact footprint with four pads,
assign N1 to pads 1/2 and N2 to pads 3/4, draw the specified tracks and independent openings,
and verify all values numerically. A supplied net-intent manifest can be used for a coupon;
add a matching schematic later for a PCB-schematic parity demonstration.

## 3. Prevent a moving reference

Do not leave the target opening generated from the moving pad. A mask-expansion setting
of zero does not freeze the opening; it only makes its boundary match the current pad.
For all writable pads disable their automatic mask apertures, and put the authoritative
opening geometry in separate locked board graphics. Do not group them with the copper
for a move operation. Also ensure no track-derived mask aperture is enabled.

For solder mask, F.Mask can represent the fixed opening artwork.
For coverlay, keep role, side, opening-vs-material polarity and units explicit. For this
visualization experiment one may map a coverlay-opening specimen to F.Mask, but this is
only a geometry surrogate, not a statement that coverlay and solder mask are the same
material or that KiCad's manufacturing metadata is correct for coverlay.
Alternatively keep an authoritative external coverlay Gerber and use User.1 for reference;
never relabel its output as a finished coverlay file without checking plot semantics.

Freeze the baseline plotted aperture as well as its JSON geometry. In the baseline plot,
confirm that web-width/merging or any other plot setting did not change the intended shape.
Keep these settings fixed for every subsequent candidate. Do not relax them to pass checks.

## 4. No-edit round trip

Save/reopen a migration copy, run DRC, plot F.Cu/B.Cu/F.Mask/Edge.Cuts, then reopen outputs in
GerbView. Compare geometries against the unedited baseline, including the declared origin
and coordinate transform. Headers or object ordering may change; raw file equality and
geometric equality are separate checks. Hash original files regardless.

Only after this passes should a geometry change be called a repair experiment.

## 5. Manual replay before automation

Start from 'before'. Do not move the entire footprint. Edit pad 1's local X from 0.35 to
0.05 while keeping its local Y=0, size=1.4x1.8, layer=F.Cu and net=N1.
Keep the parent footprint at (20,20).
Replace only the three authorized trace segments with:

- (20.05,20.00) -> (20.05,21.50), width 0.25, N1.
- (20.05,21.50) -> (20.00,21.55), width 0.25, N1.
- (20.00,21.55) -> (20.00,23.00), width 0.25, N1.

The downstream segment from (20,23) to (20,26) stays fixed.
Use numeric properties instead of visual alignment. Do not use unrestricted shove routing:
it can solve a local problem by moving an object outside the authorization set.

Check the mask rectangles remain at the old coordinates. Save candidate separately.
Compare the edited object identities, nets and geometry. A library update can overwrite
local pad changes, so do not update footprints during this experiment.

## 6. Native checks and plotting

Run the supplied export_kicad.py on before and candidate, or equivalent commands:

```sh
kicad-cli pcb drc --format json --severity-all --exit-code-violations \
  -o drc.json coupon.kicad_pcb
kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Mask,Edge.Cuts \
  --precision 6 --no-protel-ext -o gerbers/ coupon.kicad_pcb
kicad-cli pcb export ipcd356 -o candidate.d356 coupon.kicad_pcb
```

DRC exit 5 means reported violations, not a tool crash. Preserve the full report and compare
violation identities/categories, not only counts. Do not omit warnings or change policy
merely to obtain a green status. Schematic parity is not tested because this coupon has no
schematic; add it only with a genuine matching schematic.

No stencil/paste or drill output is claimed by this coupon. For real jobs retain and export
all required unaffected layers and drills, along with job metadata. Do not plot Edge.Cuts
as a 'common layer' into copper or mask files; keep each manufacturing layer separate.

## 7. Exported geometry checks

Read EXPORT_VALIDATION.md. GerbView is for visual cross-checking; it does not establish
all custom registration, exposure, connectivity and scope predicates.
Gerber and IPC-D-356 exports from the same candidate are not independent proof of intent.
Keep the original design intent separately.

## 8. Then automate editing

After manual replay and native output checks work, use the version-pinned IPC API for
supported object reads and writes in a running PCB Editor. KiCad 9/10 IPC needs the GUI;
KiCad 11 headless documentation is not a promise about an installed 10.x release.
First perform a read-only capability test (pads, layers, nets, UUIDs, tracks), then one
isolated pad/trace update and save. API calls must be tested against the installed version.
The legacy pcbnew/SWIG interface is deprecated; avoid making it the new product's foundation.
Keep the constructive fixture generator separate from any real-board editing adapter.
Never mutate a customer board using regex substitutions.

## 9. Live presentation sequence

Show failing original against the fixed aperture; show the candidate's allowed object delta;
show unchanged aperture and foreign objects; reopen plotted results; show geometry metrics,
DRC results and coverage; show a broken-connection and moved-mask candidate rejected; show
unknown input causing review. Until export checks pass, call this an internal prototype,
not a validated manufacturing workflow.
