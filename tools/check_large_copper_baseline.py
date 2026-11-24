"""Read-only source-baseline check, usable on macOS and Linux.

This verifies input bytes and optionally the existing maintained-parser intake.
It does not execute trimming, validate saved geometry, or acknowledge a viewer.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'baselines/large_copper_0.2.0'
SOURCE_SHA256 = '207a51318f103190a4d61e76f4a0457fcfd11fd3db560c9439dd2f5f460f9b90'


def check(baseline=BASELINE, *, parse=False):
    sys.path.insert(0, str(ROOT))
    from tools.preflight import verify_manifest
    assets = verify_manifest()
    baseline = Path(baseline)
    reference = json.loads((baseline / 'reference.json').read_bytes())
    if (reference.get('schema') != 'large-copper-reference/1'
            or reference['source']['file'] != 'source.gbr'
            or reference['source']['sha256'] != SOURCE_SHA256):
        raise ValueError('BASELINE_REFERENCE_CHANGED')
    source = baseline / 'source.gbr'
    if source.is_symlink():
        raise ValueError('BASELINE_SOURCE_SYMLINK_REJECTED')
    raw = source.read_bytes()
    if (hashlib.sha256(raw).hexdigest() != SOURCE_SHA256
            or len(raw) != reference['source']['bytes']):
        raise ValueError('BASELINE_SOURCE_BYTES_CHANGED')
    answer = dict(status='PASS_SOURCE_BYTES_ONLY', source_sha256=SOURCE_SHA256,
                  source_bytes=len(raw), assets_verified=assets, trimming='NOT_RUN', geometry_parity='NOT_RUN',
                  native_display='NOT_RUN')
    if parse:
        import gerbonara
        import numpy
        import shapely
        from src.gerber_u05.gerber_source_profile import parse_source
        versions = dict(gerbonara=gerbonara.__version__, numpy=numpy.__version__,
                        shapely=shapely.__version__, geos=shapely.geos_version_string)
        if any(reference['runtime'][key] != value for key, value in versions.items()):
            raise ValueError('BASELINE_PARSER_ENVIRONMENT_CHANGED:' + json.dumps(versions))
        parsed, parser, oracle = parse_source(raw)
        if (len(parsed.objects) != reference['source']['source_occurrences']
                or len(parser.spans) != len(parsed.objects)
                or any(not obj.polarity_dark for obj in parsed.objects)):
            raise ValueError('BASELINE_SOURCE_INTAKE_CHANGED')
        answer.update(status='PASS_SOURCE_INTAKE_ONLY', versions=versions,
                      source_occurrences=len(parsed.objects), coordinate_oracle=oracle)
    return answer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parse', action='store_true', help='Also run the existing source parser; no treatment')
    args = parser.parse_args()
    try:
        print(json.dumps(check(parse=args.parse), sort_keys=True))
    except Exception as error:
        print(json.dumps(dict(status='FAIL', error=repr(error))), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
