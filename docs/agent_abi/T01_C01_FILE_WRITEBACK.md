# C01 file write-back through the native route

User authorization: create separate KiCad and Gerber candidates through Local
Code → macOS adapter → native runner/contracts → PCB data ABI. The user then
specified geometry-based preservation and EDIT as the practical reference,
instead of preserving identical native-file bytes.

The declared working interpretation is **ORG + verified T01 geometry, using
EDIT's filled-polygon representation**. EDIT's file and geometry remain unchanged;
its unrelated copper changes are not imported. The candidate uses the verified
session305 C01 result, not a rerun or copy of EDIT copper.

## Representation and precision

The native source represents these lands as filled copper drawing objects, not
net-aware KiCad pads. Forty-two growing sites / 43 aliases become filled
`gr_poly` objects in the same form used by EDIT. Nine unchanged sites / 10 aliases
retain their native circles. The source board is parsed and reserialized with
sexpdata; protected nodes must remain semantically equal. Byte equality is not a
preservation requirement. Actual new bytes are still hashed for custody.

The KiCad/Gerber file grid is 0.000001 mm (1 nm), with six-decimal native plotting.
Simple independent vertex rounding produces invalid polygons at S01 and other
near-coincident boundaries. The writer therefore applies Shapely's documented
`set_precision(..., mode='valid_output')`. It reports raw symmetric area and
boundary changes, removed subgrid sections and before/after vertex counts. It
rejects empty, multipart or holed results and area changes beyond a perimeter/grid
bound. This is explicit file-format normalization; the verified T01 WKB, numerical
policy and shared clearance rules remain unchanged.

Both stored-file rereads compare against that declared file-grid reference.
The polygon boundary tolerance is 0.000002 mm. Unchanged native circles are
compared to the source kernel's polygonal approximation at 0.000014 mm, accounting
for source-circle and Gerber arc/buffer approximation. The output reports which
comparison each source uses. Do not call these files byte-identical or exact
high-precision WKB copies. File fidelity is distinct from a new whole-board DRC,
net intent, native electrical or manufacturing qualification.

References: [Shapely precision semantics](https://shapely.readthedocs.io/en/2.1.2/reference/shapely.set_precision.html)
and [KiCad board format](https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/).

## Operations

`tools/pcb_data_abi.py` implements the bounded `pcb-data-abi/1` interface with
three closed request fields: abi_version, request_id and operation. A digest-bound
native host registry fixes the verified predecessor, source and EDIT hashes,
output scope and authority. Operators cannot supply arbitrary paths or geometry.

The macOS profile `--profile c01-files` exposes five single-operation calls:

1. `pcb_kicad_write`: materialize the separate native candidate and target map.
2. `pcb_kicad_verify`: freshly reparse that stored file and check all 51 sites /
   53 aliases plus every protected node.
3. `pcb_gerber_export`: run the pinned KiCad CLI on source and candidate boards,
   recording executable/version/commands/stdout/stderr/exits and hashes. Export
   F.Cu, B.Cu, both masks/pastes/silkscreens, and Edge.Cuts.
4. `pcb_gerber_verify`: freshly reparse the nine candidate plots with the existing
   maintained Gerber adapter. Check all target contours, all unaffected F.Cu
   plotting primitives, eight other layer plots and file roles. No copper-derived
   registration fit is allowed: X stays X and Gerber Y maps to negative native Y.
5. `pcb_export_controls`: retain and reject three corrupted copies: incorrect
   units, missing S31 growth contour, and a changed protected F.Mask line.

Each call requires actual native checks and Local Code's response-digest-bound
observation audit before continuation. The existing stdlib client and file
mailbox are reused; no MCP, network listener or global setup is added.
The default setup profile and existing C01 construction profile retain their
scope. No T02–T05 construction occurs.

## Runtime scope

Pinned KiCad 10.99.0 executable SHA256:
`9b06a97e609f8ff61753a6e2ca5e4710572df77643630366c8c2ad1428b4b497`.
Gerbonara 1.6.3, sexpdata 1.0.2, Shapely 2.1.2 and the existing qualified native
runtime are required. No dependency lock, parser grammar or shared kernel is
modified. The local verifier handles Gerbonara 1.6.3's known empty Region
attribute factory and admits KiCad's empty TO.N declaration; named Gerber object
attributes remain explicitly outside this graphic-only profile.

Engineering preflights are distinct from actual Local Code proof. Preserve all
failed preflights and assessments under session306. Actual independent review
remains NOT_RUN: CHANNEL_UNAVAILABLE; owner and manufacturing acceptance remain
separate from file round-trip correctness.

## Observed bounded result — session 306

The engineering preflight and Local Code live route passed all five operations
and five digest-bound observation audits. Native KiCad 10.99.0 wrote nine Gerber
layers; both stored KiCad and Gerber rereads passed all 51 sites / 53 aliases.
Forty-two growing sites / 43 aliases are polygons; nine sites / ten aliases keep
circles. Unaffected F.Cu primitives and eight other layer plots are preserved.
Sixty focused tests passed. The three deliberate corruptions failed for their
expected reasons. Failed development preflights remain preserved with separate
ABI packaging/verification assessments; they are not Local Code failures.

The live operator used one instruction, zero per-step coordinator transport or
continuation prompts, and reported 10m33s total. All five audits completed at
430.403 seconds from the pre-submission marker. Source/frozen custody and the
preceding session305 evidence remain unchanged. The adapter was stopped cleanly.

Open `out/crop_dynamic_tasks/t01_file_writeback_20261031_306/index.html` for the
actual before/after file views, precision/normalization metrics, exact file links,
native commands and the candidate ZIP. These are review candidates; owner,
independent, electrical and manufacturing acceptance are not granted.

## User clarification of EDIT's role — 2026-10-31

The user clarified that EDIT is a practical production compatibility reference,
which may itself be far from an optimal representation or storage scheme. Codex
may choose a compatible scheme; copying EDIT's entire geometry or exact native
serialization is not required.

The tested C01 choice remains filled polygons for growing contours and native
circles for unchanged sites. This is a bounded, tested representation, not a
claim of optimal storage. Future representation changes should be judged by
native compatibility, geometric fidelity, preserved layer/object roles, explicit
precision, storage complexity and source/alias traceability. This clarification
does not itself require regeneration or change the existing acceptance limits.

Additive decision record:
`out/crop_dynamic_tasks/t01_file_representation_clarification_20261031_307/DECISION.json`.
Session306's sealed evidence and delivered files remain unchanged.
