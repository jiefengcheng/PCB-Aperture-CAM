import pytest
from shapely.geometry import Polygon,box
from shapely import union_all
from src.gerber_u05 import legacy_export as e,pipeline as p
from src.gerber_u05.native_material import equality
from test_gerber_source import source_circle


def hole_shape(size=1e-6):
    return box(0,0,.01,.01).difference(box(.005,.005,.005+size,.005+size))


def test_complete_existing_owner_covers_closed_grid_hole():
    g=hole_shape();owner=box(.004,.004,.007,.007)
    result,proof=e.owned_grid_holes(g,owner)
    assert not result.interiors and len(proof)==1
    assert result.union(owner).equals(g.union(owner))
    assert proof[0]['added_physical_copper_mm2']==0.


@pytest.mark.parametrize('owner',[None,box(0,0,.004,.004),box(.005,.005,.0050005,.005001)])
def test_uncovered_or_partly_covered_holes_remain_exact(owner):
    g=hole_shape();result,proof=e.owned_grid_holes(g,owner)
    assert p.to_wkb(result)==p.to_wkb(g) and proof==[]


def test_larger_holes_are_not_subject_to_microscopic_support_rule():
    g=hole_shape(2e-6);result,proof=e.owned_grid_holes(g,box(0,0,.02,.02))
    assert p.to_wkb(result)==p.to_wkb(g) and proof==[]


def test_other_holes_survive_and_exact_positive_surface_is_preserved():
    g=hole_shape().difference(box(.002,.002,.003,.003))
    result,proof=e.owned_grid_holes(g,box(.004,.004,.007,.007))
    assert len(result.interiors)==1 and len(proof)==1
    assert result.covers(g)


def test_legacy_output_reparses_to_same_physical_owner_union(tmp_path):
    g=hole_shape();owner=box(.004,.004,.007,.007);store=p.Store(tmp_path/'store')
    records,blocks=[],[]
    e.append_regions(g,'t05','route-test',records,blocks,store,owner=owner)
    base,_=e.canonical_base(source_circle());parsed=e.parse((base+''.join(blocks)+'M02*\n').encode())
    actual=union_all([p.affine_scale(p.source_profile.object_geometry(obj)[0],1,-1,origin=(0,0))
                      for obj in parsed.objects[-len(records):]])
    equality(owner.union(g),owner.union(actual),grid_mm=e.GRID_MM)
    assert records[0]['component_reference_proof']['redundant_owned_grid_holes']


def test_legacy_ordinary_encoding_without_owner_keeps_hole(tmp_path):
    g=hole_shape();store=p.Store(tmp_path/'store');records,blocks=[],[]
    e.append_regions(g,'t05','route-test',records,blocks,store)
    assert len(p.geometry(store,records[0]['geometry_ref']).interiors)==1
