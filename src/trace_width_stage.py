"""T04 pure group model: admission and source-offset construction, no I/O/search.

Membership is supplied by a source-qualified caller. This module validates its
partition; it does not infer parallelism or electrical connectivity from labels.
"""
import functools
import math
from .source_offset_width import construct_source_offset_width


def validate_width_partition(chains, groups, *, fixed_source_ids=()):
    if not chains or not groups:
        raise ValueError('COMPLETE_TRACES_AND_GROUPS_REQUIRED')
    assignment = {}
    group_ids = set()
    for group in groups:
        gid = group['group_id']
        if gid in group_ids or not group['members']:
            raise ValueError('DUPLICATE_OR_EMPTY_WIDTH_GROUP')
        group_ids.add(gid)
        for cid in group['members']:
            if cid not in chains or cid in assignment:
                raise ValueError('TRACE_GROUP_PARTITION_INVALID')
            assignment[cid] = gid
    if set(assignment) != set(chains):
        raise ValueError('TRACE_GROUP_PARTITION_INCOMPLETE')
    represented = set()
    for chain in chains.values():
        ids = chain['source_ids']
        if not ids or len(set(ids)) != len(ids) or represented.intersection(ids):
            raise ValueError('TRACE_SOURCE_PARTITION_INVALID')
        represented.update(ids)
    if represented.intersection(fixed_source_ids):
        raise ValueError('PROTECTED_SOURCE_SELECTED_FOR_WIDTH')
    return assignment, represented


class SourceWidthStage:
    """Build one uniform source family per complete trace; cohorts share scale."""
    def __init__(self, raw, chains, groups, meta, blobs, *, fixed_source_ids=()):
        self.assignment, self.represented = validate_width_partition(
            chains, groups, fixed_source_ids=fixed_source_ids)
        self.chains = chains
        self.group_ids = set(self.assignment.values())
        self._construct = functools.lru_cache(maxsize=800)(
            lambda cid, factor: construct_source_offset_width(
                raw, chains[cid], meta, blobs, factor))

    def construct(self, cid, factor):
        if cid not in self.chains or type(factor) not in (int, float) or not math.isfinite(factor) or not 1 <= factor <= 1.5:
            raise ValueError('INVALID_COMPLETE_TRACE_SCALE')
        return self._construct(cid, factor)

    def build(self, scales):
        if set(scales) != self.group_ids:
            raise ValueError('EXACT_GROUP_SCALE_VECTOR_REQUIRED')
        traces, records, envelopes, nominal = [], [], {}, {}
        for cid in sorted(self.chains):
            record, np, ep, core, _, envelope = self.construct(
                cid, scales[self.assignment[cid]])
            traces.append(dict(id=cid, original=core, candidate=envelope,
                               verified_original_width_mm=record['verified_original_width_mm']))
            records.append(record)
            envelopes.update(ep)
            nominal.update(np)
        return traces, records, envelopes, nominal
