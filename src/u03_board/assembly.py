"""Group-level search assembly; the source constructor and full checker are unchanged.

State follows the last *assembled* vector, including rejected trials. Every call
compares the complete supplied vector, so rejection, rollback and final-neighbor
proofs cannot retain stale geometry. Final materialization uses model.build.
"""
import math


class GroupCandidateAssembly:
    def __init__(self, model):
        self.model = model
        self.ids = sorted(model.chains)
        self.members = {gid: [] for gid in model.group_ids}
        for index, sid in enumerate(self.ids):
            self.members[model.assignment[sid]].append((index, sid))
        self.scales = {}
        self.rows = [None] * len(self.ids)
        self.calls = self.updated_groups = self.updated_routes = 0

    def traces(self, scales):
        if set(scales) != self.model.group_ids:
            raise ValueError('EXACT_GROUP_SCALE_VECTOR_REQUIRED')
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 1 <= v <= 1.5
               for v in scales.values()):
            raise ValueError('INVALID_COMPLETE_TRACE_SCALE')
        changed = [g for g in scales if g not in self.scales or scales[g] != self.scales[g]]
        pending = []
        for gid in changed:
            for index, sid in self.members[gid]:
                record, _, _, core, _, envelope = self.model.construct(sid, scales[gid])
                pending.append((index, dict(id=sid, original=core, candidate=envelope,
                    verified_original_width_mm=record['verified_original_width_mm'])))
        # Publish only after all constructors succeed. Previously returned lists
        # and their row records remain unchanged when a later trial is assembled.
        for index, row in pending:
            self.rows[index] = row
        self.scales = dict(scales)
        self.calls += 1
        self.updated_groups += len(changed)
        self.updated_routes += len(pending)
        return list(self.rows)
