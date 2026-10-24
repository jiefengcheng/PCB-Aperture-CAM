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

def require_square_control(report, required_keys=('S31',)):
    controls=report['square_disabled_controls'];assert len(controls)==len(required_keys)
    assert {control['key'] for control in controls}==set(required_keys)
    decisions={d['source_id']:d for d in report['decisions']}
    for control in controls:
        d=decisions[control['source_id']]
        assert d['key']==control['key'] and d['square_guided'] and len(d['square_recesses'])==1
        assert control['symmetric_difference_mm2']>1e-8

def main(out):
    assert out.resolve().is_relative_to(ROOT/'out')
    r=json.loads((out/'report.json').read_bytes());policy=json.loads((out/'policy.json').read_bytes());selection=json.loads((out/'selection.json').read_bytes())
    assert sha(out/'policy.json')==r['policy_sha256'] and sha(out/'selection.json')==r['selection_sha256']
    expected_policies={'balanced-t01-crop-trial-policy/2':'b7b2063cdeadac5ccb1fe44ab872a596428f7a2caaa7d2dacbcd72c392605f59',
                      'diameter-class-t01-trial-policy/1':'c5605b67986dfb64a7cf1cf8400aa624547231e73145af0ea39e7fa1b9731397',
                      'diameter-class-t01-trial-policy/2':'b74681cec401ba54ca2e92fc0dc6d265a1373d21892be0e200993f7ca44d47be',
                      'diameter-class-t01-trial-policy/3':'1b084cb2366a08e356841ebe5b8890248ba0f75656280e174dee23af1f1fcf5f'}
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
    if policy['schema'].startswith('diameter-class-t01-trial-policy/'):
        expected_exceptions=set(policy['square_guided_sites'])
        assert len(priority)==26-len(expected_exceptions) and len(selection['priority_exceptions'])==len(expected_exceptions)
        assert {decisions[e['source_id']]['key'] for e in selection['priority_exceptions']}==expected_exceptions
        for exception in selection['priority_exceptions']:
            assert exception['reason']=='OWNER_REQUESTED_SQUARE_GUIDED_RECESS'
            assert decisions[exception['source_id']]['square_guided'] is True
        assert len({s['physical_contact_group'] for s in sites.values()})==26
    else:assert len(priority)==26 and not selection['priority_exceptions']
    if policy['schema'].startswith('diameter-class-t01-trial-policy/'):
        audit_diameter_contract(policy,selection,decisions)
        require_square_control(r,policy['square_guided_sites'])
        assert r['diameter_classes_mm']==policy['diameter_classes_mm']
        assert all(d['size_class']==selection['size_classes'][sid] for sid,d in decisions.items())
    else:
        for group in selection['groups']:
            assert len(group['site_ids']) in [1,2] and 1<=group['factor']<=1.5
            for sid in group['site_ids']:assert decisions[sid]['factor']==group['factor']
    geometries={sid:saved[d['geometry']['dynamic']] for sid,d in decisions.items()}
    statics={sid:saved[d['geometry']['static']] for sid,d in decisions.items()}
    core={sid:saved[d['geometry']['core']] for sid,d in decisions.items()}
    owner_checks=[]
    if policy.get('owner_review_application'):
        previous_dir=ROOT/policy['previous_bundle'];undo_dir=ROOT/policy['undo_reference_bundle']
        assert sha(previous_dir/'report.json')==policy['previous_report_sha256']
        assert sha(undo_dir/'report.json')==policy['undo_reference_report_sha256']
        assert sha(out/'owner_annotations.json')==policy['owner_feedback_sha256']
        previous=json.loads((previous_dir/'report.json').read_bytes());undo=json.loads((undo_dir/'report.json').read_bytes())
        previous_keys={item['key']:item for item in previous['decisions']};undo_keys={item['key']:item for item in undo['decisions']}
        for sid,d in decisions.items():
            key=d['key'];old=previous_keys[key];assert sid==old['source_id']
            if key in policy['undo_sites']:
                reference=undo_keys[key];path=undo_dir/reference['geometry']['dynamic']
                assert sha(path)==undo['geometry_sha256'][reference['geometry']['dynamic'][:-4]]
                assert sid==reference['source_id'] and d['proposed_radius_mm']==reference['proposed_radius_mm']
                assert geometries[sid].equals_exact(from_wkb(path.read_bytes()),0)
                assert d['priority'] is True
                owner_checks.append({'key':key,'status':'EXACT_PRE_PROMOTION_CONTOUR_RESTORED','diameter_mm':2*d['proposed_radius_mm'],'reference_report_sha256':policy['undo_reference_report_sha256']})
            elif key in policy['square_recess_neighbors']:
                neighbor_key=policy['square_recess_neighbors'][key]
                neighbor=next(item['source_id'] for item in decisions.values() if item['key']==neighbor_key)
                assert d['proposed_radius_mm']>old['proposed_radius_mm'] and d['square_guided'] and not d['priority']
                assert len(d['square_recesses'])==1 and d['square_recesses'][0]['source_id']==neighbor
                owner_checks.append({'key':key,'status':'LARGER_ENVELOPE_AND_REQUESTED_NEIGHBOR_RECESS','neighbor_key':neighbor_key,'diameter_mm':2*d['proposed_radius_mm']})
            else:assert d['proposed_radius_mm']==old['proposed_radius_mm'],'UNAUTHORIZED_TARGET_RADIUS_CHANGE'
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
                unexempted_contact=addition.intersection(shape).difference(port).area
                if unexempted_contact>1e-10:violations.append({'source_id':canonical,'intrusion_mm2':unexempted_contact,'reason':'NEW_CONTACT_OUTSIDE_FIXED_PORT'})
            else:minimum=min(minimum,addition.distance(shape))
            forbidden=shape.buffer(.020,quad_segs=128)
            if port is not None:forbidden=forbidden.difference(port)
            intrusion=addition.intersection(forbidden).area
            if intrusion>1e-10:violations.append({'source_id':canonical,'intrusion_mm2':intrusion})
        return {'source_id':sid,'kind':kind,'full_source_records_scanned':len(rows),'gap_status':'PASS' if not violations else 'FAIL','violations':violations,'ports':port_count,'relevant_objects':relevant,'minimum_unexempted_gap_within_031_band_mm':minimum if math.isfinite(minimum) else None}
    round_controls=[]
    if policy.get('round_promotion'):
        assert all(next(d for d in decisions.values() if d['key']==key)['priority'] for key in policy['marked_sites'])
        assert all(not next(d for d in decisions.values() if d['key']==key)['square_guided'] for key in policy['marked_sites'])
        round_scene={sid:geometries[sid] for sid in priority}
        for sid in sorted(priority):
            d=decisions[sid];s=sites[sid];size=selection['size_classes'][sid]
            larger=[diameter for diameter in size['admissible_classes_mm'] if 2*d['proposed_radius_mm']<diameter<=size['desired_diameter_mm']]
            opportunity=size['round_opportunity']
            assert opportunity['next_class_diameter_mm']==(min(larger) if larger else None)
            if not larger:continue
            radius=min(larger)/2;assert radius<=1.5*s['radius']
            next_circle=unary_union([core[sid],Point(*s['center']).buffer(radius,quad_segs=128)])
            # The proposed radius differs from the selected envelope: check it
            # against the independently built next envelope, not audit_one's
            # selected-envelope containment predicate.
            saved_envelope=saved[d['geometry']['envelope']]
            saved[d['geometry']['envelope']]=next_circle
            try:
                source_case=audit_one(sid,next_circle,{},'rejected_next_round_class_source')
                reserved_case=audit_one(sid,next_circle,round_scene,'rejected_next_round_class_with_reservations')
            finally:saved[d['geometry']['envelope']]=saved_envelope
            round_pairs=[];square_pairs=[]
            for other in priority:
                if other==sid:continue
                gap=math.dist(s['center'],sites[other]['center'])-radius-decisions[other]['proposed_radius_mm']
                if gap<policy['construction_gap']+policy['safety']:round_pairs.append({'source_id':other,'gap_mm':gap})
            for group in selection['groups']:
                if len(group['site_ids'])!=2:continue
                aid,bid=group['square_anchor_id'],group['square_follower_id']
                if sid not in (aid,bid):continue
                a,b=sites[aid],sites[bid];ra=radius if aid==sid else decisions[aid]['proposed_radius_mm'];rb=radius if bid==sid else decisions[bid]['proposed_radius_mm']
                h=ra/math.sqrt(2);theta=math.radians(policy['orientation']);cx,cy=a['center']
                corners=[(cx+x*math.cos(theta)-y*math.sin(theta),cy+x*math.sin(theta)+y*math.cos(theta)) for x,y in [(-h,-h),(h,-h),(h,h),(-h,h)]]
                normals=[]
                for index in [1,2,3,0]:
                    v,w=corners[index],corners[(index+1)%4];length=math.dist(v,w);n=((w[1]-v[1])/length,(v[0]-w[0])/length)
                    normals.append(sum(n[j]*(b['center'][j]-a['center'][j]) for j in range(2)))
                bound=max(normals)-policy['construction_gap']-policy['safety']-ra/math.sqrt(2)
                if rb>max(b['radius'],bound):square_pairs.append({'group_id':group['group_id'],'follower_source_id':bid,'radius_bound_mm':bound})
            assert source_case['violations'] or round_pairs or square_pairs,'FREE_FULL_ROUND_CLASS_REMAINS'
            # Save the rejected hypothesis and its actual hard-gap intrusion.
            source_ids={v['source_id'] for v in reserved_case['violations']}
            blockers=unary_union([round_scene.get(alias.get(row['id'],row['id']),original[row['id']]) for row in rows if alias.get(row['id'],row['id']) in source_ids])
            forbidden=[]
            for row in rows:
                canonical=alias.get(row['id'],row['id'])
                if canonical not in source_ids:continue
                band=round_scene.get(canonical,original[row['id']]).buffer(.020,quad_segs=128)
                if row['id'] in selection['ports'][sid]:band=band.difference(from_wkb(bytes.fromhex(selection['ports'][sid][row['id']])))
                forbidden.append(band)
            intrusion=next_circle.difference(core[sid]).intersection(unary_union(forbidden))
            diagnostics={}
            for label,geometry in [('circle',next_circle),('blockers',blockers),('intrusion',intrusion)]:
                path=out/'round_diagnostics'/(d['key']+'_'+label+'.wkb');path.parent.mkdir(exist_ok=True);path.write_bytes(to_wkb(geometry,byte_order=1))
                diagnostics[label]={'path':str(path.relative_to(out)),'sha256':sha(path)}
            round_controls.append({'key':d['key'],'source_id':sid,'diameter_mm':2*radius,'source_case':source_case,'reservation_case':reserved_case,'round_blockers':round_pairs,'square_blockers':square_pairs,'geometry':diagnostics})
    dynamic_cases=[audit_one(sid,geometries[sid],geometries,'dynamic_assembled') for sid in decisions]
    static_cases=[audit_one(sid,statics[sid],statics,'static_assembled_comparator') for sid in decisions]
    assert all(not c['violations'] for c in dynamic_cases),'ASSEMBLED_DYNAMIC_GAP_FAILURE'
    event_cases=[]
    ordered=r['decisions']
    square_controls=[]
    for control in r.get('square_disabled_controls',[]):
        sid=control['source_id'];d=decisions[sid];s=sites[sid]
        assert d['square_guided'] and d['key'] in policy['square_guided_sites'] and sid not in priority
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
        preferred_key=policy.get('square_recess_neighbors',{}).get(d['key'])
        if preferred_key:
            preferred=next(item['source_id'] for item in r['decisions'] if item['key']==preferred_key)
            conflicts=[item for item in conflicts if item[1]==preferred]
            assert conflicts,'REQUIRED_OWNER_RECESS_NEIGHBOR_NOT_IN_CONFLICT'
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
        'owner_review_checks':owner_checks,
        'dynamic_cases':dynamic_cases,'static_comparator_cases':static_cases,'counterfactual_cases':event_cases,
        'square_disabled_controls':square_controls,
        'round_next_class_controls':round_controls,
        'static_comparator_violating_sites':sum(bool(c['violations']) for c in static_cases),
        'verified_earlier_neighbor_response_sites':r['actual_adapted_later_sites'],
        'reservation_response_sites':r['reservation_response_later_sites'],
        'actual_adapted_later_sites':evolving_sites,'required_actual_sites':3,
        'dynamic_causality_criterion':'EVIDENCED_LOCALLY' if evolving_sites>=3 else 'NOT_MET',
        'owner_acceptance':'PENDING_USER_FULL_CROP_REVIEW','t01_overall':'PARTIAL_PENDING_OWNER_REVIEW' if evolving_sites>=3 else 'PARTIAL_INSUFFICIENT_ACTUAL_DYNAMIC_EVENTS'}
    (out/'fresh_audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'dynamic_causality_criterion':result['dynamic_causality_criterion'],'evolving_companion_sites':evolving_sites,'reservation_response_sites':r['reservation_response_later_sites'],'static_violating_sites':result['static_comparator_violating_sites']},indent=2))

if __name__=='__main__':main(Path(sys.argv[1]))
