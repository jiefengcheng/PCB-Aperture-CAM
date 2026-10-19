## Findings

- **High — Qualification semantics can be downgraded without rejection (false-pass risk)**
  - **File:** `src/common_catalogue.py` **Lines:** 144-147  
  - **Issue:** retrieval verifies only the *set of qualification codes* and that each `artifact_roles` entry exists, but does not validate per-code semantic fields (`status`, `severity`, `geometry`, expected report/measurement structure).
  - **Why this matters:** a coherent-but-wrong qualification payload (same 3 codes, altered meaning) can still pass `retrieve()` + `validate_positive()`, weakening the “qualification preservation” guarantee.
  - **Reproduction (read-only reasoning):**
    1. Start from a valid bundle.
    2. Replace qualification content so `code` values remain unchanged, but mutate semantics (for example, flip `L2GND_ROI_MISMATCH` away from mismatch semantics or strip its meaningful measurement fields).
    3. Rebind envelope to that payload and reseal revision.
    4. Retrieval path still passes current checks because only code presence + artifact role membership are enforced.
  - **Control gap evidence:** frozen controls/tests cover missing qualification object, but not semantic mutation of preserved qualifications.

```140:150:src/common_catalogue.py
        links=json.loads(catalog.read_payload(envelope['links']));quals=json.loads(catalog.read_payload(envelope['qualifications']))
        require(set(links)==set(roles),'MISSING_CORRESPONDENCE')
        require({q['code'] for q in quals}=={'BOUNDED_NATIVE_PROFILE','L2GND_ROI_MISMATCH','TOP_PARSE_UNSUPPORTED'},'MISSING_QUALIFICATION')
        for q in quals:
            for key in q.get('retained_payloads',[]):catalog.read_payload(key)
            require(all(a in artifacts for a in q['artifact_roles']),'QUALIFICATION_ARTIFACT_MISMATCH')
        result=[]
```

```147:155:tests/test_common_catalogue.py
        for mutation,reason in [
            (lambda e:e['roles'].pop('connected_trace'),'OMITTED'),
            (lambda e:e['artifacts']['native'].update(source_sha256='0'*64),'MIXED_ARTIFACT'),
            (lambda e:e.pop('qualifications'),'MISSING_QUALIFICATIONS'),
            (lambda e:e['roles']['R140.1'].update(plotted=e['roles']['R140.2']['plotted']),'CORRESPONDENCE_ENDPOINT'),
        ]:
```

## Commands Run (Read-Only) and Results

- `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python` hash-check script on `out/common_catalogue/review_packet_20261018/source_snapshot.json` (before review)  
  - Result: `SNAPSHOT_FILES=42`, `MISSING=0`, `MISMATCH=0`
- `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/common_catalogue.py retrieve --bundle out/common_catalogue/execution_20261018_d/selection --revision ad413456a164715527a3b089950d145ce3032dc8cdffaf38908ffad7e923b131`  
  - Result: PASS JSON returned, `status=COMPLETE_IN_DECLARED_SCOPE`, `result_sha256=a2143f...`, 4 roles, expected NOT_ESTABLISHED engineering boundary retained
- `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python out/common_catalogue/verification_20261018/audit_controls.py`  
  - Result: `{"status":"PASS",...}` with positive pass and declared reject controls observed
- `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/ingestion.py --help`  
  - Result: verified `--verify` interface
- `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/ingestion.py --verify out/ingestion/directory_intake/workbench/run-86e1ffc195954d1c8ef871e86e7afc19`  
  - Result: PASS (`schema=pcb-ingestion-publication-v2`, `outputs_verified=378`, `datasets_verified=5`, `comparisons_verified=3`)
- `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python` summary scripts against `out/common_catalogue/execution_20261018_d/reopened.json`  
  - Result: confirmed named-net retention, null numeric net codes, contact/proximity separation, mask polarity `Negative`, copper polarity `Positive`
- `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python` hash-check script on snapshot (after review)  
  - Result: `SNAPSHOT_FILES=42`, `MISSING=0`, `MISMATCH=0`

## Snapshot / Dataset / UI Runtime Status

- Source snapshot integrity: **clean before and after review**.
- Reviewed dataset revision: `ad413456a164715527a3b089950d145ce3032dc8cdffaf38908ffad7e923b131`.
- Workbench publication runtime verification availability: **available** and independently verified on run `run-86e1ffc195954d1c8ef871e86e7afc19`.
- `common_context` binding present in published registry and hash-bound.

## Important Remaining Limits (as evidenced)

- No independent net-intent or manufacturing acceptance claim.
- Scope remains bounded to selected R140 slice and retained qualifications.
- Browser is replay/published artifact inspection, not live SQL/query execution.

## Verdict

**UNQUALIFIED** (blocking high-severity false-pass risk remains in qualification-semantic enforcement).
