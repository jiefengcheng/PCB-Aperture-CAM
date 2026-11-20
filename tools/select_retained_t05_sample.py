#!/usr/bin/env python3
"""Select a reproducible, varied, bounded T05 sample without running geometry."""
import argparse
import hashlib
import json
from pathlib import Path
import random

MAX_SAMPLE = 12


def select(stage, sizes, *, count=6, seed=0, route_ids=()):
    """Cover distinct outcomes before adding seeded examples from the remainder.

    The cap is deliberate: this performance route cannot become a whole-board
    evaluation. Selection order is restored to the retained decision order so
    earlier accepted additions keep their original meaning during replay.
    """
    rows = stage['candidate']['decisions']
    by_id = {d['source_id']: d for d in rows}
    if len(by_id) != len(rows):
        raise ValueError('DUPLICATE_RETAINED_ROUTE')
    if type(count) is not int or not 1 <= count <= MAX_SAMPLE:
        raise ValueError('LOCAL_SAMPLE_COUNT_MUST_BE_1_TO_12')
    rng = random.Random(seed)
    selected = {}
    if route_ids:
        if len(set(route_ids)) != len(route_ids) or len(route_ids) > MAX_SAMPLE:
            raise ValueError('INVALID_EXPLICIT_ROUTE_SELECTION')
        for sid in route_ids:
            if sid not in by_id:
                raise ValueError('UNKNOWN_RETAINED_ROUTE:' + sid)
            selected[sid] = 'explicit'
    else:
        grown = [d for d in rows if d['status'] == 'GROWN']
        ordered = sorted(grown, key=lambda d: (sizes[d['source_id']], d['source_id']))
        # Extremes expose large overlays and small geometry overhead. Other
        # buckets rotate with the seed; unavailable categories stay explicit.
        buckets = [
            ('large_addition', ordered[-1:]),
            ('small_addition', ordered[:1]),
            ('reduced_radius', [d for d in grown if d['scale'] < 1]),
            ('multiple_attachments', [d for d in grown if len(d['land_ids']) > 1]),
            ('blocked', [d for d in rows if d.get('reason') == 'BLOCKED_REQUIRED_TREATMENT']),
            ('already_satisfied', [d for d in rows if d.get('reason') == 'PREDECESSOR_ALREADY_SATISFIES']),
            ('no_contact', [d for d in rows if d.get('reason') == 'NO_DECLARED_SOURCE_CONTACT']),
        ]
        for label, candidates in buckets:
            candidates = list(candidates)
            if label not in ('large_addition', 'small_addition'):
                rng.shuffle(candidates)
            for row in candidates:
                if len(selected) >= count:
                    break
                if row['source_id'] not in selected:
                    selected[row['source_id']] = label
                    break
        remaining = [d for d in rows if d['source_id'] not in selected]
        rng.shuffle(remaining)
        for row in remaining:
            if len(selected) >= count:
                break
            selected[row['source_id']] = 'seeded_extra'
    if not selected or len(selected) >= len(rows):
        raise ValueError('WHOLE_BOARD_SELECTION_FORBIDDEN')
    return dict(schema='pcb-cam/t05-local-sample/1', seed=seed,
                requested_count=len(route_ids) if route_ids else count,
                maximum_count=MAX_SAMPLE, retained_route_count=len(rows),
                routes=[dict(source_id=d['source_id'], category=selected[d['source_id']],
                             status=d['status'], reason=d.get('reason'),
                             scale=d.get('scale'), attachments=len(d['land_ids']),
                             patch_bytes=sizes.get(d['source_id'], 0))
                        for d in rows if d['source_id'] in selected],
                whole_board_allowed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--count', type=int, default=6)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--route-id', action='append', default=[])
    args = parser.parse_args()
    raw = args.checkpoint.read_bytes()
    stage = json.loads(raw)
    sizes = {}
    for row in stage['candidate']['decisions']:
        if row['status'] != 'GROWN':
            continue
        ref = row['patch_ref']
        # Only canonical content-addressed geometry names are accepted.
        expected = ref['sha256']
        if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('INVALID_GEOMETRY_HASH')
        if ref['artifact_id'] != 'geometry:' + expected:
            raise ValueError('INVALID_GEOMETRY_REFERENCE')
        body = (args.artifacts / ref['artifact_id']).read_bytes()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError('GEOMETRY_ARTIFACT_CHANGED')
        sizes[row['source_id']] = len(body)
    result = select(stage, sizes, count=args.count, seed=args.seed, route_ids=args.route_id)
    result['raw_checkpoint_sha256'] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
