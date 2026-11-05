"""Bounded indexed GEOS distance for large disjoint copper surfaces.

No geometry is simplified, quantized or clipped. Every original boundary edge
is retained in the GEOS indexed-facet calculation. Intersections, unsupported types, small
inputs and comparison-boundary measurements use the original GEOS distance.
"""
from collections import OrderedDict,Counter
import atexit,ctypes,hashlib,math,threading,weakref
from pathlib import Path
import shapely,numpy as np
from shapely import STRtree
from shapely.geometry import LineString
from shapely import get_num_coordinates,get_precision,to_wkb
from src.clearance_policy import HARD_GAP_MM,CONSTRUCTION_GAP_MM

LIMIT=128*1024**2
STATS=Counter();CONTROL=threading.RLock()
ENGINE=None
CHUNKS=OrderedDict();CHUNK_WEIGHT=0
MEASUREMENTS=OrderedDict();MEASURE_WEIGHT=0
SIGNATURES=OrderedDict();VALUES=OrderedDict();VALUE_WEIGHT=0

def measurement_budget():return min(2*1024**2,LIMIT//64)
def signature_budget():return min(2*1024**2,LIMIT//64)
def value_budget():return min(8*1024**2,LIMIT//16)
def chunk_budget():return LIMIT-LIMIT//4-measurement_budget()-signature_budget()-value_budget()

def signature(shape):
    # Shapely 2 geometries are immutable. Weak identity prevents both stale
    # identity reuse and retaining old proposal geometries solely for hashes.
    with CONTROL:
        key=id(shape);old=SIGNATURES.get(key)
        if old is not None and old[0]()is shape:
            if hashlib.sha256(old[1].encode()).hexdigest()!=old[2]:raise ValueError('IMMUTABLE_GEOMETRY_SIGNATURE_CHANGED')
            SIGNATURES.move_to_end(key);STATS['signature_hits']+=1;return old[1]
        value=hashlib.sha256(to_wkb(shape)).hexdigest();STATS['signature_misses']+=1
        if signature_budget()>=512:
            while SIGNATURES and(len(SIGNATURES)+1)*512>signature_budget():SIGNATURES.popitem(last=False)
            SIGNATURES[key]=(weakref.ref(shape),value,hashlib.sha256(value.encode()).hexdigest())
        return value

def clear():
    global ENGINE,CHUNK_WEIGHT,MEASURE_WEIGHT,VALUE_WEIGHT
    with CONTROL:
        if ENGINE is not None:ENGINE.close();ENGINE=None
        STATS.clear();CHUNKS.clear();CHUNK_WEIGHT=0;MEASUREMENTS.clear();MEASURE_WEIGHT=0;SIGNATURES.clear();VALUES.clear();VALUE_WEIGHT=0

def legacy_value(left,right):
    """Retain exact fallback witnesses only for byte-identical ordered operands."""
    global MEASURE_WEIGHT
    key=(signature(left),signature(right))
    with CONTROL:
        old=MEASUREMENTS.get(key)
        if old is not None:
            value,checksum=old
            if type(value)is not float or not math.isfinite(value)or hashlib.sha256((key[0]+key[1]+value.hex()).encode()).hexdigest()!=checksum:raise ValueError('EXACT_DISTANCE_MEASUREMENT_CACHE_CHANGED')
            MEASUREMENTS.move_to_end(key);STATS['exact_measurement_hits']+=1;return value
        value=float(left.distance(right));STATS['exact_measurement_misses']+=1
        if math.isfinite(value)and measurement_budget()>=512:
            while MEASUREMENTS and(MEASURE_WEIGHT+512>measurement_budget()or len(MEASUREMENTS)>=4096):MEASUREMENTS.popitem(last=False);MEASURE_WEIGHT-=512
            MEASUREMENTS[key]=(value,hashlib.sha256((key[0]+key[1]+value.hex()).encode()).hexdigest());MEASURE_WEIGHT+=512
        return value

class Engine:
    """Own reentrant GEOS context and bounded WKB-derived geometry handles."""
    def __init__(self):
        library=Path(shapely.__file__).parent/'.dylibs/libgeos_c.1.19.2.dylib'
        if not library.is_file():raise RuntimeError('PINNED_GEOS_LIBRARY_UNAVAILABLE')
        self.library_sha256=hashlib.sha256(library.read_bytes()).hexdigest()
        if self.library_sha256!='29d74cf4b9747ee581b6d35c513281672fa9e9fcdaf9896b5357a5e5773fbd7c':raise RuntimeError('PINNED_GEOS_BINARY_CHANGED')
        self.api=ctypes.CDLL(str(library));void=ctypes.c_void_p
        declarations=[('GEOS_init_r',[],void),('GEOS_finish_r',[void],None),('GEOSWKBReader_create_r',[void],void),('GEOSWKBReader_destroy_r',[void,void],None),('GEOSWKBReader_read_r',[void,void,void,ctypes.c_size_t],void),('GEOSGeom_destroy_r',[void,void],None),('GEOSDistanceIndexed_r',[void,void,void,ctypes.POINTER(ctypes.c_double)],ctypes.c_int)]
        for name,args,result in declarations:fn=getattr(self.api,name);fn.argtypes=args;fn.restype=result
        self.context=self.api.GEOS_init_r();self.reader=self.api.GEOSWKBReader_create_r(self.context);self.handles=OrderedDict();self.weight=0;self.lock=threading.RLock();self.closed=False
        if not self.context or not self.reader:raise RuntimeError('INDEXED_GEOS_CONTEXT_FAILED')
    def handle(self,shape):
        key=signature(shape);old=self.handles.get(key)
        if old is not None:self.handles.move_to_end(key);STATS['geometry_hits']+=1;return old[0],False
        blob=to_wkb(shape)
        buffer=ctypes.create_string_buffer(blob);handle=self.api.GEOSWKBReader_read_r(self.context,self.reader,buffer,len(blob))
        if not handle:raise RuntimeError('INDEXED_GEOS_WKB_READ_FAILED')
        weight=6*len(blob)+int(get_num_coordinates(shape))*64+1024
        # Caller destroys uncached handles after its one measurement. Eviction
        # happens after the measurement so the other operand stays live.
        if weight<=LIMIT//4 and int(get_num_coordinates(shape))>=32768:self.handles[key]=(handle,weight);self.weight+=weight;return handle,False
        return handle,True
    def measure(self,left,right):
        with self.lock:
            a,free_a=self.handle(left);b,free_b=self.handle(right)
            try:
                result=ctypes.c_double();status=self.api.GEOSDistanceIndexed_r(self.context,a,b,ctypes.byref(result))
                if status!=1:raise RuntimeError('INDEXED_GEOS_DISTANCE_FAILED')
                return result.value
            finally:
                if free_a:self.api.GEOSGeom_destroy_r(self.context,a)
                if free_b:self.api.GEOSGeom_destroy_r(self.context,b)
                while self.handles and(self.weight>LIMIT//4 or len(self.handles)>256):
                    _,(handle,weight)=self.handles.popitem(last=False);self.api.GEOSGeom_destroy_r(self.context,handle);self.weight-=weight;STATS['evictions']+=1
    def close(self):
        if self.closed:return
        with self.lock:
            for handle,_ in self.handles.values():self.api.GEOSGeom_destroy_r(self.context,handle)
            self.handles.clear();self.weight=0;self.api.GEOSWKBReader_destroy_r(self.context,self.reader);self.api.GEOS_finish_r(self.context);self.closed=True

def chunks(shape):
    polygons=[shape]if shape.geom_type=='Polygon'else list(shape.geoms);result=[]
    for poly in polygons:
        for ring in[poly.exterior,*poly.interiors]:
            coords=shapely.get_coordinates(ring);segments=len(coords)-1;full=segments//32
            if full:
                offsets=np.arange(full)[:,None]*32+np.arange(33)[None,:]
                result.append(shapely.linestrings(coords[offsets]))
            if segments%32:result.append(np.asarray([shapely.linestrings(coords[full*32:])],dtype=object))
    return np.concatenate(result)

def legacy_minimum(left,right,upper):
    """Use the indexed upper bound only to enumerate a conservative superset.

    Final values use the original GEOS segment distance with original left/right
    orientation. This retains the legacy floating witness and report hashes.
    The padding expands candidates only; it never changes a clearance verdict.
    """
    global CHUNK_WEIGHT
    key=signature(right);entry=CHUNKS.get(key)
    if entry is None:
        blob=to_wkb(right)
        parts=chunks(right);tree=STRtree(parts);weight=6*len(blob)+int(get_num_coordinates(right))*64+len(parts)*1024+1024;entry=(tree,parts,weight)
        if weight<=chunk_budget() and int(get_num_coordinates(right))>=32768:
            while CHUNKS and(CHUNK_WEIGHT+weight>chunk_budget() or len(CHUNKS)>=64):
                _,old=CHUNKS.popitem(last=False);CHUNK_WEIGHT-=old[2];STATS['chunk_evictions']+=1
            CHUNKS[key]=entry;CHUNK_WEIGHT+=weight
        STATS['chunk_builds']+=1
    else:CHUNKS.move_to_end(key);STATS['chunk_hits']+=1
    tree,parts,_=entry;queries=chunks(left);magnitude=max(1.,*(abs(x)for x in(*left.bounds,*right.bounds)))
    padding=max(128*math.ulp(magnitude),128*math.ulp(upper));indices=tree.query(queries,predicate='dwithin',distance=upper+padding)
    if indices.shape[1]==0:raise ValueError('INDEXED_DISTANCE_WITNESS_CANDIDATES_MISSING')
    values=shapely.distance(queries[indices[0]],parts[indices[1]]);STATS['exact_chunk_pairs']+=len(values)
    result=float(np.min(values))
    near=values[np.abs(values-result)<=padding]
    if len(np.unique(near))>1:
        STATS['ambiguous_tie_fallbacks']+=1
        return legacy_value(left,right)
    if result>upper+padding:raise ValueError('INDEXED_DISTANCE_WITNESS_OUTSIDE_BOUND')
    return result

def compute_distance(left,right):
    global ENGINE
    STATS['calls']+=1
    if(left.geom_type not in('Polygon','MultiPolygon')or right.geom_type not in('Polygon','MultiPolygon')or left.is_empty or right.is_empty or max(int(get_num_coordinates(left)),int(get_num_coordinates(right)))<1024 or max(int(get_num_coordinates(left)),int(get_num_coordinates(right)))>1000000 or get_precision(left)!=0 or get_precision(right)!=0):
        STATS['legacy_fallbacks']+=1;return left.distance(right)
    # Keep the legacy overlap/containment witness, including any tiny floating
    # distance in numerically delicate touching cases.
    if left.intersects(right):STATS['intersection_fallbacks']+=1;return left.distance(right)
    with CONTROL:
        if ENGINE is None:ENGINE=Engine()
        value=ENGINE.measure(left,right)
        value=legacy_minimum(left,right,value)
    if not math.isfinite(value)or value<0:raise ValueError('INDEXED_DISTANCE_INVALID')
    # Never let changed traversal/roundoff decide a clearance boundary. This
    # executes the original measurement with the unchanged 1e-12 comparison.
    if value<=1e-12 or any(abs(value-threshold)<=4e-12 for threshold in(HARD_GAP_MM,CONSTRUCTION_GAP_MM)):
        STATS['boundary_fallbacks']+=1;return legacy_value(left,right)
    STATS['indexed_calls']+=1;return value

def distance(left,right):
    global VALUE_WEIGHT
    with CONTROL:
        key=(signature(left),signature(right),float(get_precision(left)),float(get_precision(right)));old=VALUES.get(key)
        if old is not None:
            value,checksum=old
            if type(value)is not float or not math.isfinite(value)or hashlib.sha256((repr(key)+value.hex()).encode()).hexdigest()!=checksum:raise ValueError('GEOMETRY_DISTANCE_CERTIFICATE_CHANGED')
            VALUES.move_to_end(key);STATS['distance_value_hits']+=1;return value
        value=float(compute_distance(left,right));STATS['distance_value_misses']+=1
        if math.isfinite(value)and value_budget()>=512:
            while VALUES and VALUE_WEIGHT+512>value_budget():VALUES.popitem(last=False);VALUE_WEIGHT-=512
            VALUES[key]=(value,hashlib.sha256((repr(key)+value.hex()).encode()).hexdigest());VALUE_WEIGHT+=512
        return value

def diagnostics():return dict(STATS,retained_bytes=CHUNK_WEIGHT+MEASURE_WEIGHT+len(SIGNATURES)*512+VALUE_WEIGHT+(0 if ENGINE is None else ENGINE.weight),limit_bytes=LIMIT,retained_geometries=0 if ENGINE is None else len(ENGINE.handles),exact_measurement_bytes=MEASURE_WEIGHT,algorithm='Exact-coordinate indexed distance with bounded immutable signatures and ordered distance certificates; legacy ambiguity/boundary fallback',library_sha256=None if ENGINE is None else ENGINE.library_sha256)

atexit.register(lambda:ENGINE.close()if ENGINE is not None else None)
