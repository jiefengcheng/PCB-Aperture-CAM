"""Generate one self-contained, read-only visual bundle from pinned evidence."""
from pathlib import Path
import argparse,datetime,hashlib,html,json,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.visual_scene import ROOT,build_scene,UnverifiedEvidence,sha

def embed_scene(scene):
    # Escape script-closing text from arbitrary source metadata.
    return json.dumps(scene,sort_keys=True,separators=(',',':')).replace('<','\\u003c').replace('&','\\u0026')

def overview(scene):
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1320" height="1320" viewBox="0 0 1320 1320"><rect width="1320" height="1320" fill="#eef3f5"/><text x="30" y="40" font-family="sans-serif" font-size="22" fill="#153545">PCB / CAM · bound evidence overview</text>']
    for i,c in enumerate(scene['cases']):
        selected=c['states'][1] if c['id']=='halpi2' else next(s for s in c['states'] if s['id']==c['default_state'])
        y=70+i*405
        out.append(f'<text x="30" y="{y}" font-family="sans-serif" font-size="18">{html.escape(c["name"])} · {html.escape(selected["label"])}</text>')
        for column,state in enumerate([c['states'][0],selected]):
            x=30+column*640;view=' '.join(map(str,c['focus'] if c['id']=='halpi2' else c['fit']))
            out.append(f'<svg x="{x}" y="{y+16}" width="610" height="310" viewBox="{view}"><rect x="-1000" y="-1000" width="2000" height="2000" fill="#102634"/>')
            for layer,color in [('F.Cu','#c8ab77'),('F.Mask','#73d8ee'),('Edge.Cuts','#b9d0da')]:
                key=state['layers'].get(layer)
                if key:
                    d=scene['geometry'][key]['path'];attrs=f'fill="none" stroke="{color}" stroke-width=".035"' if 'Mask' in layer else f'fill="{color}"'
                    out.append(f'<path d="{d}" fill-rule="evenodd" {attrs}/>')
            out.append('</svg>')
        verdict='Geometry '+selected['candidate_verdict']+'; electrical '+c['electrical'] if c['id']=='glowstitch' else 'Candidate '+selected['candidate_verdict']
        if selected['control_test']:verdict+=' · fault test '+selected['control_test']['status']
        out.append(f'<text x="30" y="{y+352}" font-family="sans-serif" font-size="14" fill="#284a5a">{html.escape(verdict)}</text>')
    out.append('<text x="30" y="1310" font-family="sans-serif" font-size="12">Actual exported artwork · display derivative only · shared coordinates · no manufacturing approval</text></svg>')
    return ''.join(out)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=ROOT/'contracts/visual_inputs_v1.json');args=ap.parse_args()
    run=ROOT/'out/visual'/datetime.datetime.now(datetime.timezone.utc).strftime('run_%Y%m%dT%H%M%S_%fZ');run.mkdir()
    try:
        scene=build_scene(json.loads(args.manifest.read_text()),run)
        scene['build']={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'working_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),'source_sha256':{p:sha(ROOT/p) for p in ('src/visual_scene.py','tools/visual_report.py','web/workbench.html','web/workbench.js')},'manifest_sha256':sha(args.manifest)}
        status='PASS'
    except (UnverifiedEvidence,FileNotFoundError) as exc:
        scene={'scene_schema_version':'1.0','integrity':'STALE_UNVERIFIED','error':str(exc),'cases':[]};status='UNVERIFIED'
    raw=embed_scene(scene);digest=hashlib.sha256(raw.encode()).hexdigest()
    template=(ROOT/'web/workbench.html').read_text();app=(ROOT/'web/workbench.js').read_text()
    page=template.replace('__SCENE__',raw).replace('__DIGEST__',digest).replace('__APP__',app)
    (run/'index.html').write_text(page);(run/'scene.json').write_text(raw)
    if status=='PASS':(run/'overview.svg').write_text(overview(scene))
    (run/'build_receipt.json').write_text(json.dumps({'status':status,'scene_sha256':digest,'html_sha256':sha(run/'index.html'),'outputs':{str(p.relative_to(run)):sha(p) for p in sorted(run.rglob('*')) if p.is_file()},'source_manifest':str(args.manifest),'rendering_basis':'Qualified composed Gerber layers, with separately labelled source annotations'},indent=2)+'\n')
    (ROOT/'out/visual/current.txt').write_text(str(run)+'\n')
    print(json.dumps({'run':str(run),'status':status,'scene_sha256':digest}),flush=True)
    return status!='PASS'
if __name__=='__main__':sys.exit(main())
