"""Read-only validator for the explicitly supported single-layer V1 coupon subset.

Gerbonara owns parsing. The lexical guard only rejects unqualified semantics;
it never produces geometry. No copper net attribute is used for connectivity.
"""
from pathlib import Path
import hashlib, json, math, re, warnings
from gerbonara.rs274x import GerberFile
from gerbonara.graphic_objects import Flash, Line, Region
from gerbonara.apertures import RectangleAperture, CircleAperture
from shapely.geometry import box, Polygon, LineString, Point
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
TOL = 0.001
# 128 chords/quadrant: radial underestimate <= radius*(1-cos(pi/512)).
QUADS = 128
ROLES = {'F_Cu': ('Copper','L1','Top'), 'F_Mask': ('Soldermask','Top'), 'Edge_Cuts': ('Profile','NP')}
class Unsupported(ValueError): pass

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def guard(text):
    # Strict lexical coverage, including commands Gerbonara may merely warn about.
    for line in text.splitlines():
        s = line.strip()
        if not s: continue
        if s.startswith('%'):
            if not s.endswith('%'): raise Unsupported('multiline extended operation')
            v = s[1:-1]
            if re.fullmatch(r'(?:TF|TA|TO)\.[A-Za-z]+,[^*%]*\*|TD(?:\.[A-Za-z]+)?\*|FSLAX46Y46\*|MOMM\*|LPD\*|ADD\d+(?:C,\d+\.\d+|R,\d+\.\d+X\d+\.\d+)\*', v): continue
            raise Unsupported('unsupported extended command: '+s)
        if s.startswith('G04 ') and s.endswith('*'): continue
        if re.fullmatch(r'(?:G01|G36|G37|M02|D\d+)\*|(?:X-?\d+)?(?:Y-?\d+)?D0[123]\*', s): continue
        raise Unsupported('unsupported operation: '+s)
    if text.count('M02*') != 1 or not text.rstrip().endswith('M02*'):
        raise Unsupported('missing or misplaced end marker')

def load(path, role):
    text = Path(path).read_text()
    guard(text)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try: g = GerberFile.open(path)
        except Exception as exc: raise Unsupported('parse error: '+str(exc)) from exc
    if caught: raise Unsupported('parser warning: '+'; '.join(str(w.message) for w in caught))
    if g.file_attrs.get('.FileFunction') != ROLES[role]: raise Unsupported('unknown layer role')
    expected = ('Negative',) if role == 'F_Mask' else ('Positive',)
    polarity = g.file_attrs.get('.FilePolarity')
    if polarity != expected and not (role == 'Edge_Cuts' and polarity is None):
        raise Unsupported('unsupported file polarity')
    if str(g.unit) != 'mm': raise Unsupported('unsupported units')
    shapes, pads, widths = [], {}, []
    for index, o in enumerate(g.objects):
        if not o.polarity_dark: raise Unsupported('clear image operations unsupported')
        if isinstance(o, Flash) and isinstance(o.aperture, RectangleAperture):
            a=o.aperture
            if a.hole_dia or min(a.w,a.h)<=0: raise Unsupported('invalid pad aperture')
            shape=box(o.x-a.w/2,-o.y-a.h/2,o.x+a.w/2,-o.y+a.h/2)
            pin=o.attrs.get('.P')
            if role!='F_Cu' or pin is None or pin[0]!='CPN1' or pin[1] not in ('1','2','3','4'):
                raise Unsupported('unknown terminal identity')
            key='P'+pin[1]
            if key in pads: raise Unsupported('duplicate terminal')
            pads[key]=(o.x,-o.y,shape)
        elif isinstance(o, Line) and isinstance(o.aperture, CircleAperture):
            a=o.aperture
            if a.hole_dia or a.diameter<=0: raise Unsupported('invalid stroke aperture')
            if a.diameter/2*(1-math.cos(math.pi/(4*QUADS)))>TOL/10:
                raise Unsupported('stroke polygonization error exceeds numerical budget')
            shape=LineString([(o.x1,-o.y1),(o.x2,-o.y2)]).buffer(a.diameter/2,quad_segs=QUADS)
            widths.append(a.diameter)
            if role=='F_Mask': raise Unsupported('mask stroke outside qualified subset')
        elif isinstance(o, Region):
            if role!='F_Mask' or any(c is not None for c in o.arc_centers):
                raise Unsupported('region type outside qualified subset')
            shape=Polygon([(x,-y) for x,y in o.outline])
            if not shape.is_valid or shape.is_empty: raise Unsupported('invalid region')
        else: raise Unsupported('object outside qualified subset: '+type(o).__name__)
        if not shape.is_valid or shape.is_empty: raise Unsupported('invalid geometry')
        shapes.append(shape)
    if not shapes: raise Unsupported('empty layer')
    return {'geometry':unary_union(shapes), 'objects':shapes,'pads':pads,'widths':widths,
            'inventory':{'path':str(path),'sha256':sha(path),'role':role,'polarity':polarity,
                         'objects':len(shapes),'types':[type(o).__name__ for o in g.objects]}}

def layers(directory):
    return {role:load(Path(directory)/('coupon-'+role+'.gbr'),role) for role in ROLES}

def equivalent(a,b):
    # Both distance directions, with area guard to prevent tiny distant additions.
    return a.hausdorff_distance(b)<=TOL and a.symmetric_difference(b).area<=TOL*(a.length+b.length)

def evaluate(before, candidate):
    checks=[]
    def check(key,ok,actual):
        checks.append({'id':key,'status':'PASS' if ok else 'FAIL','mandatory':True,
                       'actual':actual,'tolerance':{'linear_mm':TOL},
                       'evidence':[str(before),str(candidate)]})
    try: b,c=layers(before),layers(candidate)
    except (Unsupported, OSError, ValueError) as exc:
        return {'checks':[{'id':'coverage','status':'NOT_ESTABLISHED','mandatory':True,
                          'evidence':[str(exc)]}],'overall':'NOT_ESTABLISHED','coverage':{}}
    check('coverage',True,{k:v['inventory'] for k,v in c.items()})
    check('fixed_reference',all(equivalent(b[k]['geometry'],c[k]['geometry']) for k in ('F_Mask','Edge_Cuts')),
          {k:b[k]['geometry'].symmetric_difference(c[k]['geometry']).area for k in ('F_Mask','Edge_Cuts')})
    bp,cp=b['F_Cu']['pads'],c['F_Cu']['pads']
    if set(bp)!=set(('P1','P2','P3','P4')) or set(cp)!=set(bp):
        check('terminal_inventory',False,list(cp)); return {'checks':checks,'overall':'FAIL','coverage':{}}
    policy=json.loads((ROOT/'assets/starter/reference/policy.json').read_text())
    intent=json.loads((ROOT/'assets/starter/reference/intended_connections.json').read_text())
    # Aperture association from independent A1 intent; geometry comes only from Gerber.
    opening=next((s for s in c['F_Mask']['objects'] if s.covers(Point(20,20))),None)
    before_opening=next((s for s in b['F_Mask']['objects'] if s.covers(Point(20,20))),None)
    margin=policy['minimum_overlap_mm']+policy['registration_uncertainty_xy_mm']
    if opening is None:
        check('exposure',False,'A1 not located')
    else:
        expanded=box(opening.bounds[0]-margin,opening.bounds[1]-margin,
                     opening.bounds[2]+margin,opening.bounds[3]+margin)
        exposed=opening.intersection(c['F_Cu']['geometry']).area
        check('exposure',cp['P1'][2].buffer(TOL,join_style=2).covers(expanded),
              {'candidate_exposed_mm2':exposed,'opening_mm2':opening.area,
               'before_exposed_mm2':before_opening.intersection(b['F_Cu']['geometry']).area if before_opening else None,
               'required_margin_mm':margin,'uncovered_expanded_mm2':expanded.difference(cp['P1'][2]).area})
        offset=[cp['P1'][i]-opening.centroid.coords[0][i] for i in (0,1)]
        check('center_registration',all(abs(v)<=policy['maximum_nominal_center_error_xy_mm']+TOL for v in offset),offset)
    copper=c['F_Cu']['geometry']
    components=list(copper.geoms) if copper.geom_type=='MultiPolygon' else [copper]
    assigned={}
    for key,(x,y,_) in cp.items():
        hits=[i for i,s in enumerate(components) if s.covers(Point(x,y))]
        if len(hits)==1: assigned[key]=hits[0]
    connected=all(a in assigned and d in assigned and assigned[a]==assigned[d] for a,d in intent['pairs'])
    # Erode the whole copper by half minimum width minus numerical tolerance:
    # rejects point contact and narrow necks despite nominal topological connection.
    core=copper.buffer(-(policy['minimum_trace_width_mm']/2-TOL),quad_segs=QUADS)
    robust=list(core.geoms) if core.geom_type=='MultiPolygon' else [core]
    neck_ok=all(any(s.covers(Point(cp[a][:2])) and s.covers(Point(cp[d][:2])) for s in robust) for a,d in intent['pairs'])
    check('connectivity',connected and neck_ok,{'terminal_components':assigned,'components':len(components),'minimum_neck_mm':0.2,'erosion_connected':neck_ok})
    n1={assigned[k] for k in assigned if intent['pin_net_intent'][k]=='N1'}
    n2={assigned[k] for k in assigned if intent['pin_net_intent'][k]=='N2'}
    check('no_short',not bool(n1 & n2),{'merged_components':sorted(n1 & n2)})
    orphan=set(range(len(components)))-n1-n2
    check('copper_assignment',not orphan,{'unassigned_components':sorted(orphan)})
    distance=min((components[i].distance(components[j]) for i in n1 for j in n2),default=0)
    check('clearance',distance>=policy['minimum_copper_clearance_mm']+TOL,{'minimum_mm':distance,'required_mm':0.2})
    check('trace_width',bool(c['F_Cu']['widths']) and min(c['F_Cu']['widths'])>=0.2+TOL,c['F_Cu']['widths'])
    delta=b['F_Cu']['geometry'].symmetric_difference(copper)
    allowed=box(*policy['allowed_copper_change_rectangle']).buffer(TOL,join_style=2)
    protected=all(equivalent(bp[k][2],cp[k][2]) for k in ('P2','P3','P4'))
    # Explicit invariant strokes T4 and T5 matched by their physical shapes, not net labels.
    protected_tracks=[s for s in b['F_Cu']['objects'] if s.bounds[1]>=22.875-TOL or s.bounds[0]>22]
    protected=protected and all(any(equivalent(s,t) for t in c['F_Cu']['objects']) for s in protected_tracks)
    check('scope',protected and delta.difference(allowed).area<=1e-9,
          {'outside_authorized_region_mm2':delta.difference(allowed).area,'protected_objects_equal':protected})
    move=Point(bp['P1'][:2]).distance(Point(cp['P1'][:2]))
    size=[cp['P1'][2].bounds[2]-cp['P1'][2].bounds[0],cp['P1'][2].bounds[3]-cp['P1'][2].bounds[1]]
    check('target_geometry',move<=0.5+TOL and all(abs(x-y)<=TOL for x,y in zip(size,policy['allowed_pad_size_mm'])),{'movement_mm':move,'size_mm':size})
    return {'checks':checks,'overall':'FAIL' if any(x['status']=='FAIL' for x in checks) else 'PASS',
            'coverage':{'before':{k:v['inventory'] for k,v in b.items()},'candidate':{k:v['inventory'] for k,v in c.items()}}}
