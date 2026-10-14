# Consolidation acceptance audit

This audit covers the eight outcomes of CODEX_CONSOLIDATION_HANDOFF.md and its
A/B/C/D work packages. It does not turn explicitly unknown/deferred capabilities
into an aggregate electrical, manufacturing or independent-review PASS.
Exact run paths and hashes are in FINAL_EVIDENCE.json and CONSOLIDATION_DECISION.md.

| Requirement | Authoritative evidence and checked scope | Disposition |
|---|---|---|
| A1 / RPL-01: one event projection | replay_model.js; accepted/rejected model tests; native browser red control of preserved original; nine events, 82 control-cycle checks, 18 actual resizes and nine synchronized pans | Established for retained snapshots; intermediate/missing execution geometry unavailable |
| A2 / UI-02: requirement versus observation | finding_navigation.json: HAL open shows 15 broken relationships; bridge names /HDMI.D2+, /HDMI.D2- and GND; fault-test PASS separate from candidate FAIL | Established |
| A2 / UI-03: precise records and source labels | Generated finding pages resolve exact RFC 6901 pointers at generation; complete source reports remain linked; final source-name/raw-code navigation check | Established in recorded cases |
| A2 / PROV-04: execution/build/seal | Frozen execution core revision, captured clean visual build revision/source hashes, separate append-only seal receipt; old dirty metadata preserved | Established; no authorship/live-source claim |
| A3: visual correctness boundary | Qualified exported-Gerber layers, shared coordinates, display simplification isolated; 30 case/state/mode combinations, checksums and immutable controls | Established in native Codex in-app browser; no universal-browser claim |
| B1 / LZ-01: declared inventory | Five source datasets; counts reconcile source objects/layer instances/available geometry; nested pads, arcs, vias, fills/voids, transforms/repeated IDs and explicit unsupported reasons tested | Established within declared extraction/geometry scope |
| B1: conservative proximity | Brute-force recall comparisons; outward-rounded finite envelopes, overflow rejection; recorded within-2-mm queries and query/candidate/exact-witness overlay | Established for declared nominal geometry; proximity does not merge components |
| B1: topology after removal | Removal and shaving tests recompute split components; singleton/component counts retained separately from PCB_GROUP | Established |
| B2 / LZ-02: revision-safe identity | Catalog keys include revision/occurrence; same UUID on boards/revisions, repeated references, parent FKs and duplicate proof occurrences tested | Established; UUID is metadata, never a global key |
| B2 / LZ-03: exact original source | Source SHA plus byte spans; UTF-8/quotes/comments/CRLF tests; CAS source bytes and browser excerpts verified against original bytes | Established; no reserialization preservation claim |
| B2: persistence/query errors | Reopen/idempotence, partial import rollback, corruption/index/source drift, cache invalidation, private cache copies, missing/error/cancel/truncated distinctions and work/byte limits | Established in application-consistency scope |
| B2: area/aspect definitions | Filled area and bbox area separate; width/height aspect with degenerate status; recorded component envelope-area/aspect filtering | Established as diagnostic metrics, not manufacturing rules |
| B3 / LZ-04/05: controlled selection | Explicit empty/all, named group/object/region, deduplication, missing/ambiguous/cyclic references, bounded dependencies/context and protected write allowlist tests | Established |
| B3: selective native export | General legacy reassembly explicitly UNSUPPORTED; preserved source artifacts/locators form diagnostic bundles; actual supported coupon export uses unchanged V2 | Allowed fallback delivered; general exporter not promoted |
| C: one shared surface | Processing/Cases/Storage in same HTML; seven real source stages with actual receipts/counts/omissions/timings, bounded object list/viewport and full original evidence | Established; missing historical timing remains NOT_RECORDED |
| C: linked object/context/case | P1 record/source → T1 witness → Cases; source-bound reverse navigation; physical six / writable four / protected P2+T4; native/reference switching preserves geometry | Established for recorded mappings; ambiguous/unavailable mapping refuses |
| C: public/legacy limits | HAL same-layer findings, GlowStitch unknown electrical intent, legacy Group_55 diagnostic selection and unsupported shapes; public permissions disabled/reset | Established as read-only context/regression, not approved edits |
| D: real native reuse | Pinned dirty-source content, copied build inputs, actual DB0 executable and APIs, source/binary hashes, materializations and child processes | Established for typed graph reads; no mock native PASS |
| D1: identity/scope/proof parity | Full-string identity/local VID/local tag tests, 0/254/255 boundaries, incoming/outgoing direction, layer/type/revision rejection, duplicate proof retention, six real outgoing whole-materialization parity scopes | Established in explicitly recorded scope; other read guarantees not inferred |
| D1 / recovery: partial index build | FILES_STAGED/INDEX_BUILT faults retain previous queryable materialization; stale/corrupt/missing/truncated results explicit | Established at application level, not power-loss durability |
| D2: real workload measurements | Five datasets; extraction/decode/geometry/index/persistence/query/serialization timings, SQL plans, region/proximity/component queries, actual native probes and child memory; browser DOM timing separate | Measured; three repetitions, OS caches uncontrolled, no production/GPU speed claim |
| D3: component decisions | Catalog ADOPT; SQLite, libspatialindex and GEOS KEEP_REFERENCE; gfs SHADOW_ONLY; custom C++ B/R-tree DEFER | Decisions established; custom-index capability remains unavailable in admitted source |
| E: unchanged approved operation | Reopened catalog context admitted to same frozen contract; actual pinned KiCad exports; independent frozen validators; candidate SHA equals original acceptance; 13 Gerber controls plus executor failures/rollback | Established for same synthetic MovePadWithConnections family |
| Custody / reproducibility | Initial 56 regressions and final 110 tests; 70 asset hashes; 1,268 historical hashes; source-stability guards; one aggregate command; snapshot verifier; clean-source generation and local commit seal | Established within named runs and retained workspace |
| Governance / scope | Frozen commits/contracts/decisions retained; no public edits, new repair families, V3, shared-core/global writes or remote publication; frozen read-only review packet | Established operational scope; Cursor NOT_RUN: CHANNEL_UNAVAILABLE |

## Qualifications preserved

Original aggregate V1.5 and GlowStitch electrical intent remain NOT_ESTABLISHED.
HALPI2 qualification remains bounded same-layer native intent, without schematic,
cross-layer or signal-integrity acceptance. Native geometry omissions remain
unknown even when an available-geometry query is complete. Neither graph traversal
nor physical grouping grants edit permission or replaces independent validation.

Custom C++ B-tree/R-tree APIs were not established in the admitted source; their
DEFER disposition satisfies the mandate's explicit-gap fallback, not native
index integration. Native licensing remains NOT_ESTABLISHED for redistribution.
General native reassembly, full crash/power-loss durability, shared-core concurrent
snapshot/cancellation/thread guarantees and manufacturing release are outside the
established result. Cursor review was not run and is not simulated by this audit.

## Evidence history and verification limits

The original defect red control is explicitly a post-implementation native-browser
reproduction of the preserved original; the supplied review already retained its
own earlier reproduction. No earlier execution date is invented. The first final
resize attempt targeted another browser selection (actual dimensions stayed
1280×720); its failed receipt is retained. A dedicated selected tab then verified
all requested dimensions. It is excluded from successful resize counts.

The full browser matrix binds the 6a66857 bundle. The final 6396170 change only
maps source trace net labels and adds their raw-code metadata; the event model,
pipeline/backend models, geometry drawing and replay controls are unchanged.
Final targeted label/navigation/context checks bind the new clean-source bundle.
The old matrix is not relabeled as a new run. All source/output hashes remain
available for that distinction.

Earlier failed native builds, the restored historical pointer, and the documented
producer-source-drift observation remain retained. Their outputs are not promoted
as final source-bound evidence. The final mechanical audit verifies current hashes,
reopened revisions, native materializations and candidate identity; it is one
part of this requirement audit, not an independent engineering review.

## Final disposition

The eight consolidation outcomes are established within the scopes above. The
explicit-gap fallback is used for custom native B/R-tree reuse and general native
reassembly; neither is marked PASS. No in-scope implementation item remains open.
Independent Cursor review remains unavailable and manufacturing acceptance remains
NOT_ESTABLISHED. Final source is 6396170; the separate seal binds the later local
documentation commit without rewriting generation or execution metadata.

The HTML embeds its scene/viewer and has no external script/style/media loaders.
The optional direct-file runtime check was blocked by the browser URL security
policy (http/https only); no bypass was attempted. Offline local-server operation
was tested, while direct-file launch remains NOT_RUN in this browser.
