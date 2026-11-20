from dataclasses import replace
import pytest
from shapely.geometry import box
from src.stage_abi.loaded_geometry import GeometryMemo
from src.junction_spindle_blend import check_spindle


def test_ordered_exact_scalars_keep_current_gap_checks_and_corruption_controls():
    memo=GeometryMemo('scope',limit=8192,entries=8)
    left,right=box(0,0,1,1),box(2,0,3,1)
    assert memo.exact_distance(left,right)==left.distance(right)==1.
    assert memo.exact_distance(left,right)==1. and memo.stats['distance_measurement_hits']==1
    memo.exact_distance(right,left)
    assert memo.stats['distance_measurement_builds']==2
    key=next(iter(memo.values));memo.values[key]=replace(memo.values[key],value=.1)
    with pytest.raises(ValueError,match='DISTANCE_CORRUPTED'):memo.exact_distance(left,right)


def test_witnesses_match_and_current_clearance_threshold_is_never_cached():
    owner=box(-1,0,0,1);addition=box(0,.2,.2,.8);candidate=owner.union(addition)
    window=box(-2,-2,3,3);foreign=[('other',box(.3,0,.4,1))]
    memo=GeometryMemo('scope',limit=1024**2);memo.exact_distance_reuse=True
    for gap in (.04,.15):
        assert check_spindle(owner,candidate,addition,window,foreign,gap=gap,geometry=memo)==check_spindle(owner,candidate,addition,window,foreign,gap=gap)
    assert memo.stats['distance_measurement_hits']==1
