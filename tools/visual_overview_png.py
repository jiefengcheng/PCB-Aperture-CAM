"""Optional quick-look raster of the generated constrained scene paths.
Uses Pillow if already available. Canonical one-command bundle includes SVG
without Pillow; this convenience renderer does not read PCB/Gerber or decide.
"""
from pathlib import Path
import json,re,sys
from PIL import Image,ImageDraw,ImageFont,ImageChops
ROOT=Path(__file__).resolve().parents[1]
run=Path(sys.argv[1]) if len(sys.argv)>1 else Path((ROOT/'out/visual/current.txt').read_text().strip())
scene=json.loads((run/'scene.json').read_text());page=Image.new('RGB',(1320,1320),'#eef3f5');d=ImageDraw.Draw(page)
font=ImageFont.load_default(size=16);title=ImageFont.load_default(size=22);small=ImageFont.load_default(size=13)
d.text((30,20),'PCB / CAM - evidence-linked case overview',font=title,fill='#153545')
for i,case in enumerate(scene['cases']):
 state=case['states'][1] if case['id']=='halpi2' else next(s for s in case['states'] if s['id']==case['default_state']);y=70+i*405
 d.text((30,y),case['name']+' | '+state['label'],font=font,fill='#153545')
 for column,revision in enumerate([case['states'][0],state]):
  canvas=Image.new('RGB',(610,310),'#102634');view=case['focus'] if case['id']=='halpi2' else case['fit'];scale=min(610/view[2],310/view[3]);ox=(610-view[2]*scale)/2;oy=(310-view[3]*scale)/2
  for layer,color in [('F.Cu','#c8ab77'),('F.Mask','#73d8ee'),('Edge.Cuts','#b9d0da')]:
   key=revision['layers'].get(layer)
   if not key:continue
   mask=Image.new('1',canvas.size)
   for contour in scene['geometry'][key]['path'].split('M')[1:]:
    numbers=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',contour)));points=[(ox+(numbers[j]-view[0])*scale,oy+(numbers[j+1]-view[1])*scale) for j in range(0,len(numbers),2)]
    if 'Mask' in layer:ImageDraw.Draw(canvas).line(points,fill=color,width=1)
    else:
     ring=Image.new('1',canvas.size);ImageDraw.Draw(ring).polygon(points,fill=1);mask=ImageChops.logical_xor(mask,ring)
   if 'Mask' not in layer:canvas.paste(color,(0,0,610,310),mask)
  page.paste(canvas,(30+column*640,y+27))
  d.text((40+column*640,y+35),'ORIGINAL' if column==0 else 'SELECTED STATE',font=small,fill='#e3eef0')
 verdict=('Geometry '+state['candidate_verdict']+'; electrical '+case['electrical']) if case['id']=='glowstitch' else 'Candidate '+state['candidate_verdict']
 if state['control_test']:verdict+=' | Fault-control test '+state['control_test']['status']
 d.text((30,y+350),verdict,font=font,fill='#284a5a')
 if case['id']=='halpi2':d.text((30,y+375),'J22.1 pad retained. Its 15 expected GND relationships fail in the open control.',font=small,fill='#607385')
d.text((30,1300),'Actual exported artwork | display derivative | shared coordinates | no manufacturing approval',font=small,fill='#607385')
page.save(run/'overview.png');print(run/'overview.png')
