---
type: "catalogue-result"
title: "Minimum common catalogue and R140 retrieval"
summary: "Stored R140 context with source identities, retained qualifications, verified matches and fresh-process retrieval/export."
generated: {"by": "codex/bounded-common-catalogue", "at": "2026-10-17T17:12:56.885895+00:00"}
status: "stable"
tags: ["pcb", "catalogue", "storage", "qualification", "retrieval"]
sources: [{"id": "definition", "resource": "/references/common-catalogue-definition.json", "title": "Original definition and infrastructure review"}, {"id": "execution", "resource": "/references/common-catalogue-execution.json", "title": "Final persisted execution and completion"}, {"id": "cursor", "resource": "/references/common-catalogue-cursor.txt", "title": "Final independent Cursor audit"}]
---

# One stored context

The bounded slice now persists source/revision and occurrence identities, native/Gerber object types, component/pad references, net annotations, layers, positions and bounds in millimetres. It reuses the existing SQLite revision catalogue, exact source locators, grouping and reference spatial predicates. Existing inventories and workbench capabilities remain available.

The first reopened retrieval returns **R140.1, its connected trace, nearby R140.2 and the corresponding mask opening**, plus the footprint dependency, original source identities and separate match/qualification states. A small dataset manifest binds the per-artifact revisions and cross-source correspondence/qualification records. Diagnostic context export reuses the same selection; it does not claim native board reassembly.

**Storage & indexes** follows Find records → Inspect relationships/groups → Reopen the stored revision → Export selected context. Its central result is the four-role table with actual geometry, source identities, match states and qualification links. Recorded public/synthetic inspectors remain available. Correction replays stay in Cases.

# Current evidence

The user-directed payload ceiling is now **128 MiB**. The actual 72,514,570-byte native source admits and reads back byte-for-byte; write/read boundary checks and 33 existing-infrastructure regressions pass. The earlier 64 MiB rejection is preserved.

The definition review reproduced unsupported back-side pad geometry and loss of this board's `(net "name")` annotations in the existing inventory. The separate bounded adapter now retains the names and qualifies the exact R140 back-side pose. Native/Gerber matches have individual tolerance-bounded witnesses. Cross-artifact sidecars and the diagnostic context export are implemented; aggregate ROI equality is kept separate from object-level matching.

Warnings and geometry mismatches are retained qualifications. They do not have to be resolved before the data can be stored and managed. Integrity failures still reject publication. Database query completeness, geometry availability and correspondence qualification retain separate statuses.

The [definition evidence](/references/common-catalogue-definition.json) retains the original design and infrastructure review. The [execution evidence](/references/common-catalogue-execution.json) identifies the actual materialized revision, source-bound qualifications, fresh-process retrieval and portable diagnostic export. Earlier Cursor findings were corrected through report-derived semantics and immutable report artifact revisions. The [final independent audit](/references/common-catalogue-cursor.txt) returns **QUALIFIED_IN_DECLARED_SCOPE**, with no actionable remaining findings; all 52 snapshot hashes remained unchanged. The final suite has 155 Python tests passing, alongside UI regressions and 17 frozen control outcomes. Whole-board ingestion/equivalence, independent net intent and manufacturing acceptance remain unestablished.
