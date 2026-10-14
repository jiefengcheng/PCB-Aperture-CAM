# Codex-only coordination; independent Cursor verification

Codex is the **sole coordinator** for this project. No human relay is part of the protocol. Do not presume that Codex and Cursor have a universal messaging interface. First *discover and verify* an existing direct Cursor tool, integration, or authorized agent execution channel from Codex. No global installs or credentials changes just to make it work.

**If a direct channel exists**, freeze a V1 implementation commit/hash; hand Cursor read-only access to this one checkout (ideally a dedicated read-only worktree) plus `docs/ACCEPTANCE.md`, parser/version inventory, `out/v1_validation.json`, the exact commands and negative-test fixtures. Cursor must not modify either this repository or any other lane. Codex remains the integrator and retains raw review evidence under `reviews/cursor/` (only after review actually occurs).

Ask Cursor to independently challenge: Gerber X2 file polarity (including F.Mask negative), Y mapping, flashed pad vs drawing semantics, arc/cap tolerances, copper component extraction, intended net vs physical connectivity, scope and unchanged protected shapes, false-positive acceptance on 6 negative tests, evidence completeness, and immutability. Request explicit reviewed commit/hash, tests independently run, reproducible findings and severity.

**If no direct channel exists**, set `cursor_review.status = NOT_RUN`, `reason = CHANNEL_UNAVAILABLE`; create a review packet under `out/` for a future automated channel and stop. Do **not** claim Cursor reviewed. Do not ask the user to copy comments back and forth. This must not block local deterministic validation work but blocks any assertion of independent Cursor review.

Any future write delegation needs separate explicit permission, non-overlapping tasks and a branch/worktree *in this repository only*. Other Codex/Cursor research projects and lanes are out of scope.


## Authorized V1.5 amendment — 2026-10-14

The user authorized public reference acquisition and read-only realistic-design qualification after frozen V1. See `docs/ROADMAP.md` for the binding sequence, separate gates and stop line. Preserve V1 source assets, policy, implementation and acceptance result. External inputs belong in immutable `external/sources/`; derived evidence belongs in `out/v1_5/`. GlowStitch precedes HALPI2-HDMI-FPC and official Ucamco parser fixtures. Public compatibility does not establish electrical/manufacturing correctness or authorize V2/V3. Cursor review requires an actual authenticated channel; none has been verified.


## Charter alignment — 2026-10-14 (documentation only)

[PROJECT_CHARTER.md](PROJECT_CHARTER.md) is the reconciled proposed strategic reference. [CHARTER_INTEGRATION.md](CHARTER_INTEGRATION.md) records the conflicts and proposed corrections; [CHARTER_EVIDENCE_AUDIT.md](CHARTER_EVIDENCE_AUDIT.md) checks retained evidence and records current verification limits. Frozen V1/V1.5 results, operational isolation and acceptance contracts remain unchanged. Strategic CH-G1–CH-G6 labels are separate from existing milestone gates. [NEXT_GATE_PROPOSAL.md](NEXT_GATE_PROPOSAL.md) awaits explicit user approval; no implementation follows from this pointer. Cursor governance review remains NOT_RUN / CHANNEL_UNAVAILABLE unless a direct authenticated channel is verified.
