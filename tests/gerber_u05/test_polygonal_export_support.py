"""Zero-width clipping remnants cannot masquerade as copper objects."""
import pytest
from shapely import to_wkb,union_all
from shapely.geometry import GeometryCollection,LineString,Point,Polygon,box
from src.gerber_u05.export_absorption import compact_supported_region,polygonal_support
from src.u05_board.export import NATIVE_OWNER_OVERLAP_MM
from src.component_absorption import absorb
from src.component_voids import RemedyContract


def test_tangent_support_remnant_is_removed_without_changing_any_copper():
 domain=box(-1,-1,2,2)
 owner=union_all([box(0,0,1,.5),box(2-NATIVE_OWNER_OVERLAP_MM,.2,2.5,.3)])
 addition=box(.4,.4,.6,.6);window=domain.buffer(-NATIVE_OWNER_OVERLAP_MM,quad_segs=64)
 old=owner.union(addition).intersection(window).union(addition)
 assert old.geom_type=='GeometryCollection'and old.is_valid
 assert any(g.geom_type=='LineString'and g.area==0 for g in old.geoms)
 with pytest.raises(ValueError,match='VALID_POLYGONAL_COPPER_REQUIRED'):
  absorb(old,owner,owner,[],RemedyContract())
 region,support,mode=compact_supported_region(addition,owner,domain)
 assert mode=='CHECKED_COMPLETE_LOCAL_JOINT_SURFACE'
 assert region.geom_type=='Polygon'and region.is_valid
 assert old.symmetric_difference(region).area==0
 assert addition.difference(region).is_empty
 assert support.difference(owner).area==0
 assert owner.union(region).symmetric_difference(owner.union(addition)).area==0
 assert region.difference(domain).area==0
 assert absorb(region,owner,owner,[],RemedyContract())[0].equals(region)


def test_all_exact_faces_holes_and_microscopic_islands_survive():
 hole=box(.2,.2,.4,.4);body=box(0,0,1,1).difference(hole)
 tiny=Polygon([(2,0),(2.0000001,0),(2,.0000001)])
 raw=GeometryCollection([body,GeometryCollection([tiny,LineString([(4,0),(4,1)]),Point(5,0)])])
 result=polygonal_support(raw)
 assert result.geom_type=='MultiPolygon'
 assert sorted(to_wkb(g)for g in result.geoms)==sorted([to_wkb(body),to_wkb(tiny)])
 assert result.intersection(hole).area==0 and result.covers(tiny)
 assert result.symmetric_difference(raw).area==0


@pytest.mark.parametrize('bad',[
 LineString([(0,0),(1,1)]),GeometryCollection([Point(0,0)]),Polygon(),
 Polygon([(0,0),(1,1),(0,1),(1,0)]),
 GeometryCollection([box(0,0,2,2),box(1,1,3,3)]),
])
def test_invalid_or_nonmaterial_support_still_halts(bad):
 with pytest.raises(ValueError,match='T05_EXPORT_SUPPORT_POLYGONAL_REQUIRED'):
  polygonal_support(bad)


def test_polygonal_input_is_unchanged_and_outside_addition_is_not_clipped():
 g=box(0,0,1,1).difference(box(.2,.2,.4,.4))
 assert polygonal_support(g)is g
 with pytest.raises(ValueError,match='SUPPORT_CHANGES_QUALIFIED_COPPER'):
  compact_supported_region(box(2,0,3,1),box(0,0,1,1),box(-1,-1,1.5,2))
