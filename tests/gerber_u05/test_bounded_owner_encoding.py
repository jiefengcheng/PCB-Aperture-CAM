"""Serialization can join islands through existing copper without adding growth."""
from shapely import union_all
from shapely.geometry import box
from src.gerber_u05 import exporter as e,pipeline as p
from src.gerber_u05.compact_contours import require_budget
from src.junction_spindle_stage import CONTRACT


def encode(store,owner,region):
    records,blocks=[],[]
    e.append_regions(owner,'t01','owner',records,blocks,store)
    first=len(records)
    e.append_regions(region,'t05','joint',records,blocks,store)
    body=('%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.001*%\n'+''.join(blocks)+'M02*\n').encode()
    parsed=e.parse(body)
    actual=union_all([p.affine_scale(p.source_profile.object_geometry(o)[0],1,-1,origin=(0,0))for o in parsed.objects])
    return actual,records[first:]


def test_fragmented_joint_fits_unchanged_budget_with_identical_native_copper(tmp_path):
    owner=box(0,0,1,.1);domain=box(-.1,-.1,1.1,.3)
    region=union_all([box(i*.08+.01,.09,i*.08+.012,.102)for i in range(11)])
    original,old_records=encode(p.Store(tmp_path/'old'),owner,region)
    assert len(old_records)==11
    compact,proof=e.bounded_owner_surface(region,owner,domain)
    assert proof['accepted'] and proof['output_components']==1
    actual,records=encode(p.Store(tmp_path/'new'),owner,compact)
    assert require_budget(len(records),1,8)['passed']
    assert region.difference(compact).is_empty
    assert owner.union(compact).symmetric_difference(owner.union(region)).area<=CONTRACT.area_epsilon_mm2
    assert e.fidelity(original,actual)['passed']


def test_pin_channel_and_source_hole_survive_existing_owner_support(tmp_path):
    # Branches share a far-end bar. That does not permit filling their gap.
    owner=union_all([box(0,0,.2,1),box(.3,0,.5,1),box(0,0,.5,.1)])
    owner=owner.difference(box(.04,.4,.12,.5))
    region=union_all([box(.19,.7,.21,.71),box(.29,.7,.31,.71),box(.19,.8,.21,.81),box(.29,.8,.31,.81)])
    protected=box(.22,.11,.28,.99);source_hole=box(.04,.4,.12,.5)
    compact,proof=e.bounded_owner_surface(region,owner,box(-.1,-.1,.6,1.1))
    assert proof['accepted']
    actual,_=encode(p.Store(tmp_path/'native'),owner,compact)
    assert actual.intersection(protected).area==0
    assert actual.intersection(source_hole).area==0
    assert e.fidelity(owner.union(region),actual)['passed']


def test_surface_with_a_resolved_cutout_keeps_it_in_actual_gerber(tmp_path):
    hole=box(.4,.4,.6,.6);owner=box(0,0,1,1).difference(hole)
    region=union_all([box(.01,.99,.02,1.01),box(.98,-.01,.99,.01)])
    compact,proof=e.bounded_owner_surface(region,owner,box(-.1,-.1,1.1,1.1))
    assert proof['accepted'] and len(compact.interiors)==1
    actual,_=encode(p.Store(tmp_path/'native'),owner,compact)
    assert actual.intersection(hole).area==0
    assert e.fidelity(owner.union(region),actual)['passed']


def test_failed_support_cannot_clip_qualified_region_into_domain():
    owner=box(0,0,1,1);region=union_all([box(.9,.1,1.1,.2),box(.9,.3,1.1,.4)])
    actual,proof=e.bounded_owner_surface(region,owner,box(0,0,1,1))
    assert actual is region and not proof['accepted']
    assert proof['metrics']['outside_domain_mm2']>CONTRACT.area_epsilon_mm2


def test_disconnected_owner_cannot_invent_a_connection():
    owner=union_all([box(0,0,1,1),box(2,0,3,1)])
    region=union_all([box(.9,.2,1.1,.3),box(1.9,.2,2.1,.3)])
    actual,proof=e.bounded_owner_surface(region,owner,box(-1,-1,4,2))
    assert actual is region and not proof['accepted']
    assert actual.intersection(box(1.2,0,1.8,1)).is_empty


def test_single_surface_is_returned_unchanged():
    shape=box(0,0,1,1)
    actual,proof=e.bounded_owner_surface(shape,shape,shape)
    assert actual is shape and proof is None
