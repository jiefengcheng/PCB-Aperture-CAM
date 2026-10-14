# Independent exported-result validation specification — NOT IMPLEMENTED in v0.1

This is the next code increment, not a completed capability of the supplied demo.
Use a maintained Gerber reader, such as Gerbonara (see PUBLIC_ASSETS.md), to read the ACTUAL
KiCad exports. Do not feed the validator the original JSON as a substitute for exported
geometry. The generator and internal checker here share geometry assumptions.

## Read and normalize

Declare a job-wide transformation from exported coordinates to the board-reference frame.
Check units, scale, origin, side, rotation/mirroring and file role. Establish this transform
using immutable reference geometry on a no-edit baseline and then freeze it. Do not align
copper and aperture separately or optimize the transform on the edited pad.

Resolve aperture definitions, flashes, strokes, filled regions, arcs, macros, step repeats
and sequential dark/clear polarity into filled geometry. A Gerber 'aperture' is a plotting
tool definition; it is not itself a uniquely identified physical mask window. Reject or
escalate unsupported constructs rather than ignoring them. Use declared approximation
and snap-error bounds. Keep the original vector representation alongside derived polygons.

## Checks on each actual output

1. Reference unchanged: normalized aperture geometry equals the frozen reference. Report
   boundary displacement and symmetric-difference area, not only a hash. A byte hash is
   also required for an external fixed file copied unchanged into the final job.
2. Objective: for this covered-rim coupon, A expanded by 0.10+0.05 in each axis is contained
   by the permitted pad geometry. Required exposed copper covers A. Validate both shape
   and area; equal area can hide the wrong shape or location.
3. No unwanted exposure: inspect all copper under the target opening and its uncertainty
   envelope. Use independently supplied pad/terminal/net associations; shared group windows
   require an explicit allowed exposure map rather than forbidding every second net.
4. Connectivity: reconstruct connected components from output copper and associate them
   to original stable terminal seeds. Required pairs remain connected; distinct intended
   nets must not merge. Check every terminal in the affected connected components, not
   only the chosen pair, when scaling beyond this two-net coupon. In multilayer work,
   actual plated drill/via evidence is required; this coupon excludes it.
5. Clearance and neck: check different-net distances using output filled copper. Confirm
   allowed widths and robust pad/trace junctions. Zero-area touching or a microscopic neck
   must not silently qualify as manufacturable continuity.
6. Scope: normalized copper symmetric difference must lie inside the allowed change area;
   compare native objects too, so moving protected objects inside that area is still caught.
   Compare all unrelated full-job layers and holes; a local crop cannot prove preservation.
7. Semantic consistency: output layer attributes and side mapping remain correct; preserve
   available X2/X3 object attributes and original semantics separately. Candidate-derived
   netlists are observations of the candidate, not the authority for intended connections.

A 0.001 mm comparison tolerance is an invented starting budget in this suite. Derive the
actual export/parser/arc-approximation error budget and verify it against smaller challenge
features. Never use a tolerance to heal a real gap. Count an unresolvable feature as UNKNOWN.

## Acceptance record

Record PASS/FAIL/NOT_ESTABLISHED per required check, source hashes, transformation, units,
parser version, geometry-kernel version, precision/approximation bounds, native tool version,
policy hash, authorized object IDs, full DRC report, output files and reviewer decision.
Only accept when all mandatory checks have evidence. Manufacturing signoff is a separate
human/process gate. A web viewer may be used on public/synthetic data; do not upload private
customer data without authorization.

## Next test expansion

Add rotations, oval/circular pads, multiple discrete windows, a single window exposing
multiple separate pads, clear-polarity regions, aperture macros, missing metadata, bottom
side mirrored data, an actually unrouteable fixed-obstacle case, and format round trips.
Keep synthetic perturbation labels separate from real historical defects. Generate test
variants not used in solver development. No GNN or LLM is required for these checks.
