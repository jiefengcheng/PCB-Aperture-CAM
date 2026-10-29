# Owner-accepted C01 and C02 results — 2026-10-30

Open `index.html` for the two frozen visual results. Both are **owner accepted, final so far**. The acceptance receipts supersede the construction-time `PENDING_USER` and experimental labels retained unchanged inside the historical result/replay files. Those files are not silently rewritten.

| Crop | Accepted geometry SHA-256 | Order |
|---|---|---|
| C01 | `587d10f5855c4b7afe2f37130277d3c0bdc711b84b74c0dd8c69f6d4ff932966` | Existing frozen T01 → T04 → T05; no T03 route change; T02 skipped by owner |
| C02 | `60f60b0012277f28fad494df16e14957fa8196fcd11475a5cafb42500918040a` | T01 → T03(no route change needed) → T04 → T02 → T05 |

## Included

- Complete C01 accepted spindle result260 snapshot and owner-freeze261 receipt.
- C02 generated result263: exact before/after/addition WKB, accepted patch/window/owner geometry, every route decision, final checks, rendered full crop and original run-bound source snapshots.
- C02 constructor replay264, runtime, focused test log and fixed-bulk coverage reconciliation.
- C02 visual review265 with all 19 image bindings and eight same-frame detail pairs.
- C02 latest predecessor-freeze262 and owner-freeze266 receipts, plus the hashes of their complete local freeze contents.
- `SHA256SUMS.json` enumerates every file actually included in **this Git result delivery**.

The full local C02 freeze includes 881 files under `out/crop_dynamic_tasks/c02_final_so_far_freeze_20261030_266/`; the Git delivery intentionally omits the large original-board source manifest/cache, 606 predecessor-source replacement files and duplicate local freeze copies. `LOCAL_FULL_FREEZE_SHA256SUMS.json` records those original local scopes, not a claim that every listed file is present here. No raw KiCad board or original customer source cache is uploaded. Generated result geometry and visual evidence are included under the owner's explicit commit-and-push instruction.

Historical `source_snapshot/` scripts preserve exact execution text; they are archival evidence, not portable scripts to execute from docs. Production entry points are under `tools/`. Their source-bound constructor replay requires the retained project-local input cache and frozen `out/` evidence; a fresh clone with only this result delivery does not contain all original inputs.

## Verify the checked-in delivery

```
.venv/bin/python tools/verify_accepted_t05_results.py docs/results/t05_20261030
```

This checks the delivery hashes and local links, exact accepted after/predecessor bindings, valid additive geometry with no material predecessor loss, C01 frozen snapshot file hashes, all 56 saved C02 patch/window/owner records and the recorded source-bound replay identity. It does not rerun the omitted original-source constructor replay or establish independent/electrical/native/manufacturing acceptance.

## Preserved limits

C01: five branched/mixed components and one contacted component remain untreated in the accepted displayed result. C02: 57 unchanged routes are accounted for (51 have no exposed qualified land contact, five produce no new copper, one rejects disconnected/invalid candidate geometry). Sixteen exposed fixed nonroute sources match the existing owner-directed bulk skips; no new exclusions were added.

Current local source-bound C02 constructor replay passes. The inherited independent REV234 verdict remains **REVISE_STRICT_EXACT_REPLAY_NOT_CLOSED**; human visual acceptance does not waive that historical cross-runtime failure. Native export, electrical intent and manufacturing qualification are not established by these results. C03 remains stopped.
