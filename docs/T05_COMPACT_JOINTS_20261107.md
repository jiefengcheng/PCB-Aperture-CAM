# Isolated T05 local profiles and compact representation

Status: implemented and locally verified, UNINTEGRATED. Base revision:
`7de93a34af28fd1e82aed1f377cf66e89fc235a9`. Branch:
`codex/t05-compact-smoothing-20261107`. No T04 algorithm changes.

Evidence root, abbreviated E below:
`out/lacie_work/evidence/t05_implementation_20261107/` in the normal checkout.
The isolated source is E/source. Historical board results and failed runs are
unchanged. This candidate is separate from the concurrent T04 implementation.

## Behavior

1. T05 joint export can include existing owner copper inside its existing local
   domain. This removes the need to encode every small difference fragment.
   Redundant support alone is inset by the existing 4 nm overlap constant;
   qualified added copper is retained completely. Existing support, missing
   material, physical-union and domain predicates remain at their original
   epsilon. If those predicates fail, the original support builder is used.
2. For T05 serialization only, an exact triangular partition can be coalesced
   through integer directed-edge cancellation. A merge must form a valid simple
   hole-free polygon. The original exact signed-boundary and doubled-area proof
   is required before and after coalescing, then again after actual Gerber
   reparse. No positive face, source hole, vertex position or clearance tolerance
   is discarded. Existing successful cut-in encodings remain in use.
3. A bounded additive joint profile runs after T05's existing completion. It
   extends one local connected surface inside a declared contact window and
   convex transition envelope. The entire proposal is rejected when protected
   pin separation or existing remedy checks fail; it is never clipped against
   those barriers into acceptable fragments. Native-grid material is checked
   again. Existing source cutouts and approved partial-pocket openings remain
   protected. Original physical ownership and functional channel ownership are
   kept distinct, preserving temporary source frames without using them to join
   growth channels.
4. The captured, hash-bound `contracts/t05_joint/settings.json` supplies a
   replaceable radius fraction (0.25) and a direct-export region budget (8 per
   attachment). Exceeding the budget halts export instead of accepting an
   object explosion. The budget counts directly emitted T05 junction regions in
   each land contact window, including support caps. It does not yet count all
   accumulated floor/completion regions per attachment.

Smoothing is initially limited to the three reported 3020212826 recesses,
identified by raw source SHA, circle geometry SHA, center and local window.
Other sources receive no new profile. A missing/changed source witness halts.
Automatic all-board contact-window discovery is outside this slice. No claim
of mathematical C1 tangency is made; the highlighted local transitions require
visual review. Positive/negative flattening of the complete source is a separate
requirement and is not implemented here.

## Evidence and checks

`E/REGRESSION_RELEASE.log`: **436 passed** (7.17 s), including exact partition,
smallest positive grid face, source-hole, missing-triangle negative control,
whole pin rejection, foreign-clearance rejection, local-window, per-attachment
budget and physical-versus-functional ownership regressions.

Command from the isolated source:

```sh
tools/Run_PCB_Tests.command tests/gerber_u05 tests/test_junction_spindle_blend.py tests/test_junction_spindle_stage.py -q
```

`E/SYNTHETIC_ROUTE_FROZEN.log`: all **47 native checks PASS**, including fresh
construction, both evaluations, export/reparse, corruption controls, rendering
and final custody/delivery. Final status:
`U05_EXPORT_REPARSE_CONTROLS_RENDER_PASSED`. Job:
`E/source/out/lacie_work/synthetic_qualification_frozen`.
This fresh synthetic source does not exercise the three board-specific profile
declarations; stage-application tests and the real retained local trials cover
that behavior separately. This is not fresh whole-board qualification.

`E/ACTUAL_JOINT_PROFILES.json` and `E/joint_profiles.png`: the three new profiles
on retained final geometry pass the integrated source-bound 13-slot pin rule and
existing local remedy predicates. Minimum checked foreign gaps, respectively:
0.046332765, 0.043279681 and 0.042406450 mm, above the 0.0401 mm construction
guard. Added/carrier ratios are approximately 1.41%, 2.08% and 1.51%, below the
existing 20% cap. The retained predecessor has earlier client-reported pin
merges: these local trials prove no new protected-slot fill by the proposals,
not correction/acceptance of that historical full board.

`E/ACTUAL_COMPACT_JUNCTIONS.json`: real direct T05 trials with fresh maintained
parser reparse and native material proof:

| Retained route suffix | Previous regions | Candidate regions |
| --- | ---: | ---: |
| e6c1b99c4a6a8c6a | 535 | 7 |
| 6f96246c03110a6b | 394 | 4 |
| fec25ddf16c253b5 | 301 | 2 |
| 0fd3908585bdff28 | 252 | 3 |
| Total | 1482 | 16 |

`E/ACTUAL_PARTITION_COMPACTION.json`: a real completion parent changes from
3156 triangles to 3 regions, with exact material proof and actual Gerber reparse.
No new vertices or dropped positive parts. Standalone local Gerbers and hashes
are retained beside these reports. They are not delivered full-board artwork.
Recorded trial timings measure different scopes; no end-to-end speedup claim.

The first synthetic harness placed its source inside historical evidence but
outside its fresh job; final custody reread halted despite its 47 native passes.
`E/SYNTHETIC_ROUTE_01.log` retains that failure. Separate fresh jobs placed their
source inside their own job, using the existing supported authority model. No
read fence was weakened, failed job resumed, or failure promoted to PASS.
Other exploratory failures and diagnosis logs are retained in E.

## Integration and remaining qualification

1. Review this isolated commit and the highlighted local comparison first.
   Integrate only after the other chat's T04 work is stable and between jobs.
   Reconcile the shared worker/export hooks against the latest revision; retain
   the new T04 algorithm and source-bound pin checks.
2. Run the supplied regressions on the combined revision. Capture current
   policy and producer hashes for a separate fresh qualification job. Do not
   resume historical jobs or silently reuse a stale T04 prefix.
3. Qualify the combined 3020212826 route: whole-board clearance, every protected
   pin slot, source cutouts, native owner/channel checks, region counts and
   export/reparse/negative controls. Review the final highlighted board render.
   Confirm the three source-bound profile witnesses against the new T04 result;
   a blocked proposal stays unchanged with its reason recorded.
4. Measure final total objects/file size/runtime on that combined board. These
   local counts do not establish the full-board region total or runtime.

No integration or new full-board 3020212826 run was performed in this slice.
The 0.040 mm nominal clearance and 0.0401 mm construction guard are unchanged;
no 1% allowance was consumed. Prior `.DS_Store` custody failures remain explicit
and unwaived. Owner acceptance is pending; independent review is
`NOT_RUN: CHANNEL_UNAVAILABLE`; electrical/manufacturing acceptance is
`NOT_ESTABLISHED`.
