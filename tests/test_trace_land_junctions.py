from dataclasses import replace
import pytest
from shapely.geometry import Point,box,LineString
from src.trace_land_junctions import propose_taper,verify_taper,fit_taper,JunctionContract

W=.1
TRACE=LineString([(-.5,0),(.2,0)]).buffer(W/2,quad_segs=128)
ROUTE=[(-.5,0),(.2,0)]

@pytest.mark.parametrize('land',[Point(.2,0).buffer(.2,quad_segs=128),box(0,-.2,.4,.2)])
def test_circle_and_rectangle_tapers_keep_owners_and_width(land):
 p=propose_taper(ROUTE,TRACE,land,W);r=verify_taper(p,TRACE,land,[])
 assert r['passed'] and r['robust_witness_passed']
 assert r['added_area_mm2']>0 and all(x['passed'] for x in r['stations'])
 assert TRACE.union(land).union(p['patch']).covers(TRACE.union(land))

def test_overlarge_blend_outside_independently_bound_window_rejected():
 land=box(0,-.2,.4,.2);p=propose_taper(ROUTE,TRACE,land,W);p['patch']=p['patch'].buffer(.5)
 assert 'OUTSIDE_WRITABLE_WINDOW' in verify_taper(p,TRACE,land,[])['failures']

def test_disconnected_blend_rejected():
 land=box(0,-.2,.4,.2);p=propose_taper(ROUTE,TRACE,land,W);p['patch']=box(1,1,1.1,1.1)
 r=verify_taper(p,TRACE,land,[])
 assert 'DISCONNECTED_FROM_TRACE' in r['failures'] and 'DISCONNECTED_FROM_LAND' in r['failures']

def test_too_thin_neck_fails_measured_width_and_robust_witness():
 land=box(0,-.2,.4,.2);p=propose_taper(ROUTE,TRACE,land,W);thin=LineString(ROUTE).buffer(.005);p['patch']=thin
 r=verify_taper(p,thin,land,[])
 assert 'THIN_NECK_AT_DECLARED_STATION' in r['failures']
 assert 'ROBUST_CONNECTED_NECK_NOT_ESTABLISHED' in r['failures']

def test_foreign_contact_never_excused_by_component_label():
 land=box(0,-.2,.4,.2);p=propose_taper(ROUTE,TRACE,land,W);foreign=box(-.07,.051,-.03,.085)
 r=verify_taper(p,TRACE,land,[dict(id='unrelated',geometry=foreign,component='same')])
 assert 'FOREIGN_COPPER_CLEARANCE:unrelated' in r['failures']

def test_bounded_fit_reduces_or_rejects_growth_without_modifying_owners():
 land=box(0,-.2,.4,.2);before=TRACE.wkb,land.wkb
 best,attempts=fit_taper(ROUTE,TRACE,land,W,[dict(id='close',geometry=box(-.1,.08,-.02,.2))])
 assert len(attempts)<=JunctionContract().search_steps+1
 assert before==(TRACE.wkb,land.wkb)
 assert best is None or best[1]['passed']

@pytest.mark.parametrize('width',[0,-1,float('nan')])
def test_unverified_width_rejected(width):
 with pytest.raises(ValueError,match='WIDTH'):propose_taper(ROUTE,TRACE,box(0,-.2,.4,.2),width)

def test_changed_policy_fails_closed():
 with pytest.raises(ValueError,match='CONTRACT_CHANGED'):
  propose_taper(ROUTE,TRACE,box(0,-.2,.4,.2),W,contract=replace(JunctionContract(),construction_gap_mm=0))
