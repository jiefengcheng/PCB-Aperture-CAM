"""Disjoint primary parallel cohorts; hard trace identities remain indivisible.

Parallel proximity is not a global equality graph. A source unit may occur in
several local bundle candidates, but receives one primary cohort. All omitted
parallel relationships remain clearance interactions in the geometry checker.
"""
import math
from .parallel_trace_relations import relation_groups


def choose_primary_cohorts(unit_ids, candidates):
    ids=sorted(unit_ids)
    if len(ids)!=len(set(ids)):raise ValueError('DISTINCT_HARD_UNITS_REQUIRED')
    allowed=set(ids);remaining=set(ids);result=[]
    for c in candidates:
        members=set(c['members'])
        if (not math.isfinite(c['score']) or c['score']<=0 or not members<=allowed
                or any(len(e)!=2 or e[0]==e[1] or not set(e)<=members for e in c['edges'])):
            raise ValueError('VALID_SOURCE_BOUND_COHORT_REQUIRED')
    ordered=sorted(candidates,key=lambda r:(r.get('priority',0),-r['score'],r['candidate_id']))
    for c in ordered:
        live=sorted(remaining.intersection(c['members']))
        if len(live)<2:continue
        edges=[tuple(e) for e in c['edges'] if e[0] in live and e[1] in live]
        for members in relation_groups(live,edges):
            if len(members)<2:continue
            result.append(dict(units=members,primary_candidate_id=c['candidate_id'],score=c['score']))
            remaining.difference_update(members)
    result.extend(dict(units=[u],primary_candidate_id=None,score=0) for u in sorted(remaining))
    flat=[u for r in result for u in r['units']]
    if sorted(flat)!=ids:raise ValueError('PRIMARY_COHORT_ACCOUNTING_FAILURE')
    return sorted(result,key=lambda r:r['units'])


def station_spacing_links(evidence, *, max_neighbor_ratio=2.):
    """Do not bridge separate local bundles across a much larger gap.

    This is a selection heuristic only. Rejected membership links remain
    full-scene clearance interactions, not omitted copper.
    """
    if not math.isfinite(max_neighbor_ratio) or max_neighbor_ratio<1:raise ValueError('VALID_SPACING_SELECTION_RATIO_REQUIRED')
    kept=[];rejected=[]
    for row in evidence:
        gap=row['surface_gap_mm']
        if not math.isfinite(gap) or gap<=0:raise ValueError('POSITIVE_SOURCE_CROSS_SECTION_GAP_REQUIRED')
        pair={row['port_a'],row['port_b']};near=[]
        for other in evidence:
            if {other['port_a'],other['port_b']}==pair:continue
            if pair.intersection((other['port_a'],other['port_b'])):near.append(other['surface_gap_mm'])
        if near and gap>max_neighbor_ratio*min(near):rejected.append(row)
        else:kept.append(row)
    return kept,rejected
