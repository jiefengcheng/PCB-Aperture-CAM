# Public acquisition register

Verified at source-page level on 2026-10-14. Not downloaded or integrated into the fixture.
Public availability is not proof of unrestricted redistribution rights.

## 1. GlowStitch — realistic flex geometry, simpler than HDMI

- Source: https://github.com/sjpiper145/GlowStitch
- Author: sjpiper145; project is GlowStitch.
- Declared license in README: CC BY-SA 4.0.
- README describes editable KiCad files inside design ZIPs, including LED strips.
- Start with one small LED-strip design, not the whole panel.
- Obtain the original repository snapshot and relevant ZIP; record commit and SHA256.
- Preserve unmodified source, extract to a separate derived directory, inventory actual
  .kicad_pcb/.kicad_pro/.kicad_sch/.kicad_mod files. Do not assume every ZIP has all formats.
- Retain artwork and attribution notices. Label injected faults as SYNTHETIC, not defects
  found in the original design. Keep material/process assumptions separate from geometry.

## 2. HALPI2-HDMI-FPC — later coverlay/contact-group context

- Source: https://github.com/hatlabs/HALPI2-HDMI-FPC
- Author: Hat Labs Oy.
- Declared license in README: CERN-OHL-S v2.
- Confirmed source tree: HALPI2-HDMI-FPC.kicad_pcb, .kicad_pro, .kicad_sch, .kicad_dru,
  fp-lib-table, Connector_FPC_Gold_Finger.pretty/.
- README describes a 2-layer flex PCB and yellow coverlay, designed in KiCad 9.
- Use initially for read-only geometry and extraction of a native data specimen.
- It includes high-speed/impedance requirements. Passing this starter's geometry checks
  does NOT establish preserved HDMI operation, impedance or bend reliability.
- Do not run prepare_assembly.sh merely to inspect the source; it introduces panelization
  dependencies not needed for this experiment.

## 3. Ucamco official Gerber specimens — reader/format tests

- Source index: https://www.ucamco.com/en/gerber/downloads
- Entries checked: Gerber Layer Format - Test files; PCB fabrication data - Test file 1;
  Gerber Job Format - Sample files; XNC Format - Test files.
- Use to exercise polarity, regions, macros, units, attributes and drill handling.
- These are publicly downloadable format specimens, not a verified paired repair dataset.
- Redistribution license not established by this review; keep links/source register and
  inspect terms before bundling them in a shared commercial corpus.
- Independent viewer: https://www.ucamco.com/en/gerber/reference-gerber-viewer
- Only upload public/synthetic artifacts to web viewers without separate authorization.

## 4. Process-reading material — not the factory's policy

- Texas Instruments, QFN and SON PCB Attachment:
  https://www.ti.com/lit/slua271
  Explains solder-mask-defined and copper/non-solder-mask-defined land patterns.
  Package-specific recommendations must not become universal default rules.
- All Flex Circuit & Heater Design Guide:
  https://www.allflexinc.com/wp-content/uploads/2025/05/322822-PC-AllFlex-Circuit_Heater-Design-Guide-0408b.pdf
  Discusses coverlay materials, registration and individual/group openings.
  Read as background. Do not substitute its numbers for the partner's approved process.

## 5. Tool documentation

- KiCad 10 PCB editor: https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html
- KiCad CLI: https://docs.kicad.org/10.0/en/cli/cli.html
- KiCad GerbView: https://docs.kicad.org/10.0/en/gerbview/gerbview.html
- IPC add-on interface:
  https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/for-addon-developers/index.html
- PCB bindings status: https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/index.html
- KiCad board format: https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/
- KiCad common S-expression format: https://dev-docs.kicad.org/en/file-formats/sexpr-intro/
- Gerbonara: https://gerbolyze.gitlab.io/gerbonara/
- Gerbonara release metadata: https://pypi.org/project/gerbonara/
  Reviewed 1.6.3; Python >=3.12; declared Apache-2.0. Not installed/tested here.
- Shapely: https://shapely.readthedocs.io/
  The internal tests used 2.1.2; current web documentation may describe a newer release.

## Acquisition procedure

```sh
mkdir -p external/sources external/derived
# Inspect terms and file inventory before reuse.
git clone https://github.com/sjpiper145/GlowStitch.git external/sources/GlowStitch
git -C external/sources/GlowStitch rev-parse HEAD > external/GlowStitch.commit.txt
git clone https://github.com/hatlabs/HALPI2-HDMI-FPC.git external/sources/HALPI2-HDMI-FPC
git -C external/sources/HALPI2-HDMI-FPC rev-parse HEAD > external/HALPI2-HDMI-FPC.commit.txt
```

Inspect README and license declarations before running repository scripts. For each asset,
record source URL, acquisition time, exact commit or release, artifact paths, file hashes,
license declaration, dimensions/units/layers, conversion steps and intended use.
A public board is realistic context, not a repair oracle. A known-good manufactured board
is also not automatically compliant with the newly invented fixed-aperture constraint.
