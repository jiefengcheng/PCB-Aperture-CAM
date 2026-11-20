"""Bounded sampling and adversarial controls for T05 geometry shortcuts."""
import copy
import hashlib
import json

import pytest
from shapely import set_precision
from shapely.geometry import box

from src.junction_spindle_blend import check_spindle
from src.stage_abi.loaded_geometry import GeometryMemo
from tools.select_retained_t05_sample import select
from tools.compare_retained_t05_local import compare, canonical


class CountingMemo(GeometryMemo):
    def __init__(self):
        super().__init__('local-control')
        self.differences = []
        self.symmetric = 0

    def difference(self, left, right):
        self.differences.append((left, right))
        return super().difference(left, right)

    def symmetric_difference(self, left, right):
        self.symmetric += 1
        return super().symmetric_difference(left, right)


def test_exact_additive_composition_avoids_only_proved_empty_cuts():
    owner, addition, window = box(0, 0, 1, 1), box(.9, .2, 1.2, .8), box(-1, -1, 2, 2)
    candidate = owner.union(addition)
    memo = CountingMemo()
    assert check_spindle(owner, candidate, addition, window, [], geometry=memo)['passed']
    assert memo.symmetric == 0
    # Owner preservation and addition/window scope checks still execute.
    assert len(memo.differences) == 2


@pytest.mark.parametrize('mutation,failure', [
    ('extra', 'DELTA_MISMATCH'), ('remove', 'OWNER_REMOVED'),
    ('window', 'OUTSIDE_WINDOW'), ('foreign', 'FOREIGN_CLEARANCE:other'),
])
def test_shortcut_keeps_extra_copper_and_clearance_controls(mutation, failure):
    owner, addition, window = box(0, 0, 1, 1), box(.9, .2, 1.2, .8), box(-1, -1, 2, 2)
    candidate, foreign = owner.union(addition), []
    if mutation == 'extra':
        candidate = candidate.union(box(.9, .5, 1.4, .7))
    elif mutation == 'remove':
        candidate = candidate.difference(box(0, 0, .1, 1))
    elif mutation == 'window':
        window = box(0, 0, 1, 1)
    else:
        foreign = [('other', box(1.21, .3, 1.4, .7))]
    result = check_spindle(owner, candidate, addition, window, foreign,
                           geometry=CountingMemo())
    assert not result['passed'] and failure in result['failures']


def test_fixed_precision_owner_subtraction_keeps_original_overlay():
    owner = set_precision(box(0, 0, 1, 1), .001)
    addition = set_precision(box(.9, .2, 1.2, .8), .001)
    memo = CountingMemo()
    assert check_spindle(owner, owner.union(addition), addition, box(-1, -1, 2, 2),
                         [], geometry=memo)['passed']
    assert len(memo.differences) == 2


def population():
    rows = [dict(source_id=str(i), status='GROWN', scale=.75 if i % 3 == 0 else 1.,
                 land_ids=['a', 'b'] if i % 2 else ['a']) for i in range(16)]
    for i, reason in enumerate(('BLOCKED_REQUIRED_TREATMENT',
                               'PREDECESSOR_ALREADY_SATISFIES',
                               'NO_DECLARED_SOURCE_CONTACT'), start=16):
        rows.append(dict(source_id=str(i), status='KEEP', reason=reason,
                         land_ids=[] if i == 18 else ['a']))
    return dict(candidate=dict(decisions=rows)), {str(i): 100 + i for i in range(16)}


def test_varied_selection_has_reproducible_seed_and_preserves_source_order():
    stage, sizes = population()
    first = select(stage, sizes, count=6, seed=17)
    assert first == select(stage, sizes, count=6, seed=17)
    assert [r['category'] for r in first['routes']].count('blocked') == 1
    assert {r['category'] for r in first['routes']} == {
        'large_addition', 'small_addition', 'reduced_radius',
        'multiple_attachments', 'blocked', 'already_satisfied'}
    assert [int(r['source_id']) for r in first['routes']] == sorted(
        int(r['source_id']) for r in first['routes'])
    assert first['routes'] != select(stage, sizes, count=6, seed=43)['routes']


@pytest.mark.parametrize('count', [0, 13, 1000])
def test_sample_size_cannot_enable_whole_board(count):
    stage, sizes = population()
    with pytest.raises(ValueError, match='COUNT'):
        select(stage, sizes, count=count)


def test_tiny_population_cannot_accidentally_select_whole_board():
    stage, sizes = population()
    small = copy.deepcopy(stage)
    small['candidate']['decisions'] = small['candidate']['decisions'][:2]
    with pytest.raises(ValueError, match='WHOLE_BOARD'):
        select(small, sizes, count=2)


def test_explicit_route_selection_is_bounded_and_rejects_missing_ids():
    stage, sizes = population()
    assert [r['source_id'] for r in select(stage, sizes, route_ids=['17', '1'])['routes']] == ['1', '17']
    with pytest.raises(ValueError, match='UNKNOWN'):
        select(stage, sizes, route_ids=['missing'])


def comparison_cases(tmp_path):
    cases = [tmp_path / 'baseline', tmp_path / 'candidate']
    script = b'# identical bounded profiler\n'
    witness = [dict(route='local-route', replay_passed=True,
                    patch_sha256='a' * 64, check=dict(passed=True, failures=[]))]
    seal = dict(original='/retained', scope='local only', checkpoint_sha256='b' * 64,
                raw_checkpoint_sha256='c' * 64, entry_files={'input': 'd' * 64})
    profile = dict(status='PASS', full_board_t05_evaluations=0, search_calls=0,
                   selected=['local-route'], witnesses=witness,
                   witness_sha256=hashlib.sha256(canonical(witness)).hexdigest(),
                   profiler_sha256=hashlib.sha256(script).hexdigest(),
                   local_seconds=1., python='test', shapely='test', geos='test',
                   **{k: seal[k] for k in ('scope', 'checkpoint_sha256', 'raw_checkpoint_sha256')})
    for case in cases:
        case.mkdir()
        (case / 'profile_local.py').write_bytes(script)
        (case / 'SEAL.json').write_text(json.dumps(seal))
        (case / 'PROFILE.json').write_text(json.dumps(profile))
    return cases


def test_comparison_accepts_identical_local_witnesses_only(tmp_path):
    cases = comparison_cases(tmp_path)
    result = compare(*cases)
    assert result['status'] == 'PASS' and result['full_board_speedup'] == 'NOT_MEASURED'


@pytest.mark.parametrize('mutation', ['witness', 'selection', 'scope', 'full_board', 'script'])
def test_comparison_rejects_changed_evidence(tmp_path, mutation):
    cases = comparison_cases(tmp_path)
    case = cases[1]
    profile = json.loads((case / 'PROFILE.json').read_bytes())
    if mutation == 'witness':
        profile['witnesses'][0]['patch_sha256'] = 'e' * 64
    elif mutation == 'selection':
        profile['selected'] = ['another-route']
    elif mutation == 'scope':
        profile['scope'] = 'whole board'
    elif mutation == 'full_board':
        profile['full_board_t05_evaluations'] = 1
    else:
        (case / 'profile_local.py').write_bytes(b'changed')
    (case / 'PROFILE.json').write_text(json.dumps(profile))
    with pytest.raises(ValueError):
        compare(*cases)
