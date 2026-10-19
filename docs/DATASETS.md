# Local client dataset register

Client source bytes and their OKF knowledge bundles live under Git-ignored
`dataset/`. This document retains a small discovery and custody record; it does
not contain the client PCB artwork.

Durable operational instructions are maintained in the separate
[project OKF runbook bundle](okf/index.md), linked from the local dataset
catalogue. It covers already exercised intake checks, visual replay, bounded
client reproduction, native exports and the existing discovery/storage pipeline.
Runbook updates do not change the frozen source package or its seal.

## VME-WREN intake — 2026-10-16

- Dataset ID: `client:vme-wren:20261016:v1`
- Packaging version: `1.0.0` (not a CAD design revision)
- Entry point: [dataset/vme-wren_20261016_v1/index.md](../dataset/vme-wren_20261016_v1/index.md)
- Contents: one native KiCad board, 39 Gerbers, two Excellon drill files,
  `layerfunction.txt`, original `testDemo.zip`, provenance and prior evidence.
- Source payload: 113,075,667 bytes; 44 raw files including the original archive.
- Native source SHA-256:
  `f3d5d3e60f2a7fae25d9d1b1741335c8765409405833e32a0948a83c984b1b6d`
- `SHA256SUMS` external seal:
  `7b1374e5eeb4cac943f3d7512a19da8a65a93212bd6bfa80c006930c85bc9e0e`
- Manifest SHA-256:
  `bb48313b4b875b9a1e2b94d8512e7d2c967d96f20c59dcac9245f92c95aab07a`

From the project root, run:

```sh
python3 dataset/vme-wren_20261016_v1/scripts/verify.py \
  --expected-seal 7b1374e5eeb4cac943f3d7512a19da8a65a93212bd6bfa80c006930c85bc9e0e \
  --receipt out/dataset_registration/verify.json
```

The verifier requires Python 3.9+ and its standard library only. It works from
any working directory when invoked by absolute path. It checks file hashes,
strict inventory, emitted OKF structure and links, all 42 ZIP members against
their raw copies, and historical comparison source bindings. A PASS does not
recompute geometry or establish electrical correctness.

Organization follows [Google Open Knowledge Format v0.2](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/SPEC.md).
The JSON manifest, raw-file layout, SHA-256 index and runner are documented local
extensions, not Google-defined dataset packaging rules.

The representations remain **partially matched**. The prior R140.1 B.Cu/mask
region matches; L2GND has a confirmed copper discrepancy. Exact whole-board
revision equivalence, electrical correctness and manufacturing acceptance remain
NOT_ESTABLISHED. No pcb_Z ingestion runs as part of registration.

The original inputs remain at their existing locations. Future raw revisions
receive new dataset directories; derived extraction/index/database/run artifacts
belong under `out/` with dataset ID and source hashes. Existing workbench pointers
and frozen evidence are not redirected by this registration.
