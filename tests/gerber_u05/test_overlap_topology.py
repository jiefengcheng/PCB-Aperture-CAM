import hashlib,json
from pathlib import Path
import pytest
from shapely import from_wkb,to_wkb,set_precision
from shapely.geometry import box,Polygon
from shapely.errors import GEOSException
from src.gerber_u05.component_finish import overlap_region

def test_actual_valid_operand_failure_retains_exact_approved_patch():
    root=Path(__file__).parent/'fixtures/overlap_topology'
    manifest=json.loads((root/'MANIFEST.json').read_bytes());values={}
    for name,expected in manifest.items():
        body=(root/name).read_bytes();assert hashlib.sha256(body).hexdigest()==expected;values[name]=from_wkb(body)
    patch,owner=set_precision(values['patch.wkb'],.000001,mode='pointwise'),values['owner.wkb']
    assert patch.is_valid and owner.is_valid
    with pytest.raises(GEOSException):patch.union(owner.intersection(patch.buffer(.000004,quad_segs=32)))
    region,mode=overlap_region(patch,owner)
    assert mode=='IDENTICAL_COORDINATES_WITHOUT_TRANSIENT_PRECISION_TAGS'
    plain_patch=values['patch.wkb']
    from src.component_voids import RemedyContract
    assert plain_patch.difference(region).area<=RemedyContract().area_epsilon_mm2
    assert owner.union(region).symmetric_difference(owner.union(plain_patch)).area<=RemedyContract().area_epsilon_mm2

def test_ordinary_overlap_preserves_same_physical_owner_union():
    owner=box(0,0,1,1);patch=box(.5,.5,1.5,1.5)
    region,mode=overlap_region(patch,owner)
    assert mode=='ORIGINAL_REDUNDANT_OWNER_OVERLAP'
    assert owner.union(region).equals(owner.union(patch))

def test_invalid_operand_cannot_be_repaired_as_support():
    invalid=Polygon([(0,0),(1,1),(1,0),(0,1)])
    with pytest.raises(ValueError,match='VALID_FILLED_OVERLAP_OPERANDS_REQUIRED'):overlap_region(invalid,box(0,0,2,2))
