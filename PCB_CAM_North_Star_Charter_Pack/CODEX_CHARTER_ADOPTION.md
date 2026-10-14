# Codex handoff — Adopt the PCB/CAM Project Charter

**Action requested:** governance/document alignment only. **Do not start V2/V3 or change frozen acceptance criteria.**

1. Read the supplied `PCB_CAM_PROJECT_CHARTER.md` in full. Verify the V1 (`36eab151...`) and V1.5 (`cb0377c`) evidence against the local repository, especially `docs/ROADMAP.md`, `docs/V1_5_DECISION.md`, tests and manifests. Treat user-supplied summaries as reported claims until verified.
2. Propose placing the charter at `docs/PROJECT_CHARTER.md` in the isolated PCB checkout. Reconcile with current `AGENTS.md`, `docs/ROADMAP.md`, milestone acceptance docs and Cursor protocol. **Do not replace or discard existing rules.** Add a short pointer in `AGENTS.md` that makes the adopted charter the strategic reference, while retaining operational isolation and permissions.
3. Create/update a small `docs/DECISIONS.md` recording the charter adoption, version/date, authorizing user, frozen V1/V1.5 commits, the explicit `NOT_ESTABLISHED` realistic-validation result, and the Cursor `CHANNEL_UNAVAILABLE` state. If the charter conflicts with verified evidence, propose corrections before adoption.
4. Create `docs/TRACEABILITY.md` mapping partner needs (trace movement, pad-group adjustment, vias, teardrops, mask/coverlay and layer outputs) to operation-case concepts, planned gates, and current evidence. Do not claim unsupported manufacturing rules.
5. Create `docs/NEXT_GATE_PROPOSAL.md`: identify the smallest falsifiable next gate after V1.5, with options for aperture-block/realistic Gerber coverage and minimal operation-case modeling. Include negative tests, cost/risks, dependencies and explicit NOT_ESTABLISHED statuses. **Proposal only; no implementation.**
6. If a verified direct Cursor channel exists, request a read-only governance review of the frozen documents. Otherwise preserve `NOT_RUN / CHANNEL_UNAVAILABLE` and do not route through the user.
7. Run only relevant documentation, asset integrity and bootstrap checks; commit the documentation changes on this isolated PCB checkout, report commit/hash and conflicts, then **STOP and request approval** for the next implementation gate.

**North Star:** engineer-supervised CAM modification: preserve source → understand rules and object relationships → bounded deterministic operation → exported independent validation → engineer decision → provenance. Synthetic coupon and public KiCad designs are technical fixtures, not manufacturing approval.
