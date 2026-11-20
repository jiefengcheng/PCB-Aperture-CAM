# T05 source construction and public certificate consumption

This explicitly selected legacy T05 route runs one source constructor, then two public-only readers, replacing the two full reconstruction workers for acceptance. All original physical proposal checks, actual stored-patch binding, attachment/KEEP/scope/source/pin/void guards, real scene composition and final worker guards remain at issuance. Public readers authenticate the completed root, frozen inputs, actual artifact bytes, exact local containment, original window witnesses and complete accepted-prefix chain; they do not reconstruct routes, reparse source, compose copper or repeat clearance checks.

The coordinator generates an ephemeral P-256/SHA256 key. The constructor receives signing capability through an anonymous inherited FD. Readers receive only the coordinator-pinned public anchor and expected-binding hash through separate anonymous FDs. Inner HMAC authority is authenticated live before publication, and no private or HMAC key is persisted. Arbitrary unsigned retained JSON is never treated as authority. Repeated-build determinism remains a separate audit.

Configured source memo: 510.5 MiB geometry + 0.5 MiB inner ledger/index + 1 MiB bounded outer journal = 512 MiB. Public readers use no construction memo and have a separately bounded 64 MiB read-manifest metadata pool. These accounting bounds are not process RSS or transient native geometry limits. This source path does not require the 160-route reference-fitting bank.

The retained full-board result passed with 7,730 decisions, 771 grown routes, 949 physical issuance checks and zero outer physical rechecks/rebuilds. Both readers together took 18.528234 s. Complete time including setup was 3191.915613 s; including independent read-only qualification was 3234.202489 s (53m 54.20s). All 771 patch blobs and before/after copper matched the retained fully checked result. [Result and proof receipts](evidence/t05_outer_full_board_20261119/README.md) preserve the exact historical producer and scope. No new full-board or reference run is performed by this commit.

The source-isolated Git line intentionally excludes the developing T04 algorithms and T02 sizing changes. Existing committed T04/T02 code provides the small regression fixture only. T05 uses its unchanged no-elapsed-cutoff policy locally, while T04/T02 bounds and geometry remain at the branch base. Shared edits are limited to T05 dependencies, opt-in certificate/parse hooks and actual validated-read/completion observations. The future joined T04/T05 qualification remains pending. Historical full-board measurements describe their exact frozen producer, not a newly issued acceptance for this separated commit.

## Explicit checkpoint route

```sh
tools/Run_T05_Certified_Checkpoint.command --prepare "/absolute/completed/job/legacy" --t04-sha256 "exact-retained-checkpoint-hash"
# Execute the returned fresh job only when separately authorized:
tools/Run_T05_Certified_Checkpoint.command --measure "/absolute/prepared/job"
```

The route validates exact historical T01/T03/T04/T02 bytes, paired receipts and named producers, then copies them into a new LaCie job and seals current options/source. It does not relabel historical assembly as a current live assembly. A frozen plan/expected binding and exclusive latch prohibit retry or resume. The constructor's file fence permits only fresh-job writes and exact named historical reads. Any missing/changed proof or failed check halts with preserved evidence and later operations NOT_RUN; there is no fallback rebuild or resealing.

Use `tools/Run_PCB_Tests.command` for the focused certificate/cache controls. LaCie must be prepared before engineering writes. Existing source/export policies and default connected operator behavior remain unchanged. Pin intent in the retained result is UNDECLARED; no connected finishing, export/render/delivery, electrical or manufacturing acceptance is implied. Independent reviewer remains NOT_RUN / CHANNEL_UNAVAILABLE.
