"""Actual point-contact export regression; no qualified growth is recomputed."""
import hashlib,json
from pathlib import Path
import pytest
from shapely import from_wkb
from shapely.geometry import box
from src.gerber_u05 import exporter as e,pipeline as p

def fixture():
 folder=Path(__file__).with_name('fixtures')/'encoding_owner_overlap'
 manifest=json.loads((folder/'MANIFEST.json').read_bytes());values={}
 for name,sha in manifest['files'].items():
  body=(folder/(name+'.wkb')).read_bytes()
  assert hashlib.sha256(body).hexdigest()==sha
  values[name]=from_wkb(body)
 return values

def test_actual_grid_point_contacts_join_using_existing_owner_only(tmp_path):
 g=fixture()
 assert g['encoded_owner'].union(e.native_grid(g['region'])).geom_type=='MultiPolygon'
 region,proof=e.owner_encoding_overlap(g['region'],g['owner'],g['domain'])
 assert all(v==0 for v in proof['metrics'].values())
 store=p.Store(tmp_path/'store');rows=[];blocks=[]
 parents=e.append_regions(region,'t05','route:JR-d768923fe90277e2',rows,blocks,store)
 material=g['encoded_owner'].union(p.unary_union(parents))
 assert material.is_valid and material.geom_type=='Polygon'
 assert e.preserve_point_contacts(g['encoded_owner'],parents,'retained',rows,blocks,store)==[]

def test_encoding_overlap_rejects_copper_outside_domain():
 with pytest.raises(ValueError,match='EXPORT_OWNER_OVERLAP_CHANGES_QUALIFIED_COPPER'):
  e.owner_encoding_overlap(box(0,0,1,1),box(-1,-1,2,2),box(0,0,.5,.5))


def test_optional_zero_area_owner_overlap_rejected_as_a_whole():
 region=box(0,.2,.2,.4);owner=box(-.1,0,0,1);domain=box(0,0,1,1)
 selected,proof=e.owner_encoding_overlap(region,owner,domain)
 assert not proof['accepted']
 assert proof['attempted_candidate_type']=='GeometryCollection'
 assert selected.wkb==region.wkb
 assert proof['selected_geometry_unchanged']
 assert proof['epsilon_mm2']==1e-12


def test_invalid_original_region_is_not_salvaged_by_fallback():
 from shapely.geometry import Polygon
 region=Polygon()
 with pytest.raises(ValueError,match='EXPORT_OWNER_OVERLAP_CHANGES_QUALIFIED_COPPER'):
  e.owner_encoding_overlap(region,box(-1,-1,2,2),box(0,0,1,1))


def test_direct_owner_union_proof_retains_cutouts_and_existing_support():
 owner=box(0,0,2,2).difference(box(.5,.5,1.5,1.5))
 region=box(1.9,.8,2.3,1.2)
 candidate=region.union(owner.intersection(box(1.8,.7,2.2,1.3)))
 proof=e.owner_surface_equivalence(region,owner,candidate,1e-12)
 assert proof['passed']
 assert owner.union(candidate).equals(owner.union(region))
 assert candidate.intersection(box(.6,.6,1.4,1.4)).is_empty


@pytest.mark.parametrize('defect',['missing-growth','foreign-bridge','filled-cutout'])
def test_direct_owner_union_proof_rejects_real_material_changes(defect):
 owner=box(0,0,2,2).difference(box(.5,.5,1.5,1.5));region=box(1.9,.8,2.3,1.2)
 candidate={'missing-growth':box(1.9,.8,2.1,1.2),
            'foreign-bridge':region.union(box(2.2,.9,2.8,1.1)),
            'filled-cutout':region.union(box(.6,.6,1.4,1.4))}[defect]
 assert not e.owner_surface_equivalence(region,owner,candidate,1e-12)['passed']
