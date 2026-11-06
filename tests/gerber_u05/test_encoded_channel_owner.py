import pytest
from shapely.geometry import box
from src import source_channel_scope as functional
from src.source_common_frame import discover
from src.source_channel_guard import SourceChannels
from src.gerber_u05 import pipeline as p,legacy_export as e
from tests.gerber_u05.test_channel_construction import fixture

def owners(tmp_path,monkeypatch):
 store,scene,source,old,objects=fixture(tmp_path,monkeypatch);branch=box(8,4,8.3,4.1);ref=p.geomref(store,branch);scene['objects'].append(dict(source_id='local-branch',kind='fixed_source',original_ref=ref,geometry_ref=ref,metadata={}));source=source.union(branch);frame,cert=discover(source,'a'*64,scene,store);objects={r['source_id']:p.geometry(store,r['original_ref'])for r in scene['objects']};scope=functional.Scope(SourceChannels(source,'a'*64,frame,cert,store=store),cert,objects);scope.assign('short-route',None,scope.ids['trace:1']);monkeypatch.setattr(functional,'ACTIVE',scope);return store,objects,scope

def test_native_support_uses_other_original_parts_of_the_same_channel(tmp_path,monkeypatch):
 store,objects,scope=owners(tmp_path,monkeypatch);patch=box(8.25,4.08,8.27,4.2);records=[];blocks=[];e.append_regions(patch,'t05','short-route',records,blocks,store);native=e.parse(b'%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.100000*%\n'+''.join(blocks).encode()+b'M02*\n');parents=[p.affine_scale(p.source_profile.object_geometry(obj)[0],1,-1,origin=(0,0))for obj in native.objects]
 local=objects['trace:1']
 with pytest.raises(ValueError,match='NOT_FILE_GRID_POINT_CONTACT'):e.preserve_point_contacts(local,parents,'short-route',records,blocks,store)
 complete=e.encoded_route_owner(objects,['trace:1'],[],'short-route')
 assert complete.covers(objects['local-branch'])and not complete.intersects(objects['trace:0'])
 assert e.preserve_point_contacts(complete,parents,'short-route',records,blocks,store)==[]

def test_a_remote_bar_cannot_hide_disconnected_material_from_another_channel(tmp_path,monkeypatch):
 store,objects,scope=owners(tmp_path,monkeypatch);own=e.encoded_route_owner(objects,['trace:1'],[],'short-route');foreign=box(2,5,2.01,5.1)
 with pytest.raises(ValueError,match='NOT_FILE_GRID_POINT_CONTACT'):e.preserve_point_contacts(own,[foreign],'short-route',[],[],store)

def test_nonchannel_legacy_owner_operand_is_unchanged(tmp_path,monkeypatch):
 store,objects,scope=owners(tmp_path,monkeypatch);monkeypatch.setattr(functional,'ACTIVE',None)
 assert e.encoded_route_owner(objects,['trace:1'],['local-branch'],'short-route').wkb==p.unary_union([objects['trace:1'],objects['local-branch']]).wkb
