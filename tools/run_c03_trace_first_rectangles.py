#!/usr/bin/env python3
"""C03 T02 after T04: whole rectangles, joint source-visible checks, <=20% inclusive fills."""
from pathlib import Path
import sys,json,argparse,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import box,GeometryCollection
from shapely.affinity import scale
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.prepared_land_scene import PreparedLandScene
from src.joint_rectangle_growth import fit_joint_rectangle
from src.crop_stage_growth import check_proposal,GrowthContract
from tools.c03_sequence_scene import load_scene,sha,read,save
from tools.render_c03_source_frame import render_source_frame as render

def main(run,*,scene_loader=load_scene):
 if not run.resolve().is_relative_to(ROOT/'out'):raise ValueError('PROJECT_LOCAL_RUN_REQUIRED')
 out=run/'T02'
 if out.exists():raise ValueError('FRESH_STAGE_REQUIRED')
 assets=verify_assets();scope,meta,original,current,protected,routes=scene_loader(run,'T04');crop=box(*scope['viewport_mm']);rows=sorted([r for r in scope['records'] if r['scope_disposition']=='T02_RECTANGLE_TARGET_PROPOSAL'],key=lambda r:(original[r['source_id']].centroid.y,original[r['source_id']].centroid.x,r['source_id']));targets={r['source_id']:r for r in rows};aliases={s:sorted(i for i,m in meta.items() if m['kind']=='gr_poly' and m['geometry_sha256']==meta[s]['geometry_sha256']) for s in targets};land_ids=set(targets)
 lands=[dict(id=s,original=original[s],candidate=original[s],native_source_kind='gr_poly',native_stroke_width_mm=0.) for s in sorted(land_ids)];fixed=[dict(id=s,geometry=g,trace_width_mm=meta[s]['trace_width_mm']) for s,g in current.items() if s not in land_ids];checker=PreparedLandScene(lands,fixed);selected={s:original[s] for s in land_ids};ports=[]
 # Pre-T04 source contacts define attachment permission; the wider current trace
 # cannot create a new T02 contact exception merely by touching a land.
 for sid in sorted(land_ids):
  core=original[sid]
  for i in checker.tree.query(core,predicate='intersects'):
   oid=checker.ids[int(i)]
   if oid==sid:continue
   old=original[oid];overlap=core.intersection(old);contact=not overlap.is_empty;width=max(checker.widths[sid],checker.widths[oid])+checker.contract.original_port_buffer_gap_mm;port=overlap.buffer(width,quad_segs=checker.contract.port_quad_segs) if contact else None;checker.ports[(sid,oid)]=(port,contact,core.distance(old));ports.append(dict(source_id=sid,neighbor_id=oid,original_contact=contact,port_sha256=None if port is None else sha(to_wkb(port))))
 def check(sid=None,candidate=None,materialize=False):
  return checker.check([dict(id=s,original=original[s],candidate=candidate if s==sid else selected[s],native_source_kind='gr_poly',native_stroke_width_mm=0.) for s in sorted(land_ids)],materialize_scene=materialize,fail_fast=not materialize)
 assert check()['passed'],'T02_SOURCE_KEEP_BASELINE_FAILED';out.mkdir();(out/'rectangle_parts').mkdir();decisions=[];ids=sorted(current);tree=STRtree([current[s] for s in ids])
 for row in rows:
  sid=row['source_id'];core=original[sid];neighbors=[current[ids[int(i)]] for i in tree.query(core,predicate='intersects') if ids[int(i)] not in set(aliases[sid])];covered=core.difference(unary_union(neighbors)).area<=1e-12;attempts=dict(evaluations=0,rejections=0);failures=[]
  def feasible(g):
   attempts['evaluations']+=1;q=check(sid,g)
   if g.difference(crop).area>1e-12:return False
   if not q['passed']:
    attempts['rejections']+=1
    if len(failures)<12:failures.append(q['failures'][:8])
   return q['passed']
  candidate,factors=(core,(1.,1.)) if covered else fit_joint_rectangle(core,feasible)
  if candidate.difference(core).area<=1e-12:candidate=core;factors=(1.,1.)
  assert candidate.covers(core) and feasible(candidate);selected[sid]=candidate
  for a in aliases[sid]:current[a]=candidate
  blob=to_wkb(candidate);(out/'rectangle_parts'/f"{row['key']}.wkb").write_bytes(blob);decision=dict(key=row['key'],source_id=sid,aliases=aliases[sid],factors=list(factors),status='COVERED_SKIP' if covered else 'GROWN' if candidate.difference(core).area>1e-12 else 'KEEP_CLEARANCE_LIMITED',candidate_sha256=sha(blob),added_area_mm2=candidate.difference(core).area,no_recess=len(candidate.exterior.coords)==5 and not candidate.interiors,search=attempts,rejections=failures);decisions.append(decision)
  print(json.dumps(dict(rectangles_completed=len(decisions),total=len(rows),last=decision['status'])),flush=True)
 final=check(materialize=True);assert final['passed'] and final['evaluation_complete'];before=from_wkb((run/'T04/after.wkb').read_bytes());ordinary=before.union(unary_union([selected[s].difference(original[s]) for s in sorted(land_ids)]));(out/'ordinary_after.wkb').write_bytes(to_wkb(ordinary));after=ordinary
 # Same bounded row/column and sub-row discovery used in C02, measured anew.
 def aligned(a,b,axis):
  p,q=original[a].bounds,original[b].bounds;j=1-axis;t1,t2=p[j+2]-p[j],q[j+2]-q[j];overlap=min(p[j+2],q[j+2])-max(p[j],q[j]);dc=abs((p[j]+p[j+2]-q[j]-q[j+2])/2);gap=max(p[axis],q[axis])-min(p[axis+2],q[axis+2]);return overlap>=.75*min(t1,t2) and dc<=.15*max(t1,t2) and max(t1,t2)<=2*min(t1,t2) and 0<=gap<=2*max(p[axis+2]-p[axis],q[axis+2]-q[axis])
 groups=[]
 for axis in (0,1):
  remaining=set(land_ids)
  while remaining:
   seed=min(remaining);remaining.remove(seed);group={seed};pending=[seed]
   while pending:
    a=pending.pop();links={b for b in remaining if aligned(a,b,axis)};group.update(links);remaining-=links;pending.extend(sorted(links))
   if len(group)>1:
    members=sorted(group,key=lambda s:original[s].bounds[axis])
    for first in range(len(members)-1):
     for last in range(first+2,len(members)+1):groups.append((axis,tuple(sorted(members[first:last]))))
 ids=sorted(current);tree=STRtree([current[s] for s in ids]);claimed=set();accepted=[];merges=[];(out/'merges').mkdir()
 for index,(axis,members) in enumerate(sorted(set(groups),key=lambda x:(-len(x[1]),x[0],x[1])),1):
  cid=f'M{index:03}';rect=box(*unary_union([current[s] for s in members]).bounds);span=after.intersection(rect);shortage=rect.difference(span).area/rect.area;near=[ids[int(i)] for i in tree.query(rect.buffer(.021))];supports=set(members)|{s for s in near if meta[s]['kind'] in ('segment','arc') and current[s].intersection(span).area>0};support_union=unary_union([current[s] for s in supports]);covered={s for s in near if s not in supports and current[s].difference(support_union).is_empty};foreign=[dict(source_id=s,original=current[s],geometry=current[s],trace_width_mm=meta[s]['trace_width_mm']) for s in near if s not in supports|covered];q=check_proposal(span,rect,foreign,crop=crop,cap=rect,contract=GrowthContract());addition=rect.difference(after);reasons=[]
  if shortage>.20:reasons.append('SHORTAGE_ABOVE_20_PERCENT')
  if span.geom_type!='Polygon':reasons.append('SPAN_NOT_ONE_CONNECTED_SURFACE')
  if claimed.intersection(members):reasons.append('SOURCE_ALREADY_MERGED')
  if not q['passed']:reasons.append('FOREIGN_CLEARANCE_FAILED')
  if addition.area<=1e-12:reasons.append('NO_VISIBLE_ADDITION')
  for prior in accepted:
   outside=prior.difference(span)
   if not outside.is_empty and not addition.is_empty and addition.distance(outside)<.0201:reasons.append('PRIOR_MERGE_CLEARANCE_FAILED')
  record=dict(candidate=cid,orientation='ROW' if axis==0 else 'COLUMN',rectangle_members=list(members),support_trace_source_ids=sorted(supports-set(members)),covered_sources_skipped=sorted(covered),missing_area_fraction=shortage,threshold=.20,inclusive_bounds_mm=list(rect.bounds),status='MERGED' if not reasons else 'REJECTED',reasons=reasons,check=q)
  if not reasons:
   blob=to_wkb(rect);(out/'merges'/f'{cid}.wkb').write_bytes(blob);record.update(inclusive_wkb_sha256=sha(blob),added_area_mm2=addition.area);after=after.union(rect);accepted.append(rect);claimed.update(members)
  merges.append(record)
 for sid,blob in protected.items():assert to_wkb(current[sid])==blob,'T01_OR_T04_PART_CHANGED'
 assert before.difference(after).area<=1e-12
 for name,g in [('before',before),('after',after),('added',after.difference(before))]:(out/f'{name}.wkb').write_bytes(to_wkb(g))
 for name,d in [('DECISIONS.json',decisions),('INCLUSIVE_CANDIDATES.json',merges),('FINAL_ORDINARY_CHECK.json',final),('ORIGINAL_PORT_BINDINGS.json',ports)]:save(out/name,d)
 result=dict(status='C03_TRACE_FIRST_T02_LOCAL_PROPOSAL',asset_integrity=assets,source_sha256=scope['source_sha256'],predecessor_sha256=sha((run/'T04/after.wkb').read_bytes()),scope_sha256=sha((run/'T01/SUPPORTED_TARGETS.json').read_bytes()),after_sha256=sha(to_wkb(after)),sequence=['T01','T03_NO_ROUTE_CHANGE','T04','T02'],rectangle_targets=len(decisions),grown=sum(r['status']=='GROWN' for r in decisions),keep=sum(r['status']!='GROWN' for r in decisions),inclusive_candidates=len(merges),inclusive_merges=len(accepted),added_area_mm2=after.difference(before).area,protected_T01_T04_parts=len(protected),protected_parts='ALL_BYTE_IDENTICAL',registration=scope['screenshot_registration'],owner_acceptance='PENDING_USER',independent_native_electrical_manufacturing='NOT_ESTABLISHED');save(out/'RESULT.json',result)
 for name,g,d in [('before',before,GeometryCollection()),('after',after,after.difference(before))]:
  p=out/f'{name}.svg';render(p,f'C03 / T02 after T04 / {name}',g,d,scope['viewport_mm'],notes=[f"{len(decisions)} rectangles;{result['grown']} grow;{result['keep']} KEEP/covered;{len(accepted)} inclusive merges.",'Whole rectangles only, ordinary per-axis1.25 cap; inclusive shortage<=20%; no recess.',f"All{len(protected)} T01/T04 source parts retained; teal is actual T02 addition.",'Source localization provisional; local proposal, no owner/native/manufacturing acceptance.']);subprocess.run(['sips','-s','format','png',str(p),'--out',str(p.with_suffix('.png'))],capture_output=True,check=True)
 print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);main(**vars(p.parse_args()))
