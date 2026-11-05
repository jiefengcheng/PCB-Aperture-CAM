"""Run the frozen T02 rectangle experiment from ORG + accepted T01 evidence only."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
raise SystemExit('T02_LEGACY_LATENT_GROWTH_ROUTE_RETIRED: contained circles/rectangles must KEEP; use the current T02 adapter. Frozen results remain read-only.')
REGISTRATION=ROOT/'out/crop_dynamic_tasks/t02_crop_registration_20261024'
POLICY_PATH=ROOT/'contracts/crop_rect_t02_policy_v15.json'
INVENTORY_PATH=ROOT/'out/crop_dynamic_tasks/t02_org_inventory_20261025_v16'
OUT=ROOT/'out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v65'
if '--policy' in sys.argv:
    i=sys.argv.index('--policy')
    try: POLICY_PATH=(ROOT/sys.argv[i+1]).resolve()
    except IndexError: raise SystemExit('--policy requires a checkout-relative path')
    del sys.argv[i:i+2]
if '--inventory' in sys.argv:
    i=sys.argv.index('--inventory')
    try: INVENTORY_PATH=(ROOT/sys.argv[i+1]).resolve()
    except IndexError: raise SystemExit('--inventory requires a checkout-relative path')
    del sys.argv[i:i+2]
if '--output' in sys.argv:
    arg_index=sys.argv.index('--output')
    try: OUT=Path(sys.argv[arg_index+1]).resolve()
    except IndexError: raise SystemExit('--output requires a path')
    del sys.argv[arg_index:arg_index+2]
import hashlib,json,platform
from collections import Counter
from shapely import wkb
from shapely.geometry import box,LineString
from shapely.ops import unary_union
from sexpdata import loads
from src.crop_circle_sources import verify_assets
from src.org_edit_target_map import _inventory_side,_row_geometry,_svg_path
from src.native_reference import one
from src.native_inventory import arc_points
from src.crop_rect_t02 import (RectGrowthPolicy,rectangular_feature,execute,limiting_constraints,
                               envelope_constraint_records,
                               validate_accepted_t01_baseline,bind_source_dispositions,
                               physical_component_index,validate_component_preservation,
                               side_trace_copper_region,grow_covered_circles,_scaled_rectangle)
from tools.build_copper_group_review import _mask_keypoints,_fit_translation_from_anchors
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(path,obj):(OUT/path).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
assert verify_assets()['status']=='PASS'
policy_raw=POLICY_PATH.read_bytes();policy_doc=json.loads(policy_raw);policy_hash=sha(policy_raw)
orgpath=ROOT/policy_doc['source']
raw=orgpath.read_bytes();source_hash=sha(raw)
assert source_hash==policy_doc['source_sha256']
report=json.loads((REGISTRATION/'comparison_report.json').read_text())
assert list(report['crop_bounds_org_mm'])==list(policy_doc['crop_bounds_org_mm'])
crop=box(*policy_doc['crop_bounds_org_mm'])
# Bind the selected crop to the exact frozen T01 scene in the owner registry.
decisions=json.loads((ROOT/'contracts/agent_abi/v0_1/owner_decisions.json').read_text())['decisions']
registry=json.loads((ROOT/'contracts/agent_abi/v0_1/registry.json').read_text())['profiles']
owner=decisions['t01_marked_area_fix_freeze_20261025']
profile=registry[owner['profile_id']]
def artifact_bytes(name):
    return (ROOT/profile['artifacts'][name]['path']).read_bytes()
t01_report_bytes=artifact_bytes('report')
t01_policy_bytes=artifact_bytes('policy')
t01_selection_bytes=artifact_bytes('selection')
t01_scene_bytes=(ROOT/profile['scene']['path']).read_bytes()
t01_audit_bytes=artifact_bytes('audit')
t01_receipt_bytes=artifact_bytes('receipt')
t01=json.loads(t01_report_bytes);t01_policy=json.loads(t01_policy_bytes)
selection=json.loads(t01_selection_bytes)
t01_audit=json.loads(t01_audit_bytes);t01_receipt=json.loads(t01_receipt_bytes)
try:
    if owner.get('status')!='ACCEPTED_VISUAL_CROP' or profile.get('claims',{}).get('owner_review')!='ACCEPTED_VISUAL_CROP':
        raise ValueError('T01_OWNER_DECISION_NOT_ACCEPTED')
    if sha(t01_audit_bytes)!=owner.get('audit_sha256') or t01_audit.get('status')!='PASS_FRESH_PROCESS_RETRIEVAL_AND_GEOMETRY_AUDIT':
        raise ValueError('T01_AUDIT_HASH_BINDING_MISMATCH')
    if (sha(t01_report_bytes)!=owner.get('report_sha256') or sha(t01_policy_bytes)!=owner.get('policy_sha256')
            or sha(t01_scene_bytes)!=owner.get('scene_sha256') or sha(t01_selection_bytes)!=owner.get('selection_sha256')):
        raise ValueError('T01_OWNER_ARTIFACT_BINDING_MISMATCH')
    if (t01_receipt.get('decision_id')!=owner['decision_id'] or t01_receipt.get('status')!='ACCEPTED_VISUAL_CROP'
            or t01_receipt.get('artifacts',{}).get('report',{}).get('sha256')!=sha(t01_report_bytes)
            or t01_receipt.get('artifacts',{}).get('audit',{}).get('sha256')!=sha(t01_audit_bytes)
            or t01_receipt.get('artifacts',{}).get('selection',{}).get('sha256')!=sha(t01_selection_bytes)):
        raise ValueError('T01_PUBLICATION_RECEIPT_BINDING_MISMATCH')
    if t01.get('status')!='OWNER_ACCEPTED_VISUAL_CROP' or t01.get('scene_sha256')!=sha(t01_scene_bytes):
        raise ValueError('T01_FROZEN_SCENE_BINDING_MISMATCH')
    if selection.get('source_sha256')!=source_hash:
        raise ValueError('T01_SELECTION_SOURCE_MISMATCH')
    validate_accepted_t01_baseline(
        owner_decision=owner, registry_profile=profile, t01_report=t01,
        t01_policy=t01_policy, target_source_sha256=source_hash,
        target_viewport_mm=report['crop_bounds_org_mm'],
        report_sha256=sha(t01_report_bytes), policy_sha256=sha(t01_policy_bytes),
        scene_sha256=sha(t01_scene_bytes), selection_sha256=sha(t01_selection_bytes),
    )
except ValueError as exc:
    admission={
        'schema':'t02-baseline-admission/1',
        'status':'BLOCKED_ACCEPTED_T01_CROP_COVERAGE',
        'reason':str(exc),
        'source_sha256':source_hash,
        't02_viewport_mm':report['crop_bounds_org_mm'],
        't01_decision_id':owner['decision_id'],
        't01_profile_id':profile['profile_id'],
        't01_scene_sha256':sha(t01_scene_bytes),
        't01_viewport_mm':t01.get('viewport_mm'),
        't01_report_sha256':sha(t01_report_bytes),
        't01_policy_sha256':sha(t01_policy_bytes),
        't01_selection_sha256':sha(t01_selection_bytes),
        't01_audit_sha256':sha(t01_audit_bytes),
        't01_publication_receipt_sha256':sha(t01_receipt_bytes),
        'crop_registration_report_sha256':sha((REGISTRATION/'comparison_report.json').read_bytes()),
        't02_geometry_generation':'NOT_RUN',
        'edit_geometry_read':'NO',
        'historical_t02_outputs':'PRESERVED_UNMODIFIED',
    }
    admission_dir=ROOT/'out/crop_dynamic_tasks/t02_baseline_admission_20261025_v3'
    admission_dir.mkdir(parents=True,exist_ok=True)
    admission_path=admission_dir/'baseline_admission.json'
    encoded=json.dumps(admission,indent=2,sort_keys=True)+'\n'
    if admission_path.exists() and admission_path.read_text()!=encoded:
        raise FileExistsError(f'Refusing to overwrite existing admission evidence: {admission_path}')
    admission_path.write_text(encoded)
    print(json.dumps(admission,indent=2))
    raise SystemExit(2)
if OUT.exists() or not OUT.is_relative_to(ROOT/'out'):
    raise ValueError('FRESH_PROJECT_OUT_DIRECTORY_REQUIRED')
OUT.mkdir(parents=True)
for implementation_path in ['src/crop_rect_t02.py','tools/run_crop_rect_t02.py']:
    stored=OUT/'implementation_sources'/implementation_path
    stored.parent.mkdir(parents=True,exist_ok=True)
    stored.write_bytes((ROOT/implementation_path).read_bytes())
side=_inventory_side(raw,source_hash)
inventory_report=json.loads((INVENTORY_PATH/'inventory_report.json').read_bytes())
inventory_dispositions=json.loads((INVENTORY_PATH/'feature_dispositions.json').read_bytes())
inventory_manifest=(INVENTORY_PATH/'SHA256SUMS.txt').read_bytes()
inventory_hash=sha(inventory_manifest)
if (inventory_report.get('status')!='ORG_RECTANGLE_TARGET_SET_FROZEN'
        or inventory_report.get('source_sha256')!=source_hash
        or inventory_report.get('policy_sha256')!=policy_hash
        or inventory_dispositions.get('target_set_sha256')!=inventory_report.get('candidate_target_ids_sha256')):
    raise ValueError('T02_FROZEN_ORG_INVENTORY_BINDING_MISMATCH')
inventory_target_ids={d['source_id'] for d in inventory_dispositions['dispositions'] if d.get('disposition')=='TREAT'}
features=[];target_ids=set(); dispositions=[]; all_shapes=[]; fcu=[]; source_shapes_by_id={}
for row in side['rows']:
    if 'F.Cu' not in row.get('layers',[]): continue
    geom=_row_geometry(row,side['payloads']) if row.get('coverage')=='GEOMETRY_AVAILABLE' else None
    if geom is not None and not geom.is_empty:
        source_shapes_by_id[row['id']]=geom
        all_shapes.append(geom)
        if geom.intersects(crop):fcu.append(geom)
        feature=rectangular_feature(row,side['payloads'],crop,max_axis_factor=float(policy_doc['factor_per_axis']))
        if feature:
            features.append(feature);target_ids.add(row['id'])
            dispositions.append({'source_id':row['id'],'source_sha256':row['source_sha256'],'source_span':row['source_span'],'source_geometry_sha256':row['geometry_sha256'],'source_kind':row['kind'],'source_layer':'F.Cu','source_geometry_role':row['geometry_role'],'geometric_class':'axis-aligned filled rectangle','net_name':row.get('net_name'),'footprint_reference':row.get('reference'),'disposition':'TREAT','reason':'Exact source-bound filled rectangle; geometry-derived eligibility. No pad/net identity inferred.'})
        elif geom.intersects(crop):
            rect_without_cap_gate=rectangular_feature(
                row,side['payloads'],crop,enforce_full_cap_in_crop=False,
                max_axis_factor=float(policy_doc['factor_per_axis']))
            boundary_reason=(f'Exact rectangle withheld: its complete {float(policy_doc["factor_per_axis"]):.2f}x growth envelope crosses the selected crop boundary; preserve the entire source shape unchanged.'
                             if rect_without_cap_gate else
                             'Non-target source copper retained unchanged; may include circles, routed primitives, and two other polygon contours.')
            dispositions.append({'source_id':row['id'],'source_sha256':row['source_sha256'],'source_span':row['source_span'],'source_geometry_sha256':row['geometry_sha256'],'source_kind':row['kind'],'source_layer':'F.Cu','source_geometry_role':row['geometry_role'],'bounds_mm':row['bounds_mm'],'net_name':row.get('net_name'),'footprint_reference':row.get('reference'),'disposition':'KEEP_PROTECTED','reason':boundary_reason})
        else: continue
    elif row.get('bounds_mm') and box(*row['bounds_mm']).intersects(crop):
        dispositions.append({'source_id':row['id'],'source_sha256':row['source_sha256'],'source_span':row['source_span'],'source_kind':row['kind'],'source_layer':'F.Cu','disposition':'UNSUPPORTED_GEOMETRY','reason':row.get('unsupported_reason') or 'GEOMETRY_UNAVAILABLE'})
if target_ids!=inventory_target_ids:
    raise ValueError('T02_RUNTIME_TARGET_SET_DIFFERS_FROM_FROZEN_ORG_INVENTORY')
policy=RectGrowthPolicy(
    max_axis_factor=float(policy_doc['factor_per_axis']),
    construction_gap_mm=float(policy_doc['construction_gap_mm']),
    hard_gap_mm=float(policy_doc['hard_experimental_gap_mm']),
    geometry_tolerance_mm=float(policy_doc['geometry_tolerance_mm']),
    quad_segs=int(policy_doc['quad_segs']),
    corner_contact_separation_mm=float(policy_doc['trace_interactions'].get('corner_contact_separation_mm', 0.00002)),
    trace_spacing_mode=policy_doc.get('trace_interactions',{}).get('rule_mode','surface_side_priority_v15'),
)
policy.validate()
surface_mode=True
reopened_mode=True
trace_source_ids={row['id'] for row in side['rows']
                  if row.get('kind') in policy_doc['trace_interactions']['trace_source_kinds']
                  and 'F.Cu' in row.get('layers',[])}
protected=[g for row in side['rows'] if 'F.Cu' in row.get('layers',[]) and row.get('id') not in target_ids|trace_source_ids and (g:=source_shapes_by_id.get(row['id'])) is not None]
def native_trace_path(row):
    node=loads(raw[row['source_span'][0]:row['source_span'][1]].decode('utf-8'))
    xy=lambda key:tuple(map(float,one(node,key)))
    start,end=xy('start'),xy('end')
    points=arc_points(start,xy('mid'),end) if row['kind']=='arc' else [start,end]
    return LineString(points)
def native_trace_width(row):
    node=loads(raw[row['source_span'][0]:row['source_span'][1]].decode('utf-8'))
    return float(one(node,'width')[0])
side_traces=[{'source_id':row['id'],'source_kind':row['kind'],'source_span':row['source_span'],
              'geometry':source_shapes_by_id[row['id']],
              'trace_path_geometry':native_trace_path(row),
              'width_mm':native_trace_width(row),
              'geometry_sha256':row.get('geometry_sha256')}
              for row in side['rows'] if row.get('kind') in policy_doc['trace_interactions']['trace_source_kinds']
             and 'F.Cu' in row.get('layers',[]) and row['id'] in source_shapes_by_id]
# Reconstruct the accepted scene from its exact owner-bound WKB, then add its
# positive contribution to protected geometry for every T02 proposal.
t01_scene=wkb.loads(t01_scene_bytes)
org_region=unary_union([g.intersection(crop) for g in fcu])
t01_scene_loss=org_region.difference(t01_scene)
assert t01_scene_loss.area<=1e-8, 'ACCEPTED_T01_SCENE_REMOVES_ORG_COPPER'
t01_additions=t01_scene.difference(org_region)
assert t01_scene.difference(crop).area<=1e-8, 'ACCEPTED_T01_SCENE_EXCEEDS_REGISTERED_CROP'
protected.append(t01_additions)
component_by_source,component_members=(physical_component_index(source_shapes_by_id)
                                     if reopened_mode else (None,None))
result=execute(features,protected,crop,policy,side_traces=side_traces,
               source_geometries=source_shapes_by_id if reopened_mode else None,
               component_by_source=component_by_source)
add=result['accepted_addition_union']
combined=t01_scene.union(add)
if reopened_mode:
    save('component_preservation.json',result['component_preservation'])
    save('physical_component_membership.json',{'source_sha256':source_hash,
         'component_count':len(component_members),'source_count':len(component_by_source),
         'component_by_source':component_by_source,'component_members':component_members})
    previous_run=ROOT/'out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v31'
    old_decisions=json.loads((previous_run/'t02_decisions.json').read_bytes())['decisions']
    old_additions={d['source_id']:wkb.loads((previous_run/'t02_candidates'/(sha(d['source_id'].encode())+'.wkb')).read_bytes()).difference(source_shapes_by_id[d['source_id']])
                   for d in old_decisions if d['decision']=='GROW'}
    save('rejected_v31_component_negative_control.json',validate_component_preservation(
         source_shapes_by_id,component_by_source,old_additions))
    from src.crop_circle_sources import source_scene
    _,circle_rows,_,_,circle_sites=source_scene(raw,
         {**t01_policy,'radius_multiplier':t01_policy['max_growth_factor']},
         expected_unique_sites=t01_policy['expected_unique_circle_sites'],
         expected_occurrences=t01_policy['expected_circle_occurrences'])
    # Embedded circle centers/radii come from native analytic coordinates,
    # rather than the floating centroid/bounds of their polygonal source core.
    import math
    circle_row_by_id={row['id']:row for row in circle_rows}
    for site in circle_sites:
        native_row=circle_row_by_id[site['source_id']]
        node=loads(raw[slice(*native_row['source_span'])].decode('utf-8'))
        center=tuple(map(float,one(node,'center')))
        end=tuple(map(float,one(node,'end')))
        site['center']=list(center)
        site['radius']=math.dist(center,end)
    covered=grow_covered_circles(circle_sites,circle_rows,source_shapes_by_id,
         result['candidates_by_source'],crop,
         policy_doc['embedded_covered_circle_pass']['diameter_classes_mm'],
         max_factor=policy_doc['embedded_covered_circle_pass']['max_radius_factor'])
    covered_geometries=covered.pop('geometries_by_source')
    circle_dir=OUT/'t02_embedded_circles';circle_dir.mkdir()
    for sid,geometry in covered_geometries.items():
        (circle_dir/(sha(sid.encode())+'.wkb')).write_bytes(geometry.wkb)
    covered.update({'source_sha256':source_hash,'policy_sha256':policy_hash,
                    'accepted_T01_geometry_changed':False})
    save('embedded_covered_circles.json',covered)
# Persist each complete target contour, then independently reload and recheck it.
target_dir=OUT/'t02_candidates';target_dir.mkdir(exist_ok=True)
for d in result['decisions']:
    source_id=d['source_id'];candidate=result['candidates_by_source'][source_id]
    filename=sha(source_id.encode())+'.wkb'
    (target_dir/filename).write_bytes(candidate.wkb)
    d['candidate_wkb_file']='t02_candidates/'+filename
# Saved-output verification re-reads bytes and evaluates invariants against every other
# original F.Cu contribution plus every other accepted T02 addition.
by_id={f['source_id']:f for f in features}
all_source_ids=[row['id'] for row in side['rows'] if 'F.Cu' in row.get('layers',[]) and row['id'] in source_shapes_by_id]
all_source_geoms=[source_shapes_by_id[i] for i in all_source_ids]
from shapely import STRtree
source_tree=STRtree(all_source_geoms)
source_index_to_id=all_source_ids
added_by_source=result['accepted_additions_by_source']
added_ids=list(added_by_source);added_geoms=[added_by_source[i] for i in added_ids]
added_tree=STRtree(added_geoms) if added_geoms else None
source_meta_by_id={row['id']:row for row in side['rows'] if row['id'] in source_shapes_by_id}
accepted_t01_constraint_id=f"T01_SCENE:{owner['decision_id']}"
limiting_source_geometries=dict(source_shapes_by_id)
limiting_source_metadata=dict(source_meta_by_id)
if not t01_additions.is_empty:
    limiting_source_geometries[accepted_t01_constraint_id]=t01_additions
    limiting_source_metadata[accepted_t01_constraint_id]={
        'kind':'accepted_T01_scene_addition', 'source_span':[],
        'geometry_sha256':sha(t01_scene_bytes),
    }
trace_by_id={t['source_id']:t['geometry'] for t in side_traces}
prior_t02_source_ids=[]
for d in result['decisions']:
    sid=d['source_id'];f=by_id[sid]
    candidate=wkb.loads((OUT/d['candidate_wkb_file']).read_bytes())
    assert f['geometry'].difference(candidate).area<=policy.area_epsilon_mm2
    cap=_scaled_rectangle(f['geometry'],f['center_mm'],f['orientation_radians'],policy.max_axis_factor,policy.max_axis_factor)
    assert candidate.difference(cap).area<=policy.area_epsilon_mm2
    query=candidate.buffer(policy.hard_gap_mm+policy.geometry_tolerance_mm)
    other=[source_shapes_by_id[source_index_to_id[int(i)]] for i in sorted(source_tree.query(query)) if source_index_to_id[int(i)]!=sid and source_index_to_id[int(i)] not in trace_source_ids
           and not (reopened_mode and f['geometry'].covers(source_shapes_by_id[source_index_to_id[int(i)]]))]
    if added_tree is not None:
        other.extend(added_geoms[int(i)] for i in sorted(added_tree.query(query)) if added_ids[int(i)]!=sid)
    blockers=unary_union(other) if other else crop.difference(crop)
    if not t01_additions.is_empty:
        blockers=unary_union([blockers,t01_additions])
    growth=candidate.difference(f['geometry'])
    current_trace_constraints=dict(trace_by_id)
    for reservation in d['trace_gap_reservations']:
        if reservation['side_by_side_classification']:
            trace=next(t for t in side_traces if t['source_id']==reservation['source_id'])
            current_trace_constraints[trace['source_id']]=side_trace_copper_region(
                f['geometry'],f['center_mm'],f['orientation_radians'],cap,trace,
                policy.construction_gap_mm)[0]
    report_sources=({key:g for key,g in limiting_source_geometries.items()
                    if key not in trace_source_ids and not f['geometry'].covers(g)}
                    if reopened_mode else limiting_source_geometries)
    d['limiting_constraints']=limiting_constraints(
        growth,
        target_source_id=sid,
        source_geometries=report_sources,
        source_metadata=limiting_source_metadata,
        prior_t02_additions={prior_id:added_by_source[prior_id] for prior_id in prior_t02_source_ids},
        trace_reservations=d['trace_gap_reservations'],
        trace_geometries=current_trace_constraints,
        hard_gap_mm=policy.hard_gap_mm,
        construction_gap_mm=policy.construction_gap_mm,
        tolerance_mm=policy.geometry_tolerance_mm,
    )
    d['limiting_constraints'].update(envelope_constraint_records(
        candidate, cap, crop,
        accepted_size_mm=d['accepted_size_mm_in_source_axes'],
        maximum_size_mm=d['maximum_size_mm'],
        policy_sha256=policy_hash,
        tolerance_mm=policy.geometry_tolerance_mm,
        area_epsilon_mm2=policy.area_epsilon_mm2,
    ))
    assert growth.is_empty or growth.distance(blockers)+policy.geometry_tolerance_mm>=policy.hard_gap_mm
    for reservation in d['trace_gap_reservations']:
        trace=next(t for t in side_traces if t['source_id']==reservation['source_id'])
        assert abs(f['geometry'].distance(trace['geometry'])-reservation['org_surface_gap_mm'])<=policy.geometry_tolerance_mm
        if reservation['required_retained_gap_mm']>0:
            assert growth.is_empty or growth.distance(current_trace_constraints[trace['source_id']])+policy.geometry_tolerance_mm>=reservation['required_retained_gap_mm']
    d['verification']['saved_trace_gap_reservations_pass']=True
    assert candidate.is_valid
    assert sha(candidate.wkb)==d['candidate_geometry_sha256']
    if d['decision']=='GROW':
        prior_t02_source_ids.append(sid)
bound_dispositions=bind_source_dispositions(
    inventory_dispositions['dispositions'],dispositions,result['decisions'])
source_disposition_counts=Counter(d['disposition'] for d in bound_dispositions)
source_class_counts=Counter(d.get('geometric_class') or 'unclassified_protected_source'
                            for d in bound_dispositions)
save('feature_dispositions.json',{
    'schema':'crop-t02-feature-dispositions/2',
    'source_sha256':source_hash,
    'crop_bounds_mm':report['crop_bounds_org_mm'],
    'source_disposition_count':len(bound_dispositions),
    'source_disposition_counts':dict(sorted(source_disposition_counts.items())),
    'source_class_counts':dict(sorted(source_class_counts.items())),
    'target_count':len(features),
    'target_set_sha256':inventory_report['candidate_target_ids_sha256'],
    'inventory_manifest_sha256':inventory_hash,
    'dispositions':bound_dispositions,
})
(OUT/'t02_policy.json').write_bytes(policy_raw)
save('org_inventory_binding.json',{'schema':'t02-org-inventory-binding/1','inventory_directory':str(INVENTORY_PATH.relative_to(ROOT)),'inventory_manifest_sha256':inventory_hash,'inventory_report_sha256':sha((INVENTORY_PATH/'inventory_report.json').read_bytes()),'target_set_sha256':inventory_report['candidate_target_ids_sha256'],'target_count':inventory_report['candidate_target_count'],'policy_sha256':policy_hash,'source_sha256':source_hash})
rows=[]
for d in result['decisions']:
    q={k:v for k,v in d.items() if k!='candidate_wkb_file'}
    rows.append(q)
future_trace_items=[{'rectangle_source_id':d['source_id'],'rectangle_source_span':d['source_span'],**item}
                    for d in rows for item in d.get('future_trace_overlap_records',[])]
trace_copper_union=unary_union([t['geometry'] for t in side_traces]) if side_traces else crop.difference(crop)
unique_t02_trace_overlap=add.intersection(trace_copper_union)
clearance_issues=[{'rectangle_source_id':d['source_id'],'rectangle_source_span':d['source_span'],**item}
                  for d in rows for item in d.get('future_trace_clearance_work_items',[])]
save('future_trace_work_items.json',{
    'schema':'t02-future-trace-work-items/1','task':'T02_ONLY','status':'RECORDED_FOR_FUTURE_TRACE_TASK',
    'source_sha256':source_hash,'policy_sha256':policy_hash,'t01_scene_sha256':sha(t01_scene_bytes),
    'trace_changed_in_t02':False,'count':len(future_trace_items),
    'pairwise_overlap_area_total_mm2':sum(item['overlap_area_mm2'] for item in future_trace_items),
    'unique_t02_added_copper_overlap_area_mm2':unique_t02_trace_overlap.area,
    'unique_overlap_fraction_of_t02_added_area':unique_t02_trace_overlap.area/add.area if add.area else 0.0,
    'items':future_trace_items,
    'clearance_issue_count':len(clearance_issues),
    'clearance_issues':clearance_issues,
})
save('t02_decisions.json',{'schema':'crop-t02-decisions/3','policy':{'max_axis_factor':policy.max_axis_factor,'construction_gap_mm':policy.construction_gap_mm,'hard_gap_mm':policy.hard_gap_mm,'geometry_tolerance_mm':policy.geometry_tolerance_mm,'quad_segs':policy.quad_segs},'policy_sha256':policy_hash,'inventory_manifest_sha256':inventory_hash,'source_sha256':source_hash,'target_set_sha256':sha('\n'.join(sorted(target_ids)).encode()),'decision_count':len(rows),'counts':dict(Counter(d['decision'] for d in rows)),'decisions':rows})
(OUT/'t02_additions.wkb').write_bytes(add.wkb)
(OUT/'t01_accepted_plus_t02.wkb').write_bytes(combined.wkb)
basepath=REGISTRATION/'org_crop.wkb'
assert unary_union([g.intersection(crop) for g in fcu]).symmetric_difference(wkb.loads(basepath.read_bytes())).area < 1e-8
# Render using same bounds. Positive layer red; changed region teal.
scale_px=160
for name,g,color in [('org_crop.svg',org_region,'#e9485b'),('accepted_t01_crop.svg',t01_scene,'#e9485b'),('t01_plus_t02.svg',combined,'#e9485b'),('t02_delta.svg',add,'#35d4b7')]:
    path=_svg_path(g,*report['crop_bounds_org_mm'][:2],scale_px)
    w=(report['crop_bounds_org_mm'][2]-report['crop_bounds_org_mm'][0])*scale_px;h=(report['crop_bounds_org_mm'][3]-report['crop_bounds_org_mm'][1])*scale_px
    (OUT/name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="#071522"/><path fill="{color}" fill-rule="evenodd" d="{path}"/></svg>')
def ring_data(g):
    polygons=list(g.geoms) if g.geom_type=='MultiPolygon' else [g]
    return {'bounds_mm':report['crop_bounds_org_mm'],'polygons':[{'exterior':list(x.exterior.coords),'interiors':[list(r.coords) for r in x.interiors]} for x in polygons if x.geom_type=='Polygon']}
for name,g in [('org',org_region),('accepted_t01',t01_scene),('t01_plus_t02',combined),('t02_delta',add)]:
    save(name+'_render_rings.json',ring_data(g))
causal_events=[{'target_source_id':d['source_id'],'neighbor':n} for d in rows for n in d['causal_prior_t02_neighbors']]
summary={'task':'T02_ONLY','status':'EXPERIMENTAL_REAL_CROP_EXECUTED','accepted_T01_decision_id':owner['decision_id'],'accepted_T01_status':'ACCEPTED_VISUAL_CROP','accepted_T01_scene_sha256':sha(t01_scene_bytes),'accepted_T01_scene_area_mm2':t01_scene.area,'accepted_T01_policy_sha256':sha(t01_policy_bytes),'accepted_T01_selection_sha256':sha(t01_selection_bytes),'accepted_T01_square_recess_policy':t01_policy.get('square_guided_recess'),'accepted_T01_owner_correction':t01_policy.get('owner_marked_area_correction'),'source_sha256':source_hash,'policy_sha256':policy_hash,'org_inventory_manifest_sha256':inventory_hash,'crop_bounds_mm':report['crop_bounds_org_mm'],'target_set_count':len(features),'target_set_sha256':sha('\n'.join(sorted(target_ids)).encode()),'decision_counts':dict(Counter(d['decision'] for d in rows)),'source_disposition_counts':dict(source_disposition_counts),'source_class_counts':dict(source_class_counts),'added_area_mm2':add.area,'accepted_union_area_mm2':combined.area,'all_per_target_checks_pass':all(all(d['verification'].values()) for d in rows),'current_neighbor_events':len(causal_events),'current_neighbor_causal_pairs':causal_events,'side_trace_reservation_count':sum(len(d['trace_gap_reservations']) for d in rows),'future_trace_overlap_count':len(future_trace_items),'future_trace_overlap_pairwise_area_total_mm2':sum(item['overlap_area_mm2'] for item in future_trace_items),'future_trace_overlap_unique_area_mm2':unique_t02_trace_overlap.area,'future_trace_overlap_unique_fraction_of_additions':unique_t02_trace_overlap.area/add.area if add.area else 0.0,'future_trace_work_items':'future_trace_work_items.json','trace_changed_in_t02':False,'edit_access_in_constructor':False,'native_export':'NOT_RUN','electrical_status':'NOT_ESTABLISHED','manufacturing_status':'NOT_ESTABLISHED','EDIT_equivalence':'NOT_ESTABLISHED','environment':{'python':platform.python_version()},'limitations':['Standalone F.Cu geometry records contain no pad/net identity; TREAT denotes a source-owned geometric rectangle only.','Native segment/arc proximity is geometric; it does not infer same-net or attachment intent.','EDIT was used only to locate the displayed viewport and was not read by proposal generation.','Screenshot crop edge estimate uncertainty is at least 0.0223 mm; source geometry uses exact native units.','The 1.25x per-axis ceiling, intact rectangle rule, and circle occupancy plus construction gap are experimental guardrails, not manufacturing rules.','Every positive-area T02-addition/trace-copper overlap is recorded; traces remain unchanged. Pairwise and unique overlap metrics are separately reported. The owner has not yet numerically bounded slight overlap.']}
if reopened_mode:
    assert covered['all_checks_pass'], 'T02_EMBEDDED_CIRCLE_CHECK_FAILED'
    import shapely
    summary.update({
        'geometry_environment':{'shapely':shapely.__version__,'geos':shapely.geos_version_string},
        'trace_rule_mode':policy.trace_spacing_mode,
        'side_by_side_surface_construction_gap_mm':policy.construction_gap_mm if surface_mode else None,
        'original_component_preservation':result['component_preservation'],
        'future_trace_clearance_issue_count':len(clearance_issues),
        'future_trace_issue_counts':dict(Counter(x['issue_type'] for x in clearance_issues)),
        'baseline_side_gap_issue_count':sum(x['issue_type']=='SOURCE_SIDE_GAP_REQUIRES_FUTURE_TRACE_REPAIR' for x in clearance_issues),
        'minimum_safe_gap_status':'OPEN_BASELINE_AND_CORNER_TRACE_ISSUES',
        'future_trace_width_rule':'MUST_NOT_SHRINK_FROM_ORG_WIDTH',
        'embedded_covered_circle_count':covered['count'],
        'embedded_covered_circle_grown_count':covered['grown_count'],
        'embedded_circle_checks_pass':covered['all_checks_pass'],
        'embedded_circle_visible_added_copper_mm2':covered['visible_added_copper_mm2'],
        'owner_review':'PENDING_USER',
        'implementation_sha256':{path:sha((ROOT/path).read_bytes()) for path in
              ['src/crop_rect_t02.py','tools/run_crop_rect_t02.py']},
        'limitations':policy_doc['limitations'],
    })
save('t02_result.json',summary)
print(json.dumps(summary,indent=2))
