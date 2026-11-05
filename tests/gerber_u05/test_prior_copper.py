from types import SimpleNamespace
import pytest
from shapely.geometry import box,Polygon
from shapely.ops import unary_union
from src.gerber_u05.prior_copper import local_floor,protected_owners,CoverageAdapter,BaseCoverageAdapter
from src import component_clearance as cc


def test_wider_shorter_rectangle_retains_earlier_taller_copper():
 current=box(0,0,1.4,1.);prior=box(0,0,1.,1.4);region,proof=local_floor(current,prior);after=unary_union([current,region])
 assert proof['required'] and proof['remaining_mm2']<=1e-12
 assert prior.difference(after.buffer(2e-6)).area<=1e-12
 assert current.difference(after).area<=1e-12
 assert region.difference(unary_union([current,prior])).area<=1e-12


def test_already_carried_prior_does_not_create_another_material_surface():
 region,proof=local_floor(box(0,0,2,2),box(.2,.2,.8,.8))
 assert region is None and not proof['required']


def test_common_original_hole_stays_empty():
 shell=[(0,0),(2,0),(2,2),(0,2)];hole=[(.5,.5),(.5,1.),(1.,1.),(1.,.5)]
 current=Polygon(shell,[hole]);prior=Polygon([(0,0),(2.1,0),(2.1,2.1),(0,2.1)],[hole]);region,_=local_floor(current,prior)
 assert unary_union([current,region]).intersection(Polygon(hole)).area==0.


@pytest.mark.parametrize('parameter,value',[('tolerance_mm',.000004),('support_mm',.001)])
def test_floor_cannot_change_existing_native_tolerance(parameter,value):
 with pytest.raises(ValueError,match='EXISTING_NATIVE_TOLERANCE'):local_floor(box(0,0,1,1),box(0,0,2,2),**{parameter:value})


def test_foreign_prior_cannot_disappear_from_new_spindle_checks(monkeypatch):
 current_a=box(0,0,.06,.02);current_b=box(.20,0,.24,.02);prior_a=current_a;prior_b=box(.18,0,.24,.02)
 monkeypatch.setattr(cc,'ACTIVE',SimpleNamespace(binding='source-bound',reserved={'A':prior_a,'B':prior_b}))
 monkeypatch.setattr(BaseCoverageAdapter,'_operands',lambda self,*args:(current_a,.01,box(-.1,-.1,.3,.1),[('owner:B',current_b)]))
 adapter=CoverageAdapter(box(-1,-1,1,1));adapter._snapshot=object();adapter._copper_owners={'A':current_a,'B':current_b};adapter.owner_for_route=lambda sid:'A'
 _,_,_,foreign=adapter._operands(None,None,None,None,{'source_id':'route'})
 proposed=box(0,0,.155,.02)
 assert proposed.distance(current_b)>.04
 assert dict(foreign)['owner:B'].distance(proposed)<.04
 assert dict(foreign)['owner:B'].covers(prior_b)
 # The owner's own source-connected prior never becomes internal clearance.
 assert set(dict(foreign))=={'owner:B'}


def test_original_owner_inventory_is_frozen():
 with pytest.raises(ValueError,match='OWNER_INVENTORY'):protected_owners({'A':box(0,0,1,1)},{'B':box(0,0,1,1)})


def test_legacy_profile_keeps_original_adapter_descriptor(monkeypatch):
 monkeypatch.setattr(cc,'ACTIVE',None)
 a=CoverageAdapter(box(0,0,1,1));b=BaseCoverageAdapter(box(0,0,1,1));assert a.describe()==b.describe()
