#!/usr/bin/env python3
"""Source-bound constructor replay of C02 T05 after T02, same-assistant scope."""
from pathlib import Path
import sys,argparse,json,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb,STRtree
from shapely.ops import unary_union
from src.crop_circle_sources import verify_assets
from src.junction_spindle_blend import spindle_blend,check_spindle
from tools.run_c02_t05_spindle import load_scene,read,save,sha

def main(freeze,proposal,out):
 if out.exists() or not out.resolve().is_relative_to(ROOT/'out'):raise ValueError('FRESH_PROJECT_OUTPUT_REQUIRED')
 assets=verify_assets();receipt,original,current,meta,lands,skipped,routes,crop=load_scene(freeze);result=read(proposal/'RESULT.json');assert result['predecessor_freeze_sha256']==sha((freeze/'FREEZE_RECEIPT.json').read_bytes());assert sha((proposal/'before.wkb').read_bytes())==receipt['after_sha256']==result['predecessor_sha256'];routes={r['component_id']:r for r in routes};ids=sorted(current);tree=STRtree([current[s] for s in ids]);decisions=read(proposal/'DECISIONS.json');assert [r['route_id'] for r in decisions]==sorted(routes);accepted=[];allchecks=[]
 for row in decisions:
  r=routes[row['route_id']];assert row['source_ids']==r['complete_source_ids'] and row['nominal_width_mm']==r['uniform_nominal_width_mm'];trace=unary_union([current[s] for s in row['source_ids']]);oldtrace=unary_union([original[s] for s in row['source_ids']]);attached=[d for d in lands if oldtrace.intersection(d['original']).area>1e-12 and trace.intersection(d['geometry']).area>1e-12];assert row['land_ids']==[d['id'] for d in attached]
  if row['status']!='GROWN':continue
  cid=row['id'];owner=unary_union([trace]+[d['geometry'] for d in attached]);base_radius=min(min(d['geometry'].bounds[2]-d['geometry'].bounds[0],d['geometry'].bounds[3]-d['geometry'].bounds[1])/2 for d in attached);assert any(abs(row['blend_radius_mm']-base_radius*x)<=1e-14 for x in [1.,.75,.5,.25]);window=unary_union([d['geometry'].buffer(2*base_radius,quad_segs=64) for d in attached]).intersection(crop)
  for suffix,g,k in [('_owner',owner,'owner_sha256'),('_window',window,'window_sha256')]:assert sha(to_wkb(g))==row[k]==sha((proposal/'patches'/f'{cid}{suffix}.wkb').read_bytes())
  allowed=set(row['source_ids'])|{s for d in attached for s in d['source_ids']};foreign=[(ids[int(i)],current[ids[int(i)]]) for i in tree.query(window.buffer(.02011)) if ids[int(i)] not in allowed];base_foreign=foreign[:];foreign += [('T05:'+a['id'],a['addition']) for a in accepted]
  barriers=unary_union([g.buffer(.02011,quad_segs=64) for _,g in foreign if not g.difference(owner).is_empty]);_,addition=spindle_blend(owner,row['blend_radius_mm'],window);addition=addition.difference(barriers)
  assert sha(to_wkb(addition))==row['addition_sha256']==sha((proposal/'patches'/f'{cid}.wkb').read_bytes());check=check_spindle(owner,owner.union(addition),addition,window,foreign);assert check['passed'];accepted.append(dict(id=cid,owner=owner,window=window,addition=addition,foreign=base_foreign))
 for a in accepted:
  foreign=a['foreign']+[(b['id'],b['addition']) for b in accepted if b['id']!=a['id']];check=check_spindle(a['owner'],a['owner'].union(a['addition']),a['addition'],a['window'],foreign);assert check['passed'];allchecks.append(dict(id=a['id'],check=check))
 before=from_wkb((freeze/'before_T05.wkb').read_bytes());after=before.union(unary_union([a['addition'] for a in accepted]));assert sha(to_wkb(after))==result['after_sha256']==sha((proposal/'after.wkb').read_bytes());assert before.difference(after).area<=1e-12
 for name,h in read(freeze/'SHA256SUMS.json').items():assert sha((freeze/name).read_bytes())==h
 coverage=[]
 for row in read(proposal/'NONROUTE_SOURCE_CONTACTS.json'):
  sid=row['source_id'];g=current[sid].intersection(crop);others=[current[ids[int(i)]] for i in tree.query(g,predicate='intersects') if ids[int(i)]!=sid];exposed=g.difference(unary_union(others)).area
  coverage.append(dict(source_id=sid,exposed_crop_area_mm2=exposed,original_diagnostic_full_source_area_mm2=row['exposed_area_mm2'],disposition='COVERED_IN_CROP' if exposed<=1e-12 else 'EXPOSED_FIXED_SOURCE_OUTSIDE_T04_ROUTE_SET_NOT_MODIFIED',land_ids=row['land_ids']))
 gaps=[p['gap_mm'] for r in allchecks for p in r['check']['pairs'] if p.get('gap_mm') is not None];out.mkdir();save(out/'FINAL_CHECKS.json',allchecks);save(out/'NONROUTE_CROP_RECONCILIATION.json',coverage)
 report=dict(status='PASS_SAME_ASSISTANT_SOURCE_BOUND_C02_T05_CONSTRUCTOR_REPLAY',assets=assets,predecessor_sha256=result['predecessor_sha256'],after_sha256=result['after_sha256'],proposal_result_sha256=sha((proposal/'RESULT.json').read_bytes()),routes_accounted=len(decisions),patches_exactly_reconstructed=len(accepted),frozen_parts_preserved=len(read(freeze/'REPLACEMENTS.json')),source_ports='Original positive-area land contacts rechecked; no component-label exemption',windows='Reconstructed from exact current lands and fixed radius bounds',minimum_added_foreign_surface_gap_mm=min(gaps),cumulative_byte_replay=True,exposed_fixed_nonroute_sources=sum(r['exposed_crop_area_mm2']>1e-12 for r in coverage),qualification='Local geometric replay only; inherited independent REV234 REVISE remains open; native/electrical/manufacturing/owner T05 acceptance not established')
 save(out/'REPLAY.json',report);print(json.dumps(report))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['freeze','proposal','out']:p.add_argument(name,type=Path)
 main(**vars(p.parse_args()))
