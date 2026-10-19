---
type: "review-guide"
title: "Restore a dataset by selecting its directory"
summary: "Project-local directory selection restores an already-qualified sealed package, registration and recorded review."
generated: {"by": "codex/directory-intake", "at": "2026-10-17T23:34:30.710992+08:00"}
status: "stable"
tags: ["pcb", "ingestion", "directory", "persistence"]
sources: [{"id": "restoration", "resource": "/references/directory-intake.json", "title": "Directory restoration execution and checks"}, {"id": "removal", "resource": "/references/dataset-removal.json", "title": "Persistent dataset-row removal and reconstruction checks"}]
---

# Add the preserved directory

The **+** beside Registered dataset opens a directory selector. Select `dataset/vme-wren_20261016_v1`. The directory contains one KiCad board, 39 Gerbers, two drill files, a layer-description file, the original ZIP, metadata and retained evidence. All 71 package files are checked, including the package seal.

The browser hashes the selected files. It sends relative file names, sizes and hashes to the local server; it sends no file contents or external requests. The server checks these identities against the qualified project-local package, verifies its complete inventory and seal, restores the registration and publishes a new review revision. After successful publication the browser selects Client VME-WREN. Reloading keeps that dataset because its registration is saved in the new run's `registry.json`, not only in browser memory.

The prior entry remains published if validation or publication fails. Cancellation changes nothing. An identical already-registered package remains one row; a conflicting registration is rejected. Historical runs, immutable source packages and the canonical registration contract remain untouched.

# Remove a saved row

Select a dataset and click **−** beside **+**. This removes only that dataset registration from the current saved dropdown and publishes a new workbench revision. It survives reload, server restart and an ordinary rebuild. The original Gerber/KiCad inputs, qualified package recipes, retained evidence and historical workbench runs are not deleted. Use **+** to restore the supported sealed client package later. Other datasets need their applicable registration recipe; the + directory workflow is still limited to the qualified VME-WREN package.

With no rows remaining, the view says No datasets registered, + stays available and − is disabled. Missing/unknown selections and failed publication leave the previous entry intact. Historical run URLs retain their original rows because they are immutable snapshots. Open the current entry rather than an older run to see the saved removal.

An ordinary rebuild now reads the current published registry. Supplying `--registry` explicitly chooses that recipe and can intentionally reconstruct rows it contains; the canonical recipe remains unchanged.

# What is restored

**Stored on disk**, **Input findings**, saved comparison geometry, receipt-derived measurements and evidence links return when their retained bindings are available and verified. Cases continue to expose the existing recorded operations and rejection controls. These are historical REPLAY. No new CAM operation or native export runs during restoration.

The raw package supplies both the KiCad and Gerber representations. Restoring its registration does not create extracted KiCad pad/track records, a client board database, a common object catalogue or reopened board queries. Their existing Not implemented statuses remain visible.

The restoration recipe lives independently of the dropdown in `contracts/ingestion_packages_v1.json`. It binds the package seal and retained qualification/render inputs. This is why a missing dataset row can be reconstructed. The sealed folder alone does not contain every retained replot and operation input used by this review. Missing or changed dependencies cause rejection rather than invented comparisons. This first workflow supports the known sealed VME-WREN package at its project-local location; unfamiliar directories have no qualified restoration profile and are rejected explicitly. This is not general ingestion of arbitrary raw folders.

# Run locally

The directory action needs the local ingestion server, rather than the older static preview server:

```sh
.venv/bin/python tools/ingestion.py --serve --port 8769 \
  --output out/ingestion/directory_intake/workbench
```

Open `http://127.0.0.1:8769/index.html`. The server binds only loopback and accepts mutation requests only from its own origin. It serializes intake requests. Do not run another publisher against the same entry concurrently.

The equivalent command uses the same verification and restoration logic:

```sh
.venv/bin/python tools/ingestion.py \
  --add-directory dataset/vme-wren_20261016_v1 \
  --output out/ingestion/directory_intake/workbench
```

Only derived files under `out/` are written. Atomic entry replacement preserves the prior entry on detected failure; power-loss recovery remains NOT_ESTABLISHED.

# Execution evidence

The [restoration evidence](/references/directory-intake.json) records a real four-row baseline, selection through the + directory picker, restored fifth row, comparison/measurement checks, publication verification and negative controls. Independent review of this directory feature is NOT_RUN. The [shared review guide](/ingestion/visual-review.md) explains the three workbench sections.
