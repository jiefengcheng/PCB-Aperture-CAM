"""Registered gap matching is distinct from frozen-corridor growth permission."""
import json
import pytest
from shapely.geometry import box
from shapely.affinity import scale
from shapely.ops import unary_union
from src import t02_shared_gaps as gaps
from src.t02_gap_settings import REGISTRY,from_bytes,capture
from test_t02_shared_gaps import fixture,contexts

def shifted(tmp_path,shift):
 original,scene,store=fixture(tmp_path)
 current=dict(original,wall=original['wall'].union(box(2-shift,2,3,3)))
 spec=gaps.records(scene,original,current)
 proposed={s:scale(original[s],1.1,1.1,origin=original[s].centroid)for s in('a','b')}
 return original,scene,store,current,spec,proposed

def test_default_is_global_one_percent_and_snapshot_binds_raw_registry():
 setting=capture();assert setting.maximum_relative_gap_difference==.01
 snapshot=setting.snapshot();assert snapshot['registry_json']==REGISTRY.read_text()
 assert from_bytes(snapshot['registry_json'].encode())==setting
 assert gaps.policy()['gap_matching']==snapshot

@pytest.mark.parametrize('value',[-.01,1,True,'0.01',None])
def test_invalid_matching_limits_fail_closed(value):
 setting=json.loads(REGISTRY.read_bytes());setting['maximum_relative_gap_difference']=value
 with pytest.raises(ValueError,match='TOLERANCE_OUT_OF_RANGE'):from_bytes(json.dumps(setting).encode())

def test_nonfinite_duplicate_and_changed_schema_are_rejected():
 raw=REGISTRY.read_bytes()
 with pytest.raises(ValueError,match='NONFINITE'):from_bytes(raw.replace(b'0.01',b'NaN'))
 with pytest.raises(ValueError,match='DUPLICATE'):from_bytes(raw.replace(b'0.01',b'0.01, "maximum_relative_gap_difference": 0.02'))
 with pytest.raises(ValueError,match='SCHEMA_CHANGED'):from_bytes(raw.replace(b'PROVISIONAL',b'ACCEPTED'))

def test_registry_can_be_replaced_for_future_captures_without_mutating_snapshot(tmp_path):
 path=tmp_path/'settings.json';path.write_bytes(REGISTRY.read_bytes());before=capture(path)
 data=json.loads(path.read_bytes());data['maximum_relative_gap_difference']=.005;path.write_text(json.dumps(data));after=capture(path)
 assert before.maximum_relative_gap_difference==.01 and after.maximum_relative_gap_difference==.005
 assert before.snapshot()['registry_sha256']!=after.snapshot()['registry_sha256']

@pytest.mark.parametrize('relative',[.005,.01])
def test_distinct_qualified_wall_positions_within_one_percent_keep_their_actual_planes(tmp_path,relative):
 shift=.95*relative/(1+relative)
 original,scene,store,current,spec,proposed=shifted(tmp_path,shift)
 result,proof=gaps.project(spec,original,current,proposed)
 whole=unary_union(list(dict(current,**result).values()));check=gaps.complete(proof,whole)
 assert check['passed']and check['gap_matching']['groups'][0]['relative_gap_difference']==pytest.approx(relative)
 assert proof['zones'][0]['right']==pytest.approx(2.)
 assert proof['zones'][1]['right']==pytest.approx(2-shift)
 assert current['wall'].difference(whole).is_empty
 assert gaps.frozen(spec,dict(current,**result))['zones']==proof['zones']

def test_more_than_one_percent_is_rejected_without_trimming_qualified_wall(tmp_path):
 original,scene,store,current,spec,proposed=shifted(tmp_path,.95*.0101/1.0101)
 before=current['wall'].wkb
 with pytest.raises(ValueError,match='MATCHING_TOLERANCE_EXCEEDED'):gaps.project(spec,original,current,proposed)
 assert current['wall'].wkb==before

def test_zero_can_restore_strict_matching_and_captured_policy_does_not_follow_later_changes(tmp_path,monkeypatch):
 original,scene,store,current,spec,proposed=shifted(tmp_path,.002)
 data=json.loads(REGISTRY.read_bytes());data['maximum_relative_gap_difference']=0
 strict=from_bytes(json.dumps(data).encode());monkeypatch.setattr(gaps,'gap_settings',lambda:strict)
 result,proof=gaps.project(spec,original,current,proposed)
 assert proof['policy']['gap_matching']['maximum_relative_gap_difference']==.01
 strict_spec=gaps.records(scene,original,current)
 with pytest.raises(ValueError,match='MATCHING_TOLERANCE_EXCEEDED'):gaps.project(strict_spec,original,current,proposed)

def test_matching_tolerance_does_not_grant_a_fresh_fill_allowance(tmp_path,monkeypatch):
 original,scene,store,current,spec,proposed=shifted(tmp_path,.002)
 result,proof=gaps.project(spec,original,current,proposed);whole=unary_union(list(dict(current,**result).values()))
 monkeypatch.setattr(gaps,'ACTIVE',proof)
 # This changes the gap by much less than 1%, but would spend additional
 # copper after its actual T02 wall was accepted. Matching is not permission
 # to bypass the frozen growth decision or refresh a later remedy budget.
 logical=box(1.049,.2,1.0501,.8)
 assert not gaps.remedy(logical,whole)['passed']
 assert not gaps.fill_check(dict(shared_neighbor_gaps=spec),dict(current,**result),logical)['passed']
 with pytest.raises(ValueError,match='UNIFORMITY'):gaps.complete(proof,whole.union(logical))
