import copy
from shapely import to_wkb
from shapely.geometry import box
from src.stage_abi.store import ArtifactStore
from src.stage_abi.width import WidthAdapter,width_parameters
from src.source_offset_width import construct_source_offset_width
from tests.test_uniform_trace_width import fixture
from tests.stage_abi_support import host,run_verify


def case(tmp_path,*,duplicate_group=False,wrong_width=False):
 store=ArtifactStore(tmp_path/'runtime');raw,chain,meta,blobs=fixture(['(segment (start 0 0) (end 1 0) (width 0.1) (layer F.Cu) (net 0))','(segment (start 0 0.16) (end 1 0.16) (width 0.1) (layer F.Cu) (net 0))']);source=store.put('native-source',raw);rows=[]
 for i,member in enumerate(chain['source_ids']):
  sid='trace-'+str(i);c=dict(chain,component_id=sid,source_ids=[member]);_,_,_,core,_,_=construct_source_offset_width(raw,c,meta,blobs,1.);ref=store.put('geometry',to_wkb(core));native=store.put_json('native-route',dict(source_ref=source,chain=c,manifest_rows={member:meta[member]},geometry_refs={member:store.put('geometry',blobs[member])}));rows.append(dict(source_id=sid,kind='trace',original_ref=ref,geometry_ref=ref,metadata=dict(native_route_ref=native,nominal_width_mm=.2 if wrong_width else .1)))
 fixed=store.put('geometry',to_wkb(box(2,2,3,3)));rows.append(dict(source_id='fixed-land',kind='rectangle',original_ref=fixed,geometry_ref=fixed,metadata={}))
 selection=dict(source_ids=['trace-0','trace-1'],groups=[dict(group_id='parallel',members=['trace-0','trace-1','trace-0'] if duplicate_group else ['trace-0','trace-1'])]);return host(store,'t04',WidthAdapter(),rows,width_parameters(),selection,source_sha256=chain['source_sha256'])

def test_real_native_collective_search_and_exact_source_verification(tmp_path):
 e=case(tmp_path);assert 'plan_error' not in e,e
 c,v=run_verify(e,dict(scope='complete-source-nominal-envelope-and-upper-proofs'));candidate=c['candidate'];scales=candidate['solution']['selected_scales'];assert len(scales)==1 and 1<scales['parallel']<1.5;assert candidate['solution']['maximum_established'];assert len(candidate['parts'])==2;assert v['verification']['check']['reconstructed_native_parts']==2
 assert {r['factor'] for r in candidate['construction']}=={scales['parallel']}

def test_width_rejects_incorrect_original_nominal_width(tmp_path):
 e=case(tmp_path,wrong_width=True);assert e['plan_error']['error']['code']=='SOURCE_ROUTE_GEOMETRY_MISMATCH'

def test_width_rejects_duplicate_parallel_membership(tmp_path):
 e=case(tmp_path,duplicate_group=True);assert e['plan_error']['status']=='REJECTED'

def test_width_verifier_detects_changed_native_part(tmp_path):
 e=case(tmp_path);c,_=run_verify(e,dict(scope='complete-source-nominal-envelope-and-upper-proofs'));bad=copy.deepcopy(c['candidate']);member=next(iter(bad['parts']));bad['parts'][member]['nominal_ref']=e['store'].put('geometry',to_wkb(box(0,0,.1,.1)));ref=e['store'].put_json('candidate',bad);proof=e['store'].put_json('proof-scope',dict(scope='complete-source-nominal-envelope-and-upper-proofs'));r=e['service'].dispatch(e['req']('verify',dict(candidate_ref=ref,verifier_ref=e['verifier'],proof_scope_ref=proof),plan_ref=e['plan'],authorization_ref=e['auth'],idempotency_key='tampered'));assert r['error']['code']=='WIDTH_RECONSTRUCTION_MISMATCH'
