"""Actual source-ID assembly respects channels tied only by source frame copper."""
import copy
import pytest
from shapely.geometry import box
from src.gerber_u05 import pipeline as p
from src.gerber_u05.native_component_checks_final import decoded_groups,clearance,final_inventory,NativeGroups
from src.source_channel_scope import install_reserved
from tests.gerber_u05.test_channel_construction import fixture

def test_native_groups_preserve_the_bar_but_keep_two_functional_channels(tmp_path,monkeypatch):
 store,scene,source,scope,originals=fixture(tmp_path,monkeypatch)
 groups=decoded_groups(source,{})
 assert len(groups)==1 and len(groups.channels)==2
 assert p.unary_union(list(groups.values())).equals(source)
 proof=final_inventory(source,groups)
 assert proof['passed']and proof['original_components_preserved']==1
 assert proof['functional_channels_preserved']==2

def test_actual_bridge_is_rejected_even_when_physical_source_owner_is_one(tmp_path,monkeypatch):
 store,scene,source,scope,originals=fixture(tmp_path,monkeypatch)
 before=decoded_groups(source,{});after=decoded_groups(source,{'trace:0':[box(2,6,8.1,6.1)]})
 assert len(after)==1
 with pytest.raises(ValueError,match='NATIVE_FOREIGN_ORIGINAL_COMPONENT_CLEARANCE_FAILED'):clearance(before,after)
 with pytest.raises(ValueError,match='MERGED_OR_UNBOUND|PARTITION_CHANGED'):final_inventory(source,after)

def test_native_local_growth_does_not_need_clearance_from_its_own_source(tmp_path,monkeypatch):
 store,scene,source,scope,originals=fixture(tmp_path,monkeypatch)
 before=decoded_groups(source,{});after=decoded_groups(source,{'trace:0':[box(1.9,4,2.2,4.2)]})
 assert clearance(before,after)['functional_channels']['passed']
 assert final_inventory(source,after)['passed']

def test_actual_appended_frame_growth_is_never_a_channel(tmp_path,monkeypatch):
 store,scene,source,scope,originals=fixture(tmp_path,monkeypatch)
 sid=next(iter(scope.frame_ids))
 with pytest.raises(ValueError,match='TEMPORARY_FRAME_NATIVE_ADDITION_NOT_ALLOWED'):decoded_groups(source,{sid:[originals[sid].buffer(.01)]})

def sidecar_fixture(store,scope):
 return dict(schema='actual-native-channel-reservation/1',status='PASS',source_sha256=scope.source_hash,generated_sha256='b'*64,channel_certificate_sha256=p.digest(p.canonical(scope.certificate)),owned_geometry_refs={o:p.geomref(store,g)for o,g in scope.cores.items()})

def test_reservation_reloads_known_native_channels_instead_of_cutting_the_bar(tmp_path,monkeypatch):
 store,scene,source,scope,originals=fixture(tmp_path,monkeypatch)
 payload=sidecar_fixture(store,scope)
 assert install_reserved(scope,store,payload,'b'*64)['passed']
 assert set(scope.reserved)==set(scope.cores)

@pytest.mark.parametrize('key',['source_sha256','generated_sha256','channel_certificate_sha256','status'])
def test_changed_native_channel_reservation_binding_cannot_be_used(tmp_path,monkeypatch,key):
 store,scene,source,scope,originals=fixture(tmp_path,monkeypatch);payload=sidecar_fixture(store,scope);payload[key]='CHANGED'
 with pytest.raises(ValueError,match='NATIVE_CHANNEL_RESERVATION'):install_reserved(scope,store,payload,'b'*64)
