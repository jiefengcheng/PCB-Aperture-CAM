# Isolated T01 explicit-clear BGA single-circle case

This slice implements the owner's separate BGA single-circle case, after the
original-Region attachment correction. It remains unintegrated. Paired pads,
ordinary single terminals on long feeds, and isolated array islands are distinct
source cases; remote connectivity and local growth competition are not proof of
a pad pair.

## Source qualification and construction

The classifier requires a complete axis-aligned equal-pitch array of identical
original circular flashes, at least three positions on each axis, on native
coordinate ticks. Each flash must restore material actually removed by an
earlier original clear operation. Merely being near a negative footprint is
insufficient. The array witness records source identities, drawing ordinals,
removed-material hashes, axes, source grid and the captured provisional policy.
This is an explicit source-pattern profile, not inference of package identity.
Incomplete, rotated or irregular arrays retain ordinary T01 behavior.

Only circles whose complete original contact neighbourhood contains their exact
aliases qualify as isolated islands. Any trace, Region, other pad or remote
common-bar attachment retains the ordinary attachment/pair policy. This
qualification is recomputed from original finite copper before allocation;
current growth cannot create permission. The 3020212826 array contains 25 circle
positions and five qualifying isolated islands. A sixth nearby circle with an
existing attachment is explicitly excluded from this new case.

Qualified islands receive independent single-site allocations, using the
existing diameter palette and strict 1.5x radius cap. They have no artificial
proximity partner or paired square-follower ceiling. Their optional growth may
be clipped against all actual original and live neighbours, while their exact
source cores remain intact. Ordinary paired-pad square rules remain unchanged.
All source ports, live primitive checks, full-surface checks, physical/functional
channel checks, pin separation, native export/reparse and corruption controls
remain required. No clearance value, construction reserve, tolerance, smoothing
or downstream remedy rule is changed.

The strictly-greater-than-70% other-copper KEEP rule and full-containment KEEP
take precedence. Their registry is unchanged. No clear footprint is imposed as
a permanent no-growth mask: dark material restored later in drawing order is
copper. Clear provenance only classifies this explicit growth case. This is
separate from representation-only flattening, which remains unapplied here.

The registry is contracts/t01_bga_single/settings.json. Captured policy values
and raw-file hash appear in the canonical marker, allocation and source-array
witnesses. Replacing the registry invalidates a stale canonical policy rather
than changing a sealed job silently.

## Evidence and limits

All new evidence is under
out/lacie_work/evidence/t01_bga_single_20261107/. Source snapshots, failed jobs
and test logs are immutable. Qualification_01 preserves the erroneous six-island
harness inventory. Qualification_02 preserves the discovery that the old
proximity-pair allocator still demoted standalone islands using a pair's square
ceiling. The corrected source uses independent singleton allocations. No failed
job is resumed or promoted. The synthetic before/after test also proves that
removing array provenance restores ordinary complete-round behavior.

BROAD_03.log reports 650 passing scoped regressions, including the original
70% and containment rules, attachment recognition, T04 ladder/caps, protected
pin slots, source/export corruption controls and Gerber U05 checks. The earlier
test fixture lacking site metadata and the too-close synthetic source gap are
retained as test failures; no product guard was relaxed for either.

The real-source qualification is deliberately bounded to the five BGA islands
with the complete original board held as context. It does not generate a new
full-board T01/U05 delivery or run T03/T04/T02/T05. Other boards remain paused.
Final findings, highlighted actual-reparse views and worker/check receipts are
delivered before any integration. Owner review is pending; independent review
is NOT_RUN: CHANNEL_UNAVAILABLE; electrical/manufacturing is NOT_ESTABLISHED.
Historical .DS_Store custody failures remain EXPLICIT_UNWAIVED_UNATTRIBUTED.

## Bounded result

Qualification_03 passes construction and two fresh sequential reconstruction
workers (46.61, 45.38 and 45.22 seconds). Candidate and Gerber hashes are identical
across all three workers. All five original 0.250 mm circles receive clipped
optional growth inside the existing 0.3749 mm envelope class; this is not a claim
that their resulting contours are complete circles. Actual new copper totals
0.209315098414 mm2.

Actual export/reparse preserves the 1,921 original objects and three original
clear operations and appends five positive regions. Native-grid boundary and
area differences are zero within the existing 0.000002 mm fidelity tolerance.
All 126 physical components, 128 original holes and 13 protected pin checks
survive. Full construction and actual-file land checks pass. Actual-file source
prefix alteration and appended-region removal reject for their intended reasons.
These are same-author native proofs, not independent review or release approval.

The highlighted source/reparse comparison, rejected-round diagnostic and existing
read-only viewer are in visual_01/. Source_04 is the exact qualified engineering
snapshot. The retained input inventory's older source_revision describes its
input origin; SOURCE_PROVENANCE_01.json binds this new implementation's actual
producer files, snapshot manifest and isolated commit without changing that
historical input metadata. See FINDINGS_01.md, FINDINGS_01.json and PER_CIRCLE_01.csv
in the external evidence folder for complete links and case decisions.
