#!/usr/bin/env python3
"""Fresh-process full-source verification of saved crop geometry and controls.

No editing constructor, source-scene index or trial runner is imported.
"""
import hashlib,json,math,re,sys
from pathlib import Path
from shapely import from_wkb,to_wkb
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.native_inventory import inventory


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def gh(g):return hashlib.sha256(to_wkb(g,byte_order=1)).hexdigest()
def parts(g):
    if g.is_empty:return []
    return [g] if g.geom_type=='Polygon' else [p for p in getattr(g,'geoms',()) if p.geom_type=='Polygon']
def vertices(g):return [v for p in parts(g) for v in p.exterior.coords]

def main(out):
    assert out.resolve().is_relative_to(ROOT/'out')
    r=json.loads((out/'report.json').read_bytes());policy=json.loads((out/'policy.json').read_bytes());selection=json.loads((out/'selection.json').read_bytes())
    assert sha(out/'policy.json')==r['policy_sha256'] and sha(out/'selection.json')==r['selection_sha256']
    assert policy['hard_factor']==1.5 and r['groups']==selection['groups']
    for name,h in r['code_sha256'].items():assert sha(out/'review_source'/name)==h
    source=(ROOT/policy['source']).read_bytes();assert hashlib.sha256(source).hexdigest()==policy['source_sha256']==r['source_sha256']
    inv=inventory(source);rows=[row for row in inv['objects'] if 'F.Cu' in row['layers']];assert len(rows)==17849 and all(row['geometry_sha256'] for row in rows)
    original={row['id']:from_wkb(inv['payloads'][row['geometry_sha256']]) for row in rows}
    saved={}
    for name,h in r['geometry_sha256'].items():assert sha(out/(name+'.wkb'))==h;saved[name+'.wkb']=from_wkb((out/(name+'.wkb')).read_bytes())
    sites={s['source_id']:s for s in selection['sites']};decisions={d['source_id']:d for d in r['decisions']}
    assert len(sites)==len(decisions)==51 and sum(len(s['aliases']) for s in sites.values())==53
    alias={a:sid for sid,s in sites.items() for a in s['aliases']};priority=set(selection['priorities_by_physical_component'].values())
    assert len(priority)==26 and not selection['priority_exceptions']
    for group in selection['groups']:
        assert len(group['site_ids']) in [1,2] and 1<=group['factor']<=1.5
        for sid in group['site_ids']:assert decisions[sid]['factor']==group['factor']
    geometries={sid:saved[d['geometry']['dynamic']] for sid,d in decisions.items()}
    statics={sid:saved[d['geometry']['static']] for sid,d in decisions.items()}
    core={sid:saved[d['geometry']['core']] for sid,d in decisions.items()}
    for sid,s in sites.items():
        d=decisions[sid];candidate=geometries[sid];radius=d['proposed_radius_mm']
        assert original[sid].equals_exact(core[sid],0)
        assert 1<=d['factor']<=1.5 and radius==d['factor']*s['radius'] and radius<=1.5*s['radius']
        assert max(math.dist(s['center'],v) for v in vertices(candidate))<=1.5*s['radius']+1e-12
        if sid in priority:
            assert max(abs(math.dist(s['center'],v)-radius) for v in vertices(candidate))<=.00002
        square=saved[d['geometry']['square']];h=radius/math.sqrt(2);theta=math.radians(-45);cx,cy=s['center']
        expected=[(cx+x*math.cos(theta)-y*math.sin(theta),cy+x*math.sin(theta)+y*math.cos(theta)) for x,y in [(-h,-h),(h,-h),(h,h),(-h,h)]]
        assert all(math.dist(v,e)<=1e-12 for v,e in zip(list(square.exterior.coords)[:4],expected))
    # All original rows are scanned; this independent numeric bounds filter can
    # skip only geometry too distant to affect the .020 hard gap.
    def audit_one(sid,candidate,scene,kind):
        s=sites[sid];d=decisions[sid];base=core[sid];envelope=saved[d['geometry']['envelope']]
        assert candidate.is_valid and not candidate.is_empty
        assert base.difference(candidate).area<=1e-10 and candidate.difference(envelope).area<=1e-10
        addition=candidate.difference(base);assert all(p.distance(base)<=1e-9 for p in parts(addition))
        if addition.is_empty:return {'source_id':sid,'kind':kind,'full_source_records_scanned':0,'full_source_records_available':len(rows),'gap_status':'NOT_APPLICABLE_NO_ADDITION','violations':[],'ports':0}
        ax0,ay0,ax1,ay1=candidate.bounds;violations=[];port_count=0;relevant=0;minimum=math.inf
        for row in rows:
            source_id=row['id'];canonical=alias.get(source_id,source_id)
            if canonical==sid:continue
            shape=scene.get(canonical,original[source_id]);bx0,by0,bx1,by1=shape.bounds
            dx=max(0,ax0-bx1,bx0-ax1);dy=max(0,ay0-by1,by0-ay1)
            if math.hypot(dx,dy)>.031:continue
            if shape.distance(candidate)>.031:continue
            relevant+=1;port=None
            if row['kind'] in ['segment','arc'] and original[source_id].intersects(base.buffer(1e-7,quad_segs=128)):
                width=float(re.search(r'\(\s*width\s+([0-9.]+)\s*\)',source[slice(*row['source_span'])].decode()).group(1))
                port=original[source_id].buffer(max(.005,width/2+.005),quad_segs=128).intersection(base.buffer(.5*s['radius'],quad_segs=128))
                assert port.equals_exact(from_wkb(bytes.fromhex(selection['ports'][sid][source_id])),0)
                port_count+=1
                assert base.intersection(original[source_id]).difference(candidate).area<=1e-10
                assert addition.intersection(shape).difference(port).area<=1e-10
            else:minimum=min(minimum,addition.distance(shape))
            forbidden=shape.buffer(.020,quad_segs=128)
            if port is not None:forbidden=forbidden.difference(port)
            intrusion=addition.intersection(forbidden).area
            if intrusion>1e-10:violations.append({'source_id':canonical,'intrusion_mm2':intrusion})
        return {'source_id':sid,'kind':kind,'full_source_records_scanned':len(rows),'gap_status':'PASS' if not violations else 'FAIL','violations':violations,'ports':port_count,'relevant_objects':relevant,'minimum_unexempted_gap_within_031_band_mm':minimum if math.isfinite(minimum) else None}
    dynamic_cases=[audit_one(sid,geometries[sid],geometries,'dynamic_assembled') for sid in decisions]
    static_cases=[audit_one(sid,statics[sid],statics,'static_assembled_comparator') for sid in decisions]
    assert all(not c['violations'] for c in dynamic_cases),'ASSEMBLED_DYNAMIC_GAP_FAILURE'
    event_cases=[]
    ordered=r['decisions']
    for event in r['events']:
        sid=event['target_source_id'];neighbor=event['neighbor_source_id'];revision=event['input_scene_revision']
        prior={d['source_id']:geometries[d['source_id']] for d in ordered[:revision]}
        assert neighbor in prior
        earlier=saved[event['earlier_copper_wkb']];assert earlier.equals_exact(prior[neighbor],0)
        assert earlier.difference(core[neighbor]).area>1e-8
        cf=saved[event['counterfactual_wkb']];delta=geometries[sid].symmetric_difference(cf).area
        assert delta>1e-8 and abs(delta-event['changed_area_mm2'])<1e-12
        prior[neighbor]=core[neighbor]
        case=audit_one(sid,cf,prior,'single_neighbor_counterfactual');assert not case['violations']
        case['event_id']=event['event_id'];case['changed_area_recomputed_mm2']=delta;event_cases.append(case)
    assert len({e['target_source_id'] for e in r['events']})==r['actual_adapted_later_sites']
    evolving_sites=len({e['target_source_id'] for e in r['events'] if e['neighbor_role']=='earlier accepted companion'})
    assert evolving_sites==r['t01_dynamic_adapted_later_sites']
    assert saved['dynamic_effective.wkb'].difference(saved['original_effective.wkb']).difference(saved['write_domain_caps.wkb']).area<=1e-10
    assert r['same_policy_replay_equal'] is True
    result={'status':'PASS_SCOPED_FRESH_CROP_AUDIT','report_sha256':sha(out/'report.json'),'auditor_sha256':sha(Path(__file__)),
        'scope':'Same-author fresh-process verifier; shared native parser and geometry kernel. No constructor, trial runner, or source-scene spatial index imported.',
        'coverage':{'unique_sites':51,'occurrences':53,'full_source_fcu_records':17849,'priority_sites':26},
        'dynamic_cases':dynamic_cases,'static_comparator_cases':static_cases,'counterfactual_cases':event_cases,
        'static_comparator_violating_sites':sum(bool(c['violations']) for c in static_cases),
        'verified_earlier_neighbor_response_sites':r['actual_adapted_later_sites'],
        'reservation_response_sites':r['reservation_response_later_sites'],
        'actual_adapted_later_sites':evolving_sites,'required_actual_sites':3,
        'dynamic_causality_criterion':'EVIDENCED_LOCALLY' if evolving_sites>=3 else 'NOT_MET',
        'owner_acceptance':'PENDING_USER_FULL_CROP_REVIEW','t01_overall':'PARTIAL_PENDING_OWNER_REVIEW' if evolving_sites>=3 else 'PARTIAL_INSUFFICIENT_ACTUAL_DYNAMIC_EVENTS'}
    (out/'fresh_audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'dynamic_causality_criterion':result['dynamic_causality_criterion'],'actual_sites':r['actual_adapted_later_sites'],'static_violating_sites':result['static_comparator_violating_sites']},indent=2))

if __name__=='__main__':main(Path(sys.argv[1]))
