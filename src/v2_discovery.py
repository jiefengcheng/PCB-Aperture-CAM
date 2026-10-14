"""Read-only pcb_Z helper qualification plus bounded native coupon discovery.
Only audited function ASTs are executed. No legacy module initialization,
pcbnew, SQLite, SaveBoard, grouping writes or log/Excel writes run.
"""
from pathlib import Path
import ast,hashlib,math
from collections import defaultdict
from types import SimpleNamespace
import sexpdata
from rtree import index
from shapely.geometry import box,LineString

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def children(n,k):return [v for v in n if isinstance(v,list) and v and str(v[0])==k]
def field(n,k):
    found=children(n,k)
    if len(found)!=1:raise ValueError('missing/ambiguous native field '+k)
    return found[0][1:]

def legacy_helpers(contract):
    folder=Path(contract['pcb_Z_path']);namespace={'sexpdata':sexpdata,'index':index,'defaultdict':defaultdict}
    for filename,names in contract['pcb_Z_allowed_functions'].items():
        path=folder/filename
        if digest(path)!=contract['pcb_Z_source_sha256'][filename]:raise ValueError('pcb_Z source changed')
        tree=ast.parse(path.read_text());nodes=[v for v in tree.body if isinstance(v,ast.FunctionDef) and v.name in names]
        if {v.name for v in nodes}!=set(names):raise ValueError('missing legacy helper')
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
    return namespace

class Item:
    def __init__(self,uid,layer,geometry):self.uid,self.layer,self.geometry=uid,layer,geometry
    def GetLayer(self):return self.layer
    def GetBoundingBox(self):
        a,b,c,d=self.geometry.bounds
        return SimpleNamespace(GetX=lambda:a,GetY=lambda:b,GetRight=lambda:c,GetBottom=lambda:d)
    def GetEffectiveShape(self):return self
    def Collide(self,other,clearance=0):return self.geometry.distance(other.geometry)<=clearance

class BoardView:
    def __init__(self,tracks,drawings):self.tracks,self.drawings=tracks,drawings
    def GetTracks(self):return self.tracks
    def GetDrawings(self):return self.drawings

def discover(text,contract):
    helper=legacy_helpers(contract);root=sexpdata.loads(text);records={};tracks=[];pads=[];drawings=[]
    def register(node,kind,geometry=None,layer=None,**extra):
        uid=helper['extract_uuid_from_expr'](node)
        if uid is None:raise ValueError('missing native identity')
        uid=str(uid)
        if uid in records:raise ValueError('duplicate native identity')
        records[uid]={'id':uid,'kind':kind,'node':node,'geometry':geometry,'layer':layer,**extra}
        return Item(uid,layer,geometry) if geometry is not None else None
    for fp in children(root,'footprint'):
        at=field(fp,'at');fx,fy=map(float,at[:2])
        if len(at)>2 and float(at[2])!=0:raise ValueError('rotated footprint outside executor profile')
        for p in children(fp,'pad'):
            if str(p[2])!='smd' or str(p[3])!='rect' or field(p,'layers')!=['F.Cu']:raise ValueError('unsupported pad')
            a=field(p,'at');x,y=fx+float(a[0]),fy+float(a[1])
            if len(a)>2 and float(a[2])!=0:raise ValueError('rotated pad outside executor profile')
            w,h=map(float,field(p,'size'));net=field(p,'net')
            if min(w,h)<=0 or not str(net[1]):raise ValueError('invalid/unknown pad intent')
            pads.append(register(p,'pad',box(x-w/2,y-h/2,x+w/2,y+h/2),'F.Cu',center=[x,y],size=[w,h],local=list(map(float,a[:2])),footprint=[fx,fy],net=int(net[0]),pin=str(p[1])))
    for node in root:
        if not isinstance(node,list) or not node:continue
        kind=helper['extract_type_from_expr'](node)
        layer=helper['extract_layer_from_expr'](node)
        if kind in ('via','arc','zone'):raise ValueError('unsupported copper topology')
        if kind=='segment':
            a=list(map(float,field(node,'start')));b=list(map(float,field(node,'end')));width=float(field(node,'width')[0])
            if layer!='F.Cu' or width<=0:raise ValueError('unsupported segment')
            tracks.append(register(node,kind,LineString([a,b]).buffer(width/2,quad_segs=128),layer,start=a,end=b,width=width,net=int(field(node,'net')[0])))
        elif kind=='gr_rect':
            a=list(map(float,field(node,'start')));b=list(map(float,field(node,'end')))
            if layer not in ('F.Mask','Edge.Cuts'):raise ValueError('unsupported graphic')
            drawings.append(register(node,kind,box(min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1])),layer,start=a,end=b))
    view=BoardView(tracks,drawings)
    legacy_items=helper['get_layer_items'](view,'F.Cu')
    # Legacy layer discovery omits footprint pads; explicitly append qualified pads.
    items=legacy_items+pads
    groups=helper['find_connected_components'](items,clearance=0)
    return {'root':root,'records':records,'groups':[[x.uid for x in g] for g in groups],
            'qualification':{'legacy_layer_items':len(legacy_items),'adapter_added_pads':len(pads),'grouping_clearance':0,'geometry_engine':'Shapely/GEOS Item adapter + installed rtree; not native pcbnew.GetEffectiveShape','legacy_side_effects_executed':False}}
