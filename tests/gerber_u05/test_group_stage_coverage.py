from types import SimpleNamespace
import pytest
from shapely.geometry import box
from src.gerber_u05 import group_stage as stage
from src import source_channel_scope as sc


@pytest.mark.parametrize('fully_covered',[False,True])
@pytest.mark.parametrize('hybrid',[False,True])
def test_actual_group_entry_uses_occurrence_coverage_and_keeps_native_route(tmp_path,monkeypatch,fully_covered,hybrid):
    ids=['hidden']if fully_covered else['hidden','visible']
    rows={s:dict(kind='stroke',metadata=dict(route_kind='segment',minimum_caliper_mm=.05,
         source_port_width_mm=.05,route_points_mm=[[i,0.],[i+1.,0.]]))for i,s in enumerate(ids)}
    rows['bulk']=dict(kind='region',metadata={})
    current={s:box(i,-.025,i+1.,.025)for i,s in enumerate(ids)}
    current['bulk']=box(-.1,-.1,1.2,.2)
    path=dict(path_id='r',source_ids=ids,ordered_source_edges=[])
    native=dict(admitted=[path],paths=[dict(path=path)],groups=[])
    scope=SimpleNamespace(index=None,ids={s:('owner',)for s in current},cores={'owner':current['bulk'].union(current[ids[-1]])})
    monkeypatch.setattr(sc,'ACTIVE',scope)
    monkeypatch.setattr(stage.p,'operands',lambda *a:(rows,current,current))
    monkeypatch.setattr(stage,'prepare_or_load',lambda *a:({},native,{}))
    straight=dict(runs=[],cases={'admitted_0.05':dict(edges=[])})
    curves=dict(arcs=[],cases={'admitted_0.05':dict(groups=[])})
    monkeypatch.setattr(stage,'catalogue',lambda *a:(straight,curves,{}))
    prep=tmp_path/'prep';prep.mkdir();(prep/'ROLES.json.gz').write_bytes(b'roles')
    rule=dict(scope='BOUNDED',input_binding={},source_preparation=str(prep),group_cache='',
              relationship_cache_root=tmp_path/'relationships',
              arc_member_cache=tmp_path/'arcs',
              member_cache=tmp_path/'members',coverage_cache=tmp_path/'coverage',hybrid_components=hybrid)
    q=stage.run(None,dict(scene='accepted'),route_ids=['r'],settings=SimpleNamespace(maximum_factor=1.5,maximum_total_width_increase_mm=.03),rule=rule)
    assert q['requested_routes']==['r']
    assert q['native_trace_source_ids_by_route']==dict(r=ids)
    assert q['covered_trace_projection']['covered_source_ids']==['hidden']
    assert q['growth_source_ids_by_route']==({}if fully_covered else dict(r=['visible']))
    if hybrid:
        h=q['hybrid_components']
        assert h['covered_trace_copper_preserved']and h['joint_connections']['reports'][0]['passed']
        assert 'hidden'not in h['continuous_source_bodies']and h['constructed_groups_audited']==0
