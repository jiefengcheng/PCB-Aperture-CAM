## Additive Read-Only Audit (Same Frozen Packet)

Scope followed: read-only, in-checkout only, no edits, no installs/network/subagents, no temp-file tests.

### Independent commands executed and outputs

```text
$ git rev-parse HEAD
19ff47204d429b93fdac21d3b1a94ed3462b3629
```

```text
$ PYTHONDONTWRITEBYTECODE=1 python3 <packet-hash-check>
packet_schema pcb-cursor-readonly-audit-packet-v1
packet_head 19ff47204d429b93fdac21d3b1a94ed3462b3629
file_entries 14
missing_count 0
mismatch_count 0
packet_hash_verification PASS
```

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/ingestion.py --verify out/ingestion/workbench/run-05888c57424f4db48bd9821fc8324b36
{"status": "PASS", "schema": "pcb-ingestion-publication-v2", "scope": "Required files, exact inventory, embedded scene, registry, receipt-derived measurements and evidence/render-input bindings; no engineering acceptance or authorship claim", "run": "/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/ingestion/workbench/run-05888c57424f4db48bd9821fc8324b36", "outputs_verified": 351, "datasets_verified": 5, "comparisons_verified": 3}
exit=0
```

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/ingestion.py --verify out/review/ingestion_assessment_20261016T184844_296975Z/empty_failed
{"status": "FAIL", "error": "Unsupported/missing publication schema; legacy v1 is unqualified"}
exit=1
```

```text
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/ingestion.py --verify out/review/ingestion_assessment_20261016T184844_296975Z/empty_unknown
{"status": "FAIL", "error": "Unsupported/missing publication schema; legacy v1 is unqualified"}
exit=1
```

No permission/sandbox restriction blocked these commands.

---

### Findings and R1–R4 reassessment

- **R1 (false-positive verifier acceptance): PASS, independently confirmed.**  
  - Trigger: verifying retained `empty_failed`/`empty_unknown` controls.
  - Expected: nonzero exit and rejection.
  - Actual: both return `FAIL` with `exit=1`.
  - File/line anchor: File `src/ingestion_verification.py`; lines enforcing schema/status/required outputs are present.

- **R2 (actual render input binding/drift): no new defect found; independent adversarial runtime not re-executed in this pass.**  
  - Command-level verifier on published run passed (`comparisons_verified=3`), and code path remains bound through receipt/inputs.
  - File/line anchor: File `src/ingestion_visuals.py`; verify-before/after composition logic present.
  - Status: **supported by code+published-run verification; not adversarially re-proven here**.

- **R3 (cross-pane geometry leakage): no new defect found; browser not re-run now.**  
  - File/line anchor: File `web/ingestion_views.js`; source/native/delta panes are explicitly separated.
  - Status: **code-supported; live browser confirmation remains unrun in this pass**.

- **R4 (hardcoded/cross-dataset measurement leakage): no new defect found; browser/test replay not re-run now.**  
  - File/line anchor: File `web/ingestion_views.js`; uses dataset `qualification_data.records` rendering rather than literals.
  - Status: **code-supported; not re-executed interactively here**.

---

### Remaining unrun checks (explicit)

- Live browser visual inspection of panes and links in this session: **NOT_RUN**.
- Unit/JS test suites that may create temp files: **NOT_RUN by instruction**.
- Any mutation/adversarial temp-workspace checks: **NOT_RUN by instruction**.

These are **execution gaps due requested scope/constraints**, not newly observed code defects.

---

### Metadata/status handling note

- The published run’s `NOT_RUN: CHANNEL_UNAVAILABLE` in `receipt.json` is historical generation-time metadata and was not modified.
- Current review capability is now evidenced by this independent command execution addendum.
- Concrete advisory retained: avoid hardcoding review-channel status in future build outputs (prefer run-context/status injection).

---

## Scoped Verdict

**QUALIFIED_IN_DECLARED_SCOPE**

Reason: all requested independent non-mutating checks succeeded exactly as expected (HEAD match, packet hash recomputation PASS, published run verifier PASS, both retained controls rejected with nonzero exit).  
Limits: browser/runtime UI inspection and temp-file-producing test reruns were intentionally not executed in this pass.
