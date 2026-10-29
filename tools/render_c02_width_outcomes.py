#!/usr/bin/env python3
"""Make complete route coverage versus legal growth explicit on actual copper."""
import sys,json,hashlib,subprocess,html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from tools.run_c02_four_attachment_diagnostic_v2 import compute
from tools.run_c02_growth_coverage import render,svg_shape


def main():
    pre,definitions,group_dir,proposal,out=map(Path,sys.argv[1:]);assert not out.exists()
    report,g=compute(pre);result=json.loads((proposal/'RESULT.json').read_text())
    assert result['land_predecessor_sha256']==report['cumulative_sha256']
    d=json.loads((definitions/'UNIFORM_SOURCE_PATHS.json').read_text());groups=json.loads((group_dir/'PARALLEL_MEMBERSHIP.json').read_text())['groups']
    assignment={cid:r['group_id'] for r in groups for cid in r['members']};scales=result['selected_scales'];paths={r['path_id']:r for r in d['paths'] if r['path_id'] in assignment}
    exposed={}
    for cid,r in paths.items():
        blob=(definitions/'exposed_source_paths'/f'{cid}.wkb').read_bytes()
        assert hashlib.sha256(blob).hexdigest()==r['exposed_in_crop_wkb_sha256'];exposed[cid]=from_wkb(blob)
    positive=[cid for cid in paths if scales[assignment[cid]]>1];kept=[cid for cid in paths if scales[assignment[cid]]==1]
    out.mkdir();overlay=unary_union(list(exposed.values()))
    svg=out/'coverage_and_growth.svg'
    render(svg,'C02 / all visible routes / growth outcome coverage',g['after'],overlay,g['base']['bounds'],[],{},[
        f'{len(paths)} visible routes accounted for: {len(positive)} positive-growth proposals; {len(kept)} constrained KEEP routes.',
        'TEAL = original exposed footprint of a positively widened route. AMBER = included but constrained to original width.',
        'This panel locates route outcomes; colors are not added copper. See cumulative after image for actual nominal growth.',
        'Every complete route checked against full-source finite copper, including remote constraints. Shared group factors apply.',
        'Frozen T01/T02 lands unchanged. Model proposal pending batch audit; no native/electrical/manufacturing acceptance.'])
    text=svg.read_text();initial=svg_shape(overlay.intersection(box(*g['base']['bounds'])),'#21bda8');assert text.count(initial)==1;text=text.replace(initial,'',1)
    colors=''.join(svg_shape(exposed[cid],'#e5ab41' if cid in kept else '#21bda8') for cid in sorted(paths))
    svg.write_text(text.replace('</svg>',colors+'</svg>',1))
    subprocess.run(['sips','-s','format','png',str(svg),'--out',str(out/'coverage_and_growth.png')],check=True,capture_output=True)
    rows=''.join('<tr><td>'+r['group_id']+'</td><td>'+str(len(r['members']))+'</td><td>'+format(scales[r['group_id']],'.9f')+'</td><td>'+html.escape(', '.join(r['members']))+'</td></tr>' for r in groups)
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>C02 width outcomes and complete coverage</title><style>body{font:18px system-ui;max-width:1500px;margin:28px auto;color:#142a3f}img{width:100%}td{padding:7px;border-bottom:1px solid #ddd}</style><h1>C02 — complete visible-route width outcomes</h1><p>Every included route is shown, including legal KEEP outcomes. Positive growth does not imply every group reaches1.5×.</p><img src="coverage_and_growth.png"><h2>Cumulative nominal copper result</h2><img src="../'+proposal.name+'/after.png"><p><a href="../'+proposal.name+'/index.html">Before/after and exact scene checks</a></p><table><tr><th>Group</th><th>Routes</th><th>Common factor</th><th>Exact route IDs</th></tr>'+rows+'</table>')
    (out/'OUTCOMES.json').write_text(json.dumps(dict(visible_routes=len(paths),positive_routes=len(positive),keep_routes=len(kept),group_count=len(groups),groups=[dict(r,factor=scales[r['group_id']]) for r in groups],result_sha256=hashlib.sha256((proposal/'RESULT.json').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(visible_routes=len(paths),positive_routes=len(positive),keep_routes=len(kept))))


if __name__=='__main__':main()
