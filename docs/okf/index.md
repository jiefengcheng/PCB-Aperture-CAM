---
okf_version: "0.2"
---

# PCB/CAM durable runbooks

These instructions preserve repeatable procedures from completed project experiments. Run commands from the project root. They rely on the existing checkout and retained local inputs; this knowledge bundle is self-contained for reading, while execution requires the named project tools and data.

# Choose by intent

- [Visualize storage infrastructure](catalogue/storage-themes.md) - discovery, relationship grouping, actual on-disk structures and read-only selective export.

- [Bounded common catalogue](catalogue/minimum-slice.md) - implemented R140 records, retained qualifications, real reopened retrieval/export and final Cursor audit.

- [Add a dataset directory](ingestion/directory-intake.md) - restore a qualified sealed package through the + selector.

- [Dataset review layout](ingestion/visual-review.md) - shared Stored on disk / Input findings views and explicit availability states.

- [Latest ingestion maintenance](ingestion/maintenance.md) - refactor, corrected review metadata, publication safety and fresh Cursor audit.
- [ORG WKB-to-SVG fidelity](ingestion/org-svg-fidelity.md) - measured display-path round-trip, fill semantics and bounded error for the pinned map.
- [Manual review and execution guide](ingestion/manual-review.md) - start here for the consolidated delivery, expected results, isolated reruns and Step 2 review notes.

- [Start and custody](runbooks/start.md) - check applicable source versions, runtime and frozen assets.
- [Verify a registered dataset](runbooks/dataset.md) - offline hashes, provenance and intake limits.
- [Review the existing workbench](runbooks/workbench.md) - replay recorded evidence without running a transformation.
- [Reproduce the bounded client case](runbooks/client-case.md) - create a new local operation and visual replay with controls.
- [Export native artwork](runbooks/native-export.md) - fresh KiCad outputs from copies or a registered native input.
- [Discovery, storage and consolidated demo](runbooks/pipeline.md) - the existing native catalogue pipeline and its broader recorded demo.
- [Evidence and scope register](experiments/register.md) - which experiment supports each recipe, and instructions not promoted as durable.
- [Cursor ingestion audit](ingestion/cursor-audit.md) - independent scoped verdict and unrun-check limits.
- [Ingestion baseline](ingestion/baseline.md) - read-only registration, provenance, qualification and reproducible workbench entry.
- [Ingestion consolidation handoff](ingestion/handoff.md) - agreed next-chat work, evidence locations and completion criteria before common catalogue design.
- [Sources and OKF conventions](references/project-sources.md) - exact documentation/code bindings and metadata conventions.
- [Update history](log.md) - curation changes.

# Read first

Verify applicability before executing a recipe:

```sh
.venv/bin/python docs/okf/references/verify_runbooks.py
```

A PASS confirms recorded source/evidence hashes, metadata links and recipe syntax. It does not execute the commands or reconfirm engineering outcomes. A source change is STALE, requiring review of the affected recipe. No historical acceptance or independent review transfers automatically to a new run.
