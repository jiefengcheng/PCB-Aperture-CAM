# Temporary common frame and functional source channels

The owner clarified on 2026-11-06 that channels joined only through the end bar
must retain separation. The slim outer trace and end bar are excluded from
connectivity grouping, while all their original copper remains in the Gerber.
This supersedes the broad same-physical-component exemption for those channels.

## Evidence and actual implementation boundary

The untouched 3020212922 source contains positive-area source-contact paths from
the sampled pads/traces to a common bottom bar. The original frame is a uniform
closed cycle of 40 unique strokes, represented by 80 source occurrences.
Previous whole-board component ownership therefore grouped physically connected
channels whose local separation must be preserved.

`source_common_frame.discover` identifies the outer source cycle without a board
name, crop coordinate, or known end-bar ID. It retains every duplicate occurrence
in its certificate. It assembles functional source copper from original
non-frame occurrences, rather than subtracting independently tessellated whole
unions. This avoids fictitious sub-grid frame fragments becoming channel IDs.
Frame classification uses only the existing 2 nm file bound. It grants no output
geometry, clearance, or tolerance waiver.

`SourceChannels.check` adds actual new copper to that immutable functional source
assembly, rejects merges between distinct channels, and checks new copper against
the complete other-channel surfaces at the production floor. Source-prefix,
physical-owner, stage-bound, source-hole, local-remedy and native checks remain
mandatory independently. These modules are isolated prototypes: the production
constructors and route are not yet wired to use them.

Earlier physical checks passing do not establish this clarified channel rule.
The isolated 2922 merge trial and earlier preview fail the additional criterion.
Do not integrate or label them final. Accepted 2956/2849 preview bytes and every
historical audit remain unchanged; earlier acceptance does not prove this new
criterion.

## Construction and qualification work still required

1. Capture source-only frame/channel certificates once per fresh job. Preserve
   exact frame occurrences in intake, inventories and output; mark them protected
   from growth, not missing or discarded. Fail ambiguous frame recognition.
2. Carry frozen functional-channel IDs alongside physical-owner IDs. A local
   pad-to-trace joint remains integral; a remote frame tie supplies no local
   clearance exemption. Do not infer electrical net names from Gerber.
3. T01 must constrain both inherited new copper and each new site against current
   and reserved foreign channels. Preserve canonical allocation, contained KEEP,
   priority full-round rules and all original occurrences.
4. T03 keeps routes fixed and rechecks complete channel clearance. T04 must check
   each counterfactual against all affected foreign channels, retain uniform
   1..1.5 bounds, fixed consecutive subgroup decisions, complete selected checks,
   both envelope/nominal checks and every upper rejection. Frame strokes remain
   accounted-for protected KEEP. No path or dependency is omitted.
5. T02/T04/T05 completion must use local channel surfaces. Do not construct a
   spindle or inclusive fill from the entire frame-connected physical component.
   Retain source holes, complete connected support, foreign clearance and the
   single cumulative 20% smooth-rim budget.
6. Rebuild any incompatible prior-positive reference under the same captured
   channel policy. A formerly checked reference cannot override the clarified
   rule or be silently trimmed after qualification.
7. Recompute downstream stages in a fresh source-bound job. Reparse the actual
   Gerber, retain all paired native evaluations and original corruption controls,
   and add a channel-bridge negative control based on the actual rejected output.
   Preserve failed jobs. Compare new highlighted visuals with historical accepted
   previews and disclose material differences before integration.

The isolated bounded owner-surface cache correction separately reproduced and
removed the actual 2849 preparation budget failure while matching all 142 owner
surfaces byte-for-byte. Its combined retained estimate stayed within the existing
192 MiB snapshot limit. That preparation trial is not full T05 qualification.

All batch outputs, consolidation, commit/push and full native qualification remain
unfinished. The .DS_Store custody finding stays explicit and unwaived. Coverage
recovery remains independent. Electrical/manufacturing acceptance is not inferred.

The source-channel presence predicate uses the untouched original Gerber image
as its authority. Loss of an actual source feature is intersected with the
functional channel cores; a separately re-unioned source subset is not allowed
to invent missing source copper. No area threshold is used: the regression
includes loss of a positive 1 nm triangle below the areal comparison epsilon.
The failed real-source predicate from candidate189 remains retained separately.

## Isolated construction progress after the first prototype

Candidate205 passed 384 focused tests and a fresh native 2922 T01/T03/T04
prefix: all 11 prefix operations, paired reconstructions and T01 supplements
passed. All 80 frame source occurrences remain unchanged. The original
canonical surface-guard source file and pinned hash are unchanged; the extra
channel guard is a separate delegated construction guard.

Candidate214 additionally constrains T02 inclusive merges by frozen functional
channels, permits local integral fill without treating the outer frame's
interior as a protected functional hole, and protects frame-only T05 source
paths with an explicit unchanged-source contact inventory. Native per-source
channel material bookkeeping and bounded two-version route geometry preparation
are implemented separately. 403 focused tests pass.

The native 2922 legacy reference was checked by assigning all 1743 parsed
regions through their original source IDs. Three true channel clearance
violations remain under the clarified rule (minimum about 0.005757 mm). It
cannot be inherited as a qualified floor. Its older native outcomes remain
unchanged. A newly generated channel-aware reference and downstream connected
construction/export qualification are required. Image-only subtraction had
also produced misleading unbound cap fragments at the bar; source-bound native
contours, not nearest-shape inference, resolve their assignment.

The native channel-reservation sidecar, connected T04/T05 owner-surface
completion and final native channel-verification hooks are still pending. Do
not integrate this partial candidate or present a final Gerber from it.

## Candidate226 and fresh-worker rim registration correction

Candidate226 wires channel-owned T05 preparation, source-native reservation
sidecars, inclusive completion, final actual-material channel checks and an
additional remote-frame bridge corruption control. A supported synthetic case
passed all 44 operations, both export evaluations, all eight corruptions and the
final rendering. This is not qualification of any customer board.

A second synthetic case formed a large new pocket and retained its bounded rim.
Its next worker exposed a registration-order error before T02. Candidate248
validates the frozen channel ID and original witness before deriving that row's
channel assignment. The physical proof still precedes functional partial-budget
registration. The original failed case remains HALTED.

411 focused tests pass in log route_candidate_regression_252.log. This includes
changed-witness and changed-channel rejection plus guarded retained-prefix reuse:
only the exact registration correction is allowed, every retained entry/output
scene is hash-checked, and any retained approved partial forbids dormant-branch
reuse. Full native qualification of the correction remains pending.

## Candidate257: repeated geometry keeps distinct route identities

Customer2922 candidate226 passed 14 native operations through T02, then
halted in T05 scene validation. Its failed scene contains 19 repeated geometry
IDs across 42 addition rows, with maximum ID length84. All old evidence remains
unchanged. The existing connected-route ID rule is extended to the functional
legacy context: IDs include the source route, while identical geometry bytes
remain one content-addressed blob. No route obligation or contour is removed.

Candidate248 separately passed all44 operations and eight corruption controls
on the supported large-pocket synthetic case254. Its actual native rim share
is0.19998895225156949, within0.20. Later stages and final export preserve the
opening. Candidate257 adds the legacy-functional ID correction and rejects
legacy T05 reuse whenever the T05 adapter changes. Its corrected2922 continuation
retains only the14 fully verified preceding operations; all T05 and later work
is fresh. Neither the failed run nor prior acceptance is promoted.

## Candidate266: native encoding uses the same functional owner

The corrected2922 T05 construction and both reconstructions passed under257.
Its export constructor still assembled the local route/lands owner for native
point-contact checking, although the qualified spindle used the full frozen
functional channel. It halted before producing an export, retaining17 verified
geometry operations and the failed export receipt.

Candidate266 projects the actual previously encoded copper through that same
frozen functional channel for the encoding-support predicate. The complete
physical source union is not a replacement owner. The predicate, connectivity
requirement and one-grid support limits remain unchanged. An actual parsed
positive patch attached through another original part of the same channel is
accepted; a patch on another channel joined remotely by the bar still rejects.
The non-channel legacy path is byte-identical in its operand expression.

416 focused tests pass in route_candidate_regression_269.log. Only unchanged
geometry stages through T05 may be retained; export construction/evaluations,
reference generation, connected stages and all final checks remain fresh.

## Candidate274: nested retained source authority

The266 customer continuation stopped before any native operation: nested prefix
verification needed the oldest source revision but the read fence included only
the immediate parent source tree.274 includes all and only the source roots
returned by recursive, hash-bound prefix verification, both for initial explicit
authority and for the sealed inherited binding used by fresh workers. Unrelated
historical results and sibling directories remain denied; altered seals reject.

419 focused tests pass in route_candidate_regression_276.log. The416-code
synthetic272 route also completed all44 operations, both actual export/reparse
checks, all eight corruptions and the final render. No copper computation,
threshold, stage predicate or native evidence is changed by the fence correction.
The customer continuation retains17 unchanged verified geometry operations and
starts fresh at export. All prior failures remain immutable.
