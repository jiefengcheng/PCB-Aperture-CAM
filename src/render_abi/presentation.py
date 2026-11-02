"""Offline synchronized comparison and a labeled standalone PNG."""

import html
import json
from PIL import Image, ImageDraw


def present(out, contract):
    width, height = contract['pixels']
    sheet = Image.new('RGB', (width*2+24, height+190), '#eef3f7')
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 15), 'C01 / exported KiCad and Gerber / same native-mm viewport', fill='#152a40', font_size=30)
    draw.text((20, 58), 'Fresh headless rendering of stored files. Review candidate; owner acceptance PENDING_USER.', fill='#152a40', font_size=20)
    draw.text((20, 83), 'Run: '+str(out.relative_to(out.parents[3]))+' / details and exact commands in render.json', fill='#152a40', font_size=13)
    for index, (name, label) in enumerate((('kicad', 'KiCad board / native CLI SVG'), ('gerber', 'Existing Gerber / native CLI PNG'))):
        x = index*(width+24)
        draw.text((x+15, 100), label, fill='#152a40', font_size=24)
        with Image.open(out/(name+'.png')) as image:
            sheet.paste(image.convert('RGB'), (x, 140))
    draw.text((20, height+150), 'X right, native Y down; Gerber Y = -native Y. Raster error bounds: KiCad 1 um / Gerber 5 um. No T02-T05 execution.', fill='#152a40', font_size=18)
    draw.text((20, height+173), 'Input SHA256 / KiCad '+contract['inputs']['kicad']['sha256']+' / Gerber '+contract['inputs']['gerber']['sha256'], fill='#152a40', font_size=16)
    sheet.save(out/'comparison.png')
    inputs = ''.join('<li>'+html.escape(k)+': <code>'+html.escape(v['sha256'])+'</code></li>' for k,v in contract['inputs'].items())
    bounds = json.dumps(contract['bounds_mm'])
    (out/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>C01 / KiCad and Gerber comparison</title>
<style>body{font:16px system-ui;margin:24px;color:#152a40;background:#eef3f7}h1{font-size:25px}button,input{font:inherit}button{padding:6px 14px}code{overflow-wrap:anywhere}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}.view{overflow:hidden;position:relative;aspect-ratio:1280/1077;background:#061727;touch-action:none;cursor:crosshair}.view img{width:100%;height:100%;display:block;transform-origin:0 0;user-select:none;pointer-events:none}.panel h2{font-size:19px}nav{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:20px 0}.note{background:white;padding:12px;border-left:4px solid #466c8e}a{color:#1c547b}footer{margin-top:24px}output{font-variant-numeric:tabular-nums}</style>
<h1>C01: exported KiCad and Gerber, side by side</h1>
<p class="note">Fresh headless rendering of stored exported files (REPLAY of their geometry). Review only; owner acceptance <strong>PENDING_USER</strong>. Frozen C01/C02/C03 and T02-T05 are unchanged.</p>
<nav><button id="reset">Reset view</button><label>Linked zoom <input id="zoom" type="range" min="1" max="5" step="0.25" value="1"></label><output id="level">1.00x</output><span>Drag either image to pan both.</span></nav>
<div class="pair"><section class="panel"><h2>KiCad board / native CLI SVG</h2><div class="view"><img alt="C01 from exported KiCad board" src="kicad.png" draggable="false"></div></section><section class="panel"><h2>Existing Gerber / native CLI PNG</h2><div class="view"><img alt="C01 from existing top copper Gerber" src="gerber.png" draggable="false"></div></section></div>
<p><output id="position">Move across either image for native and Gerber coordinates.</output></p>
<p>Common native-mm bounds: <code>'''+html.escape(bounds)+'''</code>. X right, native Y down; Gerber Y = -native Y. S31 recess reference: native (3.424, -14.089) mm.</p>
<p>Raster boundary error limits: KiCad 0.001 mm; Gerber 0.005 mm. The Gerber renderer approximates some circles more coarsely. Pixel pitch is about 0.002517 mm. Image agreement is a display check, not a clearance, connectivity or manufacturing verdict.</p>
<p><a href="comparison.png">Standalone side-by-side PNG</a> · <a href="render.json">Render receipt</a> · <a href="verification.json">Separate raster/frame audit</a> · <a href="controls.json">Negative controls</a></p>
<details><summary>Exact input hashes</summary><ul>'''+inputs+'''</ul></details>
<footer>No edits, fitted alignment, later-stage construction, network access or acceptance promotion.</footer>
<script>
const bounds='''+bounds+'''; const views=[...document.querySelectorAll('.view')]; const slider=document.querySelector('#zoom');
let scale=1,px=0,py=0,drag=null;
function apply(){px=Math.min(0,Math.max(1-scale,px));py=Math.min(0,Math.max(1-scale,py));views.forEach(v=>v.firstElementChild.style.transform=`translate(${px*100}%,${py*100}%) scale(${scale})`);document.querySelector('#level').value=scale.toFixed(2)+'x';}
slider.oninput=()=>{const old=scale;scale=Number(slider.value);px=.5-(.5-px)*scale/old;py=.5-(.5-py)*scale/old;apply();};
document.querySelector('#reset').onclick=()=>{scale=1;px=py=0;slider.value=1;apply();};
views.forEach(v=>{v.onpointerdown=e=>{drag={id:e.pointerId,x:e.clientX,y:e.clientY,px,py};v.setPointerCapture(e.pointerId);};v.onpointerup=v.onpointercancel=()=>drag=null;v.onpointermove=e=>{const r=v.getBoundingClientRect();if(drag){px=drag.px+(e.clientX-drag.x)/r.width;py=drag.py+(e.clientY-drag.y)/r.height;apply();}const u=((e.clientX-r.left)/r.width-px)/scale,w=((e.clientY-r.top)/r.height-py)/scale;const x=bounds[0]+u*(bounds[2]-bounds[0]),y=bounds[1]+w*(bounds[3]-bounds[1]);document.querySelector('#position').value=`Native X ${x.toFixed(6)}, Y ${y.toFixed(6)} mm | Gerber X ${x.toFixed(6)}, Y ${(-y).toFixed(6)} mm`;};});
</script></html>''')
