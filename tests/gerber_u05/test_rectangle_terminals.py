"""Terminal admission, trace coverage and actual existing T02 growth controls."""
import math
import pytest
from shapely import to_wkb
from shapely.affinity import scale
from src.gerber_u05 import pipeline as p
from src.gerber_u05.rectangle_terminals import FAMILY, qualify
from src import component_clearance as cc, pin_separation as pin, source_channel_scope
from src import t04_width_fence as fence

HEADER = '%FSLAX46Y46*%\n%MOMM*%\n%ADD10R,0.4X0.4*%\n%ADD11C,0.08*%\n%LPD*%\n'


def source(tmp_path, body, header=HEADER):
    raw=(header+body+'M02*\n').encode()
    store=p.Store(tmp_path/'runtime');binding=p.build_source(store,raw)
    return store,binding,store.get_json(binding['scene_ref'],kind='scene')


@pytest.fixture(autouse=True)
def isolated_contexts(monkeypatch):
    for module in (cc,pin,source_channel_scope,fence):
        monkeypatch.setattr(module,'ACTIVE',None)


@pytest.mark.parametrize('end,axis',[('X50000Y0','x'),('X0Y50000','y'),('X-50000Y0','x')])
def test_short_draw_is_one_source_land_with_unchanged_native_ports(tmp_path,end,axis):
    store,binding,scene=source(tmp_path,'D10*\nX0Y0D02*\n'+end+'D01*\n')
    row=scene['objects'][0];md=row['metadata'];g=p.geometry(store,row['original_ref'])
    assert row['kind']=='rectangle'and md['qualified_land']
    assert md['rectangle_terminal']['family']==FAMILY and md['rectangle_terminal']['axis']==axis
    assert md['source_kind']=='Line'and md['alias_source_ids']==[row['source_id']]
    assert md['minimum_caliper_mm']==.4 and md['source_port_width_mm']==math.hypot(.4,.4)
    assert md['nominal_width_mm']==md['original_width_mm']==0.
    assert binding['width_metadata_rows'][0]['kind']=='segment'
    assert binding['width_metadata_rows'][0]['trace_width_mm']==math.hypot(.4,.4)
    assert row['geometry_ref']==row['original_ref']and g.area==pytest.approx(.4*.45)
    assert not p.width_admission(store,scene)['paths']
    t03=p.run_t03(store,scene,binding,{})
    assert t03['summary']['trace_occurrences']==1 and t03['summary']['moved']==0


@pytest.mark.parametrize('aperture,end',[
    ('0.065X0.065','X0Y1735000'), # top finger
    ('0.18X0.18','X0Y505000'),   # connector finger
    ('0.4X0.4','X1000000Y0'),   # ordinary longer trace
    ('0.4X0.4','X50000Y50000'), # diagonal has a nonrectangular sweep
    ('0.4X0.4','X0Y0'),         # degenerate source context
])
def test_long_fingers_diagonals_and_degenerate_draws_stay_traces(tmp_path,aperture,end):
    header=HEADER.replace('0.4X0.4',aperture)
    store,binding,scene=source(tmp_path,'D10*\nX0Y0D02*\n'+end+'D01*\n',header)
    row=scene['objects'][0]
    assert row['kind']=='stroke'and not row['metadata']['qualified_land']
    assert 'rectangle_terminal'not in row['metadata']


def test_clear_clipped_draw_cannot_get_terminal_authority(tmp_path):
    store,binding,scene=source(tmp_path,'D10*\nX0Y0D02*\nX50000Y0D01*\n')
    raw=store.get(binding['source_ref'],kind='gerber-source');parsed,_,_=p.source_profile.parse_source(raw)
    obj=parsed.objects[0];complete=p.source_profile.object_geometry(obj)[0]
    assert qualify(obj,complete,scale(complete,.99,1,origin=complete.centroid))is None
    clipped=raw.replace(b'M02*',b'%LPC*%\nD11*\nX200000Y0D03*\nM02*')
    with pytest.raises(ValueError,match='CLEAR_CLIPPED_TRACE'):
        p.build_source(store,clipped)


def test_terminal_aliases_and_flash_coverage_are_source_bound(tmp_path):
    store,binding,scene=source(tmp_path,'D10*\nX0Y0D02*\nX50000Y0D01*\nX0Y0D02*\nX50000Y0D01*\nX2000000Y0D03*\n')
    a,b,c=scene['objects']
    assert a['kind']==b['kind']==c['kind']=='rectangle'
    assert a['metadata']['alias_source_ids']==b['metadata']['alias_source_ids']==sorted([a['source_id'],b['source_id']])
    assert a['source_id']!=b['source_id']and a['original_ref']==b['original_ref']
    assert 'rectangle_terminal'not in c['metadata']


def test_t02_grows_terminal_and_retains_integral_trace_joint(tmp_path):
    store,binding,scene=source(tmp_path,'D10*\nX0Y0D02*\nX50000Y0D01*\nD11*\nX0Y0D02*\nX0Y1000000D01*\n')
    pad,trace=scene['objects'];old=p.geometry(store,pad['original_ref'])
    result=p.run_t02(store,scene);after=store.get_json(result['output_scene_ref'],kind='scene')
    assert result['verification']['passed']and result['summary']['rectangles']==1
    decision=result['candidate']['decisions'][0]
    assert decision['status']=='GROWN'and decision['shape']['factors']==[1.25,1.25]
    grown=p.geometry(store,decision['candidate_ref'])
    assert grown.covers(old)and grown.equals(scale(old,1.25,1.25,origin=old.centroid))
    out={r['source_id']:r for r in after['objects']}
    assert out[trace['source_id']]==trace
    assert grown.intersection(p.geometry(store,trace['original_ref'])).area>0


def test_component_t03_still_accounts_for_reclassified_native_draw(tmp_path,monkeypatch):
    store,binding,scene=source(tmp_path,'D10*\nX0Y0D02*\nX50000Y0D01*\n')
    _,current,_=p.operands(store,scene)
    monkeypatch.setattr(cc,'ACTIVE',cc.Context(p.unary_union(list(current.values())),scene['source_sha256'],current))
    proof=p.run_t03(store,scene,binding,{})
    assert proof['full_source_clearance']['passed']and proof['summary']['trace_occurrences']==1
    assert proof['records'][0]['source_id']==scene['objects'][0]['source_id']


def test_retained_trace_widening_cannot_be_relabelled_as_terminal_growth(tmp_path):
    store,binding,scene=source(tmp_path,'D10*\nX0Y0D02*\nX50000Y0D01*\n')
    row=scene['objects'][0];core=p.geometry(store,row['original_ref'])
    row['geometry_ref']=p.geomref(store,core.buffer(.01))
    from src.stage_abi.contracts import StageABIError
    with pytest.raises(StageABIError)as error:
        p.run_t02(store,scene)
    assert error.value.code=='WHOLE_RECTANGLE_REQUIRED'


def test_classification_preserves_t01_physical_allocation_inputs(tmp_path,monkeypatch):
    from src.gerber_u05 import rectangle_terminals
    store,binding,scene=source(tmp_path,'D10*\nX0Y0D02*\nX50000Y0D01*\nD11*\nX0Y500000D03*\n')
    raw=store.get(binding['source_ref'],kind='gerber-source')
    monkeypatch.setattr(rectangle_terminals,'qualify',lambda *args:None)
    baseline=p.build_source(store,raw);old=store.get_json(baseline['scene_ref'],kind='scene')
    assert binding['width_metadata_rows']==baseline['width_metadata_rows']
    assert binding['width_metadata_encoding_ref']==baseline['width_metadata_encoding_ref']
    assert [(r['source_id'],r['original_ref'])for r in scene['objects']]==[(r['source_id'],r['original_ref'])for r in old['objects']]
    assert p.canonical(p.legacy_run_t01(store,scene,binding)['allocation'])==p.canonical(p.legacy_run_t01(store,old,baseline)['allocation'])


def test_t04_t02_t05_keeps_new_terminal_attachment_and_trace_checks(tmp_path):
    from src.t04_settings import capture_job
    store,binding,scene=source(tmp_path,'D10*\nX0Y0D02*\nX50000Y0D01*\nD11*\nX0Y0D02*\nX0Y1000000D01*\n')
    capture_job(store.root.parent)
    t04=p.run_t04(store,scene);entry=store.get_json(t04['output_scene_ref'],kind='scene')
    assert t04['summary']['trace_occurrences']==1 and t04['checks']['envelope']['passed']
    t02=p.run_t02(store,entry);t05=p.run_t05(store,store.get_json(t02['output_scene_ref'],kind='scene'),t04)
    assert t05['verification']['passed']and t05['summary']['source_attachments']==1
    assert t05['contacts'][0]['lands']==[scene['objects'][0]['source_id']]


def test_new_terminals_cannot_bridge_protected_same_component_slot(tmp_path,monkeypatch):
    from shapely.geometry import box
    body=('D10*\nX0Y0D02*\nX50000Y0D01*\n'
          'X510000Y0D02*\nX560000Y0D01*\n'
          'D11*\nX0Y0D02*\nX0Y2000000D01*\n'
          'X510000Y2000000D01*\nX510000Y0D01*\n')
    store,binding,scene=source(tmp_path,body);a,b=scene['objects'][:2]
    _,current,_=p.operands(store,scene);whole=p.unary_union(list(current.values()))
    assert whole.geom_type=='Polygon' # Remote copper joins the two branches.
    slot=pin.Slot(scene['source_sha256'],'terminal-pair',(a['source_id'],b['source_id']),
                  box(-.3,-.4,.85,.4),whole,(current[a['source_id']],current[b['source_id']]))
    rule=pin.Rule([slot],construction_gap=p.CONSTRUCTION_GAP_MM,finished_gap=p.HARD_GAP_MM)
    monkeypatch.setattr(pin,'ACTIVE',rule)
    result=p.run_t02(store,scene);out=store.get_json(result['output_scene_ref'],kind='scene')
    assert result['verification']['passed']and rule.check(p.composed(store,out))['passed']
    decisions=result['candidate']['decisions']
    assert all(d['shape']['factors'][0]<1.25 for d in decisions)
    assert any(not attempt['passed']for d in decisions for attempt in d['attempts'])
    assert not any(d['status']=='MERGED'for d in result['candidate']['inclusive_candidates'])
    rejected=[d for d in result['candidate']['inclusive_candidates']if d.get('pin_separation',{}).get('passed')is False]
    assert rejected and rule.rejected_count==len(rejected)
    assert not rule.rejected.is_empty


def test_shared_catalogue_has_exclusive_t02_and_retains_native_roles(tmp_path):
    from src.gerber_u05.source_catalogue import authority,native_draw,t04_trace,t02_land,t05_land
    store,binding,scene=source(tmp_path,'D10*\nX0Y0D02*\nX50000Y0D01*\nD11*\nX0Y0D02*\nX0Y1000000D01*\n')
    pad,trace=scene['objects'];value=store.get_json(binding['source_catalogue_ref'],kind='source-catalogue')
    assert value['source_sha256']==scene['source_sha256']and value['owner_counts']=={'T02':1,'T04':1}
    assert authority(pad)['growth_owner']=='T02'
    assert native_draw(pad)and t02_land(pad)and t05_land(pad)and not t04_trace(pad)
    assert native_draw(trace)and t04_trace(trace)and not t02_land(trace)and not t05_land(trace)
    assert {r['source_id']for r in value['records']}=={r['source_id']for r in scene['objects']}


@pytest.mark.parametrize('mutation',['owner','erase','kind','core'])
def test_shared_stage_assignment_cannot_be_removed_or_redirected(tmp_path,mutation):
    from src.gerber_u05.source_catalogue import t04_trace,t02_land
    store,binding,scene=source(tmp_path,'D10*\nX0Y0D02*\nX50000Y0D01*\n')
    row=scene['objects'][0]
    if mutation=='owner':row['metadata']['growth_authority']['growth_owner']='T04'
    elif mutation=='erase':del row['metadata']['growth_authority']
    elif mutation=='kind':row['kind']='stroke'
    else:row['original_ref']={'artifact_id':'geometry:'+'a'*64,'sha256':'a'*64}
    for query in (t04_trace,t02_land):
        with pytest.raises(ValueError):query(row)
