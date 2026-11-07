# Native verification of an approved T02 inclusive rectangle

Export-only job `20261107T225342Z-bc83faf328f346239e868f74e4fbd399` passed
source assembly and export construction. Its generated Gerber SHA-256 is
`14748a13afc6cbffb59280556afaac4107748200adc1343737852fb94b97a6b7`.
Both export evaluations then stopped on a missing predecessor dictionary key
for the accepted T02 inclusive fill
`t02-inclusive:5f6e0e8f9528bfbf00c08a2808b38dd96538671cb5d3a4068816587148d9aab1`.
The failure preceded that fill's native land check. Its 38 retained operations,
four fresh PASS operations, two FAIL operations and three remaining NOT_RUN
operations remain unchanged. This is not final export qualification.

The legacy native verifier already supplies a new inclusive rectangle with
the union of its member pads as predecessor and the union of their original
source shapes for contact permissions. The connected exporter omitted this
handling. The isolated correction applies the same member-derived identity.
It does not declare the new fill itself to be original copper, skip a native
land check or alter the selected rectangle.

Additional binding checks require one accepted T02 decision, exact source
members and geometry references, the complete member-derived logical box,
the existing 20% acceptance limit, original member hashes and frozen physical
and functional ownership. Rejected fills, changed references, mixed channels
and arbitrary new objects cannot obtain a predecessor through this path.
All existing actual land, source-core, clearance, shared-gap, pin, topology,
source-void and final image checks still run. Export construction is unchanged.

The actual retained client fill binds successfully with no geometry or source
store writes. A synthetic source with two pads joined by an original filled
region produces one accepted inclusive rectangle in both construction roles
and passes all 47 native operations, including the new native binding, both
export checks, eight corruption controls, defect audit and rendering. The
earlier synthetic variant uses a T04 trace joint: its frozen-width veto
correctly rejects the fill. It also passes its native route, and is retained
as a negative case rather than claimed as positive inclusive coverage.

Focused qualification passes 646 tests. Early diagnostic/setup errors and
the initial same-process report write rejected by the native read fence remain
preserved. Reporting is performed separately; the fence is unchanged.

Evidence is under
`out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/export_inclusive_identity_01/`.
The next real job retains the original three successful T05 proofs and requires
a new export-only tail. No T01-through-T05 growth or full primary-board restart
is authorized. The old generated file remains a failed-run artifact.

The correction remains isolated pending final qualification and highlighted
client findings. Other boards remain paused. Six baseline failures are deferred
and unwaived. Positive-only flattening remains separately unfinished.
`.DS_Store` custody remains **EXPLICIT_UNWAIVED_UNATTRIBUTED**. Owner PENDING_USER;
independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.
