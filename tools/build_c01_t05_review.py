#!/usr/bin/env python3
"""Same-frame source-derived C01 T05 review, with all accepted patch details."""
from pathlib import Path
import sys,json,hashlib,subprocess,html
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb
from shapely.geometry import GeometryCollection,box
from tools.run_c02_growth_coverage import render
BASE=ROOT/'out/crop_dynamic_tasks'
F=BASE/'c01_existing_t01_freeze_20261029_239'
P=BASE/'c01_t05_junction_proposal_20261029_256'
R=BASE/'c01_t05_replay_20261029_257'
OUT=BASE/'c01_t05_visual_review_20261029_258'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if OUT.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
    result=json.loads((P/'RESULT.json').read_text());replay=json.loads((R/'REPLAY.json').read_text());assert replay['status'].startswith('PASS_') and replay['proposal_result_sha256']==sha(P/'RESULT.json')
    f=json.loads((F/'FREEZE_RECEIPT.json').read_text());rows=json.loads((P/'DECISIONS.json').read_text());unresolved=json.loads((P/'UNRESOLVED_CONTACTS.json').read_text())
    original=from_wkb((F/'frozen/context.wkb').read_bytes()).union(from_wkb((F/'frozen/original_effective.wkb').read_bytes()))
    before=from_wkb((P/'before.wkb').read_bytes());after=from_wkb((P/'after.wkb').read_bytes());added=from_wkb((P/'added.wkb').read_bytes());OUT.mkdir();bindings=[]
    def picture(name,title,geom,delta,view,notes):
        path=OUT/(name+'.svg');render(path,title,geom,delta,view,[],{},notes);png=path.with_suffix('.png');subprocess.run(['sips','-s','format','png',str(path),'--out',str(png)],capture_output=True,check=True)
        bindings.append(dict(file=png.name,sha256=sha(png),svg_sha256=sha(path),viewport_mm=view,source_sha256=result['source_sha256'],proposal_result_sha256=sha(P/'RESULT.json')))
    notes=['C01: 12 additive junction tapers; 35 KEEP; 2 unresolved source-side contacts.','Frozen T01: all 266 file hashes unchanged. T04: all 126 source parts and routes retained.','Teal shows actual added T05 copper only. No T02 applied. Source-bound local replay PASS.','17 width stations and eroded connectivity witness; independent/native/electrical qualification open.']
    for name,title,g,d in [('org','ORG source copper',original,GeometryCollection()),('before','T01 + T04 / before T05',before,GeometryCollection()),('clean_after','C01 / after T05',after,GeometryCollection()),('growth','C01 / T05 addition in teal',after,added)]:picture(name,title,g,d,f['viewport_mm'],notes)
    sections=[]
    for i,row in enumerate([r for r in rows if r['status']=='GROWN'],1):
        patch=from_wkb((P/'patches'/(row['id']+'.wkb')).read_bytes());minx,miny,maxx,maxy=patch.bounds;cx,cy=(minx+maxx)/2,(miny+maxy)/2;radius=max(maxx-minx,maxy-miny)*.85+row['width_mm'];view=[cx-radius,cy-radius,cx+radius,cy+radius]
        note=[f"{row['id']} / {row['land_label']} / {row['route_id']}",f"Existing trace width {row['width_mm']:.6f} mm; local flare fraction {row['alpha']:.6f}.",'Original trace route and land contribution unchanged; additions checked against 0.02010 mm foreign gap.','Same exact coordinates and scale in both panels; teal = added copper.']
        for suffix,g,d in [('before',before,GeometryCollection()),('after',after,added)]:picture(f'junction_{i:02}_{suffix}',f'C01 / neck {i:02} / {suffix}',g,d,view,note)
        # Exact patch bounds locate each detail in the complete scene.
        loc=box(*patch.bounds).boundary
        picture(f'junction_{i:02}_locator',f'C01 / exact patch bounds / neck {i:02}',after,loc.buffer(.003),f['viewport_mm'],[row['id'],'Teal locator follows the actual patch bounds; not a group or connectivity assertion.'])
        sections.append(f'<h2 id="neck{i}">Neck {i}: {row["land_label"]}</h2><p>{row["id"]}</p><div class="pair"><img src="junction_{i:02}_before.png"><img src="junction_{i:02}_after.png"></div><details><summary>Full-crop locator</summary><img src="junction_{i:02}_locator.png"></details>')
    table=''.join('<tr><td>'+html.escape(r['id'])+'</td><td>'+html.escape(r['land_label'])+'</td><td>'+r['status']+'</td><td>'+html.escape(r.get('reason','Bounded taper passed final checks'))+'</td></tr>' for r in rows)
    page='<!doctype html><meta charset="utf-8"><title>C01 T05 review</title><style>body{font:17px system-ui;max-width:1500px;margin:30px auto;padding:20px}img{max-width:100%}.pair{display:flex}.pair img{width:50%}td{padding:8px;border-bottom:1px solid #ccc}</style><h1>C01 · T05 neck transitions before T02</h1><p>12 additive tapers; 35 unchanged candidates; 2 unresolved side contacts. Frozen T01 and T04 source contributions unchanged. No T02 applied. Local source-bound replay passes; independent qualification open.</p>'
    for name,label in [('org','ORG'),('before','Before T05'),('clean_after','After T05'),('growth','Actual T05 addition')]:page+=f'<h2>{label}</h2><img src="{name}.png">'
    page+=''.join(sections)+'<h2>All approach decisions</h2><table>'+table+'</table><h2>Unresolved side contacts</h2><pre>'+html.escape(json.dumps(unresolved,indent=2))+'</pre><p><a href="../'+P.name+'/DECISIONS.json">All bounded attempts and operands</a> · <a href="../'+R.name+'/REPLAY.json">Source-bound replay</a> · <a href="IMAGE_BINDINGS.json">Image bindings</a></p>'
    (OUT/'index.html').write_text(page);(OUT/'IMAGE_BINDINGS.json').write_text(json.dumps(bindings,indent=2)+'\n');print(json.dumps(dict(output=str(OUT),images=len(bindings),accepted_details=len(sections))))
if __name__=='__main__':main()
