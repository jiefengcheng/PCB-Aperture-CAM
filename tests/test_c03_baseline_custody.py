"""Successor custody is exact, explicit and cannot admit unrelated changes."""
import json
import shutil
from pathlib import Path

import pytest
from shapely import to_wkb
from shapely.geometry import Point,LineString,box
from src.c03_baseline_custody import ROOT, SUCCESSOR, specification, marker, check
from src.c03_input_family import specification as input_specification
from src.c03_recovery import SOURCE_SHA256,CROP_SHA256,bound_bytes


@pytest.fixture
def case(tmp_path):
    root=tmp_path/'checkout';root.mkdir()
    spec,baseline=specification()
    references=[spec[k] for k in ('historical_baseline','authorization','source_provenance')]
    references += [spec['successors'][0][k] for k in ('historical_copy','successor_copy')]
    names=set(baseline)|{r['path'] for r in references}|{'contracts/operator/c03_baseline_custody.json'}
    # This test qualifies the retained historical contract. Its fixture must
    # contain that revision, not whichever canonical implementation is current.
    archive=ROOT/'out/lacie_work/evidence/canonical_T01_restoration_20261104T135353Z/source_before'
    for name in names:
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
        if name==SUCCESSOR:
            # This positive case tests the exact recorded successor, never a
            # newer implementation installed by an authorized optimization.
            row=spec['successors'][0]['successor_copy']
            target.write_bytes(bound_bytes(ROOT,row['path'],row['sha256']))
            continue
        source=archive/name if name in baseline and (archive/name).is_file() else ROOT/name
        shutil.copyfile(source,target)
    session=tmp_path/'job/native';session.mkdir(parents=True)
    (session.parent/'job.json').write_text(json.dumps(dict(inputs=dict(kicad=dict(sha256=SOURCE_SHA256)),crop=dict(sha256=CROP_SHA256))))
    input_spec,_,sha=input_specification()
    (session/'C03_INPUT_FAMILY.json').write_text(json.dumps(dict(schema='c03-input-family-selected/1',contract=input_spec,contract_sha256=sha)))
    (session/'C03_BASELINE_CUSTODY.json').write_text(json.dumps(marker(root)))
    return root,session,root/spec['historical_baseline']['path'],spec,baseline


def test_all_entries_and_original_failure_are_retained(case):
    root,session,path,spec,baseline=case
    before=path.read_bytes();result=check(root,session,path)
    assert result['effective_status']=='PASS' and result['baseline_files']==484
    assert [r['path'] for r in result['retained_historical_mismatches']]==[SUCCESSOR]
    assert result['retained_historical_mismatches'][0]['historical_status']=='FAIL_RETAINED'
    assert path.read_bytes()==before


def test_generic_route_still_rejects_the_same_mismatch(case):
    root,session,path,_,_=case
    (session/'C03_BASELINE_CUSTODY.json').unlink()
    with pytest.raises(ValueError,match='BASELINE_CODE_CHANGED:src/junction_spindle_blend.py'):
        check(root,session,path)


@pytest.mark.parametrize('fault',['unrelated','successor','old_source','old_copy','authorization','contract','marker','input_family','job_source','symlink'])
def test_no_tamper_or_additional_exception_is_admitted(case,fault):
    root,session,path,spec,baseline=case
    if fault=='unrelated':
        other=next(p for p in sorted(baseline) if p!=SUCCESSOR);(root/other).write_bytes(b'changed')
    elif fault=='successor':(root/SUCCESSOR).write_bytes((root/SUCCESSOR).read_bytes()+b'\n')
    elif fault=='old_source':(root/SUCCESSOR).write_bytes((root/spec['successors'][0]['historical_copy']['path']).read_bytes())
    elif fault=='old_copy':(root/spec['successors'][0]['historical_copy']['path']).write_bytes(b'wrong')
    elif fault=='authorization':(root/spec['authorization']['path']).write_text('{}')
    elif fault=='contract':
        p=root/'contracts/operator/c03_baseline_custody.json';value=json.loads(p.read_bytes());value['successors'].append(value['successors'][0]);p.write_text(json.dumps(value))
    elif fault=='marker':(session/'C03_BASELINE_CUSTODY.json').write_text('{}')
    elif fault=='input_family':(session/'C03_INPUT_FAMILY.json').unlink()
    elif fault=='job_source':
        p=session.parent/'job.json';value=json.loads(p.read_bytes());value['inputs']['kicad']['sha256']='0'*64;p.write_text(json.dumps(value))
    else:
        blob=(root/SUCCESSOR).read_bytes();p=root/'source_copy';p.write_bytes(blob);(root/SUCCESSOR).unlink();(root/SUCCESSOR).symlink_to(p)
    with pytest.raises(ValueError):check(root,session,path)


@pytest.mark.parametrize('shape',['circle_neck','rectangle_neck'])
def test_committed_successor_preserves_historical_results_and_rejections(shape):
    spec,_=specification();ref=spec['successors'][0]['historical_copy']
    old={};exec(compile(bound_bytes(ROOT,ref['path'],ref['sha256']),ref['path'],'exec'),old)
    from src.junction_spindle_blend import spindle_blend,check_spindle
    trace=LineString([(-.5,0),(.5,0)]).buffer(.025)
    owner=(Point(0,0).buffer(.2,quad_segs=64) if shape=='circle_neck' else box(-.1,-.2,.3,.2)).union(trace)
    window=box(-.6,-.4,.6,.4)
    expected=old['spindle_blend'](owner,.2,window);actual=spindle_blend(owner,.2,window)
    assert tuple(map(to_wkb,expected))==tuple(map(to_wkb,actual))
    c,a=actual
    for candidate,addition,domain,foreign in [(c,a,window,[]),(c,a,window,[('foreign',a)]),
            (c.difference(box(-.1,-.1,.1,.1)),a,window,[]),(c,a,box(3,3,4,4),[]),
            (c,a.union(box(3,3,4,4)),window,[])]:
        assert check_spindle(owner,candidate,addition,domain,foreign)==old['check_spindle'](owner,candidate,addition,domain,foreign)


def test_current_prepared_kernel_cannot_masquerade_as_historical_successor(case):
    root,session,path,spec,baseline=case
    actual=(ROOT/SUCCESSOR).read_bytes()
    from src.stage_abi.store import digest
    assert digest(actual)!=spec['successors'][0]['successor_sha256']
    (root/SUCCESSOR).write_bytes(actual)
    with pytest.raises(ValueError,match='BASELINE_CODE_CHANGED:src/junction_spindle_blend.py'):
        check(root,session,path)
