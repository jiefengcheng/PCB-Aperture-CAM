"""Image-to-source ROI location in the PCB data ABI; images never supply copper.

Bounded initial image model: red-copper screenshots, isotropic scale, right-angle
rotations/reflection, no perspective. Ambiguous/unmatched images fail closed.
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sexpdata
from src.native_reference import one
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from shapely import from_wkb, STRtree,contains_xy
from shapely.geometry import box,Point
from shapely.ops import unary_union
from src.native_inventory import inventory
from src.stage_abi.store import canonical, digest
from .service import CLI, CLI_SHA
from .gerber import parse, protected_counter

ROOT=Path(__file__).resolve().parents[2]
OPERATIONS=('pcb_inputs_verify','pcb_roi_locate','pcb_roi_verify')
POLICY=dict(version='pcb-roi-location/2',method='whole-board source-circle constellation hypotheses followed by complete native-copper mask refinement',minimum_iou=.90,
            boundary_uncertainty_pixels=2, maximum_outside_boundary_fraction=.001,
            minimum_distinct_location_margin=.10,minimum_landmarks=6,
            landmark_tolerance_mm=.020,max_roi_width_mm=25,
            transforms='isotropic scale; 0/90/180/270 degrees and reflection; no perspective')

def read(p):return json.loads(Path(p).read_bytes())
def local(p,output=False):
    p=Path(p).absolute()
    if ('..' in p.parts or not p.is_relative_to(ROOT) or
            any(q.is_symlink() for q in (p,*p.parents) if q.is_relative_to(ROOT)) or
            (output and not p.is_relative_to(ROOT/'out'))):
        raise ValueError('PCB_ROI_PROJECT_PATH_REQUIRED')
    return p
def fresh(p,value):
    with Path(p).open('xb') as f:f.write(canonical(value))
def bound(row):
    p=local(row['path']);blob=p.read_bytes()
    if digest(blob)!=row['sha256']:raise ValueError('PCB_ROI_INPUT_CHANGED')
    return p

def red_mask(image):
    a=np.asarray(image.convert('RGB'),dtype=np.int16)
    return (a[:,:,0]>100)&(a[:,:,0]>1.5*a[:,:,1])&(a[:,:,0]>1.3*a[:,:,2])

def image_panels(image):
    mask=red_mask(image);active=np.flatnonzero(mask.sum(1)>max(4,image.width*.01))
    if not len(active):raise ValueError('PCB_ROI_IMAGE_PROFILE_UNSUPPORTED: red copper not found')
    groups=[];begin=last=int(active[0])
    for y in active[1:]:
        y=int(y)
        if y-last>max(8,round(image.height*.02)):
            groups.append((begin,last+1));begin=y
        last=y
    groups.append((begin,last+1));panels=[]
    for y0,y1 in groups:
        xs=np.flatnonzero(mask[y0:y1].any(0))
        if not len(xs):continue
        x0,x1=int(xs[0]),int(xs[-1])+1
        if min(x1-x0,y1-y0)>=32:
            panels.append(dict(pixel_bounds=[x0,y0,x1,y1],mask=mask[y0:y1,x0:x1]))
    if not panels or len(panels)>4:raise ValueError('PCB_ROI_IMAGE_PANELS_UNSUPPORTED')
    return panels

def raster(shapes,bounds,ppm):
    x0,y0,x1,y1=bounds
    size=(max(1,math.ceil((x1-x0)*ppm)),max(1,math.ceil((y1-y0)*ppm)))
    if size[0]*size[1]>30_000_000:raise ValueError('PCB_ROI_RASTER_BUDGET')
    im=Image.new('L',size,0);draw=ImageDraw.Draw(im)
    def polygon(g):
        draw.polygon([((x-x0)*ppm,(y-y0)*ppm) for x,y in g.exterior.coords],fill=255)
        for ring in g.interiors:draw.polygon([((x-x0)*ppm,(y-y0)*ppm) for x,y in ring.coords],fill=0)
    for g in shapes:
        if g.geom_type=='Polygon':polygon(g)
        elif g.geom_type=='MultiPolygon':
            for p in g.geoms:polygon(p)
        else:raise ValueError('PCB_ROI_SOURCE_GEOMETRY_UNSUPPORTED:'+g.geom_type)
    return np.asarray(im)>127

def orient(a,k,mirror):
    a=np.rot90(a,k)
    return np.fliplr(a) if mirror else a

def scores(source,target):
    """Exact binary IoU at every valid translation, FFT plus integral sums."""
    H,W=source.shape;h,w=target.shape
    if h>H or w>W:return None
    shape=tuple(1<<(int(n)-1).bit_length() for n in (H+h-1,W+w-1))
    a=np.fft.rfftn(source.astype(np.float32),s=shape,axes=(0,1))
    b=np.fft.rfftn(target[::-1,::-1].astype(np.float32),s=shape,axes=(0,1))
    inter=np.fft.irfftn(a*b,s=shape,axes=(0,1))[h-1:H,w-1:W]
    inter=np.clip(np.rint(inter),0,min(target.sum(),source.sum()))
    ii=np.pad(source.cumsum(0,dtype=np.float64).cumsum(1),((1,0),(1,0)))
    sums=ii[h:,w:]-ii[:-h,w:]-ii[h:,:-w]+ii[:-h,:-w]
    return inter/np.maximum(target.sum()+sums-inter,1)

def resized(a,width):
    height=max(2,round(width*a.shape[0]/a.shape[1]))
    return np.asarray(Image.fromarray(a.astype('uint8')*255).resize((width,height),Image.Resampling.NEAREST))>127

def maxima(score,h,w,count):
    s=score.copy();out=[]
    for _ in range(count):
        index=int(np.argmax(s));y,x=np.unravel_index(index,s.shape);v=float(s[y,x])
        if v<0:break
        out.append((v,int(x),int(y)))
        dy,dx=max(3,h//2),max(3,w//2)
        s[max(0,y-dy):y+dy+1,max(0,x-dx):x+dx+1]=-1
    return out

def distinct(rows,count=6):
    chosen=[]
    for row in sorted(rows,key=lambda q:-q['iou']):
        x0,y0,x1,y1=row['bounds_mm'];cx,cy=(x0+x1)/2,(y0+y1)/2
        if any(math.dist((cx,cy),((r['bounds_mm'][0]+r['bounds_mm'][2])/2,(r['bounds_mm'][1]+r['bounds_mm'][3])/2))<min(x1-x0,y1-y0)*.45 for r in chosen):continue
        chosen.append(row)
        if len(chosen)==count:break
    return chosen

def circle_features(manifest,shapes):
    features={}
    for row,g in zip(manifest['objects'],shapes,strict=True):
        if row['kind']!='gr_circle' or g.geom_type!='Polygon' or g.interiors:continue
        r=(g.bounds[2]-g.bounds[0]+g.bounds[3]-g.bounds[1])/4
        if r<=0 or abs(g.area/(math.pi*r*r)-1)>.01:continue
        key=(round(g.centroid.x,6),round(g.centroid.y,6),round(r,6))
        features.setdefault(key,dict(source_id=row['id'],aliases=[],center=[g.centroid.x,g.centroid.y],radius=r))['aliases'].append(row['id'])
    return list(features.values())

def peaks(mask):
    # Eight-neighbour chamfer distance: hypotheses only; no source copper comes
    # from this raster approximation. Final acceptance uses native masks/witnesses.
    d=np.where(mask,1000.,0.).astype('float32');weight=math.sqrt(2)
    for _ in range(64):
        p=np.pad(d,1,constant_values=0)
        d=np.minimum.reduce([d,p[:-2,1:-1]+1,p[2:,1:-1]+1,p[1:-1,:-2]+1,p[1:-1,2:]+1,
                             p[:-2,:-2]+weight,p[:-2,2:]+weight,p[2:,:-2]+weight,p[2:,2:]+weight])
    maximum=np.asarray(Image.fromarray(d.astype('uint8')).filter(ImageFilter.MaxFilter(13)))
    yy,xx=np.where((d>=7)&(d<=min(mask.shape)*.07)&(d>=maximum-.1))
    selected=[]
    for radius,x,y in sorted(zip(d[yy,xx].tolist(),xx.tolist(),yy.tolist()),reverse=True):
        if min(x,y,mask.shape[1]-x,mask.shape[0]-y)<radius+2:continue
        if all(math.dist((x,y),(q[0],q[1]))>max(8,radius) for q in selected):selected.append((x,y,radius))
    return selected

def seed_poses(mask,features):
    observed=peaks(mask)
    if observed:
        cutoff=max(7,.60*observed[0][2])
        observed=[p for p in observed if p[2]>=cutoff][:60]
    if len(observed)<POLICY['minimum_landmarks']:raise ValueError('PCB_ROI_IMAGE_LANDMARKS_INSUFFICIENT')
    centers=np.array([f['center'] for f in features]);radii=np.array([f['radius'] for f in features])
    tree=STRtree([Point(*p) for p in centers]);rows=[];H,W=mask.shape
    anchors=observed[:8]
    for k in range(4):
        points=[]
        for x,y,r in observed:
            for _ in range(k):x,y,W0,H0=y,W-1-x,H,W;W,H=W0,H0
            points.append((x,y,r));H,W=mask.shape
        ow,oh=orient(mask,k,False).shape[1],orient(mask,k,False).shape[0]
        for mirror in (False,True):
            p=np.array([(ow-1-x if mirror else x,y,r) for x,y,r in points])
            for a in range(min(8,len(p))):
                for c in range(a+1,min(8,len(p))):
                    vector=p[c,:2]-p[a,:2];length=float(np.linalg.norm(vector))
                    if not min(ow,oh)*.12<length<min(ow,oh)*.65:continue
                    for i,center in enumerate(centers):
                        scale=radii[i]/p[a,2]
                        if not .6<ow*scale<POLICY['max_roi_width_mm']:continue
                        predicted=center+scale*vector
                        tolerance=max(.012,length*scale*.10)
                        for j in tree.query(box(predicted[0]-tolerance,predicted[1]-tolerance,predicted[0]+tolerance,predicted[1]+tolerance)):
                            j=int(j)
                            if j==i:continue
                            delta=centers[j]-center;s=float(delta@vector/(length*length))
                            if s<=0 or np.linalg.norm(delta-s*vector)>max(.007,3*s) or abs(radii[j]/radii[i]-p[c,2]/p[a,2])>.18:continue
                            translation=center-s*p[a,:2]
                            # Additional landmark support prunes hypotheses before
                            # complete native-mask refinement, across the whole board.
                            projected=translation+s*p[:,:2]
                            distances=np.sqrt(((projected[:,None,:]-centers[None,:,:])**2).sum(2))
                            nearest=np.min(distances,axis=1);matched=nearest<=max(.012,4*s)
                            support=int(matched.sum())
                            if support<6 or support<.65*len(p):continue
                            x0,y0=translation
                            rows.append(dict(iou=support/len(p),seed_landmarks=support,k=k,mirror=mirror,
                                bounds_mm=[float(x0),float(y0),float(x0+ow*s),float(y0+oh*s)]))
    return distinct(rows,8)

def fit_panel(mask,shapes,bounds,features):
    candidates=seed_poses(mask,features);tree=STRtree(shapes)
    for row in candidates:
        a=orient(mask,row['k'],row['mirror'])
        for ppm,spread,steps in [(40,.06,21),(100,.025,21),(200,.006,17)]:
            old=row['bounds_mm'];width=old[2]-old[0];height=old[3]-old[1]
            pad=max(.04,width*spread*1.3)
            window=[old[0]-pad,old[1]-pad,old[2]+pad,old[3]+pad]
            source=raster([shapes[int(i)] for i in tree.query(box(*window))],window,ppm)
            best=None
            for physical in np.linspace(width*(1-spread),width*(1+spread),steps):
                target=resized(a,max(8,round(physical*ppm)));s=scores(source,target)
                if s is None:continue
                y,x=np.unravel_index(int(np.argmax(s)),s.shape);v=float(s[y,x]);h,w=target.shape
                q=dict(iou=v,k=row['k'],mirror=row['mirror'],bounds_mm=[window[0]+x/ppm,window[1]+y/ppm,window[0]+(x+w)/ppm,window[1]+(y+h)/ppm])
                if best is None or v>best['iou']:best=q
            if best is not None:row.update(best)
        # Final coordinate fit samples the exact native union at screenshot
        # pixel centres. This avoids coarse-raster edge/rounding bias without
        # relaxing the location acceptance thresholds.
        w=a.shape[1];h=a.shape[0];old=row['bounds_mm']
        geometry=unary_union([shapes[int(i)] for i in tree.query(box(old[0]-.2,old[1]-.2,old[2]+.2,old[3]+.2))])
        params=np.array([(old[0]+old[2])/2,(old[1]+old[3])/2,old[2]-old[0]],dtype=float)
        def objective(values,step):
            target=a[::step,::step]
            xs=values[0]+(np.arange(w)[::step]+.5-w/2)*values[2]/w
            ys=values[1]+(np.arange(h)[::step]+.5-h/2)*values[2]/w
            native=contains_xy(geometry,xs[None,:],ys[:,None])
            return float((native&target).sum()/max(1,(native|target).sum()))
        for delta,subsample in [(.005,3),(.002,2),(.0005,1)]:
            for _ in range(3):
                for axis in (2,0,1):
                    options=[]
                    for offset in (-2,-1,0,1,2):
                        q=params.copy();q[axis]+=offset*delta
                        options.append((objective(q,subsample),q))
                    _,params=max(options,key=lambda r:r[0])
        row.update(iou=objective(params,1),bounds_mm=[float(params[0]-params[2]/2),float(params[1]-params[2]*h/w/2),float(params[0]+params[2]/2),float(params[1]+params[2]*h/w/2)])
        row['boundary_metrics']=pixel_metrics(a,geometry,row['bounds_mm'])
    return sorted(candidates,key=lambda r:-r['iou'])

def pixel_metrics(mask,geometry,bounds):
    h,w=mask.shape;x0,y0,x1,y1=bounds
    xs=x0+(np.arange(w)+.5)*(x1-x0)/w;ys=y0+(np.arange(h)+.5)*(y1-y0)/h
    expected=contains_xy(geometry,xs[None,:],ys[:,None])
    n=POLICY['boundary_uncertainty_pixels']
    def dilate(a):return np.asarray(Image.fromarray(a.astype('uint8')*255).filter(ImageFilter.MaxFilter(2*n+1)))>0
    far=(mask&~dilate(expected))|(expected&~dilate(mask));union=max(1,int((mask|expected).sum()))
    return dict(iou=float((mask&expected).sum()/union),outside_boundary_pixels=int(far.sum()),
                outside_boundary_fraction=float(far.sum()/union),boundary_uncertainty_pixels=n)

def assess(matches,landmarks=None):
    if not matches or matches[0]['iou']<POLICY['minimum_iou']:
        raise ValueError('PCB_ROI_NOT_LOCATED')
    metrics=matches[0].get('boundary_metrics',{})
    if metrics.get('boundary_uncertainty_pixels')!=POLICY['boundary_uncertainty_pixels'] or metrics.get('outside_boundary_fraction',1)>POLICY['maximum_outside_boundary_fraction']:
        raise ValueError('PCB_ROI_BOUNDARY_MODEL_EXCEEDED')
    if len(matches)>1 and matches[0]['iou']-matches[1]['iou']<POLICY['minimum_distinct_location_margin']:
        raise ValueError('PCB_ROI_AMBIGUOUS: supply one landmark or a larger crop')
    if landmarks is not None:
        good=[r for r in landmarks if r['matched']]
        if len(good)<POLICY['minimum_landmarks'] or len(good)<.8*len(landmarks):
            raise ValueError('PCB_ROI_LANDMARKS_NOT_ESTABLISHED')
    return True

def landmark_check(mask,bounds,sites):
    """Post-fit conditional witness; not independent of image-based selection."""
    im=Image.fromarray(mask.astype('uint8')*255);distance=np.zeros(mask.shape,dtype=np.uint8)
    for n in range(1,65):
        im=im.filter(ImageFilter.MinFilter(3));a=np.asarray(im)>127
        if not a.any():break
        distance[a]=n
    peaks=(distance>4)&(distance==np.asarray(Image.fromarray(distance).filter(ImageFilter.MaxFilter(13))))
    yy,xx=np.where(peaks);rank=sorted(zip(distance[yy,xx].tolist(),xx.tolist(),yy.tolist()),reverse=True)
    maxima=[]
    for radius,x,y in rank:
        if all(math.dist((x,y),(q[0],q[1]))>8 for q in maxima):maxima.append((x,y))
    x0,y0,x1,y1=bounds;sx=mask.shape[1]/(x1-x0);sy=mask.shape[0]/(y1-y0);out=[];used=set()
    for site in sites:
        x,y=site['center'];r=site['radius']
        if not (x0+r<x<x1-r and y0+r<y<y1-r):continue
        px,py=(x-x0)*sx,(y-y0)*sy
        ranked=sorted((math.hypot((qx-px)/sx,(qy-py)/sy),i) for i,(qx,qy) in enumerate(maxima) if i not in used)
        error,index=ranked[0] if ranked else (None,None)
        matched=error is not None and error<=POLICY['landmark_tolerance_mm']
        if matched:used.add(index)
        out.append(dict(source_id=site['source_id'],native_center_mm=[x,y],matched=matched,residual_mm=error))
    return out

class ROIService:
    def __init__(self,host):
        if set(host)!={'schema','inputs','output'} or host['schema']!='pcb-roi-host/1':raise ValueError('PCB_ROI_HOST_INVALID')
        if set(host['inputs'])!={'kicad','gerber','crop'}:raise ValueError('PCB_ROI_INPUT_SET_INVALID')
        self.host=host;self.inputs={k:bound(v) for k,v in host['inputs'].items()};self.out=local(host['output'],True)
        if digest(CLI.read_bytes())!=CLI_SHA:raise ValueError('PINNED_KICAD_CLI_CHANGED')
    def command(self,argv,stem):
        p=subprocess.run(list(map(str,argv)),capture_output=True,timeout=100,env=dict(os.environ,KICAD_RUN_FROM_BUILD_DIR='1'))
        (self.out/(stem+'.stdout')).write_bytes(p.stdout);(self.out/(stem+'.stderr')).write_bytes(p.stderr)
        fresh(self.out/(stem+'.command.json'),dict(argv=list(map(str,argv)),returncode=p.returncode,cli_sha256=CLI_SHA,at=datetime.now(timezone.utc).isoformat()))
        if p.returncode:raise ValueError('PCB_ROI_NATIVE_COMMAND_FAILED:'+stem)
        return p.stdout.decode().strip()
    def load_source(self):
        saved=read(self.out/'inputs.json');raw=(self.out/'source_manifest.json').read_bytes()
        if digest(raw)!=saved['manifest_sha256']:raise ValueError('PCB_ROI_MANIFEST_CHANGED')
        manifest=json.loads(raw);shapes=[]
        for row in manifest['objects']:
            blob=(self.out/'source_wkb'/f'{row["geometry_sha256"]}.wkb').read_bytes()
            if digest(blob)!=row['geometry_sha256']:raise ValueError('PCB_ROI_SOURCE_CACHE_CHANGED')
            shapes.append(from_wkb(blob))
        return manifest,shapes
    def verify_inputs(self):
        self.out.mkdir();raw=self.inputs['kicad'].read_bytes();inv=inventory(raw)
        rows=[r for r in inv['objects'] if 'F.Cu' in r['layers']]
        for row in rows:
            node=sexpdata.loads(raw[slice(*row['source_span'])].decode())
            width=one(node,'width',None) if row['kind'] in ('segment','arc') else one(one(node,'stroke',[]),'width',None)
            row['trace_width_mm']=float(width[0]) if width else 0.
            if row['kind'] in ('segment','arc') and row['trace_width_mm']<=0:raise ValueError('PCB_ROI_SOURCE_TRACE_WIDTH_UNSUPPORTED')
        unsupported=[r['id'] for r in rows if not r['geometry_sha256']]
        if unsupported:raise ValueError('PCB_ROI_UNSUPPORTED_FCU_SOURCE:'+str(unsupported[:10]))
        if not rows:raise ValueError('PCB_ROI_NO_FCU_SOURCE')
        (self.out/'source_wkb').mkdir()
        for h in sorted({r['geometry_sha256'] for r in rows}):(self.out/'source_wkb'/(h+'.wkb')).write_bytes(inv['payloads'][h])
        manifest=dict(source_sha256=inv['source_sha256'],objects=rows)
        fresh(self.out/'source_manifest.json',manifest)
        plot=self.out/'source_plot';plot.mkdir()
        if self.command([CLI,'version'],'version')!='10.99.0':raise ValueError('KICAD_VERSION_CHANGED')
        self.command([CLI,'pcb','export','gerbers','--layers','F.Cu','--precision','6','--no-protel-ext','-o',str(plot)+'/',self.inputs['kicad']],'source_export')
        generated=list(plot.glob('*.gbr'))
        if len(generated)!=1:raise ValueError('PCB_ROI_SOURCE_PLOT_MISSING')
        supplied,plotted=parse(self.inputs['gerber']),parse(generated[0])
        roles=lambda g:{k:v for k,v in g.file_attrs.items() if k not in ('.CreationDate','.ProjectId')}
        if (roles(supplied)!=roles(plotted) or supplied.file_attrs.get('.FileFunction')!=('Copper','L1','Top') or
                protected_counter(supplied.objects,set())!=protected_counter(plotted.objects,set())):
            raise ValueError('PCB_ROI_KICAD_GERBER_MISMATCH')
        result=dict(facts=dict(passed=True,source_objects=len(rows),source_gerber_correspondence=True,
                    registration_fit_used=False,layer='F.Cu',construction_status='NOT_RUN'),
                    inputs=self.host['inputs'],manifest_sha256=digest((self.out/'source_manifest.json').read_bytes()),
                    generated_source_gerber=str(generated[0]),generated_source_gerber_sha256=digest(generated[0].read_bytes()),
                    scope='Same pinned exporter semantic primitive correspondence; not arbitrary exporter compatibility or electrical intent')
        fresh(self.out/'inputs.json',result);return result
    def locate(self):
        manifest,shapes=self.load_source();bounds=[min(g.bounds[0] for g in shapes),min(g.bounds[1] for g in shapes),max(g.bounds[2] for g in shapes),max(g.bounds[3] for g in shapes)]
        image=Image.open(self.inputs['crop']);image.load()
        if max(image.size)>5000 or image.width*image.height>16_000_000:raise ValueError('PCB_ROI_IMAGE_BUDGET')
        panels=image_panels(image);rows=[]
        features=circle_features(manifest,shapes)
        for index,panel in enumerate(panels):
            for r in fit_panel(panel['mask'],shapes,bounds,features):rows.append(dict(r,panel=index,pixel_bounds=panel['pixel_bounds']))
        matches=distinct(rows,6)
        fresh(self.out/'location_hypotheses.json',dict(candidates=matches,policy=POLICY))
        assess(matches)
        best=matches[0];chosen=panels[best['panel']];a=orient(chosen['mask'],best['k'],best['mirror'])
        Image.fromarray(a.astype('uint8')*255).save(self.out/'located_mask.png')
        result=dict(facts=dict(passed=True,located=True,unique_in_supported_search=True,construction_status='NOT_RUN'),
            best=best,candidates=matches,policy=POLICY,source_bounds_mm=bounds,
            uncertainty_mm=.005+POLICY['boundary_uncertainty_pixels']*max((best['bounds_mm'][2]-best['bounds_mm'][0])/a.shape[1],(best['bounds_mm'][3]-best['bounds_mm'][1])/a.shape[0]),
            limits=['Two screenshot pixels bound raster-edge uncertainty; outside-band disagreement must not exceed 0.1 percent. This is image localization, not copper clearance.', 'Search uniqueness is bounded by the declared scale/orientation grid, not a proof over arbitrary perspectives.','Post-fit landmark checks are separate but not independent of image selection.','Screenshot locates ROI only; native geometry supplies candidates.'])
        fresh(self.out/'location.json',result);return result
    def verify(self):
        manifest,shapes=self.load_source();location=read(self.out/'location.json');best=location['best'];bounds=best['bounds_mm']
        # Data-ABI geometric landmarks, independent of T01 selection/policy.
        grouped={}
        for row,g in zip(manifest['objects'],shapes,strict=True):
            if row['kind']!='gr_circle' or not g.intersects(box(*bounds)) or g.geom_type!='Polygon' or g.interiors:continue
            radius=(g.bounds[2]-g.bounds[0]+g.bounds[3]-g.bounds[1])/4
            if radius<=0 or abs(g.area/(math.pi*radius**2)-1)>.01:continue
            s=grouped.setdefault(row['geometry_sha256'],dict(source_id=row['id'],aliases=[],center=[g.centroid.x,g.centroid.y],radius=radius))
            s['aliases'].append(row['id'])
        sites=list(grouped.values())
        mask=np.asarray(Image.open(self.out/'located_mask.png'))>127
        geometry=unary_union([shapes[int(i)] for i in STRtree(shapes).query(box(*bounds))])
        actual=pixel_metrics(mask,geometry,bounds)
        if actual!=best['boundary_metrics']:raise ValueError('PCB_ROI_LOCATION_METRICS_CHANGED')
        landmarks=landmark_check(mask,bounds,sites);assess(location['candidates'],landmarks)
        expected=raster([shapes[int(i)] for i in STRtree(shapes).query(box(*bounds))],bounds,mask.shape[1]/(bounds[2]-bounds[0]))
        expected=np.asarray(Image.fromarray(expected.astype('uint8')*255).resize((mask.shape[1],mask.shape[0]),Image.Resampling.NEAREST))>127
        overlay=np.zeros((*mask.shape,3),dtype='uint8');overlay[mask]=[235,35,55];overlay[expected]=[20,170,100];overlay[mask&expected]=[245,220,70]
        Image.fromarray(overlay).save(self.out/'roi_overlay.png')
        # Deliberate location controls use copies only. Never alter the source,
        # accepted mask, or source-to-Gerber correspondence to make them pass.
        controls=[]
        def reject(name,action):
            try:action()
            except ValueError as e:controls.append(dict(name=name,rejection=str(e)))
            else:raise ValueError('PCB_ROI_CONTROL_NOT_REJECTED:'+name)
        shifted=[bounds[0]+.1,bounds[1],bounds[2]+.1,bounds[3]]
        wrong=dict(best,boundary_metrics=pixel_metrics(mask,geometry,shifted))
        wrong['iou']=wrong['boundary_metrics']['iou']
        reject('wrong_location_100um',lambda:assess([wrong]))
        altered=mask.copy();x,y,r=peaks(mask)[0];yy,xx=np.ogrid[:mask.shape[0],:mask.shape[1]]
        altered[(xx-x)**2+(yy-y)**2<(r*.85)**2]=False
        Image.fromarray(altered.astype('uint8')*255).save(self.out/'control_missing_copper.png')
        wrong=dict(best,boundary_metrics=pixel_metrics(altered,geometry,bounds));wrong['iou']=wrong['boundary_metrics']['iou']
        reject('missing_interior_copper',lambda:assess([wrong]))
        reject('ambiguous_locations',lambda:assess([best,dict(best)]))
        fresh(self.out/'roi_controls.json',dict(controls=controls,scope='Conditional location gate controls; not independent source-registration qualification'))
        result=dict(facts=dict(passed=True,location_verified=True,source_circle_landmarks=len(sites),source_circle_occurrences=sum(len(s['aliases']) for s in sites),
                              matched_landmarks=sum(r['matched'] for r in landmarks),deliberate_controls=len(controls),kicad_gerber_correspondence=True,construction_status='NOT_RUN'),
                    bounds_mm=bounds,location_sha256=digest((self.out/'location.json').read_bytes()),
                    input_manifest_sha256=digest((self.out/'inputs.json').read_bytes()),landmarks=landmarks,
                    uncertainty_mm=location['uncertainty_mm'],overlay=str(self.out/'roi_overlay.png'))
        fresh(self.out/'roi_verified.json',result);return result
    def dispatch(self,operation):
        return dict(pcb_inputs_verify=self.verify_inputs,pcb_roi_locate=self.locate,pcb_roi_verify=self.verify)[operation]()
