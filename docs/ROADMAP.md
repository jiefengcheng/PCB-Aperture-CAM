# PCB Aperture CAM roadmap — amendment authorized 2026-10-14

Codex remains sole coordinator, author and integrator. All work stays in this checkout. V1 implementation and gates are frozen at `36eab151a0bf00ea57eef09f1dc425c4b5603e50`; the V1.5 amendment does not broaden that technical PASS.

| Phase | Purpose | Assets / evidence |
|---|---|---|
| V0 | Establish the synthetic KiCad experiment | Completed synthetic source experiment |
| V1 | Build and falsify an independent Gerber validator | Synthetic coupon; bounded technical PASS, Cursor review NOT_RUN |
| V1.5 | Qualify realistic open-source PCB assets and parser compatibility | GlowStitch first, then HALPI2-HDMI-FPC, then official Ucamco test fixtures |
| V2 | Automate constrained copper modification | Synthetic and selected qualified public cases; NOT AUTHORIZED |
| V3 | Add AI-assisted modification planning | Validated cases and engineering rules; NOT AUTHORIZED |

## V1.5 protocol

1. Acquire `https://github.com/sjpiper145/GlowStitch.git` into `external/sources/GlowStitch`. Record origin, exact commit, declared license, byte hashes and all native/project/schematic/Gerber/mask/coverlay/drill assets, including ZIP contents.
2. Keep source checkouts immutable after acquisition. Extract and copy into `out/v1_5/` only. Do not run scripts supplied by public repositories. Never insert them into `assets/` or change the coupon policy.
3. Select a usable native KiCad board. Pin the supplied KiCad 10.99.0 CLI by binary hash and retain commands, logs, exports, source custody and supplementary DRC. Establish repeated no-edit CLI exports. Report GUI opening and native save/reload separately if unrun. No silent substitution of byte, parsed-object or geometry equality for one another.
4. Apply the frozen V1 importer read-only before any broader compatibility analysis. Report unsupported constructs as NOT_ESTABLISHED. Do not substitute coupon terminal identities or invented margins for public electrical/manufacturing intent. A successful native load or parser run is not geometry acceptance, correct repair, impedance proof or fabrication approval.
5. Only after GlowStitch's initial read-only qualification report, evaluate `https://github.com/hatlabs/HALPI2-HDMI-FPC.git` as a second native design. Then acquire selected official test files from `https://www.ucamco.com/en/gerber/downloads` for parser compatibility only. Preserve source URL and hash; record license declarations without inventing rights or redistributing assets.
6. Prepare a frozen read-only Cursor packet covering provenance, parser coverage, source immutability and bounded claims. Request review only through an authenticated direct channel. The earlier session found no such channel; current status remains NOT_RUN / CHANNEL_UNAVAILABLE until verified otherwise. No human relay or global configuration changes.

## V1.5 decision gates

| Gate | Required evidence | Missing evidence |
|---|---|---|
| A0 Custody | Exact origins/commits or download URLs, licenses as declared, complete hashes, unchanged sources | NOT_ESTABLISHED / FAIL on mutation |
| A1 Native compatibility | Selected native board loads/exports in pinned tool, retained logs and no-edit repeated outputs | NOT_RUN / NOT_ESTABLISHED |
| A2 Import coverage | Per-layer roles, primitive inventory, warnings and frozen V1 support boundary | NOT_ESTABLISHED for unsupported semantics |
| A3 Realistic geometry/electrical validity | Qualified independent intent and applicable public design rules; complete relevant geometry support | NOT_ESTABLISHED, never coupon-rule FAIL against a public PCB |
| A4 Evidence and review | Qualification reports and frozen packet; Cursor actual review status separate | NOT_RUN for unavailable review |

A V1.5 exploration may close with a negative compatibility decision and explicit NOT_ESTABLISHED validation. It must not be described as successful generalization. Compatibility fixtures do not teach correct repairs. No V2 or V3 starts at this gate.


## Charter alignment — 2026-10-14 (documentation only)

[PROJECT_CHARTER.md](PROJECT_CHARTER.md) is the reconciled proposed strategic reference. [CHARTER_INTEGRATION.md](CHARTER_INTEGRATION.md) records the conflicts and proposed corrections; [CHARTER_EVIDENCE_AUDIT.md](CHARTER_EVIDENCE_AUDIT.md) checks retained evidence and records current verification limits. Frozen V1/V1.5 results, operational isolation and acceptance contracts remain unchanged. Strategic CH-G1–CH-G6 labels are separate from existing milestone gates. [NEXT_GATE_PROPOSAL.md](NEXT_GATE_PROPOSAL.md) awaits explicit user approval; no implementation follows from this pointer. Cursor governance review remains NOT_RUN / CHANNEL_UNAVAILABLE unless a direct authenticated channel is verified.


## FC-1 authorization and decision — 2026-10-14

The user approved the reconciliations and FC-1 only (DECISIONS D-009); earlier proposal/approval-stop text is retained as history. [FC1_DECISION.md](FC1_DECISION.md) records oracle qualification PASS for one exact Ucamco source, with [FC1_ORACLE_DERIVATION.md](FC1_ORACLE_DERIVATION.md) defining the independent expectations and numerical limits. Extended parser support and realistic PCB validation remain NOT_ESTABLISHED; Cursor review NOT_RUN / CHANNEL_UNAVAILABLE. MC-1 and FC-2A are not authorized, and no V2/V3 begins. Stop at this gate.
