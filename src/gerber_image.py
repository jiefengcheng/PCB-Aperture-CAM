"""Versioned completion adapter around Gerbonara 1.6.3, not frozen V1.
Ordered image composition with bounded non-nested AB and aperture transforms.
No sample names/hashes/expected geometry are used by this implementation.
"""
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
import collections, math, re
from gerbonara.rs274x import GerberFile, GerberParser
from gerbonara import graphic_objects as go, graphic_primitives as gp
from gerbonara.utils import MM
from shapely.geometry import Point, Polygon, LineString, GeometryCollection
from shapely import affinity
from shapely.ops import unary_union, polygonize
from .validator import Unsupported

SAG=1e-6
MAX_POINTS=200000

def arc_points(start,end,center,cw):
    r=math.dist(start,center)
    if r<=0 or abs(math.dist(end,center)-r)>2e-6:raise Unsupported('inconsistent circular arc radius')
    a=math.atan2(start[1]-center[1],start[0]-center[0]);b=math.atan2(end[1]-center[1],end[0]-center[0])
    sweep=(a-b)%(2*math.pi) if cw else (b-a)%(2*math.pi)
    if math.dist(start,end)<1e-12:sweep=2*math.pi
    n=max(1,math.ceil(sweep/(2*math.acos(max(-1,1-SAG/r)))))
    if n>MAX_POINTS:raise Unsupported('arc approximation resource bound')
    sign=-1 if cw else 1
    points=[(center[0]+r*math.cos(a+sign*sweep*i/n),center[1]+r*math.sin(a+sign*sweep*i/n)) for i in range(n+1)]
    points[0]=start;points[-1]=end
    return points

def disk(center,r):
    if r<0:raise Unsupported('negative circle radius')
    if r==0:return GeometryCollection()
    q=max(16,math.ceil(math.pi/(4*math.acos(max(-1,1-SAG/r)))))
    if q>MAX_POINTS//4:raise Unsupported('disk resource bound')
    return Point(center).buffer(r,quad_segs=q)

def contour(points):
    if len(points)<3:raise Unsupported('incomplete contour')
    if math.dist(points[0],points[-1])>2e-6:raise Unsupported('unclosed contour')
    polygon=Polygon(points)
    if polygon.is_valid:return polygon
    # Interpret only legal axial coincident out-and-back cut-ins. Never repair
    # a transversal self-intersection or arbitrary weakly-simple polygon.
    edges=collections.defaultdict(list)
    for a,b in zip(points,points[1:]):
        if a==b:raise Unsupported('zero-length contour segment')
        edges[tuple(sorted((a,b)))].append((a,b))
    cuts=[];unique=[]
    for key,group in edges.items():
        if len(group)==1:unique.append(group[0])
        elif len(group)==2 and group[0]==group[1][::-1] and (key[0][0]==key[1][0] or key[0][1]==key[1][1]):cuts.append(key)
        else:raise Unsupported('invalid repeated contour edge')
    if not cuts:raise Unsupported('invalid contour: no qualified cut-in')
    directions={a[0]==b[0] for a,b in cuts}
    if len(directions)!=1:raise Unsupported('mixed cut-in directions')
    degrees=collections.Counter(p for edge in unique for p in edge)
    if any(v!=2 for v in degrees.values()):raise Unsupported('non-cut-in contour self-touch')
    linework=[LineString(e) for e in unique]
    network=unary_union(linework)
    # Noding must not add intermediate vertices or change edge inventory.
    count=sum(len(x.coords)-1 for x in network.geoms) if hasattr(network,'geoms') else len(network.coords)-1
    if count!=len(unique):raise Unsupported('contour intersection outside cut-in endpoints')
    for a,b in cuts:
        hit=LineString([a,b]).intersection(network)
        pts=list(hit.geoms) if hasattr(hit,'geoms') else [hit]
        if any(g.geom_type!='Point' or tuple(g.coords[0]) not in (a,b) for g in pts):raise Unsupported('cut-in crosses/overlaps boundary')
    faces=list(polygonize(network))
    if not faces:raise Unsupported('cut-in has no closed faces')
    def winding(p):
        x,y=p.x,p.y;number=0
        for (x1,y1),(x2,y2) in unique:
            side=(x2-x1)*(y-y1)-(x-x1)*(y2-y1)
            if y1<=y<y2 and side>0:number+=1
            elif y2<=y<y1 and side<0:number-=1
        return number
    values=[winding(f.representative_point()) for f in faces]
    if any(abs(v)>1 for v in values) or len({v for v in values if v})>1:
        raise Unsupported('cut-in winding violates valid contour semantics')
    return unary_union([f for f,v in zip(faces,values) if v])

def primitive(p):
    if isinstance(p,gp.Circle):return disk((p.x,p.y),p.r)
    if isinstance(p,gp.Rectangle):
        shape=Polygon([(-p.w/2,-p.h/2),(p.w/2,-p.h/2),(p.w/2,p.h/2),(-p.w/2,p.h/2)])
        return affinity.translate(affinity.rotate(shape,p.rotation,origin=(0,0),use_radians=True),p.x,p.y)
    if isinstance(p,gp.Line):
        r=p.width/2
        if p.width<0:raise Unsupported('negative line width')
        if p.width==0:return GeometryCollection()
        q=max(16,math.ceil(math.pi/(4*math.acos(max(-1,1-SAG/r)))))
        return LineString([(p.x1,p.y1),(p.x2,p.y2)]).buffer(r,quad_segs=q)
    if isinstance(p,gp.Arc):
        points=arc_points((p.x1,p.y1),(p.x2,p.y2),(p.cx,p.cy),p.clockwise)
        r=p.width/2
        if r<=0:raise Unsupported('nonpositive arc stroke width')
        q=max(16,math.ceil(math.pi/(4*math.acos(max(-1,1-SAG/r)))))
        return LineString(points).buffer(r,quad_segs=q)
    if isinstance(p,gp.ArcPoly):
        points=[]
        for a,b,(cw,c) in p.segments:
            part=[a,b] if cw is None else arc_points(a,b,c,cw)
            points.extend(part if not points else part[1:])
        return contour(points)
    raise Unsupported('unqualified plotting primitive '+type(p).__name__)

def ordered(items):
    # Batch consecutive dark objects only; clear operations retain exact order.
    result=GeometryCollection();pending=[]
    for geom,dark in items:
        if dark:pending.append(geom)
        else:
            if pending:result=unary_union([result,*pending]);pending=[]
            result=result.difference(geom)
    if pending:result=unary_union([result,*pending])
    return result

@dataclass
class Block:
    geometry:object
    unit:object=MM

def object_geometry(obj):
    if isinstance(obj,go.Flash):
        if isinstance(obj.aperture,Block):shape=obj.aperture.geometry
        else:
            positive=replace(obj,x=0,y=0,polarity_dark=True)
            shape=ordered((primitive(p),p.polarity_dark) for p in positive.to_primitives(unit=MM))
        mx,my,rotation,scale=getattr(obj,'completion_transform',(1,1,0,1))
        shape=affinity.scale(shape,mx,my,origin=(0,0));shape=affinity.rotate(shape,rotation,origin=(0,0));shape=affinity.scale(shape,scale,scale,origin=(0,0))
        return affinity.translate(shape,obj.x,obj.y)
    positive=replace(obj,polarity_dark=True) if not isinstance(obj,go.Region) else obj
    return ordered((primitive(p),True) for p in positive.to_primitives(unit=MM))

def compose(objects):return ordered((object_geometry(o),o.polarity_dark) for o in objects)

class CompletionParser(GerberParser):
    STATEMENT_REGEXES={
      'block_open':r'^ABD(?P<number>\d+)$','block_close':r'^AB$',
      'mirror':r'^LM(?P<value>N|X|Y|XY)$','rotate':r'^LR(?P<value>[+-]?\d+(?:\.\d+)?)$',
      'scaling':r'^LS(?P<value>\d+(?:\.\d+)?)$',**GerberParser.STATEMENT_REGEXES}
    # Upstream dispatch can match a prefix and discard command suffixes.
    # Require complete matches without replacing the maintained grammar.
    STATEMENT_REGEXES={name:'(?:'+pattern+')\\Z' for name,pattern in STATEMENT_REGEXES.items()}
    def __init__(self,target):
        super().__init__(target);self.block_frame=None;self.transform=(1,1,0,1);self.inventory=collections.Counter()
    def warn(self,msg,kls=SyntaxWarning):raise Unsupported(msg)
    def _split_commands(self,data):
        pattern=r'G04.*?\*\s*|%.*?%\s*|[^*%]*\*\s*';end=0
        for match in re.finditer(pattern,data,re.DOTALL):
            if data[end:match.start()].strip():raise Unsupported('unconsumed Gerber bytes')
            end=match.end()
        if data[end:].strip():raise Unsupported('trailing unconsumed Gerber bytes')
        for cmd in super()._split_commands(data):
            if self.eof_found:raise Unsupported('command after EOF')
            self.inventory[cmd[:2]]+=1
            if re.match(r'M\d',cmd) and cmd!='M02':raise Unsupported('end/control code outside profile')
            if cmd.startswith(('SR','IF','IP','IR','MI','SF','OF','AS','G74')):raise Unsupported('unqualified command '+cmd[:12])
            yield cmd
    def _parse_mirror(self,m):
        v=m['value'];_,_,r,s=self.transform;self.transform=(-1 if 'X' in v else 1,-1 if 'Y' in v else 1,r,s)
    def _parse_rotate(self,m):
        x,y,_,s=self.transform;r=float(m['value'])
        if not math.isfinite(r) or abs(r)>360:raise Unsupported('rotation outside profile')
        self.transform=(x,y,r,s)
    def _parse_scaling(self,m):
        x,y,r,_=self.transform;s=float(m['value'])
        if not 0<s<=1:raise Unsupported('scale outside profile')
        self.transform=(x,y,r,s)
    def _parse_block_open(self,m):
        if self.block_frame is not None or self.current_region is not None:raise Unsupported('nested/recursive block outside profile')
        number=int(m['number'])
        if number<10 or number in self.aperture_map:raise Unsupported('invalid/redefined block aperture')
        self.block_frame=(number,self.target.objects);self.target.objects=[];self.graphics_state.point=None
    def _parse_block_close(self,m):
        if self.block_frame is None or self.current_region is not None:raise Unsupported('unmatched block close')
        number,outer=self.block_frame;self.aperture_map[number]=Block(compose(self.target.objects))
        self.target.objects=outer;self.block_frame=None;self.graphics_state.point=None
        # Per spec: no graphics-state stack; retain end-of-block state.
    def _parse_coord(self,m):
        old=len(self.target.objects);super()._parse_coord(m)
        for obj in self.target.objects[old:]:
            if isinstance(obj,go.Flash):obj.completion_transform=self.transform
            elif getattr(obj,'aperture',None) is not None:
                if isinstance(obj.aperture,Block):raise Unsupported('block aperture cannot stroke')
                if self.transform[:3]!=(1,1,0) and not isinstance(obj.aperture,__import__('gerbonara.apertures',fromlist=['CircleAperture']).CircleAperture):raise Unsupported('noncircular transformed stroke')
                obj.aperture=obj.aperture.scaled(self.transform[3])

def read_image(path):
    text=Path(path).read_text();g=GerberFile();p=CompletionParser(g)
    try:
        p.parse(text,filename=str(path))
        if p.block_frame is not None or p.current_region is not None:raise Unsupported('unclosed block/region')
        if len(g.objects)>200000:raise Unsupported('object resource bound')
        if p.inventory['MO']!=1 or p.inventory['FS']!=1:raise Unsupported('exactly one explicit unit/format required')
        if p.file_settings.number_format not in ((2,6),(4,6)):raise Unsupported('coordinate format outside declared profile')
        if p.file_settings.unit!=MM or not re.search(r'%MOMM\*%',text):raise Unsupported('required millimeter units absent')
        if p.file_settings.notation!='absolute':raise Unsupported('nonabsolute coordinates')
        shape=compose(g.objects)
        if not shape.is_valid:raise Unsupported('composed image invalid')
    except (ValueError,AssertionError,SyntaxError,AttributeError,KeyError) as exc:
        raise Unsupported(str(exc)) from exc
    return {'geometry':shape,'objects':g.objects,'file_attrs':g.file_attrs,'inventory':dict(p.inventory),'object_types':dict(collections.Counter(type(o).__name__ for o in g.objects))}
