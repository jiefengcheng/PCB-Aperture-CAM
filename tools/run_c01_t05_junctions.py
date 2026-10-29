#!/usr/bin/env python3
"""Source-bound additive T05 tapers on a frozen C01 T01 + T04 scene.

No T02, route editing, trace narrowing, ABI adapter or source-fixture mutation.
"""
from pathlib import Path
import argparse,hashlib,json,sys,math,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import Point,LineString,box,GeometryCollection
from shapely.ops import unary_union,substring
from src.crop_circle_sources import verify_assets
from src.trace_land_junctions import JunctionContract,fit_taper,verify_taper
from src.native_reference import one
from tools.run_c02_growth_coverage import render
import sexpdata


def sha(blob):return hashlib.sha256(blob).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def main(freeze,width,definitions,cache,out):
    inputs=[freeze,width,definitions,cache]
    if any(not p.resolve().is_relative_to(ROOT) for p in inputs):raise ValueError('PROJECT_LOCAL_INPUTS_REQUIRED')
    if out.exists() or not out.resolve().is_relative_to(ROOT/'out'):raise ValueError('FRESH_PROJECT_OUTPUT_REQUIRED')
    assets=verify_assets();f=json.loads((freeze/'FREEZE_RECEIPT.json').read_text());P=freeze/'frozen'
    for name,h in f['file_bindings'].items():assert sha((P/name).read_bytes())==h
    w=json.loads((width/'RESULT.json').read_text());before_blob=(width/'after.wkb').read_bytes();assert sha(before_blob)==w['after_sha256'];before=from_wkb(before_blob)
    raw=(P/'ORG_source.kicad_pcb').read_bytes();assert sha(raw)==f['source_sha256']==w['source_sha256']
    bank=json.loads((cache/'source_manifest.json').read_text());assert bank['source_sha256']==f['source_sha256'];meta={r['id']:r for r in bank['objects']};original={}
    for sid,r in meta.items():
        blob=(cache/'source_wkb'/f"{r['geometry_sha256']}.wkb").read_bytes();assert sha(blob)==r['geometry_sha256'];original[sid]=from_wkb(blob)
    current=dict(original);t01=json.loads((P/'report.json').read_text());lands=[];claimed=set()
    for d in t01['decisions']:
        blob=(P/d['geometry']['dynamic']).read_bytes();assert sha(blob)==d['candidate_sha256'];geom=from_wkb(blob)
        for sid in d['aliases']:current[sid]=geom;claimed.add(sid)
        lands.append(dict(id=d['source_id'],aliases=d['aliases'],label=d['key'],kind='circle',original=original[d['source_id']],geometry=geom))
    # Actual original filled rectangles, not arbitrary circular IDs or group boxes.
    rect_groups={}
    for sid,r in meta.items():
        if r['kind']!='gr_poly' or not original[sid].intersects(box(*f['viewport_mm'])):continue
        node=sexpdata.loads(raw[slice(*r['source_span'])].decode());fill=str(one(node,'fill',['none'])[0])
        if fill not in ('yes','solid') or not original[sid].equals(box(*original[sid].bounds)):continue
        rect_groups.setdefault(r['geometry_sha256'],[]).append(sid)
    for members in rect_groups.values():
        sid=min(members);lands.append(dict(id=sid,aliases=sorted(members),label='RECT:'+sid.rsplit(':',2)[1],kind='rectangle',original=original[sid],geometry=current[sid]))
    construction=json.loads((width/'CONSTRUCTION.json').read_text());routes={r['component_id']:r for r in construction};d=json.loads((definitions/'UNIFORM_SOURCE_PATHS.json').read_text());paths={r['path_id']:r for r in d['paths']};trace_geoms={};trace_original={}
    for rid,r in routes.items():
        blobs=[]
        for part in r['primitives']:
            sid=part['source_id'];blob=(width/'nominal_source_parts'/f'{sha(sid.encode())}.wkb').read_bytes();assert sha(blob)==part['nominal_candidate_wkb_sha256'];current[sid]=from_wkb(blob);blobs.append(current[sid])
        trace_geoms[rid]=unary_union(blobs);trace_original[rid]=unary_union([original[s] for s in r['complete_source_ids']])
    ids=sorted(current);tree=STRtree([current[s] for s in ids]);crop=box(*f['viewport_mm']);contract=JunctionContract();contacts=[];unresolved=[]
    for rid,path in sorted(paths.items()):
        if rid not in routes:continue
        points=path['ordered_route_points_mm'];line=LineString(points)
        if line.length<=0:continue
        for land in sorted(lands,key=lambda x:x['id']):
            if not land['original'].intersects(crop) or trace_original[rid].intersection(land['original']).area<=1e-12:continue
            inside=line.intersection(land['geometry']);pieces=[inside] if inside.geom_type=='LineString' else list(getattr(inside,'geoms',()))
            found=False
            for piece in pieces:
                if piece.geom_type!='LineString' or piece.length<=1e-12:continue
                stations=[line.project(Point(p)) for p in piece.coords];lo,hi=min(stations),max(stations);middle=(lo+hi)/2
                for direction,approach in [('forward',substring(line,0,middle))] if hi>=line.length-1e-10 else [('reverse',substring(line,line.length,middle))] if lo<=1e-10 else [('forward',substring(line,0,middle)),('reverse',substring(line,line.length,middle))]:
                    if approach.geom_type!='LineString' or approach.length<=0:continue
                    if lo<=1e-10 and hi>=line.length-1e-10:continue
                    key=json.dumps([rid,land['id'],direction,round(middle,12)],separators=(',',':'));cid='J-'+sha(key.encode())[:16]
                    contacts.append(dict(id=cid,route_id=rid,land=land,route_toward_land=list(approach.coords),width_mm=routes[rid]['uniform_nominal_width_mm'],direction=direction,source_interval_end_arclength_mm=middle));found=True
            if not found:
                embedded=trace_geoms[rid].difference(land['geometry']).is_empty or land['geometry'].difference(trace_geoms[rid]).is_empty
                unresolved.append(dict(route_id=rid,land_source_id=land['id'],reason='FULLY_EMBEDDED_OWNER_CONTACT_NO_EXPOSED_NECK' if embedded else 'SOURCE_SIDE_CONTACT_WITHOUT_QUALIFIED_CENTERLINE_APPROACH',classification='NOT_A_SEPARATE_EXPOSED_JUNCTION' if embedded else 'UNRESOLVED_LOCAL_OPERATOR',source_width_preserved=True))
    contacts=list({c['id']:c for c in contacts}.values());out.mkdir();(out/'patches').mkdir();accepted=[];decisions=[];scopes={}
    for contact in sorted(contacts,key=lambda x:x['id']):
        cid,rid,land=contact['id'],contact['route_id'],contact['land'];trace=trace_geoms[rid];allowed=set(routes[rid]['complete_source_ids'])|set(land['aliases']);reach=LineString(contact['route_toward_land']).intersection(land['geometry'].buffer(contract.taper_length_widths*contact['width_mm']+contract.max_flare_ratio*contact['width_mm']))
        foreign=[dict(id=ids[int(i)],geometry=current[ids[int(i)]]) for i in tree.query(reach.envelope.buffer(contract.construction_gap_mm+contract.max_flare_ratio*contact['width_mm'])) if ids[int(i)] not in allowed]
        foreign += [dict(id='T05:'+a['id'],geometry=a['proposal']['patch']) for a in accepted]
        best,attempts=fit_taper(contact['route_toward_land'],trace,land['geometry'],contact['width_mm'],foreign)
        row={k:v for k,v in contact.items() if k!='land'};row.update(land_source_id=land['id'],land_aliases=land['aliases'],land_label=land['label'],land_kind=land['kind'],original_contact_area_mm2=trace_original[rid].intersection(land['original']).area,trace_part_ids=routes[rid]['complete_source_ids'],attempts=attempts)
        if best is None:row.update(status='KEEP_NO_VALID_BOUNDED_TAPER',reason='Construction, station, robust witness or foreign-clearance constraints block growth')
        else:
            proposal,check=best;addition=proposal['patch'].difference(trace.union(land['geometry']))
            if proposal['window'].difference(crop).area>contract.area_epsilon_mm2:row.update(status='KEEP_CROP_BOUNDARY',reason='Bounded writable window crosses C01 crop')
            elif addition.area<=contract.area_epsilon_mm2:row.update(status='KEEP_NO_VISIBLE_ADDITION',reason='Existing owner copper already covers the proposed taper')
            else:
                row.update(status='GROWN',alpha=proposal['alpha'],check=check,patch_sha256=sha(to_wkb(proposal['patch'])),window_sha256=sha(to_wkb(proposal['window'])),width_mm=proposal['width_mm'],stations=proposal['stations']);(out/'patches'/f'{cid}.wkb').write_bytes(to_wkb(proposal['patch']));(out/'patches'/f'{cid}_window.wkb').write_bytes(to_wkb(proposal['window']));accepted.append(dict(id=cid,contact=contact,proposal=proposal));scopes[cid]=foreign
        decisions.append(row)
    # Full final repeat includes later accepted patches, not just preceding ones.
    final_checks=[]
    for a in accepted:
        c=a['contact'];base=[n for n in scopes[a['id']] if not n['id'].startswith('T05:')];base += [dict(id='T05:'+b['id'],geometry=b['proposal']['patch']) for b in accepted if b['id']!=a['id']]
        check=verify_taper(a['proposal'],trace_geoms[c['route_id']],c['land']['geometry'],base);assert check['passed'],(a['id'],check['failures']);final_checks.append(dict(id=a['id'],check=check))
    patches=unary_union([a['proposal']['patch'] for a in accepted]);after=before.union(patches);assert before.difference(after).area<=1e-12
    for name,h in f['file_bindings'].items():assert sha((P/name).read_bytes())==h
    for name,geom in [('before',before),('after',after),('added',after.difference(before))]:(out/f'{name}.wkb').write_bytes(to_wkb(geom))
    for name,data in [('DECISIONS',decisions),('UNRESOLVED_CONTACTS',unresolved),('FINAL_CHECKS',final_checks)]:save(out/f'{name}.json',data)
    result=dict(status='C01_T05_LOCAL_ADDITIVE_JUNCTION_PROPOSAL',assets=assets,freeze_receipt_sha256=sha((freeze/'FREEZE_RECEIPT.json').read_bytes()),T04_result_sha256=sha((width/'RESULT.json').read_bytes()),T04_predecessor_sha256=sha(before_blob),source_sha256=sha(raw),qualified_contacts=len(contacts),grown=sum(r['status']=='GROWN' for r in decisions),kept=sum(r['status']!='GROWN' for r in decisions),unresolved_contacts=len(unresolved),circle_land_candidates=sum(c['land']['kind']=='circle' for c in contacts),rectangle_land_candidates=sum(c['land']['kind']=='rectangle' for c in contacts),added_area_mm2=after.difference(before).area,after_sha256=sha(to_wkb(after)),frozen_T01='ALL266FILES_UNCHANGED',T04_trace_parts='UNCHANGED; local T05 taper additions only',routes='UNCHANGED',T02='NOT_APPLIED',contract=contract.__dict__,implementation_sha256={p:sha((ROOT/p).read_bytes()) for p in ['src/trace_land_junctions.py','tools/run_c01_t05_junctions.py']},independent_qualification='OPEN',owner_acceptance='PENDING_USER');save(out/'RESULT.json',result)
    for name,geom,delta in [('before',before,GeometryCollection()),('clean_after',after,GeometryCollection()),('growth',after,after.difference(before))]:
        path=out/f'{name}.svg';render(path,'C01 / T05 junction tapers / '+name,geom,delta,f['viewport_mm'],[],{},[f'{result["grown"]} additive neck tapers; {result["kept"]} unchanged candidates; {len(unresolved)} unresolved source contacts.','Teal = actual T05 addition. Frozen T01 and T04 source parts retained exactly; no T02.','17 declared width stations plus eroded connectivity witness; full local foreign-copper checks.','Local geometric proposal; independent/native/electrical/manufacturing qualification open.']);subprocess.run(['sips','-s','format','png',str(path),'--out',str(path.with_suffix('.png'))],capture_output=True,check=True)
    table=''.join(f'<tr><td>{r["id"]}</td><td>{r["land_label"]}</td><td>{r["status"]}</td><td>{r.get("alpha",0):.6f}</td></tr>' for r in decisions)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C01 T05 junction tapers</title><style>body{font:18px system-ui;max-width:1500px;margin:30px auto}img{width:100%}td{padding:8px;border-bottom:1px solid #ddd}</style><h1>C01 T05 · additive land–trace necks</h1><p>Actual source-bound candidates. Frozen T01 and existing T04 source parts unchanged. T02 not applied.</p><h2>Before</h2><img src="before.png"><h2>Clean after</h2><img src="clean_after.png"><h2>Actual added neck copper in teal</h2><img src="growth.png"><table>'+table+'</table><p><a href="RESULT.json">Result</a> · <a href="DECISIONS.json">Attempts, source identities and width checks</a> · <a href="UNRESOLVED_CONTACTS.json">Unresolved source contacts</a> · <a href="FINAL_CHECKS.json">Final simultaneous checks</a></p>')
    print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['freeze','width','definitions','cache','out']:p.add_argument(name,type=Path)
    a=p.parse_args();main(a.freeze,a.width,a.definitions,a.cache,a.out)
