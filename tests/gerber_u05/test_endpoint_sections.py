from shapely.geometry import box
from shapely.ops import unary_union
from src.gerber_u05.endpoint_sections import audit


def obligation(lo,hi):
    return dict(route_id='r',source_id='short',endpoint_mm=[0,0],
                section=dict(lower_mm=[0,lo],upper_mm=[0,hi]))


def test_frozen_section_uses_both_emitted_sides_of_a_native_joint():
    short=box(0,-.025,1,.025); joint=box(-.1,-.0375,.1,.0375)
    q=obligation(-.0375,.0375)
    assert not audit({'r':short},[q])['passed']
    result=audit({'r':unary_union([short,joint])},[q,obligation(-.035,.035)])
    assert result['passed'] and result['checked']==2


def test_a_real_missing_section_or_another_routes_copper_cannot_pass():
    result=audit({'r':box(0,-.025,1,.025),'other':box(-.1,-.1,.1,.1)},
                 [obligation(-.0375,.0375)])
    assert not result['passed'] and result['failures'][0]['missing_section_length_mm']>.02


def test_wide_neighbor_alone_cannot_mask_a_rejected_narrow_continuation():
    material=unary_union([box(-1,-.0375,0,.0375),box(0,-.025,1,.025)])
    q=dict(obligation(-.0375,.0375),inward_offset_mm=[.00002,0.])
    assert not audit({'r':material},[q])['passed']


def test_a_transition_proof_does_not_waive_actual_endpoint_section_coverage():
    q=dict(obligation(-.0375,.0375),native_frame_transition_admitted=True)
    assert not audit({'r':box(0,-.025,1,.025)},[q])['passed']


def test_chain_admission_stops_at_the_actual_taper_length():
    from src.gerber_u05.endpoint_sections import transition_sites
    rows={s:dict(metadata=dict(route_points_mm=p)) for s,p in
          [('a',[[0,0],[.02,0]]),('b',[[.02,0],[.12,0]])]}
    patch=dict(route_id='r',endpoint_mm=[0,0],recipe=dict(schema='t04-larger-corner-transition/1',
               joint_receiver_source_ids=['a','b'],length_mm=.05))
    assert transition_sites(rows,[patch])=={('r',(0.,0.)),('r',(.02,0.))}


def test_identical_route_obligations_reuse_one_exact_native_error_buffer():
    q=obligation(-.025,.025)
    result=audit({'r':box(-.1,-.03,1.,.03)},[q,q])
    assert result['passed']and result['checked']==2
    assert result['native_error_buffers_built']==1


def test_buffer_reuse_is_bound_to_the_exact_immutable_route_operand():
    buffers={};body=box(0,-.03,1,.03);q=obligation(-.025,.025)
    assert audit({'r':body},[q],buffers=buffers)['native_error_buffers_built']==1
    assert audit({'r':body},[q],buffers=buffers)['native_error_buffers_built']==0
    changed=box(0,-.02,1,.02)
    result=audit({'r':changed},[q],buffers=buffers)
    assert result['native_error_buffers_built']==1 and not result['passed']
