"""Complete crop inventories exceed transport pages without changing shared ABIs."""
import copy,json
from pathlib import Path
import pytest
from shapely.geometry import box
from shapely import to_wkb
from src.stage_abi import ABI_VERSION
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.stage_abi.contracts import StageABIError
from src.t01_crop import PROFILE
from src.t01_crop.paging import store_pages,read_pages,inspection_binding,PageBudget
from src.t01_crop.service import CropService
from src.t01_crop.protocol import validate


def environment(tmp_path,n=115):
    store=ArtifactStore(tmp_path/'runtime');geometry=store.put('geometry',to_wkb(box(0,0,1,1)))
    objects=[dict(source_id=f'object-{i:06d}',kind='circle',original_ref=geometry,geometry_ref=geometry,metadata={}) for i in range(n)]
    scene=dict(source_sha256=digest(b'synthetic pagination fixture'),frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=[-1,-1,2,2],objects=objects,findings=[],lineage=[],acceptance={})
    scene_ref=store.put_json('scene',scene);policy_ref=store.put_json('policy',dict(stage='t01'))
    bounds=store.put_json('bounds',dict(max_source_objects=n,max_targets=n,max_evaluations=10000,max_output_bytes=200000000,max_seconds=3600))
    verifier=store.put_json('verifier',{})
    host=dict(schema='t01-crop-host/1',compiler_binding_refs=[],stage_registry=dict(schema='stage-agent-registry/1',profiles={PROFILE:dict(stage='t01',adapter=PROFILE,policy_ref=policy_ref,scene_refs=[scene_ref],bounds_ref=bounds,verifier_ref=verifier)},authorization_refs=[],decision_refs=[]))
    service=CropService(store,host)
    def request(verb,payload):
        return dict(abi_version=ABI_VERSION,request_id='pagination-test',operation='t01_'+verb,profile_id=PROFILE,scene_ref=scene_ref,policy_ref=policy_ref,plan_ref=None,authorization_ref=None,idempotency_key=None,payload=payload)
    ids=[row['source_id'] for row in objects]
    selection=store.put_json('selection',dict(stage='t01',scene_ref=scene_ref,source_ids=ids))
    return store,service,request,scene,selection,bounds


@pytest.mark.parametrize('count',[1,100,101,115,1001])
def test_complete_inspection_pages_all_records(tmp_path,count):
    store,service,req,scene,selection,bounds=environment(tmp_path,count)
    r=service.dispatch(req('inspect_all',dict(selection_ref=selection,page_size=100)))
    assert r['status']=='OK',r
    result=r['result'];assert result['total_records']==count and len(result['records'])==count
    assert result['page_count']==(count+99)//100 and result['next_cursor'] is None
    rows,index=read_pages(store,result['pagination_ref'],binding=inspection_binding(req('inspect_all',{}),selection),kind='t01-inspection',identity=lambda x:x['record']['source_id'])
    assert rows==result['records'] and {x['record']['source_id'] for x in rows}==set(result['selected_source_ids'])


def test_comparison_crosses_former_1000_id_limit_without_shared_change(tmp_path):
    store,service,req,scene,selection,bounds=environment(tmp_path,1001)
    view=store.put_json('viewport',dict(frame=scene['frame'],bounds_mm=scene['viewport_mm']))
    selected=store.put_json('evidence-selection',dict(source_ids=[row['source_id'] for row in scene['objects']]))
    r=service.dispatch(req('compare_all',dict(left_ref=req('x',{})['scene_ref'],right_ref=req('x',{})['scene_ref'],viewport_ref=view,evidence_selection_ref=selected,page_size=100)))
    assert r['status']=='OK',r
    assert len(r['result']['source_changes'])==1001 and r['result']['page_count']==11
    assert r['result']['added_area_mm2']==0 and r['result']['removed_area_mm2']==0


@pytest.mark.parametrize('mutation',['drop','reverse','repeat','bad-total','bad-binding','broken-link','bad-cursor','duplicate-id','truncated-final'])
def test_page_corruptions_fail_closed(tmp_path,mutation):
    store=ArtifactStore(tmp_path/'runtime');binding=dict(scene='source-bound');kind='fixture'
    rows=[dict(source_id=f's{i}') for i in range(115)]
    ref=store_pages(store,rows,binding=binding,kind=kind)
    index=store.get_json(ref,kind=kind+'-index')
    if mutation=='drop':index['pages'].pop()
    elif mutation=='reverse':index['pages'].reverse()
    elif mutation=='repeat':index['pages'].append(index['pages'][0])
    elif mutation=='bad-total':index['total_records']=114
    elif mutation=='bad-binding':index['binding']={'scene':'other'}
    else:
        entry=index['pages'][1];page=store.get_json(entry['page_ref'],kind=kind+'-page')
        if mutation=='broken-link':page['previous_page_ref']=None
        elif mutation=='bad-cursor':page['next_offset']=114
        elif mutation=='duplicate-id':page['records'][0]['source_id']='s0'
        elif mutation=='truncated-final':page['records'].pop()
        entry['page_ref']=store.put_json(kind+'-page',page)
    altered=store.put_json(kind+'-index',index)
    with pytest.raises(StageABIError):read_pages(store,altered,binding=binding,kind=kind,identity=lambda x:x['source_id'])


def test_source_inventory_above_20000_is_complete(tmp_path):
    store=ArtifactStore(tmp_path/'runtime');records=[dict(source_id=f's{i}') for i in range(20001)];binding=dict(source_sha256=digest(b'source'))
    ref=store_pages(store,records,binding=binding,kind='t01-source-inventory')
    actual,index=read_pages(store,ref,binding=binding,kind='t01-source-inventory',identity=lambda r:r['source_id'])
    assert actual==records and len(index['pages'])==201 and index['pages'][-1]['count']==1


def test_resource_budget_retained_without_fixed_record_cap(tmp_path):
    store=ArtifactStore(tmp_path/'runtime')
    with pytest.raises(StageABIError,match='Pagination byte/time'):
        store_pages(store,[dict(source_id='one')],binding={},kind='fixture',budget=PageBudget(max_bytes=1))


@pytest.mark.parametrize('page_size',[0,101,True])
def test_wire_page_size_stays_bounded(tmp_path,page_size):
    store,service,req,scene,selection,bounds=environment(tmp_path)
    r=service.dispatch(req('inspect_all',dict(selection_ref=selection,page_size=page_size)))
    assert r['status']=='REJECTED'


def test_first_legacy_page_cannot_authorize_complete_plan(tmp_path):
    store,service,req,scene,selection,bounds=environment(tmp_path)
    page=service.dispatch(req('inspect',dict(selection_ref=selection,page_size=100,cursor=None)))
    assert page['status']=='OK' and len(page['result']['records'])==100 and page['result']['total_records']==115
    q=store.put_json('verification',dict(scene_ref=req('x',{})['scene_ref'],geometric_status='PASS'))
    r=service.dispatch(req('plan',dict(inspection_ref=page['result']['inspection_ref'],selection_ref=selection,predecessor_qualification_ref=q,bounds_ref=bounds,strategy='priority_companion_growth')))
    assert r['status']=='REJECTED' and r['error']['code']=='T01_COMPLETE_INSPECTION_REQUIRED'


def test_plan_rechecks_aggregate_records_and_page_chain_before_adapter(tmp_path):
    store,service,req,scene,selection,bounds=environment(tmp_path)
    inspected=service.dispatch(req('inspect_all',dict(selection_ref=selection,page_size=100)))['result']
    artifact=store.get_json(inspected['inspection_ref'],kind='inspection');artifact['records']=artifact['records'][:100]
    bad=store.put_json('inspection',artifact)
    q=store.put_json('verification',dict(scene_ref=req('x',{})['scene_ref'],geometric_status='PASS'))
    r=service.dispatch(req('plan',dict(inspection_ref=bad,selection_ref=selection,predecessor_qualification_ref=q,bounds_ref=bounds,strategy='priority_companion_growth')))
    assert r['status']=='REJECTED' and r['error']['code']=='T01_COMPLETE_INSPECTION_REQUIRED'


def test_host_counts_and_inventory_binding_are_data_derived_above_20000(tmp_path,monkeypatch):
    from tools import t01_crop_host as host
    session=tmp_path/'session';(session/'data_roi/source_wkb').mkdir(parents=True)
    raw=b'(synthetic host pagination fixture)';native=session/'source.kicad_pcb';native.write_bytes(raw)
    geometry=to_wkb(box(0,0,1,1));h=digest(geometry)
    (session/'data_roi/source_wkb'/f'{h}.wkb').write_bytes(geometry)
    rows=[dict(id=f's{i}',kind='gr_circle',geometry_sha256=h,trace_width_mm=0) for i in range(20001)]
    (session/'data_roi/source_manifest.json').write_bytes(canonical(dict(objects=rows)))
    (session/'data_roi/roi_verified.json').write_bytes(canonical(dict(bounds_mm=[0,0,1,1],uncertainty_mm=.01)))
    (session/'crop_inputs.json').write_bytes(canonical(dict(kicad=dict(path=str(native)))))
    monkeypatch.setattr(host,'check',lambda p:None)
    cap=host.prepare(session);store=ArtifactStore(Path(cap['store_path']))
    counts=store.get_json(cap['bounds_ref'],kind='bounds');binding=store.get_json(cap['binding_ref'],kind='t01-binding')
    from src.t01_crop.policy import validate_binding
    assert validate_binding(binding)['source_objects']==20001
    assert counts['max_source_objects']==counts['max_targets']==20001
    records,index=read_pages(store,binding['source_inventory_ref'],binding=dict(source_sha256=binding['source_sha256'],manifest_sha256=binding['manifest_sha256']),kind='t01-source-inventory',identity=lambda x:x['source_id'])
    assert len(records)==20001 and len(index['pages'])==201
