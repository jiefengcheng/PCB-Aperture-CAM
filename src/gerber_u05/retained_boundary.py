"""Two local finishing passes over admitted widening, in one shared context.

The entry revision owns source roles and physical ownership. Query views carry
the actual changing geometry. The final verified output revision is published
by the board runner, after its assembled checks, rather than rebuilding owners
while trying individual features.
"""
import json
from time import perf_counter
from shapely import to_wkb
from .finite_profile_union import polygonal
from .pipeline import digest
from .boundary_prepare import supports,bridge_allowances,shoulder_dependencies


def saved_inputs(before,sources):
    keys={s:digest(to_wkb(before[s]))for s in sources}
    return dict(source_sha256=keys,
        geometry_wkb_hex_by_sha256={h:to_wkb(before[s]).hex()for s,h in keys.items()})


def verify_dependencies(plans,local,report,before,after,original,angle):
    """Check the combined emitted output once per prepared dependency group."""
    from shapely.geometry import Point,Polygon
    from shapely.ops import unary_union
    from .boundary_finish import sharp_points,sharp_vertices
    from .growth_bridge import meaningful_shoulders
    from .boundary_finish import new_pockets
    from .pipeline import EPS
    from src.native_inventory import ERROR_MM
    records={r['plan_index']:r for r in report['reports']};checks=[];partial=0
    source_missing={}
    for group in report['copper_budgets']['groups']:
        members=group['members'];clips=[local[i]['clip']for i in members]
        clip=unary_union(clips)
        sources={s for i in members for s in local[i]['neighbors']}
        sources.update(s for i in members for s in plans[i]['record']['source_ids'])
        ordered=[s for s in before if s in sources]
        a=polygonal(unary_union([before[s].intersection(clip)for s in ordered]))
        b=polygonal(unary_union([after[s].intersection(clip)for s in ordered]))
        floor=polygonal(unary_union([original[s].intersection(clip)for s in ordered]))
        changed=a.symmetric_difference(b)
        view=b.simplify(ERROR_MM/10,preserve_topology=True);vertices=sharp_vertices(view,angle)
        corners=[p for p in meaningful_shoulders(b,sharp_points(view,a,angle,vertices=vertices))
            if clip.boundary.distance(Point(p))>2*ERROR_MM and changed.distance(Point(p))<=2*ERROR_MM]
        # Preserve exact contribution containment before clipping/unioning.
        # Independently assembled floors can manufacture overlay slivers even
        # when every original contribution survives in its own emitted body.
        # Cache each source subtraction across overlapping dependency groups;
        # actual missing material still has to be covered by emitted neighbors.
        for s in ordered:
            if s not in source_missing:
                source_missing[s]=(original[s].difference(after[s])
                    if original[s] is not after[s] else Polygon())
        missing=polygonal(unary_union([source_missing[s].intersection(clip)
            for s in ordered if not source_missing[s].is_empty]).difference(b))
        lost=missing.area>EPS or not polygonal(missing.difference(b.buffer(ERROR_MM,quad_segs=128))).is_empty
        pockets=new_pockets(a,floor,b)
        check=dict(group=group['id'],passed=not corners and not lost and not pockets,
            new_corners_mm=corners,source_floor_loss_mm2=missing.area,new_pockets=len(pockets),
            source_floor_preserved=not lost,
            source_ids=ordered,clip_wkb_hex=to_wkb(clip).hex(),
            before_sha256=digest(to_wkb(a)),after_sha256=digest(to_wkb(b)))
        checks.append(check)
        if not check['passed']:partial+=1
        final_points=meaningful_shoulders(b,sharp_points(view,floor,angle,vertices=vertices))
        for i in members:
            record=records[i];target=Point(record['point_mm']).buffer(max(.03,2*record['height_mm']))
            remaining=[p for p in final_points if target.covers(Point(p))]
            record['final_remaining_points_mm']=remaining
            record['final_verification_scope']='COMBINED_SERIALIZED_DEPENDENCIES'
            if not remaining and record['status']=='UNRESOLVED':
                record['status']='RESOLVED_BY_COUPLED_BRIDGE'
                record['superseded_constructor_reason']=record.pop('reason',None)
            elif (remaining and record['status']=='RESOLVED_BY_COUPLED_BRIDGE'and
                    record.get('baseline_preserved')is True and
                    record.get('added_area_mm2')==record.get('removed_area_mm2')==0.):
                # A neighboring edit did not finish this pre-existing feature.
                # No correction was applied here; retain it as unresolved,
                # rather than inventing a failed material-changing repair.
                record.update(status='UNRESOLVED',reason='PREEXISTING_SHOULDER_REMAINS',
                    superseded_resolution='RESOLVED_BY_COUPLED_BRIDGE')
            elif remaining and record['status']in('BRIDGED','RESOLVED_BY_COUPLED_BRIDGE'):
                record['status']='FAILED_FINAL_DEPENDENCY_CHECK';partial+=1
    report.update(final_dependency_checks=dict(passed=partial==0,groups=checks),partial=partial,
        smoothed=sum(r['status']=='BRIDGED'for r in report['reports']),
        unresolved=sum(r['status']=='UNRESOLVED'for r in report['reports']))


def run(rows,paths,bodies,original,caps,*,material,covered,contacts,revision,
        eligibility,terminals=(),protected_voids=(),angle=10.,progress=None,carriers=None,endpoint_sections=()):
    from .growth_bridge import run as gaps
    from .shoulder_bridge import run as shoulders
    from .terminal_handoff import attachment_scopes,refresh_attachments
    started=perf_counter()
    terminals=attachment_scopes(terminals,rows,original,caps)
    intermediate,gap_changes,gap_sections,gap_report=gaps(rows,paths,bodies,original,caps,
        covered=covered,supports=contacts,maximum_transition_angle_degrees=angle,
        progress=progress,terminals=terminals,
        prepare=lambda plans:bridge_allowances(plans,material,revision,protected_voids=protected_voids))
    current=dict(material);current.update(intermediate)
    changed_routes={r:ss for r,ss in paths.items()if set(ss).intersection(gap_changes)}
    refreshed=dict(contacts)
    if changed_routes:refreshed.update(supports(rows,changed_routes,original,revision,
        with_sources=True,admitted=intermediate))
    policy=json.loads(eligibility['policy']['source_json'])
    fill=revision.context.prepared_broad_fill(revision,eligibility['large_fill_coverage_support_source_ids'],
        radius=policy['large_fill_core_radius_mm'],minimum_area=policy['minimum_large_fill_core_area_mm2'])
    native_ids={s for ss in eligibility['complete_native_route_inventory'].values()for s in ss}
    prepared={}
    def prepare(plans):
        local,finish=shoulder_dependencies(plans,current,revision,original=original,
            protected_voids=protected_voids,broad_fill=fill,native_ids=native_ids)
        prepared.update(plans=plans,local=local)
        return local,finish
    final,shoulder_changes,sections,report=shoulders(rows,paths,intermediate,original,caps,
        covered=covered,supports=refreshed,material=current,terminals=terminals,
        carriers=carriers,endpoint_sections=[dict(item,section=gap_sections.get(
            (item['source_id'],tuple(round(v,10)for v in item['endpoint_mm'])),item['section']))for item in endpoint_sections],
        maximum_transition_angle_degrees=angle,progress=progress,
        prepare=prepare)
    emitted=dict(current);emitted.update(final)
    verify_dependencies(prepared['plans'],prepared['local'],report,current,emitted,original,angle)
    changes={s:polygonal(bodies[s].symmetric_difference(final[s]))for s in
        set(gap_changes)|set(shoulder_changes)if to_wkb(bodies[s])!=to_wkb(final[s])}
    replacements=dict(gap_sections);replacements.update(sections)
    report.update(schema='t04-retained-widening-bridges/1',maximum_transition_angle_degrees=angle,
        initial_gap_phase=gap_report,shoulder_baseline_inputs=saved_inputs(intermediate,shoulder_changes),
        contact_routes_reused=len(paths)-len(changed_routes),contact_routes_refreshed=len(changed_routes),
        partial=report.get('partial',0),preserved_unresolved=True,chains=[],withdrawn_growth=[],
        deferred_terminals=refresh_attachments(terminals,emitted,refreshed,angle),local_controls=True,
        original_copper_removed_mm2=0.,
        added_copper_mm2=sum(r.get('added_area_mm2',0.)for r in report['reports']),
        removed_optional_copper_mm2=sum(r.get('removed_area_mm2',0.)for r in report['reports']),
        wall_s=perf_counter()-started)
    return final,changes,replacements,report
