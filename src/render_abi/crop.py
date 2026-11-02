"""Generic read-only display from an audited data-ABI ROI and fresh exports."""
import json,html
from importlib.metadata import version
from PIL import Image,ImageDraw
from src.stage_abi.store import digest
from src.pcb_data_abi.crop_custody import validate_host
from .service import RenderService,bound_bytes,local,CLI,ROOT
from .crop_pixels import choose_pixels

def present_crop(out,contract):
    w,h=contract['pixels'];im=Image.new('RGB',(2*w+24,h+160),'#eef3f7');d=ImageDraw.Draw(im)
    d.text((20,12),'T01 / exported KiCad and Gerber / verified uploaded ROI',fill='#152a40',font_size=28)
    d.text((20,50),'Review candidate; owner acceptance PENDING_USER. Same native-mm viewport.',fill='#152a40',font_size=20)
    for i,(name,label) in enumerate((('kicad','KiCad board / native CLI SVG'),('gerber','Gerber export / native CLI PNG'))):
        x=i*(w+24);d.text((x+15,83),label,fill='#152a40',font_size=24)
        with Image.open(out/(name+'.png')) as a:im.paste(a.convert('RGB'),(x,120))
    d.text((20,h+130),'Native X right, Y down. Display only; no T02-T05 execution.',fill='#152a40',font_size=18);im.save(out/'comparison.png')
    bounds=html.escape(json.dumps(contract['bounds_mm']))
    links=''.join(f'<li>{html.escape(k)} SHA256: <code>{v["sha256"]}</code></li>' for k,v in contract['inputs'].items())
    (out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none';img-src 'self';style-src 'unsafe-inline';script-src 'unsafe-inline'"><title>T01 uploaded ROI / KiCad and Gerber</title><style>body{font:16px system-ui;background:#eef3f7;color:#152a40;margin:24px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}.view{overflow:hidden;touch-action:none}.view img{display:block;width:100%;transform-origin:0 0;pointer-events:none}code{overflow-wrap:anywhere}</style><h1>T01: KiCad and Gerber exports</h1><p>Fresh native rendering, REPLAY of the exported files. Owner review PENDING_USER. Image fidelity is distinct from clearance, electrical or manufacturing acceptance.</p><label>Linked zoom <input id="zoom" type="range" min="1" max="5" step=".25" value="1"></label><button id="reset">Reset</button><div class="pair"><section><h2>KiCad board / native CLI SVG</h2><div class="view"><img src="kicad.png" alt="T01 KiCad export"></div></section><section><h2>Gerber export / native CLI PNG</h2><div class="view"><img src="gerber.png" alt="T01 Gerber export"></div></section></div><p>Native mm bounds: '''+bounds+'''</p><p>Drag either panel to pan both. Frozen C01/C02/C03 and T02-T05 unchanged.</p><ul>'''+links+'''</ul><p><a href="comparison.png">PNG</a> · <a href="render.json">Native commands and receipt</a> · <a href="verification.json">Raster audit</a> · <a href="controls.json">Controls</a></p><script>const vs=[...document.querySelectorAll('.view')],z=document.querySelector('#zoom');let s=1,x=0,y=0,drag=null;function apply(){x=Math.min(0,Math.max(1-s,x));y=Math.min(0,Math.max(1-s,y));vs.forEach(v=>v.firstElementChild.style.transform=`translate(${x*100}%,${y*100}%) scale(${s})`)}z.oninput=()=>{s=Number(z.value);apply()};document.querySelector('#reset').onclick=()=>{s=1;x=y=0;z.value=1;apply()};vs.forEach(v=>{v.onpointerdown=e=>{drag=[e.clientX,e.clientY,x,y];v.setPointerCapture(e.pointerId)};v.onpointerup=v.onpointercancel=()=>drag=null;v.onpointermove=e=>{if(drag){const r=v.getBoundingClientRect();x=drag[2]+(e.clientX-drag[0])/r.width;y=drag[3]+(e.clientY-drag[1])/r.height;apply()}}});</script></html>''')

class CropRenderService(RenderService):
    presenter=staticmethod(present_crop)
    def __init__(self,host):
        root=validate_host(host,'render');self.contract_path=local(host['contract_path'])
        if self.contract_path.parent!=root:raise ValueError('CROP_RENDER_CONTRACT_SCOPE')
        self.contract_blob=bound_bytes(self.contract_path,host['contract_sha256']);self.contract=json.loads(self.contract_blob)
        roi=json.loads((root/'data_roi/roi_verified.json').read_bytes())
        if self.contract['bounds_mm']!=roi['bounds_mm']:raise ValueError('CROP_RENDER_ROI_MISMATCH')
        exports={'kicad':root/'data_output/candidate/board.kicad_pcb','gerber':root/'data_output/candidate/gerbers/board-F_Cu.gbr'}
        if self.contract['inputs']!={k:dict(path=str(p.relative_to(ROOT)),sha256=digest(p.read_bytes())) for k,p in exports.items()}:raise ValueError('CROP_RENDER_EXPORT_MISMATCH')
        reference=json.loads((ROOT/'contracts/render/crop.json').read_bytes())
        mutable={'bounds_mm','pixels','inputs','authority','schema'}
        if {k:v for k,v in self.contract.items() if k not in mutable}!={k:v for k,v in reference.items() if k not in mutable}:raise ValueError('CROP_RENDER_POLICY_CHANGED')
        w,h=self.contract['pixels'];b=roi['bounds_mm']
        if [w,h]!=choose_pixels(b,reference['pixel_policy']):raise ValueError('CROP_RENDER_PIXEL_BINDING')
        self.versions={n:version(n) for n in self.contract['dependencies']}
        if self.versions!=self.contract['dependencies']:raise ValueError('RENDER_DEPENDENCY_VERSION_CHANGED')
        self.out=local(host['output']);self.inputs={k:local(ROOT/v['path']) for k,v in self.contract['inputs'].items()};self.bounds=b;self.size=[w,h];self.check_inputs()
        if digest(CLI.read_bytes())!=self.contract['cli_sha256']:raise ValueError('RENDER_KICAD_EXECUTABLE_CHANGED')
    def dispatch(self,operation):return dict(render_compare=self.render,render_verify=self.verify,render_controls=self.controls)[operation]()
