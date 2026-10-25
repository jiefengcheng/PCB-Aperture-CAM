# T01 candidate on the newly registered crop

**Review state:** `PENDING_USER`
**Candidate:** [`t01_crop_review.png`](../../../out/crop_dynamic_tasks/t01_multicircle_new_crop_20261025/t01_crop_review.png)
**Saved evidence:** [`report.json`](../../../out/crop_dynamic_tasks/t01_multicircle_new_crop_20261025/report.json), [`fresh_audit.json`](../../../out/crop_dynamic_tasks/t01_multicircle_new_crop_20261025/fresh_audit.json), [`policy.json`](../../../out/crop_dynamic_tasks/t01_multicircle_new_crop_20261025/policy.json)

The user directed T01 to run over the newly selected ORG crop before T02 and asked that circles unique within their local growth component remain round. The crop contains 87 unique filled circle geometries from 96 source occurrences. Local growth components connect circles whose proposed 1.5× source-radius envelopes could come within the 0.02002 mm construction gap.

That rule produced 54 singleton circles held at their exact ORG cores and 33 circles in nine multi-circle components processed by the T01 shared-diameter-class pass. The new candidate grew 17 circles, kept 70 unchanged, added 0.6127648931 mm² of copper in the registered viewport, and recorded seven neighbor counterfactual pairs affecting six later decisions. The hard per-circle limit remains 1.5×. The provisional palette and gap are experimental, not manufacturing standards.

Fresh-process retrieval and saved-geometry checks pass. Deterministic replay matched. The prior T01 acceptance remains untouched; this new-crop candidate is not accepted until owner review. T02 stays held until that review. No EDIT contours were used to construct it, and no electrical, native-export, or manufacturing claim is made.

The first render invocation failed because the project virtualenv does not contain Pillow. The candidate geometry was retained; rendering then completed with system Pillow 12.2.0. No dependency was installed. The execution note records this sequence.

## Owner correction — 2026-10-25

The preceding candidate and counts are retained as historical evidence, but are
not the current shape policy. Do not conflate T01 envelope groups with physical
F.Cu components: envelope groups control local growth competition; physical
components determine the crop-specific shape allowance. The owner accepted four
multi-circle physical components. Circles outside those four remain exact round
ORG cores for this crop. Within each accepted physical component, at most one
circle may use non-round growth while the remaining circles retain round
construction. The exact existing T01 priority rule that selects that one site
is awaiting clarification. No updated growth candidate has been run under this
correction; T02 remains held.
