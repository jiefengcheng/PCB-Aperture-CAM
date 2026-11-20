"""Safety controls: exact containment stays mandatory; the cover is recertified."""
import pytest
from shapely.geometry import box,Polygon
from src.t05_certified_enclosure import certified_enclosure as build,window_policy_proof

def certified_enclosure(base,patch,domain,certify):
    return build(base,patch,domain,certify,area_epsilon_mm2=1e-12)

def test_cover_is_freshly_checked_without_changing_copper():
    base=box(0,0,1,1);patch=box(.1,.1,.9,.9);raw=patch.wkb;seen=[]
    region,stats=certified_enclosure(base,patch,box(-1,-1,2,2),lambda r:(seen.append(r),True)[1])
    assert patch.wkb==raw and region.covers(patch) and len(seen)==1
    assert seen[0]is region and region.area>base.area
    assert stats['roundoff_enclosure_guard_mm']==1e-10 and stats['roundoff_enclosure_fresh_certifications']==1

def test_roundoff_sized_outside_material_needs_a_new_physical_certificate():
    base=box(0,0,1,1);patch=box(0,0,1+1e-11,1);calls=[]
    assert not base.covers(patch) and not patch.difference(base).is_empty
    region,_=certified_enclosure(base,patch,box(-1,-1,2,2),lambda r:(calls.append(r),r.distance(box(2,0,3,1))>=.5)[1])
    assert region.covers(patch) and len(calls)==1

def test_tight_clearance_must_reject_expanded_cover_even_when_patch_itself_fits():
    base=box(0,0,1,1);patch=box(.1,.1,.9,.9);obstacle=box(1.2,0,2,1)
    assert patch.distance(obstacle)>.2
    with pytest.raises(ValueError,match='CLEARANCE_REJECTED'):
        certified_enclosure(base,patch,box(-1,-1,3,3),lambda r:r.distance(obstacle)>=.2)

def test_substantive_outside_patch_is_not_hidden_by_resemblance_allowance():
    with pytest.raises(ValueError,match='PATCH_OUTSIDE'):
        certified_enclosure(box(0,0,1,1),box(0,0,1.0001,1),box(-1,-1,2,2),lambda _:True)

def test_domain_policy_is_separate_and_never_materializes_an_intersection():
    domain=box(0,0,1,1);patch=box(.1,.1,.9,.9)
    cover,stats=certified_enclosure(domain,patch,domain,lambda r:r.distance(box(3,0,4,1))>1.)
    assert not cover.difference(domain).is_empty and patch.difference(domain).is_empty
    assert stats['separate_window_outside_area_mm2']==0.
    # This real outside-window area exceeds the ORIGINAL epsilon and rejects,
    # even though it fits in the safely expanded enclosure.
    with pytest.raises(ValueError,match='WINDOW_POLICY_REJECTED'):
        certified_enclosure(domain,box(.1,.1,1+1e-11,.9),domain,lambda _:True)

def test_existing_window_area_epsilon_is_preserved_without_relaxing_cell_containment():
    domain=box(0,0,1,1);patch=box(.1,.1,1+1e-13,.9)
    witness=window_policy_proof(patch,domain,area_epsilon_mm2=1e-12)
    assert 0.<witness['outside_area_mm2']<=1e-12
    cover,_=certified_enclosure(domain,patch,domain,lambda _:True)
    assert cover.covers(patch)
    with pytest.raises(ValueError,match='WINDOW_POLICY_REJECTED'):
        window_policy_proof(patch,domain,area_epsilon_mm2=0.)

def test_excessive_coordinate_roundoff_cannot_inflate_the_cover():
    with pytest.raises(ValueError,match='ROUNDOFF_BOUND'):
        certified_enclosure(box(1e7,1e7,1e7+1,1e7+1),box(1e7+.1,1e7+.1,1e7+.9,1e7+.9),box(1e7-1,1e7-1,1e7+2,1e7+2),lambda _:True)

@pytest.mark.parametrize('empty_base,empty_patch',[(True,False),(False,True)])
def test_empty_regions_do_not_get_authority(empty_base,empty_patch):
    with pytest.raises(ValueError,match='INVALID_INPUT'):
        certified_enclosure(Polygon()if empty_base else box(0,0,1,1),Polygon()if empty_patch else box(.1,.1,.9,.9),box(-1,-1,2,2),lambda _:True)
