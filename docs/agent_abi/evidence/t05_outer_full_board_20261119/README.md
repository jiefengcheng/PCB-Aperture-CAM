# Retained 3020301113B full-board T05 result

One original source constructor and two public-only certificate readers passed on the exact saved legacy T04/T02 checkpoint. The readers performed zero construction, source reparse, composition or physical rechecks. All 7,730 decisions, 771 grown routes and 7,991 attachment outcomes are accounted for. All 771 actual patch blobs and complete before/after copper matched the retained fully checked result byte for byte: 0% per-route and aggregate added-copper difference, within 20%. Memo stayed 512 MiB; no measurement bank or extra reference run was used.

| Measured scope | Seconds |
|---|---:|
| Construction process, including original physical checks and sealing | 3084.547227 |
| Two public readers, concurrent wall | 18.528234 |
| Execution including prepared setup, counted once | 3191.915613 |
| Additional independent read-only qualification | 42.286876 |
| Total with read-only qualification | 3234.202489 |

Standalone T05 was 53m 54.20s including qualification. Upstream T02 was reused; this is not a fresh combined T02/T05 time or a controlled A/B savings claim. The separate 133-test integration preflight was 16.10s. Refer to [disjoint timing](TIMING.json), [timing chart](TIMING.svg), [result](RESULT.json), [external stopwatch](OUTER_TIMING.json) and [readback](READBACK.json).

[Signed root](OUTER_CERTIFICATE.json), [public anchor](PUBLIC.pem), [coordinator binding](EXPECTED.json), [reader 1](CONSUMER_1.json), [reader 2](CONSUMER_2.json) and [bundle checksums](BUNDLE_MANIFEST.json) preserve the recorded proof identities. These are historical execution receipts, not a new certificate issued for this Git commit. The original frozen producer was `007cf21c8b0356bd525975be76a214d2c6bcbb80ca744681db6cb3cff4ef9d9b`; the full job/source capsule remains unchanged on LaCie. Actual stage SHA: `729d60c77eee51f511e9e34c27e543b83ac20d8562a3a0c90e36c76bcbb53fdc`.

[Original terminal manifest](TERMINAL_MANIFEST.json) also names raw geometry/profiles that remain on LaCie and are deliberately absent from this small receipt bundle. Its hashes were reread before packaging. [Original report](ORIGINAL_REPORT.md) is kept verbatim, including its local evidence references; use this README for portable links. Reproducing the full geometry qualification requires those retained artifacts and the exact historical source/policy custody. No client Gerber, patch WKB or private key is included here. The public key is not a signing capability.

Pin intent remains UNDECLARED. Legacy diagnostic scope only; connected finishing, export/reparse, render and delivery were NOT_RUN, and electrical/manufacturing acceptance is NOT_ESTABLISHED. Independent review is NOT_RUN / CHANNEL_UNAVAILABLE. Repeat-build determinism is a separate audit not performed by certificate readers. The future joined test with developing T04 is PENDING, not supplied by these saved-checkpoint receipts.
