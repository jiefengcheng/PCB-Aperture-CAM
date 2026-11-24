import shutil

import pytest

from tools.check_large_copper_baseline import BASELINE, check


def test_versioned_source_matches_recorded_intake():
    result = check(parse=True)
    assert result['status'] == 'PASS_SOURCE_INTAKE_ONLY'
    assert result['source_occurrences'] == 17849
    assert result['trimming'] == result['geometry_parity'] == result['native_display'] == 'NOT_RUN'


def test_changed_input_is_rejected_before_parsing(tmp_path):
    shutil.copytree(BASELINE, tmp_path / 'baseline')
    source = tmp_path / 'baseline/source.gbr'
    source.write_bytes(source.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='BASELINE_SOURCE_BYTES_CHANGED'):
        check(tmp_path / 'baseline', parse=True)
