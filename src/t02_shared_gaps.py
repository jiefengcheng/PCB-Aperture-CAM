"""Source-bound repeated straight gaps; centered rectangles share bank offsets.

This only removes optional proposed T02 growth. Original/entry copper, existing
joints and all ordinary finite predicates remain authoritative. A missing or
KEEP member pins its bank. Complete fill proposals cannot invade frozen gaps.
"""
import hashlib
from collections import defaultdict
from shapely import STRtree,to_wkb
from shapely.geometry import box,LineString
from shapely.affinity import scale
from shapely.ops import unary_union
from src.trace_width_clearance import TraceWidthContract
from src.stage_abi.store import canonical
from src.t02_rectangle_exposure import original_index

EPS=TraceWidthContract().comparison_epsilon_mm
POLICY=dict(schema='t02-shared-neighbor-gaps/1',source='ORIGINAL_RESOLVED_COPPER',
 recognition='REPEATED_COLLINEAR_FACES_WITH_EMPTY_STRAIGHT_CORRIDORS',
 minimum_side_overlap_fraction=.75,maximum_gap_width_multiple=2.,
 maximum_repeat_spacing_multiple=2.,projection='MINIMUM_SAFE_CENTERED_BANK_OFFSET',
 fixed_or_keep_member='ANCHOR_BANK_WITHOUT_REASSIGNMENT',
 fills='REJECT_ENTIRE_PROPOSAL_ON_PROTECTED_GAP_INTRUSION',
 comparison_epsilon_mm=EPS)
ACTIVE=None

def policy():return dict(POLICY)

def surfaces(g):
 if g.geom_type=='Polygon':return [g]
 return [p for q in getattr(g,'geoms',())for p in surfaces(q)]

def interval_edges(material):
 """Coalesce collinear source edges before discovering full pad-facing slots."""
 edges=defaultdict(list)
 for ordinal,p in enumerate(surfaces(material)):
  for ring in [p.exterior,*p.interiors]:
   for a,b in zip(ring.coords,list(ring.coords)[1:]):
    for axis in (0,1):
     other=1-axis
     if abs(a[axis]-b[axis])<=EPS and abs(a[other]-b[other])>EPS:
      edges[axis,round(a[axis],12),ordinal].append(tuple(sorted((a[other],b[other]))))
 result=[]
 for (axis,plane,owner),spans in sorted(edges.items()):
  merged=[]
  for lo,hi in sorted(spans):
   if merged and lo<=merged[-1][1]+EPS:merged[-1][1]=max(hi,merged[-1][1])
   else:merged.append([lo,hi])
  result.extend(dict(axis=axis,plane=plane,owner=owner,lo=lo,hi=hi)for lo,hi in merged)
 return result

def corridor(axis,lo,hi,start,end):
 return box(lo,start,hi,end)if axis==0 else box(start,lo,end,hi)

def records(scene,original,current):
 index=original_index(scene,original);source=index.geometries
 rects={r['source_id']:source[r['source_id']]for r in scene['objects']if r['kind']=='rectangle'and r['source_id']in source}
 # Exact source aliases cannot manufacture a repeated slot or an extra variable.
 unique={}
 for sid,g in sorted(rects.items()):
  if not any(g.equals(v)for v in unique.values()):unique[sid]=g
 rects=unique;material=unary_union([source[s]for s in sorted(source)]);parts=surfaces(material);tree=STRtree(parts);edges=interval_edges(material);boundary=material.boundary;found=[]
 for sid,g in sorted(rects.items()):
  if not g.equals(box(*g.bounds)):continue
  owners=[int(i)for i in tree.query(g,predicate='intersects')if parts[int(i)].intersection(g).area>EPS]
  if len(owners)!=1:continue
  own=owners[0];bounds=g.bounds
  for axis in (0,1):
   other=1-axis;start,end=bounds[other],bounds[other+2];width=bounds[axis+2]-bounds[axis];length=end-start
   for sign in (-1,1):
    plane=bounds[axis+2]if sign==1 else bounds[axis]
    face=LineString([(plane,start),(plane,end)])if axis==0 else LineString([(start,plane),(end,plane)])
    exposed=face.intersection(boundary)
    if exposed.length+EPS<POLICY['minimum_side_overlap_fraction']*length:continue # Integral attachment faces are not slots.
    segments=[exposed]if exposed.geom_type=='LineString'else[g for g in getattr(exposed,'geoms',())if g.geom_type=='LineString']
    candidates=[]
    for edge in edges:
     if edge['axis']!=axis:continue
     gap=sign*(edge['plane']-plane)
     if not EPS<gap<=POLICY['maximum_gap_width_multiple']*width:continue
     for segment in segments:
      lo=max(start,edge['lo'],segment.bounds[other]);hi=min(end,edge['hi'],segment.bounds[other+2])
      if hi-lo+EPS<POLICY['minimum_side_overlap_fraction']*length:continue
      left,right=sorted((plane,edge['plane']));slot=corridor(axis,left,right,lo,hi)
      if material.intersection(slot).area>EPS:continue
      candidates.append((gap,edge['plane'],lo,hi,edge['owner']))
    if not candidates:continue
    gap,opposite,lo,hi,owner=min(candidates)
    found.append(dict(axis=axis,left=min(plane,opposite),right=max(plane,opposite),lo=lo,hi=hi,owners=[own,owner]if sign==1 else[owner,own],source_id=sid,bank=0 if sign==1 else 1))
 buckets=defaultdict(list)
 for row in found:buckets[row['axis'],round(row['left'],12),round(row['right'],12)].append(row)
 groups=[]
 for (axis,left,right),rows in sorted(buckets.items()):
  slots={}
  for row in rows:slots.setdefault((round(row['lo'],12),round(row['hi'],12)),[]).append(row)
  # Separate far-away coincidental alignments; shared ownership grants no exemption.
  runs=[]
  for (lo,hi),witnesses in sorted(slots.items()):
   if runs and lo-runs[-1][-1]['hi']<=POLICY['maximum_repeat_spacing_multiple']*max(hi-lo,runs[-1][-1]['hi']-runs[-1][-1]['lo']):runs[-1].append(dict(lo=lo,hi=hi,witnesses=witnesses))
   else:runs.append([dict(lo=lo,hi=hi,witnesses=witnesses)])
  for run in runs:
   # Repeated disjoint channels, not aliases/overlapping views of one slot.
   if len(run)<2 or any(b['lo']<a['hi']-EPS for a,b in zip(run,run[1:])):continue
   common=[set.intersection(*[{w['owners'][bank]for w in s['witnesses']}for s in run])for bank in (0,1)]
   if not any(common):continue # At least one genuinely shared original neighbor.
   banks=[set(),set()];anchors=[False,False]
   for slot in run:
    for bank in (0,1):
     members={w['source_id']for w in slot['witnesses']if w['bank']==bank}
     banks[bank].update(members);anchors[bank]|=not members
   group=dict(axis=axis,left=left,right=right,original_gap_mm=right-left,shared_source_components=[sorted(v)for v in common],banks=[sorted(b)for b in banks],fixed_wall_anchors=anchors,slots=[dict(lo=s['lo'],hi=s['hi'])for s in run])
   group['group_id']=hashlib.sha256(canonical(group)).hexdigest();groups.append(group)
 result=dict(policy=policy(),source_sha256=scene['source_sha256'],groups=groups)
 # Existing unequal intrusions are a failed predecessor, not permission to trim it.
 material_now=unary_union([current[s]for s in sorted(current)])
 for group in groups:
  for slot in group['slots']:
   zone=corridor(group['axis'],group['left'],group['right'],slot['lo'],slot['hi'])
   if material_now.intersection(zone).area>EPS:raise ValueError('SHARED_GAP_STAGE_ENTRY_INTRUSION:'+group['group_id'])
 return result

def project(spec,original,current,proposed,*,factor_rows=None):
 """Intersect bank equalities by union-find; no search, offset compounding or additions."""
 # Other rectangles can approach a shared slot from its ends. Bound those
 # whole centered proposals too, before solving bank equalities. Protected
 # coordinated slots are subsets of these source corridors, so the reductions
 # remain safe after projection and require no iterative geometry search.
 proposed=dict(proposed);factor_rows={s:list(factor_rows[s])if factor_rows is not None else[(g.bounds[a+2]-g.bounds[a])/(current[s].bounds[a+2]-current[s].bounds[a])for a in (0,1)]for s,g in proposed.items()};guards=[]
 for sid,g in sorted(proposed.items()):
  core=current[sid]
  for group in spec['groups']:
   if any(sid in bank for bank in group['banks']):continue
   for slot in group['slots']:
    zone=corridor(group['axis'],group['left'],group['right'],slot['lo'],slot['hi'])
    if g.intersection(zone).area<=EPS:continue
    choices=[]
    for axis in (0,1):
     a,b=core.bounds[axis],core.bounds[axis+2];lo,hi=zone.bounds[axis],zone.bounds[axis+2]
     distance=lo-b if b<=lo+EPS else a-hi if a>=hi-EPS else None
     if distance is None:continue
     factors=list(factor_rows[sid]);factors[axis]=min(factors[axis],1+2*max(0.,distance)/(b-a));trial=core if factors==[1.,1.]else scale(core,*factors,origin=core.centroid)
     if trial.intersection(zone).area<=EPS:choices.append((trial.area,-axis,trial,factors,axis))
    if not choices:raise ValueError('SHARED_GAP_ENTRY_OR_PROPOSAL_UNRESOLVED')
    _,_,g,factors,axis=max(choices,key=lambda v:v[:2]);factor_rows[sid]=factors
    guards.append(dict(source_id=sid,group_id=group['group_id'],axis=axis,factors=factors))
  proposed[sid]=g
 parents={};anchored=set()
 def find(x):
  parents.setdefault(x,x)
  if parents[x]!=x:parents[x]=find(parents[x])
  return parents[x]
 def join(a,b):
  a,b=find(a),find(b)
  if a!=b:parents[max(a,b)]=min(a,b)
 for group in spec['groups']:
  axis=group['axis']
  for bank,ids in enumerate(group['banks']):
   variables=[(sid,axis)for sid in ids]
   for var in variables:find(var)
   for var in variables[1:]:join(variables[0],var)
   if group['fixed_wall_anchors'][bank]:anchored.update(variables)
 components=defaultdict(list)
 for var in parents:components[find(var)].append(var)
 offsets={};ledger=[]
 for root,variables in sorted(components.items()):
  offered=[]
  for sid,axis in sorted(variables):
   core=current[sid];delta=(factor_rows[sid][axis]-1)*(core.bounds[axis+2]-core.bounds[axis])/2 if sid in proposed else 0.
   if delta<-EPS:raise ValueError('SHARED_GAP_PROJECTION_REMOVES_ENTRY')
   offered.append(max(0.,delta))
  value=0. if any(v in anchored for v in variables)else min(offered)
  for var in variables:offsets[var]=value
  ledger.append(dict(variables=[list(v)for v in sorted(variables)],offered_offsets_mm=offered,common_offset_mm=value,fixed_wall_anchor=any(v in anchored for v in variables)))
 result=dict(proposed);result_factors={}
 for sid,g in proposed.items():
  core=current[sid];factors=[]
  for axis in (0,1):
   w=core.bounds[axis+2]-core.bounds[axis]
   if (sid,axis)not in offsets and factor_rows is not None:factors.append(factor_rows[sid][axis])
   else:
    off=offsets.get((sid,axis),(g.bounds[axis+2]-g.bounds[axis]-w)/2);factors.append(min(factor_rows[sid][axis],max(1.,1+2*off/w)))
  target=core if factors==[1.,1.]else scale(core,*factors,origin=core.centroid)
  if not target.covers(core)or target.difference(g).area>EPS:raise ValueError('SHARED_GAP_PROJECTION_NOT_SUBSET')
  result[sid]=target
  result_factors[sid]=factors
 zones=[]
 for group in spec['groups']:
  axis=group['axis'];bank_offsets=[min([offsets[(sid,axis)]for sid in ids],default=0.)for ids in group['banks']];left=group['left']+bank_offsets[0];right=group['right']-bank_offsets[1]
  if right-left<=0:raise ValueError('SHARED_GAP_COLLAPSED')
  zones.extend(dict(group_id=group['group_id'],axis=axis,left=left,right=right,lo=s['lo'],hi=s['hi'],gap_mm=right-left)for s in group['slots'])
 proof=dict(policy=policy(),source_sha256=spec['source_sha256'],banks=ledger,zones=zones,factors=result_factors,approaching_proposal_limits=guards)
 return result,proof

def check(proof,material,*,tolerance_mm=0.):
 checks=[]
 for row in proof['zones']:
  zone=corridor(row['axis'],row['left'],row['right'],row['lo'],row['hi']);inner=zone.buffer(-tolerance_mm,join_style=2)if tolerance_mm else zone
  intrusion=material.intersection(inner).area
  checks.append(dict(group_id=row['group_id'],gap_mm=row['gap_mm'],intrusion_mm2=intrusion,passed=intrusion<=EPS))
 return dict(passed=all(q['passed']for q in checks),checks=checks,tolerance_mm=tolerance_mm,scope='Complete original straight slot spans; same-net and fill allowances do not override')

def require(proof,material,*,tolerance_mm=0.):
 q=check(proof,material,tolerance_mm=tolerance_mm)
 if not q['passed']:raise ValueError('T02_SHARED_NEIGHBOR_GAP_INTRUSION')
 return q

def fill_check(details,current,logical):
 spec=details.get('shared_neighbor_gaps')
 if spec is None:return None # Legacy direct merge fixtures have no public plan.
 return check(frozen(spec,current),logical)

def frozen(spec,current):
 zones=[]
 for group in spec['groups']:
  axis=group['axis'];offsets=[]
  for bank,ids in enumerate(group['banks']):
   values=[current[s].bounds[axis+2]-group['left']if bank==0 else group['right']-current[s].bounds[axis]for s in ids]
   if group['fixed_wall_anchors'][bank]:values.append(0.)
   if values and max(values)-min(values)>EPS:raise ValueError('SHARED_GAP_BANK_NONUNIFORM')
   offsets.append(min(values,default=0.))
  left,right=group['left']+offsets[0],group['right']-offsets[1]
  if right<=left:raise ValueError('SHARED_GAP_COLLAPSED')
  zones.extend(dict(group_id=group['group_id'],axis=axis,left=left,right=right,lo=s['lo'],hi=s['hi'],gap_mm=right-left)for s in group['slots'])
 return dict(policy=policy(),source_sha256=spec['source_sha256'],zones=zones)

def complete(proof,material,*,tolerance_mm=0.):
 q=check(proof,material,tolerance_mm=tolerance_mm);edges=[];boundary=interval_edges(material);epsilon=max(tolerance_mm,EPS)
 for row in proof['zones']:
  for plane in (row['left'],row['right']):
   face=LineString([(plane,row['lo']),(plane,row['hi'])])if row['axis']==0 else LineString([(row['lo'],plane),(row['hi'],plane)])
   # Compare straight boundary intervals directly: no nearly-zero GEOS buffers,
   # and no repeated whole-board offsets. Existing numerical tolerance only.
   intervals=sorted((max(row['lo'],e['lo']),min(row['hi'],e['hi']))for e in boundary if e['axis']==row['axis']and abs(e['plane']-plane)<=epsilon and e['hi']>=row['lo']and e['lo']<=row['hi'])
   covered=0.;end=row['lo']
   for lo,hi in intervals:
    covered+=max(0.,hi-max(lo,end));end=max(end,hi)
   missing=max(0.,row['hi']-row['lo']-covered)
   edges.append(dict(group_id=row['group_id'],missing_boundary_mm=missing,passed=missing<=EPS))
 q.update(boundaries=edges,passed=q['passed']and all(v['passed']for v in edges))
 if not q['passed']:raise ValueError('T02_SHARED_NEIGHBOR_UNIFORMITY_FAILED')
 return q

def restore(store,scene):
 global ACTIVE
 ACTIVE=None
 if scene is None:return
 for entry in scene['lineage']:
  ref=entry.get('plan_ref')
  if entry.get('stage')!='t02'or ref is None:continue
  plan=store.get_json(ref,kind='plan')
  spec=plan.get('details',{}).get('shared_neighbor_gaps')
  if spec is None:continue
  # Actual post-projection widths are carried with immutable source identities.
  from src.stage_abi.runtime import operands
  _,now,_=operands(store,scene);before_scene=store.get_json(plan['scene_ref'],kind='scene');_,before,original=operands(store,before_scene)
  if records(before_scene,original,before)!=spec:raise ValueError('SHARED_GAP_RESTORED_SOURCE_CHANGED')
  if 'shared_gap_state_ref'not in entry:raise ValueError('SHARED_GAP_FROZEN_STATE_MISSING')
  state=store.get_json(entry['shared_gap_state_ref'],kind='shared-gap-state')
  if state.get('source_sha256')!=scene['source_sha256']or state.get('policy')!=policy():raise ValueError('SHARED_GAP_FROZEN_STATE_CHANGED')
  expected={(g['group_id'],s['lo'],s['hi'])for g in spec['groups']for s in g['slots']}
  actual={(s['group_id'],s['lo'],s['hi'])for s in state['zones']}
  if expected!=actual or len(state['zones'])!=len(expected):raise ValueError('SHARED_GAP_FROZEN_COVERAGE_CHANGED')
  ACTIVE=state
  complete(ACTIVE,unary_union(list(now.values())))

def remedy(logical,predecessor):
 if ACTIVE is None:return None
 return check(ACTIVE,logical.difference(predecessor))
