"""Actual-data common-coordinate source/result/growth views; no geometry edits."""
import os,sys,json,copy,importlib.util,hashlib
from pathlib import Path
from . import exporter as e
p=e.p;visual_assets=p.ROOT;run=Path(sys.argv[1]);p.configure()
from .guard import install_read_fence
install_read_fence(run.parent)
proofs=[p.load(run/'export'/('proof_'+str(i)+'.json'))for i in(1,2)]
if p.canonical(proofs[0])!=p.canonical(proofs[1])or proofs[0]['status']!='PASS':raise ValueError('TWO_NATIVE_PROOFS_REQUIRED')
body=(run/'export/top.art.gbr').read_bytes()
if p.digest(body)!=proofs[0]['generated_sha256']:raise ValueError('VISUAL_OUTPUT_BYTES_CHANGED')
e.verify_sources(run)
raw=(run/'source_snapshot/top.art.gbr').read_bytes();original,_,_=p.source_profile.parse_source(raw);n=len(original.objects)
source=p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in original.objects),1,-1,origin=(0,0))
base=(run/'reference/top.art.gbr').read_bytes()
if p.digest(base)!=p.load(run/'REFERENCE_BINDING.json')['generated_sha256']:raise ValueError('FRESH_REFERENCE_CHANGED')
prior_native=e.parse(base)
prior=source.union(p.unary_union([p.affine_scale(p.source_profile.object_geometry(o)[0],1,-1,origin=(0,0))for o in prior_native.objects[n:]]))
native=e.parse(body);new=[p.affine_scale(p.source_profile.object_geometry(o)[0],1,-1,origin=(0,0))for o in native.objects[n:]];after=source.union(p.unary_union(new));growth=after.difference(source);repair=after.difference(prior);folder=run/'visual';folder.mkdir();os.environ['MPLCONFIGDIR']=str(folder/'matplotlib_cache')
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.path import Path as PlotPath
from matplotlib.patches import PathPatch
from shapely.geometry.polygon import orient
from src.growth_void_remedy_v09 import surface_parts
from src.visual_scene import svg_path
from tools.visual_report import embed_scene
import numpy as np
BG='#102634';GRAY='#bac8ce';GREEN='#42f599'
def vector(shape):
 vertices=[];codes=[]
 for piece in surface_parts(shape):
  piece=orient(piece,sign=1.)
  for ring in [piece.exterior,*piece.interiors]:
   pts=np.asarray(ring.coords);vertices.extend(pts.tolist());codes.extend([PlotPath.MOVETO]+[PlotPath.LINETO]*(len(pts)-2)+[PlotPath.CLOSEPOLY])
 path=PlotPath(np.asarray(vertices).reshape((-1,2)),np.asarray(codes,dtype=np.uint8));path.should_simplify=False;return path
shapes=dict(source=source,prior=prior,after=after,growth=growth,repair=repair);paths={k:vector(v)for k,v in shapes.items()}
x,y,x1,y1=source.bounds;size=max(x1-x,y1-y);pad=size*.035;cx,cy=(x+x1)/2,(y+y1)/2;fit=[cx-size/2-pad,cy-size/2-pad,cx+size/2+pad,cy+size/2+pad]
def axes(ax,bounds,title=None):
 a,b,c,d=bounds;ax.set_facecolor(BG);ax.set_xlim(a,c);ax.set_ylim(d,b);ax.set_aspect('equal');ax.set_axis_off()
 if title:ax.set_title(title,color='white',fontsize=14,pad=12)
def draw(ax,key,color):ax.add_patch(PathPatch(paths[key],facecolor=color,edgecolor='none',linewidth=0,antialiased=True))
def single(name,basekey,delta=None):
 fig=Figure(figsize=(10,10),dpi=180,facecolor=BG);FigureCanvasAgg(fig);ax=fig.add_axes([0,0,1,1]);axes(ax,fit);draw(ax,basekey,GRAY)
 if delta:draw(ax,delta,GREEN)
 target=folder/(name+'.png');fig.canvas.print_png(target);fig.clear();return target
files=[single('source','source'),single('corrected_growth','after','growth'),single('pocket_repairs','after','repair')]
fig=Figure(figsize=(15,15),dpi=180,facecolor=BG);FigureCanvasAgg(fig)
details=sorted(surface_parts(repair),key=lambda x:(-x.area,x.wkb))[:3]
focuses=[]
for part in details:
 a,b,c,d=part.bounds;pad=max(c-a,d-b,.10)*.35;focuses.append([a-pad,b-pad,c+pad,d+pad])
while len(focuses)<3:focuses.append(fit)
marked=focuses[0]
for row,bounds in enumerate(focuses):
 for col,(key,title,delta)in enumerate((('source','Source',None),('prior','Prior U05',None),('after','Connected-copper correction — new fills in green','repair'))):
  ax=fig.add_subplot(3,3,row*3+col+1);axes(ax,bounds,title);draw(ax,key,GRAY)
  if delta:draw(ax,delta,GREEN)
fig.subplots_adjust(left=.015,right=.985,bottom=.025,top=.95,wspace=.04,hspace=.12);target=folder/'pocket_detail_comparison.png';fig.canvas.print_png(target);fig.clear();files.append(target)
# Relevant rejected control uses actual reparsed corruption bytes.
control_body=(run/'negative_controls/SOURCE_VOID_FILLED.gbr').read_bytes();control_native=e.parse(control_body);bad=p.affine_scale(p.source_profile.object_geometry(control_native.objects[-1])[0],1,-1,origin=(0,0));paths['bad_control']=vector(bad);cx,cy=bad.centroid.coords[0];control_bounds=[cx-.06,cy-.06,cx+.06,cy+.06]
fig=Figure(figsize=(12,6),dpi=180,facecolor=BG);FigureCanvasAgg(fig)
for col,title in enumerate(('Protected source hole','REJECTED — source hole fill')):
 ax=fig.add_subplot(1,2,col+1);axes(ax,control_bounds,title);draw(ax,'prior',GRAY)
 if col:draw(ax,'bad_control','#ff708a')
fig.subplots_adjust(left=.015,right=.985,bottom=.02,top=.93,wspace=.04);control_png=folder/'rejected_source_void_control.png';fig.canvas.print_png(control_png);fig.clear();files.append(control_png)
# Reuse the existing scene and viewer, with an explicit source-left and growth
# overlay-right default. This artifact is read-only; browser QA is separate.
scene=dict(scene_schema_version='1.0',integrity='BOUND_RECORDED_DATA',review='Owner PENDING_USER; independent NOT_RUN',manufacturing='NOT_ESTABLISHED',display_transform='mm, y-down; actual Gerber reparse',display_simplification_mm=0,measurement_authority='Native source/export proofs; PNG/SVG are display derivatives',geometry={},cases=[dict(id='gerber-u05',kind='operation',basis='Actual Gerber source and fresh exported result',electrical='NOT_ESTABLISHED',aggregate='NOT_ESTABLISHED',source_aware='SOURCE_BOUND_PHYSICAL_GEOMETRY',states=[dict(objects=[],pairs=[],checks=[],metrics={},replay=[],control_test=None)],scope=None)])
case=scene['cases'][0];case['name']=p.load(run/'input_inventory.json')['input_directory'].split('/')[-1]+' — U05 result';case['story']='REPLAY of actual parsed source and connected-copper correction Gerber. Green highlights added copper; source holes remain protected. No manufacturing release.';case['run_id']=str(run);case['profile_id']='gerber-growth-inclusive-remedy/1';case['code_commit']=p.load(run/'input_inventory.json')['source_revision'].get('commit','NOT_ESTABLISHED');case['default_state']='corrected';case['fit']=[fit[0],fit[1],fit[2]-fit[0],fit[3]-fit[1]];case['focus']=[marked[0],marked[1],marked[2]-marked[0],marked[3]-marked[1]];case['limitations']=['Owner result review pending; independent NOT_RUN: CHANNEL_UNAVAILABLE; electrical/manufacturing NOT_ESTABLISHED.','Only top.art.gbr processed; F.Cu is a computation-surface label, not inferred X2 stack identity.','Every stage is freshly constructed and reconstructed twice from source. Final exported file is reparsed and checked twice.','Prior .DS_Store custody findings remain explicit and unwaived.','Browser interaction QA NOT_RUN; PNGs are informational native-data previews.']
scene['geometry']={k:dict(path=svg_path(g,tolerance=None),bounds=case['fit'],basis='Actual Gerber reparse; no display simplification')for k,g in shapes.items()};scene['geometry']['empty']=dict(path='',bounds=case['fit']);template_state=case['states'][0]
case['states']=[]
for key,label,geometry,highlight in [('source','Original source','source',None),('prior','Prior U05','prior','prior_growth'),('corrected','Connected-copper correction — growth highlighted','after','growth'),('repairs','Connected-copper correction — pocket repairs highlighted','after','repair')]:
 state=copy.deepcopy(template_state);state.update(id=key,label=label,layers={'F.Cu':geometry},growth_highlight=highlight,delta={'F.Cu':dict(added='growth'if key=='corrected'else'repair',removed='empty')},evidence=dict(source_sha256=p.digest((run/'source_snapshot/top.art.gbr').read_bytes()),generated_sha256=p.digest(body)),candidate_verdict='RECORDED_SCOPED_CHECKS');case['states'].append(state)
scene['geometry']['prior_growth']=dict(path=svg_path(prior.difference(source),tolerance=None),bounds=case['fit']);scene['build']=p.load(run/'input_inventory.json')['source_revision'];scene['provenance']=[case['states'][-1]['evidence']];rawscene=embed_scene(scene);(folder/'scene.json').write_text(rawscene)
paths_web=['web/replay_model.js','web/backend_model.js','web/pipeline_views.js','web/workbench.js'];app='\n'.join((visual_assets/name).read_text()for name in paths_web);old="draw($('left'),C.kind==='inspection'?st:C.states[0],false)"
if old not in app:raise ValueError('VISUAL_TEMPLATE_SOURCE_BINDING_CHANGED')
app=app.replace(old,"draw($('left'),C.states[0],false)").replace("const palette={'F.Cu':'#c8ab77'","const palette={'F.Cu':'#bac8ce'")
app+='''\nconst priorDraw=draw;draw=function(svg,revision,right){priorDraw(svg,revision,right);if(right&&mode!=='delta'&&revision.growth_highlight){const path=document.createElementNS(NS,'path');path.setAttribute('d',S.geometry[revision.growth_highlight].path);path.setAttribute('fill','#42f599');path.setAttribute('fill-rule','evenodd');svg.append(path);}};\nconst resultRender=render;render=function(){resultRender();$('right-title').textContent=st.label+' — actual Gerber reparse';document.querySelector('#left').previousElementSibling.firstElementChild.textContent='Original top.art.gbr';$('scope-title').textContent='Source / growth / pocket repair comparison';$('separate-statuses').replaceChildren(text('p','Owner review: PENDING_USER'),text('p','Independent: NOT_RUN; electrical/manufacturing: NOT_ESTABLISHED'));$('metrics').replaceChildren(text('p','Nominal clearance: 0.040 mm; owner allowance not consumed'),text('p','Green = added copper; select the pocket-repair view for the latest change.'));$('focus').hidden=false;$('focus').textContent='Focus marked terminal cluster';$('focus').onclick=()=>viewBox(C.focus);document.querySelector('.story-guide').hidden=true;$('integrity').textContent='REPLAY — actual source/generated bytes; scoped checks only';};\n'''
web=(visual_assets/'web/workbench.html').read_text().replace('__SCENE__',rawscene).replace('__DIGEST__',p.digest(rawscene.encode())).replace('__APP__',app);(folder/'index.html').write_text(web)
receipt=dict(status='ACTUAL_PARSED_RESULT_VISUAL_AVAILABLE',generated_sha256=p.digest(body),baseline_sha256=p.digest(base),source_sha256=p.digest((run/'source_snapshot/top.art.gbr').read_bytes()),added_growth_area_mm2=growth.area,added_repair_area_mm2=repair.area,renderer='Matplotlib Agg '+matplotlib.__version__,path_simplification=False,browser_interaction='NOT_RUN: retained local-file URL restriction; no bypass attempted',native_renderer_qualification='NOT_ESTABLISHED; scientific previews only',source_geometry='Actual source/prior/connected-copper correction Gerber data in common coordinates',default_view='Source left; actual candidate result plus all growth in green right',files=[dict(path=str(f),sha256=p.digest(f.read_bytes()))for f in [*files,folder/'scene.json',folder/'index.html']],viewer_sources={n:p.digest((visual_assets/n).read_bytes())for n in paths_web},producer_sha256=p.digest(Path(__file__).read_bytes()),rendering_producer_binding_sha256=p.digest((run/'PRODUCER_BINDING.json').read_bytes()))
p.save(folder/'RECEIPT.json',receipt);e.verify_sources(run);print(json.dumps(receipt),flush=True)
