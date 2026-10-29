"""Source-ID coverage of the existing T02 inventory and trace-work records.

Record membership selects a candidate, never establishes an actual defect or
electrical applicability. Historical records are retained without reclassification.
"""
from collections import defaultdict


def focused_rectangle_coverage(decisions, future_work, previous_decisions=()):
    eligible = {}
    for row in decisions:
        sid = row['source_id']
        if sid in eligible:
            raise ValueError('DUPLICATE_RECTANGLE_SOURCE')
        eligible[sid] = row
    evidence = defaultdict(list)
    for collection in ('clearance_issues', 'items'):
        for ordinal, row in enumerate(future_work[collection], 1):
            sid = row['rectangle_source_id']
            if sid not in eligible:
                raise ValueError('TRACE_WORK_RECTANGLE_NOT_IN_ELIGIBLE_SET')
            evidence[sid].append({
                'collection': collection, 'ordinal': ordinal,
                'trace_source_id': row['trace_source_id'],
                'classification': row.get('issue_type', row.get('interaction_class')),
                'original_record': row,
            })
    prior = {r['source_id']: r['key'] for r in previous_decisions}
    return [{
        'key': f'R{ordinal:03d}', 'source_id': sid,
        'selected': sid in evidence,
        'selection_reason': ('EXISTING_TRACE_WORK_SOURCE_REFERENCE' if sid in evidence
                             else 'CONTEXT_ONLY_NO_TRACE_WORK_REFERENCE'),
        'previous_eleven_site_key': prior.get(sid),
        'trace_work_references': evidence.get(sid, []),
    } for ordinal, sid in enumerate(sorted(eligible), 1)]
