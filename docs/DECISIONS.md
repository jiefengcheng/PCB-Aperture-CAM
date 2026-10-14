# Decision log

Entries distinguish user authorization, recorded evidence and proposals. They do not independently grant permission. Codex is sole coordinator; no manufacturing approval is recorded.

| ID / date | Decision owner and authorization | Decision / evidence | Status and stop |
|---|---|---|---|
| D-001 / 2026-10-14 | User-authorized isolated V1; Codex technical decision | Freeze V1 `36eab151a0bf00ea57eef09f1dc425c4b5603e50`; recorded coupon technical PASS with synthetic rules, limited Gerber subset, 13 corruption controls and eight-test receipt | Historical technical result; no manufacturing signoff; Cursor NOT_RUN |
| D-002 / 2026-10-14 | User public-reference roadmap amendment; Codex qualification decision | Freeze V1.5 `cb0377cbdcdac25ee9b89c01aca6901b3ae48d0d`; source custody and no-edit CLI compatibility established, realistic validation NOT_ESTABLISHED | Historical qualification closure; no V2/V3 |
| D-003 / 2026-10-14 | User explicitly requested private GitHub repository under `jiefengcheng` | Existing project history published to `jiefengcheng/PCB-Aperture-CAM`; generated evidence and external checkouts stayed Git-ignored/local | Past upload authorization fulfilled; this documentation task does not initiate another push |
| D-004 / 2026-10-14 | Repository owner in current Codex conversation: adopt supplied charter as proposed strategic reference, reconcile/verify, commit documentation and stop | Integrate `PCB-CAM-CHARTER-001` supplied v1.0 (2026-10-14), with aligned copy v1.0-alignment.1; preserve both supplied Markdown documents; add operational pointer, evidence audit and requirements traceability | Documentation integration authorized; reconciliations proposed for approval, no new implementation authority |
| D-005 / 2026-10-14 | Codex read-only audit within D-004 | Frozen source/schema/asset checks, retained native/public/export hashes, schema, negative receipts, test-count/log review support the bounded historical claims; fresh four bootstrap tests pass | Audit consistency PASS; no fresh geometry/parser/full-suite rerun and no independent review |
| D-006 / 2026-10-14 | Codex reconciliation proposal, awaiting user decision | C-01 authority separation; C-02 frozen overall status enum; C-03 unverified GUI claim; C-04 qualification/round-trip limits; C-05 strategic gate namespace; C-06 unverified partner requirements | See [CHARTER_INTEGRATION.md](CHARTER_INTEGRATION.md); original charter preserved, no frozen result changed |
| D-007 / 2026-10-14 | Codex next-gate recommendation, awaiting explicit user approval | FC-1: independent oracle and support decision for one already acquired non-nested aperture-block example; alternative MC-1 passive operation-case record | PROPOSED / NOT_RUN. No parser implementation, executor, V2/V3, new downloads or partner contact authorized |
| D-008 / 2026-10-14 | Codex tool-inventory observation | No authenticated direct Cursor agent/review tool found. Governance packet prepared under `out/charter_adoption/` | Review NOT_RUN / CHANNEL_UNAVAILABLE; no human relay or implied approval |

Evidence audit: [CHARTER_EVIDENCE_AUDIT.md](CHARTER_EVIDENCE_AUDIT.md). Requirements map: [TRACEABILITY.md](TRACEABILITY.md). Approval target: [NEXT_GATE_PROPOSAL.md](NEXT_GATE_PROPOSAL.md).

User approval of a future gate must be recorded as a new entry with its exact scope, allowed mutations, acceptance obligations and stop condition. Do not rewrite an old entry to imply earlier authorization. The charter describes eventual product success, not an active implementation mandate.
