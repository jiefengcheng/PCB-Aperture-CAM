import itertools
import math
import pytest
from src.gerber_u05.group_allocation import maximum_faces, consecutive_widths, units, mm
from src.gerber_u05.coupled_growth import proportional_fill


def test_total_growth_reclaims_capacity_that_fair_filling_leaves_unused():
    fair, _ = proportional_fill({'al': 1., 'ar': 1., 'bl': 1.},
                               {'al': 1., 'ar': 1., 'bl': 1.},
                               [('al', 'ar', 1.), ('ar', 'bl', 1.)])
    q = maximum_faces(['a', 'b'], {'a': 1., 'b': 1.}, [1.],
                      face_caps={'a': {'left': 1., 'right': 1.},
                                 'b': {'left': 1., 'right': 0.}})
    assert sum(fair.values()) == 1.5
    assert q['total_width_growth_mm'] == 2.
    assert q['face_growth_mm'] == {'a': {'left': 1., 'right': 0.},
                                   'b': {'left': 1., 'right': 0.}}
    assert q['minimum_cut_units'] == q['total_width_growth_units']


def test_exhaustive_small_lane_problems_match_mathematical_maximum():
    # Exhaust all integral face choices, independently of the flow algorithm.
    for caps in itertools.product(range(3), repeat=3):
        for gaps in itertools.product(range(3), repeat=2):
            face = {'a': {'left': 0., 'right': mm(caps[0])},
                    'b': {'left': mm(caps[1]), 'right': mm(caps[1])},
                    'c': {'left': mm(caps[2]), 'right': 0.}}
            q = maximum_faces(list('abc'), dict(zip('abc', map(mm, caps))),
                              list(map(mm, gaps)), face_caps=face)
            best = max((a+bl+br+c for a, bl, br, c in itertools.product(range(3), repeat=4)
                        if a <= caps[0] and bl+br <= caps[1] and c <= caps[2]
                        and a+bl <= gaps[0] and br+c <= gaps[1]), default=0)
            assert q['total_width_growth_units'] == best
            assert q['minimum_cut_units'] == best


def test_budget_rounding_is_downwards_and_zero_caps_keep_fixed_neighbours():
    q = maximum_faces(['fixed', 'moving'], {'fixed': 0., 'moving': .03}, [.0040000009])
    assert q['face_growth_mm']['fixed'] == {'left': 0., 'right': 0.}
    assert q['face_growth_units']['moving']['left'] <= 4_000_000
    assert q['total_width_growth_mm'] == .03
    assert units(.0040000009) == 4_000_000


def test_local_25_percent_allows_50_percent_change_along_route():
    values = {'corridor': .1, 'joint': .125, 'outer': .15}
    assert consecutive_widths(values, [('corridor', 'joint'), ('joint', 'outer')]) == values
    assert consecutive_widths({'a': .1, 'b': .15}, [('a', 'b')]) == {'a': .1, 'b': .125}


def test_local_limits_propagate_only_through_actual_connections():
    assert consecutive_widths({'a': .1, 'b': .15, 'c': .15, 'other': .2},
                             [('b', 'c'), ('a', 'b')]) == {'a': .1, 'b': .125, 'c': .15, 'other': .2}


@pytest.mark.parametrize('bad', [-1., math.inf, math.nan, True, '1'])
def test_invalid_budgets_are_not_silently_accepted(bad):
    with pytest.raises(ValueError, match='NONNEGATIVE_GROUP_BUDGET'):
        maximum_faces(['a', 'b'], {'a': bad, 'b': .01}, [.01])


def test_missing_or_duplicate_relations_fail_explicitly():
    with pytest.raises(ValueError, match='DISTINCT_PARALLEL'):
        maximum_faces(['a', 'a'], {'a': .01}, [.01])
    with pytest.raises(ValueError, match='COMPLETE_ADJACENT'):
        maximum_faces(['a', 'b'], {'a': .01, 'b': .01}, [])
    with pytest.raises(ValueError, match='COMPLETE_TWO_FACE'):
        maximum_faces(['a', 'b'], {'a': .01, 'b': .01}, [.01], face_caps={})
    with pytest.raises(ValueError, match='ACTUAL_ROUTE_ADJACENCY'):
        consecutive_widths({'a': .1}, [('a', 'missing')])


def test_signed_faces_keep_width_and_match_independent_exhaustive_optimum():
    for cap_a, cap_b, gap in itertools.product(range(3), range(3), range(-2, 3)):
        possibilities = [(al+ar+bl+br) for al, ar, bl, br in
                         itertools.product(range(-1, cap_a+2), range(-1, cap_a+2),
                                           range(-1, cap_b+2), range(-1, cap_b+2))
                         if 0 <= al+ar <= cap_a and 0 <= bl+br <= cap_b and ar+bl <= gap]
        q = maximum_faces(['a', 'b'], {'a': mm(cap_a), 'b': mm(cap_b)}, [mm(gap)],
                          recessions={'a': mm(1), 'b': mm(1)})
        assert q['total_width_growth_units'] == max(possibilities)
        assert q['minimum_cut_units'] == q['total_width_growth_units']
        # Independently check the certificate's bounded-flow conservation.
        balance = {}
        for e in q['network_edges']:
            assert e['lower'] <= e['flow'] <= e['upper']
            balance[e['a']] = balance.get(e['a'], 0)-e['flow']
            balance[e['b']] = balance.get(e['b'], 0)+e['flow']
        assert all(v == 0 for n, v in balance.items() if n not in (0, 1))
        assert balance[1] == q['total_width_growth_units']+q['shifted_objective_constant_units']
