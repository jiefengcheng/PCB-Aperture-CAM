import pytest
from shapely.geometry import LineString,box
from shapely import to_wkb
from src.original_copper_owners import OriginalOwners
from src.gerber_u05.native_contact_support import proposals,assemble


def fixture(gap=.03):
    points={'a':[[0.,0.],[1.,0.]],'b':[[1.+gap,0.],[2.,0.]]}
    rows={s:dict(metadata=dict(route_points_mm=ps,minimum_caliper_mm=.05))for s,ps in points.items()}
    originals={s:LineString(ps).buffer(.025,quad_segs=128)for s,ps in points.items()}
    return rows,originals


def test_native_contact_proposals_are_exact_source_copper_only():
    rows,originals=fixture();before={s:to_wkb(g)for s,g in originals.items()}
    found=list(proposals(rows,['a','b'],originals,{'a','b'},{}))
    assert len(found)==2
    for p in found:
        assert originals[p['source_id']].covers(p['geometry'])
        assert p['contact_sources']==(['b']if p['source_id']=='a'else['a'])
    assert before=={s:to_wkb(g)for s,g in originals.items()}


def test_exact_shared_ends_and_disconnected_originals_use_no_cap_recovery():
    for gap in (0.,.1):
        rows,originals=fixture(gap)
        assert not list(proposals(rows,['a','b'],originals,{'a','b'},{}))


def test_shared_end_caps_require_the_explicit_second_recovery_phase():
    rows,originals=fixture(0.)
    found=list(proposals(rows,['a','b'],originals,{'a','b'},{},shared=True))
    assert len(found)==2 and all(p['shared_endpoint']for p in found)
    assert all(originals[p['source_id']].covers(p['geometry'])for p in found)


def test_covered_sources_can_support_but_are_never_recovery_candidates():
    rows,originals=fixture()
    found=list(proposals(rows,['a','b'],originals,{'a'},{}))
    assert len(found)==1 and found[0]['source_id']=='a'


def test_declared_assembly_retains_tiny_faces_and_covered_sources():
    main=box(0,0,1,1);tiny=box(2,0,2.000001,.000001);covered=box(-1,0,0,1)
    body=main.union(tiny)
    result=assemble(['a','covered'],{'a':body},{'covered':covered})
    assert result.covers(body)and result.covers(covered)
    assert len(OriginalOwners(result).owners)==2
    with pytest.raises(KeyError):assemble(['missing'],{}, {})
