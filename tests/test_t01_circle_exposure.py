"""Analytic arc measure, strict >=70% eligibility, frozen original union."""
import json,math
from unittest.mock import patch
import pytest
from shapely.geometry import Point,box
from src.shape_containment import ContainmentIndex
from src.t01_circle_exposure import capture,from_bytes,exposed_arcs,assess


def case(others=()):
    core=Point(0,0).buffer(1,quad_segs=128)
    site=dict(source_id='circle',aliases=['circle'],core=core,center=[0,0],radius=1.)
    return site,ContainmentIndex(dict(circle=core,**dict(others)))


@pytest.mark.parametrize('fraction',[.1,.5,.69999999,.7,.70000001,.9])
def test_analytic_half_plane_arc_and_exact_seventy_boundary(fraction):
    # x>cos(pi*f) leaves f of a true circle's circumference exposed.
    cutoff=math.cos(math.pi*fraction)
    site,index=case([('half_plane',box(-2,-2,cutoff,2))])
    result=assess(site,index,capture())
    assert result['exposed_circumference_fraction']==pytest.approx(fraction,abs=1e-14)
    assert result['keep']is(fraction<.7)


def test_area_coverage_no_longer_authorizes_or_blocks_growth():
    site,index=case([('inner',Point(0,0).buffer(.9,quad_segs=128))])
    assert index.assess('circle')['uncovered_area_mm2']/site['core'].area<.2
    q=assess(site,index,capture())
    assert q['exposed_circumference_fraction']==1 and not q['keep']
    # Half a disk was eligible under the old area rule but is now <70% exposed.
    site,index=case([('half_plane',box(-2,-2,0,2))])
    q=assess(site,index,capture())
    assert q['exposed_circumference_fraction']==.5 and q['keep']


def test_union_aliases_tangencies_and_holes():
    site,index=case();core=site['core']
    for others in [dict(alias=core),dict(touch=box(1,-2,2,2)),
                   dict(ring=box(-2,-2,2,2).difference(Point(0,0).buffer(1.2,quad_segs=128)))]:
        q=assess(site,ContainmentIndex(dict(circle=core,**others)),capture())
        assert q['exposed_circumference_fraction']==1 and not q['keep']
    stripe=box(-2,-.5,2,.5)
    a=assess(site,ContainmentIndex(dict(circle=core,stripe=stripe)),capture())
    b=assess(site,ContainmentIndex(dict(circle=core,duplicate=stripe,stripe=stripe)),capture())
    assert a['exposed_arc_length_mm']==b['exposed_arc_length_mm']
    assert a['exposed_circumference_fraction']==pytest.approx(2/3)
    q=assess(site,ContainmentIndex(dict(circle=core,cover=box(-2,-2,2,2))),capture())
    assert q['fully_contained']and q['keep']and q['exposed_arc_length_mm']==0


def test_entry_geometry_is_frozen_and_order_is_irrelevant():
    site,index=case([('left',box(-2,-2,0,2))]);old=assess(site,index,capture())
    incoming=dict(circle=site['core'],left=box(-2,-2,0,2));index=ContainmentIndex(incoming)
    incoming['left']=box(-2,-2,2,2)
    assert assess(site,index,capture())==old
    same=ContainmentIndex(dict(left=box(-2,-2,0,2),circle=site['core']))
    assert assess(site,same,capture())==old


@pytest.mark.parametrize('bad',[True,-.01,1.01,float('nan'),float('inf'),'0.7'])
def test_bad_registered_exposure_threshold_rejects(bad):
    value=json.loads(capture().raw_json);value['minimum_exposed_circumference_fraction_for_growth']=bad
    with pytest.raises(ValueError):from_bytes(json.dumps(value).encode())


def test_replaceable_global_exposure_parameter_invalidates_stale_job_policy():
    from src.t01_canonical import marker,require
    from src.t01_board.policy import compile_policy,english
    from src.stage_abi.contracts import StageABIError
    old=compile_policy(english(),dict(artifact_id='t01-binding:'+'a'*64,sha256='a'*64))
    value=json.loads(capture().raw_json);value['minimum_exposed_circumference_fraction_for_growth']=.8
    replacement=from_bytes(json.dumps(value).encode())
    with patch('src.t01_canonical.exposure_settings',return_value=replacement):
        assert marker()['circle_exposure_settings']['minimum_exposed_circumference_fraction_for_growth']==.8
        with pytest.raises(StageABIError):require(old)
    with pytest.raises(ValueError,match='DUPLICATE'):
        from_bytes(capture().raw_json.replace('"revision": 1','"revision": 1, "revision": 2').encode())


def test_legacy_area_setting_is_diagnostic_only_in_new_allocation(monkeypatch):
    from tests.test_t01_circle_overlap import canonical_case
    from src import t01_canonical as tc
    from src.t01_circle_overlap import from_bytes as old_settings,capture as old_capture
    baseline=canonical_case()[-1][1]
    value=json.loads(old_capture().raw_json);value['maximum_other_copper_coverage_fraction_for_growth']=1.
    with patch('src.t01_circle_overlap.capture',return_value=old_settings(json.dumps(value).encode())):
        changed=canonical_case()[-1][1]
    assert changed['circle_exposure_keep_source_ids']==baseline['circle_exposure_keep_source_ids']
    assert 'target'in changed['circle_exposure_keep_source_ids']
    assert changed['circle_eligibility_metric']=='ORIGINAL_EXPOSED_CIRCUMFERENCE_FRACTION'
