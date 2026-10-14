"""Read-only completed-image and independently source-mapped checks."""
import hashlib,itertools,math
from shapely.geometry import Point
from gerbonara.graphic_objects import Flash
from .gerber_image import object_geometry

TOL=1e-5
ANCHOR_TOL=.002

def summary(g):
    parts=list(g.geoms) if g.geom_type=='MultiPolygon' else ([] if g.is_empty else [g])
    return {'area_mm2':g.area,'bounds_mm':list(g.bounds) if not g.is_empty else [],'components':len(parts),'holes':sum(len(x.interiors) for x in parts),'wkb_sha256':hashlib.sha256(g.wkb).hexdigest(),'empty':g.is_empty}

def equivalent(a,b):
    sa,sb=summary(a),summary(b)
    if sa['wkb_sha256']==sb['wkb_sha256']:return {'status':'PASS','symmetric_difference_mm2':0,'identity':'complete composed WKB identical','before':sa,'after':sb}
    delta=a.symmetric_difference(b).area
    topology=sa['components']==sb['components'] and sa['holes']==sb['holes'] and sa['empty']==sb['empty']
    mutual=a.difference(b.buffer(TOL)).is_empty and b.difference(a.buffer(TOL)).is_empty
    ok=delta<=TOL*(a.length+b.length) and topology and mutual
    return {'status':'PASS' if ok else 'FAIL','symmetric_difference_mm2':delta,'mutual_containment_within_mm':TOL,'mutual_containment':mutual,'topology_equal':topology,'before':sa,'after':sb}

def anchors(image,pads,layer):
    flashes=[o for o in image['objects'] if isinstance(o,Flash) and '.P' in o.attrs]
    rows=[];selected=[]
    for pad in pads:
        if layer not in pad['layers']:continue
        candidates=[o for o in flashes if o.attrs['.P'][:2]==(pad['ref'],pad['pin']) and math.dist((o.x,o.y),pad['center_mm'])<=ANCHOR_TOL]
        if len(candidates)!=1:
            rows.append({'source_id':pad['source_id'],'status':'NOT_ESTABLISHED','reason':'ambiguous/missing source-terminal association','matches':len(candidates)});continue
        o=candidates[0];shape=object_geometry(o);reference=pad['shape']
        ok=reference is not None and shape.symmetric_difference(reference).area<=ANCHOR_TOL*(shape.length+reference.length)
        inside=image['geometry'].covers(Point(pad['center_mm']))
        rows.append({'source_id':pad['source_id'],'ref':pad['ref'],'pin':pad['pin'],'center_mm':pad['center_mm'],'net':pad['net'],'gerber_terminal_attribute':o.attrs['.P'],'center_error_mm':math.dist((o.x,o.y),pad['center_mm']),'source_shape_delta_mm2':shape.symmetric_difference(reference).area if reference is not None else None,'copper_at_source_center':inside,'status':'PASS' if ok and inside else 'FAIL'})
        selected.append(pad)
    return {'status':'PASS' if all(r['status']=='PASS' for r in rows) else 'NOT_ESTABLISHED' if any(r['status']=='NOT_ESTABLISHED' for r in rows) else 'FAIL','terminals':rows,'count':len(rows)}

def intent_check(copper,pads,source_routes,layer):
    parts=[] if copper.is_empty else list(copper.geoms) if copper.geom_type=='MultiPolygon' else [copper]
    labeled={};mapping={};pairs=[]
    for p in pads:
        if layer not in p['layers'] or not p['net']:continue
        hits=[i for i,g in enumerate(parts) if g.covers(Point(p['center_mm']))]
        if len(hits)==1:
            mapping[p['source_id']]=hits[0];labeled.setdefault(hits[0],set()).add(p['net'])
    shorts=[{'component':i,'source_nets':sorted(n)} for i,n in labeled.items() if len(n)>1]
    for (l,net),geom in source_routes.items():
        if l!=layer:continue
        source_parts=list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]
        terminals=[p for p in pads if layer in p['layers'] and p['net']==net]
        for a,b in itertools.combinations(terminals,2):
            if not any(g.covers(Point(a['center_mm'])) and g.covers(Point(b['center_mm'])) for g in source_parts):continue
            aa,bb=mapping.get(a['source_id']),mapping.get(b['source_id'])
            pairs.append({'source_net':net,'a':a['source_id'],'b':b['source_id'],'status':'PASS' if aa is not None and aa==bb else 'FAIL'})
    tagged=[(i,next(iter(n))) for i,n in labeled.items() if len(n)==1]
    distances=[parts[i].distance(parts[j]) for (i,n),(j,m) in itertools.combinations(tagged,2) if n!=m]
    return {'no_short':'FAIL' if shorts else 'PASS' if labeled else 'NOT_ESTABLISHED','shorts':shorts,
            'connections':'FAIL' if any(x['status']=='FAIL' for x in pairs) else 'PASS' if pairs else 'NOT_ESTABLISHED','source_justified_same_layer_pairs':pairs,
            'terminal_mappings':mapping,'named_net_components':len(labeled),'unlabeled_components':len(parts)-len(labeled),
            'measured_named_net_clearance_mm':min(distances) if distances else None,
            'whole_board_clearance_acceptance':'NOT_ESTABLISHED','factory_threshold':None,
            'limitation':'Same-layer source-justified pairs and source-labeled components only; unassigned copper and cross-layer connectivity not qualified.'}


def physical_connections(copper,segments,layer):
    parts=[] if copper.is_empty else list(copper.geoms) if copper.geom_type=='MultiPolygon' else [copper]
    rows=[]
    for s in segments:
        if s['layer']!=layer:continue
        aa=Point(s['a']);bb=Point(s['b'])
        ok=any(g.covers(aa) and g.covers(bb) for g in parts)
        rows.append({**s,'status':'PASS' if ok else 'FAIL'})
    return {'status':'PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL','pairs':rows,
            'meaning':'Preserve each independently source-declared same-layer straight conductor endpoint relation; no named net inferred.'}
