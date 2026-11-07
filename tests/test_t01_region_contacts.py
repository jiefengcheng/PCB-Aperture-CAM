"""Filled-source attachment recognition; foreign copper never gains a port."""
import copy
import pytest
from shapely.geometry import Point,box
from shapely import to_wkb
from src.stage_abi.store import digest
from src.t01_region_contacts import source_marker,original_port,port_buffer_mm
from src.crop_balanced_t01 import WorkingScene,CropSettings,choose_priorities
from src.crop_square_neighbor_experiment import verify_addition
from src.clearance_policy import CONTACT_BUFFER_MM

SOURCE='a'*64

def case(marked=True):
    shapes=[Point(0,0).buffer(.15,quad_segs=128),
            Point(1,0).buffer(.125,quad_segs=128),box(0,-.035,1,.035)]
    ids=[SOURCE+':bytes:'+p for p in ('0:10','11:20','21:30')]
    rows=[dict(id=s,kind='gr_circle'if i<2 else'gr_poly',trace_width_mm=0.,
               geometry_sha256=digest(to_wkb(g)),source_span=[0,0])
          for i,(s,g)in enumerate(zip(ids,shapes))]
    if marked:rows[2]['t01_original_region']=source_marker(SOURCE,ids[2],rows[2]['geometry_sha256'])
    sites=[dict(source_id=ids[i],aliases=[ids[i]],indexes=[i],core=shapes[i],
                center=[i,0],radius=r,physical_contact_group='source-pair')
           for i,r in enumerate((.15,.125))]
    return rows,shapes,sites


def test_original_filled_neck_restores_one_larger_round_priority():
    rows,shapes,sites=case(False)
    assert choose_priorities(sites,WorkingScene(b'',rows,shapes,sites,CropSettings()))[0]=={}
    rows,shapes,sites=case()
    scene=WorkingScene(b'',rows,shapes,sites,CropSettings())
    priorities,exceptions=choose_priorities(sites,scene)
    assert priorities=={'source-pair':sites[0]['source_id']} and not exceptions
    for site in sites:
        port=scene.ports[site['source_id']][rows[2]['id']]
        contact=site['core'].intersection(shapes[2])
        assert port.covers(contact)
        assert port.difference(shapes[2].buffer(port_buffer_mm(),quad_segs=128)).area<=1e-12
        assert port.difference(site['core'].buffer(.5*site['radius'],quad_segs=128)).area==0
    candidate=sites[0]['core'].union(Point(0,0).buffer(.1687,quad_segs=128))
    assert verify_addition(sites[0]['core'],candidate,candidate,scene.obstacles(sites[0],0),
                           settings=scene.settings.kernel())['passed']


@pytest.mark.parametrize('left',[.15,.150001,.2])
def test_touching_or_nearby_region_does_not_acquire_a_port(left):
    rows,shapes,sites=case();g=box(left,-.03,1,.03)
    row=dict(rows[2],geometry_sha256=digest(to_wkb(g)))
    row['t01_original_region']=source_marker(SOURCE,row['id'],row['geometry_sha256'])
    assert original_port(sites[0],row,g,quad_segs=128)is None


@pytest.mark.parametrize('fault',['source_id','geometry','unbound','kind'])
def test_region_marker_mutation_rejects(fault):
    rows,shapes,sites=case();row=copy.deepcopy(rows[2]);g=shapes[2]
    if fault=='source_id':row['t01_original_region']['source_id']='foreign'
    elif fault=='geometry':g=g.buffer(.000001)
    elif fault=='unbound':row['t01_original_region']['basis']='CURRENT_CONTACT'
    else:row['kind']='gr_circle'
    with pytest.raises(ValueError,match='CONTACT_BINDING_CHANGED'):
        original_port(sites[0],row,g,quad_segs=128)


def test_current_contact_cannot_rewrite_original_attachment_permission():
    rows,shapes,sites=case();g=box(.16,-.03,.8,.03)
    row=dict(rows[2],geometry_sha256=digest(to_wkb(g)))
    row['t01_original_region']=source_marker(SOURCE,row['id'],row['geometry_sha256'])
    assert sites[0]['core'].buffer(.03).intersects(g)
    assert original_port(sites[0],row,g,quad_segs=128)is None


def test_local_original_region_to_trace_chain_is_recognized_without_new_contact():
    from src.t01_region_contacts import integral_trace_ports
    rows,shapes,sites=case()
    # The trace does not touch the circle, but joins its existing Region locally.
    trace=box(.155,-.02,.4,.02);sid=SOURCE+':bytes:31:40'
    rows.append(dict(id=sid,kind='segment',geometry_sha256=digest(to_wkb(trace))))
    shapes.append(trace)
    assert trace.intersection(sites[0]['core']).area==0
    linked=integral_trace_ports(sites[0],rows,shapes,quad_segs=128)
    assert sid in linked
    remote=box(-.3,.21,.3,.24);foreign=SOURCE+':bytes:41:50'
    rows.append(dict(id=foreign,kind='segment',geometry_sha256=digest(to_wkb(remote))))
    shapes.append(remote)
    assert foreign not in integral_trace_ports(sites[0],rows,shapes,quad_segs=128)


def test_remote_connection_inside_one_region_cannot_exempt_another_local_arm():
    rows,shapes,sites=case()
    region=shapes[2].union(box(-1,.21,1,.26)).union(box(.95,-.035,1,.26))
    rows[2]['geometry_sha256']=digest(to_wkb(region))
    rows[2]['t01_original_region']=source_marker(SOURCE,rows[2]['id'],rows[2]['geometry_sha256'])
    shapes[2]=region;scene=WorkingScene(b'',rows,shapes,sites,CropSettings())
    candidate=sites[0]['core'].buffer(.04)
    q=verify_addition(sites[0]['core'],candidate,candidate,scene.obstacles(sites[0],0),
                      settings=scene.settings.kernel())
    assert not q['passed'] and any(v['source_id']==rows[2]['id']for v in q['hard_gap_violations'])


def test_source_guard_and_full_scene_reconstruct_the_same_region_ports():
    from src.t01_canonical_surface import SurfaceGuard
    from src.prepared_land_scene import PreparedLandScene
    from src.t01_region_contacts import install_prepared_ports
    rows,shapes,sites=case();scene=WorkingScene(b'',rows,shapes,sites,CropSettings())
    guard=SurfaceGuard(rows,shapes,sites);site=sites[0]
    candidate=site['core'].union(Point(0,0).buffer(.1687,quad_segs=128))
    bounded=guard.limit(site,candidate,scene,priority=True)
    assert bounded.symmetric_difference(candidate).area<=scene.settings.area_epsilon
    lands=[dict(id=site['source_id'],original=site['core'],candidate=bounded,
                native_source_kind='gr_circle',native_stroke_width_mm=0.)]
    fixed=[dict(id=rows[i]['id'],geometry=shapes[i],trace_width_mm=0.)for i in [1,2]]
    checker=PreparedLandScene(lands,fixed)
    proof=install_prepared_ports(checker,rows)
    assert len(proof)==1 and checker.check(lands,materialize_scene=True)['passed']
    assert to_wkb(checker.ports[(site['source_id'],rows[2]['id'])][0])==to_wkb(scene.ports[site['source_id']][rows[2]['id']])


def test_legitimate_joint_does_not_exempt_a_foreign_pin_or_its_gap():
    rows,shapes,sites=case();foreign=box(-1,.21,1,.26)
    sid=SOURCE+':bytes:31:40';rows.append(dict(id=sid,kind='gr_poly',trace_width_mm=0.,
        source_span=[0,0],geometry_sha256=digest(to_wkb(foreign)),
        t01_original_region=source_marker(SOURCE,sid,digest(to_wkb(foreign)))))
    shapes.append(foreign);scene=WorkingScene(b'',rows,shapes,sites,CropSettings())
    assert rows[2]['id']in scene.ports[sites[0]['source_id']]
    assert sid not in scene.ports[sites[0]['source_id']]
    proposed=sites[0]['core'].buffer(.04)
    q=verify_addition(sites[0]['core'],proposed,proposed,scene.obstacles(sites[0],0),
                      settings=scene.settings.kernel())
    assert not q['passed'] and any(v['source_id']==sid for v in q['hard_gap_violations'])


def test_region_recognition_does_not_waive_protected_same_component_slot(monkeypatch):
    from src import pin_separation as pin
    left=box(.2,0,.3,2);right=box(.4,0,.5,2);pad=Point(.25,1.5).buffer(.08,quad_segs=128)
    source=left.union(right).union(box(.2,1.9,.5,2.1)).union(pad)
    slot=pin.Slot(SOURCE,'slot',('left','right'),box(.25,-.1,.45,1.8),source,(left,right),('joint',))
    rule=pin.Rule([slot],construction_gap=.0401,finished_gap=.04)
    row=dict(id=SOURCE+':bytes:21:30',kind='gr_poly',geometry_sha256=digest(to_wkb(left)))
    row['t01_original_region']=source_marker(SOURCE,row['id'],row['geometry_sha256'])
    site=dict(core=pad,radius=.08)
    assert original_port(site,row,left,quad_segs=128)is not None
    assert not rule.growth_parts([source],[source.union(box(.29,1.49,.41,1.51))])['passed']
