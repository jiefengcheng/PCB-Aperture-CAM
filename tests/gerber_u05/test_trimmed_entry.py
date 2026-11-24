import copy
import pytest
from shapely.geometry import box
from src.gerber_u05.trimmed_entry import bind_floor, constructor_operands
from src.gerber_u05.source_trace_floor import preserve


def entry():
    original={'a':box(0,0,2,1)}
    current={'a':box(0,0,1.9,1)}
    rows={'a':{'original_ref':'immutable raw source'}}
    return rows,current,original


def test_preservation_floor_does_not_restore_the_trimmed_bump():
    rows,current,original=entry()
    proof=bind_floor(rows,current,original,{})
    _,_,floor=constructor_operands((rows,current,original),proof)
    result,_=preserve(floor['a'],box(0,0,1.8,1))
    assert result.symmetric_difference(current['a']).area==0
    assert original['a'].difference(result).area==pytest.approx(.1)
    assert rows['a']['original_ref']=='immutable raw source'


@pytest.mark.parametrize('change',['current','raw','inventory','receipt'])
def test_changed_entry_cannot_reuse_the_verified_floor(change):
    rows,current,original=entry();proof=bind_floor(rows,current,original,{})
    if change=='current':current['a']=box(0,0,1.8,1)
    elif change=='raw':original['a']=box(0,0,2.1,1)
    elif change=='inventory':current['b']=box(3,3,4,4)
    else:proof['schema']='ordinary source'
    with pytest.raises(ValueError,match='T04_TRIMMED_ENTRY'):
        constructor_operands((rows,current,original),proof)


def test_cleanup_addition_is_rejected_before_growth():
    rows,current,original=entry();current['a']=box(0,0,2.1,1)
    with pytest.raises(ValueError,match='HAS_ADDITIONS'):
        bind_floor(rows,current,original,{})


def test_only_authenticated_empty_contribution_is_readable(tmp_path):
    from shapely.geometry import Polygon
    from src.gerber_u05 import pipeline as p
    store=p.Store(tmp_path/'runtime')
    original={'a':box(0,0,2,1)}; current={'a':Polygon()}
    rows={'a':dict(source_id='a',metadata={},original_ref=p.geomref(store,original['a']),geometry_ref=p.geomref(store,current['a']))}
    receipt=bind_floor(rows,current,original,dict(source_sha256='source'))
    scene=dict(source_sha256='source',objects=list(rows.values()),lineage=[dict(
        stage='verified-large-copper-trim-entry',receipt_ref=store.put_json('t04-trimmed-entry',receipt))])
    assert p.operands(store,scene)[1]['a'].is_empty
    positive=dict(scene,lineage=[])
    with pytest.raises(Exception,match='finite valid filled copper'):
        p.operands(store,positive)
    receipt['entry_fingerprints']['a']='changed'
    scene['lineage'][0]['receipt_ref']=store.put_json('t04-trimmed-entry',receipt)
    with pytest.raises(ValueError,match='UNAUTHORIZED_EMPTY'):
        p.operands(store,scene)


def test_empty_member_in_mixed_route_is_kept_without_deleting_native_identity(tmp_path):
    from shapely.geometry import Polygon
    from src.gerber_u05.covered_traces import prepare
    rows={s:dict(kind='stroke',metadata=dict(route_kind='segment',minimum_caliper_mm=.05))for s in ('removed','live')}
    current=dict(removed=Polygon(),live=box(0,0,1,.05)); paths=dict(route=['removed','live'])
    with pytest.raises(ValueError,match='EMPTY_SOURCE_AUTHORITY'):
        prepare(tmp_path/'reject',{},rows,current,paths)
    active,ledger,_=prepare(tmp_path/'allow',{},rows,current,paths,authorized_empty_ids=['removed'])
    assert active==dict(route=['live'])
    assert ledger['native_source_ids_by_route']==paths and ledger['source_ids_deleted']==[]
    assert ledger['reports']['removed']['disposition']=='KEEP_VERIFIED_CLEANUP_TOMBSTONE'


def test_residual_workspace_preserves_empty_custody_and_native_union():
    from shapely.geometry import Polygon
    from src.gerber_u05.component_workspace import ResidualScene
    from src.gerber_u05.native_contact_support import assemble
    material=ResidualScene(dict(removed=Polygon(),live=box(0,0,1,.05)))
    try:
        assert set(material)=={'removed','live'} and material['removed'].is_empty
        assert tuple(material.query(box(-1,-1,2,2)))==('live',)
        assert assemble(['removed','live'],{},material).equals(material['live'])
    finally:material.close()


def test_zero_material_native_route_has_zero_components_but_invalid_copper_still_rejects():
    from shapely.geometry import Polygon,GeometryCollection
    from src.gerber_u05.native_contact_support import component_count
    assert component_count(Polygon())==component_count(GeometryCollection())==0
    assert component_count(box(0,0,1,1))==1
    with pytest.raises(ValueError,match='VALID_FILLED_SOURCE'):
        component_count(Polygon([(0,0),(1,1),(0,1),(1,0),(0,0)]))


def test_query_only_candidate_reuses_source_index_includes_new_bounds_and_has_no_acceptance():
    from src.shared_copper_context import for_board
    raw=dict(a=box(0,0,1,1),b=box(3,0,4,1))
    with for_board(raw) as copper:
        current=dict(a=box(10,0,11,1),b=raw['b'])
        before=copper.stats['revision_cold_preparations']
        view=copper.query_view(current)
        assert view.sources(box(-1,-1,2,2))==()
        assert view.sources(box(9,-1,12,2))==('a',)
        assert view.sources(box(2,-1,5,2))==('b',)
        assert copper.query_view(current) is view
        assert copper.stats['revision_overlay_index_builds']==1
        assert copper.stats['revision_cold_preparations']==before
        with pytest.raises(ValueError,match='NO_VERIFIED_OWNERSHIP'):view.owner('a')
        with pytest.raises(ValueError,match='VERIFIED_PARENT'):copper.acquire({},parent=view)
