"""Crop handoff cannot omit source/ROI evidence or reuse a later-stage authority."""
from pathlib import Path
import json,copy
import pytest
from src.stage_abi.store import canonical,digest,ArtifactStore
from src.pcb_data_abi.crop_custody import verify_checkpoint,ROI,T01,CHECK
from src.t01_crop.service import CropService
from src.t01_crop import PROFILE


def test_missing_roi_receipt_cannot_create_materialization_host(tmp_path):
    p=tmp_path/'proof.json';p.write_bytes(canonical(dict(schema='pcb-crop-checkpoint/1',operations=list((*ROI,*T01,CHECK)),files={})))
    with pytest.raises(ValueError,match='REQUIRED_EVIDENCE_MISSING'):verify_checkpoint(p,digest(p.read_bytes()),(*ROI,*T01,CHECK))

@pytest.mark.parametrize('stage',['t02','t03','t04','t05'])
def test_crop_service_has_no_later_stage_operation(tmp_path,stage):
    store=ArtifactStore(tmp_path/'runtime');service=CropService(store,dict(schema='t01-crop-host/1',compiler_binding_refs=[],stage_registry=dict(schema='stage-agent-registry/1',profiles={},authorization_refs=[],decision_refs=[])))
    r=service.dispatch(dict(abi_version='stage-agent-abi/1.0',request_id='later-stage-control',operation=stage+'_run',profile_id=None,scene_ref=None,policy_ref=None,plan_ref=None,authorization_ref=None,idempotency_key=None,payload={}))
    assert r['status']=='REJECTED' and r['result'] is None

@pytest.mark.parametrize('input_value',[None,[],{'schema':'foreign'}])
def test_crop_service_rejects_malformed_host(tmp_path,input_value):
    with pytest.raises((ValueError,TypeError)):CropService(ArtifactStore(tmp_path/'runtime'),input_value)


def test_t01_cannot_skip_data_location_or_pending_observation(tmp_path):
    from tools.t01_crop_route import CropRoute,STEPS
    route=CropRoute.__new__(CropRoute);route.submitted=True;route.halted=False;route.pending=None
    route.position=0;route.operations=list(STEPS);route.route_id='gate-test';route.session=tmp_path
    with pytest.raises(ValueError,match='Audit current result'):
        route._step('t01_run',dict(route_id=route.route_id,attempt_id='forbidden'),dict(name='test'))
    route.pending=dict(attempt_id='not-yet-reviewed')
    with pytest.raises(ValueError,match='Audit current result'):
        route._step('pcb_inputs_verify',dict(route_id=route.route_id,attempt_id='forbidden'),dict(name='test'))
    assert not list(tmp_path.iterdir())


def binding(store,roi_value):
    from src.t01_crop.policy import validate_binding
    raw=b'source';manifest=canonical(dict(source_sha256=digest(raw),objects=[]));roi_blob=canonical(roi_value)
    return dict(schema='t01-crop-binding/1',source_ref=store.put('native-source',raw),manifest_ref=store.put('native-manifest',manifest),source_sha256=digest(raw),manifest_sha256=digest(manifest),source_objects=1,viewport_mm=[0,0,1,1],roi_ref=store.put('roi-binding',roi_blob),roi_sha256=digest(roi_blob),location_uncertainty_mm=.01,reviewed_pairs=[],recess_source_ids=[])

@pytest.mark.parametrize('key,value',[('viewport_mm',[0,0,True,1]),('source_objects',True),('source_objects',0),('source_sha256','bad'),('location_uncertainty_mm',float('nan')),('reviewed_pairs',[['a','b'],['b','c']])])
def test_binding_rejects_invalid_numeric_or_identity_authority(tmp_path,key,value):
    from src.t01_crop.policy import validate_binding
    b=binding(ArtifactStore(tmp_path/'runtime'),{});b[key]=value
    with pytest.raises(ValueError):validate_binding(b)

@pytest.mark.parametrize('change',[dict(bounds_mm=[0,0,2,1]),dict(uncertainty_mm=.02),dict(facts=dict(location_verified=False))])
def test_t01_binding_cannot_reinterpret_verified_data_roi(tmp_path,change):
    from src.t01_crop.source import context
    store=ArtifactStore(tmp_path/'runtime');roi=dict(bounds_mm=[0,0,1,1],uncertainty_mm=.01,facts=dict(location_verified=True));roi.update(change)
    b=binding(store,roi);policy=dict(binding_ref=store.put_json('t01-binding',b))
    with pytest.raises(ValueError,match='receipt bounds/uncertainty'):context(store,dict(objects=[]),policy)


def test_route_rejects_export_that_omits_discovered_aliases(tmp_path):
    from tools.t01_crop_route import CropRoute
    route=CropRoute.__new__(CropRoute);route.discovery=dict(unique_sites=3,occurrences=4)
    r=dict(status='OK',error=None,result=dict(facts=dict(passed=True,canonical_sites=3,source_occurrences=3)))
    with pytest.raises(ValueError,match='complete discovered selection'):route._facts('pcb_kicad_write',r,0,tmp_path/'raw')
