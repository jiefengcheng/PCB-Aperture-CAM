#!/usr/bin/env python3
"""Synthetic aperture-constrained copper demo, not a production CAM engine.

Generates JSON geometry, a deliberately small KiCad board/project and reference
Gerbers. Tests operate on JSON geometry using Shapely, NOT on KiCad exports.
All fixture dimensions are invented test parameters, not manufacturing rules.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import uuid

try:
    import shapely
    from shapely.geometry import box, LineString, Point
    from shapely.ops import unary_union
except ImportError as e:
    raise SystemExit('Install dependencies: python -m pip install -r requirements.txt') from e

ROOT = Path(__file__).resolve().parents[1]
EPS = 1e-8  # floating-point comparison allowance, NOT a manufacturing tolerance


def dump(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf8')


def uid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'aperture-cam-synthetic-v1/' + name))


def rect(cx: float, cy: float, w: float, h: float) -> dict:
    return {'cx': cx, 'cy': cy, 'w': w, 'h': h}


def rectangle(r: dict):
    return box(r['cx']-r['w']/2, r['cy']-r['h']/2,
               r['cx']+r['w']/2, r['cy']+r['h']/2)


def geometry(o: dict):
    if o['kind'] == 'pad':
        return rectangle(o)
    if o['kind'] == 'track':
        # Round caps are approximated. Only simple straight segments are supported.
        return LineString([o['start'], o['end']]).buffer(o['width']/2, quad_segs=64)
    raise ValueError(f"Unsupported object kind: {o['kind']}")


def route(cx: float, width: float = .25) -> list[dict]:
    # This pre-authorized 45-degree template is NOT a general router.
    pts = [[cx,20.0], [cx,21.5], [20.0,21.5+abs(cx-20.0)], [20.0,23.0]]
    # The candidate chosen below has cx=20.05, so no zero-length segments arise.
    return [{'id':f'T{i+1}','kind':'track','net':'N1','layer':'F.Cu',
             'start':pts[i], 'end':pts[i+1], 'width':width} for i in range(3)]


def original() -> dict:
    pads = [{'id':p,'kind':'pad','net':n,'layer':'F.Cu', **rect(x,y,1.4,1.8)}
            for p,n,x,y in [('P1','N1',20.35,20.0),('P2','N1',20.0,26.0),
                            ('P3','N2',23.0,20.0),('P4','N2',23.0,26.0)]]
    tracks = route(20.35) + [
        {'id':'T4','kind':'track','net':'N1','layer':'F.Cu','start':[20.0,23.0],
         'end':[20.0,26.0],'width':.25},
        {'id':'T5','kind':'track','net':'N2','layer':'F.Cu','start':[23.0,20.0],
         'end':[23.0,26.0],'width':.25}]
    apertures = [{'id':f'A{i+1}','layer':'F.Mask','role':'opening',
                  **rect(x,y,1.0,1.4)} for i,(x,y) in enumerate([(20.,20.),(20.,26.),(23.,20.),(23.,26.)])]
    return {'schema':'synthetic-aperture-coupon/1','units':'mm',
            'coordinate_frame':'KiCad top view, +Y down, absolute board coordinates',
            'outline':[17.,17.,26.,29.], 'objects':pads+tracks,'apertures':apertures}


POLICY = {
    'id':'invented-demo-policy/1', 'status':'SYNTHETIC_NOT_FACTORY_APPROVED',
    'units':'mm', 'aperture_role':'opening', 'mode':'copper_covers_aperture',
    'target_pad':'P1','target_aperture':'A1', 'write_ids':['P1','T1','T2','T3'],
    'allowed_copper_change_rectangle':[18.8,18.8,21.2,23.2],
    'minimum_overlap_mm':.10, 'registration_uncertainty_xy_mm':.05,
    'minimum_copper_clearance_mm':.20, 'minimum_trace_width_mm':.20,
    'maximum_pad_move_mm':.50, 'required_center_offset_xy_mm':[0.,0.],
    'maximum_nominal_center_error_xy_mm':.05,
    'allowed_pad_size_mm':[1.4,1.8],
    'required_pairs':[['P1','P2'],['P3','P4']],
    'pin_net_intent':{'P1':'N1','P2':'N1','P3':'N2','P4':'N2'},
    'export_geometry_tolerance_mm':.001,
    'limitations':['One front copper layer; axis-aligned rectangular pads and openings',
                   'No holes, zones, arcs, paste, components, bend, impedance or thermal constraints',
                   'JSON tests do not establish correctness of a KiCad or Gerber export']}


def indexed(model: dict) -> dict:
    return {o['id']:o for o in model['objects']}


def validate(base: dict, candidate: dict, policy: dict) -> dict:
    checks: dict[str,bool] = {}
    if policy.get('aperture_role') != 'opening':
        return {'status':'NEEDS_REVIEW','checks':{'known_aperture_role':False},
                'reason':'Aperture polarity/role is unresolved.'}
    bi, ci = indexed(base), indexed(candidate)
    pid = policy['target_pad']
    if pid not in ci:
        return {'status':'REJECT','checks':{'target_present':False}}
    p = ci[pid]
    a = next(a for a in base['apertures'] if a['id']==policy['target_aperture'])
    ap = rectangle(a)
    pad = rectangle(p)
    m = policy['minimum_overlap_mm']
    r = policy['registration_uncertainty_xy_mm']
    checks['aperture_layer_unchanged'] = base['apertures']==candidate['apertures']
    checks['board_outline_unchanged'] = base['outline']==candidate['outline']
    checks['object_set_unchanged'] = set(bi)==set(ci)
    checks['unrelated_objects_unchanged'] = all(ci.get(k)==v for k,v in bi.items() if k not in policy['write_ids'])
    checks['net_and_layer_identity_preserved'] = all(k in ci and ci[k]['net']==v['net'] and ci[k]['layer']==v['layer'] for k,v in bi.items())
    checks['pad_size_preserved'] = abs(p['w']-policy['allowed_pad_size_mm'][0])<EPS and abs(p['h']-policy['allowed_pad_size_mm'][1])<EPS
    checks['maximum_motion'] = math.hypot(p['cx']-bi[pid]['cx'],p['cy']-bi[pid]['cy'])<=policy['maximum_pad_move_mm']+EPS
    ce = policy['maximum_nominal_center_error_xy_mm']
    offx,offy = policy['required_center_offset_xy_mm']
    checks['nominal_center_registration'] = abs(p['cx']-a['cx']-offx)<=ce+EPS and abs(p['cy']-a['cy']-offy)<=ce+EPS
    # Box dilation exactly represents the chosen +/- X,Y uncertainty model.
    nom = box(*[ap.bounds[0]-m,ap.bounds[1]-m,ap.bounds[2]+m,ap.bounds[3]+m])
    robust = box(ap.bounds[0]-m-r,ap.bounds[1]-m-r,ap.bounds[2]+m+r,ap.bounds[3]+m+r)
    checks['nominal_overlap'] = nom.difference(pad).area<=EPS
    checks['robust_overlap'] = robust.difference(pad).area<=EPS
    checks['required_exposure'] = ap.difference(pad).area<=EPS
    gs = {k:geometry(o) for k,o in ci.items()}
    copper = unary_union(list(gs.values()))
    base_copper = unary_union([geometry(o) for o in bi.values()])
    allowed = box(*policy['allowed_copper_change_rectangle'])
    checks['copper_delta_inside_scope'] = copper.symmetric_difference(base_copper).difference(allowed).area<=EPS
    by_net = {n:unary_union([gs[k] for k,v in ci.items() if v['net']==n]) for n in set(v['net'] for v in ci.values())}
    nets=sorted(by_net)
    distances = [by_net[n].distance(by_net[n2]) for i,n in enumerate(nets) for n2 in nets[i+1:]]
    min_distance = min(distances,default=math.inf)
    checks['different_net_clearance'] = min_distance+EPS>=policy['minimum_copper_clearance_mm']
    # Physical contacts are computed independent of net assignments.
    adjacency={k:set() for k in ci}
    for i,k in enumerate(ci):
        for k2 in list(ci)[i+1:]:
            if gs[k].intersects(gs[k2]):
                adjacency[k].add(k2);adjacency[k2].add(k)
    def reachable(k: str) -> set:
        seen=set(); stack=[k]
        while stack:
            v=stack.pop()
            if v not in seen: seen.add(v);stack.extend(adjacency[v]-seen)
        return seen
    checks['required_connectivity'] = all(p1 in ci and p2 in ci and p2 in reachable(p1) for p1,p2 in policy['required_pairs'])
    checks['no_different_net_physical_merge'] = all(len({ci[x]['net'] for x in reachable(k)})==1 for k in ci)
    uncertain_opening = box(ap.bounds[0]-r,ap.bounds[1]-r,ap.bounds[2]+r,ap.bounds[3]+r)
    other = unary_union([gs[k] for k,v in ci.items() if v['net']!=p['net']])
    checks['no_foreign_copper_exposure_at_target'] = uncertain_opening.intersection(other).area<=EPS
    checks['trace_widths'] = all(v['width']+EPS>=policy['minimum_trace_width_mm'] for v in ci.values() if v['kind']=='track')
    return {'status':'PASS_INTERNAL_GEOMETRY' if all(checks.values()) else 'REJECT',
            'checks':checks,'metrics':{'pad_center_mm':[p['cx'],p['cy']],
             'pad_displacement_mm':[p['cx']-bi[pid]['cx'],p['cy']-bi[pid]['cy']],
             'aperture_area_mm2':ap.area,'target_exposed_copper_area_mm2':ap.intersection(pad).area,
             'minimum_different_net_clearance_mm':min_distance},
            'not_established':['KiCad load and DRC','KiCad-exported Gerber geometry',
                'Schematic parity','Fabricator acceptance','Physical registration or electrical performance']}


def repair(base: dict, policy: dict) -> tuple[dict|None,dict]:
    if policy.get('aperture_role')!='opening':
        return None,{'status':'NEEDS_REVIEW','reason':'Aperture layer role unknown'}
    c=copy.deepcopy(base); p=next(o for o in c['objects'] if o['id']==policy['target_pad'])
    a=next(a for a in c['apertures'] if a['id']==policy['target_aperture'])
    margin=policy['minimum_overlap_mm']+policy['registration_uncertainty_xy_mm']
    # Analytic feasible interval. No gold board or expected result is read.
    xmin=a['cx']+a['w']/2+margin-p['w']/2
    xmax=a['cx']-a['w']/2-margin+p['w']/2
    ymin=a['cy']+a['h']/2+margin-p['h']/2
    ymax=a['cy']-a['h']/2-margin+p['h']/2
    if xmin>xmax+EPS or ymin>ymax+EPS:
        return None,{'status':'NO_FEASIBLE_RECTANGULAR_TRANSLATION','reason':'Fixed pad cannot cover robust opening; resizing is not authorized'}
    x=round(min(max(p['cx'],xmin),xmax),6); y=round(min(max(p['cy'],ymin),ymax),6)
    if abs(y-20.)>EPS:
        return None,{'status':'UNSUPPORTED','reason':'This route template supports horizontal pad translation only'}
    p.update(cx=x,cy=y)
    rr={o['id']:o for o in route(x)}
    c['objects']=[rr.get(o['id'],o) for o in c['objects']]
    result=validate(base,c,policy)
    if result['status']!='PASS_INTERNAL_GEOMETRY':
        return None,{'status':'NO_ACCEPTABLE_TEMPLATE_CANDIDATE','validation':result,
                     'note':'This is not proof that every possible routing strategy is infeasible.'}
    return c,{'status':'CANDIDATE_CREATED','validation':result}


def write_kicad(model: dict, out: Path) -> None:
    out.mkdir(parents=True,exist_ok=True)
    s=['(kicad_pcb (version 20240108) (generator "aperture_cam_fixture")',
       ' (general (thickness 1.6)) (paper "A4")',
       ' (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (35 "F.Paste" user)',
       '  (37 "F.SilkS" user) (39 "F.Mask" user) (44 "Edge.Cuts" user)',
       '  (49 "F.Fab" user) (50 "User.1" user "DEMO_REFERENCE"))',
       ' (setup (pad_to_mask_clearance 0) (solder_mask_min_width 0))',
       ' (net 0 "") (net 1 "N1") (net 2 "N2")',
       f' (footprint "Synthetic:ContactCoupon" (layer "F.Cu") (tstamp {uid("footprint")}) (at 20 20)',
       '  (attr board_only exclude_from_pos_files exclude_from_bom)',
       '  (fp_text reference "CPN1" (at 0 -3) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))',
       '  (fp_text value "SYNTHETIC_NOT_FOR_FABRICATION" (at 0 -4) (layer "F.Fab") (effects (font (size .7 .7) (thickness .1))))']
    for o in model['objects']:
        if o['kind']=='pad':
            n=1 if o['net']=='N1' else 2
            s.append(f'  (pad "{o["id"][1:]}" smd rect (at {o["cx"]-20:.6f} {o["cy"]-20:.6f}) (size {o["w"]} {o["h"]}) (layers "F.Cu") (net {n} "{o["net"]}") (tstamp {uid(o["id"])}))')
    s.append(' )')
    for o in model['objects']:
        if o['kind']=='track':
            n=1 if o['net']=='N1' else 2
            s.append(f' (segment (start {o["start"][0]:.6f} {o["start"][1]:.6f}) (end {o["end"][0]:.6f} {o["end"][1]:.6f}) (width {o["width"]}) (layer "F.Cu") (net {n}) (tstamp {uid(o["id"])}))')
    for a in model['apertures']:
        x1,y1,x2,y2=rectangle(a).bounds
        # Board-level graphics are independent of pad/footprint position.
        s.append(f' (gr_rect locked (start {x1:.6f} {y1:.6f}) (end {x2:.6f} {y2:.6f}) (stroke (width 0) (type default)) (fill solid) (layer "F.Mask") (tstamp {uid(a["id"])}))')
    x1,y1,x2,y2=model['outline']
    s.append(f' (gr_rect locked (start {x1} {y1}) (end {x2} {y2}) (stroke (width .05) (type default)) (fill none) (layer "Edge.Cuts") (tstamp {uid("outline")}))')
    s.append(')')
    (out/'coupon.kicad_pcb').write_text('\n'.join(s)+'\n')
    (out/'coupon.kicad_dru').write_text('(version 1)\n(rule "Demo copper clearance" (constraint clearance (min 0.20mm)))\n(rule "Demo trace width" (constraint track_width (min 0.20mm)))\n')
    dump(out/'coupon.kicad_pro',{'meta':{'filename':'coupon.kicad_pro','version':1}})


def write_reference_gerber(model: dict, out: Path) -> None:
    """Small deterministic generator, NOT the KiCad plotter or a general writer.

    Uses only positive rectangles and circular-aperture straight strokes.
    Numeric Y sign is inverted to map the KiCad top-view Y-down frame to Gerber.
    These files require independent parser/viewer checks before use.
    """
    out.mkdir(parents=True,exist_ok=True)
    def coord(x,y): return f'X{round(x*1e6)}Y{round(-y*1e6)}'
    base=['G04 SYNTHETIC REFERENCE - NOT KICAD EXPORTED - NOT FOR FABRICATION*',
          '%FSLAX46Y46*%','%MOMM*%','%LPD*%','G01*']
    copper=base+['%ADD10R,1.4X1.8*%']
    widths=sorted({o['width'] for o in model['objects'] if o['kind']=='track'})
    for i,w in enumerate(widths): copper.append(f'%ADD{11+i}C,{w}*%')
    copper+=['D10*']
    for o in model['objects']:
        if o['kind']=='pad': copper.append(coord(o['cx'],o['cy'])+'D03*')
    for o in model['objects']:
        if o['kind']=='track':
            copper+= [f'D{11+widths.index(o["width"])}*', coord(*o['start'])+'D02*',coord(*o['end'])+'D01*']
    copper+=['M02*']
    (out/'reference-F_Cu.gbr').write_text('\n'.join(copper)+'\n')
    mask=base+['%ADD10R,1.0X1.4*%','D10*']
    mask+=[coord(a['cx'],a['cy'])+'D03*' for a in model['apertures']]
    mask+=['M02*']
    (out/'reference-F_Mask.gbr').write_text('\n'.join(mask)+'\n')


def main() -> None:
    base=original(); candidate,attempt=repair(base,POLICY)
    assert candidate is not None, attempt
    cases={'before':base,'candidate':candidate}
    c=copy.deepcopy(candidate); c['apertures'][0]['cx']+=.3;cases['reject_mask_moved']=c
    c=copy.deepcopy(candidate); c['objects']=[o for o in c['objects'] if o['id']!='T3'];cases['reject_connection_cut']=c
    c=copy.deepcopy(candidate); c['objects'].append({'id':'BRIDGE','kind':'track','net':'N1','layer':'F.Cu','start':[20.05,20.],'end':[23.,20.],'width':.25});cases['reject_short']=c
    c=copy.deepcopy(candidate); next(o for o in c['objects'] if o['id']=='P3')['cx']+=.1;cases['reject_scope']=c
    c=copy.deepcopy(candidate); next(o for o in c['objects'] if o['id']=='T1')['width']=.1;cases['reject_trace_width']=c
    c=copy.deepcopy(candidate); next(o for o in c['objects'] if o['id']=='P1')['cx']=20.08;cases['reject_nominal_only']=c
    results={name:validate(base,c,POLICY) for name,c in cases.items()}
    assert results['before']['status']=='REJECT'
    assert results['candidate']['status']=='PASS_INTERNAL_GEOMETRY'
    for name in cases:
        if name.startswith('reject_'): assert results[name]['status']=='REJECT',name
    assert results['reject_connection_cut']['checks']['required_connectivity'] is False
    assert results['reject_short']['checks']['no_different_net_physical_merge'] is False
    assert results['reject_nominal_only']['checks']['nominal_overlap'] is True
    assert results['reject_nominal_only']['checks']['robust_overlap'] is False
    missing=copy.deepcopy(POLICY);missing['aperture_role']='unknown'
    results['needs_review_role']=validate(base,candidate,missing)
    impossible=copy.deepcopy(POLICY);impossible['minimum_overlap_mm']=.30
    _,failure=repair(base,impossible);results['infeasible_fixed_pad']=failure
    assert failure['status']=='NO_FEASIBLE_RECTANGULAR_TRANSLATION'
    assert results['needs_review_role']['status']=='NEEDS_REVIEW'
    dump(ROOT/'reference'/'policy.json',POLICY)
    dump(ROOT/'reference'/'intended_connections.json',{'pairs':POLICY['required_pairs'],'pin_net_intent':POLICY['pin_net_intent'],'source':'synthetic author-supplied intent; not inferred from copper'})
    dump(ROOT/'reference'/'fixed_apertures.json',base['apertures'])
    dump(ROOT/'evidence'/'repair_attempt.json',attempt)
    for name,c in cases.items():
        d=ROOT/'fixtures'/name
        dump(d/'geometry.json',c);write_kicad(c,d/'kicad');write_reference_gerber(c,d/'reference_gerbers')
    dump(ROOT/'evidence'/'internal_geometry_results.json',results)
    dump(ROOT/'evidence'/'execution_status.json',{'python':platform.python_version(),'shapely':shapely.__version__,
        'internal_test_cases':len(results),'internal_expectations':'PASS',
        'kicad_load':'NOT_RUN','kicad_drc':'NOT_RUN','exported_gerber_validation':'NOT_RUN',
        'external_source_downloads':'NOT_BUNDLED','manufacturing_validation':'NOT_ESTABLISHED'})
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'fixtures').rglob('*')) if p.is_file()}
    dump(ROOT/'evidence'/'fixture_sha256.json',manifest)
    print(f'PASS: {len(results)} synthetic internal case expectations; KiCad and Gerber validation NOT RUN.')
    for name,v in results.items():print(f'{name:27} {v["status"]}')

if __name__=='__main__':
    main()
