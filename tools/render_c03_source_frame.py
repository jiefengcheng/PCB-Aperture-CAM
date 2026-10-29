#!/usr/bin/env python3
"""C03 presentation in the established source-baseline display frame.

Native WKB stays unchanged. Only the SVG display uses x=native x, y=-native y,
matching build_c03_source_baseline.py's ymax-y mapping.
"""
from pathlib import Path
import sys,json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb
from shapely.affinity import scale
from tools.run_c02_growth_coverage import render


def render_source_frame(path,title,copper,addition,bounds,rows=(),cores=None,notes=(),*,detail=None):
    x0,y0,x1,y1=bounds;screen=[x0,-y1,x1,-y0]
    flip=lambda g:scale(g,xfact=1,yfact=-1,origin=(0,0))
    render(path,title,flip(copper),flip(addition),screen,rows,{k:flip(v) for k,v in (cores or {}).items()},list(notes)+['Display x=native x, y=-native y, matching the earlier C03 baseline. Native source coordinates and WKB unchanged.'])


def main(proposal,baseline,out):
    if out.exists():raise ValueError('FRESH_OUTPUT_REQUIRED')
    b=json.loads(baseline.read_text());r=json.loads((proposal/'RESULT.json').read_text());before=from_wkb((proposal/'before.wkb').read_bytes());after=from_wkb((proposal/'after.wkb').read_bytes());added=from_wkb((proposal/'added.wkb').read_bytes())
    if hashlib.sha256((proposal/'after.wkb').read_bytes()).hexdigest()!=r['after_sha256']:raise ValueError('SOURCE_SCENE_HASH_MISMATCH')
    out.mkdir();bindings=[]
    for name,bounds in [('full',b['native_crop_bounds_mm']),('neighborhood',b['closeup_bounds_mm'])]:
        for stage,copper in [('before',before),('after',after)]:
            svg=out/f'{name}_{stage}.svg';render_source_frame(svg,f'C03 / round-class T01 proposal / {name} {stage}',copper,added if stage=='after' else added.difference(added),bounds,notes=[
                f'{r["target_count"]} supported circles;{r["positive_targets"]} positive round-class growth;{r["keep_targets"]}KEEP;{r["final_joint_checks"]} final checks pass.',
                'Actual source copper in red; exact added copper once in teal. Source cores, round shape and attachments retained.',
                f'{r["unresolved_class_source_count"]} source class range remains unresolved. T02notrun; no complete C03stage freeze.',
                'Earlier C03 presentation used opposite vertical orientation; this presentation supersedes its images only.',
                'Screenshot localization remains provisional; no EDIT target geometry or C02 land acceptance inherited.'])
            subprocess.run(['sips','-s','format','png',str(svg),'--out',str(svg.with_suffix('.png'))],check=True,capture_output=True)
            bindings.append(dict(image=svg.with_suffix('.png').name,native_viewport_mm=bounds,display_transform='x=x_native;y=-y_native',source_scene_sha256=hashlib.sha256((proposal/f'{stage}.wkb').read_bytes()).hexdigest()))
    (out/'DISPLAY_BINDINGS.json').write_text(json.dumps(dict(status='CORRECTED_PRESENTATION_ONLY_NO_GEOMETRY_CHANGE',source_proposal=str(proposal),source_proposal_result_sha256=hashlib.sha256((proposal/'RESULT.json').read_bytes()).hexdigest(),source_baseline_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),images=bindings),indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C03 source-frame comparison</title><style>body{font:18px system-ui;margin:24px}img{max-width:100%}</style><h1>C03 round-class proposals in the source-baseline display frame</h1><p>Corrected vertical presentation only; original geometry unchanged. Target scope remains provisional.</p><h2>Source before</h2><img src="full_before.png"><h2>Cumulative after</h2><img src="full_after.png"><h2>Located neighborhood before</h2><img src="neighborhood_before.png"><h2>Located neighborhood after</h2><img src="neighborhood_after.png"><a href="DISPLAY_BINDINGS.json">Exact native-to-display mapping</a>')
    print(json.dumps(dict(status='PASS_PRESENTATION_FRAME_CORRECTION',source_geometry_changed=False)))

if __name__=='__main__':main(*map(Path,sys.argv[1:]))
