# Bounded C01 render ABI

`pcb-render-abi/1` reads the separate session306 KiCad board and existing F.Cu
Gerber. It produces an offline side-by-side HTML view and labeled PNG. It does
not construct copper, export new manufacturing Gerbers, alter geometry, fit a
registration, run T01 or T02-T05, or grant acceptance.

The exact files and hashes, native-mm viewport, layer, dimensions, dependencies,
tool identity, raster fidelity bounds and controls are in
`contracts/render/c01.json`. Other files/crops/layers are unsupported by this
first profile. The closed JSON request contains only `abi_version`, `request_id`
and `operation`; see the adjacent request/response schemas. The native host
registry is separately hash-bound and fixes a fresh output directory under out/.

## Native execution

1. `render_c01_compare`: verify input hashes and Gerber role/units/polarity;
   execute pinned KiCad 10.99.0 `pcb export svg --layers F.Cu` with page coordinates
   retained and drawing sheet excluded. Set the SVG display viewport directly
   to the C01 native bounds, preserving plot paths. Rasterize via macOS sips-316.
   Independently invoke `gerber convert png --strict` on the existing Gerber,
   with an explicit millimetre viewport and the same 1280 x 1077 pixels.
2. `render_c01_verify`: freshly parse both stored input files with the existing
   native and maintained Gerber readers. Compare every raster pixel centre to
   the corresponding finite-width copper in the declared frame. Check SVG
   viewport, image dimensions/opacity, input and output hashes.
3. `render_c01_controls`: preserve separate mirrored-Gerber, blank-image,
   wrong-SVG-viewport and changed-input-hash controls; all must fail for their
   named reason.

Native coordinates are X right, Y down. Gerber X stays X and Gerber Y = -native Y.
The Gerber viewport origin is `(native xmin, -native ymax)`. No geometry-derived
alignment or automatic crop is admitted. Both panels use exactly the same
world-to-pixel map. The HTML synchronizes zoom/pan and reports both coordinates;
it only transforms the displayed images, not file geometry. It runs offline.

Native commands retain argv, tool hashes/version, environment, raw stdout,
stderr and exits, including failures/timeouts. The render receipt hashes the
display and plots. The route pins all delivered outputs across later calls and
observation audits. This is same-user integrity, not a security boundary against
a process that can rewrite the checkout and coordinator state.

## Display precision

Pixel pitch is about 0.002517 mm. KiCad's SVG has its plotting precision and
anti-aliasing; the native Gerber PNG renderer more coarsely approximates some
circles. Permitted pixel-classification mismatches must be within 0.001 mm of
KiCad copper boundaries and 0.005 mm of Gerber copper boundaries, respectively.
Every mismatch outside those bands is a failure. A blank/solid image, mirror,
wrong crop or changed input cannot be a silent success.

The engineering trial measured maximum mismatch distances of approximately
0.000744 and 0.003694 mm. These are raster display bounds, not modifications to
file fidelity, T01 growth or clearance policy. The session306 file-level
verification remains the numerical contour evidence. Display cannot establish
net intent, electrical isolation or manufacturing readiness.

## macOS adapter and Local Code

Start once with a fresh directory:

```sh
.venv/bin/python -B tools/t01_macos_adapter.py --session out/<fresh>/run --profile c01-render
```

Give the file-capable agent the emitted `agent_setup.json`. The existing stdlib
client and local mailbox are reused. No MCP, network listener, installed service,
package installation or global setup is added. Only the three render operations,
info, receipt verification and observation audit are exposed. Native run/verify
authority for PCB construction is not exposed.

The operator independently selects each next operation and audits its actual
response digest/facts before proceeding. One initiating instruction is sufficient;
no per-step coordinator transport is required. An observation audit establishes
consistent reading of the result, not independent geometric or human visual
acceptance. Qualification of actual Local Code use is recorded separately from
coordinator engineering preflight and unit tests.

The standard client without `--operation` retains setup conformance for setup
profiles. When the descriptor excludes conformance (including this render
profile), its default is read-only `native_route.info`. This prevents the default
entry point from requesting an unavailable setup tool. An explicit operation
still receives the real native response; there is no retry or failure fallback.

The evidence namespace is
`out/crop_dynamic_tasks/t01_render_abi_20261031_309/`.
Owner acceptance remains PENDING_USER. Independent review remains
NOT_RUN: CHANNEL_UNAVAILABLE; electrical/manufacturing remain NOT_ESTABLISHED.


## Observed session309 result

The bounded renderer and actual macOS native route pass: three native render
operations, three Local Code digest-bound observation audits, 83 focused tests
and four successful corruption controls. Each panel checks 1,378,560 pixel
centres. Measured maximum mismatch distances are 0.000743727 mm (KiCad) and
0.003694126 mm (Gerber), within the declared display-only bands. The actual PNG
was visually inspected. The offline linked-view script passes a mock-DOM logic
check; browser interaction is NOT_RUN because the app blocked local file URLs.

Local Code's broader operator qualification is **limited, not fully qualified**.
The first trial repeated excluded setup calls; the ambiguous standard-client
default was corrected and tested. A fresh trial completed all three operations
and audits with no route error or per-step coordinator transport. Afterwards,
Local Code reported extra ls/file probes outside the brief (file exit127), and a
read-only ls/git-status command appeared when it was stopped. These extra probes
are UI-observed/reported, not native-runner receipts; the last command's execution
is not established. The successful native display remains valid.

All three observation audits completed at 624.654 seconds; the native ABI
subprocesses totalled 9.354 seconds. Low-latency operation, general tool discipline
and general ABI mastery are not established. The native route constrains its own
operations; it does not sandbox another agent's tools. No further retry was made.

Seventy assets, 484 baseline code files, 19,990 frozen payloads, and the complete
session305/306 delivery manifests remain unchanged. T01's implementation and the
shared runtime fingerprints are unchanged. T02-T05 were neither modified nor
executed. Owner acceptance stays PENDING_USER; independent and manufacturing
qualification are not granted. Detailed evidence: session309/index.html and
FINAL_COORDINATOR_AUDIT.json.
