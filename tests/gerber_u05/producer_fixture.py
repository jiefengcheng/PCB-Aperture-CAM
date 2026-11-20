"""Read canonical historical producers from Git for exact compatibility tests."""
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
WIDTH_REVISION = '404a31d456d9dde86f9160f1bb03e8169c7fe438'
T01_REVISION = '703f66ffd144d6fa52e2b83ee726090456832200'


def historical_source(relative, revision=WIDTH_REVISION):
    """Current code can evolve without changing the fixture's exact digest."""
    if not (ROOT / '.git').exists():
        pytest.skip('exact historical producer fixture requires checkout Git objects')
    result = subprocess.run(
        ['git', 'show', f'{revision}:{relative}'], cwd=ROOT,
        capture_output=True, check=False,
    )
    if result.returncode:
        pytest.fail(f'Missing pinned historical producer {revision}:{relative}')
    return result.stdout
