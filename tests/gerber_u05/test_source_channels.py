import pytest
from shapely import to_wkb
from shapely.geometry import box,Point
from src.source_channel_guard import SourceChannels,POLICY
from src.stage_abi.store import digest

def case():
 frame=box(0,0,10,10).difference(box(.1,.1,9.9,9.9));left=box(2,0,2.1,8).union(Point(2.05,7).buffer(.4,quad_segs=64));right=box(8,0,8.1,8);source=frame.union(left).union(right);certificate=dict(policy=POLICY,source_sha256='a'*64,frame_geometry_sha256=digest(to_wkb(frame)));return SourceChannels(source,'a'*64,frame,certificate),source,left,right

def test_remote_common_frame_is_not_a_local_merge_exemption():
 guard,source,left,right=case()
 assert guard.check(source)['passed']
 assert len(guard.original)==2
 bad=source.union(box(2,6,8.1,6.1));check=guard.check(bad)
 assert not check['passed']and check['failures'][0]['reason']=='CHANNELS_MERGED_OUTSIDE_TEMPORARY_FRAME'

def test_local_pad_to_trace_growth_retains_its_integral_channel():
 guard,source,left,right=case();grown=source.union(Point(2.05,7).buffer(.45,quad_segs=64));assert guard.check(grown)['passed']

def test_new_channel_gap_is_checked_before_a_bridge_is_formed():
 guard,source,left,right=case();grown=source.union(box(2,6,7.98,6.1));check=guard.check(grown)
 assert not check['passed']and any(r['reason']=='NEW_COPPER_TO_DIFFERENT_SOURCE_CHANNEL_CLEARANCE'for r in check['failures'])
 assert guard.check(source.union(box(2,6,7.95,6.1)))['passed']

def test_original_close_channel_gap_is_not_misreported_as_new_growth():
 guard,source,left,right=case();assert guard.check(source)['pairs']==[]

def test_analytical_exclusion_does_not_delete_or_mutate_source_copper():
 guard,source,left,right=case();before=to_wkb(source);frame=to_wkb(guard.frame);guard.check(source.union(Point(2.05,7).buffer(.45,quad_segs=64)))
 assert to_wkb(source)==before and to_wkb(guard.frame)==frame
 assert source.covers(guard.frame)

def test_actual_unbound_new_copper_is_rejected():
 guard,source,left,right=case();check=guard.check(source.union(box(4,4,5,5)))
 assert not check['passed']and check['failures'][0]['reason']=='NEW_UNBOUND_COPPER_OUTSIDE_TEMPORARY_FRAME'

def test_missing_original_channel_is_rejected():
 guard,source,left,right=case();check=guard.check(guard.frame.union(left))
 assert not check['passed']and check['failures'][0]['reason']=='FROZEN_SOURCE_CHANNEL_MISSING'

def test_frame_binding_and_nominal_gap_cannot_be_substituted():
 guard,source,left,right=case()
 with pytest.raises(ValueError,match='BINDING_CHANGED'):SourceChannels(source,'b'*64,guard.frame,dict(policy=POLICY,source_sha256='a'*64,frame_geometry_sha256=digest(to_wkb(guard.frame))))
 with pytest.raises(ValueError,match='FLOOR_CHANGED'):guard.check(source,gap=.02)

def frame_scene(tmp_path,duplicate=False,open_end=False):
 from src.stage_abi.store import ArtifactStore
 from shapely.geometry import LineString
 from shapely.ops import unary_union
 store=ArtifactStore(tmp_path/'runtime');rows=[];shapes=[]
 for i,(a,b)in enumerate([((0,0),(10,0)),((10,0),(10,10)),((10,10),(0,10)),((0,10),(0,0))]):
  if open_end and i==3:continue
  g=LineString([a,b]).buffer(.05,quad_segs=64);ref=store.put('geometry',to_wkb(g));rows.append(dict(source_id='frame:'+str(i),kind='stroke',original_ref=ref,geometry_ref=ref,metadata=dict(aperture_family=['C',.1],endpoints_decimal_mm=[[str(x)for x in a],[str(x)for x in b]])));shapes.append(g)
 if duplicate:rows.append(dict(rows[0],source_id='duplicate-frame-alias'))
 for i,x in enumerate((2,8)):
  g=LineString([(x,0),(x,8)]).buffer(.04,quad_segs=64);ref=store.put('geometry',to_wkb(g));rows.append(dict(source_id='trace:'+str(i),kind='stroke',original_ref=ref,geometry_ref=ref,metadata=dict(aperture_family=['C',.08],endpoints_decimal_mm=[[str(x),'0'],[str(x),'8']])));shapes.append(g)
 return store,dict(source_sha256='a'*64,units='mm',objects=rows),unary_union(shapes)

def test_frame_discovery_is_source_bound_and_preserves_duplicate_occurrences(tmp_path):
 from src.source_common_frame import discover
 store,scene,source=frame_scene(tmp_path,duplicate=True);before=to_wkb(source);frame,certificate=discover(source,'a'*64,scene,store)
 assert certificate['frame_parts']==4 and certificate['all_occurrences']==5
 assert certificate['source_channels']==2 and not certificate['material_edit']
 assert guard_for(frame,certificate,source,store).check(source)['passed']and before==to_wkb(source)

def guard_for(frame,certificate,source,store):return SourceChannels(source,'a'*64,frame,certificate,store=store)

def test_open_perimeter_cannot_be_silently_treated_as_a_common_frame(tmp_path):
 from src.source_common_frame import discover
 store,scene,source=frame_scene(tmp_path,open_end=True);frame,report=discover(source,'a'*64,scene,store)
 assert frame is None and report['status']=='NO_UNAMBIGUOUS_COMMON_FRAME'

def test_frame_discovery_ignores_current_growth_and_rejects_source_tampering(tmp_path):
 from src.source_common_frame import discover
 store,scene,source=frame_scene(tmp_path);first=discover(source,'a'*64,scene,store)[1]
 for row in scene['objects']:row['geometry_ref']=store.put('geometry',to_wkb(box(-20,-20,20,20)))
 assert discover(source,'a'*64,scene,store)[1]==first
 ref=scene['objects'][0]['original_ref'];(store.root/'artifacts'/ref['artifact_id']).write_bytes(b'corrupt')
 with pytest.raises(ValueError)as ex:discover(source,'a'*64,scene,store)
 assert ex.value.code=='ARTIFACT_CORRUPTED'

def test_non_enclosing_source_loop_cannot_supply_frame_exemption(tmp_path):
 from src.source_common_frame import discover
 store,scene,source=frame_scene(tmp_path);frame,report=discover(source.union(box(20,20,21,21)),'a'*64,scene,store)
 assert frame is None and report['status']=='NO_UNAMBIGUOUS_COMMON_FRAME'

def test_actual_source_loss_is_rejected_even_below_the_area_epsilon():
 from shapely.geometry import Polygon
 guard,source,left,right=case();triangle=Polygon([(2.1,4),(2.100001,4),(2.1,4.000001)]);extended=source.union(triangle)
 certificate=dict(policy=POLICY,source_sha256='a'*64,frame_geometry_sha256=digest(to_wkb(guard.frame)));strict=SourceChannels(extended,'a'*64,guard.frame,certificate)
 assert triangle.area<1e-12 and strict.check(extended)['passed']
 result=strict.check(source)
 assert not result['passed']and any(r['reason']=='FROZEN_SOURCE_CHANNEL_MISSING'for r in result['failures'])
