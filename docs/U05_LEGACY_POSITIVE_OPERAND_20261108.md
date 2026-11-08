# Legacy export: actual positive spindle operands

The isolated 3020212868 export at `d8fa13e` constructed successfully but both
native evaluations rejected the first T05 route, `JR-036829360bab1111`, with
`DELTA_MISMATCH`. The unchanged predicate found 2.1624313666063658e-12 mm² after
subtracting the complete earlier-stage image and re-adding that Boolean result.
The parsed region support outside the local owner was exactly zero. All foreign
distance checks for that captured contact passed. The failed file, both process
exits, immutable source and 39,701-file custody record remain retained.

The connected exporter already uses `native_spindle_operand.operand`: the actual
parsed positive Gerber regions, including redundant existing owner support. The
legacy checker now uses the same operand. It still invokes the ordinary spindle
predicate with its unchanged 1e-12 mm² delta, owner and scope comparisons and
0.040 mm finished-file clearance. Scope and clearance see the complete positive
operand, which is conservative relative to its net new subset. Net addition is
retained as diagnostic evidence. No contour, growth decision, grid, cap or
export byte is changed by this verification correction.

Original source ownership still filters only exactly source-authorized internal
contacts. Pin checks, all prior stage/source predicates, whole-file fidelity,
attachment extents, native reparse and corruption controls remain mandatory.
The exact reference-reuse hash guard accepts only the known old exporters and
this qualified complete source file; unknown parser/geometry/tolerance edits
remain rejected. No failed job is resumed or marked passed.

Evidence is under `out/lacie_work/evidence/t02_qualified_entry_gaps_20261107/`
`export_inclusive_identity_01/remaining_boards_01/shared_gap_entry_contour_01/`
`pregrid_connection_01/ACTUAL_DELTA_DIAGNOSTIC_01.json`. That function-level
capture is diagnostic, not native board acceptance. All-contact actual-operand
checks and fresh native export/reparse remain required before integration.

3020212849 has a separate T04 prior-width/source-hole finding, which this change
does not solve. The completed primary board stays frozen with no full rerun.
The explicit unwaived/unattributed `.DS_Store` custody finding, six deferred broad
findings and separate unfinished positive-only flattening remain unchanged.
Owner PENDING_USER; independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.
