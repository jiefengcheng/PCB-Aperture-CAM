from pathlib import Path
import pytest
from src.gerber_u05 import pipeline as p, profile_job as job, profile_intake as intake


def fixture_job(tmp_path, monkeypatch, algorithm='checked-profile'):
    inputs = dict(source_sha256='a'*64, t03_sha256='b'*64,
                  scene_ref=dict(sha256='c'*64), policy_sha256={})
    monkeypatch.setattr(intake, 'source_inventory', lambda: {})
    monkeypatch.setattr(intake, 'read', lambda *a: (None, {}, {'lineage': []}, None, inputs))
    monkeypatch.setattr(intake, 'prepare', lambda *a: None)
    monkeypatch.setattr(job.hole_acceptance, 'bind', lambda *a: None)
    root = tmp_path/'job'
    result = job.prepare(tmp_path/'source', root, algorithm=algorithm)
    assert result['status'] == 'PREPARED_NOT_EXECUTED'
    return root


def test_preparation_cannot_execute_native_growth(tmp_path, monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError('native construction called during preparation')
    monkeypatch.setattr(p, 'initialize_t04', forbidden)
    root = fixture_job(tmp_path, monkeypatch)
    assert not (root/'runtime').exists() and not (root/'RUNNING.json').exists()


def test_full_board_requires_qualification_before_any_attempt(tmp_path, monkeypatch):
    root = fixture_job(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='FULL_BOARD_QUALIFICATION_REQUIRED'):
        job.execute(root, whole_board=True)
    assert not (root/'RUNNING.json').exists()
    with pytest.raises(ValueError, match='EXPLICIT_BOUND_OR_WHOLE_BOARD_REQUIRED'):
        job.execute(root)


def test_failed_native_attempt_is_retained_and_cannot_be_resumed(tmp_path, monkeypatch):
    root = fixture_job(tmp_path, monkeypatch)
    routes = tmp_path/'routes.json';routes.write_text('{"routes":["r"]}')
    def reject(*a, **kw):
        raise ValueError('deliberate native initialization failure')
    monkeypatch.setattr(p, 'initialize_t04', reject)
    with pytest.raises(ValueError, match='deliberate native'):
        job.execute(root, routes)
    failure = (root/'FAILED.json').read_bytes()
    assert p.load(root/'FAILED.json')['status'] == 'FAIL'
    with pytest.raises(ValueError, match='ALREADY_ATTEMPTED_NO_RESUME'):
        job.execute(root, routes)
    assert (root/'FAILED.json').read_bytes() == failure


def test_group_increment_cannot_switch_algorithm_or_expand_to_full_board(tmp_path, monkeypatch):
    root = fixture_job(tmp_path, monkeypatch, algorithm='parallel-groups')
    routes = tmp_path/'routes.json';routes.write_text('{"routes":["r"]}')
    with pytest.raises(ValueError, match='PREPARED_ALGORITHM_CHANGED'):
        job.execute(root, routes)
    with pytest.raises(ValueError, match='GROUP_INCREMENT_BOUNDED_ONLY'):
        job.execute(root, whole_board=True, group_construction=True)
    assert not (root/'RUNNING.json').exists()


def test_group_stage_dispatch_does_not_run_old_two_phase_growth(monkeypatch):
    from src.gerber_u05 import profile_stage, group_stage
    def forbidden(*args, **kwargs):
        raise AssertionError('legacy profile construction called')
    monkeypatch.setattr(p, 'run_t04', forbidden)
    monkeypatch.setattr(group_stage, 'run', lambda *a, **kw: {'status': 'DIRECT_GROUP_INCREMENT'})
    assert profile_stage.run(None, {}, route_ids=['r'], rule={'group_construction': True}) == {'status': 'DIRECT_GROUP_INCREMENT'}
    with pytest.raises(ValueError, match='REFERENCE_INPUT_FORBIDDEN'):
        profile_stage.run(None, {}, route_ids=['r'], rule={'group_construction': True, 'baseline_seed': 'saved'})
