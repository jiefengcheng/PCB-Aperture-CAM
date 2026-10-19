---
type: "Reference"
title: "Project runbook provenance"
description: "Code and document hashes identify applicability without inventing independent review."
generated: {"by": "codex/pcb-cam-runbooks-v1", "at": "2026-10-16T14:43:36.762882+00:00"}
status: "stable"
tags: ["pcb", "cam", "runbook", "project-local"]
sources: [{"id": "implementation", "resource": "/references/sources.json", "title": "Version-bound implementation and source register"}]
---

# Provenance

[Source bindings](/references/sources.json) record original project-relative paths and hashes. Authoritative source documents are mirrored unchanged as `.txt` attachments so every Markdown concept remains OKF-conformant. Implementation stays in its original project location; it is referenced by hash, not copied into a second executable lane.

[Historical experiment references](/references/experiments.json) identify the actual retained receipts. Their existence and hashes are checked, while engineering claims retain their original scope. No Cursor/human verification event is invented.

# OKF

This knowledge bundle follows [Google Open Knowledge Format v0.2](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/ad30107c31c06aec8a7d5636e0d1058118604e6f/SPEC.md): typed Markdown/YAML concepts, sources, indexes, links and a dated log. Root index carries only the OKF version. JSON values in YAML frontmatter provide a valid, easily parsed subset.

The source-binding schema and verifier are local extensions. Execution requires this repository and its named local dependencies. The frozen client data bundle remains separately sealed; runbook curation does not rewrite its manifest.

# Maintain

When source code or source documents change, verify applicability and review affected instructions before updating their source hashes/snapshots. Preserve historical receipts. Run the structural/source checker after editing; new experiments need their own evidence. Durable instructions do not grant permission for new repair families or external actions.
