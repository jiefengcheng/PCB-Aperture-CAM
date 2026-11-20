"""Entry ordering, safe context boundaries and downstream rejection controls."""
from contextlib import contextmanager
from types import SimpleNamespace
import copy
import pytest
from shapely.geometry import box
from shapely.ops import unary_union
from src import component_clearance as cc
from src.gerber_u05 import ladder_width as ladder, t04_edge_entry as entry


def test_preparation_precedes_admission_and_entire_ladder(monkeypatch):
    events=[];input_scene={'lineage':[]};prepared_scene={'lineage':[{'stage':'prepared'}]}
    @contextmanager
    def prepare(store,scene,ids,settings,**kwargs):
        assert scene is input_scene and ids==['cap']
        events.append('prepare');yield prepared_scene,{'verified':True};events.append('restore')
    def run(store,scene,**kwargs):
        assert scene is prepared_scene and events==['prepare']
        events.append('admission-and-ladder');return {'done':True}
    monkeypatch.setattr(entry,'prepared',prepare);monkeypatch.setattr(ladder,'_run',run)
    result=ladder.run(None,input_scene,route_ids=['trace'],settings=object(),edge_restore_ids=['cap'])
    assert events==['prepare','admission-and-ladder','restore'] and result['edge_preparation']['verified']


def test_no_implicit_unbounded_run_or_repeated_edge_smoothing():
    with pytest.raises(ValueError,match='BOUNDED_ROUTE_IDS_REQUIRED'):
        ladder.run(None,{'lineage':[]},edge_restore_ids=['cap'])
    with pytest.raises(ValueError,match='DOWNSTREAM_REPLAY_NOT_QUALIFIED'):
        ladder.run(None,{'lineage':[{'stage':'t04-edge-entry-bounded'}]})


def contexts():
    originals={'body':box(0,0,1,1),'cap':box(.4,.9,.6,1.05),'other':box(2,0,3,1)}
    physical=cc.Context(unary_union(list(originals.values())),'a'*64,originals)
    functional=SimpleNamespace(frame_ids=frozenset(),originals=dict(originals),
        ids=copy.deepcopy(physical.ids),reserved={},approved_partial_pockets={},
        channels=SimpleNamespace(original=physical.cores,analytic_source=physical.index.source),
        binding='functional',source_objects=dict(originals))
    return physical,functional


def test_working_partition_keeps_all_source_members_and_old_context_immutable():
    physical,functional=contexts();before=physical.binding
    working,scope,proof=entry._working_context(physical,functional,{'cap':box(.4,.9,.6,1)}, {'test':'cap'})
    assert working is not physical and scope is not functional
    assert proof['original_components']==proof['working_components']==2
    assert physical.originals['cap'].bounds[-1]==1.05 and physical.binding==before
    assert working.originals['cap'].bounds[-1]==1
    assert working.binding!=before and scope.physical_context is working


@pytest.mark.parametrize('field',['reserved','approved_partial_pockets','checking_envelopes'])
@pytest.mark.parametrize('which',['physical','functional'])
def test_existing_safety_reservations_are_not_dropped(field,which):
    physical,functional=contexts();setattr(physical if which=='physical' else functional,field,{'protected':box(0,0,1,1)})
    with pytest.raises(ValueError,match='UNQUALIFIED_CONTEXT_OR_RETAINED_FLOOR'):
        entry._working_context(physical,functional,{}, {})


def test_original_separate_components_cannot_be_merged():
    physical,functional=contexts()
    with pytest.raises(ValueError,match='COMPONENT_MERGE_OR_LOSS'):
        entry._working_context(physical,functional,{'cap':box(.4,.9,2.5,1)}, {})


def test_hole_creation_cannot_hide_behind_same_component_count():
    physical,functional=contexts()
    with pytest.raises(ValueError,match='OWNER_HOLE_TOPOLOGY_CHANGED'):
        entry._working_context(physical,functional,{'body':box(0,0,1,1).difference(box(.1,.1,.2,.2))}, {})


def test_split_functional_channels_are_not_collapsed_into_physical_owners():
    physical,functional=contexts();functional.ids['cap']=['separate-functional-channel']
    with pytest.raises(ValueError,match='FUNCTIONAL_PARTITION_DIFFERS'):
        entry._working_context(physical,functional,{}, {})


@pytest.mark.parametrize('stage',['initialize','t02','t05'])
def test_unqualified_downstream_replay_rejects_before_any_geometry(stage):
    from src.gerber_u05 import pipeline as p
    scene={'lineage':[{'stage':'t04-edge-entry-bounded','receipt_ref':{}}]}
    with pytest.raises(ValueError,match='DOWNSTREAM_REPLAY_NOT_QUALIFIED'):
        if stage=='initialize':p.initialize(None,None,scene)
        elif stage=='t02':p.run_t02(None,scene)
        else:p.run_t05(None,scene,None)


def test_positive_only_export_rejects_smoothed_predecessor(tmp_path,monkeypatch):
    from src.gerber_u05 import exporter, pipeline as p, component_stages
    scene={'lineage':[{'stage':'t04-edge-entry-bounded'}]}
    monkeypatch.setattr(p,'Store',lambda root:SimpleNamespace(get_json=lambda *a,**k:scene))
    monkeypatch.setattr(p,'load',lambda path:{'output_scene_ref':{}})
    monkeypatch.setattr(p,'initialize',lambda *a:None)
    monkeypatch.setattr(component_stages,'reserve_prior',lambda *a:None)
    with pytest.raises(ValueError,match='DOWNSTREAM_REPLAY_NOT_QUALIFIED'):
        exporter.context(tmp_path)
