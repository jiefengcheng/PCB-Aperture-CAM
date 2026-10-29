#!/usr/bin/env python3
"""C03 same-frame cumulative sequence review using only saved source geometry."""
from pathlib import Path
import sys,argparse,json,subprocess,base64,re
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb
from shapely.geometry import GeometryCollection
from tools.c03_sequence_scene import read,save,sha
from tools.render_c03_source_frame import render_source_frame as render

def main(run):
 out=run/'review'
 if out.exists() or not run.resolve().is_relative_to(ROOT/'out'):raise ValueError('FRESH_PROJECT_LOCAL_REVIEW_REQUIRED')
 scope=read(run/'T01/SUPPORTED_TARGETS.json');baseline=read(run/'T01/C03_SOURCE_BASELINE.json');replay=read(run/'verification/REPLAY.json');t04=read(run/'T04/RESULT.json');t02=read(run/'T02/RESULT.json');t05=read(run/'T05/RESULT.json');assert replay['after_sha256']==t05['after_sha256'];out.mkdir();bindings=[];stages=[]
 def picture(name,title,g,d,view,notes):
  p=out/(name+'.svg');render(p,title,g,d,view,notes=notes);png=p.with_suffix('.png');subprocess.run(['sips','-s','format','png',str(p),'--out',str(png)],capture_output=True,check=True);bindings.append(dict(image=png.name,sha256=sha(png.read_bytes()),svg_sha256=sha(p.read_bytes()),native_viewport_mm=view,display_transform='x=x_native;y=-y_native',source_sha256=scope['source_sha256'],final_after_sha256=t05['after_sha256']))
 notes=[f"T01:153 circles; T03:no route change; T04:{t04['visible_complete_routes']} complete runs/{t04['group_count']} shared-scale groups.",f"T02:{t02['grown']} rectangle grows/{t02['keep']} KEEP and{t02['inclusive_merges']} inclusive merges; T05:{t05['grown_routes']} route blends.",'Teal = actual addition since the preceding displayed stage. All earlier source parts retained.', 'C03 source screenshot localization provisional (IoU0.964868 <0.970000). No exact EDIT-equivalence claim.', 'Local model and same-assistant replay only; owner/independent/native/electrical/manufacturing acceptance not established.']
 previous=None
 for name,label,path in [('ORG','Original source',run/'T01/before.wkb'),('T01','After T01; T03 recheck passes without route change',run/'T01/after.wkb'),('T04','After T04 uniform trace widths',run/'T04/after.wkb'),('T02','After T02 rectangles and inclusive fills',run/'T02/after.wkb'),('T05','After T05 spindle junctions',run/'T05/after.wkb')]:
  g=from_wkb(path.read_bytes());delta=GeometryCollection() if previous is None else g.difference(previous);removed=0. if previous is None else previous.difference(g).area;assert removed<=1e-12;picture(name+'_clean','C03 / '+label,g,GeometryCollection(),scope['viewport_mm'],notes);picture(name+'_growth','C03 / '+label+' / actual added copper',g,delta,scope['viewport_mm'],notes);stages.append(dict(stage=name,label=label,geometry_sha256=sha(path.read_bytes()),added_area_mm2=delta.area,removed_area_mm2=removed));previous=g
 final=from_wkb((run/'T05/after.wkb').read_bytes());before_t05=from_wkb((run/'T02/after.wkb').read_bytes());t05added=final.difference(before_t05)
 for name,g in [('T01',from_wkb((run/'T01/after.wkb').read_bytes())),('T04',from_wkb((run/'T04/after.wkb').read_bytes())),('T02',before_t05),('T05',final)]:picture(name+'_neighborhood','C03 / located source neighborhood / '+name,g,GeometryCollection(),baseline['closeup_bounds_mm'],notes)
 grown=sorted([r for r in read(run/'T05/DECISIONS.json') if r['status']=='GROWN'],key=lambda r:-r['added_area_mm2']);selected=[]
 for kind in ['circle','rectangle','inclusive_rectangle']:selected += [r for r in grown if kind in r['land_kinds'] and r not in selected][:2]
 selected += [r for r in grown if r not in selected][:max(0,8-len(selected))];details=[]
 for i,row in enumerate(selected,1):
  patch=from_wkb((run/'T05/patches'/f"{row['id']}.wkb").read_bytes());parts=[patch] if patch.geom_type=='Polygon' else list(patch.geoms);big=max(parts,key=lambda p:p.area);x0,y0,x1,y1=big.bounds;cx,cy=(x0+x1)/2,(y0+y1)/2;half=max(x1-x0,y1-y0)*.8+row['nominal_width_mm'];view=[cx-half,cy-half,cx+half,cy+half];n=[row['route_id']+' / '+', '.join(row['land_kinds']),f"Nominal fixed trace width {row['nominal_width_mm']:.6f} mm; additive junction radius {row['blend_radius_mm']:.6f} mm.",'Same coordinates/scale in both panels. Teal = T05 addition; prior source contributions unchanged.', 'Source-bound local result; not owner or independent acceptance.']
  for suffix,g,d in [('before',before_t05,GeometryCollection()),('after',final,t05added)]:picture(f'neck_{i:02}_{suffix}',f'C03 / neck {i:02} / {suffix}',g,d,view,n)
  details.append(f'<h2>Junction detail{i}: {", ".join(row["land_kinds"])}</h2><div class="pair"><img src="neck_{i:02}_before.png"><img src="neck_{i:02}_after.png"></div>')
 def inline(file):return 'data:image/png;base64,'+base64.b64encode(file.read_bytes()).decode()
 page='<!doctype html><meta charset="utf-8"><title>C03 cumulative sequence</title><style>body{font:18px system-ui;max-width:1700px;margin:30px auto;padding:20px;line-height:1.5}img{width:100%}.pair{display:flex}.pair img{width:50%}td{padding:8px;border-bottom:1px solid #ccc}</style><h1>C03 · T01 → T03 → T04 → T02 → T05</h1><p>Actual source-derived cumulative candidate. C01/C02 accepted results remain frozen. C03 is a separate overlapping crop experiment, not an accepted whole-board merge. Screenshot localization remains provisional; no inherited crop acceptance or exact EDIT equivalence.</p><p>T01 reuses153 circle decisions; T03 growth-only recheck requires no route change. T04 excludes source-bound bulk fields and uses one uniform factor per complete trace, shared within parallel groups, up to1.5×. T02 follows fixed widened traces; ordinary cap1.25× and connected inclusive fills≤20% shortage. T05 adds bounded spindle transitions.</p><h2>Latest cumulative C03 result</h2><img src="'+inline(out/'T05_clean.png')+'"><h2>Sequence at common coordinates and scale</h2>'
 for r in stages:page+=f'<h3>{r["label"]}</h3><div class="pair"><img src="{r["stage"]}_clean.png"><img src="{r["stage"]}_growth.png"></div><p>Left:cumulative copper. Right:actual stage addition in teal; added {r["added_area_mm2"]:.9f} mm².</p>'
 page+='<h2>Same located source neighborhood across stages</h2><div class="pair"><img src="T01_neighborhood.png"><img src="T04_neighborhood.png"></div><div class="pair"><img src="T02_neighborhood.png"><img src="T05_neighborhood.png"></div>'+''.join(details)
 page+='<h2>Checks and remaining limits</h2><p>Source-bound local replay passes; the full rejected T04 search history was hash-checked rather than re-executed. All KEEP/fixed roles and unsupported outcomes remain in the linked ledgers. C03 owner, independent, native, electrical and manufacturing acceptance remain open. Provisional localization is retained, not waived.</p><p><a href="../verification/REPLAY.json">Sequence replay</a> · <a href="../T04/RESULT.json">Trace scales and scope</a> · <a href="../T04/GROWTH_OPERATIONS.json">Unioned trace expansion operations</a> · <a href="../T02/DECISIONS.json">Every rectangle outcome</a> · <a href="../T02/INCLUSIVE_CANDIDATES.json">Inclusive candidates</a> · <a href="../T05/DECISIONS.json">Every junction outcome</a> · <a href="../T05/NONROUTE_CONTACTS.json">Fixed/nonroute source contacts</a> · <a href="../C03_FIXED_BULK_ROLES.json">C03 original bulk-field roles</a> · <a href="STAGES.json">Stage geometry hashes</a></p>'
 (out/'index.html').write_text(page);save(out/'IMAGE_BINDINGS.json',bindings);save(out/'STAGES.json',stages)
 for link in re.findall(r'(?:src|href)="([^"]+)"',page):
  if link.startswith('data:'):continue
  assert (out/link).exists(),link
 print(json.dumps(dict(review=str(out),images=len(bindings),detail_pairs=len(details),after_sha256=t05['after_sha256'])))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);main(**vars(p.parse_args()))
