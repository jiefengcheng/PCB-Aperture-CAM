"""U03 image hypotheses using visible round pads, with unchanged ROI acceptance.

Bulk copper must not set a global minimum landmark radius. Candidate features
are hypotheses only: the original full native-mask refinement, pixel-error,
uniqueness and landmark predicates remain mandatory. Shared ROI code is frozen.
"""
import math
import numpy as np
from PIL import Image
from shapely import STRtree,contains_xy
from shapely.geometry import Point,box
from shapely.ops import unary_union
from src.pcb_data_abi.roi import POLICY,peaks,distinct,orient,raster,resized,scores,pixel_metrics


def round_peak_records(mask):
    angles=np.arange(48)*2*math.pi/48;records=[]
    for x,y,radius in peaks(mask):
        fractions=[]
        for factor in (.8,1.1,1.35):
            xx=np.rint(x+factor*radius*np.cos(angles)).astype(int)
            yy=np.rint(y+factor*radius*np.sin(angles)).astype(int)
            valid=(xx>=0)&(yy>=0)&(xx<mask.shape[1])&(yy<mask.shape[0])
            if not valid.all():break
            fractions.append(float(mask[yy,xx].mean()))
        if len(fractions)==3 and fractions[0]>=.95 and max(fractions[1:])<=.35:
            records.append(dict(x=x,y=y,radius=radius,inner_red_fraction=fractions[0],edge_red_fraction=fractions[1],outer_red_fraction=fractions[2]))
    records.sort(key=lambda r:(r['edge_red_fraction']+r['outer_red_fraction'],-r['radius'],r['y'],r['x']))
    return records


def round_peaks(mask):
    return [(r['x'],r['y'],r['radius']) for r in round_peak_records(mask)]


def seed_poses(mask,features):
    observed=round_peaks(mask)[:60]
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

