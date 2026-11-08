import hashlib
import json
import pytest
from src.gerber_u05 import hole_policy_prefix as transition


def test_exact_policy_delta_only_before_fresh_t04():
    name = 'src/t04_topology.py'
    before, after = transition.PAIRS[name]
    assert transition.allowed_delta(name, before, after, ('t01', 't03'))
    assert not transition.allowed_delta(name, before, after, ('t01', 't03', 't04', 't02'))
    assert not transition.allowed_delta(name, before, '0' * 64, ('t01', 't03'))
    assert not transition.allowed_delta('src/component_clearance.py', before, after, ('t01', 't03'))


def snapshot(run, changed=False):
    settings = json.loads((transition.ROOT / 'contracts/component_remedy/settings.json').read_text())
    settings['source_voids'] = 'PRESERVE_INHERITED_SOURCE_VOIDS'
    if changed:
        settings['maximum_shortage_fraction'] = .21
    raw = json.dumps(settings)
    value = dict(settings=settings, registry_json=raw,
                 registry_sha256=hashlib.sha256(raw.encode()).hexdigest(), other='unchanged')
    (run / 'REMEDY_POLICY_SNAPSHOT.json').write_text(json.dumps(value))
    return value


def test_transition_changes_only_hole_label_and_keeps_numerical_settings(tmp_path):
    old = snapshot(tmp_path)
    proof = transition.transition_remedy_snapshot(tmp_path)
    new = json.loads((tmp_path / 'REMEDY_POLICY_SNAPSHOT.json').read_text())
    assert proof['fresh_from'] == 't04' and new['other'] == old['other']
    assert new['settings']['maximum_shortage_fraction'] == .2
    assert new['settings']['source_voids'] == 'FOLLOW_CAPTURED_HOLE_ACCEPTANCE_POLICY'
    assert json.loads((tmp_path / 'prefix_evidence/PRETRANSITION_REMEDY_POLICY_SNAPSHOT.json').read_text()) == old


def test_transition_rejects_nonhole_policy_change(tmp_path):
    snapshot(tmp_path, changed=True)
    with pytest.raises(ValueError, match='NONHOLE_SETTINGS'):
        transition.transition_remedy_snapshot(tmp_path)
