from shapely.geometry import box
from shapely import union_all
from src.viewer_abi.board_growth import partition


def test_material_partition_accounts_for_overlap_and_removed_copper():
    before = union_all([box(0, 0, 2, 1), box(1, 0, 3, 1)])
    after = union_all([box(0, 0, 1, 1), box(1, 0, 3, 2)])
    parts = dict(partition(before, after))
    assert parts['source'].area == 3
    assert parts['added'].area == 2
    assert parts['removed'].is_empty
    # Reducing one contribution beneath an overlapping source is no material removal.
    after = box(1, 0, 4, 1)
    parts = dict(partition(before, after))
    assert parts['removed'].equals(box(0, 0, 1, 1))
    assert union_all([parts['source'], parts['added']]).equals(after)
    assert union_all([parts['source'], parts['removed']]).equals(before)
    assert parts['added'].intersection(parts['removed']).area == 0
