#!/usr/bin/env python3
"""Apply bounded circle/rectangle junction blends AFTER frozen C02 T02.

Original result232, all source parts and independent-audit limitations remain.
"""
from pathlib import Path
import sys,json,hashlib,argparse,subprocess,shutil,html
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import box,GeometryCollection
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.junction_spindle_blend import spindle_blend,check_spindle
from src.native_reference import one
from tools.run_c02_growth_coverage import render
import sexpdata
B=ROOT/'out/crop_dynamic_tasks';CACHE=B/'c02_focused_growth_coverage_20261028_05/inputs'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,d):p.write_text(json.dumps(d,indent=2)+'\n')

def load_scene(freeze):
 receipt=read(freeze/'FREEZE_RECEIPT.json');assert sha((freeze/'SHA256SUMS.json').read_bytes())==receipt['manifest_sha256']
 for name,h in read(freeze/'SHA256SUMS.json').items():assert sha((freeze/name).read_bytes())==h
 bank=read(freeze/'source_manifest.json');assert bank['source_sha256']==receipt['source_sha256'];raw=(CACHE/'ORG_source.kicad_pcb').read_bytes();assert sha(raw)==receipt['source_sha256'];meta={r['id']:r for r in bank['objects']};original={}
 for sid,r in meta.items():
  blob=(CACHE/'source_wkb'/f"{r['geometry_sha256']}.wkb").read_bytes();assert sha(blob)==r['geometry_sha256'];original[sid]=from_wkb(blob)
 current=dict(original)
 for r in read(freeze/'REPLACEMENTS.json'):
  blob=(freeze/r['path']).read_bytes();assert sha(blob)==r['sha256'];current[r['source_id']]=from_wkb(blob)
 crop=box(*receipt['viewport_mm']);groups={}
 for sid,r in meta.items():
  g=original[sid]
  if r['kind'] not in ('gr_circle','gr_poly') or not g.intersects(crop):continue
  if r['kind']=='gr_poly' and not g.equals(box(*g.bounds)):continue
  node=sexpdata.loads(raw[slice(*r['source_span'])].decode());fill=str(one(node,'fill',['none'])[0])
  if fill not in ('yes','solid'):continue
  groups.setdefault((r['kind'],r['geometry_sha256']),[]).append(sid)
 lands=[]
 for (kind,_),members in groups.items():
  sid=min(members);geom=current[sid];assert all(current[s].equals(geom) for s in members)
  lands.append(dict(id=sid,source_ids=sorted(members),kind='circle' if kind=='gr_circle' else 'rectangle',geometry=geom,original=original[sid]))
 for row in read(freeze/'INCLUSIVE_MERGES.json'):
  sid='inclusive:'+row['candidate'];blob=(freeze/'merges'/f"{row['candidate']}.wkb").read_bytes();assert sha(blob)==row['geometry_sha256'];geom=from_wkb(blob);current[sid]=geom
  lands.append(dict(id=sid,source_ids=[sid],native_land_members=row['rectangle_members'],kind='inclusive_rectangle',geometry=geom,original=unary_union([original[s] for s in row['rectangle_members']])))
 ids=sorted(current);tree=STRtree([current[s] for s in ids]);exposed=[];skipped=[]
 for land in lands:
  allowed=set(land['source_ids']);g=land['geometry'];others=[current[ids[int(i)]] for i in tree.query(g,predicate='intersects') if ids[int(i)] not in allowed]
  if others and g.difference(unary_union(others)).area<=1e-12:
   skipped.append(dict(id=land['id'],kind=land['kind'],reason='FULLY_COVERED_BY_OTHER_CURRENT_COPPER'));continue
  exposed.append(land)
 routes=read(freeze/'T04_CONSTRUCTION.json')
 for r in routes:
  for part in r['primitives']:assert sha(to_wkb(current[part['source_id']]))==part['nominal_candidate_wkb_sha256']
 return receipt,original,current,meta,exposed,skipped,routes,crop


def main(freeze,out):
 if not freeze.resolve().is_relative_to(ROOT) or not out.resolve().is_relative_to(ROOT/'out') or out.exists():raise ValueError('PROJECT_LOCAL_FRESH_OUTPUT_REQUIRED')
 assets=verify_assets();receipt,original,current,meta,lands,skipped,routes,crop=load_scene(freeze);ids=sorted(current);tree=STRtree([current[s] for s in ids]);before_blob=(freeze/'before_T05.wkb').read_bytes();assert sha(before_blob)==receipt['after_sha256'];before=from_wkb(before_blob);out.mkdir();(out/'patches').mkdir();accepted=[];rows=[]
 for route in sorted(routes,key=lambda r:r['component_id']):
  rid=route['component_id'];source_ids=route['complete_source_ids'];trace=unary_union([current[s] for s in source_ids]);oldtrace=unary_union([original[s] for s in source_ids]);attached=[d for d in lands if oldtrace.intersection(d['original']).area>1e-12 and trace.intersection(d['geometry']).area>1e-12]
  row=dict(route_id=rid,source_ids=source_ids,nominal_width_mm=route['uniform_nominal_width_mm'],land_ids=[d['id'] for d in attached],land_kinds=[d['kind'] for d in attached],status='KEEP')
  if not attached:row['reason']='NO_EXPOSED_SOURCE_QUALIFIED_LAND_CONTACT';rows.append(row);continue
  owner=unary_union([trace]+[d['geometry'] for d in attached]);radius=min(min(d['geometry'].bounds[2]-d['geometry'].bounds[0],d['geometry'].bounds[3]-d['geometry'].bounds[1])/2 for d in attached)
  if radius<=0:raise ValueError('INVALID_LAND_SIZE')
  window=unary_union([d['geometry'].buffer(2*radius,quad_segs=64) for d in attached]).intersection(crop);allowed=set(source_ids)|{s for d in attached for s in d['source_ids']};foreign=[(ids[int(i)],current[ids[int(i)]]) for i in tree.query(window.buffer(.02011)) if ids[int(i)] not in allowed]
  base_foreign=foreign[:];foreign += [('T05:'+a['id'],a['addition']) for a in accepted];barriers=unary_union([g.buffer(.02011,quad_segs=64) for _,g in foreign if not g.difference(owner).is_empty]);attempts=[];best=None
  for scale in [1.,.75,.5,.25]:
   try:
    _,addition=spindle_blend(owner,radius*scale,window);addition=addition.difference(barriers);candidate=owner.union(addition);check=check_spindle(owner,candidate,addition,window,foreign)
   except ValueError as e:attempts.append(dict(scale=scale,error=str(e)));continue
   attempts.append(dict(scale=scale,passed=check['passed'],failures=check['failures'],added_area_mm2=addition.area))
   if check['passed'] and addition.area>1e-8:best=(addition,check,scale);break
  row['attempts']=attempts
  if best is None:row['reason']='NO_VALID_BOUNDED_ADDITIVE_BLEND';rows.append(row);continue
  addition,check,scale=best;cid='J-'+sha(rid.encode())[:16];row.update(id=cid,status='GROWN',blend_radius_mm=radius*scale,window_sha256=sha(to_wkb(window)),owner_sha256=sha(to_wkb(owner)),addition_sha256=sha(to_wkb(addition)),added_area_mm2=addition.area,check=check)
  for suffix,g in [('',addition),('_window',window),('_owner',owner)]:(out/'patches'/f'{cid}{suffix}.wkb').write_bytes(to_wkb(g))
  accepted.append(dict(id=cid,owner=owner,window=window,addition=addition,foreign=base_foreign));rows.append(row)
 final=[]
 for a in accepted:
  foreign=a['foreign']+[(b['id'],b['addition']) for b in accepted if b['id']!=a['id']];check=check_spindle(a['owner'],a['owner'].union(a['addition']),a['addition'],a['window'],foreign);assert check['passed'],(a['id'],check['failures']);final.append(dict(id=a['id'],check=check))
 additions=unary_union([a['addition'] for a in accepted]);after=before.union(additions);assert before.difference(after).area<=1e-12
 for name,h in read(freeze/'SHA256SUMS.json').items():assert sha((freeze/name).read_bytes())==h
 for name,g in [('before',before),('after',after),('added',after.difference(before))]:(out/f'{name}.wkb').write_bytes(to_wkb(g))
 save(out/'DECISIONS.json',rows);save(out/'SKIPPED_COVERED_LANDS.json',skipped);save(out/'FINAL_CHECKS.json',final)
 covered_routes={s for r in routes for s in r['complete_source_ids']};coverage=[]
 for sid,r in meta.items():
  if r.get('trace_width_mm',0)<=0 or not original[sid].intersects(crop) or sid in covered_routes:continue
  contacts=[d['id'] for d in lands if original[sid].intersection(d['original']).area>1e-12]
  if not contacts:continue
  geom=current[sid];neighbors=[current[ids[int(i)]] for i in tree.query(geom,predicate='intersects') if ids[int(i)]!=sid];visible=geom.difference(unary_union(neighbors)).area
  coverage.append(dict(source_id=sid,land_ids=contacts,exposed_area_mm2=visible,disposition='FULLY_COVERED_SOURCE_SKIP' if visible<=1e-12 else 'OUTSIDE_FROZEN_T04_ROUTE_SET_RETAINED_NOT_TREATED'))
 save(out/'NONROUTE_SOURCE_CONTACTS.json',coverage)
 result=dict(status='C02_T05_AFTER_T02_LOCAL_SPINDLE_CANDIDATE',assets=assets,predecessor_freeze_sha256=sha((freeze/'FREEZE_RECEIPT.json').read_bytes()),predecessor_sha256=sha(before_blob),source_sha256=receipt['source_sha256'],after_sha256=sha(to_wkb(after)),sequence=['T01','T03_NO_ROUTE_CHANGE','T04','T02','T05'],routes_evaluated=len(routes),grown_routes=len(accepted),keep_routes=len(routes)-len(accepted),grown_land_contact_incidences=sum(len(r['land_ids']) for r in rows if r['status']=='GROWN'),grown_rectangle_contact_incidences=sum(k!='circle' for r in rows if r['status']=='GROWN' for k in r['land_kinds']),added_area_mm2=after.difference(before).area,covered_lands_skipped=len(skipped),exposed_nonroute_source_contacts=sum(r['disposition'].startswith('OUTSIDE') for r in coverage),frozen_predecessor='UNCHANGED_EXACT_BYTES',T01_T04_T02_source_parts='ALL_606_UNCHANGED',routes_and_nominal_widths='UNCHANGED',independent_qualification='OPEN; inherited REV234 strict replay REVISE not waived',owner_new_T05_acceptance='PENDING_USER',limitations='Bounded additive junction model; all KEEP and nonroute contacts retained; no native/electrical/manufacturing or final owner acceptance')
 save(out/'RESULT.json',result);(out/'source_snapshot').mkdir()
 for name in ['tools/run_c02_t05_spindle.py','src/junction_spindle_blend.py']:shutil.copyfile(ROOT/name,out/'source_snapshot'/Path(name).name)
 for name,title,g,d in [('before','C02 / frozen T01 + T04 + T02',before,GeometryCollection()),('after','C02 / T05 after T02 / cumulative copper',after,GeometryCollection()),('growth','C02 / actual T05 junction addition',after,after.difference(before))]:
  p=out/f'{name}.svg';render(p,title,g,d,receipt['viewport_mm'],[],{},[f"{len(accepted)} trace routes blended; {result['grown_land_contact_incidences']} land-contact incidences; {result['grown_rectangle_contact_incidences']} rectangle incidences.",'Teal = actual T05 added copper only. Frozen result232 and all source parts retained.',f"{result['keep_routes']} KEEP routes; {result['exposed_nonroute_source_contacts']} exposed source contacts outside frozen T04 route set recorded.",'Local model checks; inherited independent audit REVISE remains open. No native/electrical/manufacturing claim.']);subprocess.run(['sips','-s','format','png',str(p),'--out',str(p.with_suffix('.png'))],capture_output=True,check=True)
 table=''.join('<tr><td>'+html.escape(r['route_id'])+'</td><td>'+r['status']+'</td><td>'+html.escape(', '.join(r['land_kinds']))+'</td><td>'+html.escape(r.get('reason','Additive blend passed'))+'</td></tr>' for r in rows)
 (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 T05 after T02</title><style>body{font:18px system-ui;max-width:1600px;margin:30px auto}img{width:100%}td{padding:8px;border-bottom:1px solid #ddd}</style><h1>C02 · T01 → T03 → T04 → T02 → T05</h1><p>New additive junction candidate on exact accepted result232. Prior C01 accepted result frozen separately. Existing independent-audit limits retained.</p><h2>Frozen predecessor</h2><img src="before.png"><h2>Cumulative after T05</h2><img src="after.png"><h2>Actual T05 addition</h2><img src="growth.png"><table>'+table+'</table><p><a href="RESULT.json">Bound result</a> · <a href="DECISIONS.json">Every attempt and source contact</a> · <a href="NONROUTE_SOURCE_CONTACTS.json">Other source contacts</a> · <a href="FINAL_CHECKS.json">Final simultaneous checks</a></p>');print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('freeze',type=Path);p.add_argument('out',type=Path);main(**vars(p.parse_args()))
