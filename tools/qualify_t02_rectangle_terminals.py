"""Bounded real-source T02 qualification; never a full U05/release verdict.

Retain the prior T03 copper exactly, rebuild source classification, and exercise
the marked rectangles with fresh T02 checks. T04 admission is inventoried;
no prior T04/T02/T05 growth is adopted. Export/reparse is checked separately.
"""
import argparse,copy,json,os,resource,time
from pathlib import Path
from shapely.ops import unary_union
from src.gerber_u05 import pipeline as p

TARGET_SPANS=('118642:118654','101374:101386','113610:113622',
              '101474:101486','113678:113690','113508:113520',
              '113542:113554','118042:118054','118141:118152',
              '120433:120452','106691:106702')

def seal(job):
    from src.gerber_u05.guard import producer_files
    p.save(job/'PRODUCER.json',dict(files={str(f):p.digest(f.read_bytes())for f in producer_files()},
                                  inputs={n:p.digest((job/n).read_bytes())for n in
                                          ('source.json','ENTRY.json','SCOPE.json','PIN_SEPARATION_POLICY.json','SOURCE_ASSEMBLY_BINDING.json')}))


def verify(job):
    proof=p.load(job/'PRODUCER.json')
    for name,expected in proof['files'].items():
        if p.digest(Path(name).read_bytes())!=expected:raise ValueError('QUALIFICATION_PRODUCER_CHANGED:'+name)
    for name,expected in proof['inputs'].items():
        if p.digest((job/name).read_bytes())!=expected:raise ValueError('QUALIFICATION_INPUT_CHANGED:'+name)


def prepare(job,old):
    from tools.preflight import verify_manifest
    assets=verify_manifest();job.mkdir(exist_ok=False);store=p.Store(job/'runtime')
    raw=(old/'source_snapshot/top.art.gbr').read_bytes();binding=p.build_source(store,raw)
    previous=p.load(old/'source.json');prior=p.load(old/'t03.json')
    def copy_ref(ref):
        blob=(old/'runtime/artifacts'/ref['artifact_id']).read_bytes()
        if p.digest(blob)!=ref['sha256']:raise ValueError('RETAINED_ARTIFACT_CHANGED')
        if store.put(ref['artifact_id'].split(':')[0],blob)!=ref:raise ValueError('COPIED_ARTIFACT_CHANGED')
    def refs(value):
        if isinstance(value,dict):
            if set(value)=={'artifact_id','sha256'}:copy_ref(value)
            else:
                for v in value.values():refs(v)
        elif isinstance(value,list):
            for v in value:refs(v)
    refs(previous['scene_ref']);refs(prior['output_scene_ref'])
    old_source=store.get_json(previous['scene_ref'],kind='scene');entry=store.get_json(prior['output_scene_ref'],kind='scene');refs(entry)
    new=store.get_json(binding['scene_ref'],kind='scene');old_rows={r['source_id']:r for r in old_source['objects']}
    current={r['source_id']:r for r in entry['objects']}
    if set(current)!=set(old_rows)or set(current)!={r['source_id']for r in new['objects']}:raise ValueError('COMPLETE_SOURCE_INVENTORY_CHANGED')
    admitted=[];new_entry=copy.deepcopy(new)
    for row in new_entry['objects']:
        sid=row['source_id'];old_row=old_rows[sid]
        if row['original_ref']!=old_row['original_ref']:raise ValueError('ORIGINAL_SOURCE_COPPER_CHANGED')
        row['geometry_ref']=current[sid]['geometry_ref']
        if row['metadata'].get('rectangle_terminal'):admitted.append(sid)
    # Classification is changed before T04; retained native copper is unchanged.
    # This is an explicit retained prefix, not a fresh current-T01 qualification.
    new_entry['lineage']=copy.deepcopy(entry['lineage'])
    new_entry['lineage'].append(dict(stage='t02-terminal-isolated-entry',retained_geometry='EXACT_T03_OCCURRENCE_REFERENCES',retained_source=str(old)))
    if any(r['geometry_ref']!=current[r['source_id']]['geometry_ref']for r in new_entry['objects']):raise ValueError('PRECEDING_STAGE_GEOMETRY_CHANGED')
    p.save(job/'source.json',binding);p.save(job/'ENTRY.json',store.put_json('scene',new_entry))
    for name in ('PIN_SEPARATION_POLICY.json','SOURCE_ASSEMBLY_BINDING.json'):
        (job/name).write_bytes((old/name).read_bytes())
    targets=[r['source_id']for r in new['objects']if r['source_id'].split(':bytes:')[-1]in TARGET_SPANS]
    if len(targets)!=len(TARGET_SPANS):raise ValueError('MARKED_RECTANGLE_INVENTORY_INCOMPLETE')
    p.save(job/'SCOPE.json',dict(scope='ELEVEN_MARKED_T02_RECTANGLES_WITH_COMPLETE_RETAINED_T03_CONTEXT; NOT_FULL_U05',
        original_job=str(old),source_sha256=p.digest(raw),retained_files={n:p.digest((old/n).read_bytes())for n in ('source.json','t03.json','PIN_SEPARATION_POLICY.json','SOURCE_ASSEMBLY_BINDING.json')},
        new_terminal_ids=sorted(admitted),qualification_target_ids=sorted(targets),assets_verified=assets,
        native_predecessor_occurrences=len(current),preceding_geometry='BYTE_IDENTICAL_RETAINED_T03',
        new_T01_T04_T05='NOT_RUN; isolated T02 qualification only',
        custody_finding='.DS_Store: prior custody FAIL remains EXPLICIT_UNWAIVED_UNATTRIBUTED'))
    seal(job);print(json.dumps(dict(status='PREPARED',new_terminals=len(admitted))),flush=True)


def execute(job,mode):
    verify(job)
    from tools.preflight import verify_manifest
    verify_manifest();start=time.monotonic();store=p.Store(job/'runtime');binding=p.load(job/'source.json')
    entry=store.get_json(p.load(job/'ENTRY.json'),kind='scene')
    # Initialize frozen source owners/pins; no later-stage reservation is reused.
    p.initialize(store,binding)
    from src import component_clearance as cc,pin_separation as pin,source_channel_scope
    _,before,_=p.operands(store,entry)
    pin_before=pin.require(unary_union(list(before.values())),scope='isolated_retained_t03')
    admission=p.width_admission(store,entry);new_ids=set(p.load(job/'SCOPE.json')['new_terminal_ids'])
    trace_members={s for r in admission['paths']for s in r['path']['source_ids']}
    if trace_members&new_ids:raise ValueError('T02_TERMINAL_STILL_IN_T04')
    prepared=time.monotonic();print(json.dumps(dict(mode=mode,status='PREPARED',seconds=prepared-start)),flush=True)
    ids=p.load(job/'SCOPE.json')['qualification_target_ids'];adapter=p.FastRectangleAdapter('t02')
    entry_ref=store.put_json('scene',entry);policy=dict(stage='t02',parameters=p.land_parameters('t02'))
    details=adapter.plan(store,entry,policy,dict(stage='t02',scene_ref=entry_ref,source_ids=ids),p.bounds(entry))
    plan=dict(stage='t02',scene_ref=entry_ref,policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details)
    candidate=adapter.run(store,entry,policy,plan,lambda _:None)
    checked=adapter.verify(store,entry,policy,plan,candidate,dict(scope='complete-source-land-and-inclusive'),lambda _:None)
    if not checked['passed']:raise ValueError('T02_COMPLETE_SELECTED_RECTANGLE_CHECK_FAILED')
    result=dict(output_scene_ref=candidate['output_scene_ref'],candidate=candidate,plan=plan,verification=checked,
                summary=dict(rectangles=len(ids),grown=sum(d['status']=='GROWN'for d in candidate['decisions']),
                             contained_keep=sum(d['status']=='COVERED_SKIP'for d in candidate['decisions']),
                             inclusive=sum(d['status']=='MERGED'for d in candidate['inclusive_candidates'])))
    scene=store.get_json(result['output_scene_ref'],kind='scene')
    _,after,_=p.operands(store,scene);cc.ACTIVE.register_scene(store,scene)
    physical=cc.ACTIVE.complete_clearance(after,p.CONSTRUCTION_GAP_MM)
    if not physical['passed']:raise ValueError('T02_COMPLETE_PHYSICAL_CLEARANCE_FAILED')
    logical=unary_union(list(after.values()));pin_after=pin.require(logical,scope='isolated_t02_complete')
    ids={r['source_id']for r in result['candidate']['decisions']}
    if not set(p.load(job/'SCOPE.json')['qualification_target_ids'])==ids:raise ValueError('MARKED_TERMINAL_T02_COVERAGE_INCOMPLETE')
    proof=dict(result=result,physical=physical,pin_before=pin_before,pin_after=pin_after,
               t04_trace_occurrences=admission['trace_occurrences'],new_terminals_in_T04=0)
    if mode=='construct':p.save(job/'RESULT.json',proof)
    elif p.canonical(proof)!=p.canonical(p.load(job/'RESULT.json')):raise ValueError('FRESH_T02_RECONSTRUCTION_CHANGED')
    solved=time.monotonic();print(json.dumps(dict(mode=mode,status='T02_CHECKED',seconds=solved-prepared,summary=result['summary'])),flush=True)
    from src.gerber_u05 import exporter as export
    from tools.qualify_t04_ladder_bundles import serialize_occurrence
    raw=store.get(binding['source_ref'],kind='gerber-source');base,_=export.canonical_base(raw)
    records=[];blocks=[];parents=[];original_scene=store.get_json(binding['scene_ref'],kind='scene');original_rows={r['source_id']:r for r in original_scene['objects']}
    for row in scene['objects']:
        if row['source_id']in original_rows and row['geometry_ref']==original_rows[row['source_id']]['geometry_ref']:continue
        parents.extend(serialize_occurrence(p.geometry(store,row['geometry_ref']),row['source_id'],records,blocks,store))
    body=(base+'\n'+''.join(blocks)+'M02*\n').encode('ascii');parsed=export.parse(body)
    original,_,_=p.source_profile.parse_source(raw);n=len(original.objects)
    if len(parsed.objects)!=n+len(records):raise ValueError('ACTUAL_EXPORT_OCCURRENCE_COUNT_CHANGED')
    for a,b in zip(original.objects,parsed.objects[:n]):
        ga,_=p.source_profile.object_geometry(a);gb,_=p.source_profile.object_geometry(b)
        if type(a)!=type(b)or a.polarity_dark!=b.polarity_dark or ga.hausdorff_distance(gb)>1e-8 or ga.symmetric_difference(gb).area>2*ga.length*1e-8:raise ValueError('ORIGINAL_PLOTTING_ATOM_CHANGED')
    decoded=[];fidelity=[]
    for obj,record in zip(parsed.objects[n:],records):
        if not obj.polarity_dark or not isinstance(obj,p.go.Region):raise ValueError('ACTUAL_APPEND_POLARITY_CHANGED')
        g,_=p.source_profile.object_geometry(obj);g=p.affine_scale(g,1,-1,origin=(0,0));decoded.append(g)
        fidelity.append(export.fidelity(p.geometry(store,record['geometry_ref']),g))
    welded,material_proof=export.weld_native_material(records,decoded,parents,grid_mm=.000001)
    observed={}
    for (_,sid,_),shape in welded:observed.setdefault(sid,[]).append(shape)
    from src.gerber_u05.native_component_checks_final import project_groups,decoded_groups,clearance,final_inventory
    actual=decoded_groups(cc.ACTIVE.index.source,observed)
    native_clearance=clearance(project_groups(before),actual);topology=final_inventory(cc.ACTIVE.index.source,actual)
    whole=unary_union(list(actual.values()));native_pin=pin.require(whole,finished=True,scope='isolated_actual_reparsed_gerber')
    native=dict(status='PASS',generated_sha256=p.digest(body),original_atoms_preserved=n,contour_fidelity=fidelity,
                material=material_proof,clearance=native_clearance,topology=topology,pin_separation=native_pin)
    if mode=='construct':
        (job/'qualification.top.art.gbr').write_bytes(body);p.save(job/'NATIVE.json',native)
        (job/'BEFORE.wkb').write_bytes(p.to_wkb(unary_union(list(before.values()))));(job/'AFTER.wkb').write_bytes(p.to_wkb(whole))
    elif body!=(job/'qualification.top.art.gbr').read_bytes()or p.canonical(native)!=p.canonical(p.load(job/'NATIVE.json')):raise ValueError('ACTUAL_T02_EXPORT_REPARSE_CHANGED')
    store.verify_reads();verify(job)
    p.save(job/('PROOF_'+mode+'.json'),dict(status='PASS',result_sha256=p.digest(p.canonical(proof)),native_sha256=p.digest(p.canonical(native))))
    p.save(job/('METRICS_'+mode+'.json'),dict(mode=mode,pid=os.getpid(),prepare_seconds=prepared-start,t02_seconds=solved-prepared,total_seconds=time.monotonic()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    print(json.dumps(dict(status='PASS',mode=mode,seconds=time.monotonic()-start)),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','construct','1','2']);parser.add_argument('--job',type=Path,required=True);parser.add_argument('--retained',type=Path);args=parser.parse_args()
    p.configure()
    if not args.job.is_absolute()or not args.job.resolve().is_relative_to(p.configure().resolve()):parser.error('job must be on prepared LaCie workspace')
    if args.action=='prepare':prepare(args.job,args.retained)
    else:execute(args.job,args.action)


if __name__=='__main__':main()
