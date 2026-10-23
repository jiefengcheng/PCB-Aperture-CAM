---
type: "review-guide"
title: "Profile a newly received dataset"
summary: "Create a sealed local copy and generic file-identity profile without claiming content qualification."
status: "draft"
generated: {"by": "codex/profile-materialization", "at": "2026-10-21T22:05:06+08:00"}
sources: [{"id": "profile-materialization", "resource": "/references/profile-materialization.json", "title": "Szu before/after persistence and retrieval evidence"}]
tags: ["pcb", "ingestion", "profiling", "custody"]
---

# General directory profiling

Use `tools/profile_dataset.py` when a received directory has no existing qualified package recipe. The program copies regular files without interpreting them, records relative source paths, byte counts, SHA-256 hashes and extension hints, then seals the staged result. It does not run parsers, CAM operations, native extraction or workbench publication.

```sh
.venv/bin/python tools/profile_dataset.py \
  --source /path/to/received/directory \
  --dataset-id client:project:revision:v1 \
  --output out/dataset_profiles/project-revision-v1

.venv/bin/python tools/profile_dataset.py \
  --verify out/dataset_profiles/project-revision-v1
```

The output must be a new directory under this checkout's `out/` or `dataset/`; existing profiles are never overwritten. Use `out/` for temporary review and `dataset/` for a durable local intake package. The output has preserved bytes in `raw/`, machine-readable profile, manifest, provenance, versions and a registration recipe under `metadata/`, a readable index, qualification/evidence boundary notes, and `SHA256SUMS`. The recipe is included in the package seal and records source/evidence bindings plus the explicit unqualified status. The profile records the selected source directory and its label; per-file identity uses source-relative paths and hashes. Extension labels are hints, not parser findings.

## Continue into the workbench

After profiling, verify the package, start the local ingestion server, then manually select the generated package directory with **+**:

```sh
.venv/bin/python tools/profile_dataset.py --verify dataset/project-revision-v1

.venv/bin/python tools/ingestion.py --serve --port 8769 \
  --output out/ingestion/workbench
```

Open `http://127.0.0.1:8769/index.html`, click **+**, and choose `dataset/project-revision-v1` (or the output directory you used). The browser computes file names, sizes and SHA-256 identities for the selected package and sends those identities to the loopback server; file contents are not uploaded. The server validates the sealed inventory and embedded registration recipe, registers the profile-only dataset, and publishes a new workbench revision. Reopening the published workbench restores the row from its saved registry. macOS directory pickers may omit `.DS_Store` from their selection list; the server still verifies that file against the package seal, while requiring the picker identities for all other files to match.

This addition step verifies custody and records file identity. It does not parse inputs, extract native objects, compare KiCad and Gerber data, run CAM operations, or qualify the dataset. The row remains `PROFILED_NOT_QUALIFIED`, `qualification` remains `NOT_RUN`, and engineering acceptance remains `NOT_ESTABLISHED`. The generated package uses local OKF-aligned documentation and metadata, but is not represented as a fully OKF-conformant corpus. A qualified package with saved review still uses its separately reviewed restoration recipe.

## Materialize records for the selected profile

For a profile-only row, **Board-record materialization → Run paired extraction** starts a dataset-bound read-only extraction. Each profiled row resolves its own `metadata/profile.json`, registration recipe and `SHA256SUMS`; processing does not borrow another dataset's historical catalogue or the most recently added profile. It inventories native KiCad objects and source-located Gerber plotting commands, retains parser/geometry warnings, persists versioned revisions in SQLite/content-addressed storage, then starts a fresh reader process and paginates every stored revision. The workbench changes the materialization/query statuses to complete only after the accepted receipt and fresh-process check verify.

The same operation can be reproduced directly:

```sh
.venv/bin/python tools/materialize_profile.py acceptance \
  --package-root dataset/project-revision-v1 \
  --dataset-id client:project:revision:v1 \
  --output out/ingestion/profile_materializations/project-revision-v1

.venv/bin/python tools/materialize_profile.py verify \
  --bundle out/ingestion/profile_materializations/project-revision-v1
```

The bundle contains `materialization.json`, the SQLite revision store and its content-addressed geometry payloads, `reopened.json`, and `acceptance.json`. Reopening checks package seals and source hashes, revision IDs, stored object and payload inventories, complete query pagination, and returned-record digests. Parser warnings and unsupported geometry stay attached to the records. A successful persistence/retrieval receipt does not qualify a copper change, native/Gerber correspondence, terminal identity, electrical connectivity, or manufacturing acceptance.

For the current `3020301113B` profile, the sealed `ORG/` and `EDIT/` directories are shown as before and after based on those source folder names. The run stored 358,989 records across 41 supported source files and returned all 358,989 in a distinct reader process. It retained 41 warning groups: 38 Gerber deprecation warnings, 2 native non-positive-stroke groups (2,708 and 3,412 objects), and 1 degenerate-arc group (84 objects). The native inventories contain no pad records, footprint references, or net names; Gerber file-function attributes are absent. Copper-area change and terminal/pad/connection matches therefore remain `NOT_ESTABLISHED`. The differing `F.Cu` primitive counts (17,849 before and 35,776 after) are inventory counts, not an area measurement. The [bound execution evidence](/references/profile-materialization.json) records output hashes, retrieval digest, warnings, publication and status limits.

The same server can also perform the registration without the browser for a reproducible local check:

```sh
.venv/bin/python tools/ingestion.py \
  --add-directory dataset/project-revision-v1 \
  --output out/ingestion/workbench
```

This first implementation supports ordinary files and nested folders. It rejects symbolic links, empty folders and source/output overlap. It preserves all regular files, including hidden files; it does not expand archives or filter temporary files. Keep sensitive inputs local and choose an identity that makes the intended revision clear.
