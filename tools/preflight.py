#!/usr/bin/env python3
"""Stdlib-only asset integrity and coupon-specific smoke test; NOT Gerber validation."""
from pathlib import Path
import hashlib, json, re, argparse

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets'
BEFORE=ASSETS/'observed_before'


def verify_manifest():
    lines=(ROOT/'contracts/asset_manifest.sha256').read_text().splitlines()
    expected=set()
    for line in lines:
        digest,sep,rel=line.partition('  ')
        if not sep or not re.fullmatch(r'[0-9a-f]{64}',digest):
            raise AssertionError(f'bad manifest entry: {line!r}')
        path=ROOT/rel
        assert rel.startswith('assets/'),rel
        if not path.is_file():
            raise AssertionError(f'asset missing: {rel}')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise AssertionError(f'asset changed: {rel}')
        expected.add(rel)
    actual={p.relative_to(ROOT).as_posix() for p in ASSETS.rglob('*') if p.is_file()}
    if expected!=actual:
        raise AssertionError(f'asset inventory mismatch: extra={sorted(actual-expected)},missing={sorted(expected-actual)}')
    return len(expected)


def positions():
    a={}
    for case in ('before','candidate'):
        j=json.loads((ASSETS/'starter'/'fixtures'/case/'geometry.json').read_text())
        pads={item['id']:item for item in j['objects'] if item['kind']=='pad'}
        p=pads['P1']
        aperture=next(item for item in j['apertures'] if item['id']=='A1')
        a[case]={'pad_x_mm':p['cx'],'pad_y_mm':p['cy'],'aperture_x_mm':aperture['cx']}
    assert a['before']=={'pad_x_mm':20.35,'pad_y_mm':20.0,'aperture_x_mm':20.0}
    assert a['candidate']=={'pad_x_mm':20.05,'pad_y_mm':20.0,'aperture_x_mm':20.0}
    b=(ASSETS/'starter'/'fixtures'/'before'/'geometry.json').read_text()
    c=(ASSETS/'starter'/'fixtures'/'candidate'/'geometry.json').read_text()
    jb=json.loads(b);jc=json.loads(c)
    assert jb['apertures']==jc['apertures']
    assert jb['outline']==jc['outline']
    assert json.loads((ASSETS/'starter'/'reference'/'policy.json').read_text())['target_pad']=='P1'
    return a


def observed_baseline_smoke():
    # This is NOT a Gerber interpreter. These are only expected header/content signals.
    roles={'coupon-F_Cu.gbr':'Copper,L1,Top','coupon-F_Mask.gbr':'Soldermask,Top','coupon-Edge_Cuts.gbr':'Profile,NP'}
    for filename,role in roles.items():
        b=(BEFORE/filename).read_text()
        for token in (f'%TF.FileFunction,{role}*%','%FSLAX46Y46*%','%MOMM*%','M02*'):
            assert token in b, (filename,token)
    cu=(BEFORE/'coupon-F_Cu.gbr').read_text()
    mask=(BEFORE/'coupon-F_Mask.gbr').read_text()
    edge=(BEFORE/'coupon-Edge_Cuts.gbr').read_text()
    assert '%TF.FilePolarity,Negative*%' in mask
    assert 'X20350000Y-20000000D03*' in cu
    assert mask.count('G36*')==4 and mask.count('G37*')==4
    assert mask.count('D03*')==0
    assert 'D03*' not in edge and 'G36*' not in edge
    job=json.loads((BEFORE/'coupon-job.gbrjob').read_text())
    return {'board_version':job['Header']['GenerationSoftware']['Version'],'mask_regions':4,'note':'known-coupon syntax only, not composed Gerber image'}


def preflight():
    count=verify_manifest()
    values=positions()
    observed=observed_baseline_smoke()
    return {
      'status':'PASS_BOOTSTRAP_ONLY',
      'assets_hashed':count,
      'source_positions':values,
      'observed_before_syntax':observed,
      'native_candidate_export':'NOT_RUN',
      'v1_independent_gerber_validation':'NOT_RUN',
      'connectivity_clearance_and_scope':'NOT_ESTABLISHED',
      'cursor_review':'NOT_RUN',
      'manufacturing_signoff':'NOT_ESTABLISHED'
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output')
    args=ap.parse_args()
    result=preflight()
    print(json.dumps(result,indent=2))
    if args.output:
        p=Path(args.output)
        if not p.is_absolute(): p=ROOT/p
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__': main()
