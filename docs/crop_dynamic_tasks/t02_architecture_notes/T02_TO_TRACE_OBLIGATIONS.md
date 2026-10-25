# Accepted T02 scene and future trace obligations

The next trace capability must receive the accepted T01+T02 scene together with its source-bound open-work ledger. Visual acceptance of T02 does not clear, repair or reclassify that ledger.

## Bound handoff

| Artifact | v69 binding |
|---|---|
| Accepted T01+T02 WKB | SHA-256 68f2ee5668a6a025e1fbd99ad10e50cbd1d049bc8a46c6720f5bfd834c5a88e1 |
| T02 result | SHA-256 d70b87a8cfc80a87e54332539dc455e7b0ba8d0c12ffe6aa3fc609f047b73863 |
| T02 policy | v15, SHA-256 54c9542dd7c31fb8fb24698d97741dcc72a049b050bae6408c421f1b25174df8 |
| Future-trace ledger | out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v69/future_trace_work_items.json, SHA-256 2ba25efffaeb6f2bfdc91ea140ceff6a963a2985fbec139d7c61624401c49662 |
| Owner acceptance | docs/crop_dynamic_tasks/t02_authorization/T02_OWNER_ACCEPTANCE_20261025.md |

The ledger file contains two separate collections: 255 clearance issues and 120 non-side deferred overlap witnesses. Do not sum those populations as 375 distinct problems; they represent different evidence types and can refer to related source geometry.

## Open clearance issues

| Ledger class | Count | Meaning |
|---|---:|---|
| SOURCE_SIDE_GAP_REQUIRES_FUTURE_TRACE_REPAIR | 4 | Original source-side gaps below the 0.02000 mm hard experimental floor. Their geometry is unchanged by T02. |
| CORNER_NEAR_GAP_REQUIRES_FUTURE_TRACE_REVIEW | 21 | Corner or endpoint approaches below the hard floor. The separate 0.00010 mm topology-only guard prevents contact; it does not establish safe spacing. |
| EXISTING_ATTACHMENT_EXTENSION_REVIEW | 230 | Source-bound reviews around pre-existing attachment ports and extensions. The local port exception does not exempt the rest of a trace or its side-facing sections. |

The smallest original side-surface gap is 0.002974602642499491 mm. The other three source-bound values are 0.004070000000000462 mm, 0.01999913305377987 mm and 0.017990533416814003 mm. These are explicitly open; comparison tolerance does not turn a sub-floor distance into a pass.

The audit reports 59 applicable side-surface comparisons, while the execution receipt reports 301 reservation records. These are different populations. The 0.02002 mm construction target applies to new constrained side growth; the 0.02000 mm hard experimental floor remains the reporting boundary for existing or final copper-surface gaps. Do not treat the reservation count as a count of independent safe-gap findings.

## Separate overlap witnesses

The ledger also contains 120 positive-area trace-copper overlap witnesses classified NON_SIDE_DEFERRED. Their recorded pairwise area total is 0.7058593794704956 mm²; the unique T02-added-copper overlap area is 0.5494835407795747 mm², or about 10.35% of added area. Preserve the per-pair rectangle and trace source IDs/spans, geometry hashes, and overlap witness hashes. The unique area avoids double-counting shared overlap; it is not a proposed repair quantity or accepted severity threshold.

T02 leaves all trace geometry unchanged. Its result records the future trace width rule as MUST_NOT_SHRINK_FROM_ORG_WIDTH. A later trace capability must inspect each bound route and address the open work without silently narrowing native width, assuming route feasibility, or treating same-component membership as permission for new local contacts.

## Measurement and interpretation boundary

The active policy is surface_side_priority_v15. Current side-by-side construction and checks use distance between the complete rectangle copper and actual finite-width trace copper. The 0.00001 mm geometry tolerance is for numerical comparison/reporting only; it does not waive the 0.02000 mm floor. Corner topology separation is a different constraint and cannot weaken the side rule.

Older handoff text about trace centerlines is historical and superseded by the owner's later instruction to remove centerline-based rules. Do not carry centerline measurements, derived thresholds or centerline pass fields into a future T02/trace interface. Keep surface-gap findings explicit instead of translating them into a different metric.

The saved audit uses the existing parser and Shapely. It preserves 275 original physical components and 121,425 source contacts with zero new component joins and zero new local source-contact pairs. This source-contact check does not establish electrical net intent, trace feasibility or manufacturing acceptance.

## Trace-task admission

Use the exact accepted scene and ledger hashes above as inputs. If the local v69 bundle is absent or a hash differs, report the recorded acceptance and mark fresh geometry verification unavailable; do not regenerate or substitute a visually similar crop. Resolve each ledger row with source-bound evidence and retain original identities. Keep the 120 overlap witnesses separate from the 255 clearance issues and retain unresolved items as OPEN until their own criteria are met.

This note records handoff context only. It does not authorize T03, route editing, width changes, junction work or any automatic repair.
