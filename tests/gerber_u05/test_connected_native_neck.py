import hashlib,json
from pathlib import Path
from shapely import from_wkb,set_precision,to_wkb
from shapely.geometry import box,MultiPolygon
from src.gerber_u05.legacy_export import connected_native_normalization
from src.native_boundary_metric import distance

def test_retained_native_grid_failure_preserves_all_copper_and_connection():
    root=Path(__file__).parent/'fixtures/connected_native_neck'
    body=(root/'qualified.wkb').read_bytes()
    assert hashlib.sha256(body).hexdigest()==json.loads((root/'MANIFEST.json').read_bytes())['sha256']
    qualified=from_wkb(body)
    broken=set_precision(qualified,.000001,mode='valid_output')
    assert qualified.geom_type=='Polygon' and broken.geom_type=='MultiPolygon'
    assert len(broken.geoms)==2
    native,proof=connected_native_normalization(qualified)
    assert native.geom_type=='Polygon' and native.is_valid and native.covers(qualified)
    assert distance(qualified,native)<=.000002
    assert proof['encoding_guard_mm']==.000001
    assert proof['connectivity_support']['nearest_grid_components']==2

def test_ordinary_connected_region_retains_identical_native_bytes():
    original=box(.1234567,.2345678,1.3456789,2.4567891)
    native,proof=connected_native_normalization(original)
    assert to_wkb(native)==to_wkb(set_precision(original,.000001,mode='valid_output'))
    assert proof['encoding_guard_mm']==0 and proof['connectivity_support'] is None

def test_genuinely_disconnected_input_does_not_gain_a_connection():
    original=MultiPolygon([box(0,0,1,1),box(1.000003,0,2,1)])
    native,proof=connected_native_normalization(original)
    assert native.geom_type=='MultiPolygon' and len(native.geoms)==2
    assert proof['encoding_guard_mm']==0
    assert to_wkb(native)==to_wkb(set_precision(original,.000001,mode='valid_output'))
