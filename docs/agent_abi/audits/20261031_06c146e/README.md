# Independent five-suite ABI audit

**PASS_FOR_NEXT_SLICE_ABI_IMPLEMENTATION_ONLY** for source snapshot
`06c146e55bfcf97a49733e5d39063ae273e6e764` and the explicit supported model
families. The user-designated front Safari conversation completed this audit:
https://chatgpt.com/g/g-p-6accf804b5848191a5171de4ec8e83eb-pcb-ai-cam-proposal/c/6ae2a530-26a0-83ec-b82b-46ab0c5d1e27

- [Original independent receipt](evidence/ABI5_INDEPENDENT_AUDIT_RECEIPT_20261031.json)
- [Original independent summary](evidence/ABI5_INDEPENDENT_AUDIT_SUMMARY_20261031.md)
- [Downloaded original evidence ZIP](ABI5_INDEPENDENT_AUDIT_EVIDENCE_20261031.zip)
- [Local receipt-to-packet binding check](BINDING_CHECK.json)
- [Separate local dependency delivery](STAGE_ABI_DEPENDENCY_DELIVERY_20261031_294.zip) and [correction record](LOCAL_DEPENDENCY_CORRECTION.json)

The external auditor independently passed all **313 distinct tests and two
subtests**, including all **35 operations through production CLI factories**.
The unchanged modules/cases ran in separate invocations after a combined-run
execution limit; one uninterrupted full run was not completed. The auditor used
Linux x86-64, Python 3.13.5, pytest 9.0.2, Shapely 2.1.2 and GEOS 3.13.1; actual
commands, versions and raw logs are retained in the original receipt/evidence.
T01, T03, T04, T02, T05 and cross-suite model orchestration all received a scoped
PASS. This is independent code/contracts/model verification, not a new accepted
native-board sequence.

## Findings and follow-up boundary

| Finding | Current disposition |
|---|---|
| ABI5-001: omitted sexpdata dependency | The auditor independently verified exact 1.0.2 parser bytes from retained REV10 material. The newly uploaded supplement container was unavailable to it. Both current dependency manifests are now pinned to `sexpdata==1.0.2` as a **separate local delivery correction**, outside the audited `06c146e` snapshot. Original package, source and receipts remain unchanged. This local correction is not retroactively part of the independent verdict. |
| ABI5-002: parser bytes absent from runtime fingerprint | Retained as a future separately versioned contract-hardening item. Existing runtime hashes, plans and candidate bindings are unchanged. |
| ABI5-003: fresh saved-case verification | All six attempts correctly returned NOT_RUN_ENVIRONMENT_MISMATCH. No guard was bypassed and no saved PASS became a fresh result. Independent native-source qualification remains NOT_ESTABLISHED. |
| ABI5-004: frozen payload coverage | Auditor checked the supplied 8-file frozen subset. The complete 19,990 local payload checks remain author-executed, not independently repeated. |
| ABI5-005: narrow supported families | Exclusions remain explicit: historical non-round T01, arbitrary curved-native T03 families, T04 global optimum and electrical intent are not qualified. |
| ABI5-006: historical findings | C02 REV234 strict-exact-replay REVISE and C03 provisional localization remain open. |

The original evidence ZIP SHA-256 is
`a48989fa8475e7187d5b537970143c2ef2a4a0b444fdfca7d57d2c7880cd80f1`.
It refers to the uploaded packet SHA-256
`50705fb6db97ebc2c2c4b03edab91884c34526872530b2832d9b787faa33a449`.
The external JSON is retained byte-for-byte. This README and binding checks are
coordinator records, not statements authored by the external reviewer.

C01/C02/C03 geometry and acceptance receipts remain frozen. No source-copper
construction, new native export, electrical/manufacturing acceptance or
retroactive closure of historical failures occurred during this follow-up.
