#!/usr/bin/env python3
"""C03 T05 using the consolidated spindle stage on exact post-T02 copper."""
from pathlib import Path
import sys,argparse,json,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import box,GeometryCollection
from shapely.ops import unary_union
from src.native_reference import one
from src.crop_circle_sources import verify_assets
from src.junction_spindle_stage import CONTRACT,prepare_spindle_context,fit_spindle_blend,verify_spindle_batch,assemble_spindle_scene
from tools.c03_sequence_scene import load_scene,read,save,sha,CACHE
from tools.render_c03_source_frame import render_source_frame as render
import sexpdata

def load_junction_scene(run):
 scope,meta,original,current,protected,routes=load_scene(run,'T02');crop=box(*scope['viewport_mm']);raw=(CACHE/'ORG_source.kicad_pcb').read_bytes();groups={}
 for sid,r in meta.items():
  g=original[sid]
  if r['kind'] not in ('gr_circle','gr_poly') or not g.intersects(crop):continue
  if r['kind']=='gr_poly' and not g.equals(box(*g.bounds)):continue
  node=sexpdata.loads(raw[slice(*r['source_span'])].decode());fill=str(one(node,'fill',['none'])[0])
  if fill not in ('yes','solid'):continue
  groups.setdefault((r['kind'],r['geometry_sha256']),[]).append(sid)
 lands=[]
 for (kind,_),members in groups.items():
  sid=min(members);g=current[sid]
  if not all(current[s].equals(g) for s in members):raise ValueError('LAND_ALIAS_CURRENT_GEOMETRY_CONFLICT')
  lands.append(dict(id=sid,source_ids=sorted(members),kind='circle' if kind=='gr_circle' else 'rectangle',geometry=g,original=original[sid]))
 for row in read(run/'T02/INCLUSIVE_CANDIDATES.json'):
  if row['status']=='MERGED':lands.append(dict(id='inclusive:'+row['candidate'],source_ids=['inclusive:'+row['candidate']],kind='inclusive_rectangle',geometry=current['inclusive:'+row['candidate']],original=unary_union([original[s] for s in row['rectangle_members']])))
 ids=sorted(current);tree=STRtree([current[s] for s in ids]);visible=[];skipped=[]
 for land in lands:
  g=land['geometry'];allowed=set(land['source_ids']);others=[current[ids[int(i)]] for i in tree.query(g,predicate='intersects') if ids[int(i)] not in allowed]
  if others and g.difference(unary_union(others)).area<=1e-12:skipped.append(dict(id=land['id'],kind=land['kind'],reason='FULLY_COVERED'));continue
  visible.append(land)
 return scope,meta,original,current,protected,routes,crop,visible,skipped

def main(run):
 out=run/'T05'
 if not run.resolve().is_relative_to(ROOT/'out') or out.exists():raise ValueError('PROJECT_LOCAL_FRESH_STAGE_REQUIRED')
 assets=verify_assets();scope,meta,original,current,protected,routes,crop,lands,skipped=load_junction_scene(run);ids=sorted(current);tree=STRtree([current[s] for s in ids]);before_blob=(run/'T02/after.wkb').read_bytes();before=from_wkb(before_blob);out.mkdir();(out/'patches').mkdir();accepted=[];decisions=[]
 for route in sorted(routes,key=lambda r:r['component_id']):
  rid=route['component_id'];sids=route['complete_source_ids'];trace=unary_union([current[s] for s in sids]);oldtrace=unary_union([original[s] for s in sids]);attached=[d for d in lands if oldtrace.intersection(d['original']).area>1e-12 and trace.intersection(d['geometry']).area>1e-12];row=dict(route_id=rid,source_ids=sids,nominal_width_mm=route['uniform_nominal_width_mm'],land_ids=[d['id'] for d in attached],land_kinds=[d['kind'] for d in attached],status='KEEP')
  if not attached:row['reason']='NO_EXPOSED_SOURCE_QUALIFIED_LAND_CONTACT';decisions.append(row);continue
  owner,radius,window=prepare_spindle_context(trace,[d['geometry'] for d in attached],crop);allowed=set(sids)|{s for d in attached for s in d['source_ids']};foreign=[(ids[int(i)],current[ids[int(i)]]) for i in tree.query(window.buffer(CONTRACT.barrier_gap_mm)) if ids[int(i)] not in allowed];base_foreign=foreign[:];foreign += [('T05:'+a['id'],a['addition']) for a in accepted];best,attempts=fit_spindle_blend(owner,radius,window,foreign);row['attempts']=attempts
  if best is None:row['reason']='NO_VALID_BOUNDED_ADDITIVE_BLEND';decisions.append(row);continue
  addition,check,scale=[best[k] for k in ['addition','check','scale']];cid='J-'+sha(rid.encode())[:16];row.update(id=cid,status='GROWN',blend_radius_mm=radius*scale,owner_sha256=sha(to_wkb(owner)),window_sha256=sha(to_wkb(window)),addition_sha256=sha(to_wkb(addition)),added_area_mm2=addition.area,check=check)
  for suffix,g in [('',addition),('_window',window),('_owner',owner)]:(out/'patches'/f'{cid}{suffix}.wkb').write_bytes(to_wkb(g))
  accepted.append(dict(id=cid,owner=owner,window=window,addition=addition,foreign=base_foreign));decisions.append(row)
 final=verify_spindle_batch(accepted);after=assemble_spindle_scene(before,accepted)
 for sid,blob in protected.items():assert to_wkb(current[sid])==blob,'PROTECTED_SOURCE_PART_CHANGED'
 for name,g in [('before',before),('after',after),('added',after.difference(before))]:(out/f'{name}.wkb').write_bytes(to_wkb(g))
 for name,d in [('DECISIONS.json',decisions),('FINAL_CHECKS.json',final),('SKIPPED_COVERED_LANDS.json',skipped),('STAGE_CONTRACT.json',CONTRACT.__dict__)]:save(out/name,d)
 # Every source stroke outside the trace-growth set keeps its original role.
 represented={s for r in routes for s in r['complete_source_ids']};eligibility={r['source_id']:r for r in read(run/'eligibility/SOURCE_ELIGIBILITY.json')};nonroutes=[]
 for sid,r in meta.items():
  if r['trace_width_mm']<=0 or sid in represented or not original[sid].intersects(crop):continue
  contact=[d['id'] for d in lands if original[sid].intersection(d['original']).area>1e-12]
  if not contact:continue
  g=current[sid].intersection(crop);others=[current[ids[int(i)]] for i in tree.query(g,predicate='intersects') if ids[int(i)]!=sid];area=g.difference(unary_union(others)).area;role=eligibility.get(sid,{})
  nonroutes.append(dict(source_id=sid,land_ids=contact,exposed_crop_area_mm2=area,prior_disposition=role.get('disposition','OUTSIDE_PARENT_ELIGIBILITY'),prior_reasons=role.get('reasons',[]),treatment='SKIP_FULLY_COVERED' if area<=1e-12 else 'FIXED_ROLE_RETAINED_NOT_GROWN'))
 save(out/'NONROUTE_CONTACTS.json',nonroutes)
 result=dict(status='C03_T01_T03_T04_T02_T05_LOCAL_CUMULATIVE_PROPOSAL',asset_integrity=assets,sequence=['T01','T03_NO_ROUTE_CHANGE','T04','T02','T05'],source_sha256=scope['source_sha256'],scope_sha256=sha((run/'T01/SUPPORTED_TARGETS.json').read_bytes()),predecessor_sha256=sha(before_blob),after_sha256=sha(to_wkb(after)),routes_evaluated=len(routes),grown_routes=len(accepted),keep_routes=len(routes)-len(accepted),land_contact_incidences=sum(len(r['land_ids']) for r in decisions if r['status']=='GROWN'),rectangle_contact_incidences=sum(k!='circle' for r in decisions if r['status']=='GROWN' for k in r['land_kinds']),covered_lands_skipped=len(skipped),added_area_mm2=after.difference(before).area,protected_T01_T04_T02_parts=len(protected),protected_parts='ALL_BYTE_IDENTICAL',source_registration=scope['screenshot_registration'],C01_C02='ACCEPTED_FROZEN_RESULTS_UNMODIFIED_SEPARATE_CROP_LINEAGES',owner_acceptance='PENDING_USER',independent_native_electrical_manufacturing='NOT_ESTABLISHED');save(out/'RESULT.json',result)
 for name,g,d in [('before',before,GeometryCollection()),('after',after,GeometryCollection()),('growth',after,after.difference(before))]:
  p=out/f'{name}.svg';render(p,f'C03 / T05 after T02 / {name}',g,d,scope['viewport_mm'],notes=[f"{len(accepted)} route blends;{result['land_contact_incidences']} land-contact incidences;{result['rectangle_contact_incidences']} rectangle incidences.",'Teal = actual T05 junction addition only; all earlier source contributions and widths/routes retained.',f"{result['keep_routes']} unchanged routes accounted for. Source localization remains provisional.",'Local source-derived candidate, not owner/independent/native/electrical/manufacturing acceptance.']);subprocess.run(['sips','-s','format','png',str(p),'--out',str(p.with_suffix('.png'))],capture_output=True,check=True)
 print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);main(**vars(p.parse_args()))
