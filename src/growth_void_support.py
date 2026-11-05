"""Operation-local source-contact windows for inclusive pocket fills."""
import hashlib,math
from shapely import STRtree,to_wkb,union_all
from shapely.geometry import Polygon

class ContactSupport:
    def __init__(self,records,contact_buffer_mm):
        if not records or len({r['id']for r in records})!=len(records):raise ValueError('COMPLETE_UNIQUE_CONTACT_SOURCES_REQUIRED')
        if not math.isfinite(contact_buffer_mm) or contact_buffer_mm<0:raise ValueError('INVALID_CONTACT_BUFFER')
        if any(not r['original'].is_valid or r['original'].is_empty or r['original'].geom_type not in ('Polygon','MultiPolygon') or not math.isfinite(r['width_mm']) or r['width_mm']<0 for r in records):raise ValueError('INVALID_CONTACT_SOURCE')
        self.ids=[r['id']for r in records];self.shapes=[r['original']for r in records];self.widths=[r['width_mm']for r in records];self.buffer=contact_buffer_mm;self.maximum=max(self.widths,default=0)+self.buffer;self.tree=STRtree(self.shapes);self.cache={}
        self.binding=hashlib.sha256(b''.join((sid+':'+hashlib.sha256(to_wkb(g)).hexdigest()+':'+repr(w)+'\n').encode()for sid,g,w in zip(self.ids,self.shapes,self.widths))).hexdigest()
    def check(self,patch):
        nearby=sorted(map(int,self.tree.query(patch.buffer(self.maximum))))
        windows=[];pairs=[]
        for position,i in enumerate(nearby):
            for j in nearby[:position]:
                if not self.shapes[i].intersects(self.shapes[j]):continue
                key=(j,i)
                if key not in self.cache:
                    overlap=self.shapes[i].intersection(self.shapes[j]);window=overlap.buffer(max(self.widths[i],self.widths[j])+self.buffer,quad_segs=128)
                    self.cache[key]=window
                window=self.cache[key]
                if not window.intersects(patch):continue
                windows.append(window);pairs.append([self.ids[j],self.ids[i]])
        allowed=union_all(windows)if windows else Polygon();missing=patch.difference(allowed).area
        return dict(passed=missing<=1e-12,missing_source_contact_support_mm2=missing,source_pairs=pairs,source_binding_sha256=self.binding,contact_buffer_mm=self.buffer,window_sha256=hashlib.sha256(to_wkb(allowed)).hexdigest())
