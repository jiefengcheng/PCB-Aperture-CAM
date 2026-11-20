"""One T04 operation: source-built baseline, then additive two-face refinement.

Only the first phase may edit bulk or choose a route pose. Its freshly checked
output supplies an immutable geometry floor to the second phase. Both phases
execute the unchanged proposal predicates and complete nominal/envelope gates.
"""
from time import perf_counter
from . import pipeline as p
from .profile_floor import CopperFloor


def run(store, scene, *, route_ids=None, settings=None, rule):
    if any(k in rule for k in ('baseline_seed', 'baseline_seed_data', 'side_specific_seed', 'copper_floor')):
        raise ValueError('T04_SOURCE_BUILT_STAGE_REFERENCE_INPUT_FORBIDDEN')
    if rule.get('group_construction'):
        from .group_stage import run as construct_groups
        return construct_groups(store, scene, route_ids=route_ids, settings=settings, rule=rule)
    start = perf_counter()
    common = dict(rule)
    first = p.run_t04(store, scene, route_ids=route_ids, limiting_rule=dict(common, source_built_25=True))
    first_wall = perf_counter()-start
    first_ref = store.put_json('t04-profile-baseline', first)
    floor_start = perf_counter()
    floor = CopperFloor.accepted(store, scene, first)
    floor_seed, floors, bulk = floor.load(common['input_binding'], first['limiting_construction']['growth_source_ids_by_route'])
    floor_wall = perf_counter()-floor_start
    side_start = perf_counter()
    second = p.run_t04(store, scene, route_ids=route_ids, limiting_rule=dict(common, copper_floor=floor))
    final = store.get_json(second['output_scene_ref'], kind='scene')
    _, material, _ = p.operands(store, final)
    losses = [r for r, g in dict(floors, **bulk).items()
              if not (material[r].equals_exact(g, 0) or material[r].covers(g))]
    poses = second['limiting_construction']['published_routes']
    if losses or any(poses[r]['translation_mm'] != floor_seed['routes'][r]['translation_mm'] for r in floors):
        raise ValueError('T04_SOURCE_BUILT_BASELINE_COPPER_OR_POSE_REGRESSED:'+str(losses[:5]))
    return dict(second, source_built_profile=dict(schema='t04-source-built-side-growth/1',
        baseline_stage_ref=first_ref, floor_sha256=floor.sha256, baseline_wall_s=first_wall,
        floor_binding_wall_s=floor_wall, side_wall_s=perf_counter()-side_start,
        operation_wall_s=perf_counter()-start, routes_preserved=len(floors), bulk_sources_preserved=len(bulk),
        all_baseline_copper_preserved=True, centerlines_preserved_in_side_phase=True,
        native_proof_reuse=False, completed_t04_input=False, replay=False))
