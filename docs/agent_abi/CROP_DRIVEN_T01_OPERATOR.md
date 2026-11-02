# Crop-driven T01 operator

Implementation and bounded qualification are recorded separately. See the current
session312 report for the actual live-run outcome; this document alone is not a
passed Local Code, geometry, owner, independent or manufacturing gate.

## Ownership and ordinary-English entry

A user can attach a crop and say: “Apply T01 to this crop. Export the KiCad and
Gerber candidates and show them side by side.” The project operator resolves the
current attachment filename provided by the client. It must not replace a missing
attachment with a remembered example or a named crop. Explicitly supplied KiCad
and Gerber replacements can override the hash-bound loaded full-board input pair.

`tools/pcb_t01_operator.py start --attachment <current attachment filename>` creates a
fresh job, copies the three explicit/default inputs with recorded hashes, requests
a project-venv macOS runner through the native launch bridge, waits for its
hash-bound ready receipt, submits the inputs and invokes one slice. The user must
start `tools/Start_T01_Native_Launcher.command` once per working session; no
per-crop launcher or coordinator preparation is required.
Local Code's native Attach action stages the file in the project root. This
adapter uses that copy and never opens the original Desktop path. It checks only
the supplied filename, canonical Unicode spellings, and the macOS timestamp
narrow-space/ordinary-space variants, by direct path lookup without enumeration.
Different bytes across candidates halt. Missing staged bytes halt immediately.
Legacy `--crop <explicit path>` remains available for callers with a readable
file; the Local Code ordinary-English route uses `--attachment` instead. Each subsequent `review <observation>` retains the agent's
observation, checks its native receipt, submits the matching audit and invokes
only the next slice. This is a system-specific adapter over native contracts,
without MCP, network service, global settings or package installation. Same-user
mailboxes are transport and custody, not agent authentication or a sandbox.

The PCB data ABI owns all three initial operations:

1. `pcb_inputs_verify`: hash-bind source files, build a fresh native inventory,
   plot the original board through the pinned KiCad CLI, and compare the supplied
   Gerber's complete semantic primitives with that fresh plot. No registration
   fit can conceal disagreement between these two input files.
2. `pcb_roi_locate`: search the full native circle constellation, then refine the
   location against native copper. Neither an accepted crop rectangle nor old
   candidate contours supply a production search hint.
3. `pcb_roi_verify`: recompute native-mask metrics and post-fit landmark witnesses;
   exercise wrong-location, removed-interior-copper and ambiguity controls. Save
   a source-coordinate ROI, uncertainty, image/source hashes and overlay.

T01 receives the verified data receipt and fresh full-source cache. The render
ABI receives the verified ROI and this run's audited exports. Neither owns image
location. A screenshot locates a region; native source geometry supplies copper.

## Bounded location model

Initial support is red-copper screenshots, up to four detected panels, isotropic
scale, right-angle rotations and reflections, no perspective, ROI width at most
25 mm, and enough unambiguous round landmarks. Image limits are 5,000 pixels per
axis and 16 million pixels. Search uniqueness refers to the declared circle
hypotheses and scale/orientation model, not every possible image transformation.

The first engineering model required raw binary IoU >= 0.95. The stored composite
screenshot failed that gate (retained under session312/roi_probe). The v2 model
explicitly accounts for raster edge uncertainty: raw IoU >= 0.90 AND no more than
0.1% of union copper pixels disagree beyond a two-pixel boundary band along each image axis (a 5-by-5 square morphological neighborhood). At least
six and 80% of eligible post-fit circle witnesses must match within 0.020 mm.
The best distinct-location raw-IoU margin must be at least 0.10.

These are image-localization limits, not copper-clearance tolerances. The receipt
reports the raw score, outside-band score and conservative physical uncertainty
(0.005 mm plus two screenshot pixels per native X/Y axis, used for the ROI boundary membership guard). This is not an estimated Euclidean registration error. Whole features that stably intersect the ROI may expand beyond its rectangle. Native construction and shared clearance
rules are unchanged. The conditional post-fit witnesses reuse image evidence;
they are not independent registration qualification. Unsupported, ambiguous or
changed inputs stop before T01 is authorized.

## T01 policy and authority

Every admitted ROI uses the current 16-clause controlled-English policy in
`contracts/t01_crop/english.txt`. A literal compiler derives the closed policy;
arbitrary English is routed to the operator, not directly compiled into geometry.
Targets are all native filled, zero-stroke graphic circles intersecting the ROI,
including covered circles, edge features and exact aliases. An independent raw
source-span scan checks coverage. Source, inspection and comparison records use
100-record pages with complete content-addressed page indexes. There is no fixed
100-target or 20,000-source-object capacity cap. Snapshot counts determine the
registered count bounds; finite byte, time and computation budgets still apply.

All original copper supplies obstacle context. Priorities use the selected circle
pool; that pool and boundary effects are recorded. Changing selected membership
can change allocation. A crop name cannot choose a different T01 policy. Reviewed
feature pair/recess directives are keyed by the original source SHA and source
identity, so they follow those features into any ROI. Location-uncertain boundary
features and a selected member whose reviewed partner is absent stay unchanged.
The exact 0.020 mm T01 kernel and shared ABI clearance rules are preserved.

There are 21 separately observed native slices: three data-location operations,
nine T01 operations including an invalid-English control, a source/coverage
handoff check, five data export operations, and three display operations. The
handoff check does not open a frozen historical candidate oracle. Construction is
recomputed by the T01 verifier before exporting ORG + verified T01 as filled
polygons compatible with EDIT's representation. All other native objects and
Gerber layers are checked for preservation. Native export/reparse and render
fidelity/negative controls retain their existing numerical limits.

A native, audit, input-integrity or handoff failure latches the session. Preserve
its exact evidence; diagnosis and corrected execution use a new session. A failed
handoff after a passed observation has its own explicit failure record. Startup
requires at least 2 GB free; interrupted runs are never resumed or resealed.

## Acceptance boundary

Frozen C01/C02/C03, immutable assets, the f27d7c9 code baseline, the legacy T01
implementation and shared runtime remain hash-checked. No T02-T05 operation is
exposed or automatically run. The full English route, native execution, geometric
verification, export fidelity and display fidelity remain distinct claims. Owner
review stays PENDING_USER; independent review is NOT_RUN: CHANNEL_UNAVAILABLE;
electrical and manufacturing acceptance is NOT_ESTABLISHED.


## Automatic job setup (revision 313)

The managed job registry lives under `out/operator_routes/t01_crop/managed/`.
It does not import or modify the old prepared-route current pointer or session312.
A lock admits one facade command at a time. A new start cannot replace an unfinished
job. After a completed job, another start creates a new job, even for the same
input bytes. After a failed job, different inputs may create a new job; the same
inputs and implementation remain latched. A corrected implementation has a new
source fingerprint and may create a separate job, never resume the old one.

The native bridge starts a detached, same-user project Python runner, with stdin closed and
stdout/stderr retained per job. No shell, installation, network service or global
configuration is involved. Startup must complete within 120 seconds; native calls
retain their existing deadlines. The worker stops after a terminal facade outcome
or after 30 minutes without mailbox work. Interrupted workers are never restarted
automatically. A completed delivery can be read back without writing into its job.

The ordinary-English agent still must obtain the current attachment filename from
its client and perform all 21 distinct observations. Job setup does not qualify
an agent's attachment handling or imply that unsupported crops can pass location.
Only one sequential operator is supported per checkout; simultaneous chats and
stale observations from an old chat are outside this profile. Use a new chat for
a new manual trial, after the previous task has terminated.


## Native attachment ingestion (revision 314)

`tools/t01_crop_attachments.py` owns the Local Code attachment-name adapter.
It accepts the name/label from the current request, reads only the client's
project-root staged copy, and returns checked bytes plus provenance to job setup.
An absolute original pathname may be supplied as a label; only its basename is
used. Its parent directories are never opened. The job records the exact selected
name, content hash, naming rule, and `original_path_opened: false`, and saves its
own immutable copy before the native runner starts. Optional KiCad/Gerber
attachments use `--kicad-attachment` / `--gerber-attachment` through the same route.
The data ABI still owns source-pair qualification, ROI location and verification.

The app must actually expose file bytes through native attachment staging.
A vision-only image without a staged file cannot be recovered by this project;
`ATTACHMENT_BYTES_UNAVAILABLE` stops before job creation. No inference of pixels,
Desktop fallback, remembered example or manual file search is permitted.
Filename association is asserted by the current operator request, not proof of
authenticated chat membership. The adapter can bind a metadata hash when a client
supplies one; current Local Code metadata is not assumed to include such a hash.


## Embedded-host native launch boundary (revision 315)

A real manual Local Code trial failed with errno 45: embedded Python forbids OS
process operations. Revision313's normal-Python startup tests did not qualify
that host. Attachment ingestion passed, but the job halted before any native
slice. That exact failed job stays retained; there is no successful geometry claim.

The client now performs file I/O only for startup and liveness. It does not call
Popen, exec, os.kill or a shell. A separate native bridge, started by the user
through the project-local `.command` launcher, handles fixed per-job runner
launches. A heartbeat, correlated request/reply, job digest, worker status and
existing native setup/receipt checks bind the launch. Stale/missing bridge status
halts before allocating a job. Worker death or bridge replacement halts; no
process is restarted automatically. Completed jobs remain readable offline.

This once-per-session native host is a real setup requirement. It cannot be
bootstrapped by an embedded runtime that prohibits all OS process operations.
The bridge is local files only, same-user custody, not authentication or a sandbox.
No MCP, network listener, login item, installation, permission grant or global
configuration is added. Closing the launcher window stops accepting jobs and
requests its workers to stop; interrupted work remains unaccepted. Only one
launcher and one sequential operator per checkout are supported.


## Complete pagination and inventory-derived count bounds (revision 316)

The full owner's crop contains 115 canonical round sites, 120 native occurrences
and 17,849 original source objects. The prior manual job stopped at discovery
because max_targets was 100; max_source_objects 20,000 did not cause that halt.
That failed job is preserved. Neither count was a clearance or geometry rule.

New hosts produce a version2 crop binding with a content-addressed original source
inventory index. Each page holds at most 100 original source records. Every source
context read verifies index binding, page order, predecessor link, continuation,
record identities/counts and cumulative record digest against the complete scene
and native manifest. The crop binding requires a positive actual source count,
without a fixed upper count. Registered source/target bounds equal the actual
verified inventory size, so the same job cannot silently add unbound sources.

Crop-only `t01_inspect_all` and `t01_compare_all` have closed request/response
schemas under contracts/t01_crop. They page all selected records internally and
return the complete aggregate plus a bound page-index reference and page count.
The native route still offers the same 21 audited slices; its inspect/compare
slices invoke these complete-pagination verbs and independently read/check the
page indexes before presenting facts for the agent's observation. The planner
rechecks the inspection's entire page sequence and record-to-scene equality; a
first page that names all selected IDs cannot authorize planning. Comparison uses
the unchanged shared geometric comparison once, and pages all source-change
records without the legacy explicit-ID request limit.

Every page index binds source hash/manifest hash, or scene/policy/selection and
comparison inputs as appropriate. Missing/reordered/duplicate/truncated pages,
stale bindings, broken continuation and mismatched record digests halt. Page size
is transport granularity, not a total-selection limit. Pagination retains a
200 MB serialized byte budget and 3,600-second budget per write/read traversal;
existing native call and geometry computation budgets remain. This is not a claim
of unlimited memory, execution time or support for all native geometry semantics.
No shared dispatcher, shared schema, clearance rule or T02-T05 code is changed.


## Source-proven concentric nesting (revision 317; crop policy version 2)

The actual source contains separate filled F.Cu circles centered at native
(7.089, -8.796) mm, with radii 0.250060 and 0.124970 mm. They intersect the crop
edge and remain two canonical sites, not exact aliases. Their computational
centroids differ by approximately 1.04e-14 mm, below the unchanged facing-side
helper's 1e-12 mm degeneracy threshold. Version1 R02 required discovering both,
while version1 R09 attempted to assign a facing side to every pair and stopped.

Crop controlled-English version2 refines R09 only. A strictly nested original
source-circle pair within that existing center-degeneracy threshold has no defined
facing side. Keep both source identities and cores and omit only the pair's
undefined directional square constraint. Ordinary class selection, priorities,
source obstacles, fixed ports, live construction, final assembly and reconstruction
remain mandatory. Nonconcentric pairs retain their original directional rule.
Coincident pairs without strict, source-proven nesting still reject.

The crop grouping adapter records `apply_square_bound: false` only after checking
center distance, strict native-core containment and different radii/areas. Its
proof records both source IDs, both exact core hashes, measured center distance
and the threshold. The existing class-selection/promotion functions already honor
that explicit group flag; they are not modified. The full source-based verifier
recomputes the grouping and proof, so arbitrary disabled directional flags or
altered source proofs cannot pass. No artificial direction, alias merge, source
omission, clearance exemption or port expansion is introduced.

The 16-clause compiler now emits an explicit version2 policy. The crop interface
profile identifier is stable; policy dialect and implementation hashes identify
this revision. Old frozen policies/results and the legacy T01 source remain
unchanged. For the reported nested pair, ordinary outer-source clipping is
expected to retain the inner contour and the existing palette retains the outer
source radius. These outcomes must be established in each run, not assumed as a
hard-coded keep rule or imposed by source ID/crop name.


### Export precision finding during the full version2 crop trial

The first corrected geometry run passed all 115 assembled checks and source
reconstruction, then hit UNSUPPORTED_TARGET_POLYGON in file export. Two grown
contours (S33/S72 in that run) had a valid but essentially zero-width interior
ring, area approximately 1.60e-20 mm² each. Both holes collapse to empty under the
existing 0.000001 mm valid_output file grid. The verified raw T01 geometry is
retained unchanged.

A crop-only export adapter accepts such a target only if every hole independently
collapses to empty and normalization of the original raw geometry is exactly equal
to normalization of its hole-free exterior reference. All existing grid area/error
bounds remain. Significant holes, multipart output and invalid polygons still
reject. The unchanged shared native writer/verifier then uses that reference.
The source candidate reference, hole areas, direct-equivalence check and raw grid
collapse metrics are retained and recomputed during independent file reread.
No generic quantizer, native writer, Gerber parser, T01 geometry or clearance code
is changed. Subgrid tail collapse can remain visible in raw-to-grid Hausdorff
metrics; it is recorded under the pre-existing normalization policy, not hidden
or described as exact raw contour identity. File-grid round-trip verification and
native render checks remain distinct from raw T01 reconstruction.


### Physical display sampling for wider crops

The second full crop run passed raw geometry, KiCad readback, nine-layer Gerber
export/reparse and all export controls. Display verification stopped because its
fixed 1280-pixel width represented 4.889 µm per pixel: SIPS antialias coverage at
corners produced a 1.276 µm sample mismatch against the unchanged 1 µm KiCad band.
The native SVG coordinate precision was not the main cause.

Crop-only resolution now follows physical bounds: at least 1280 pixels wide and
at most 0.002 mm per pixel in either axis, bounded by 16 million pixels per panel
and 16,384 pixels per axis. The same helper chooses and validates the contract;
resource preflight runs immediately after ROI verification. For this crop the
result is 3129×2334 per panel. No coordinate fitting, geometry modification or
error-band increase is used. All pixels and all four existing render controls
still must pass; this policy does not assume that increasing resolution alone
qualifies arbitrary future geometry. The legacy C01 display route is unchanged.
An isolated native probe on the actual verified exports passed at 0.616 µm KiCad
and 4.578 µm Gerber maximum sample mismatch, below the original 1/5 µm bands.
