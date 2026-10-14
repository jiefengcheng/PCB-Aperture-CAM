# Codex project status — initial bootstrap

- Scope: V1 Gerber independent validator, standalone project.
- Data authority: immutable starter synthetic source; P1 before X=20.35, generated candidate X=20.05, aperture X=20.00.
- Actual baseline Gerber supplied: **before only**.
- Actual generated candidate KiCad Gerber: **NOT_RUN**, must export with available `kicad-cli`.
- Internal geometry unit expectations from starter: earlier synthetic tests exist and must be reproduced by Codex.
- New bundle hash preflight: run `python3 tools/preflight.py`.
- KiCad DRC on target exports: NOT_RUN here.
- Independent real-export parser/geometry validator: NOT_IMPLEMENTED.
- V1 positive/negative checks: NOT_RUN.
- Cursor independent review: NOT_RUN / CHANNEL_UNVERIFIED.
- Manufacturing acceptance: NOT_ESTABLISHED / out of scope.

Codex: update this status after every gate, with dated commit, command receipts, and evidence paths, keeping unsupported conclusions explicit.
