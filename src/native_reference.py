"""Independent native-source terminal reference via maintained sexpdata reader.
No Gerber image or connected component supplies the expected locations/nets.
"""
import math
import sexpdata
from .native_document import NativeSequence,NativeNode
from shapely.geometry import box,Point,Polygon,LineString
from shapely import affinity

def children(node,key):
    if isinstance(node,NativeNode):return node.named_children(key)
    return [x for x in node if isinstance(x,(list,NativeSequence)) and x and str(x[0])==key]
def one(node,key,default=None):
    if isinstance(node,NativeNode):return node.first_named_tail(key,default)
    found=children(node,key);return found[0][1:] if found else default

def terminals(path):
    board=sexpdata.loads(path.read_text());result=[]
    for fp in children(board,'module')+children(board,'footprint'):
        at=one(fp,'at',[0,0,0]);fx,fy=at[:2];angle=float(at[2]) if len(at)>2 else 0
        a=math.radians(angle);c,s=math.cos(a),math.sin(a)
        ref=None
        for text in children(fp,'fp_text'):
            if str(text[1])=='reference':ref=str(text[2])
        for prop in children(fp,'property'):
            if str(prop[1])=='Reference':ref=str(prop[2])
        for pad in children(fp,'pad'):
            p=one(pad,'at',[0,0,0]);x,y=p[:2];px=fx+c*x+s*y;py=fy-s*x+c*y
            pa=float(p[2]) if len(p)>2 else 0
            w,h=one(pad,'size');kind=str(pad[3]);net=one(pad,'net',[0,'']);layernames=list(map(str,one(pad,'layers',[])))
            layernames=[v for v in ('F.Cu','B.Cu') if v in layernames or '*.Cu' in layernames]
            if kind in ('rect','roundrect'):
                r=min(w,h)*float(one(pad,'roundrect_rratio',[0])[0]) if kind=='roundrect' else 0
                shape=box(-w/2+r,-h/2+r,w/2-r,h/2-r).buffer(r,quad_segs=256) if r else box(-w/2,-h/2,w/2,h/2)
            elif kind=='circle':shape=Point(0,0).buffer(w/2,quad_segs=256)
            else:shape=None
            if shape is not None:
                # KiCad serialized pad angle is its board orientation, while pad XY is
                # footprint-local. Do not add the footprint angle a second time.
                shape=affinity.translate(affinity.rotate(shape,-pa,origin=(0,0)),px,py)
                shape=affinity.scale(shape,1,-1,origin=(0,0))
            result.append({'source_id':str(one(fp,'uuid',one(fp,'tstamp',[ref]))[0])+':'+str(pad[1]),'ref':ref,'pin':str(pad[1]),'center_mm':(px,-py),'layers':layernames,'net':str(net[1]) if len(net)>1 and int(net[0])!=0 else None,'shape':shape,'kind':kind,'size_mm':[w,h]})
    return result

def routing_references(path,pads):
    """Source-declared same-layer nominal conductors, not candidate components.
    Zones use stored filled polygons; no zone filling or routing is performed.
    Unnamed conductor intent remains unknown.
    """
    from shapely.ops import unary_union
    board=sexpdata.loads(path.read_text());nets={int(x[1]):str(x[2]) for x in children(board,'net')}
    grouped={};unknown=[]
    def add(layer,net,shape):
        name=nets.get(int(net))
        if not name:unknown.append({'layer':layer,'net':int(net)});return
        grouped.setdefault((layer,name),[]).append(shape)
    for p in pads:
        if p['net'] and p['shape'] is not None:
            for l in p['layers']:grouped.setdefault((l,p['net']),[]).append(p['shape'])
    for item in children(board,'segment'):
        a=one(item,'start');b=one(item,'end');width=float(one(item,'width')[0]);layer=str(one(item,'layer')[0]);net=one(item,'net',[0])[0]
        add(layer,net,LineString([(a[0],-a[1]),(b[0],-b[1])]).buffer(width/2,quad_segs=256))
    for item in children(board,'arc'):
        a=one(item,'start');m=one(item,'mid');b=one(item,'end');a=(a[0],-a[1]);m=(m[0],-m[1]);b=(b[0],-b[1])
        ax,ay=a;mx,my=m;bx,by=b;det=2*(ax*(my-by)+mx*(by-ay)+bx*(ay-my))
        if abs(det)<1e-12:raise ValueError('degenerate native arc')
        ux=((ax*ax+ay*ay)*(my-by)+(mx*mx+my*my)*(by-ay)+(bx*bx+by*by)*(ay-my))/det
        uy=((ax*ax+ay*ay)*(bx-mx)+(mx*mx+my*my)*(ax-bx)+(bx*bx+by*by)*(mx-ax))/det
        # Midpoint fixes the sweep direction independently of Gerber I/J/G02.
        ang=lambda p:math.atan2(p[1]-uy,p[0]-ux)
        ccw_mid=(ang(m)-ang(a))%(2*math.pi);ccw_end=(ang(b)-ang(a))%(2*math.pi)
        clockwise=ccw_mid>ccw_end
        sweep=(ang(a)-ang(b))%(2*math.pi) if clockwise else ccw_end
        radius=math.hypot(ax-ux,ay-uy);count=max(1,math.ceil(sweep/.0005))
        points=[(ux+radius*math.cos(ang(a)+(-1 if clockwise else 1)*sweep*i/count),uy+radius*math.sin(ang(a)+(-1 if clockwise else 1)*sweep*i/count)) for i in range(count+1)]
        points[0]=a;points[-1]=b
        width=float(one(item,'width')[0]);layer=str(one(item,'layer')[0]);net=one(item,'net',[0])[0]
        add(layer,net,LineString(points).buffer(width/2,quad_segs=256))
    for zone in children(board,'zone'):
        for fill in children(zone,'filled_polygon'):
            layer=str(one(fill,'layer',one(zone,'layer'))[0]);pts=children(fill,'pts')[0]
            coords=[(float(x[1]),-float(x[2])) for x in children(pts,'xy')]
            poly=Polygon(coords)
            if not poly.is_valid:
                # Stored native zone contours use exact axial cut-ins in these
                # pinned sources; interpret verified paired edges, never repair.
                from .gerber_image import contour
                poly=contour(coords+[coords[0]] if coords[0]!=coords[-1] else coords)
            add(layer,one(zone,'net',[0])[0],poly)
    return {key:unary_union(values) for key,values in grouped.items()},unknown


def physical_segments(path):
    board=sexpdata.loads(path.read_text());rows=[]
    for index,item in enumerate(children(board,'segment')):
        a=one(item,'start');b=one(item,'end')
        rows.append({'source_id':str(one(item,'uuid',one(item,'tstamp',[index]))[0]),
          'a':(float(a[0]),-float(a[1])),'b':(float(b[0]),-float(b[1])),
          'layer':str(one(item,'layer')[0]),'width_mm':float(one(item,'width')[0]),
          'reference_kind':'immutable native conductor continuity, not an electrical net assignment'})
    return rows
