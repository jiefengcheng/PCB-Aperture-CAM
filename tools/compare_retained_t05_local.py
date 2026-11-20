#!/usr/bin/env python3
"""Compare bounded T05 replays; a local PASS never means whole-board PASS."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def compare(baseline, candidate):
    cases = (Path(baseline), Path(candidate))
    profiles = [read(case / 'PROFILE.json') for case in cases]
    seals = [read(case / 'SEAL.json') for case in cases]
    # Input custody and ordered obligations must match; source code may differ.
    for field in ('original', 'scope', 'checkpoint_sha256',
                  'raw_checkpoint_sha256', 'entry_files'):
        require(seals[0][field] == seals[1][field], 'INPUT_CHANGED:' + field)
    for case, profile, seal in zip(cases, profiles, seals):
        require(profile['status'] == 'PASS', 'LOCAL_REPLAY_FAILED')
        require(profile['full_board_t05_evaluations'] == profile['search_calls'] == 0,
                'BOUNDED_SCOPE_EXCEEDED')
        require(0 < len(profile['selected']) <= 12, 'BOUNDED_SELECTION_REQUIRED')
        require(profile['selected'] == [w['route'] for w in profile['witnesses']],
                'WITNESS_COVERAGE_CHANGED')
        require(len(set(profile['selected'])) == len(profile['selected']),
                'DUPLICATE_ROUTE')
        require(all(w.get('replay_passed', w.get('check', {}).get('passed'))
                    for w in profile['witnesses']),
                'LOCAL_CHECK_FAILED')
        if 'sample_sha256' in profile:
            sample = read(case / 'SAMPLE.json')
            require(hashlib.sha256((case / 'SAMPLE.json').read_bytes()).hexdigest()
                    == profile['sample_sha256'], 'SAMPLE_BYTES_CHANGED')
            require(sample['whole_board_allowed'] is False and
                    len(profile['selected']) < sample['retained_route_count'],
                    'WHOLE_BOARD_SELECTION_FORBIDDEN')
            require(profile['selected'] == [r['source_id'] for r in sample['routes']],
                    'SAMPLE_COVERAGE_CHANGED')
        require(hashlib.sha256(canonical(profile['witnesses'])).hexdigest()
                == profile['witness_sha256'], 'WITNESS_HASH_CHANGED')
        for field in ('scope', 'checkpoint_sha256', 'raw_checkpoint_sha256'):
            require(profile[field] == seal[field], 'PROFILE_BINDING_CHANGED:' + field)
        require(hashlib.sha256((case / 'profile_local.py').read_bytes()).hexdigest()
                == profile['profiler_sha256'], 'PROFILER_BYTES_CHANGED')
        seconds = profile['local_seconds']
        require(type(seconds) in (float, int) and math.isfinite(seconds) and seconds > 0,
                'INVALID_TIMING')
    for field in ('selected', 'witnesses', 'witness_sha256', 'python', 'shapely',
                  'geos', 'profiler_sha256'):
        require(profiles[0][field] == profiles[1][field], 'COMPARISON_CHANGED:' + field)
    require(profiles[0].get('sample_sha256') == profiles[1].get('sample_sha256'),
            'SAMPLE_SELECTION_CHANGED')
    before, after = [p['local_seconds'] for p in profiles]
    return dict(status='PASS', scope=profiles[0]['scope'],
                witness_sha256=profiles[0]['witness_sha256'],
                checkpoint_sha256=seals[0]['checkpoint_sha256'],
                baseline_seconds=before, candidate_seconds=after,
                reduction_percent=100 * (before - after) / before,
                speedup=before / after, full_board_speedup='NOT_MEASURED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    try:
        result = compare(args.baseline, args.candidate)
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps(dict(status='INVALID_INPUT', reason=str(error))))
        return 2
    except ValueError as error:
        print(json.dumps(dict(status='FAIL', reason=str(error))))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
