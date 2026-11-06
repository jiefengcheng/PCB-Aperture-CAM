"""Positive obligations measured from freshly reparsed native export copper."""
from shapely import from_wkb,STRtree
from shapely.geometry import Polygon,box
from shapely.errors import GEOSException
from shapely.ops import unary_union
from src.junction_spindle_stage import CONTRACT
from src.junction_spindle_blend import spindle_blend
from tools.t01_operator_host import read

FILE_UNCERTAINTY_MM=.000002

def obligation_check(required,before,regions,*,already=False):
    """Require the whole approved extent, not merely some nearby new copper."""
    physical=unary_union(regions).difference(before) if regions else Polygon()
    # No copper farther than the buffer radius can cover the obligation.
    # A two-radius halo keeps every clipping edge outside that influence.
    # This checks the COMPLETE required extent, not sampled points or a crop
    # substituted for an obligation. The unchanged full operation remains the
    # fallback for any local rejection or unsupported local geometry.
    if required.is_empty:local=Polygon()
    else:
        a,b,c,d=required.bounds;halo=2*FILE_UNCERTAINTY_MM
        try:local=before.intersection(box(a-halo,b-halo,c+halo,d+halo))
        except GEOSException:local=before
    present=local if already else local.union(unary_union(regions))
    missing=required.difference(present.buffer(FILE_UNCERTAINTY_MM,quad_segs=64))
    if missing.area>CONTRACT.area_epsilon_mm2:
        present=before if already else before.union(unary_union(regions))
        missing=required.difference(present.buffer(FILE_UNCERTAINTY_MM,quad_segs=64))
    if missing.area>CONTRACT.area_epsilon_mm2:raise ValueError('U05_ACTUAL_ATTACHMENT_EXTENT_MISSING')
    effective=physical.intersection(required.buffer(FILE_UNCERTAINTY_MM,quad_segs=64)).area
    if not already and (required.area<=CONTRACT.minimum_visible_addition_mm2 or effective<=CONTRACT.minimum_visible_addition_mm2):raise ValueError('U05_ACTUAL_ATTACHMENT_NO_EFFECT')
    return dict(passed=True,required_area_mm2=required.area,missing_beyond_file_uncertainty_mm2=missing.area,effective_actual_addition_mm2=effective,file_uncertainty_mm=FILE_UNCERTAINTY_MM)

def verify_attachments(service,before_shapes,tree,actual_by_owner):
    with service.gates.adapter.execution(service.store,service.scene,service.policy):return _verify_attachments(service,before_shapes,tree,actual_by_owner)

def _verify_attachments(service,before_shapes,tree,actual_by_owner):
    g=service.gates;adapter=g.adapter;objects,current,_,_=adapter._context(service.store,service.scene,service.policy,service.plan['details']);model_before=adapter._before
    records=[];witnesses=[];all_regions=[p for group in actual_by_owner.values() for p in group];patch_tree=STRtree(all_regions)
    reference=__import__('pathlib').Path(g.reference['root']);historical={d.get('id'):d for d in read(reference/'T05/DECISIONS.json') if d['status']=='GROWN'}
    for d in service.candidate['decisions']:
        if not d['land_ids']:continue
        owner,radius,domain,foreign=adapter._operands(service.store,service.scene,service.policy,service.plan['details'],d)
        desired=spindle_blend(owner,radius,domain)[1]
        needs=adapter.needs(current,d,radius,desired.difference(model_before))
        # One local before union per cluster; all actual before atoms intersecting
        # the complete obligation domain participate, including foreign copper.
        local=unary_union([before_shapes[i] for i in sorted(map(int,tree.query(domain.buffer(FILE_UNCERTAINTY_MM))))])
        regions=actual_by_owner.get(d['source_id'],[])
        selected=from_wkb(service.store.get(d['patch_ref'],kind='geometry')) if d['status']=='GROWN' else Polygon()
        expected_physical=selected.difference(model_before)
        if len(needs)!=len(d['attachment_outcomes']):raise ValueError('U05_ACTUAL_ATTACHMENT_INVENTORY_MISSING')
        for n,a in zip(needs,d['attachment_outcomes']):
            if any(a[k]!=n[k] for k in ('id','land_id','reference_land_id','required_reference')):raise ValueError('U05_ACTUAL_ATTACHMENT_MEMBERSHIP_CHANGED')
            row=dict(a,source_id=d['source_id'],reference_id=d['reference_id'],reference_status=d['reference_status'])
            if a['status']=='TREATED_VERIFIED':
                required=expected_physical.intersection(n['window']);row['actual_export_check']=obligation_check(required,local,regions)
            elif a['status']=='ALREADY_SATISFIED_VERIFIED':
                # Max-radius, pre-barrier requirement: clipped-away copper cannot
                # manufacture an already-satisfied outcome.
                required=desired.intersection(n['window']);row['actual_export_check']=obligation_check(required,local,[],already=True)
            elif a['status']=='BLOCKED_CLEARANCE_OR_BOUNDARY' and not a['required_reference']:
                row['actual_export_check']=dict(passed=False,status='BLOCKED_NOT_COUNTED_AS_COVERED',attempts=d['attempts'])
            else:raise ValueError('U05_ACTUAL_REQUIRED_ATTACHMENT_NOT_FULFILLED')
            records.append(row)
        if d['reference_status']=='GROWN':
            old=from_wkb((reference/'T05/patches'/(d['reference_id']+'.wkb')).read_bytes());old_owner=from_wkb((reference/'T05/patches'/(d['reference_id']+'_owner.wkb')).read_bytes());old_window=from_wkb((reference/'T05/patches'/(d['reference_id']+'_window.wkb')).read_bytes())
            actual_after=local.union(unary_union([all_regions[i] for i in sorted(map(int,patch_tree.query(domain)))]));missing=old.difference(actual_after.buffer(FILE_UNCERTAINTY_MM,quad_segs=64))
            maximum=owner.union(desired);scaled=spindle_blend(owner,radius*d['scale'],domain)[0]
            upstream=missing.difference(maximum);remaining=missing.difference(upstream);scale_loss=remaining.difference(scaled);barriers=remaining.difference(scale_loss)
            witnesses.append(dict(reference_id=d['reference_id'],reference_patch_area_mm2=old.area,reference_missing_actual_mm2=missing.area,current_approved_addition_mm2=expected_physical.area,current_radius_mm=radius,current_scale=d.get('scale'),reference_radius_mm=historical[d['reference_id']]['blend_radius_mm'],owner_symmetric_difference_mm2=owner.symmetric_difference(old_owner).area,window_symmetric_difference_mm2=domain.symmetric_difference(old_window).area,T04_disposition=objects[d['source_id']]['metadata']['T04_disposition'],difference_reasons=dict(changed_upstream_owner_or_land_window_mm2=upstream.area,bounded_scale_choice_mm2=scale_loss.area,barrier_clipping_or_file_grid_mm2=barriers.area),attempts=d['attempts'],explanation='Recomputed from current U04; no reference copper copied. Difference partitions explain missing historical witness copper and do not waive current attachment obligations.',current_required_extent_passed=True))
    required=[r for r in records if r['required_reference']]
    if len(records)!=180 or len({r['id'] for r in records})!=180 or len(required)!=162 or len(witnesses)!=85:raise ValueError('U05_ACTUAL_ATTACHMENT_DENOMINATOR_CHANGED')
    if any(not r['actual_export_check']['passed'] for r in required):raise ValueError('U05_ACTUAL_REQUIRED_ATTACHMENT_NOT_FULFILLED')
    return dict(required_reference_attachments=162,verified_required_attachments=162,reference_positive_clusters=85,all_attachment_records=180,blocked_nonreference_attachments=sum(not r['actual_export_check']['passed'] for r in records),records=records,reference_witnesses=witnesses)
