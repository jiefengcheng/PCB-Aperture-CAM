## Findings

- **High — Published workbench `common_context` is bound to stale pre-fix execution and currently fails independent verify (blocking).**  
  - **Where:** `out/ingestion/directory_intake/workbench/run-86e1ffc195954d1c8ef871e86e7afc19/registry.json:1384`  
  - **What:** The publication points `common_context` to `out/common_catalogue/execution_20261018_d/acceptance.json` (dataset revision `ad4134...`), not the documented final follow-up execution `execution_20261018_e` (`b39d33...`) in `docs/catalogue/DELIVERY.md`.  
  - **Reproduction:**  
    - `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/ingestion.py --verify out/ingestion/directory_intake/workbench/run-86e1ffc195954d1c8ef871e86e7afc19`  
      - Result: `{"status":"FAIL","error":"NATIVE_QUALIFICATION_SEMANTICS_MISMATCH"}`  
    - `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/common_catalogue.py verify --bundle out/common_catalogue/execution_20261018_d/selection --revision ad413456...`  
      - Result: `FAIL / NATIVE_QUALIFICATION_SEMANTICS_MISMATCH`  
    - `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/common_catalogue.py verify --bundle out/common_catalogue/execution_20261018_e/selection --revision b39d33db...`  
      - Result: `PASS`  
  - **Impact:** Latest receipt-derived UI runtime is available but not verifiable in declared scope; fail-closed behavior is working, but delivered publication binding is stale, so this follow-up remains blocked.

```1380:1386:out/ingestion/directory_intake/workbench/run-86e1ffc195954d1c8ef871e86e7afc19/registry.json
"scope": "Preserved files, registration and recorded review; no native extraction or new CAM execution"
},
"common_context": {
  "path": "out/common_catalogue/execution_20261018_d/acceptance.json",
  "sha256": "d75b71675f751289bcfc0b261c23397969b633e80689bb7f8fc0222c796c5fc1"
}
```

- **Medium — Qualification semantic controls miss coherent provenance mutation of L2 report path.**  
  - **Where:** `src/catalogue_qualifications.py:31-39`, `tests/test_common_catalogue.py:188-201`, `out/common_catalogue/verification_20261018_post_review/controls/controls.json:50-66`  
  - **What:** L2 validation enforces `report.sha256 == retained_payload`, but not canonical `report.path`. A coherent mutation that changes only `report.path` (same hash/content) still satisfies semantic equality.  
  - **Reproduction (read-only in-memory check):** I ran a Python probe over the frozen `execution_20261018_e` selection and got `L2_path_mutation_would_pass_semantic_equality=True`.  
  - **Impact:** “Exact original source bindings” can be presentation-degraded without rejection; current 12 subcases + 3 frozen semantic controls do not exercise this coherent provenance mutation.

- **Medium — Top-warning locator can be coherently rebound to another identical trigger occurrence and still pass.**  
  - **Where:** `src/catalogue_qualifications.py:46-50`, `tests/test_common_catalogue.py:188-201`  
  - **What:** Validation checks span bounds, exact trigger text, and message contains `artifact:<sha>:` + `zero-size aperture`, but does not enforce first-occurrence identity.  
  - **Reproduction (read-only):**  
    - `rg` count on `dataset/vme-wren_20261016_v1/raw/gerber/vme-wren-Top Layer.gbr` for `X143260289Y-159004960D01*` returns `13` occurrences.  
    - In-memory coherent mutation (update `execution.source_span`, `execution.trigger`, `source_location`, and retained payload hash) produced `equal True` against `top_qualification(...)`.  
  - **Impact:** Locator provenance can be shifted to a different identical command occurrence without rejection; existing locator control catches non-coherent edits, not coherent retained-payload rebinding.

```29:50:src/catalogue_qualifications.py
require(report_binding.get('sha256')==report_hash,'L2_REPORT_BINDING_MISMATCH')
...
'severity':'warning','geometry':'NOT_MATERIALIZED_IN_THIS_SLICE','report':report_binding,
...
span=execution.get('source_span');require(isinstance(span,list) and len(span)==2,'TOP_WARNING_LOCATOR_MISSING')
a,b=span;require(isinstance(a,int) and isinstance(b,int) and 0<=a<b<=len(source),'TOP_WARNING_LOCATOR_INVALID')
require(execution.get('trigger')==source[a:b].decode('ascii'),'TOP_WARNING_TRIGGER_MISMATCH')
require(execution.get('message') and 'zero-size aperture' in execution['message'] and ('artifact:'+digest(source)+':') in execution['message'],'TOP_WARNING_MESSAGE_MISSING')
```

## Commands Actually Run (read-only)

- Snapshot integrity (before): `source_snapshot.json` check -> `FILES=43 MISSING=0 MISMATCH=0`.
- Required retrieve:  
  `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/common_catalogue.py retrieve --bundle out/common_catalogue/execution_20261018_e/selection --revision b39d33db4a2c233ab18e2e1a14aac4874b923b06f42d5240bb1f3fcb0f1b205b` -> `PASS`, result digest `5a899e4f...`.
- Required verify (new CLI full retrieval/qualification/match):  
  `... tools/common_catalogue.py verify --bundle ...execution_20261018_e/selection --revision b39d33...` -> `PASS`.
- Required frozen controls:  
  `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python out/common_catalogue/verification_20261018_post_review/audit_controls.py` -> `PASS` (positive + reject controls as listed).
- UI runtime verify from stable publication entry (`run-86e1...`):  
  `... tools/ingestion.py --verify out/ingestion/directory_intake/workbench/run-86e1ffc195954d1c8ef871e86e7afc19` -> `FAIL / NATIVE_QUALIFICATION_SEMANTICS_MISMATCH`.
- Additional diagnostic read-only probes: stale D verify, semantic-coherent mutation checks, trigger-occurrence count.
- Snapshot integrity (after): `FILES=43 MISSING=0 MISMATCH=0`.

## Scope Status

- **Source snapshot status:** clean before and after review.
- **Reviewed final dataset revision target:** `b39d33db4a2c233ab18e2e1a14aac4874b923b06f42d5240bb1f3fcb0f1b205b`.
- **Publication runtime verification availability:** available (run discovered from stable entry), but verification **failed** as above.
- **Important limits retained:** no claim of whole-board electrical/manufacturing acceptance; bounded R140 scope only.

## Verdict

**UNQUALIFIED**.
