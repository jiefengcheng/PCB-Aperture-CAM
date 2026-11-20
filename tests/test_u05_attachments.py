"""Positive attachment extent, local admission, foreign context and cache guards."""
import copy
import pytest
from shapely import to_wkb,from_wkb
from shapely.geometry import box,Point,LineString
from src.stage_abi.store import ArtifactStore
from src.u05_board.coverage import CoverageAdapter
from src.u05_board.junctions import parameters
from src.u05_board.attachment_export import obligation_check

def fixture(tmp_path, *, max_seconds=120):
    from src.u05_board.store import OverlayStore
    old=ArtifactStore(tmp_path/'old');store=OverlayStore(tmp_path/'runtime',old.root);rows=[]
    def add(sid,kind,g,**metadata):
        ref=store.put('geometry',to_wkb(g));rows.append(dict(source_id=sid,kind=kind,geometry_ref=ref,original_ref=ref,metadata=metadata))
    trace=LineString([(-.6,0),(.6,0)]).buffer(.025,quad_segs=64)
    add('physical','fixed_source',trace,native_source_ids=['physical'])
    for sid,x in [('left',-.6),('right',.6)]:add(sid,'circle',Point(x,0).buffer(.2,quad_segs=64),qualified_land=True,alias_source_ids=[sid])
    attachments=[dict(id='J:attachment:'+str(i),land_id=l,reference_land_id=l,required_reference=True) for i,l in enumerate(['left','right'])]
    add('view','trace',trace,native_route_ref={'qualified':True},reference_source_ids=['physical'],land_ids=['left','right'],attachments=attachments,reference_id='J',reference_status='GROWN')
    scene=dict(source_sha256='a'*64,frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=[-3,-3,3,3],objects=rows,lineage=[],findings=[],acceptance={'owner':'PENDING_USER'})
    adapter=CoverageAdapter(box(-2,-2,2,2));policy=dict(stage='t05',parameters=parameters());bounds=dict(max_source_objects=20,max_targets=2,max_evaluations=8,max_output_bytes=10000000,max_seconds=max_seconds)
    details=adapter.plan(store,scene,policy,dict(stage='t05',scene_ref=store.put_json('scene',scene),source_ids=['view']),bounds)
    plan=dict(stage='t05',scene_ref=store.put_json('scene',scene),policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details)
    return store,scene,policy,plan,adapter

def test_every_attachment_has_full_exported_extent_not_some_nearby_copper():
    before=box(0,0,1,1);required=box(1,.2,1.2,.8)
    assert obligation_check(required,before,[box(.9,.2,1.2,.8)])['passed']
    for bad in ([box(.9,.2,1.02,.8)],[box(1,2,1.2,3)],[]):
        with pytest.raises(ValueError,match='EXTENT_MISSING'):obligation_check(required,before,bad)
    with pytest.raises(ValueError,match='EXTENT_MISSING'):obligation_check(required,before,[],already=True)
    assert obligation_check(box(.9,.2,1,.8),before,[],already=True)['passed']

@pytest.mark.parametrize("max_seconds", [120, None])
def test_local_t05_views_preserve_complete_land_set_and_treat_both(tmp_path,max_seconds):
    store,scene,policy,plan,a=fixture(tmp_path,max_seconds=max_seconds);assert plan['details']['routes'][0]['land_ids']==['left','right']
    c=a.run(store,scene,policy,plan,lambda _:None)
    assert c['coverage']['grown']==1 and len(c['decisions'][0]['attachment_outcomes'])==2
    assert all(o['status']=='TREATED_VERIFIED' for o in c['decisions'][0]['attachment_outcomes'])
    assert a.verify(store,scene,policy,plan,c,{'scope':'complete-source-and-all-patches'},lambda _:None)['passed']
    bad=copy.deepcopy(c);bad['decisions'][0]['attachment_outcomes'].pop()
    with pytest.raises(ValueError,match='MISSING_TREATMENT'):a.verify(store,scene,policy,plan,bad,{'scope':'complete-source-and-all-patches'},lambda _:None)

def test_new_neighbor_is_physical_obstacle_but_other_views_are_not(tmp_path):
    store,scene,policy,plan,a=fixture(tmp_path);first=a._operands(store,scene,policy,plan['details'],plan['details']['routes'][0]);assert first[3]==[]
    ref=store.put('geometry',to_wkb(box(-.5,.03,-.4,.07)));scene['objects'].append(dict(source_id='new-neighbor',kind='fixed_source',geometry_ref=ref,original_ref=ref,metadata={}))
    foreign=a._operands(store,scene,policy,plan['details'],plan['details']['routes'][0])[3]
    assert [s for s,g in foreign]==['new-neighbor']

def test_bounded_snapshot_rehashes_all_operands_before_advancement(tmp_path):
    store,scene,policy,plan,a=fixture(tmp_path);a._context(store,scene,policy,plan['details'])
    ref=scene['objects'][0]['geometry_ref'];(store.root/'artifacts'/ref['artifact_id']).write_bytes(b'corrupt')
    with pytest.raises(ValueError):a.run(store,scene,policy,plan,lambda _:None)

def test_loaded_execution_rejects_mid_operation_scene_and_policy_mutation(tmp_path):
    for change in ('scene','policy','metadata'):
        store,scene,policy,plan,a=fixture(tmp_path/change)
        def mutate(_):
            if change=='scene':scene['objects'].append(copy.deepcopy(scene['objects'][0]))
            elif change=='policy':policy['parameters']['hard_gap_mm']=.001
            else:scene['objects'][-1]['metadata']['land_ids']=[]
        with pytest.raises(ValueError,match='EXECUTION_INPUT_CHANGED'):a.run(store,scene,policy,plan,mutate)

def test_scope_extension_is_exact_and_applies_only_to_named_cluster(tmp_path):
    store,scene,policy,plan,a=fixture(tmp_path);a.write=box(-.2,-.2,.2,.2);extension=box(.3,.1,.4,.2);a.exceptions={'J':extension}
    assert a.scope({'reference_id':'J'}).covers(extension)
    assert not a.scope({'reference_id':'other'}).intersects(extension)
    assert not a.scope({'reference_id':'J'}).covers(box(.4,.1,.5,.2))

def test_policy_cannot_relax_and_covered_land_is_never_removed(tmp_path):
    store,scene,policy,plan,a=fixture(tmp_path);scene['objects'][0]['geometry_ref']=store.put('geometry',to_wkb(box(-1,-1,1,1)))
    selection=dict(stage='t05',scene_ref=plan['scene_ref'],source_ids=['view'])
    assert a.plan(store,scene,policy,selection,plan['details']['bounds'])['routes'][0]['land_ids']==['left','right']
    policy['parameters']['hard_gap_mm']=.001
    with pytest.raises(ValueError,match='POLICY_OR_BOUNDS'):a.plan(store,scene,policy,selection,plan['details']['bounds'])

def test_stroke_owner_uses_source_primitive_identity_and_existing_bound():
    import sexpdata
    from gerbonara import graphic_objects as go
    from gerbonara.apertures import CircleAperture
    from gerbonara.utils import MM
    from src.u05_board.stroke_owner import primitive_match,stroke_fidelity
    ap=CircleAperture(diameter=.05,unit=MM)
    node=sexpdata.loads('(segment (start 0 0) (end 1 0) (width .05) (layer F.Cu))')
    line=go.Line(0,0,1,0,aperture=ap,unit=MM)
    assert primitive_match(node,line)
    wrong=go.Line(0,0,1,.00001,aperture=ap,unit=MM)
    assert not primitive_match(node,wrong)
    arc_node=sexpdata.loads('(arc (start 1 0) (mid .707106781 .707106781) (end 0 1) (width .05) (layer F.Cu))')
    arc=go.Arc(1,0,0,-1,-1,0,True,aperture=ap,unit=MM)
    assert primitive_match(arc_node,arc)
    assert not primitive_match(arc_node,go.Arc(1,0,0,-1,-.9,0,True,aperture=ap,unit=MM))
    assert not primitive_match(arc_node,go.Arc(1,0,0,-1,-1,0,False,aperture=ap,unit=MM))
    assert stroke_fidelity(box(0,0,1,.05),box(0,0,1,.05001))['tolerance_mm']==.000025
    with pytest.raises(ValueError,match='STROKE_GEOMETRY'):stroke_fidelity(box(0,0,1,.05),box(0,0,1,.05003))

def test_fresh_native_owner_plot_binds_exact_atoms_and_rejects_tampering(tmp_path):
    import sexpdata
    from src.u05_board.owner_plot import create,binding,plot_atom
    from src.u05_board.export import U05DataService
    from src.native_inventory import geometry
    from src.pcb_data_abi import gerber
    from src.crop_circle_sources import verify_assets
    verify_assets()
    body=b'''(kicad_pcb (version 20241229) (generator pcbnew)
    (layers (0 "F.Cu" signal) (31 "B.Cu" signal))
    (segment (start 0 0) (end 1 0) (width .05) (layer "F.Cu") (net 0))
    (arc (start 5.939 -13.495) (mid 6.07286 -13.40494) (end 6.231 -13.373) (width .11989) (layer "F.Cu") (net 0)))'''
    tree=sexpdata.loads(body.decode());s=U05DataService.__new__(U05DataService);s.raw=body;s.out=tmp_path/'data';s.out.mkdir();s.board=s.out/'candidate.kicad_pcb';s.board.write_bytes(body);s.store=ArtifactStore(tmp_path/'runtime');s.rows={};parts={};kinds={};indices=[]
    for i,n in enumerate(tree):
        if not isinstance(n,list) or str(n[0]) not in ('segment','arc'):continue
        sid='source:'+str(i);kind=str(n[0]);ref=s.store.put('geometry',to_wkb(geometry(n,kind)));parts[sid]=ref;kinds[sid]=kind;indices.append(i);s.rows[sid]=dict(kind='fixed_source',metadata=dict(native_node_indices=[i]))
    s.rows['view']=dict(kind='trace',metadata=dict(native_part_refs=parts,native_part_kinds=kinds,native_node_indices=indices))
    result=create(s);(s.out/'pcb_gerber_export.json').write_text(__import__('json').dumps(dict(owner_source_plot=result)))
    proof=binding(s);assert proof['source_nodes']==2 and len(proof['bindings'])==2
    parsed=gerber.parse(s.out/'owner_source_plot/gerbers/board-F_Cu.gbr')
    assert all(plot_atom(parsed.objects[r['isolated_plot_index']])==r['exact_plot_atom'] for r in proof['bindings'].values())
    from src.u05_board.export import require_positive_copper
    require_positive_copper(parsed)
    original=(s.out/'owner_source_plot/gerbers/board-F_Cu.gbr').read_bytes();clear=tmp_path/'clear.gbr';mutated=original.replace(b'%LPD*%',b'%LPC*%',1);assert mutated!=original;clear.write_bytes(mutated);negative=gerber.parse(clear)
    assert negative.file_attrs['.FilePolarity']==('Positive',) and any(not o.polarity_dark for o in negative.objects)
    with pytest.raises(ValueError,match='FCU_CLEAR_POLARITY_UNSUPPORTED'):require_positive_copper(parsed,negative)
    path=s.out/'owner_source_plot/gerbers/board-F_Cu.gbr';path.write_bytes(path.read_bytes().replace(b'%MOMM*%',b'%MOIN*%',1))
    with pytest.raises(ValueError,match='OWNER_SOURCE_PLOT_EVIDENCE_CHANGED'):binding(s)
