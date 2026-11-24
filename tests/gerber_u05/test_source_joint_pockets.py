from shapely.geometry import box
from shapely.ops import unary_union
from src.gerber_u05.source_joint_pockets import complete


def fixture():
    source=box(0,0,1,.1).difference(box(.4,.05,.6,.11))
    original={'a':source.intersection(box(0,0,.5,.1)),
              'b':source.intersection(box(.5,0,1,.1))}
    current={s:g.union(box(.4,.09,.6,.1).intersection(box(0 if s=='a' else .5,0,.5 if s=='a' else 1,.1)))
             for s,g in original.items()}
    rows={s:dict(metadata=dict(route_points_mm=p))for s,p in
          [('a',[[.5,.025],[0,.025]]),('b',[[.5,.025],[1,.025]])]}
    patches=[dict(source_id='a',route_id='r',endpoint_mm=[.5,.025],
                  recipe=dict(input_face_envelope_radius_mm=.1,joint_receiver_source_ids=['a','b']))]
    return rows,original,current,{'r':['a','b']},patches


def test_a_pocket_already_closed_before_the_corner_phase_uses_original_source():
    rows,original,current,paths,patches=fixture();before={s:g.wkb for s,g in original.items()}
    after,added,proof=complete(rows,original,current,paths,patches,lambda s:('owner',))
    assert proof['passed'] and proof['filled']==1 and len(added)==1
    assert not unary_union(list(after.values())).interiors
    assert before=={s:g.wkb for s,g in original.items()}
    assert unary_union(list(original.values())).difference(unary_union(list(after.values()))).area==0


def test_protected_void_or_missing_cap_cannot_be_filled():
    rows,original,current,paths,patches=fixture()
    after,added,proof=complete(rows,original,current,paths,patches,lambda s:('owner',),
                             protected_domains=[box(.42,.06,.58,.08)])
    assert not proof['passed'] and not added
    patches[0]['recipe']['input_face_envelope_radius_mm']=.01
    _,added,proof=complete(rows,original,current,paths,patches,lambda s:('owner',))
    assert not proof['passed'] and not added


def test_an_original_closed_hole_is_preserved():
    rows,original,current,paths,patches=fixture()
    after,added,proof=complete(rows,current,current,paths,patches,lambda s:('owner',))
    assert proof['passed'] and not added and proof['filled']==0
    assert {s:g.wkb for s,g in after.items()}=={s:g.wkb for s,g in current.items()}


def test_trimmed_baseline_requires_explicit_shared_revision_and_does_not_restore_cuts():
    import pytest
    from src.shared_copper_context import for_board
    rows,raw,current,paths,patches=fixture();cut=box(0,0,.01,.1)
    original={s:g.difference(cut)for s,g in raw.items()}
    current={s:g.difference(cut)for s,g in current.items()}
    with for_board(raw) as copper:
        baseline=copper.acquire(original)
        with pytest.raises(ValueError,match='SHARED_SOURCE_MISMATCH'):
            complete(rows,original,current,paths,patches,lambda s:('owner',),copper=copper)
        after,added,proof=complete(rows,original,current,paths,patches,lambda s:('owner',),
            copper=copper,baseline_revision=baseline)
        assert proof['passed'] and len(added)==1
        assert unary_union(list(after.values())).intersection(cut).area==0
        assert all(copper.source.values[s].equals_exact(raw[s],0)for s in raw)


def test_explicit_source_preparation_preserves_t04_distance_engine_lifetime():
    from src.shared_copper_context import for_board,ACTIVE
    from src.indexed_polygon_distance import measurement_engine
    rows,original,current,paths,patches=fixture()
    engine=measurement_engine();assert engine.owner is None and ACTIVE.get() is None
    with for_board(original) as copper:
        _,_,proof=complete(rows,original,current,paths,patches,lambda s:('owner',),copper=copper)
        assert proof['passed']
        assert measurement_engine() is engine and engine.owner is None and ACTIVE.get() is None
