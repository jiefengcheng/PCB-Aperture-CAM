from shapely.geometry import box
from src.gerber_u05 import marked_shoulders as marked
from tests.gerber_u05.test_shoulder_bridge import straight


def test_only_authenticated_attachment_can_defer_a_marked_shoulder(monkeypatch):
    _,_,before,floor,_=straight()
    case=dict(id='marked',image='test',regions_mm=[[-.03,-.08,.03,.08]],
        target_points_mm=[[0,.065]],target_radius_mm=.03,disposition='REPAIR')
    monkeypatch.setattr(marked,'contract',lambda:(dict(cases=[case],maximum_transition_angle_degrees=10,
        source_sha256='a'*64),'b'*64))
    images={'marked':(before['s'],before['s'],floor['s'])}
    broad=dict(window_wkb_hex=box(-1,-1,1,1).wkb_hex,optional_scope_wkb_hex=box(-1,-1,1,1).wkb_hex,points_mm=[[0,.065]])
    # A T05 search window cannot excuse an interior shoulder.
    result=marked.audit(None,None,None,local_images=images,terminals=[broad])
    assert not result['passed'] and result['cases'][0]['unresolved_interior_corners_mm']
    qualified=dict(broad,attachment_scope_wkb_hex=box(-.03,-.08,.03,.08).wkb_hex,
        attachment_dependencies=[dict(source_id='s',land_id='pad')])
    result=marked.audit(None,None,None,local_images=images,terminals=[qualified])
    assert result['passed'] and result['cases'][0]['deferred_terminal_corners_mm']
    assert result['cases'][0]['disposition']=='INTERIOR_REPAIRED; SOURCE_ATTACHMENTS_PENDING_T05'
    assert result['cases'][0]['remaining_corners_mm']


def test_final_board_outline_does_not_defer_an_interior_corner_in_t05_search_window():
    from src.gerber_u05.boundary_finish import outline_images
    _,_,before,floor,_=straight()
    terminal=dict(window_wkb_hex=box(-2,-2,2,2).wkb_hex,
        optional_scope_wkb_hex=before['s'].difference(floor['s']).wkb_hex,
        attachment_scope_wkb_hex=box(.8,-.2,1.2,.2).wkb_hex)
    result=outline_images(floor['s'],before['s'],10,[terminal],baseline=floor['s'])
    assert not result['passed'] and result['additional_shoulders']>0
    assert result['deferred_terminal_shoulders']==0
