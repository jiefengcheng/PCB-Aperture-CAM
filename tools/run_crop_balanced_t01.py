#!/usr/bin/env python3
"""Apply the tentatively approved capped/balanced process to the frozen T01 crop."""
import argparse,json,math,platform,shutil,subprocess,sys
from pathlib import Path
from collections import Counter
import shapely
from shapely import to_wkb
from shapely.geometry import Point,box
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src import crop_circle_sources as base
from src.crop_circle_sources import verify_assets
from src.crop_square_neighbor_experiment import inscribed_square,geometry_hash
from src.crop_balanced_t01 import CropSettings,WorkingScene,choose_priorities,local_groups,freeze_factors,execute
sha,dump=base.sha,base.dump
POLICY=ROOT/'contracts/crop_balanced_t01_policy.json'
POLICY_SHA='b7b2063cdeadac5ccb1fe44ab872a596428f7a2caaa7d2dacbcd72c392605f59'
DEFAULT_OUT=ROOT/'out/crop_dynamic_tasks/t01_balanced_capped_20261024'


def save_geometry(out,name,g,hashes):
    path=out/(name+'.wkb');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(to_wkb(g,byte_order=1));hashes[name]=sha(path)
    return name+'.wkb'


def main(out):
    out=out.resolve()
    if not out.is_relative_to(ROOT/'out') or out.exists():raise ValueError('FRESH_PROJECT_OUT_DIRECTORY_REQUIRED')
    assert sha(POLICY)==POLICY_SHA;p=json.loads(POLICY.read_bytes());assets=verify_assets()
    source_path=ROOT/p['source'];assert sha(source_path)==p['source_sha256'];source=source_path.read_bytes()
    out.mkdir(parents=True);shutil.copy2(POLICY,out/'policy.json');dump(out/'asset_integrity.json',assets)
    dump(out/'owner_scope.json',{'approval':'TENTATIVE_APPROVAL_OF_PAIR_PROCESS_ONLY','owner_text':p['owner_tentative_approval'],'balance_choice':p['owner_balance_choice'],'crop_acceptance':'PENDING_USER','hard_factor_ceiling':1.5})
    inv,rows,shapes,tree,sites=base.source_scene(source,p)
    assert len(sites)==51 and sum(len(s['aliases']) for s in sites)==53
    settings=CropSettings(**{key:p[key] for key in ['hard_factor','construction_gap','hard_gap','safety','orientation','qsegs','area_epsilon','event_epsilon']})
    initial=WorkingScene(source,rows,shapes,sites,settings)
    groups=local_groups(sites,p['approved_pair'],settings.construction_gap)
    priorities,exceptions=choose_priorities(sites,initial)
    factors,limits,round_factors=freeze_factors(sites,groups,priorities,initial,settings)
    selection={'source_sha256':sha(source_path),'unique_sites':len(sites),'occurrences':sum(len(s['aliases']) for s in sites),
        'sites':[base.site_record(s) for s in sites],'groups':groups,'priorities_by_physical_component':priorities,
        'priority_exceptions':exceptions,'factor_limits':limits,'source_feasible_priority_factors':round_factors,
        'ports':{sid:{trace:to_wkb(zone,byte_order=1).hex() for trace,zone in ports.items()} for sid,ports in initial.ports.items()}}
    # Freeze identities, groups, factors and component priorities before either scene run.
    dump(out/'selection.json',selection)
    print('Frozen selection:',len(sites),'sites,',len(groups),'local groups,',len(priorities),'round priorities',flush=True)
    dynamic=execute(source,rows,shapes,sites,groups,priorities,settings=settings)
    print('Dynamic construction:',dict(Counter(r['decision'] for r in dynamic['decisions'])),'events:',len(dynamic['events']),flush=True)
    static=execute(source,rows,shapes,sites,groups,priorities,dynamic=False,settings=settings,counterfactuals=False)
    replay=execute(source,rows,shapes,sites,groups,priorities,settings=settings,counterfactuals=False)
    replay_equal=all(geometry_hash(dynamic['scene'].accepted[s['source_id']])==geometry_hash(replay['scene'].accepted[s['source_id']]) for s in sites)
    hashes={};sitekeys={s['source_id']:f'S{i+1:02d}' for i,s in enumerate(sites)}
    for s in sites:
        sid=s['source_id'];key=sitekeys[sid];d=next(r for r in dynamic['decisions'] if r['source_id']==sid)
        for kind,g in [('core',s['core']),('dynamic',dynamic['scene'].accepted[sid]),('static',static['scene'].accepted[sid]),
                       ('envelope',unary_union([s['core'],Point(*s['center']).buffer(d['proposed_radius_mm'],quad_segs=128)])),
                       ('square',inscribed_square(s['center'],d['proposed_radius_mm'],orientation_degrees=-45))]:save_geometry(out,f'geometry/{key}_{kind}',g,hashes)
        d['key']=key;d['geometry']={kind:f'geometry/{key}_{kind}.wkb' for kind in ['core','dynamic','static','envelope','square']}
        d['static_changed_area_mm2']=dynamic['scene'].accepted[sid].symmetric_difference(static['scene'].accepted[sid]).area
    events=[]
    for i,event in enumerate(dynamic['events'],1):
        e={k:v for k,v in event.items() if k not in ['counterfactual','earlier_copper']}
        e['event_id']=f'E{i:03d}'
        e['counterfactual_wkb']=save_geometry(out,f'events/{e["event_id"]}_counterfactual',event['counterfactual'],hashes)
        e['earlier_copper_wkb']=save_geometry(out,f'events/{e["event_id"]}_earlier',event['earlier_copper'],hashes)
        events.append(e)
    failures=[]
    for kind,result in [('dynamic',dynamic),('static',static)]:
        for i,failure in enumerate(result['failed_patches'],1):
            f={k:v for k,v in failure.items() if k!='candidate'};f['run_kind']=kind
            f['candidate_wkb']=save_geometry(out,f'failed/{kind}_{i}',failure['candidate'],hashes);failures.append(f)
    cap_union=unary_union([Point(*s['center']).buffer(1.5*s['radius'],quad_segs=128) for s in sites])
    domain=unary_union([cap_union,box(*p['viewport_mm'])]).buffer(.031,quad_segs=128)
    indexes={int(i) for i in tree.query(domain,predicate='intersects')};target_indexes={i for s in sites for i in s['indexes']}
    context=unary_union([shapes[i] for i in sorted(indexes-target_indexes)])
    original=unary_union([context,*[s['core'] for s in sites]])
    dyn_effective=unary_union([context,*dynamic['scene'].accepted.values()])
    sta_effective=unary_union([context,*static['scene'].accepted.values()])
    for name,g in [('context',context),('original_effective',original),('dynamic_effective',dyn_effective),('static_effective',sta_effective),('write_domain_caps',cap_union),('additions',dyn_effective.difference(original))]:save_geometry(out,name,g,hashes)
    adapted_sites=sorted({e['target_source_id'] for e in events});companion_events=[e for e in events if e['neighbor_role']=='earlier accepted companion']
    counts=dict(Counter(r['decision'] for r in dynamic['decisions']));grown=sum(r['added_area_mm2']>1e-10 for r in dynamic['decisions'])
    report={'schema':'balanced-t01-crop-result/1','status':'CROP_TRIAL_PENDING_FRESH_AUDIT','policy_sha256':POLICY_SHA,'selection_sha256':sha(out/'selection.json'),
        'source_sha256':sha(source_path),'source_fcu_records':len(rows),'unsupported_fcu_records':0,'viewport_mm':p['viewport_mm'],
        'unique_sites':51,'source_occurrences':53,'groups':groups,'priority_count':len(priorities),'priority_exceptions':exceptions,
        'counts':counts,'grown_sites':grown,'unchanged_sites':51-grown,'decisions':dynamic['decisions'],'events':events,
        'actual_adapted_later_sites':len(adapted_sites),'actual_counterfactual_pairs':len(events),'companion_update_counterfactual_pairs':len(companion_events),
        'reservation_response_later_sites':len({e['target_source_id'] for e in events if e['neighbor_role']=='reserved round priority'}),
        't01_dynamic_adapted_later_sites':len({e['target_source_id'] for e in companion_events}),
        'event_credit_rule':'Priority reservations are identical in the fair static comparator. Their counterfactual effects are verified reservation responses, not evidence of accepted-companion evolution beyond that comparator.',
        'target_actual_adapted_sites':3,'failed_patches':failures,'same_policy_replay_equal':replay_equal,
        'static_comparison':{'changed_sites':sum(r['static_changed_area_mm2']>1e-8 for r in dynamic['decisions']),
            'summed_per_site_additions_mm2':sum(r['added_area_mm2'] for r in static['decisions']),
            'effective_added_union_mm2':sta_effective.difference(original).area,'status':'PENDING_ASSEMBLED_COMPARATOR_AUDIT','held_fixed':p['static']},
        'effective_added_union_mm2':dyn_effective.difference(original).area,'summed_per_site_additions_mm2':sum(r['added_area_mm2'] for r in dynamic['decisions']),
        'outside_viewport_added_area_mm2':dyn_effective.difference(original).difference(box(*p['viewport_mm'])).area,
        'scope_write_domain':'union of all complete selected 1.5x cap envelopes; no crop-boundary truncation',
        'geometry_sha256':hashes,'scene_history':dynamic['scene'].history,'static_decisions':static['decisions'],
        'owner_status':'PENDING_FULL_CROP_REVIEW_TENTATIVE_PAIR_APPROVAL_ONLY','technical_status':'PENDING_FRESH_AUDIT',
        'acceptance_status':'PARTIAL_PENDING_GEOMETRY_AND_OWNER_REVIEW','cursor_review':'NOT_RUN: CHANNEL_UNAVAILABLE',
        'runtime':{'python':platform.python_version(),'shapely':shapely.__version__,'geos':shapely.geos_version_string},
        'code_sha256':{name:sha(ROOT/name) for name in ['src/crop_balanced_t01.py','src/crop_balanced_capped_growth.py','src/crop_square_neighbor_experiment.py','src/native_inventory.py','tools/run_crop_balanced_t01.py','tools/audit_crop_balanced_t01.py','tools/render_crop_balanced_t01.py','src/crop_circle_sources.py']}}
    dump(out/'report.json',report)
    for name in report['code_sha256']:
        dest=out/'review_source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
    assert replay_equal and sha(source_path)==p['source_sha256']
    with (out/'fresh_audit.log').open('w') as log:subprocess.run([sys.executable,str(ROOT/'tools/audit_crop_balanced_t01.py'),str(out)],stdout=log,stderr=subprocess.STDOUT,check=True)
    from tools.render_crop_balanced_t01 import publish
    publish(out)
    print(json.dumps({k:report[k] for k in ['grown_sites','unchanged_sites','priority_count','actual_adapted_later_sites','actual_counterfactual_pairs','same_policy_replay_equal']},indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEFAULT_OUT);args=parser.parse_args();main(args.output)
