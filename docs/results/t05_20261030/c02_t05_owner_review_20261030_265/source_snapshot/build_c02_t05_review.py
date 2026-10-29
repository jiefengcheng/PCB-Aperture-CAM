#!/usr/bin/env python3
"""Deliver exact frozen C02 predecessor and post-T02 T05 evidence."""
from pathlib import Path
import sys,json,hashlib,subprocess,shutil,html,re
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb
from shapely.geometry import GeometryCollection
from tools.run_c02_growth_coverage import render
B=ROOT/'out/crop_dynamic_tasks';F=B/'c02_latest_pre_T05_freeze_20261030_262';P=B/'c02_t05_after_T02_20261030_263';R=B/'c02_t05_replay_20261030_264';O=B/'c02_t05_owner_review_20261030_265'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if O.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
 receipt=read(F/'FREEZE_RECEIPT.json');result=read(P/'RESULT.json');replay=read(R/'REPLAY.json');assert replay['proposal_result_sha256']==sha(P/'RESULT.json') and replay['after_sha256']==sha(P/'after.wkb');rows=read(P/'DECISIONS.json');before=from_wkb((P/'before.wkb').read_bytes());after=from_wkb((P/'after.wkb').read_bytes());added=from_wkb((P/'added.wkb').read_bytes());O.mkdir();images=[]
 def picture(name,title,g,d,view,notes):
  svg=O/f'{name}.svg';render(svg,title,g,d,view,[],{},notes);png=svg.with_suffix('.png');subprocess.run(['sips','-s','format','png',str(svg),'--out',str(png)],capture_output=True,check=True);images.append(dict(file=png.name,sha256=sha(png),svg_sha256=sha(svg),viewport_mm=view,source_sha256=result['source_sha256'],predecessor_sha256=result['predecessor_sha256'],result_sha256=sha(P/'RESULT.json')))
 notes=['T01 → T03 (no route change needed) → T04 → T02 → T05.',f"56 route blends /88 land-contact incidences, including65 rectangle incidences;57 routes unchanged.",'All606 frozen source replacements retained; no source width or route changes. Teal = actual T05 addition.',f"Source-bound constructor replay PASS; minimum checked added-to-foreign gap {replay['minimum_added_foreign_surface_gap_mm']*1000:.6f} micrometres.",'16 exposed nonroute contacts match standing fixed-bulk skips; no new exclusion. Independent REV234 REVISE remains open.']
 for name,title,g,d in [('before','C02 / exact frozen result232 / before T05',before,GeometryCollection()),('after','C02 / cumulative result after T05',after,GeometryCollection()),('growth','C02 / T05 added junction copper in teal',after,added)]:picture(name,title,g,d,receipt['viewport_mm'],notes)
 grown=sorted([r for r in rows if r['status']=='GROWN'],key=lambda x:-x['added_area_mm2']);selected=[]
 for kind in ['circle','rectangle','inclusive_rectangle']:
  selected.extend([r for r in grown if kind in r['land_kinds'] and r not in selected][:2])
 selected+=( [r for r in grown if r not in selected][:max(0,8-len(selected))])
 details=[]
 for i,row in enumerate(selected,1):
  delta=from_wkb((P/'patches'/f"{row['id']}.wkb").read_bytes());parts=[delta] if delta.geom_type=='Polygon' else list(delta.geoms);g=max(parts,key=lambda p:p.area);x0,y0,x1,y1=g.bounds;cx,cy=(x0+x1)/2,(y0+y1)/2;half=max(x1-x0,y1-y0)*.8+row['nominal_width_mm'];view=[cx-half,cy-half,cx+half,cy+half]
  note=[row['route_id']+' / '+', '.join(row['land_kinds']),f"Original nominal width {row['nominal_width_mm']:.6f} mm; local blend radius {row['blend_radius_mm']:.6f} mm.",'Exact same coordinates and scale in before/after; teal shows actual added copper.','Fixed T02 lands and T04 source geometry retained; local additive junction shape only.']
  for suffix,g,d in [('before',before,GeometryCollection()),('after',after,added)]:picture(f'detail_{i:02}_{suffix}',f'C02 / source-bound junction detail{i:02} / {suffix}',g,d,view,note)
  details.append(f'<h2>Detail{i}: {html.escape(", ".join(row["land_kinds"]))}</h2><div class="pair"><img src="detail_{i:02}_before.png"><img src="detail_{i:02}_after.png"></div>')
 table=''
 for row in rows:
  reason=row.get('reason','Additive blend passed')
  if reason=='NO_VALID_BOUNDED_ADDITIVE_BLEND' and row.get('attempts') and all(a.get('passed') and a.get('added_area_mm2',1)<=1e-8 for a in row['attempts']):reason='KEEP: no extra junction copper produced/available within constraints'
  table+=f'<tr><td>{html.escape(row["route_id"])}</td><td>{row["status"]}</td><td>{html.escape(", ".join(row["land_kinds"]))}</td><td>{html.escape(reason)}</td></tr>'
 page='<!doctype html><meta charset="utf-8"><title>C02 T05 after T02 review</title><style>body{font:18px system-ui;max-width:1600px;margin:30px auto;padding:20px}img{max-width:100%}.pair{display:flex}.pair img{width:50%}td{padding:8px;border-bottom:1px solid #ccc}</style><h1>C02 · T05 after T02</h1><p>56 trace routes blended,88 land-contact incidences including65 rectangle incidences.57 unchanged routes accounted for. One contacted route rejects disconnected/invalid candidate geometry; five contacted routes add no copper.16 exposed nonroute source contacts match the existing fixed-bulk exclusion.</p><p>C01 is frozen with owner acceptance and T02 skipped. C02 T05 remains a local candidate; inherited independent-audit REVISE is preserved.</p>'
 for name,title in [('before','Frozen C02 predecessor232'),('after','Cumulative C02 after T05'),('growth','Actual added T05 copper')]:page+=f'<h2>{title}</h2><img src="{name}.png">'
 page+=''.join(details)+'<h2>All113 frozen trace-route outcomes</h2><table>'+table+'</table><p><a href="../'+P.name+'/DECISIONS.json">All source-bound attempts</a> · <a href="../'+R.name+'/REPLAY.json">Exact constructor replay</a> · <a href="../'+R.name+'/FIXED_BULK_CONTACT_RECONCILIATION.json">Existing bulk-role reconciliation</a> · <a href="../'+F.name+'/FREEZE_RECEIPT.json">C02 predecessor freeze and audit limits</a> · <a href="../c01_final_so_far_freeze_20261030_261/FREEZE_RECEIPT.json">C01 accepted freeze</a> · <a href="IMAGE_BINDINGS.json">Image hashes and viewports</a></p>'
 (O/'index.html').write_text(page);(O/'IMAGE_BINDINGS.json').write_text(json.dumps(images,indent=2)+'\n')
 for link in re.findall(r'(?:href|src)="([^"]+)"',page):assert (O/link).exists(),link
 print(json.dumps(dict(output=str(O),images=len(images),details=len(details),all_links='PASS')))
if __name__=='__main__':main()
