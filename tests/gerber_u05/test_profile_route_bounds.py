from types import SimpleNamespace
import pytest
from shapely.geometry import box, Point
from src.t04_incremental import OwnerDependencies, IncrementalRoutes
from src.trace_width_clearance import TraceWidthContract
from src.t04_settings import capture


def test_asymmetric_growth_cannot_escape_source_void_neighbor_index(monkeypatch):
    import src.t04_topology as topology
    import src.gerber_u05.checking_envelopes as envelopes
    monkeypatch.setattr(topology, 'holes_required', lambda: True)
    monkeypatch.setattr(envelopes, 'constraint', lambda ctx, own, body: body)
    core = box(0, 0, .05, 1)
    hole = Point(.07, .5).buffer(.002)
    copper = box(0, 0, 1, 1).difference(hole)
    candidate = box(0, 0, .075, 1)
    context = SimpleNamespace(binding='source', cores={'A': copper},
                              project=lambda material: {'A': copper}, owner=lambda *a: 'A')
    parent = SimpleNamespace(original={'r': core}, required_new_copper_gap=lambda: .0401,
                             contract=TraceWidthContract())
    old = OwnerDependencies(parent, context, ['r'], {'r': .0125}, 'FUNCTIONAL_SOURCE_CHANNEL')
    # The old symmetric-radius box cannot even discover the affected opening.
    assert len(old.route_tree.query(hole.envelope)) == 0
    complete = OwnerDependencies(parent, context, ['r'], {'r': .0125}, 'FUNCTIONAL_SOURCE_CHANNEL',
                                 route_bounds={'r': (-.0001, -.0001, .0751, 1.0001)})
    assert len(complete.route_tree.query(hole.envelope)) == 1
    proof = complete.source_voids.complete({'r': candidate}, {'r': 1.5})
    assert not proof['passed']
    assert any(f['reason'] == 'ORIGINAL_SOURCE_ROUTE_VOID_REMOVED' for f in proof['failures'])


def test_candidate_outside_prepared_profile_bounds_stops_before_clearance(monkeypatch):
    from src import component_clearance as cc, source_channel_scope as sc, pin_separation as pin
    monkeypatch.setattr(cc, 'ACTIVE', None)
    monkeypatch.setattr(sc, 'ACTIVE', None)
    monkeypatch.setattr(pin, 'ACTIVE', None)
    core = box(0, 0, .05, 1)
    rows = [dict(id='r', original=core, candidate=core, verified_original_width_mm=.05)]
    stage = IncrementalRoutes(rows, [], lambda *a: box(0, 0, .08, 1), capture(), {'r': .05},
                              route_bounds={'r': (-.0001, -.0001, .0751, 1.0001)})
    with pytest.raises(ValueError, match='OUTSIDE_PREPARED_BOUNDS'):
        stage.evaluate('r', 1.5)
