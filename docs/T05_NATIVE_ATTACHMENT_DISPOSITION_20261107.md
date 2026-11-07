# Actual-file attachment disposition — isolated qualification, 2026-11-07

The preceding eight-region encoding correction successfully constructed the
whole-board Gerber, SHA-256
`757b82b0a101e27c201d43617155afaa0be051c291ecaf5d92e663aae0b08291`.
Both fresh reparse evaluations then stopped at
`U05_ACTUAL_ATTACHMENT_NO_EFFECT`. Their T01/T02/T04 clearance reports and all
112 junction checks had passed. The failed route and both evaluations remain
sealed; controls, remaining-defect audit and final rendering remained NOT_RUN.

The first failing attachment, `JR-37e014c97eeca403`, was labelled treated by the
source model, but the actual preceding exported copper already contained both
the complete approved extent and the complete unclipped maximum treatment.
Exact containment is true without a buffer; missing area is zero. Its unchanged
original already-satisfied predicate also passes. Demanding additional copper
there was an incorrect actual-file disposition, not missing treatment.

The all-attachment study identified one further case, `JR-68e5e2a18c2924b9`.
Its raw model sliver is 4.169786e-8 mm², but it adds no material on the existing
1 nm native grid. Integer material normal forms of the complete predecessor and
the predecessor plus both complete required extents are identical: 126 islands,
136 holes, material SHA-256
`6947071293bd073d88375c15b78785deea3db909d138f2774c7d49fbe8b1c4b0`.
No uncertainty halo is used to establish that identity, no contour fragment is
accepted in place of the complete maximum, and no native face or hole is
discarded after the existing normalization.

The exporter now preserves the source-model outcome separately from the actual
native outcome. A treated source request first runs the unchanged actual
positive-effect predicate. Only its specific no-effect rejection can enter
reconciliation. Both complete extents must either be exactly contained in the
actual predecessor or produce exactly its integer material on the unchanged
declared native grid. The original complete already-satisfied predicate must
also pass. Such an outcome is explicitly ALREADY_SATISFIED_VERIFIED and receives
zero new-growth credit. All other rejections propagate. Minimum visible growth,
file uncertainty, positive-region budget, clearance, pin separation, source
holes, width limits and corruption controls are unchanged.

This is checking/reporting only. It does not change T05 construction, smoothing,
selected geometry or Gerber encoding. An earlier T05 admission filter could
avoid these model-only requests in a separate slice; it is not claimed here.

Evidence under `out/lacie_work/evidence/t04_t05_integration_20261107/`:

- `CORRECTED_EXPORT_REPARSE_FAILURE_01.json`: original failed native run hashes.
- `t05_attachment_effect_diagnostic_01/REPRODUCTION.json`: original predicate
  and exact first failing operands, reproduced without resuming the native job.
- `EXACT_BEFORE_CONTAINMENT_01.json` and the nested
  `remaining_failure_01/EXACT_NATIVE_GRID_STUDY_02.json` in that diagnostic folder:
  complete predecessor proofs for the two cases.
- `ALL_ATTACHMENTS_STUDY_01.json` and `_02.json` in that folder preserve the
  intermediate conservative rejection. The report-assembly tuple/JSON setup
  failure is retained separately; it was not a geometry or native pass.
- `ALL_ATTACHMENTS_STUDY_03.json`: all 213 contacts accounted for; 160 treated,
  37 already satisfied, and the original 16 blocked outcomes remain blocked and
  uncredited. Two source-model treated outcomes are reconciled, with no new
  growth credit. This local study is not a complete native-file qualification.
- `NATIVE_ATTACHMENT_BROAD_02.log`: 544 scoped regressions pass, including
  rejection of a missing complete maximum, halo-only coverage, missing native
  copper, file-resolvable subthreshold growth and a tiny resolvable source hole.
- `NATIVE_ATTACHMENT_SMALL_QUALIFICATION_02.json`: 38 revalidated retained and
  nine fresh native operations pass, including the two actual reparses, eight
  real corrupted-Gerber controls, defect audit and rendering. The small Gerber
  remains byte-identical to the preceding encoding correction.

A fresh whole-board export and both evaluations remain mandatory. Previous
failed runs are never resumed, rewritten or promoted. The app remains
unintegrated and other boards paused. Coverage recovery is unchanged;
positive/negative flattening is separate, unapplied and uncredited. Historical
`.DS_Store` custody FAIL stays EXPLICIT_UNWAIVED_UNATTRIBUTED. Owner remains
PENDING_USER; independent review NOT_RUN: CHANNEL_UNAVAILABLE;
electrical/manufacturing acceptance NOT_ESTABLISHED.
