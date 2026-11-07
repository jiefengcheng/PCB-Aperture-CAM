"""One source-wide T01 allocation contract; no ROI or case output operands."""
import json
from pathlib import Path
from shapely.ops import unary_union
from shapely import to_wkb
from src.stage_abi.store import canonical,digest
from src.stage_abi.contracts import fail
from src.runtime_kernel_binding import matches as kernel_matches
from src.crop_balanced_t01 import CropSettings,WorkingScene,choose_priorities
from src.crop_diameter_selection import select_targets,promote_round_priorities
from src.crop_circle_sources import site_record
from src.shape_containment import ContainmentIndex,policy as containment_policy
from src.t01_bga_single import capture as bga_settings,eligible_sites as bga_eligible_sites
from src.t01_circle_exposure import capture as exposure_settings,assess as assess_exposure

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'contracts/t01_canonical/contract.json'
CONTRACT_SHA256='c69d627eede01f53541b1b81f406fe9e0c4b0753699d440fe379643c81acb01c'

def specification():
    data=CONTRACT.read_bytes()
    if digest(data)!=CONTRACT_SHA256:fail('T01_CANONICAL_CONTRACT_CHANGED','Immutable canonical revision')
    spec=json.loads(data)
    from src.clearance_policy import marker as clearance_marker,specification as clearance_spec
    clearance_spec()
    if spec['production_clearance']!=dict(path='contracts/clearance/production.json',sha256=clearance_marker()['sha256'],hard_gap_mm=clearance_marker()['hard_gap_mm']):fail('T01_CLEARANCE_POLICY_CHANGED','Pinned production defaults')
    if spec['contained_shape_keep']!=containment_policy():fail('T01_CONTAINMENT_POLICY_CHANGED','Uniform source containment rule')
    if spec['bga_single_circle_rule']['sha256']!=bga_settings()['sha256']:fail('T01_BGA_SINGLE_POLICY_CHANGED','Versioned source classification')
    for name,h in spec['kernel_sha256'].items():
        if not kernel_matches(ROOT,name,h):fail('T01_CANONICAL_KERNEL_CHANGED',name)
    directive=spec['source_directives']
    if digest((ROOT/directive['path']).read_bytes())!=directive['sha256']:fail('T01_SOURCE_DIRECTIVES_CHANGED','Versioned native source directives')
    return spec

def marker():
    s=specification()
    return dict(schema=s['schema'],family=s['family'],contract_sha256=CONTRACT_SHA256,
                bga_single_circle_settings=bga_settings(),
                circle_exposure_settings=exposure_settings().snapshot())

def fingerprint(source_sha256,result):
    return digest(canonical(dict(canonical_t01=marker(),source_sha256=source_sha256,
        geometry_by_source={sid:r['sha256']for sid,r in result['replacements'].items()})))

def require(policy):
    if policy.get('canonical_t01')!=marker() or policy.get('family')!=marker()['family']:fail('T01_CANONICAL_SOURCE_POLICY_REQUIRED','Historical/case-bound engines cannot construct new T01 candidates')
    s=specification()
    if policy['settings']!=s['settings'] or policy['diameter_classes_mm']!=s['diameter_classes_mm']:fail('T01_CANONICAL_NUMERIC_POLICY_CHANGED','No numeric relaxation')

def full_bounds(shapes):
    # Complete original bounds already enclose circle cores. Expansion by their
    # own possible radius supplies a view-independent analysis window.
    a=min(g.bounds[0]for g in shapes);b=min(g.bounds[1]for g in shapes)
    c=max(g.bounds[2]for g in shapes);d=max(g.bounds[3]for g in shapes)
    return [a-.5,b-.5,c+.5,d+.5]


def allocate(raw,rows,shapes,sites,policy,binding):
    require(policy)
    from src.t01_crop.adapter import groups_for
    spec=specification();source=digest(raw)
    directive=json.loads((ROOT/spec['source_directives']['path']).read_bytes())['sources'].get(source,{})
    if binding['reviewed_pairs']!=directive.get('reviewed_pairs',[]) or binding['recess_source_ids']!=directive.get('recess_source_ids',[]):fail('T01_SOURCE_DIRECTIVES_CHANGED','Binding must match original-source directives, never a case override')
    settings=CropSettings(**spec['settings']);initial=WorkingScene(raw,rows,shapes,sites,settings)
    ids={s['source_id']for s in sites};all_sources={r['id']for r in rows}
    protected=set(spec['permissions'].get(source,{}).get('keep_original_source_ids',[]))
    if not protected<=all_sources:fail('T01_BLOCKED_SOURCE_ID_MISSING','Complete original source required')
    containment=ContainmentIndex(dict(zip((r['id']for r in rows),shapes)))
    contained_records={s['source_id']:containment.assess(s['source_id'],s['aliases'])for s in sites}
    contained={sid for sid,r in contained_records.items()if r['contained']}
    exposure=exposure_settings()
    exposure_records={s['source_id']:assess_exposure(s,containment,exposure,contained_records[s['source_id']])for s in sites}
    # Only the owner's >=70% exposed-circumference rule controls new circle
    # eligibility. No area-overlap threshold is evaluated in this allocator.
    overlap_keep={sid for sid,r in exposure_records.items()if r['keep']}
    blocked={s['source_id']for s in sites if protected.intersection(s['aliases'])}|overlap_keep
    bga_source=bga_eligible_sites(sites,rows,shapes)
    bga=set(bga_source)-blocked
    # This case has no paired-pad partner. Giving an isolated array island a
    # synthetic proximity partner would impose that pair's square-follower
    # size limit before its independently clipped growth was ever proposed.
    # All actual neighbours remain in the complete scene and all final checks.
    groups=groups_for([s for s in sites if s['source_id']not in bga],
                      directive.get('reviewed_pairs',[]),blocked,settings.construction_gap)
    for sid in sorted(bga):
        groups.append(dict(group_id=f'G{len(groups)+1:02d}',site_ids=[sid],rule='BGA_SINGLE_CLEAR_ARRAY_INDEPENDENT_SITE'))
    for group in groups:
        if set(group['site_ids'])&blocked:
            group['rule']=('CONTAINED_SOURCE_KEEP'if set(group['site_ids'])&contained else
                           'EXPOSED_CIRCUMFERENCE_KEEP'if set(group['site_ids'])&overlap_keep else
                           'IMMUTABLE_SOURCE_PERMISSION_KEEP')
    priorities,exceptions=choose_priorities([s for s in sites if s['source_id']not in blocked],initial)
    square=set(directive.get('recess_source_ids',[]))-protected-overlap_keep
    for component,sid in list(priorities.items()):
        if sid in square or sid in bga:
            del priorities[component];exceptions.append(dict(component_id=component,source_id=sid,reason='BGA_SINGLE_CLEAR_ARRAY_OPTIONAL_GROWTH'if sid in bga else'SOURCE_RECESS_DIRECTIVE',previous_round_priority=sid))
    from src.t01_canonical_surface import SurfaceGuard
    surface=SurfaceGuard(rows,shapes,sites)
    round_checks={}
    def round_guard(site,proposal):
        key=(site['source_id'],digest(to_wkb(proposal)))
        if key not in round_checks:
            bounded=surface.limit(site,proposal,initial,priority=True,record=False)
            changed=bounded.symmetric_difference(proposal).area
            round_checks[key]=dict(passed=changed<=settings.area_epsilon and bounded.covers(site['core']),optional_difference_mm2=changed,construction_gap_mm=surface.contract.construction_gap_mm,construction_reserve_mm=surface.reserve)
        return round_checks[key]
    gap=surface.contract.construction_gap_mm+surface.reserve
    targets,records,limits=select_targets(sites,groups,priorities,initial,settings,spec['diameter_classes_mm'],round_guard=round_guard,round_separation_gap_mm=gap)
    promotions=promote_round_priorities(sites,groups,priorities,initial,settings,targets,records,round_guard=round_guard,round_separation_gap_mm=gap)
    limits.extend(dict(reason='FEASIBLE_ROUND_CLASS_PROMOTION',**p)for p in promotions)
    for s in sites:
        if s['source_id']in blocked:
            sid=s['source_id'];targets[sid]=s['radius'];records[sid].update(proposed_radius_mm=s['radius'],selected_diameter_mm=2*s['radius'],category_mm=None,original_keep=True)
            if sid in contained:records[sid]['limits'].append(dict(reason='CONTAINED_SOURCE_KEEP'))
            elif sid in overlap_keep:records[sid]['limits'].append(dict(reason='EXPOSED_CIRCUMFERENCE_BELOW_LIMIT'))
            if protected.intersection(s['aliases']):records[sid]['limits'].append(dict(reason='IMMUTABLE_SOURCE_PERMISSION_KEEP'))
    allocation=dict(canonical_t01=marker(),analysis_bounds_mm=full_bounds(shapes),groups=groups,priorities_by_physical_component=priorities,priority_exceptions=exceptions,factor_limits=limits,size_classes=records,sites=[site_record(s)for s in sites],ports={sid:{other:to_wkb(g,byte_order=1).hex()for other,g in zones.items()}for sid,zones in initial.ports.items()},boundary_keep_source_ids=[],permission_keep_source_ids=sorted(protected),priority_pool_source_ids=sorted(ids),roi_semantics='No ROI construction dependency; complete native source priority pool, original source directives and immutable permissions')
    allocation.update(contained_shape_policy=containment_policy(),containment=contained_records,
                      contained_keep_source_ids=sorted(contained),
                      circle_overlap_keep_source_ids=sorted(overlap_keep),
                      keep_source_ids=sorted(blocked))
    allocation.update(circle_exposure_settings=exposure.snapshot(),circle_exposure=exposure_records,
                      circle_exposure_keep_source_ids=sorted(overlap_keep),
                      circle_eligibility_metric='ORIGINAL_EXPOSED_CIRCUMFERENCE_FRACTION',
                      circle_overlap_keep_field_semantics='Compatibility alias of circle_exposure_keep_source_ids; area is diagnostic only')
    allocation.update(bga_single_circle_settings=bga_settings(),
                      bga_single_circle_source_proofs=bga_source,
                      bga_single_circle_growth_source_ids=sorted(bga),
                      bga_single_circle_keep_source_ids=sorted(set(bga_source)&blocked))
    return settings,allocation,targets,square
