#!/usr/bin/env python3
"""Fresh-process full-source verification of saved crop geometry and controls.

No editing constructor, source-scene index or trial runner is imported.
"""
import hashlib,json,math,re,sys
from pathlib import Path
from shapely import from_wkb,to_wkb
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union,nearest_points
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.native_inventory import inventory


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def gh(g):return hashlib.sha256(to_wkb(g,byte_order=1)).hexdigest()
def parts(g):
    if g.is_empty:return []
    return [g] if g.geom_type=='Polygon' else [p for p in getattr(g,'geoms',()) if p.geom_type=='Polygon']
def vertices(g):return [v for p in parts(g) for v in p.exterior.coords]

def audit_diameter_contract(policy,selection,decisions):
    """Independent checks of physical classes, strict caps and source KEEPs."""
    palette=policy['diameter_classes_mm'];assert palette==sorted(set(palette))
    sites={s['source_id']:s for s in selection['sites']}
    choices={sid:[d for d in palette if 2*s['radius']<d<=3*s['radius']] for sid,s in sites.items()}
    for group in selection['groups']:
        common=set(choices[group['site_ids'][0]])
        for sid in group['site_ids'][1:]:common.intersection_update(choices[sid])
        assert group['target_diameter_mm']==(max(common) if common else None)
    for sid,s in sites.items():
        d=decisions[sid];size=selection['size_classes'][sid];radius=d['proposed_radius_mm']
        assert radius==size['proposed_radius_mm'] and s['radius']<=radius<=1.5*s['radius']
        assert abs(radius-d['factor']*s['radius'])<=1e-15
        assert choices[sid]==size['admissible_classes_mm']
        if radius==s['radius']:
            assert size['category_mm'] is None and size['original_keep'] is True
        else:
            assert 2*radius in choices[sid] and size['category_mm']==2*radius and size['original_keep'] is False

def require_square_control(report):
    controls=report['square_disabled_controls']
    assert len(controls)==1 and controls[0]['key']=='S31'
    decisions={d['source_id']:d for d in report['decisions']}
    control=controls[0];d=decisions[control['source_id']]
    assert d['key']=='S31' and d['square_guided'] and len(d['square_recesses'])==1
    assert control['symmetric_difference_mm2']>1e-8

def main(out):
    assert out.resolve().is_relative_to(ROOT/'out')
    r=json.loads((out/'report.json').read_bytes());policy=json.loads((out/'policy.json').read_bytes());selection=json.loads((out/'selection.json').read_bytes())
    assert sha(out/'policy.json')==r['policy_sha256'] and sha(out/'selection.json')==r['selection_sha256']
    expected_policies={'balanced-t01-crop-trial-policy/2':'b7b2063cdeadac5ccb1fe44ab872a596428f7a2caaa7d2dacbcd72c392605f59',
                      'diameter-class-t01-trial-policy/1':'c5605b67986dfb64a7cf1cf8400aa624547231e73145af0ea39e7fa1b9731397'}
    assert r['policy_sha256']==expected_policies[policy['schema']]
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
    if policy['schema']=='diameter-class-t01-trial-policy/1':
        assert len(priority)==25 and len(selection['priority_exceptions'])==1
        exception=selection['priority_exceptions'][0]
        assert exception['reason']=='OWNER_REQUESTED_SQUARE_GUIDED_RECESS'
        assert decisions[exception['source_id']]['key']=='S31' and decisions[exception['source_id']]['square_guided'] is True
        assert len({s['physical_contact_group'] for s in sites.values()})==26
    else:assert len(priority)==26 and not selection['priority_exceptions']
    if policy['schema']=='diameter-class-t01-trial-policy/1':
        audit_diameter_contract(policy,selection,decisions)
        require_square_control(r)
        assert r['diameter_classes_mm']==policy['diameter_classes_mm']
        assert all(d['size_class']==selection['size_classes'][sid] for sid,d in decisions.items())
    else:
        for group in selection['groups']:
            assert len(group['site_ids']) in [1,2] and 1<=group['factor']<=1.5
            for sid in group['site_ids']:assert decisions[sid]['factor']==group['factor']
    geometries={sid:saved[d['geometry']['dynamic']] for sid,d in decisions.items()}
    statics={sid:saved[d['geometry']['static']] for sid,d in decisions.items()}
    core={sid:saved[d['geometry']['core']] for sid,d in decisions.items()}
    for sid,s in sites.items():
        d=decisions[sid];candidate=geometries[sid];radius=d['proposed_radius_mm']
        assert original[sid].equals_exact(core[sid],0)
        assert 1<=d['factor']<=1.5 and abs(radius-d['factor']*s['radius'])<=1e-15 and radius<=1.5*s['radius']
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
    square_controls=[]
    for control in r.get('square_disabled_controls',[]):
        sid=control['source_id'];d=decisions[sid];s=sites[sid]
        assert d['square_guided'] and d['key']=='S31' and sid not in priority
        assert control['input_revision']==d['input_revision']
        prior={item['source_id']:geometries[item['source_id']] for item in ordered[:d['input_revision']]}
        plain=saved[control['disabled_wkb']];delta=plain.symmetric_difference(geometries[sid]).area
        assert delta>1e-8 and abs(delta-control['symmetric_difference_mm2'])<1e-12
        case=audit_one(sid,plain,prior,'square_disabled_same_scene');assert not case['violations']
        envelope=saved[d['geometry']['envelope']];optional=envelope.difference(core[sid]);exclusions={}
        for row in rows:
            canonical=alias.get(row['id'],row['id'])
            if canonical==sid:continue
            shape=prior.get(canonical,original[row['id']])
            if shape.distance(envelope)>.031:continue
            exclusion=shape.buffer(policy['construction_gap'],quad_segs=128)
            if row['id'] in selection['ports'][sid]:exclusion=exclusion.difference(from_wkb(bytes.fromhex(selection['ports'][sid][row['id']])))
            exclusions[canonical]=exclusion
        conflicts=[(optional.intersection(exclusion).area,key,exclusion) for key,exclusion in exclusions.items() if optional.intersection(exclusion).area>policy['event_epsilon']]
        area,neighbor,excluded=sorted(conflicts,key=lambda item:(-item[0],item[1]))[0]
        point=nearest_points(Point(*s['center']),excluded)[1]
        square=saved[d['geometry']['square']];corners=list(square.exterior.coords)[:4]
        sides=[]
        for index,label in [(1,'+X'),(2,'+Y'),(3,'-X'),(0,'-Y')]:
            a,b=corners[index],corners[(index+1)%4];length=math.dist(a,b);normal=((b[1]-a[1])/length,(a[0]-b[0])/length)
            score=normal[0]*(point.x-s['center'][0])+normal[1]*(point.y-s['center'][1])
            sides.append((score,label,a,b,normal))
        score,label,a,b,normal=max(enumerate(sides),key=lambda item:(item[1][0],-item[0]))[1]
        recess=d['square_recesses'];assert len(recess)==1 and recess[0]['source_id']==neighbor and recess[0]['square_side']==label
        assert abs(recess[0]['conflict_area_mm2']-area)<1e-12
        assert math.dist(recess[0]['direction_point_mm'],(point.x,point.y))<1e-12
        # Independent supporting half-plane for the selected enlarged-square side.
        mx,my=(a[0]+b[0])/2,(a[1]+b[1])/2;nx,ny=normal;tx,ty=-ny,nx
        margin=max(envelope.bounds[2]-envelope.bounds[0],envelope.bounds[3]-envelope.bounds[1],1.)
        p1=(mx+margin*tx,my+margin*ty);p2=(mx-margin*tx,my-margin*ty)
        half=Polygon([p1,p2,(p2[0]+2*margin*nx,p2[1]+2*margin*ny),(p1[0]+2*margin*nx,p1[1]+2*margin*ny)])
        assert abs(optional.intersection(half).area-recess[0]['removed_optional_area_mm2'])<1e-12
        forbidden=unary_union(list(exclusions.values()))
        def attached(g):return unary_union([core[sid],*[part for part in parts(g) if part.area>1e-10 and part.distance(core[sid])<=1e-9]])
        expected=attached(optional.difference(half).difference(forbidden))
        expected_plain=attached(optional.difference(forbidden))
        assert expected.symmetric_difference(geometries[sid]).area<=1e-10
        assert expected_plain.symmetric_difference(plain).area<=1e-10
        square_controls.append({'source_id':sid,'square_side':label,'verified_changed_area_mm2':delta,'control_gap_check':case})
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
        'coverage':{'unique_sites':51,'occurrences':53,'full_source_fcu_records':17849,'priority_sites':len(priority)},
        'priority_exceptions':selection['priority_exceptions'],
        'dynamic_cases':dynamic_cases,'static_comparator_cases':static_cases,'counterfactual_cases':event_cases,
        'square_disabled_controls':square_controls,
        'static_comparator_violating_sites':sum(bool(c['violations']) for c in static_cases),
        'verified_earlier_neighbor_response_sites':r['actual_adapted_later_sites'],
        'reservation_response_sites':r['reservation_response_later_sites'],
        'actual_adapted_later_sites':evolving_sites,'required_actual_sites':3,
        'dynamic_causality_criterion':'EVIDENCED_LOCALLY' if evolving_sites>=3 else 'NOT_MET',
        'owner_acceptance':'PENDING_USER_FULL_CROP_REVIEW','t01_overall':'PARTIAL_PENDING_OWNER_REVIEW' if evolving_sites>=3 else 'PARTIAL_INSUFFICIENT_ACTUAL_DYNAMIC_EVENTS'}
    (out/'fresh_audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'dynamic_causality_criterion':result['dynamic_causality_criterion'],'evolving_companion_sites':evolving_sites,'reservation_response_sites':r['reservation_response_later_sites'],'static_violating_sites':result['static_comparator_violating_sites']},indent=2))

if __name__=='__main__':main(Path(sys.argv[1]))
