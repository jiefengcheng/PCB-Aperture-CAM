"""Run the frozen T02 rectangle experiment from ORG + accepted T01 evidence only."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
REGISTRATION=ROOT/'out/crop_dynamic_tasks/t02_crop_registration_20261024'
POLICY_PATH=ROOT/'contracts/crop_rect_t02_policy_v2.json'
INVENTORY_PATH=ROOT/'out/crop_dynamic_tasks/t02_org_inventory_20261025_v2'
OUT=ROOT/'out/crop_dynamic_tasks/t02_rectangles_crop_20261025_v5'
if '--output' in sys.argv:
    arg_index=sys.argv.index('--output')
    try: OUT=Path(sys.argv[arg_index+1]).resolve()
    except IndexError: raise SystemExit('--output requires a path')
    del sys.argv[arg_index:arg_index+2]
import hashlib,json,platform
from collections import Counter
from shapely import wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.org_edit_target_map import _inventory_side,_row_geometry,_svg_path
from src.crop_rect_t02 import RectGrowthPolicy,rectangular_feature,execute,validate_accepted_t01_baseline
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
        feature=rectangular_feature(row,side['payloads'],crop)
        if feature:
            features.append(feature);target_ids.add(row['id'])
            dispositions.append({'source_id':row['id'],'source_sha256':row['source_sha256'],'source_span':row['source_span'],'source_geometry_sha256':row['geometry_sha256'],'source_kind':row['kind'],'source_layer':'F.Cu','source_geometry_role':row['geometry_role'],'geometric_class':'axis-aligned filled rectangle','net_name':row.get('net_name'),'footprint_reference':row.get('reference'),'disposition':'TREAT','reason':'Exact source-bound filled rectangle; geometry-derived eligibility. No pad/net identity inferred.'})
        elif geom.intersects(crop):
            rect_without_cap_gate=rectangular_feature(row,side['payloads'],crop,enforce_full_cap_in_crop=False)
            boundary_reason=('Exact rectangle withheld: its complete 1.5x growth envelope crosses the selected crop boundary; preserve the entire source shape unchanged.'
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
    side_trace_gap_fraction_of_org=float(policy_doc['side_trace_gap_reservation']['fraction_of_original_surface_gap']),
)
policy.validate()
protected=[g for row in side['rows'] if 'F.Cu' in row.get('layers',[]) and row.get('id') not in target_ids and (g:=source_shapes_by_id.get(row['id'])) is not None]
side_traces=[{'source_id':row['id'],'source_kind':row['kind'],'source_span':row['source_span'],
              'geometry':source_shapes_by_id[row['id']]}
             for row in side['rows'] if row.get('kind') in policy_doc['side_trace_gap_reservation']['native_source_kinds']
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
result=execute(features,protected,crop,policy,side_traces=side_traces)
add=result['accepted_addition_union']
combined=t01_scene.union(add)
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
for d in result['decisions']:
    sid=d['source_id'];f=by_id[sid]
    candidate=wkb.loads((OUT/d['candidate_wkb_file']).read_bytes())
    assert f['geometry'].difference(candidate).area<=policy.area_epsilon_mm2
    cap=__import__('shapely.affinity',fromlist=['scale']).scale(f['geometry'],xfact=policy.max_axis_factor,yfact=policy.max_axis_factor,origin=tuple(f['center_mm']))
    assert candidate.difference(cap).area<=policy.area_epsilon_mm2
    query=candidate.buffer(policy.hard_gap_mm+policy.geometry_tolerance_mm)
    other=[source_shapes_by_id[source_index_to_id[int(i)]] for i in sorted(source_tree.query(query)) if source_index_to_id[int(i)]!=sid]
    if added_tree is not None:
        other.extend(added_geoms[int(i)] for i in sorted(added_tree.query(query)) if added_ids[int(i)]!=sid)
    blockers=unary_union(other) if other else crop.difference(crop)
    if not t01_additions.is_empty:
        blockers=unary_union([blockers,t01_additions])
    growth=candidate.difference(f['geometry'])
    assert growth.is_empty or growth.distance(blockers)+policy.geometry_tolerance_mm>=policy.hard_gap_mm
    trace_by_id={t['source_id']:t['geometry'] for t in side_traces}
    for reservation in d['trace_gap_reservations']:
        trace=trace_by_id[reservation['source_id']]
        assert abs(f['geometry'].distance(trace)-reservation['org_surface_gap_mm'])<=policy.geometry_tolerance_mm
        assert growth.distance(trace)+policy.geometry_tolerance_mm>=reservation['required_retained_gap_mm']
    d['verification']['saved_trace_gap_reservations_pass']=True
    assert candidate.is_valid
    assert sha(candidate.wkb)==d['candidate_geometry_sha256']
save('feature_dispositions.json',{'schema':'crop-t02-feature-dispositions/1','crop_bounds_mm':report['crop_bounds_org_mm'],'target_count':len(features),'dispositions':dispositions})
(OUT/'t02_policy.json').write_bytes(policy_raw)
save('org_inventory_binding.json',{'schema':'t02-org-inventory-binding/1','inventory_directory':str(INVENTORY_PATH.relative_to(ROOT)),'inventory_manifest_sha256':inventory_hash,'inventory_report_sha256':sha((INVENTORY_PATH/'inventory_report.json').read_bytes()),'target_set_sha256':inventory_report['candidate_target_ids_sha256'],'target_count':inventory_report['candidate_target_count'],'policy_sha256':policy_hash,'source_sha256':source_hash})
rows=[]
for d in result['decisions']:
    q={k:v for k,v in d.items() if k!='candidate_wkb_file'}
    rows.append(q)
save('t02_decisions.json',{'schema':'crop-t02-decisions/2','policy':{'max_axis_factor':policy.max_axis_factor,'construction_gap_mm':policy.construction_gap_mm,'hard_gap_mm':policy.hard_gap_mm,'geometry_tolerance_mm':policy.geometry_tolerance_mm,'quad_segs':policy.quad_segs,'side_trace_gap_fraction_of_org':policy.side_trace_gap_fraction_of_org},'policy_sha256':policy_hash,'inventory_manifest_sha256':inventory_hash,'source_sha256':source_hash,'target_set_sha256':sha('\n'.join(sorted(target_ids)).encode()),'decision_count':len(rows),'counts':dict(Counter(d['decision'] for d in rows)),'decisions':rows})
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
summary={'task':'T02_ONLY','status':'EXPERIMENTAL_REAL_CROP_EXECUTED','accepted_T01_decision_id':owner['decision_id'],'accepted_T01_status':'ACCEPTED_VISUAL_CROP','accepted_T01_scene_sha256':sha(t01_scene_bytes),'accepted_T01_scene_area_mm2':t01_scene.area,'accepted_T01_policy_sha256':sha(t01_policy_bytes),'accepted_T01_selection_sha256':sha(t01_selection_bytes),'accepted_T01_square_recess_policy':t01_policy.get('square_guided_recess'),'accepted_T01_owner_correction':t01_policy.get('owner_marked_area_correction'),'source_sha256':source_hash,'policy_sha256':policy_hash,'org_inventory_manifest_sha256':inventory_hash,'crop_bounds_mm':report['crop_bounds_org_mm'],'target_set_count':len(features),'target_set_sha256':sha('\n'.join(sorted(target_ids)).encode()),'decision_counts':dict(Counter(d['decision'] for d in rows)),'added_area_mm2':add.area,'accepted_union_area_mm2':combined.area,'all_per_target_checks_pass':all(all(d['verification'].values()) for d in rows),'current_neighbor_events':len(causal_events),'current_neighbor_causal_pairs':causal_events,'side_trace_reservation_fraction_of_org_gap':policy.side_trace_gap_fraction_of_org,'side_trace_reservation_count':sum(len(d['trace_gap_reservations']) for d in rows),'edit_access_in_constructor':False,'native_export':'NOT_RUN','electrical_status':'NOT_ESTABLISHED','manufacturing_status':'NOT_ESTABLISHED','EDIT_equivalence':'NOT_ESTABLISHED','environment':{'python':platform.python_version()},'limitations':['Standalone F.Cu geometry records contain no pad/net identity; TREAT denotes a source-owned geometric rectangle only.','Native segment/arc proximity is geometric; it does not infer same-net or attachment intent.','EDIT was used only to locate the displayed viewport and was not read by proposal generation.','Screenshot crop edge estimate uncertainty is at least 0.0223 mm; source geometry uses exact native units.','The shared 1.5x per-axis ceiling and half-ORG trace corridor are experimental guardrails, not manufacturing rules.']}
save('t02_result.json',summary)
print(json.dumps(summary,indent=2))
