"""Bound addendum retaining every canonical T01 check and hypothesis geometry."""
import json,sys,os
from pathlib import Path
from . import pipeline as p
from .guard import verify_sources
from src.crop_square_neighbor_experiment import verify_addition

def audit(run):
    verify_sources(run);store=p.Store(run/'runtime');binding=p.load(run/'source.json');scene=store.get_json(binding['scene_ref'],kind='scene');saved=p.load(run/'t01.json')
    p.initialize(store,binding,scene)
    sites=p.t01_sites(store,scene);_,current,_=p.operands(store,scene);rows=binding['width_metadata_rows'];shapes=[current[r['id']]for r in rows];raw=store.get(binding['width_metadata_encoding_ref'],kind='kernel-width-data');spec=p.specification();policy=dict(canonical_t01=p.marker(),family=p.marker()['family'],settings=spec['settings'],diameter_classes_mm=spec['diameter_classes_mm'])
    settings,allocation,targets,square=p.allocate(raw,rows,shapes,sites,policy,dict(reviewed_pairs=[],recess_source_ids=[]))
    guard=p.SurfaceGuard(rows,shapes,sites)
    result=p.execute(raw,rows,shapes,sites,allocation['groups'],allocation['priorities_by_physical_component'],dynamic=True,settings=settings,counterfactuals=True,targets=targets,square_guided_ids=square,surface_guard=guard)
    if p.canonical(allocation)!=p.canonical(saved['allocation'])or p.canonical(result['decisions'])!=p.canonical(saved['decisions']):raise ValueError('T01_SUPPLEMENT_RECONSTRUCTION_CHANGED')
    output=store.get_json(saved['output_scene_ref'],kind='scene');_,after,_=p.operands(store,output)
    for site in sites:
        if p.to_wkb(result['scene'].accepted[site['source_id']])!=p.to_wkb(after[site['source_id']]):raise ValueError('T01_SUPPLEMENT_GEOMETRY_CHANGED')
    for d in result['decisions']:
        if d['priority']and d['proposed_radius_mm']>d['source_radius_mm']and d['decision']!='ROUND_GROW_PRIORITY':raise ValueError('T01_ROUND_ALLOCATION_NOT_CONSTRUCTIBLE')
    if square or any(d['square_guided']for d in result['decisions']):raise ValueError('UNEXPECTED_SOURCE_RECESS_DIRECTIVE')
    events=[]
    for e in result['events']:
        q={k:v for k,v in e.items()if k not in('counterfactual','earlier_copper')}
        for k in('counterfactual','earlier_copper'):q[k+'_ref']=p.geomref(store,e[k])
        events.append(q)
    rejected=[]
    for f in result['failed_patches']:rejected.append(dict({k:v for k,v in f.items()if k!='candidate'},geometry_ref=p.geomref(store,f['candidate'])))
    stripped_events=[{k:v for k,v in e.items()if k not in('counterfactual','earlier_copper')}for e in result['events']]
    stripped_rejected=[{k:v for k,v in f.items()if k!='candidate'}for f in result['failed_patches']]
    if p.canonical(stripped_events)!=p.canonical(saved['events'])or p.canonical(stripped_rejected)!=p.canonical(saved['rejected_hypotheses']):raise ValueError('T01_HYPOTHESIS_RECONSTRUCTION_CHANGED')
    final=[]
    for site in sites:
        sid=site['source_id'];env=p.unary_union([site['core'],p.Point(*site['center']).buffer(targets[sid],quad_segs=settings.qsegs)])
        q=verify_addition(site['core'],after[sid],env,result['scene'].obstacles(site,result['scene'].revision),settings=settings.kernel());final.append(dict(source_id=sid,check=q))
    if any(not r['check']['passed']for r in final):raise ValueError('T01_ASSEMBLED_CLEARANCE_FAILED')
    store.verify_reads();verify_sources(run)
    return dict(status='PASS',source_sha256=binding['source_ref']['sha256'],stage_result_sha256=p.digest((run/'t01.json').read_bytes()),addendum_producer_sha256=p.digest(Path(__file__).read_bytes()),final_assembled_checks=final,events=events,rejected_hypotheses=rejected,construction_surface_limits=guard.records,square_disabled_controls=[],square_controls_applicable=0,scope='No source recess directives; exact positive-round, full final legacy scene, retained counterfactual and rejected geometry checks; same kernel, no independent approval')

if __name__=='__main__':
    p.configure();run=Path(sys.argv[1]);value=audit(run);p.save(run/'audits/t01'/('supplement_'+sys.argv[2]+'.json'),value);print(json.dumps(dict(status='PASS',pid=os.getpid(),proof_sha256=p.digest(p.canonical(value)),final_checks=len(value['final_assembled_checks']),events=len(value['events']),rejections=len(value['rejected_hypotheses']))))
