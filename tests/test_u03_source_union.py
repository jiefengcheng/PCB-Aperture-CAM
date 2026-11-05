"""Exact ordered union prefetch, source certificates and unchanged final closure."""
from concurrent.futures import Future
from dataclasses import replace
import random
import pytest
from shapely import to_wkb,get_precision,set_precision
from shapely.geometry import Point,LineString,box
from src.u03_board.source_union import SourceUnionWidthScene,construct_union
from src.u03_board.dependency import DependencyWidthScene


def scene():
    cores=[LineString([(0,y),(1,y)]).buffer(.05) for y in (0,.16,.4)]
    rows=[dict(id=str(i),original=g,candidate=g,verified_original_width_mm=.1) for i,g in enumerate(cores)]
    fixed=[dict(id='ring'+str(i),geometry=Point(.5,.2).buffer(2+i*.01,quad_segs=512).difference(Point(.5,.2).buffer(1.5-i*.01,quad_segs=512))) for i in range(5)]
    return rows,fixed


def trial(rows,factors):return [dict(r,candidate=r['original'] if f==1 else r['original'].buffer(.05*(f-1))) for r,f in zip(rows,factors)]


@pytest.mark.parametrize('workers,budget',[(0,0),(1,128*1024**2),(3,0),(3,1024),(3,128*1024**2)])
def test_ordered_union_and_full_reports_are_bit_identical_across_failure_and_rollback(workers,budget):
    rows,fixed=scene();a=DependencyWidthScene(rows,fixed);b=SourceUnionWidthScene(rows,fixed,union_workers=workers,union_prefetch_bytes=budget)
    try:
        for factors in [(1,1,1),(1.1,1,1),(1.5,1.5,1),(1,1,1),(1.2,1,1.3),(1.4,1.1,1.5)]:
            t=trial(rows,factors)
            assert b.check(t,fail_fast=True)==a.check(t,fail_fast=True)
            assert b.pending_weight<=budget and len(b.pending)<=4
        assert b.check(t,materialize_scene=True)==a.check(t,materialize_scene=True)
        assert b.pool is None and not b.pending and not b.source_union_search
        assert b.check(t,fail_fast=True)==a.check(t,fail_fast=True)
        if workers and budget>1024:assert b.union_submitted>0 and b.union_hits>0
    finally:b.close()


def test_prefetch_certificate_uses_exact_original_rtree_order_and_geometry_bytes():
    rows,fixed=scene();c=SourceUnionWidthScene(rows,fixed)
    try:
        c.use_width_union_window=True
        for r in fixed[:3]:c._submit(r['id'],r['geometry'])
        assert len(c.pending)==3
        for key in list(c.pending):
            expected=DependencyWidthScene.compute_original_union(c,key)
            actual=c.compute_original_union(key)
            assert to_wkb(actual,include_srid=True)==to_wkb(expected,include_srid=True)
            assert get_precision(actual)==get_precision(expected)
        assert c.union_hits==3 and not c.pending and not c.planned and not c.validated
    finally:c.close()


@pytest.mark.parametrize('field',['binding','operands_sha256','geometry_sha256','precision'])
def test_corrupt_union_certificate_rejects_without_serial_recomputation(field):
    rows,fixed=scene();c=SourceUnionWidthScene(rows,fixed);g=rows[0]['original'];key=c.original_union_key('0',g)
    proof=construct_union(c.binding,key,[c.original[c.ids[i]] for i in key])
    value=1. if field=='precision' else 'changed';future=Future();future.set_result(replace(proof,**{field:value}))
    c.pending[key]=(future,0);c.epochs[key]=0
    with pytest.raises(ValueError,match='CERTIFICATE_CHANGED'):c.compute_original_union(key)
    assert c.union_serial==0
    c.close()


def test_unused_worker_failure_is_not_hidden_by_eviction_or_final_closure():
    rows,fixed=scene();c=SourceUnionWidthScene(rows,fixed);future=Future();future.set_exception(ValueError('DELIBERATE_UNION_FAILURE'))
    c.pending[(0,)]=(future,0);c.epochs[(0,)]=0
    with pytest.raises(ValueError,match='DELIBERATE_UNION_FAILURE'):c.check(rows,materialize_scene=True)
    assert not c.pending and c.pool is None


def test_final_verifier_never_starts_workers_and_precision_models_remain_exact():
    rows,fixed=scene();rows=[dict(r,original=set_precision(r['original'],.0001),candidate=set_precision(r['candidate'],.0001)) for r in rows]
    a=DependencyWidthScene(rows,fixed);b=SourceUnionWidthScene(rows,fixed)
    try:
        assert b.check(rows,materialize_scene=True)==a.check(rows,materialize_scene=True)
        assert b.check(trial(rows,(1.5,1,1)),fail_fast=True)==a.check(trial(rows,(1.5,1,1)),fail_fast=True)
        assert b.union_submitted==0 and b.pool is None
    finally:b.close()


def test_source_union_limits_are_explicit_and_no_executor_is_created_for_small_jobs():
    rows,_=scene();c=SourceUnionWidthScene(rows,[])
    c._submit('0',rows[0]['original']);assert not c.pending and c.pool is None
    for kwargs in (dict(union_workers=4),dict(union_workers=True),dict(union_prefetch_bytes=-1),dict(union_lookahead=33)):
        with pytest.raises(ValueError,match='BUDGET_INVALID'):SourceUnionWidthScene(rows,[],**kwargs)
    c.close()
