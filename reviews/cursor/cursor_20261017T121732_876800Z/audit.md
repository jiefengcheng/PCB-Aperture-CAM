## Independent Audit Outcome

- **Scoped verdict:** `QUALIFIED_IN_DECLARED_SCOPE`
- **Bug findings (priority/file/line/reproduction):** **No actionable regressions found** in the declared maintenance scope (source split/decomposition, generation review metadata semantics, immutability destination guard, implementation hash recheck, redirect cleanup behavior).
- **Historical acceptance remains frozen**; this audit does not replace earlier review records.

## Findings

- **P0/P1/P2/P3:** none observed in this read-only audit.
- **Compatibility behavior validated:** new publication uses structured generation review metadata, while legacy frozen string metadata remains accepted for older publications without inheriting prior review into new builds.

```36:53:src/ingestion_contracts.py
def generation_review():
    """A build cannot inherit a review of a different source/run snapshot."""
    return {
        'status': 'NOT_RUN',
        'reason': 'NO_REVIEW_ATTACHED_TO_THIS_PUBLICATION',
        'scope': 'AT_GENERATION',
    }


def verify_generation_review(receipt, ingestion):
    review = receipt.get('cursor_review')
    if isinstance(review, dict):
        require(review == generation_review(), 'Invalid generation-time review status')
        require(ingestion.get('cursor_review') == review, 'Scene/receipt review status mismatch')
    else:
        require(review == 'NOT_RUN: CHANNEL_UNAVAILABLE', 'Missing/invalid legacy generation review')
        require('cursor_review' not in ingestion, 'Structured scene review requires a structured receipt review')
```

```40:47:src/ingestion_registry.py
def _publication_directory(root, destination):
    destination = Path(destination).resolve()
    if not destination.is_relative_to(root / 'out'):
        raise ValueError('Publication must stay under checkout/out')
    immutable_markers = {'receipt.json', 'build_receipt.json', 'scene.json', 'registry.json'}
    if any((destination / name).exists() for name in immutable_markers):
        raise ValueError('Publication destination is an immutable bundle; choose an entry directory')
    return destination
```

```170:178:src/ingestion_registry.py
    stage.mkdir()
    try:
        scene = _copy_replay(root, config, stage)
        render_inputs = _add_ingestion(root, config, scene)
        _copy_evidence(root, scene, stage)
        _write_workbench(stage, scene, config, sources)
        verify(root, bindings)
        verify(root, [{'path': p, 'sha256': h} for p, h in implementation.items()])
```

## Exact Independent Commands + Results

Executed in checkout root with read-only intent and `PYTHONDONTWRITEBYTECODE=1`:

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY' ...recompute packet file hashes from packet.json... PY`
  - **Exit:** `0`
  - **Result:** `19/19` packet hashes matched; no missing files; status `PASS`.

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/ingestion.py --verify /Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/ingestion/workbench/run-397f4c7683d24d44ae43537e5ad8dd28`
  - **Exit:** `0`
  - **Result:** `PASS`, schema `pcb-ingestion-publication-v2`, outputs `351`, datasets `5`, comparisons `3`.

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/ingestion.py --verify /Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/ingestion/workbench/run-05888c57424f4db48bd9821fc8324b36`
  - **Exit:** `0`
  - **Result:** `PASS`, schema `pcb-ingestion-publication-v2`, outputs `351`, datasets `5`, comparisons `3`.

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/ingestion.py --verify /Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/review/ingestion_assessment_20261016T184844_296975Z/empty_failed`
  - **Exit:** `1` (expected)
  - **Result:** `FAIL` with `Unsupported/missing publication schema; legacy v1 is unqualified`.

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/ingestion.py --verify /Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/review/ingestion_assessment_20261016T184844_296975Z/empty_unknown`
  - **Exit:** `1` (expected)
  - **Result:** same expected failure as above.

Additional independent read-only comparisons:

- New vs prior `scene.json`: `cases`, `geometry`, `pipeline` are identical.
- Ingestion projections unchanged when ignoring generation-review metadata envelope.
- New run scene/receipt generation review objects match exactly.
- `source_snapshot` copies match packet-listed source files (`18/18` matched).
- New receipt implementation hashes overlap and match packet source hashes (`16/16`).

## Author Evidence Reviewed (Not Independently Re-executed)

- `out/ingestion/maintenance/tests.log`: 25 Python tests `OK`.
- `out/ingestion/maintenance/js_checks.json`: 3 JS checks `PASS`.
- `out/ingestion/maintenance/preservation.json`: retained cases/geometry/pipeline/qualification `IDENTICAL`.
- `out/ingestion/maintenance/intake.json`: dataset verification `PASS`.
- `out/ingestion/maintenance/immutable_destination_control.json`: immutable output rejection `PASS`.

## Unrun Limits in This Read-Only Session

- No test reruns (`pytest`/Node test execution) because tests/publisher controls create temp files.
- No publish/control execution that stages/writes bundles.
- No browser/UI interactive verification beyond static code and retained artifacts.


