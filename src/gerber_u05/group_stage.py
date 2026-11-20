"""Incremental, bounded direct-construction entry using existing T04 intake.

Publishes group-interior recipes, not a completed T04 scene. Unimplemented
hybrid assembly is explicit; old audited profile results cannot qualify it.
"""
from pathlib import Path
from time import perf_counter
from src import component_clearance as cc, source_channel_scope as sc,pin_separation as pin
from . import pipeline as p
from .source_roles import prepare_or_load, project
from .limiting_growth_v2 import catalogue
from .group_boundaries import SourceBoundaries
from .group_profile import plan, transition_guard, route_join_plan


def native_board_selection(native):
    ids={v['path_id']for v in native['admitted']}
    dispositions=[(d['path']['path_id'],d.get('disposition'))for d in native['paths']]
    if (len(ids)!=len(native['admitted'])or len({k for k,_ in dispositions})!=len(dispositions)or
            any(v not in('KEEP_FULLY_COVERED','ADMIT_COMPLETE_GERBER_ROUTE')for _,v in dispositions)or
            {k for k,v in dispositions if v=='ADMIT_COMPLETE_GERBER_ROUTE'}!=ids):
        raise ValueError('T04_GROUP_BOARD_DIAGNOSTIC_NATIVE_INVENTORY_UNACCOUNTED')
    if not ids:raise ValueError('T04_GROUP_BOARD_DIAGNOSTIC_EMPTY_NATIVE_INVENTORY')
    return sorted(ids),dispositions


def run(store, scene, *, route_ids, settings, rule):
    board_diagnostic=(rule['scope']=='FULL_BOARD_DIAGNOSTIC' and rule.get('full_board_diagnostic')is True)
    if board_diagnostic:
        if route_ids is not None or not rule.get('hybrid_components'):
            raise ValueError('T04_GROUP_BOARD_DIAGNOSTIC_COMPLETE_NATIVE_SELECTION_REQUIRED')
    elif rule['scope'] != 'BOUNDED' or not route_ids:
        raise ValueError('T04_GROUP_INCREMENT_BOUNDED_ONLY')
    started = perf_counter();loaded = p.operands(store, scene)
    rows, current, original = loaded
    context = sc.ACTIVE if sc.ACTIVE is not None else cc.ACTIVE
    if context is None:raise ValueError('T04_SOURCE_OWNER_CONTEXT_REQUIRED')
    roles, native, source_binding = prepare_or_load(rule['source_preparation'], store, scene, loaded, context.index)
    admission = project(native, roles)
    native_ids = {v['path_id'] for v in native['admitted']}
    if board_diagnostic:
        route_ids,dispositions=native_board_selection(native)
    if len(set(route_ids)) != len(route_ids) or not set(route_ids) <= native_ids:
        raise ValueError('T04_NATIVE_REQUESTED_PATH_CHANGED')
    native_paths = {v['path_id']: v['source_ids'] for v in admission['admitted'] if v['path_id'] in route_ids}
    rule = dict(rule, role_table_sha256=p.digest((Path(rule['source_preparation'])/'ROLES.json.gz').read_bytes()))
    from .durable_groups import prepare as durable_members,source_catalogue
    from .covered_traces import prepare as covered_traces
    artifact_root=p.ROOT/'out/lacie_work/source_artifacts'
    tick=perf_counter()
    straight,curves,group_binding,relationship_preparation=source_catalogue(
        rule.get('relationship_cache_root',artifact_root/'t04_parallel_relationships'),
        store,scene,rows,admission,roles,rule,catalogue)
    membership,member_binding,member_hit=durable_members(rule.get('member_cache',artifact_root/'t04_parallel_members'),straight,curves,group_binding)
    member_preparation=dict(wall_s=perf_counter()-tick,cache_hit=member_hit,relationships=relationship_preparation)
    paths,coverage,coverage_preparation=covered_traces(rule.get('coverage_cache',artifact_root/'t04_trace_coverage'),scene,rows,current,native_paths)
    from .arc_catalogue import prepare as maximal_arcs
    tick=perf_counter()
    arc_members,arc_binding,arc_hit=maximal_arcs(rule.get('arc_member_cache',artifact_root/'t04_maximal_arcs'),straight,curves,member_binding)
    arc_preparation=dict(wall_s=perf_counter()-tick,cache_hit=arc_hit)
    protected=[]if pin.ACTIVE is None else [(slot.slot_id,slot.domain)for slot in pin.ACTIVE.slots]
    # Straight members are frozen first. Later residual growth must respect
    # them; reserving hypothetical future motion here suppresses legal faces.
    anchored=bool(rule.get('hybrid_components'))
    boundary = SourceBoundaries(current, roles, rows, {s for ss in paths.values() for s in ss},protected_domains=protected,
                                reserve_mutable_growth=not anchored,defer_close_sources=anchored)
    active_sources={s for members in paths.values()for s in members}
    whole_exposed_routes=[r for r,ss in native_paths.items()if set(ss)<=active_sources]
    if anchored or not whole_exposed_routes:
        from .maximal_group_plan import MaximalGroups
        model=MaximalGroups(straight,membership,list(paths)if anchored else[],settings,boundary,
                            mutable_sources=active_sources)
    else:model=None
    result = model.plan()if model is not None else plan(straight, whole_exposed_routes, settings, boundaries=boundary)
    initial_planning_wall = result['planning_wall_s']
    joins = route_join_plan(rows, paths, result, settings)
    # Propagated endpoint bounds are numerical constructor inputs, not a
    # second geometry trial. Re-solve the same group model under those bounds.
    caps = {r['run_id']: min((joins['selected_width_caps_mm'][s] for s in r['source_ids']
                              if s in joins['selected_width_caps_mm']), default=float('inf'))
            for r in straight['runs']}
    result = model.plan(width_caps=caps)if model is not None else plan(straight,whole_exposed_routes,settings,boundaries=boundary,width_caps=caps)
    result['planning_wall_s'] += initial_planning_wall
    from .continuous_profile import source_profiles
    result['continuous_source_profiles']=source_profiles(rows,paths,result)
    result.update(input_binding=rule['input_binding'], group_binding=group_binding,requested_routes=list(route_ids),
                  full_member_catalogue=membership,
                  full_member_catalogue_binding=member_binding,
                  maximal_curve_catalogue=arc_members,maximal_curve_catalogue_binding=arc_binding,
                  arc_catalogue_preparation=arc_preparation,
                  catalogue_preparation=member_preparation,
                  covered_trace_projection=coverage,coverage_preparation=coverage_preparation,
                  native_trace_source_ids_by_route=native_paths,
                  source_preparation_binding=source_binding,
                  growth_source_ids_by_route=paths,
                  local_join_width_plan=joins,
                  source_width_targets_mm=joins['selected_width_caps_mm'],
                  transition_outlier_guard=transition_guard(settings.maximum_total_width_increase_mm, .025),
                  summary=dict(routes=len(paths),native_trace_routes=len(native_paths),
                               covered_trace_sources=len(coverage['covered_source_ids']),
                               keep_covered_routes=len(coverage['keep_routes']),source_boundary_queries=boundary.queries,
                               direct_interiors=len(result['groups']), residual_groups=len(result['residual_groups'])),
                  residual_work=dict(native_routes=sorted(paths),
                      policy='EXISTING_GROWTH_AND_VERIFICATION_REQUIRED_FOR_UNRESOLVED_PARTS',
                      disposition='NOT_RUN; GROUP_INTERIOR_INCREMENT_ONLY'),
                  stage_construction_wall_s=perf_counter()-started)
    # No completed scene, native acceptance verdict or inherited proof tip.
    if rule.get('hybrid_components'):
        from .group_components import run as components
        result['phase_order']=['STRAIGHT_GROUPS','ARC_GROUPS','DEFAULT_SEARCH_AND_VERIFY']
        result['straight_priority']='FROZEN_BEFORE_ARC_AND_DEFAULT_GROWTH; NO_REVERSE_CAP_REDUCTION'
        result['corner_smoothing']=True
        if rule.get('residual_end_matching'):
            # Both flags are explicit opt-ins. Chain matching extends the old
            # nominal-only reference path; it does not enable itself merely
            # because a caller supplies residual_chain_matching alone.
            result['residual_end_matching']=dict(deviation=rule.get('residual_end_deviation',.1))
            if rule.get('residual_chain_matching'):result['residual_end_matching']['chain_matching']=True
        if rule.get('wide_end_trimming'):result['wide_end_trimming']=True
        result['hybrid_components']=components(rows,current,original,roles,paths,result,settings,context,
                                               progress=rule.get('progress'),continuous=True,coherent_pose=True)
        result['continuous_source_profiles']=source_profiles(rows,paths,result)
        result['stage_construction_wall_s']=perf_counter()-started
    if board_diagnostic:
        result.update(scope='FULL_BOARD_DIAGNOSTIC',full_board_run=True,
                      complete_native_route_inventory=True,
                      native_route_dispositions=[dict(route_id=k,disposition=v,
                          source_role=admission['source_role_dispositions'].get(k,'COVERED_NATIVE_KEEP'))
                          for k,v in dispositions])
        result['hybrid_components']['full_board_run']=True
    return result
