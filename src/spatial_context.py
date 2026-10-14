"""Rebuildable layer-scoped broad phase and exact native-geometry context.

Physical contact and within-distance are separate relations. Neither grants
editing permission nor establishes electrical acceptance.
"""
import math
import importlib.metadata
import shapely
from rtree import core
import time
from rtree import index
from shapely import from_wkb
from .revision_catalog import canonical,digest,CatalogError

class SpatialContext:
    VERSION='pcb-spatial/2'
    def __init__(self,revision,objects,payloads):
        self.kernel_versions={'shapely':importlib.metadata.version('shapely'),'geos':shapely.geos_version_string,'rtree':importlib.metadata.version('rtree'),'libspatialindex':core.rt.SIDX_Version().decode()}
        self.revision=revision;self.objects={r['id']:r for r in objects};self.shapes={};self.layers={};self.omissions=[]
        started=time.perf_counter()
        for r in objects:
            key=r.get('geometry_sha256')
            if not key or not any(l.endswith('.Cu') for l in r['layers']):
                self.omissions.append({'id':r['id'],'reason':r.get('unsupported_reason') or 'NO_COPPER_LAYER'});continue
            shape=from_wkb(payloads[key]);
            if len(shape.bounds)!=4 or not all(math.isfinite(v) for v in shape.bounds):raise CatalogError('NONFINITE_SPATIAL_GEOMETRY')
            self.shapes[r['id']]=shape
            for layer in r['layers']:
                if layer.endswith('.Cu'):self.layers.setdefault(layer,[]).append(r['id'])
        self.geometry_decode_layer_bind_seconds=time.perf_counter()-started
        index_started=time.perf_counter()
        self.indexes={}
        for layer,ids in self.layers.items():
            ids.sort();self.indexes[layer]=index.Index((i,self.shapes[uid].bounds,None) for i,uid in enumerate(ids))
        self.index_bulk_build_seconds=time.perf_counter()-index_started
        self.build_seconds=time.perf_counter()-started
        self.snapshot=digest(canonical({'revision':revision,'version':self.VERSION,'kernel_versions':self.kernel_versions,'geometry':[(uid,self.objects[uid]['geometry_sha256']) for uid in sorted(self.shapes)]}))

    def query(self,object_id,layer,*,distance_mm=0,limit=100000,expected_snapshot=None,cancel=None):
        if expected_snapshot is not None and expected_snapshot!=self.snapshot:raise CatalogError('STALE_SPATIAL_SNAPSHOT')
        if not math.isfinite(distance_mm) or distance_mm<0:raise CatalogError('INVALID_DISTANCE')
        if not isinstance(limit,int) or not 0<=limit<=100000:raise CatalogError('INVALID_QUERY_LIMIT')
        if layer not in self.layers:raise CatalogError('LAYER_INDEX_UNAVAILABLE')
        if object_id not in self.layers[layer]:raise CatalogError('OBJECT_GEOMETRY_OUTSIDE_LAYER_SCOPE')
        started=time.perf_counter();shape=self.shapes[object_id];a,b,c,d=shape.bounds
        # Conservative expanded envelope is essential for positive-distance queries.
        envelope=(math.nextafter(a-distance_mm,-math.inf),math.nextafter(b-distance_mm,-math.inf),math.nextafter(c+distance_mm,math.inf),math.nextafter(d+distance_mm,math.inf))
        if not all(math.isfinite(v) for v in envelope):raise CatalogError('SPATIAL_ENVELOPE_OVERFLOW')
        candidates=[];matches=[];status='COMPLETE'
        for i in self.indexes[layer].intersection(envelope):
            if cancel and cancel():status='CANCELLED';break
            uid=self.layers[layer][i]
            if uid==object_id:continue
            if len(candidates)>=limit:status='TRUNCATED';break
            candidates.append(uid)
            other=self.shapes[uid]
            exact=shape.intersects(other) if distance_mm==0 else shape.distance(other)<=distance_mm
            if exact:matches.append({'id':uid,'distance_mm':shape.distance(other)})
        matches.sort(key=lambda r:r['id']);candidates.sort()
        return {'revision':self.revision,'snapshot':self.snapshot,'query':{'object':object_id,'layer':layer,'distance_mm':distance_mm,'envelope_mm':list(envelope),'limit':limit},'predicate':'GEOS intersects (zero contact)' if distance_mm==0 else 'GEOS distance <= requested mm','backend':'rtree/libspatialindex + Shapely/GEOS','status':status,'complete':status=='COMPLETE','candidate_ids':candidates,'matches':matches,'result_sha256':digest(canonical(matches)),'elapsed_seconds':time.perf_counter()-started}

    def topology(self):
        """Recompute from this revision, including singletons; no insert-only cache."""
        relations=[];components=[];receipts=[]
        for layer,ids in sorted(self.layers.items()):
            adjacency={uid:set() for uid in ids}
            for uid in ids:
                q=self.query(uid,layer);receipts.append(q)
                if not q['complete']:raise CatalogError('INCOMPLETE_TOPOLOGY')
                for hit in q['matches']:
                    other=hit['id'];adjacency[uid].add(other)
                    if uid<other:
                        witness={'layer':layer,'distance_mm':hit['distance_mm'],'predicate':q['predicate'],'snapshot':self.snapshot}
                        occurrence=digest(canonical([self.revision,uid,other,witness]))
                        relations.append({'occurrence':occurrence,'source':uid,'target':other,'type':'physical_contact','witness':witness})
            unseen=set(ids)
            while unseen:
                seed=min(unseen);todo=[seed];group=set()
                while todo:
                    uid=todo.pop()
                    if uid in group:continue
                    group.add(uid);todo.extend(adjacency[uid]-group)
                unseen-=group;members=sorted(group)
                components.append({'id':digest(canonical([self.revision,layer,members])),'layer':layer,'members':members,'singleton':len(members)==1})
        return {'revision':self.revision,'snapshot':self.snapshot,'relations':relations,'components':components,'queries':receipts,'omissions':self.omissions,'scope':'available nominal native geometry, same-layer only; not electrical or manufacturing acceptance'}
