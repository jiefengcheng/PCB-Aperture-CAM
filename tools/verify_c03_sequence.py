#!/usr/bin/env python3
"""Final-source C03 sequence replay; no search-history or independent-review claim."""
from pathlib import Path
import sys,argparse,json,functools
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import Point,box
from shapely.affinity import scale
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.source_offset_width import construct_source_offset_width
from src.prepared_width_scene import PreparedWidthScene
from src.prepared_land_scene import PreparedLandScene
from src.crop_stage_growth import check_proposal,GrowthContract
from src.junction_spindle_blend import spindle_blend,check_spindle
from tools.c03_sequence_scene import load_scene,read,save,sha,CACHE
from tools.run_c03_junction_stage import load_junction_scene

def main(run):
 out=run/'verification'
 if out.exists() or not run.resolve().is_relative_to(ROOT/'out'):raise ValueError('FRESH_PROJECT_LOCAL_VERIFICATION_REQUIRED')
 assets=verify_assets();scope,meta,original,current,protected,routes=load_scene(run,'T04');crop=box(*scope['viewport_mm']);raw=(CACHE/'ORG_source.kicad_pcb').read_bytes();out.mkdir();scope_rows={r['source_id']:r for r in scope['records']};t01count=0
 for d in read(run/'T01/DECISIONS.json'):
  g=original[d['source_id']] if not d['positive_growth'] else Point(*scope_rows[d['source_id']]['center_mm']).buffer(d['selected_diameter_mm']/2,quad_segs=128)
  assert sha(to_wkb(g))==d['candidate_sha256'] and g.covers(original[d['source_id']]);assert d['radius_factor']<=1.5+1e-12;t01count+=1
 definitions=read(run/'eligibility/UNIFORM_SOURCE_PATHS.json');paths={r['path_id']:dict(r,component_id=r['path_id']) for r in definitions['paths'] if r['definition_status']=='VISIBLE_COMPLETE_UNIFORM_PATH_PROPOSAL_CONTACT_CHECKS_RETAINED'};groups=read(run/'groups/PARALLEL_MEMBERSHIP.json');assignment={cid:r['group_id'] for r in groups['groups'] for cid in r['members']};width=read(run/'T04/RESULT.json');assert set(paths)==set(assignment)=={r['component_id'] for r in routes};represented={s for r in routes for s in r['complete_source_ids']};blobs={s:(CACHE/'source_wkb'/f"{meta[s]['geometry_sha256']}.wkb").read_bytes() for s in represented};nominal=[];envelopes=[];partcount=0
 for r in routes:
  rid=r['component_id'];factor=width['selected_scales'][assignment[rid]];assert 1<=factor<=1.5 and r['factor']==factor and r['complete_source_ids']==paths[rid]['source_ids'];rr,np,ep,core,n,e=construct_source_offset_width(raw,paths[rid],meta,blobs,factor)
  for p in r['primitives']:
   sid=p['source_id'];assert to_wkb(np[sid])==(run/'T04/nominal_source_parts'/f'{sha(sid.encode())}.wkb').read_bytes();assert p['nominal_candidate_width_mm']==meta[sid]['trace_width_mm']*factor;partcount+=1
  nominal.append(dict(id=rid,original=core,candidate=n,verified_original_width_mm=r['verified_original_width_mm']));envelopes.append(dict(id=rid,original=core,candidate=e,verified_original_width_mm=r['verified_original_width_mm']))
 fixed=[dict(id=s,geometry=g,trace_width_mm=meta[s]['trace_width_mm']) for s,g in current.items() if s not in represented];checker=PreparedWidthScene(nominal,fixed);qn=checker.check(nominal);qe=checker.check(envelopes);assert qn['passed'] and qe['passed'] and qn['evaluation_complete'] and qe['evaluation_complete'];save(out/'T04_FINAL_NOMINAL_CHECK.json',qn);save(out/'T04_FINAL_ENVELOPE_CHECK.json',qe)
 ids=sorted(current);tree=STRtree([current[s] for s in ids]);assembled=unary_union([current[ids[int(i)]] for i in tree.query(crop,predicate='intersects')]).intersection(crop);assert sha(to_wkb(assembled))==width['after_sha256'];save(out/'T04_REPLAY.json',dict(status='PASS_FINAL_SOURCE_CONSTRUCTOR_AND_CURRENT_SCENE_REPLAY',routes=len(routes),parts=partcount,search_history='Stored check hashes verified below; rejected-probe geometry not all re-executed'))
 for row in read(run/'T04/CHECK_INDEX.json'):assert sha((run/'T04'/row['path']).read_bytes())==row['sha256']
 print(json.dumps(dict(stage='T04_verified',routes=len(routes),parts=partcount)),flush=True)
 # Rebind exact rectangle transforms and original source ports against the full
 # post-T04 scene, not against pre-width traces or later candidate visibility.
 rects=read(run/'T02/DECISIONS.json');rectids={r['source_id'] for r in rects};selected={}
 for r in rects:
  sid=r['source_id'];sx,sy=r['factors'];assert 1<=sx<=1.25 and 1<=sy<=1.25;g=original[sid] if sx==sy==1. else scale(original[sid],sx,sy,origin=original[sid].centroid);assert sha(to_wkb(g))==r['candidate_sha256'];assert g.covers(original[sid]) and g.difference(crop).area<=1e-12;selected[sid]=g
 lands=[dict(id=s,original=original[s],candidate=selected[s],native_source_kind='gr_poly',native_stroke_width_mm=0.) for s in sorted(rectids)];fixed=[dict(id=s,geometry=g,trace_width_mm=meta[s]['trace_width_mm']) for s,g in current.items() if s not in rectids];lc=PreparedLandScene(lands,fixed)
 for sid in sorted(rectids):
  for i in lc.tree.query(original[sid],predicate='intersects'):
   oid=lc.ids[int(i)]
   if oid==sid:continue
   overlap=original[sid].intersection(original[oid]);contact=not overlap.is_empty;port=overlap.buffer(max(lc.widths[sid],lc.widths[oid])+lc.contract.original_port_buffer_gap_mm,quad_segs=lc.contract.port_quad_segs) if contact else None;lc.ports[(sid,oid)]=(port,contact,original[sid].distance(original[oid]))
 q=lc.check(lands);assert q['passed'] and q['evaluation_complete'];save(out/'T02_ORDINARY_SOURCE_RECHECK.json',q)
 before=from_wkb((run/'T04/after.wkb').read_bytes());rebuilt=before.union(unary_union([selected[s].difference(original[s]) for s in sorted(rectids)]));assert to_wkb(rebuilt)==(run/'T02/ordinary_after.wkb').read_bytes()
 for r in rects:
  for sid in r['aliases']:current[sid]=selected[r['source_id']]
 ids=sorted(current);tree=STRtree([current[s] for s in ids]);accepted_merges=[]
 for r in read(run/'T02/INCLUSIVE_CANDIDATES.json'):
  if r['status']!='MERGED':continue
  rect=box(*unary_union([current[s] for s in r['rectangle_members']]).bounds);assert sha(to_wkb(rect))==r['inclusive_wkb_sha256'];span=rebuilt.intersection(rect);shortage=rect.difference(span).area/rect.area;assert shortage<=.20 and abs(shortage-r['missing_area_fraction'])<1e-12 and span.geom_type=='Polygon';near=[ids[int(i)] for i in tree.query(rect.buffer(.021))];supports=set(r['rectangle_members'])|set(r['support_trace_source_ids']);support_union=unary_union([current[s] for s in supports]);assert all(current[s].difference(support_union).is_empty for s in r['covered_sources_skipped']);omit=supports|set(r['covered_sources_skipped']);neighbors=[dict(source_id=s,original=current[s],geometry=current[s],trace_width_mm=meta[s]['trace_width_mm']) for s in near if s not in omit];q=check_proposal(span,rect,neighbors,crop=crop,cap=rect,contract=GrowthContract());assert q['passed'];addition=rect.difference(rebuilt)
  for previous in accepted_merges:
   outside=previous.difference(span);assert outside.is_empty or addition.is_empty or addition.distance(outside)>=.0201
  rebuilt=rebuilt.union(rect);accepted_merges.append(rect)
 assert sha(to_wkb(rebuilt))==read(run/'T02/RESULT.json')['after_sha256'];print(json.dumps(dict(stage='T02_verified',rectangles=len(rects),merges=len(accepted_merges))),flush=True)
 # Saved T05 geometry is reconstructed directly, independently of the shared
 # stage fitter, with the same explicitly qualified source operands.
 scope,meta,original,current,protected,routes,crop,landrows,skipped=load_junction_scene(run);route_map={r['component_id']:r for r in routes};ids=sorted(current);tree=STRtree([current[s] for s in ids]);patches=[];t05=read(run/'T05/RESULT.json');decisions=read(run/'T05/DECISIONS.json');assert [r['route_id'] for r in decisions]==sorted(route_map)
 for row in decisions:
  r=route_map[row['route_id']];assert row['source_ids']==r['complete_source_ids'] and row['nominal_width_mm']==r['uniform_nominal_width_mm'];trace=unary_union([current[s] for s in row['source_ids']]);oldtrace=unary_union([original[s] for s in row['source_ids']]);attached=[d for d in landrows if oldtrace.intersection(d['original']).area>1e-12 and trace.intersection(d['geometry']).area>1e-12];assert row['land_ids']==[d['id'] for d in attached]
  if row['status']!='GROWN':continue
  owner=unary_union([trace]+[d['geometry'] for d in attached]);radius=min(min(d['geometry'].bounds[2]-d['geometry'].bounds[0],d['geometry'].bounds[3]-d['geometry'].bounds[1])/2 for d in attached);assert any(abs(row['blend_radius_mm']-radius*s)<=1e-14 for s in [1.,.75,.5,.25]);window=unary_union([d['geometry'].buffer(2*radius,quad_segs=64) for d in attached]).intersection(crop);allowed=set(row['source_ids'])|{s for d in attached for s in d['source_ids']};foreign=[(ids[int(i)],current[ids[int(i)]]) for i in tree.query(window.buffer(.02011)) if ids[int(i)] not in allowed];base_foreign=foreign[:];foreign += [('T05:'+p['id'],p['addition']) for p in patches];barriers=unary_union([g.buffer(.02011,quad_segs=64) for _,g in foreign if not g.difference(owner).is_empty]);_,addition=spindle_blend(owner,row['blend_radius_mm'],window);addition=addition.difference(barriers)
  for suffix,g,key in [('',addition,'addition_sha256'),('_owner',owner,'owner_sha256'),('_window',window,'window_sha256')]:assert sha(to_wkb(g))==row[key]==sha((run/'T05/patches'/f"{row['id']}{suffix}.wkb").read_bytes())
  patches.append(dict(id=row['id'],owner=owner,window=window,addition=addition,foreign=base_foreign))
 checks=[]
 for p in patches:
  q=check_spindle(p['owner'],p['owner'].union(p['addition']),p['addition'],p['window'],p['foreign']+[(o['id'],o['addition']) for o in patches if o['id']!=p['id']]);assert q['passed'];checks.append(dict(id=p['id'],check=q))
 rebuilt=rebuilt.union(unary_union([p['addition'] for p in patches]));assert sha(to_wkb(rebuilt))==t05['after_sha256']==sha((run/'T05/after.wkb').read_bytes());save(out/'T05_FINAL_SOURCE_RECHECK.json',checks)
 protected_crops=[]
 for r in read(run/'START_RECEIPT.json')['protected_accepted_crops']:
  p=ROOT/r['path'];receipt=read(p/'FREEZE_RECEIPT.json');assert sha((p/'FREEZE_RECEIPT.json').read_bytes())==r['receipt_sha256'];manifest=read(p/'SHA256SUMS.json') if (p/'SHA256SUMS.json').exists() else receipt['files']
  for name,h in manifest.items():assert sha((p/'frozen'/name).read_bytes())==h
  protected_crops.append(dict(crop=r['path'],unchanged=True,verified_files=len(manifest)))
 gaps=[p['gap_mm'] for c in checks for p in c['check']['pairs'] if p.get('gap_mm') is not None];receipt=dict(status='PASS_SAME_ASSISTANT_C03_FINAL_SOURCE_SEQUENCE_REPLAY',asset_integrity=assets,T01_circles=t01count,T03_route_changes=0,T04_routes=len(routes),T04_source_parts=partcount,T04_scales_and_source_parts='RECONSTRUCTED_EXACTLY_FULL_FINAL_NOMINAL_AND_ENVELOPE_CHECKS_PASS',T04_search_history='Every saved check file hash verified; all failed candidate geometries not freshly rerun',T02_rectangles=len(rects),T02_inclusive_merges=len(accepted_merges),T05_reconstructed_patches=len(patches),T05_minimum_added_foreign_gap_mm=min(gaps) if gaps else None,after_sha256=t05['after_sha256'],protected_accepted_crops=protected_crops,registration=scope['screenshot_registration'],owner_acceptance='PENDING_USER',independent_native_electrical_manufacturing='NOT_ESTABLISHED');save(out/'REPLAY.json',receipt);print(json.dumps(receipt))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);main(**vars(p.parse_args()))
