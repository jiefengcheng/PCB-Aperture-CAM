"""Isolated retained-prefix qualification; never executes the old T04 search."""
import argparse,json,os,resource,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.gerber_u05 import pipeline as p
from src.t04_settings import capture_job,read_snapshot,SNAPSHOT_NAME
from src.gerber_u05.ladder_width import run as ladder

GROUPS={'central7':['JR-28fa7f783be6635e','JR-36d793f55c4798de','JR-3f16a59631e44e24','JR-6310a916f1018cc9','JR-86133b5ff9be2c54','JR-e4e592793cb69678','JR-f08de9eea04b7135'],
        'right6':['JR-07fef4f34c60d5ee','JR-452685aa44e769fe','JR-73287fe76604bc1b','JR-86ff9d0595134fce','JR-87019facde3a5adc','JR-8f7b8236c33677aa']}


def prepare(old,job,fresh=None):
    from tools.preflight import verify_manifest
    asset_count=verify_manifest()
    job.mkdir();store=p.Store(job/'runtime');seen=set();inputs={}
    def copy_refs(value,origin=old):
        if isinstance(value,dict):
            if set(value)=={'artifact_id','sha256'}:
                aid=value['artifact_id']
                if aid in seen:return
                blob=(origin/'runtime/artifacts'/aid).read_bytes()
                if p.digest(blob)!=value['sha256']:raise ValueError('RETAINED_INPUT_ARTIFACT_CHANGED:'+aid)
                seen.add(aid);kind=aid.split(':')[0]
                if store.put(kind,blob)!=value:raise ValueError('RETAINED_ARTIFACT_COPY_CHANGED')
                if kind!='geometry':
                    try:decoded=json.loads(blob)
                    except (ValueError,UnicodeError):return
                    copy_refs(decoded,origin)
            else:
                for v in value.values():copy_refs(v,origin)
        elif isinstance(value,list):
            for v in value:copy_refs(v,origin)
    for name in ('source.json','t03.json','input_inventory.json','CLEARANCE_SNAPSHOT.json','REMEDY_POLICY_SNAPSHOT.json'):
        raw=(old/name).read_bytes();inputs[name]=p.digest(raw);(job/name).write_bytes(raw)
        if name in ('source.json','t03.json'):copy_refs(json.loads(raw))
    # Retained PASS receipts remain evidence of the preceding stages only.
    receipts={}
    for stage in ('t01','t03'):
        expected=p.digest((old/(stage+'.json')).read_bytes())
        proofs=[p.load(old/'audits'/stage/(mode+'.json'))for mode in ('construct','1','2')]
        if proofs[0]!=proofs[1]or proofs[0]!=proofs[2]or proofs[0]['status']!='PASS'or proofs[0]['candidate_sha256']!=expected:
            raise ValueError('QUALIFIED_RETAINED_PREFIX_REQUIRED:'+stage)
        receipts[stage]=proofs
    adoption=None
    if fresh is not None:
        import ast
        old_seal=p.load(fresh/'QUALIFICATION_PRODUCER.json')
        # Verify every retained producer byte through its frozen CAS archive.
        for name,h in old_seal['files'].items():
            archived=fresh/'producer_blobs'/h
            if p.digest(archived.read_bytes())!=h:raise ValueError('FRESH_PREFIX_ARCHIVED_PRODUCER_CHANGED')
        roots={Path(n).parents[1]for n in old_seal['files']if n.endswith('/src/component_clearance.py')}
        if len(roots)!=1:raise ValueError('FRESH_PREFIX_SOURCE_ROOT_NOT_UNIQUE')
        previous=next(iter(roots));deltas=[]
        allowed={'src/t04_incremental.py','src/t04_width_fence.py','src/gerber_u05/ladder_width.py','tools/qualify_t04_ladder_bundles.py'}
        for name,h in old_seal['files'].items():
            relative=Path(name).relative_to(previous).as_posix();now=p.ROOT/relative
            if p.digest(now.read_bytes())==h:continue
            if relative not in allowed:raise ValueError('FRESH_PREFIX_UPSTREAM_DEPENDENCY_CHANGED:'+relative)
            if relative.startswith('tools/'):
                def constructor(raw):
                    return [ast.dump(n,include_attributes=False)for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)and n.name=='fresh_prefix']
                if constructor((fresh/'producer_blobs'/h).read_text())!=constructor(now.read_text()):raise ValueError('FRESH_PREFIX_CONSTRUCTOR_CHANGED')
            if relative=='src/t04_width_fence.py':
                def entry(raw):
                    return [ast.dump(n,include_attributes=False)for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)and n.name=='remedy']
                if entry((fresh/'producer_blobs'/h).read_text())!=entry(now.read_text()):raise ValueError('FRESH_PREFIX_NULL_WIDTH_FENCE_CHANGED')
            deltas.append(dict(path=relative,scope='T04-only or qualification transport; upstream constructor unchanged'))
        proof=p.load(fresh/'FRESH_PREFIX_PROOF.json')
        for name,key in [('FRESH_T01.json','t01_sha256'),('FRESH_T03.json','t03_sha256')]:
            raw=(fresh/name).read_bytes()
            if p.digest(raw)!=proof[key]:raise ValueError('FRESH_PREFIX_OUTCOME_CHANGED')
            (job/name).write_bytes(raw);inputs[name]=p.digest(raw);copy_refs(json.loads(raw),fresh)
        if proof['status']!='PASS'or not proof['pin_separation']['passed']:raise ValueError('FRESH_PREFIX_NOT_QUALIFIED')
        raw=(fresh/'FRESH_PREFIX_PROOF.json').read_bytes();(job/'FRESH_PREFIX_PROOF.json').write_bytes(raw);inputs['FRESH_PREFIX_PROOF.json']=p.digest(raw)
        adoption=dict(source=str(fresh),proof_sha256=p.digest(raw),code_deltas=deltas,
                      scope='Unchanged fresh guarded T01/T03 prefix only; old T04 failure remains failed; no result from old T04 adopted')
    binding=p.load(job/'source.json');(job/'source_snapshot').mkdir()
    (job/'source_snapshot/top.art.gbr').write_bytes(store.get(binding['source_ref'],kind='gerber-source'))
    from src.gerber_u05.pin_policy import capture
    capture(job,p.load(job/'input_inventory.json'));capture_job(job)
    p.save(job/'QUALIFICATION_INPUTS.json',dict(retained_run=str(old),input_sha256=inputs,artifact_count=len(seen),
        groups=GROUPS,preceding_stage_receipts=receipts,fresh_prefix_adoption=adoption,asset_manifest_files=asset_count,
        scope=('Fresh current-guard T01/T03 entry from separately byte-bound prefix'if fresh is not None else'Retained T03 entry')+'; thirteen requested routes; every other occurrence fixed. Fresh pin, physical, functional and full final checks. No old T04 result/reservation adopted; no full U05 qualification claim.',
        custody_finding='.DS_Store: prior custody FAIL remains EXPLICIT_UNWAIVED_UNATTRIBUTED'))
    from src.gerber_u05.guard import producer_files
    p.save(job/'QUALIFICATION_PRODUCER.json',dict(files={str(f):p.digest(f.read_bytes())for f in producer_files()},
        inputs={str(job/name):p.digest((job/name).read_bytes())for name in (*inputs,SNAPSHOT_NAME,'PIN_SEPARATION_POLICY.json','QUALIFICATION_INPUTS.json','source_snapshot/top.art.gbr')}))


def verify(job):
    seal=p.load(job/'QUALIFICATION_PRODUCER.json')
    for name,expected in {**seal['files'],**seal['inputs']}.items():
        if p.digest(Path(name).read_bytes())!=expected:raise ValueError('QUALIFICATION_BINDING_CHANGED:'+name)
    from src.gerber_u05.guard import producer_files
    if set(seal['files'])!={str(f)for f in producer_files()}:raise ValueError('QUALIFICATION_PRODUCER_NAMESPACE_CHANGED')


def serialize_occurrence(shape,sid,records,blocks,store):
    """Keep the exact parent vertices until actual partition proof completes.

    Canonical material assembly may drop collinear vertices only AFTER proof.
    Existing parsed-native partition checks require the original parent here.
    """
    from src.gerber_u05 import exporter as export
    from src.gerber_u05.native_assembly import key as material_key
    first=len(records);export.append_regions(shape,'t04-ladder',sid,records,blocks,store)
    identities=list(dict.fromkeys(material_key(r)for r in records[first:]))
    normalized=export.native_grid(shape)
    pieces=[normalized]if normalized.geom_type=='Polygon'else list(normalized.geoms)
    parents=[export.export_reference(piece)[0]for piece in sorted(pieces,key=p.to_wkb)]
    if len(identities)!=len(parents):raise ValueError('NATIVE_PARENT_COVERAGE_CHANGED')
    for identity,reference in zip(identities,parents):
        if p.digest(p.to_wkb(reference))!=identity[2]:raise ValueError('NATIVE_ORIGINAL_PARENT_BINDING_CHANGED')
    return list(zip(identities,parents))


def execute(job,mode):
    p.configure();verify(job)
    from tools.preflight import verify_manifest
    verify_manifest()
    store=p.Store(job/'runtime');binding=p.load(job/'source.json')
    prefix=job/'FRESH_T03.json' if (job/'FRESH_T03.json').exists() else job/'t03.json'
    before=store.get_json(p.load(prefix)['output_scene_ref'],kind='scene')
    start=time.monotonic();p.initialize(store,binding)
    from src import component_clearance as cc,pin_separation as pin
    cc.ACTIVE.register_scene(store,before)
    if getattr(cc.ACTIVE,'functional',None)is not None:cc.ACTIVE.functional.register_scene(store,before)
    _,material,_=p.operands(store,before)
    pin_entry=pin.require(p.unary_union(list(material.values())),scope='qualified_retained_t03')
    prepared=time.monotonic();print(json.dumps(dict(mode=mode,status='PREPARED',seconds=prepared-start)),flush=True)
    value=ladder(store,before,route_ids=[s for group in GROUPS.values()for s in group])
    solved=time.monotonic();print(json.dumps(dict(mode=mode,status='LADDER_COMPLETE',seconds=solved-prepared,decisions=value['solution']['decisions'])),flush=True)
    if mode=='construct':p.save(job/'RAW_LADDER.json',value)
    elif p.canonical(value)!=p.canonical(p.load(job/'RAW_LADDER.json')):raise ValueError('FRESH_COMPLETE_LADDER_RECONSTRUCTION_CHANGED')
    from src.gerber_u05.component_finish import finish
    scene=store.get_json(value['output_scene_ref'],kind='scene')
    completed=finish(store,scene,binding,'t04',mode=mode)
    after=store.get_json(completed['output_scene_ref'],kind='scene');_,after_material,_=p.operands(store,after)
    cc.ACTIVE.register_scene(store,after)
    complete_physical=cc.ACTIVE.complete_clearance(after_material,p.CONSTRUCTION_GAP_MM)
    if not complete_physical['passed']:raise ValueError('T04_POST_SMOOTHING_COMPLETE_PHYSICAL_CLEARANCE_FAILED')
    from src.t04_width_fence import require
    width_check=require(p.unary_union(list(after_material.values())),scope='post_smoothing')
    pin_final=pin.require(p.unary_union(list(after_material.values())),scope='post_smoothing')
    result=dict(raw=value,completion=completed,pin_stage_entry=pin_entry,pin_final=pin_final,width_decisions=width_check,complete_physical=complete_physical)
    if mode=='construct':p.save(job/'RESULT.json',result)
    elif p.canonical(result)!=p.canonical(p.load(job/'RESULT.json')):raise ValueError('FRESH_SMOOTHING_RECONSTRUCTION_CHANGED')
    from src.gerber_u05 import exporter as export
    raw=store.get(binding['source_ref'],kind='gerber-source');base,prefix=export.canonical_base(raw);records=[];blocks=[];parents=[]
    source_scene=store.get_json(binding['scene_ref'],kind='scene');source_rows={r['source_id']:r for r in source_scene['objects']}
    for row in after['objects']:
        if row['source_id']in source_rows and row['geometry_ref']==source_rows[row['source_id']]['geometry_ref']:continue
        parents.extend(serialize_occurrence(p.geometry(store,row['geometry_ref']),row['source_id'],records,blocks,store))
    body=(base+'\n'+''.join(blocks)+'M02*\n').encode('ascii');parsed=export.parse(body)
    original,_,_=p.source_profile.parse_source(raw);n=len(original.objects)
    if len(parsed.objects)!=n+len(records):raise ValueError('ACTUAL_EXPORT_OCCURRENCE_COUNT_CHANGED')
    if not body.startswith((base+'\n').encode('ascii')):raise ValueError('ACTUAL_SOURCE_PREFIX_CHANGED')
    for a,b in zip(original.objects,parsed.objects[:n]):
        ga,_=p.source_profile.object_geometry(a);gb,_=p.source_profile.object_geometry(b)
        if type(a)!=type(b)or a.polarity_dark!=b.polarity_dark or ga.hausdorff_distance(gb)>1e-8 or ga.symmetric_difference(gb).area>2*ga.length*1e-8:raise ValueError('ORIGINAL_PLOTTING_ATOM_CHANGED')
    decoded=[];fidelity=[]
    for obj,record in zip(parsed.objects[n:],records):
        if not obj.polarity_dark or not isinstance(obj,p.go.Region):raise ValueError('ACTUAL_APPEND_POLARITY_OR_ROLE_CHANGED')
        g,_=p.source_profile.object_geometry(obj);g=p.affine_scale(g,1,-1,origin=(0,0))
        fidelity.append(export.fidelity(p.geometry(store,record['geometry_ref']),g));decoded.append(g)
    welded,material_proof=export.weld_native_material(records,decoded,parents,grid_mm=.000001)
    observed={}
    for (_,sid,_),shape in welded:observed.setdefault(sid,[]).append(shape)
    from src.gerber_u05.native_component_checks_final import project_groups,decoded_groups,clearance,final_inventory
    source=cc.ACTIVE.index.source;actual=decoded_groups(source,observed);before_owned=project_groups(material)
    native_clearance=clearance(before_owned,actual);topology=final_inventory(source,actual)
    whole=p.unary_union(list(actual.values()));native_pin=pin.require(whole,scope='actual_reparsed_gerber');native_width=require(whole,scope='actual_reparsed_gerber')
    native=dict(status='PASS',generated_sha256=p.digest(body),source_prefix_preserved=True,positive_appended_regions=len(records),
                contour_fidelity=fidelity,exact_native_material=material_proof,topology=topology,clearance=native_clearance,pin_separation=native_pin,width_decisions=native_width)
    if mode=='construct':
        (job/'top.art.gbr').write_bytes(body);p.save(job/'NATIVE.json',native);p.save(job/'ENCODING_RECORDS.json',records)
        (job/'BEFORE.wkb').write_bytes(p.to_wkb(p.unary_union(list(material.values()))));(job/'AFTER.wkb').write_bytes(p.to_wkb(whole))
    elif body!=(job/'top.art.gbr').read_bytes()or p.canonical(native)!=p.canonical(p.load(job/'NATIVE.json')):raise ValueError('FRESH_ACTUAL_EXPORT_REPARSE_CHANGED')
    verify(job);end=time.monotonic()
    p.save(job/('PROOF_'+mode+'.json'),dict(status='PASS',result_sha256=p.digest(p.canonical(result)),native_sha256=p.digest(p.canonical(native))))
    p.save(job/('METRICS_'+mode+'.json'),dict(mode=mode,pid=os.getpid(),preparation_seconds=prepared-start,ladder_seconds=solved-prepared,
        smoothing_export_reparse_seconds=end-solved,total_seconds=end-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        scope='Thirteen routes, complete retained T03 scene; not a whole-board T04 or U05 runtime'))
    print(json.dumps(dict(mode=mode,status='PASS',seconds=end-start)),flush=True)


def fresh_prefix(job):
    """Recompute preceding stages without editing or adopting old T04 output."""
    verify(job);store=p.Store(job/'runtime');binding=p.load(job/'source.json');p.initialize(store,binding)
    source=store.get_json(binding['scene_ref'],kind='scene');start=time.monotonic()
    # This is the existing canonical allocation and guarded finite-copper T01
    # constructor, including pin and functional guards; no new T01 algorithm.
    t01=p.legacy_run_t01(store,source,binding)
    after=store.get_json(t01['output_scene_ref'],kind='scene')
    t03=p.run_t03(store,after,binding,t01)
    from src import pin_separation as pin
    _,current,_=p.operands(store,after);proof=pin.require(p.unary_union(list(current.values())),scope='fresh_guarded_t03')
    p.save(job/'FRESH_T01.json',t01);p.save(job/'FRESH_T03.json',t03)
    p.save(job/'FRESH_PREFIX_PROOF.json',dict(status='PASS',t01_sha256=p.digest(p.canonical(t01)),t03_sha256=p.digest(p.canonical(t03)),pin_separation=proof,seconds=time.monotonic()-start,
        scope='Fresh existing canonical guarded T01, fresh complete T03. Original retained prefix remains unchanged and rejected under current pin checks. No T04 or T05 executed.'))
    verify(job);print(json.dumps(dict(status='FRESH_PREFIX_PASS',seconds=time.monotonic()-start)),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','prefix','construct','1','2']);parser.add_argument('--job',type=Path,required=True);parser.add_argument('--retained',type=Path);parser.add_argument('--fresh-prefix',type=Path);args=parser.parse_args()
    p.configure()
    if args.action=='prepare':prepare(args.retained,args.job,args.fresh_prefix)
    elif args.action=='prefix':fresh_prefix(args.job)
    else:execute(args.job,args.action)
if __name__=='__main__':main()
