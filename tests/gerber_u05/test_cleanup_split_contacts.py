import pytest
from shapely.geometry import Polygon,MultiPolygon,box
from src.gerber_u05.source_edge_cleanup import check_split_source_contacts


def test_detached_numerical_face_is_rejected_without_changing_operands():
    tiny=Polygon([(39.478239284275716,-15.199835617979481),
        (39.47790210412638,-15.200420121999223),
        (39.47790210412637,-15.20042012199923)])
    before=box(39.477,-15.201,39.479,-15.199)
    after=MultiPolygon([box(39.477,-15.201,39.4775,-15.199),tiny])
    assert tiny.area>0 and tiny.area<1e-17 and after.is_valid
    working={'s':before};updates={'s':after}
    with pytest.raises(ValueError,match='TRIM_WOULD_DETACH_LOCAL_COPPER'):
        check_split_source_contacts(working,updates,['s'])
    assert working['s']is before and updates['s']is after


def test_material_split_also_remains_rejected():
    with pytest.raises(ValueError,match='TRIM_WOULD_DETACH_LOCAL_COPPER'):
        check_split_source_contacts({'s':box(0,0,4,1)},
            {'s':MultiPolygon([box(0,0,1,1),box(3,0,4,1)])},['s'])


def test_overlapping_source_can_keep_both_pieces_connected():
    working={'s':box(0,0,4,1),'bridge':box(.5,.25,3.5,.75)}
    updates={'s':MultiPolygon([box(0,0,1,1),box(3,0,4,1)])}
    proof=check_split_source_contacts(working,updates,['s','bridge'])
    assert proof['before_components']==proof['after_components']==1
    assert proof['board_unions']==proof['clearance_searches']==0


def test_unchanged_or_removed_whole_contribution_needs_no_split_check():
    working={'s':box(0,0,1,1),'island':box(3,0,4,1)}
    assert check_split_source_contacts(working,{'s':working['s']},list(working))is None
    assert check_split_source_contacts(working,{'s':Polygon()},list(working))is None
