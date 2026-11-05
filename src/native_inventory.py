from src.native_preparation import native_loads
"""Declared native-object inventory with exact occurrence locators.

Maintained sexpdata decodes semantics. Source geometry is diagnostic context,
never a replacement for the independent exported-Gerber acceptance checker.
Unsupported constructs remain queryable records with explicit reasons.
"""
import math
import re
import time
from collections import Counter
import sexpdata
from shapely import affinity,to_wkb
from shapely.geometry import Point,LineString,Polygon,box
from .source_locators import locate
from .native_reference import one,children
from .revision_catalog import digest

VERSION='native-inventory/2'
ERROR_MM=0.00001
KINDS={'footprint','module','pad','segment','arc','via','zone','filled_polygon','polygon','gr_line','gr_arc','gr_circle','gr_rect','gr_poly','gr_text','gr_text_box','gr_curve','fp_line','fp_arc','fp_circle','fp_rect','fp_poly','fp_text','fp_text_box','fp_curve','group','image','dimension','target'}

class UnsupportedGeometry(ValueError):pass

def steps(radius,sweep=math.pi/2):
    if radius<=0:raise UnsupportedGeometry('NON_POSITIVE_RADIUS')
    return max(1,math.ceil(sweep/(2*math.acos(max(-1,1-min(ERROR_MM/radius,1))))))

def arc_points(a,m,b):
    ax,ay=a;mx,my=m;bx,by=b
    d=2*(ax*(my-by)+mx*(by-ay)+bx*(ay-my))
    if abs(d)<1e-12:raise UnsupportedGeometry('DEGENERATE_ARC')
    x=((ax*ax+ay*ay)*(my-by)+(mx*mx+my*my)*(by-ay)+(bx*bx+by*by)*(ay-my))/d
    y=((ax*ax+ay*ay)*(bx-mx)+(mx*mx+my*my)*(ax-bx)+(bx*bx+by*by)*(mx-ax))/d
    angle=lambda p:math.atan2(p[1]-y,p[0]-x)
    forward=(angle(b)-angle(a))%(2*math.pi)
    sweep=forward if (angle(m)-angle(a))%(2*math.pi)<=forward else forward-2*math.pi
    radius=math.hypot(ax-x,ay-y);n=steps(radius,abs(sweep))
    return [a]+[(x+radius*math.cos(angle(a)+sweep*i/n),y+radius*math.sin(angle(a)+sweep*i/n)) for i in range(1,n)]+[b]

def inventory(source):
    started=time.perf_counter();spans=locate(source);locator_seconds=time.perf_counter()-started
    decode_started=time.perf_counter();decoded=native_loads(source.decode('utf-8'));source_decode_seconds=time.perf_counter()-decode_started
    if not decoded or str(decoded[0])!='kicad_pcb':raise ValueError('NOT_KICAD_BOARD')
    layer_table=children(decoded,'layers');layernames=[str(v[1]) for v in layer_table[0][1:] if isinstance(v,list)] if layer_table else []
    nets={int(n[1]):str(n[2]) for n in children(decoded,'net') if len(n)>2}
    metadata={'version','generator','generator_version','general','paper','title_block','layers','setup','net','net_class','embedded_fonts','embedded_files','property'}
    by_start={s.start:s for s in spans};selected={s.start:s for s in spans if s.head in KINDS or s.head.startswith(('gr_','fp_')) or (s.parent_start==spans[0].start and s.head not in metadata)}
    selected_decode_started=time.perf_counter()
    nodes={s.start:native_loads(source[s.start:s.end].decode('utf-8')) for s in selected.values()}
    selected_decode_seconds=time.perf_counter()-selected_decode_started
    geometry_seconds=0
    objects=[];payloads={};counts=Counter();instances=Counter();unsupported=Counter()
    for s in selected.values():
        node=nodes[s.start];kind=s.head;parent=s.parent_start
        while parent is not None and parent not in selected:parent=by_start[parent].parent_start
        parent_span=selected.get(parent);ancestor=parent
        while ancestor is not None and selected[ancestor].head not in ('footprint','module'):
            ancestor_parent=selected[ancestor].parent_start
            while ancestor_parent is not None and ancestor_parent not in selected:ancestor_parent=by_start[ancestor_parent].parent_start
            ancestor=ancestor_parent
        fp=nodes.get(ancestor) if ancestor is not None else None
        raw_layers=list(map(str,one(node,'layers',one(node,'layer',[]))))
        if not raw_layers and parent_span and parent_span.head=='zone':raw_layers=list(map(str,one(nodes[parent],'layers',one(nodes[parent],'layer',[]))))
        expanded=[];unresolved=[]
        for layer in raw_layers:
            matches=[n for n in layernames if n.endswith(layer[1:])] if layer.startswith('*.') else [layer] if layer in layernames else []
            if matches:expanded.extend(matches)
            else:unresolved.append(layer)
        if kind=='via' and len(expanded)==2 and all(l.endswith('.Cu') for l in expanded):
            copper=[l for l in layernames if l.endswith('.Cu')]
            def stack_position(name):
                if name=='F.Cu':return 0
                if name=='B.Cu':return 1000000
                match=re.fullmatch(r'In(\d+)\.Cu',name)
                if not match:raise UnsupportedGeometry('UNQUALIFIED_COPPER_STACK_ORDER')
                return int(match[1])
            try:
                copper.sort(key=stack_position)
                lo,hi=sorted(copper.index(l) for l in expanded);expanded=copper[lo:hi+1]
            except UnsupportedGeometry:
                unresolved.append('UNQUALIFIED_COPPER_STACK_ORDER')
        layer_set=sorted(set(expanded));counts[kind]+=1
        net=one(node,'net',[]);netcode=int(net[0]) if net and str(net[0]).lstrip('-').isdigit() else None
        native=one(node,'uuid',one(node,'tstamp',one(node,'id',[]) if kind=='group' else []))
        footprint_id=one(fp,'uuid',one(fp,'tstamp',[])) if fp else []
        reference=None
        if fp:
            for text in children(fp,'fp_text'):
                if str(text[1])=='reference':reference=str(text[2])
            for prop in children(fp,'property'):
                if str(prop[1])=='Reference':reference=str(prop[2])
        r={'id':s.identity,'parent_id':parent_span.identity if parent_span else None,'kind':kind,'native_id':str(native[0]) if native else None,'source_span':[s.start,s.end],'source_sha256':s.revision,'layers':layer_set,'unresolved_layers':unresolved,'layer_instances':[{'layer':l,'role':'copper' if l.endswith('.Cu') else 'opening' if l.endswith('.Mask') else 'drawing'} for l in layer_set],'net_code':netcode,'net_name':str(net[1]) if len(net)>1 and netcode else nets.get(netcode) if netcode else None,'geometry_sha256':None,'bounds_mm':None,'filled_area_mm2':None,'bbox_area_mm2':None,'aspect_width_over_height':None,'aspect_status':'NO_GEOMETRY','geometry_role':'source annotation','group_name':str(node[1]) if kind=='group' and len(node)>1 and not isinstance(node[1],list) else None,'native_group_members':list(map(str,one(node,'members',[]))) if kind=='group' else [],'pin':str(node[1]) if kind=='pad' else None,'footprint_native_id':str(footprint_id[0]) if footprint_id else None,'reference':reference,'source_terminal_key':str(footprint_id[0] if footprint_id else reference)+':'+str(node[1]) if kind=='pad' and fp else None,'nominal_anchor_mm':None,'coverage':'UNSUPPORTED','unsupported_reason':None}
        geometry_started=time.perf_counter()
        try:
            if unresolved:raise UnsupportedGeometry('UNRESOLVED_LAYER_MEMBERSHIP')
            if parent_span and parent_span.head=='pad':raise UnsupportedGeometry('CUSTOM_PAD_PRIMITIVE_CONTEXT_NOT_QUALIFIED')
            if kind in ('footprint','module','group'):raise UnsupportedGeometry('CONTAINER_ONLY: nested objects separately inventoried')
            if kind in ('zone','polygon'):raise UnsupportedGeometry('DECLARED_BOUNDARY_ONLY: effective copper requires stored filled_polygon')
            if fp and str(one(fp,'layer',['F.Cu'])[0])=='B.Cu':raise UnsupportedGeometry('BACK_FOOTPRINT_TRANSFORM_NOT_QUALIFIED')
            shape=geometry(node,kind)
            if fp:
                at=one(fp,'at',[0,0,0]);angle=float(at[2]) if len(at)>2 else 0
                if kind=='pad':
                    local=one(node,'at',[0,0]);a=math.radians(angle)
                    x=float(at[0])+math.cos(a)*local[0]+math.sin(a)*local[1]
                    y=float(at[1])-math.sin(a)*local[0]+math.cos(a)*local[1]
                    shape=affinity.translate(shape,x,y);r['nominal_anchor_mm']=[x,y]
                else:shape=affinity.translate(affinity.rotate(shape,-angle,origin=(0,0)),float(at[0]),float(at[1]))
            elif kind=='pad':
                at=one(node,'at',[0,0]);shape=affinity.translate(shape,float(at[0]),float(at[1]));r['nominal_anchor_mm']=list(map(float,at[:2]))
            if shape.is_empty:raise UnsupportedGeometry('EMPTY_EFFECTIVE_GEOMETRY')
            if not shape.is_valid:raise UnsupportedGeometry('INVALID_EFFECTIVE_GEOMETRY')
            data=to_wkb(shape);key=digest(data);payloads[key]=data;a,b,c,d=shape.bounds;w,h=c-a,d-b
            if not all(math.isfinite(v) for v in (a,b,c,d)):raise UnsupportedGeometry('NONFINITE_BOUNDS')
            r.update({'geometry_sha256':key,'bounds_mm':[a,b,c,d],'filled_area_mm2':shape.area,'bbox_area_mm2':w*h,'aspect_width_over_height':w/h if h else None,'aspect_status':'DEFINED' if h else 'DEGENERATE_HEIGHT','coverage':'GEOMETRY_AVAILABLE','geometry_role':'stored fill' if kind=='filled_polygon' else 'nominal native shape'})
        except (UnsupportedGeometry,TypeError,IndexError,KeyError,ValueError) as exc:
            r['unsupported_reason']=str(exc) or type(exc).__name__;unsupported[r['unsupported_reason']]+=1
        geometry_seconds+=time.perf_counter()-geometry_started
        for layer in layer_set:instances[layer]+=1
        objects.append(r)
    return {'version':VERSION,'source_sha256':spans[0].revision if spans else digest(source),'units':'mm','coordinates':'KiCad X right, Y down; no alignment or normalization','geometry_error_mm':2*ERROR_MM,'per_curve_approximation_error_mm':ERROR_MM,'objects':objects,'payloads':payloads,'counts':dict(counts),'layer_instance_counts':dict(instances),'unsupported_reasons':dict(unsupported),'metadata_exclusions':dict(Counter(s.head for s in spans if s.parent_start==spans[0].start and s.start not in selected)),'source_objects':len(objects),'layer_instances':sum(instances.values()),'geometry_available':sum(r['coverage']=='GEOMETRY_AVAILABLE' for r in objects),'timings':{'byte_locators_seconds':locator_seconds,'source_decode_seconds':source_decode_seconds,'selected_node_decode_seconds':selected_decode_seconds,'geometry_attempts_transforms_metrics_wkb_seconds':geometry_seconds},'elapsed_seconds':time.perf_counter()-started,'electrical_acceptance':'NOT_ESTABLISHED: inventory does not establish intent or continuity','native_export':'UNSUPPORTED: read-only original bytes and locators'}

def geometry(node,kind):
    def xy(name):return tuple(map(float,one(node,name)))
    width=float(one(node,'width',one((children(node,'stroke') or [[]])[0],'width',[0]))[0])
    if kind=='pad':
        w,h=map(float,one(node,'size'));shape_kind=str(node[3]);angle=one(node,'at',[0,0,0]);angle=float(angle[2]) if len(angle)>2 else 0
        if min(w,h)<=0:raise UnsupportedGeometry('NON_POSITIVE_PAD_SIZE')
        if children(node,'primitives'):raise UnsupportedGeometry('CUSTOM_PAD_PRIMITIVES')
        if shape_kind=='rect':shape=box(-w/2,-h/2,w/2,h/2)
        elif shape_kind=='circle' and w==h:shape=Point(0,0).buffer(w/2,quad_segs=steps(w/2))
        elif shape_kind in ('oval','roundrect'):
            radius=min(w,h)/2 if shape_kind=='oval' else min(w,h)*float(one(node,'roundrect_rratio',[0])[0])
            shape=box(-w/2+radius,-h/2+radius,w/2-radius,h/2-radius).buffer(radius,quad_segs=steps(radius)) if radius else box(-w/2,-h/2,w/2,h/2)
        else:raise UnsupportedGeometry('PAD_SHAPE_'+shape_kind)
        drill=one(node,'drill',[])
        if drill:
            if str(drill[0])=='oval':raise UnsupportedGeometry('OVAL_DRILL_NOT_QUALIFIED')
            radius=float(drill[0])/2;offset=one(drill,'offset',[0,0])
            shape=shape.difference(Point(*offset).buffer(radius,quad_segs=steps(radius)))
        return affinity.rotate(shape,-angle,origin=(0,0))
    if kind=='via':
        size=float(one(node,'size')[0]);drill=float(one(node,'drill')[0]);at=xy('at')
        if not 0<drill<size:raise UnsupportedGeometry('INVALID_VIA_ANNULUS')
        return Point(*at).buffer(size/2,quad_segs=steps(size/2)).difference(Point(*at).buffer(drill/2,quad_segs=steps(drill/2)))
    if kind in ('segment','gr_line','fp_line','arc','gr_arc','fp_arc'):
        if width<=0:raise UnsupportedGeometry('NON_POSITIVE_STROKE')
        pts=arc_points(xy('start'),xy('mid'),xy('end')) if kind.endswith('arc') or kind=='arc' else [xy('start'),xy('end')]
        return LineString(pts).buffer(width/2,quad_segs=steps(width/2))
    if kind in ('gr_circle','fp_circle'):
        a=xy('center');b=xy('end');radius=math.dist(a,b);fill=str(one(node,'fill',['none'])[0])
        if fill in ('yes','solid'):return Point(*a).buffer(radius,quad_segs=steps(radius))
        if width<=0:raise UnsupportedGeometry('NON_POSITIVE_STROKE')
        return Point(*a).buffer(radius+width/2,quad_segs=steps(radius+width/2)).difference(Point(*a).buffer(max(0,radius-width/2),quad_segs=steps(radius)))
    if kind in ('gr_rect','fp_rect','gr_poly','fp_poly','filled_polygon'):
        if kind.endswith('rect'):
            a=xy('start');b=xy('end');shape=box(min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1]))
        else:
            pts=children(node,'pts')[0];coords=[tuple(map(float,v[1:3])) for v in children(pts,'xy')];shape=Polygon(coords)
            if not shape.is_valid:
                from .gerber_image import contour
                shape=contour(coords+[coords[0]] if coords[0]!=coords[-1] else coords)
        if kind=='filled_polygon' or str(one(node,'fill',['none'])[0]) in ('yes','solid'):return shape
        if width<=0:raise UnsupportedGeometry('NON_POSITIVE_STROKE')
        return shape.boundary.buffer(width/2,quad_segs=steps(width/2))
    raise UnsupportedGeometry('UNQUALIFIED_GEOMETRY_'+kind)
