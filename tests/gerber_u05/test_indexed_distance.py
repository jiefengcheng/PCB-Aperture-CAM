import importlib.util,math,random,sys
from pathlib import Path
import pytest
from shapely.geometry import Point,box,Polygon,MultiPolygon
from shapely import set_precision
from src import indexed_polygon_distance as module

def test_vector_chunks_preserve_every_original_edge_and_operand_order():
    shape=Point(0,0).buffer(1,quad_segs=401).difference(box(-.1,-.1,.1,.1));expected=[];actual=[]
    for ring in[shape.exterior,*shape.interiors]:expected.extend(zip(list(ring.coords),list(ring.coords)[1:]))
    for line in module.chunks(shape):actual.extend(zip(list(line.coords),list(line.coords)[1:]))
    assert actual==expected

def test_native_distance_error_cannot_become_a_pass(monkeypatch):
    class Broken:
        def measure(self,*args):raise RuntimeError('DELIBERATE_NATIVE_FAILURE')
    module.clear();monkeypatch.setattr(module,'ENGINE',Broken())
    with pytest.raises(RuntimeError,match='DELIBERATE_NATIVE_FAILURE'):module.distance(Point(0,0).buffer(1,quad_segs=401),Point(4,0).buffer(1,quad_segs=401))

def test_ambiguous_indexed_witness_uses_original_full_measurement(monkeypatch):
    module.clear();a=box(0,0,1,1).segmentize(.001);b=box(2,0,3,1).segmentize(.001);original=module.shapely.distance;expected=a.distance(b)
    def perturb(left,right,*args,**kwargs):
        values=original(left,right,*args,**kwargs)
        if hasattr(values,'shape')and values.ndim==1 and len(values)>1:
            values=values.copy();values[0]=math.nextafter(float(values.min()),math.inf)
        return values
    monkeypatch.setattr(module.shapely,'distance',perturb)
    assert module.distance(a,b).hex()==expected.hex()
    assert module.diagnostics()['ambiguous_tie_fallbacks']==1

def test_memory_eviction_and_context_recreation_preserve_measurements(monkeypatch):
    module.clear();monkeypatch.setattr(module,'LIMIT',500000)
    for i in range(5):
        a=Point(0,0).buffer(1+i*.01,quad_segs=600);b=Point(4,0).buffer(1,quad_segs=600)
        assert module.distance(a,b).hex()==a.distance(b).hex()
        assert module.diagnostics()['retained_bytes']<=module.LIMIT
    module.clear();assert module.diagnostics()['retained_bytes']==0

@pytest.mark.parametrize('gap',[.040,.040-2e-13,.040+2e-13,.04010,.04010-2e-13,.04010+2e-13,.04010-1e-12-1e-14,.04010-1e-12+1e-14,0.,-.01,.2])
def test_clearance_boundary_and_intersection_keep_original_measurement(gap):
    module.clear();a=Point(0,0).buffer(1,quad_segs=400);b=Point(2+gap,0).buffer(1,quad_segs=400)
    assert module.distance(a,b).hex()==a.distance(b).hex()

def test_disjoint_inside_hole_and_multipart_boundaries():
    module.clear();a=Point(0,0).buffer(2,quad_segs=400).difference(Point(0,0).buffer(1,quad_segs=400));b=MultiPolygon([Point(0,0).buffer(.2,quad_segs=400),box(4,4,5,5)])
    assert module.distance(a,b).hex()==a.distance(b).hex()

def test_deterministic_separated_complex_polygons_match_legacy():
    rng=random.Random(731);module.clear()
    for i in range(32):
        a=Point(rng.random(),rng.random()).buffer(.5+rng.random(),quad_segs=300);b=Point(5+rng.random(),rng.random()).buffer(.5+rng.random(),quad_segs=300)
        assert module.distance(a,b).hex()==a.distance(b).hex()
    assert module.diagnostics()['retained_bytes']<=module.LIMIT

def test_small_unsupported_and_fixed_precision_use_original():
    for a,b in[(box(0,0,1,1),box(2,2,3,3)),(Point(0,0),box(2,2,3,3)),(set_precision(Point(0,0).buffer(1,quad_segs=400),1e-6),Point(4,0).buffer(1,quad_segs=400))]:assert module.distance(a,b).hex()==a.distance(b).hex()

def test_immutable_signature_is_exact_and_corruption_rejects():
    import hashlib
    from shapely import to_wkb
    module.clear();a=box(0,0,1,1);expected=hashlib.sha256(to_wkb(a)).hexdigest()
    assert module.signature(a)==module.signature(a)==expected
    old=module.SIGNATURES[id(a)];module.SIGNATURES[id(a)]=(old[0],'0'*64,old[2])
    with pytest.raises(ValueError,match='SIGNATURE_CHANGED'):module.signature(a)
    module.clear()

def test_distance_certificate_binds_ordered_operands_and_detects_corruption():
    module.clear();a=box(0,0,1,1);b=box(2,0,3,1);expected=a.distance(b)
    assert module.distance(a,b)==module.distance(a,b)==expected
    assert module.diagnostics()['distance_value_hits']==1
    key=next(iter(module.VALUES));value,checksum=module.VALUES[key];module.VALUES[key]=(value+.1,checksum)
    with pytest.raises(ValueError,match='DISTANCE_CERTIFICATE_CHANGED'):module.distance(a,b)
    module.clear()
