import pytest
from shapely.geometry import box
from src.gerber_u05.keep_retraction import retract


def test_keep_retracts_only_optional_growth_and_preserves_every_other_operand():
    before={'s':box(0,0,1,1).wkb,'fixed':box(3,0,4,1).wkb}
    current=dict(before,s=box(-.1,-.1,1.1,1.1).wkb)
    after,records=retract(current,before,{'s':'Original source fill boundary'})
    assert after==before and current['s']!=after['s']
    assert records[0]['added_copper'] is False
    assert records[0]['kept_predecessor_bytes_identical']


def test_missing_source_or_predecessor_outside_current_cannot_be_retracted():
    before={'s':box(0,0,1,1).wkb}
    with pytest.raises(ValueError,match='KNOWN_KEPT'):
        retract(before,before,{'unknown':'keep'})
    with pytest.raises(ValueError,match='CANNOT_ADD_OR_REMOVE'):
        retract({'s':box(0,0,.9,1).wkb},before,{'s':'keep'})
