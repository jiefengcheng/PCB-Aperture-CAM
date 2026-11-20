"""Opt-in additive two-face profile over an exact saved-25 floor.

Source centerline stations/poses are immutable. Extra material is constructed
in source-chord normal cells; left+right widths share ONE total-width cap.
"""
from pathlib import Path
from time import perf_counter
import json,hashlib,math
from collections import OrderedDict
import numpy as np
from shapely import STRtree,to_wkb,from_wkb
from shapely.geometry import LineString,Point,Polygon,box
from shapely.affinity import translate
from shapely.ops import unary_union
from src.trace_width_clearance import TraceWidthContract
from .finite_profile_union import polygonal,certified_union
from .limiting_math import GUARD,MARGIN
from .profile_refinement import clearance_barrier,contains_floor
SCHEMA='t04-side-specific-width-profile/1'
CAP_RESERVE=.0005 # construction headroom, never a relaxation of the width cap
STEP=.01
_WIDTH_PROOFS=OrderedDict();_RECIPE_PROOFS=OrderedDict()

def digest(g):return hashlib.sha256(to_wkb(g)).hexdigest()
def recipe_digest(recipe):return hashlib.sha256(json.dumps(recipe,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def remember(cache,key,value):
 cache[key]=value
 while len(cache)>128:cache.popitem(last=False)
 return value

def retain(floor,extension):
 # Exact whole-floor predicate at every step. Uncertifiable optional pieces
 # may be omitted; no positive or boundary source loss is tolerated.
 g,method=certified_union(floor,extension)
 if method!='EXACT_FLOOR_FALLBACK':return g,method
 parts=[extension]if extension.geom_type=='Polygon'else list(extension.geoms);parts=sorted(parts,key=lambda q:q.area,reverse=True);queue=[parts];g=floor;attempts=0
 while queue and attempts<64:
  batch=queue.pop(0);candidate,name=certified_union(g,unary_union(batch));attempts+=1
  if name!='EXACT_FLOOR_FALLBACK':g=candidate
  elif len(batch)>1:
   mid=len(batch)//2;queue[0:0]=[batch[:mid],batch[mid:]]
 if not contains_floor(g,floor):raise ValueError('SIDE_COMPONENT_FLOOR_UNION_FAILED')
 return g,'EXACT_COMPONENT_BATCHES_'+str(attempts)


def linear_parts(g):
 if g.geom_type=='LineString':return [g]
 return [p for c in getattr(g,'geoms',[])for p in linear_parts(c)]


def extent(body,p,n,span):
 line=LineString([p-n*span,p+n*span]);point=Point(p);parts=[g for g in linear_parts(body.intersection(line))if g.distance(point)<1e-9]
 if not parts:return None
 values=[float(np.dot(np.asarray(x)-p,n))for g in parts for x in g.coords]
 return max(values),-min(values)


def allowance(barrier,p,n,span):
 g=LineString([p,p+n*span]).intersection(barrier)
 return span if g.is_empty else float(Point(p).distance(g))


def allocate(total,left,right):
 budget=min(max(0.,total),max(0.,left)+max(0.,right))
 # Spend the shared width budget on the larger free gap first, converging
 # toward equal residual gaps. A constrained face cannot lend copper away.
 a=min(max(0.,left),budget,max(0.,(left-right+budget)/2))
 b=min(max(0.,right),budget-a);a=min(max(0.,left),budget-b)
 return a,b


def taper(values,stations,maximum,span=.05):
 v=np.asarray(values,float).copy();v[0]=v[-1]=0.;s=np.asarray(stations);rate=maximum/span
 for i in range(1,len(v)):v[i]=min(v[i],v[i-1]+rate*(s[i]-s[i-1]))
 for i in range(len(v)-2,-1,-1):v[i]=min(v[i],v[i+1]+rate*(s[i+1]-s[i]))
 return v


def quad(record,progress=1.):
 a=np.asarray(record['a']);b=np.asarray(record['b']);n=np.asarray(record['normal']);la,ra,lb,rb=record['base'];xa,ya,xb,yb=np.asarray(record['extra'])*progress
 return Polygon([a+n*(la+xa),b+n*(lb+xb),b-n*(rb+yb),a-n*(ra+ya)])


def build(floor,recipe,progress):
 if progress<=0 or not recipe['cells']:return floor
 pieces=[]
 for c in recipe['cells']:
  a=np.asarray(c['a']);b=np.asarray(c['b']);n=np.asarray(c['normal']);la,ra,lb,rb=c['base'];xa,ya,xb,yb=np.asarray(c['extra'])*progress
  # Add only the requested face. Including the unchanged opposite boundary
  # in thousands of overlapping cells creates needless exact-overlay losses.
  if max(xa,xb)>1e-10:pieces.append(Polygon([a,b,b+n*(lb+xb),a+n*(la+xa)]))
  if max(ya,yb)>1e-10:pieces.append(Polygon([a,b,b-n*(rb+yb),a-n*(ra+ya)]))
 # This is an untrusted upper mask only; accepted material is certified after
 # obstacle clipping. Never discard the proposal merely because this temporary
 # upper union cannot represent an unchanged floor boundary exactly.
 raw=polygonal(unary_union(pieces));return polygonal(unary_union([floor,raw]))


def verify_recipe(recipe,core,width,low,high,floor,body,progress):
 key=(recipe_digest(recipe),digest(core),digest(floor),digest(body),width,low,high,progress)
 if key in _RECIPE_PROOFS:return _RECIPE_PROOFS[key]
 if recipe['schema']!=SCHEMA or recipe['source_core_sha256']!=hashlib.sha256(to_wkb(core)).hexdigest()or recipe['baseline_body_sha256']!=hashlib.sha256(to_wkb(floor)).hexdigest():raise ValueError('SIDE_PROFILE_INPUT_BINDING_CHANGED')
 if recipe['source_width_mm']!=width or recipe['maximum_width_mm']>min(width*1.5,width+.03,low*1.25)+1e-12:raise ValueError('SIDE_PROFILE_TOTAL_CAP_CHANGED')
 if not contains_floor(body,floor) or not body.covers(core):raise ValueError('SIDE_PROFILE_ACCEPTED_COPPER_REMOVED')
 for c in recipe['cells']:
  a,b,n=map(np.asarray,(c['a'],c['b'],c['normal']));d=b-a
  if abs(np.linalg.norm(n)-1)>1e-10 or abs(np.dot(d,n))>1e-10 or np.linalg.norm(d)<1e-12:raise ValueError('SIDE_PROFILE_CENTERLINE_CELL_CHANGED')
  la,ra,lb,rb=c['base'];xa,ya,xb,yb=np.asarray(c['extra'])*progress
  if min(la,ra,lb,rb)<width/2-1e-6 or min(xa,ya,xb,yb)<0 or max(la+ra+xa+ya,lb+rb+xb+yb)>high+1e-12:raise ValueError('SIDE_PROFILE_TWO_FACE_WIDTH_CAP_CHANGED')
 if body.equals_exact(floor,0):
  upper=core.buffer((high-width)/2,quad_segs=128)if high>width else core
 else:upper=build(floor,recipe,progress)
 if body.difference(floor).difference(upper).area>1e-12:raise ValueError('SIDE_PROFILE_FINITE_COPPER_OUTSIDE_CERTIFIED_CELLS')
 if body.equals_exact(floor,0) and floor.difference(upper).area>1e-12:raise ValueError('SIDE_PROFILE_RETAINED_FLOOR_SOURCE_CAP_CHANGED')
 return remember(_RECIPE_PROOFS,key,dict(passed=True,cells=len(recipe['cells']),total_width_cap_mm=high,accepted_floor_retained=True,centerline_policy='IMMUTABLE_SOURCE_CHORDS_PLUS_UNCHANGED_SAVED_POSE'))


def actual_widths(floor,body,recipe,high):
 """Probe finite-copper normal sections at endpoints and quarter stations.
 Full affine-cell side-cap witnesses are checked separately by verify_recipe.
 Only an unchanged inherited floor is grandfathered at a wide junction.
 """
 key=(digest(floor),digest(body),recipe_digest(recipe),high)
 if key in _WIDTH_PROOFS:return _WIDTH_PROOFS[key]
 if body.equals_exact(floor,0):return remember(_WIDTH_PROOFS,key,dict(passed=True,failures=[],sections=0,maximum_measured_section_mm=None,identity='Exact floor; the separate source-bound geometric cap is still verified'))
 if not contains_floor(body,floor):return dict(passed=False,failures=[dict(reason='SIDE_PROFILE_FLOOR_NOT_CONTAINED')],sections=0,maximum_measured_section_mm=None)
 delta=polygonal(body.difference(floor));parts=[delta]if delta.geom_type=='Polygon'else list(delta.geoms);dtree=STRtree(parts)
 failures=[];checked=0;maximum=0.;seen=set()
 for c in recipe['cells']:
  a=np.asarray(c['a']);b=np.asarray(c['b']);n=np.asarray(c['normal']);d=b-a;length=float(np.linalg.norm(d));u=d/length
  if len(dtree.query(box(min(a[0],b[0])-high*2,min(a[1],b[1])-high*2,max(a[0],b[0])+high*2,max(a[1],b[1])+high*2)))==0:continue
  # New-cell corners are the finite profile's critical longitudinal events.
  # The source floor is independently grandfathered only when unchanged at a
  # junction; any newly increased section must fit the real total cap.
  for t in (0.,.25,.5,.75,1.):
   p=a+d*t;section_key=tuple(p)+tuple(n)
   if section_key in seen:continue
   seen.add(section_key);old=extent(floor,p,n,high*2);new=extent(body,p,n,high*2)
   if old is not None and new is None:
    # Exact retained-floor containment proves this interval still exists.
    # Recover the section by its floor plus added filled surfaces; overlay
    # lines/points are not copper, and no coordinate snapping is performed.
    intervals=[(-old[1],old[0])];ray=LineString([p-n*high*2,p+n*high*2])
    for part in linear_parts(delta.intersection(ray)):
     values=[float(np.dot(np.asarray(pt)-p,n))for pt in part.coords];intervals.append((min(values),max(values)))
    intervals.sort();merged=[]
    for lo,hi in intervals:
     if merged and lo<=merged[-1][1]+1e-12:merged[-1]=(merged[-1][0],max(merged[-1][1],hi))
     else:merged.append((lo,hi))
    found=next((v for v in merged if v[0]<=0<=v[1]),None)
    if found is not None:new=(found[1],-found[0])
   if old is None or new is None:
    ray=LineString([p-n*high*2,p+n*high*2])
    # An unsupported inherited section is kept only if no added copper enters
    # that exact section. This is not permission to construct an unbound width.
    if not delta.intersection(ray).is_empty:failures.append(dict(reason='SIDE_PROFILE_NORMAL_SECTION_MISSING',station=p.tolist(),normal=n.tolist(),old_missing=old is None,new_missing=new is None))
    continue
   oldw=sum(old);neww=sum(new);checked+=1;maximum=max(maximum,neww)
   if neww>max(high,oldw)+1e-12:failures.append(dict(reason='SIDE_PROFILE_ACTUAL_SECTION_OVER_CAP',station=p.tolist(),width_mm=neww,old_width_mm=oldw,cap_mm=high))
 value=dict(passed=not failures,failures=failures,sections=checked,maximum_measured_section_mm=maximum)
 return remember(_WIDTH_PROOFS,key,value)if not failures else value



def finish_supplement(floor,extension,recipe,high):
 """An optional construction cannot spend copper or waive a width rejection."""
 body,method=retain(floor,extension);widths=actual_widths(floor,body,recipe,high)
 rejected=list(widths['failures'])
 if not widths['passed']:
  bad=[Point(x['station']).buffer(high*2+.001,quad_segs=32) for x in widths['failures'] if 'station' in x]
  extension=polygonal(extension.difference(unary_union(bad)))
  body,method=retain(floor,extension);widths=actual_widths(floor,body,recipe,high)
 if not widths['passed']:
  # The failed supplement has no accepted status. Discard it completely,
  # then validate the exact floor; native proposal/final gates still follow.
  rejected.extend(widths['failures']);body=floor;extension=Polygon()
  method='EXACT_FLOOR_AFTER_FINITE_CAP_REJECTION'
  widths=actual_widths(floor,body,recipe,high)
 if not widths['passed']:raise ValueError('SIDE_PROFILE_ACCEPTED_FLOOR_WIDTH_REJECTED:'+str(widths['failures'][:2]))
 return body,extension,method,widths,rejected


def plan(rows,current,original,paths,roles,context,settings,rule,progress=None):
 from .translated_profile import SCHEMA as MOTION
 from .profile_floor import CopperFloor
 begin=perf_counter();floor=rule.get('copper_floor')
 if floor is None:floor=CopperFloor.saved(rule['side_specific_seed'],rule['side_specific_seed_sha256'])
 seed,floors,bulk=floor.load(rule['input_binding'],paths);floor_sha=floor.sha256
 used={s for ss in paths.values()for s in ss};fixedids=sorted(set(rows)-used);fixed=[bulk.get(s,current[s])for s in fixedids];tree=STRtree(fixed);keys=sorted(paths);contract=TraceWidthContract();owners={r:context.ids[ss[0]]for r,ss in paths.items()};cores={r:unary_union([original[s]for s in ss])for r,ss in paths.items()};barrier_cache={};chosen={};data={};plans={};recipes={};stats=[]
 for number,r in enumerate(keys):
  q=seed['routes'][r];ss=paths[r];w=q['source_width_mm'];pose=q['translation_mm'];low=q['corridor_width_mm'];high=min(w*settings.maximum_factor,w+settings.maximum_total_width_increase_mm,low*(1+rule['width_variation_limit']));core=translate(cores[r],xoff=pose[0],yoff=pose[1]);floor=floors[r]
  if ss!=q['source_ids']or any(rows[s]['metadata']['minimum_caliper_mm']!=w for s in ss)or math.hypot(*pose)>.025+1e-12 or not floor.covers(core):raise ValueError('SIDE_PROFILE_SOURCE_OR_POSE_CHANGED')
  search=high-w/2+GUARD+2*MARGIN;barriers=[]
  for i in sorted(map(int,tree.query(core,predicate='dwithin',distance=search))):
   sid=fixedids[i];g=fixed[i]
   if g.is_empty:continue
   if sid not in barrier_cache:barrier_cache[sid]=clearance_barrier(g,GUARD+2*MARGIN)
   barrier=barrier_cache[sid]
   if context.ids[sid]==owners[r]:
    contact=core.intersection(original[sid])
    if not contact.is_empty:barrier=barrier.difference(contact.buffer(w+contract.original_port_buffer_gap_mm,quad_segs=128))
   barriers.append(barrier)
  for other in keys:
   if other==r:continue
   g=chosen[other]['body']if other in chosen else floors[other]
   if core.distance(g)>search:continue
   barrier=clearance_barrier(g,GUARD+2*MARGIN)
   if owners[other]==owners[r]:
    othercore=translate(cores[other],xoff=seed['routes'][other]['translation_mm'][0],yoff=seed['routes'][other]['translation_mm'][1]);contact=core.intersection(othercore)
    if not contact.is_empty:barrier=barrier.difference(contact.buffer(min(w,seed['routes'][other]['source_width_mm'])+contract.original_port_buffer_gap_mm,quad_segs=128))
   barriers.append(barrier)
  barrier=polygonal(unary_union(barriers));cells=[];skipped=0
  for sid in ss:
   pts=np.asarray(rows[sid]['metadata']['route_points_mm'],float)+np.asarray(pose);line=LineString(pts);length=line.length
   cum=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(pts,axis=0),axis=1))];extra=np.linspace(0,length,max(2,math.ceil(length/STEP)+1));stations=np.unique(np.r_[cum,[t for t in extra if np.min(np.abs(cum-t))>1e-10]]);xy=np.column_stack([np.interp(stations,cum,pts[:,i])for i in(0,1)]);tang=np.gradient(xy,axis=0);norm=np.column_stack([-tang[:,1],tang[:,0]]);norm/=np.linalg.norm(norm,axis=1)[:,None];targets=[]
   for p,n in zip(xy,norm):
    ext=extent(floor,p,n,high*2)
    if ext is None or sum(ext)>=high-CAP_RESERVE:targets.append((0.,0.));continue
    l,rr=ext;fl=max(0.,allowance(barrier,p,n,high*2)-l);fr=max(0.,allowance(barrier,p,-n,high*2)-rr);targets.append(allocate(high-CAP_RESERVE-l-rr,fl,fr))
   left=taper([t[0]for t in targets],stations,high-w);right=taper([t[1]for t in targets],stations,high-w)
   for i,(a,b)in enumerate(zip(xy,xy[1:])):
    direction=b-a;size=np.linalg.norm(direction)
    if size<1e-10:continue
    n=np.array([-direction[1],direction[0]])/size;base=[];extras=[];ok=True
    for j,p in ((i,a),(i+1,b)):
     ext=extent(floor,p,n,high*2)
     if ext is None or sum(ext)>high-CAP_RESERVE or min(ext)<w/2-1e-6:ok=False;break
     l,rr=ext;x=min(left[j],max(0.,allowance(barrier,p,n,high*2)-l));y=min(right[j],max(0.,allowance(barrier,p,-n,high*2)-rr));budget=max(0.,high-CAP_RESERVE-l-rr)
     if x+y>budget and x+y>0:x,y=np.asarray([x,y])*budget/(x+y)
     base.extend((l,rr));extras.extend((float(x),float(y)))
    if not ok or max(extras,default=0.)<1e-7:skipped+=1;continue
    cell=dict(source_id=sid,a=a.tolist(),b=b.tolist(),normal=n.tolist(),base=base,extra=extras)
    g=quad(cell)
    if not g.is_valid or g.area<=0:skipped+=1;continue
    cells.append(cell)
  recipe=dict(schema=SCHEMA,source_core_sha256=hashlib.sha256(to_wkb(core)).hexdigest(),baseline_body_sha256=q['sha256'],source_width_mm=w,maximum_width_mm=high,source_ids=ss,translation_mm=pose,source_centerlines={s:(np.asarray(rows[s]['metadata']['route_points_mm'],float)+np.asarray(pose)).tolist()for s in ss},transition_length_mm=.05,cells=cells)
  upper=build(floor,recipe,1.);extension=polygonal(upper.difference(floor).difference(barrier))
  body,extension,method,widths,rejected_widths=finish_supplement(floor,extension,recipe,high)
  verify_recipe(recipe,core,w,low,high,floor,body,1.)
  plans[r]=dict(translation_mm=pose,source_width_mm=w,source_width_cap_mm=min(w*settings.maximum_factor,w+settings.maximum_total_width_increase_mm),corridor_width_mm=low,outer_width_ceiling_mm=high,progress_cap=settings.maximum_factor,baseline_profile=dict(factor=1.,corridor_width_mm=low,outer_width_ceiling_mm=q['floor_high_mm'],body_sha256=q['sha256']),side_specific_profile=True,candidate_count=2,fixed_contact_components=None)
  data[r]=dict(width=w,cap=high,line=LineString(rows[ss[0]]['metadata']['route_points_mm']),baseline_body=floor,maximum_body=body,allowed_extension=extension,side_recipe=recipe,bulk_floor=bulk,forbidden=barrier,unchanged_source_keep=tuple(pose)==(0.,0.) and floor.equals_exact(cores[r],0))
  chosen[r]=dict(pose=tuple(pose),low=low,high=high,body=body,delta=body.difference(context.cores[owners[r][0]]));recipes[r]=recipe
  stats.append(dict(route=r,cells=len(cells),skipped_cells=skipped,added_area_mm2=body.difference(floor).area,width_sections=widths,finite_union=method,rejected_optional_width_sections=rejected_widths))
  if progress:progress(dict(event='side_profile_plan',route=r,index=number+1,routes=len(keys),cells=len(cells),added_area_mm2=stats[-1]['added_area_mm2']))
 receipt=dict(schema=MOTION,side_specific_growth=True,side_profile_schema=SCHEMA,width_variation_limit=rule['width_variation_limit'],maximum_translation_mm=.025,transition_length_mm=.05,route_plans=plans,planning_seconds=perf_counter()-begin,exact_pair_checks=0,baseline_reference=dict(seed_sha256=floor_sha,source_stage_sha256=seed['source_stage_sha256'],reference_only=True,proof_reuse=False),baseline_retention='EVERY_SAVED_25_TRACE_AND_BULK_SURFACE_RESERVED; POSES_FIXED',side_profiles=stats,construction_cap_reserve_mm=CAP_RESERVE)
 return chosen,data,cores,receipt


def body_at(core,width,plan,data,f,*,envelope=False):
 t=max(0.,min(1.,(f-1)/(plan['progress_cap']-1)));floor=data['baseline_body']
 if t==0:body=floor
 elif t==1:body=data['maximum_body']
 else:
  upper=build(floor,data['side_recipe'],t);body=retain(floor,polygonal(upper.intersection(data['allowed_extension'])))[0]
 # Exact original-source KEEP has no new copper and inherits the original
 # ladder's unchanged checking footprint. Every actual addition or translation
 # still receives the complete checking halo.
 if envelope and not(data.get('unchanged_source_keep',False) and body.equals_exact(floor,0)):
  return body.buffer(MARGIN,quad_segs=128)
 return body
