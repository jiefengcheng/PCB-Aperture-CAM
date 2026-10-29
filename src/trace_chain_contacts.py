"""Geometric qualification of an exact-endpoint source chain, read-only."""
from shapely.geometry import Point
from shapely.ops import unary_union


def qualify_chain(component, geometries, neighbors):
    members = set(component['source_ids'])
    core = unary_union([geometries[sid] for sid in sorted(members)])
    contacts = sorted((r for r in neighbors if r['source_id'] not in members
                       and core.intersects(r['geometry'])), key=lambda r:r['source_id'])
    fixed = [r for r in contacts if r['kind'] not in ('segment', 'arc')]
    fixed_union = unary_union([r['geometry'] for r in fixed])
    exposed = core.difference(fixed_union)
    other_copper = unary_union([r['geometry'] for r in contacts])
    independently_exposed = core.difference(other_copper)
    terminals = [Point(*map(float, p)) for p in component['terminal_points_decimal_mm']]
    terminal_hits = [[r['source_id'] for r in fixed if r['geometry'].covers(p)] for p in terminals]
    terminal_ids = {sid for row in terminal_hits for sid in row}
    terminal_union = unary_union([r['geometry'] for r in fixed if r['source_id'] in terminal_ids])
    interior_trace = []
    interior_fixed = []
    for r in contacts:
        intersection = core.intersection(r['geometry'])
        if r['kind'] in ('segment', 'arc'):
            if not intersection.difference(terminal_union).is_empty:
                interior_trace.append(r['source_id'])
        elif r['source_id'] not in terminal_ids:
            if not intersection.difference(terminal_union).is_empty:
                interior_fixed.append(r['source_id'])
    reasons = list(component['unresolved_reasons'])
    if independently_exposed.is_empty:
        status = 'COVERED_SOURCE_TRACE_NO_INDEPENDENT_EXPOSED_ROUTE'
    else:
        if len(terminals) != 2 or not all(terminal_hits):
            reasons.append('LAND_TERMINALS_NOT_ESTABLISHED')
        if interior_trace:
            reasons.append('INTERIOR_TRACE_CONTACT_REQUIRES_JUNCTION_SCOPE')
        if interior_fixed:
            reasons.append('INTERMEDIATE_FIXED_COPPER_CONTACT')
        status = 'UNRESOLVED_TRACE_DEFINITION' if reasons else 'SOURCE_CHAIN_GEOMETRICALLY_QUALIFIED_FOR_WIDTH_FEASIBILITY'
    return dict(status=status, unresolved_reasons=sorted(set(reasons)),
        original_trace_union_area_mm2=core.area, exposed_outside_fixed_copper_area_mm2=exposed.area,
        exposed_outside_all_other_source_copper_area_mm2=independently_exposed.area,
        terminal_fixed_source_ids=terminal_hits,
        interior_trace_source_ids=interior_trace, intermediate_fixed_source_ids=interior_fixed,
        contact_source_ids=[r['source_id'] for r in contacts],
        interpretation='Actual source copper intersections; no electrical intent or component-label exemption',
        width_construction='NOT_RUN')
