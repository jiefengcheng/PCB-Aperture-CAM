# T04 straight-first construction (bounded prototype, 2026-11-20)

The four grouped hard-case rows exposed a sequencing problem. H2 and H4
are interactions inside one straight group; their members must be allocated
simultaneously over their full unequal native lengths. H1 and H3 involve a
bend beside a straight member, so bend treatment must consume the straight
solution rather than undo it.

The bounded actual caller in `src/gerber_u05/group_stage.py` now orders:

1. Compile maximal straight-member source supports and solve both faces of
   all group members together, maximizing summed width within source caps and
   the unchanged clearance budgets. Overlap windows are constraints, never
   new source-segment boundaries. Construct ideal straight copper and freeze it.
2. Build eligible arc-core source-rail budgets against that frozen material,
   then construct arc cores under those budgets. Pass exact two-sided straight
   endpoint cross sections to the joint/default constructor, not merely a
   symmetric total width. Freeze the constructed arc cores as well.
3. Search and verify unconstructed portions and joints against the frozen
   straight and arc copper. Unqualified straight members are default cases,
   too. No later rejection feeds a reduced cap back into a straight group.
   A failed joint is unresolved; retaining a narrow source beside a widened
   frozen end is not a completed result.

Constructed groups are never clearance-check candidates. The source constraint
certificates, finite representation checks, default verification and endpoint
custody checks have distinct scopes. Source-rail arc certificates use the
triangle inequality on preconstruction source distances; they do not infer
clearance from a fitted circle. Native centerline paths remain unchanged.

The 25% parameter applies locally between consecutive segment widths. It is not
a route-wide cap. Scalar side fields use the existing C1 transition constructor;
the provisional maximum additional transition reach is 0.11 mm. Default bends
with collapsed inner rails may use swept cells, but only as untrusted proposals
that must pass clearance verification. Their materialization is not a group
construction certificate.

Normalized default bodies can remove source edge noise. Their positive-change
checker tests all new copper, with the existing checking margin, against all
foreign copper. This is stronger than a visible-addition clearance test, but
does not claim old-edge retention or replace source/removal/continuity duties.

Evidence: `out/lacie_work/t04_route_assembly_20261120/`. It preserves source
snapshots, failed attempts, source-bound bounded diagnostics and group-context
visuals. No completed T04 scene, full-board run, replay, export, independent
review, or manufacturing qualification is implied. The existing full-board
operator has not been enabled by this prototype.
