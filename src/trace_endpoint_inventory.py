"""Read-only exact-source endpoint components; never net-intent proof.

The inventory expands crop seeds through the complete source endpoint graph.
Branched or mixed-width components are explicit unresolved trace definitions,
not silently divided into easier width-growth targets.
"""
from collections import defaultdict
from decimal import Decimal
import math


def endpoint_components(rows, seed_ids):
    objects = {r['source_id']:r for r in rows}
    if len(objects) != len(rows) or not set(seed_ids) <= objects.keys():
        raise ValueError('INVALID_TRACE_IDENTITIES')
    endpoints = defaultdict(set)
    for sid, r in objects.items():
        if (not math.isfinite(r['width_mm']) or r['width_mm'] <= 0
                or len(r['endpoints_decimal_mm']) != 2):
            raise ValueError('INVALID_ORIGINAL_TRACE')
        for xy in r['endpoints_decimal_mm']:
            key = tuple(Decimal(v) for v in xy)
            if len(key) != 2 or not all(v.is_finite() for v in key):
                raise ValueError('INVALID_ENDPOINT')
            endpoints[key].add(sid)
    unseen = set(seed_ids)
    result = []
    while unseen:
        todo = [min(unseen)]
        members = set()
        while todo:
            sid = todo.pop()
            if sid in members:
                continue
            members.add(sid)
            for xy in objects[sid]['endpoints_decimal_mm']:
                key = tuple(Decimal(v) for v in xy)
                todo.extend(sorted(endpoints[key]-members, reverse=True))
        unseen -= members
        nodes = {tuple(Decimal(v) for v in xy)
                 for sid in members for xy in objects[sid]['endpoints_decimal_mm']}
        branches = sorted(k for k in nodes if len(endpoints[k]) > 2)
        terminals = sorted(k for k in nodes if len(endpoints[k]) == 1)
        widths = sorted({objects[sid]['width_mm'] for sid in members})
        reasons = []
        if branches:
            reasons.append('BRANCHED_ENDPOINT_COMPONENT')
        if len(widths) != 1:
            reasons.append('MIXED_ORIGINAL_WIDTHS')
        if len(terminals) != 2:
            reasons.append('NOT_A_TWO_TERMINAL_CHAIN')
        result.append(dict(source_ids=sorted(members), seed_ids=sorted(set(seed_ids)&members),
            original_widths_mm=widths,
            terminal_points_decimal_mm=[[str(v) for v in k] for k in terminals],
            branch_points_decimal_mm=[[str(v) for v in k] for k in branches],
            unresolved_reasons=reasons,
            status='UNRESOLVED_TRACE_DEFINITION' if reasons else 'SOURCE_ENDPOINT_CHAIN_REQUIRES_LAND_AND_CONTACT_CHECKS',
            contact_semantics='EXACT_NATIVE_ENDPOINT_ADJACENCY_ONLY; no electrical/net claim'))
    return sorted(result, key=lambda r:r['source_ids'])
