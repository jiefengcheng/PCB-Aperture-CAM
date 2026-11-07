# Redundant microscopic export-support hole

The fresh 3020212826 run `20261107T143517Z-9def5ebf12474b29a57ff2d95cbd6d84`
halted at legacy export construction after 20 passed native operations. Its
20 PASS / 1 FAIL / 26 NOT_RUN dispositions remain unchanged.

The offending T05 support contour is associated with
`route:JR-90fb92319893d3e4`. File-grid normalization creates a 1 nm by 1 nm hole
at `[5.178475, -15.741726, 5.178476, -15.741725]` mm. The qualified predecessor
owner already covers the entire closed hole. The user explicitly said that
retaining this hole is not required.

The isolated correction omits only holes whose width and height are at most
one existing file-grid unit and whose complete closed geometry is covered by
the supplied qualified owner. Exterior vertices and other holes are unchanged.
Construction and the independent model-reference preparation use this same
explicit representation rule. The ledger retains the original qualified
geometry plus every omitted-hole hash, bounds, area and owner witness.

This duplicates copper already present in another export operand; it adds zero
physical copper. It grants no general hole-filling permission and does not
change source voids, growth decisions, source cores, protected pin slots,
clearance, shared-gap constraints, remedy budgets, native checks or corruption
controls. Original ordered dark/clear source commands remain unchanged. This
is separate from positive-only flattening, the pin fix and the 1% gap candidate.

Evidence: `out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/legacy_export_fix_01/`.
The earlier partition prototype and its failed regression are retained there;
that prototype is not integrated. A new corrected incremental job may retain
the qualified legacy stages through T05 only after the existing dependency,
input, source, artifact and separate-evaluation guards pass. The failed job is
never resumed or resealed.

Prior `.DS_Store` custody failures remain EXPLICIT_UNWAIVED_UNATTRIBUTED. Other
boards remain paused. Owner acceptance remains pending; independent review is
NOT_RUN and electrical/manufacturing acceptance is NOT_ESTABLISHED.
