"""Source-bound repeated straight gaps; centered rectangles share bank offsets.

This only removes optional proposed T02 growth. Original/entry copper, existing
joints and all ordinary finite predicates remain authoritative. A missing or
KEEP member pins its bank. Complete fill proposals cannot invade frozen gaps.
"""
import hashlib
import math
from collections import defaultdict
from shapely import STRtree,to_wkb,from_wkb
from shapely.geometry import box,LineString,Polygon
from shapely.affinity import scale
from shapely.ops import unary_union
from src.trace_width_clearance import TraceWidthContract
from src.stage_abi.store import canonical
from src.t02_rectangle_exposure import original_index
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM
from src.t02_gap_settings import capture as gap_settings

EPS=TraceWidthContract().comparison_epsilon_mm
POLICY=dict(schema='t02-shared-neighbor-gaps/5',source='ORIGINAL_RESOLVED_COPPER',
 recognition='REPEATED_COLLINEAR_FACES_WITH_EMPTY_STRAIGHT_CORRIDORS',
 minimum_side_overlap_fraction=.75,maximum_gap_width_multiple=2.,
 maximum_repeat_spacing_multiple=2.,projection='MINIMUM_SAFE_CENTERED_BANK_OFFSET',
 fixed_or_keep_member='ANCHOR_BANK_WITHOUT_REASSIGNMENT',
 fixed_wall_geometry='SOURCE_BOUND_QUALIFIED_ENTRY_CONTOUR; preceding copper retained',
 retained_entry_material='EXACT_QUALIFIED_ORIGINAL_ATTACHMENT_FOOTPRINT; NO_NEW_FILL_ALLOWANCE',
 inherited_curved_wall='FULL_SINGLE_VALUED_CONTOUR; MATCH_COMPLETE_SPAN_MINIMUM_GAPS',
 inherited_wall_recognition_tolerance_mm=POLYGON_TOLERANCE_MM,
 fills='REJECT_ENTIRE_PROPOSAL_ON_PROTECTED_GAP_INTRUSION',
 comparison_epsilon_mm=EPS)
ACTIVE=None

def policy():return dict(POLICY,gap_matching=gap_settings().snapshot())

def matching(spec,zones):
 """Compare complete accepted slot widths, never refresh a later fill budget."""
 fraction=spec['policy']['gap_matching']['maximum_relative_gap_difference']
 groups=defaultdict(list)
 for row in zones:
  if not row.get('held_for_fixed_entry'):groups[row['group_id']].append(row['gap_mm'])
 checks=[]
 for gid,widths in sorted(groups.items()):
  low,high=min(widths),max(widths)
  if low<=0:raise ValueError('SHARED_GAP_COLLAPSED')
  checks.append(dict(group_id=gid,minimum_gap_mm=low,maximum_gap_mm=high,
   relative_gap_difference=(high-low)/low,maximum_relative_gap_difference=fraction,
   passed=high-low<=fraction*low+EPS))
 return dict(passed=all(r['passed']for r in checks),groups=checks,
  basis='Whole source-qualified spans; (maximum gap - minimum gap) / minimum gap')

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

def face(axis,plane,lo,hi):
 return LineString([(plane,lo),(plane,hi)])if axis==0 else LineString([(lo,plane),(hi,plane)])

def lines(shape):
 if shape.geom_type=='LineString':return [shape]
 return [p for g in getattr(shape,'geoms',())for p in lines(g)]

def missing_length(intervals,lo,hi):
 covered=0.;end=lo
 for a,b in sorted(intervals):
  a,b=max(lo,a),min(hi,b)
  covered+=max(0.,b-max(a,end));end=max(end,b)
 return max(0.,hi-lo-covered)

def supports_face(shape,axis,plane,lo,hi):
 # Source group planes are canonicalized to 12 decimals. Match the original
 # straight intervals with the same arithmetic epsilon, not exact GEOS line
 # coincidence after that canonicalization (which can differ by one ulp).
 return any(e['axis']==axis and abs(e['plane']-plane)<=EPS and min(hi,e['hi'])-max(lo,e['lo'])>EPS for e in interval_edges(shape))

def entry_walls(groups,source,current):
 """Original faces authorize support IDs; only their entry contours may anchor.

 Recognition uses the existing native fidelity bound for inherited contours.
 It never changes a surface or allows a new bridge. The final empty corridors
 and exact model boundary witnesses still have to pass independently.
 """
 ids=sorted(source);tree=STRtree([source[s]for s in ids]);walls=[]
 for group in groups:
  axis=group['axis'];other=1-axis
  for bank in (0,1):
   for slot in group['slots']:
    lo,hi=slot['lo'],slot['hi'];plane=group['left'if bank==0 else'right'];edge=face(axis,plane,lo,hi)
    # A slot with a nominated rectangle has a movable wall, even when the
    # opposite bank of another slot is fixed in the same source group.
    members=[s for s in group['banks'][bank]if supports_face(source[s],axis,plane,lo,hi)]
    if members:continue
    window=corridor(axis,plane-EPS,plane+EPS,lo,hi)
    supports=sorted(ids[int(i)]for i in tree.query(window)if supports_face(source[ids[int(i)]],axis,plane,lo,hi))
    if not supports or any(s not in current for s in supports):raise ValueError('SHARED_GAP_FIXED_SUPPORT_MISSING')
    if any(source[s].difference(current[s]).area>EPS for s in supports):raise ValueError('SHARED_GAP_FIXED_SUPPORT_CORE_CHANGED')
    material=unary_union([current[s]for s in supports])
    candidates=[e for e in interval_edges(material)if e['axis']==axis and e['hi']>lo and e['lo']<hi and group['left']-EPS<=e['plane']<=group['right']+EPS]
    if not candidates:raise ValueError('SHARED_GAP_FIXED_WALL_NOT_STRAIGHT')
    # The longest inherited straight part supplies the nominal plane. Preserve
    # the entire actual contour, including sub-grid endpoint residues.
    nominal=max(candidates,key=lambda e:(min(hi,e['hi'])-max(lo,e['lo']),-abs(e['plane']-plane)))['plane']
    # Include genuine original joints in the inherited wall witness. A source
    # joint can leave a sub-grid lip after T04; a straight support-only witness
    # would incorrectly demand that this preceding copper disappear.
    original_support=unary_union([source[s]for s in supports])
    attachments=sorted(ids[int(i)]for i in tree.query(original_support,predicate='intersects'))
    if any(s not in current for s in attachments):raise ValueError('SHARED_GAP_FIXED_ATTACHMENT_MISSING')
    if any(source[s].difference(current[s]).area>EPS for s in attachments):raise ValueError('SHARED_GAP_FIXED_ATTACHMENT_CORE_CHANGED')
    material=unary_union([current[s]for s in attachments]);boundary=material.boundary
    clipped=boundary.intersection(corridor(axis,nominal-POLYGON_TOLERANCE_MM,nominal+POLYGON_TOLERANCE_MM,lo,hi))
    # End caps at lo/hi face along the other axis; they are not this wall.
    contour=unary_union([LineString([a,b])for line in lines(clipped)for a,b in zip(line.coords,list(line.coords)[1:])if abs(a[other]-b[other])>EPS])
    intervals=[(g.bounds[other],g.bounds[other+2])for g in lines(contour)]
    curved=missing_length(intervals,lo,hi)>EPS or contour.hausdorff_distance(face(axis,nominal,lo,hi))>POLYGON_TOLERANCE_MM
    extra={}
    if curved:
     # A qualified uniform trace end may bulge past its original straight
     # support. Keep its actual contour, not a fictitious straight wall or a
     # larger numerical tolerance. Require one wall value over the whole span.
     a,b=(nominal-POLYGON_TOLERANCE_MM,group['right'])if bank==0 else(group['left'],nominal+POLYGON_TOLERANCE_MM)
     clipped=boundary.intersection(corridor(axis,a,b,lo,hi))
     contour=unary_union([LineString([a,b])for line in lines(clipped)for a,b in zip(line.coords,list(line.coords)[1:])if abs(a[other]-b[other])>EPS])
     intervals=[(g.bounds[other],g.bounds[other+2])for g in lines(contour)]
     if missing_length(intervals,lo,hi)>EPS or abs(sum(b-a for a,b in intervals)-(hi-lo))>EPS:raise ValueError('SHARED_GAP_FIXED_WALL_NOT_SINGLE_VALUED')
     extreme=contour.bounds[axis+2 if bank==0 else axis]
     intrusion=max(0.,(extreme-nominal)*(1 if bank==0 else-1))
     if (extreme>=group['right']-EPS if bank==0 else extreme<=group['left']+EPS):raise ValueError('SHARED_GAP_FIXED_WALL_CROSSES_SOURCE_SLOT')
     extra=dict(maximum_intrusion_mm=intrusion,measurement='MINIMUM_AXIS_GAP_OVER_COMPLETE_SOURCE_SPAN')
    offset=(nominal-plane)*(1 if bank==0 else-1)
    if offset<-EPS:raise ValueError('SHARED_GAP_FIXED_WALL_RECEDES')
    # Store only the exact already-present footprint on the gap side. This is
    # not a tolerance buffer or permission for later sub-grid growth. Everything
    # outside that frozen material remains subject to the strict area predicate.
    a,b=(nominal,group['right']if curved else nominal+POLYGON_TOLERANCE_MM)if bank==0 else(group['left']if curved else nominal-POLYGON_TOLERANCE_MM,nominal)
    retained=unary_union(surfaces(material.intersection(corridor(axis,a,b,lo,hi))))
    witnesses=lambda values:[dict(source_id=s,original_sha256=hashlib.sha256(to_wkb(source[s])).hexdigest(),entry_sha256=hashlib.sha256(to_wkb(current[s])).hexdigest())for s in values]
    walls.append(dict(group_id=group['group_id'],bank=bank,lo=lo,hi=hi,offset_mm=max(0.,offset),plane=nominal,contour_wkb_hex=to_wkb(contour).hex(),retained_material_wkb_hex=to_wkb(retained).hex(),supports=witnesses(supports),original_attachments=witnesses(attachments),**extra))
  # Earlier fixed walls may differ slightly. Their individual qualified planes
  # remain immutable; the registered tolerance compares the resulting gaps.
 return walls

def bank_anchor(spec,group,bank):
 values=[w['offset_mm']for w in spec['entry_walls']if w['group_id']==group['group_id']and w['bank']==bank]
 return min(values)if values else None

def zone_rows(spec,group,left,right,current):
 held=group['group_id'] in spec.get('fixed_entry_holds',{})
 for slot in group['slots']:
  walls=[w for w in spec['entry_walls']if w['group_id']==group['group_id']and w['lo']==slot['lo']and w['hi']==slot['hi']]
  planes=[left,right];axis=group['axis']
  for bank in (0,1):
   members=slot['bank_members'][bank]
   if members:
    values=[current[s].bounds[axis+2 if bank==0 else axis]for s in members]
    planes[bank]=max(values)if bank==0 else min(values)
   else:
    inherited=[w for w in walls if w['bank']==bank]
    if len(inherited)!=1:raise ValueError('SHARED_GAP_SLOT_WALL_COVERAGE_CHANGED')
    planes[bank]=inherited[0]['plane']
  intrusion=sum(w.get('maximum_intrusion_mm',0.)for w in walls)
  row=dict(group_id=group['group_id'],axis=axis,left=planes[0],right=planes[1],lo=slot['lo'],hi=slot['hi'],gap_mm=planes[1]-planes[0]-intrusion,entry_walls=walls)
  if held:
   row['held_for_fixed_entry']=True
   witness=spec.get('occupied_entry_slots',{}).get(slot_key(group,slot))
   if witness is not None:
    row['fixed_entry_copper']=witness['copper']
    row['entry_walls']=witness['walls']
  yield row

def slot_key(group,slot):
 return hashlib.sha256(canonical([group['group_id'],slot['lo'],slot['hi']])).hexdigest()

def fixed_entry_holds(spec,current):
 """Hold the gap-facing pad axis for copper outside known entry wall footprints."""
 if not spec['groups']:return {},{}
 ids=sorted(current);tree=STRtree([current[s]for s in ids]);occupied={};holds={}
 empty=to_wkb(Polygon()).hex()
 for group in spec['groups']:
  axis=group['axis'];gid=group['group_id']
  for slot in zone_rows(spec,group,group['left'],group['right'],current):
   lo,hi=slot['lo'],slot['hi'];left,right=slot['left'],slot['right']
   zone=corridor(axis,left,right,lo,hi)
   retained=unary_union([from_wkb(bytes.fromhex(w['retained_material_wkb_hex']))for w in slot['entry_walls']])
   nearby=[ids[int(i)]for i in sorted(tree.query(zone,predicate='intersects'))]
   intruders=[s for s in nearby if current[s].intersection(zone).difference(retained).area>EPS]
   if not intruders:continue
   margin=POLYGON_TOLERANCE_MM
   window=corridor(axis,left-4*margin,right+4*margin,lo-4*margin,hi+4*margin)
   material=unary_union([current[ids[int(i)]].intersection(window)for i in sorted(tree.query(window,predicate='intersects'))])
   pieces=surfaces(material.intersection(zone))
   bank_faces=[face(axis,plane,lo,hi)for plane in (left,right)]
   # A connected bridge between both walls remains a failed slot. Only
   # existing copper that leaves the walls separated can become a witness.
   if any(all(piece.intersects(edge)for edge in bank_faces)for piece in pieces):continue
   copper=to_wkb(unary_union(pieces)).hex()
   walls=[]
   for bank,plane in enumerate((left,right)):
    clipped=material.boundary.intersection(corridor(axis,plane-margin,plane+margin,lo,hi))
    other=1-axis
    contour=unary_union([LineString([a,b])for line in lines(clipped)
                         for a,b in zip(line.coords,list(line.coords)[1:])
                         if abs(a[other]-b[other])>EPS])
    walls.append(dict(bank=bank,contour_wkb_hex=to_wkb(contour).hex(),
                      retained_material_wkb_hex=copper if bank==0 else empty,
                      supports=intruders))
   occupied[slot_key(group,slot)]=dict(copper=copper,walls=walls,source_ids=intruders)
   holds[gid]='FIXED_STAGE_ENTRY_COPPER_IN_SOURCE_SLOT'
 return occupied,holds

def measure_entry_spans(spec,current):
 """Keep source group identity and cut each measuring span around accepted copper."""
 material=list(current.values());tree=STRtree(material)
 measured=[]
 for group in spec['groups']:
  axis=group['axis'];other=1-axis;slots=[]
  entry=list(zone_rows(spec,group,group['left'],group['right'],current))
  for original_slot,row in zip(group['slots'],entry):
   lo,hi=row['lo'],row['hi'];left,right=row['left'],row['right']
   zone=corridor(axis,left,right,lo,hi)
   occupied=[]
   for i in tree.query(zone,predicate='intersects'):
    for piece in surfaces(material[int(i)].intersection(zone)):
     if piece.area>EPS:occupied.append((piece.bounds[other],piece.bounds[other+2]))
   start=lo
   for a,b in sorted(occupied)+[(hi,hi)]:
    if a-start>EPS:
     slots.append(dict(original_slot,lo=start,hi=a,entry_left=left,entry_right=right))
    start=max(start,b)
  if slots:measured.append(dict(group,slots=slots))
 return measured

def records(scene,original,current,*,from_stage_entry=None):
 index=original_index(scene,original);source=index.geometries
 if from_stage_entry is None:
  from_stage_entry=any(row['stage']=='t04'for row in scene.get('lineage',()))
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
   group=dict(axis=axis,left=left,right=right,original_gap_mm=right-left,shared_source_components=[sorted(v)for v in common],banks=[sorted(b)for b in banks],fixed_wall_anchors=anchors,slots=[dict(lo=s['lo'],hi=s['hi'],bank_members=[sorted({w['source_id']for w in s['witnesses']if w['bank']==bank})for bank in (0,1)])for s in run])
   group['group_id']=hashlib.sha256(canonical(group)).hexdigest();groups.append(group)
 # T04 does not own these rectangles. A changed T02 member is not a shifted
 # fixed trace wall and must never be adopted as the new source baseline.
 for group in groups:
  for bank in group['banks']:
   if any(s not in current or not current[s].equals(source[s])for s in bank):raise ValueError('SHARED_GAP_STAGE_ENTRY_INTRUSION:T02_MEMBER_CHANGED:'+group['group_id'])
 spec=dict(policy=policy(),source_sha256=scene['source_sha256'],groups=groups,entry_walls=entry_walls(groups,source,current))
 if from_stage_entry:
  measured=measure_entry_spans(spec,current)
  spec.update(discovery_geometry='SOURCE_GROUPS_WITH_ACCEPTED_T04_OPENINGS',
              source_groups=groups,groups=measured,
              entry_walls=entry_walls(measured,source,current))
  return spec
 occupied,holds=fixed_entry_holds(spec,current)
 if holds:spec.update(fixed_entry_holds=holds,occupied_entry_slots=occupied)
 return spec

def project(spec,original,current,proposed,*,factor_rows=None):
 """Intersect bank equalities by union-find; no search, offset compounding or additions."""
 # Other rectangles can approach a shared slot from its ends. Bound those
 # whole centered proposals too, before solving bank equalities. Protected
 # coordinated slots are subsets of these source corridors, so the reductions
 # remain safe after projection and require no iterative geometry search.
 proposed=dict(proposed);factor_rows={s:list(factor_rows[s])if factor_rows is not None else[(g.bounds[a+2]-g.bounds[a])/(current[s].bounds[a+2]-current[s].bounds[a])for a in (0,1)]for s,g in proposed.items()};guards=[]
 held=spec.get('fixed_entry_holds',{})
 for group in spec['groups']:
  if group['group_id'] in held:
   for sid in {s for bank in group['banks']for s in bank}&proposed.keys():
    factor_rows[sid][group['axis']]=1.
    core=current[sid]
    proposed[sid]=core if factor_rows[sid]==[1.,1.]else scale(core,*factor_rows[sid],origin=core.centroid)
 for sid,g in sorted(proposed.items()):
  core=current[sid]
  for group in spec['groups']:
   if any(sid in bank for bank in group['banks']):continue
   for slot in group['slots']:
    zone=corridor(group['axis'],slot.get('entry_left',group['left']),slot.get('entry_right',group['right']),slot['lo'],slot['hi'])
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
 parents={};weights={};anchors=defaultdict(list)
 def find(x):
  parents.setdefault(x,x);weights.setdefault(x,0.)
  if parents[x]!=x:
   old=parents[x];parents[x]=find(old);weights[x]+=weights[old]
  return parents[x]
 def join(a,b,difference=0.):
  ra,rb=find(a),find(b);wa,wb=weights[a],weights[b]
  if ra==rb:
   if abs(wa-wb-difference)>EPS:raise ValueError('SHARED_GAP_OFFSET_CONSTRAINT_INCONSISTENT')
  elif ra<rb:parents[rb]=ra;weights[rb]=wa-wb-difference
  else:parents[ra]=rb;weights[ra]=difference-wa+wb
 for group in spec['groups']:
  if group['group_id'] in held:continue
  axis=group['axis']
  curved=any(w.get('maximum_intrusion_mm',0.)>0 for w in spec['entry_walls']if w['group_id']==group['group_id'])
  for bank,ids in enumerate(group['banks']):
   variables=[(sid,axis)for sid in ids]
   for var in variables:find(var)
   if curved and variables:
    # Equal nearest spacing against an inherited curved wall requires unequal
    # optional pad offsets. Weighted equalities solve these once, without
    # search, clipping, added growth, or changing the preceding trace.
    constraints=[]
    for slot in group['slots']:
     members=slot['bank_members'][bank]
     if not members:continue
     walls=[w for w in spec['entry_walls']if w['group_id']==group['group_id']and w['bank']==1-bank and w['lo']==slot['lo']and w['hi']==slot['hi']]
     if len(walls)!=1:raise ValueError('SHARED_GAP_CURVED_OPPOSITE_WALL_REQUIRED')
     wall=walls[0];fixed=wall['offset_mm']+wall.get('maximum_intrusion_mm',0.)
     constraints.extend(((sid,axis),fixed)for sid in members)
    if not constraints:raise ValueError('SHARED_GAP_CURVED_MEMBER_COVERAGE_CHANGED')
    first,base=constraints[0]
    for var,fixed in constraints[1:]:join(first,var,fixed-base)
   else:
    for var in variables[1:]:join(variables[0],var)
   anchor=bank_anchor(spec,group,bank)
   if anchor is not None:
    for var in variables:anchors[var].append(anchor)
 components=defaultdict(list)
 for var in parents:components[find(var)].append(var)
 offsets={};ledger=[]
 for root,variables in sorted(components.items()):
  offered=[]
  for sid,axis in sorted(variables):
   core=current[sid];delta=(factor_rows[sid][axis]-1)*(core.bounds[axis+2]-core.bounds[axis])/2 if sid in proposed else 0.
   if delta<-EPS:raise ValueError('SHARED_GAP_PROJECTION_REMOVES_ENTRY')
   offered.append(max(0.,delta))
  potentials=[weights[v]for v in sorted(variables)]
  upper=min(o-p for o,p in zip(offered,potentials));lower=max(-p for p in potentials)
  required=[value-weights[v]for v in variables for value in anchors[v]]
  if required and min(required)>upper+EPS:raise ValueError('SHARED_GAP_FIXED_ANCHOR_INFEASIBLE')
  value=min(required)if required else upper
  if value<lower-EPS:raise ValueError('SHARED_GAP_OFFSET_COMPENSATION_INFEASIBLE')
  for var in variables:offsets[var]=max(0.,value+weights[var])
  ledger.append(dict(variables=[list(v)for v in sorted(variables)],offered_offsets_mm=offered,common_offset_mm=value,fixed_wall_anchor=bool(required),fixed_anchor_offsets_mm=required))
  if any(p!=0 for p in potentials):ledger[-1]['relative_offsets_mm']=potentials
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
  if group['group_id'] in held:
   zones.extend(zone_rows(spec,group,group['left'],group['right'],current));continue
  axis=group['axis'];bank_offsets=[min([offsets[(sid,axis)]for sid in ids],default=bank_anchor(spec,group,bank)or 0.)for bank,ids in enumerate(group['banks'])];left=group['left']+bank_offsets[0];right=group['right']-bank_offsets[1]
  if right-left<=0:raise ValueError('SHARED_GAP_COLLAPSED')
  zones.extend(zone_rows(spec,group,left,right,dict(current,**result)))
 match=matching(spec,zones)
 if not match['passed']:raise ValueError('SHARED_GAP_MATCHING_TOLERANCE_EXCEEDED:'+canonical(match).decode())
 proof=dict(policy=spec['policy'],source_sha256=spec['source_sha256'],banks=ledger,zones=zones,factors=result_factors,approaching_proposal_limits=guards)
 if 'discovery_geometry' in spec:
  proof['discovery_geometry']=spec['discovery_geometry']
  proof['source_group_ids']=[g['group_id']for g in spec['source_groups']]
 if held:proof['fixed_entry_holds']=held
 return result,proof

def check(proof,material,*,tolerance_mm=0.):
 checks=[]
 for row in proof['zones']:
  zone=corridor(row['axis'],row['left'],row['right'],row['lo'],row['hi']);inner=zone.buffer(-tolerance_mm,join_style=2)if tolerance_mm else zone
  retained=unary_union([from_wkb(bytes.fromhex(w['retained_material_wkb_hex']))for w in row['entry_walls']])
  intrusion=material.intersection(inner).difference(retained).area
  checks.append(dict(group_id=row['group_id'],gap_mm=row['gap_mm'],intrusion_mm2=intrusion,retained_entry_material_mm2=retained.area,passed=intrusion<=EPS))
 match=matching(proof,proof['zones'])
 return dict(passed=all(q['passed']for q in checks)and match['passed'],checks=checks,gap_matching=match,tolerance_mm=tolerance_mm,scope='Complete source-qualified spans and exact inherited contours; minimum axis gaps compared between slots; same-net and fill allowances do not override')

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
   anchor=bank_anchor(spec,group,bank)
   if anchor is not None:values.append(anchor)
   offsets.append(min(values,default=0.))
  left,right=group['left']+offsets[0],group['right']-offsets[1]
  if right<=left:raise ValueError('SHARED_GAP_COLLAPSED')
  zones.extend(zone_rows(spec,group,left,right,current))
 match=matching(spec,zones)
 if not match['passed']:raise ValueError('SHARED_GAP_MATCHING_TOLERANCE_EXCEEDED:'+canonical(match).decode())
 return dict(policy=spec['policy'],source_sha256=spec['source_sha256'],zones=zones)

def complete(proof,material,*,tolerance_mm=0.,native_endpoint_rounding=False):
 q=check(proof,material,tolerance_mm=tolerance_mm);edges=[];boundary=interval_edges(material);epsilon=max(tolerance_mm,EPS);outline=material.boundary
 for row in proof['zones']:
  if 'fixed_entry_copper' in row:
   retained=from_wkb(bytes.fromhex(row['fixed_entry_copper']))
   nearby=material.intersection(retained.envelope.buffer(4*max(tolerance_mm,EPS),join_style=2))
   observed=nearby.buffer(tolerance_mm) if tolerance_mm else nearby
   if retained.difference(observed).area>EPS:raise ValueError('T02_FIXED_STAGE_ENTRY_COPPER_REMOVED')
  for bank,plane in enumerate((row['left'],row['right'])):
   inherited=[w for w in row['entry_walls']if w['bank']==bank]
   if inherited:
    wall=inherited[0];expected=from_wkb(bytes.fromhex(wall['contour_wkb_hex']))
    # Retain the full preceding contour, not just its nominal straight plane.
    # This exact model test uses only the existing arithmetic epsilon; actual
    # Gerber fidelity uses the separately supplied existing native tolerance.
    missing=expected.difference(outline).length
    if missing>EPS:
     bounds=expected.bounds;axis=row['axis'];observed=outline.intersection(corridor(axis,bounds[axis]-epsilon,bounds[axis+2]+epsilon,row['lo'],row['hi']))
     # Check the whole expected linework, including a missing middle segment.
     # A vertex-only Hausdorff test could miss such a gap between its endpoints.
     # Buffer only this small local wall, never the whole-board boundary.
     if not observed.is_empty:missing=expected.difference(observed.buffer(epsilon,quad_segs=1,cap_style=2,join_style=2)).length
    edges.append(dict(group_id=row['group_id'],missing_boundary_mm=missing,passed=missing<=EPS,basis='EXACT_QUALIFIED_ENTRY_CONTOUR',entry_supports=wall['supports']))
    continue
   # Compare straight boundary intervals directly: no nearly-zero GEOS buffers,
   # and no repeated whole-board offsets. Existing numerical tolerance only.
   axis,lo,hi=row['axis'],row['lo'],row['hi']
   intervals=[(max(lo,e['lo']),min(hi,e['hi']),abs(e['plane']-plane)) for e in boundary
              if e['axis']==axis and abs(e['plane']-plane)<=epsilon and min(hi,e['hi'])>max(lo,e['lo'])]
   if native_endpoint_rounding and intervals:
    # Only the outermost observed endpoints may move within file fidelity.
    # Interior interruptions remain visible, even near the ends of the span.
    first=min(intervals,key=lambda edge:(edge[0],edge[2]))
    last=max(intervals,key=lambda edge:(edge[1],-edge[2]))
    if math.hypot(first[0]-lo,first[2])<=tolerance_mm:
     intervals.append((lo,first[0],0.))
    if math.hypot(hi-last[1],last[2])<=tolerance_mm:
     intervals.append((last[1],hi,0.))
   missing=missing_length([(a,b)for a,b,_ in intervals],lo,hi)
   edges.append(dict(group_id=row['group_id'],missing_boundary_mm=missing,passed=missing<=EPS))
 q.update(boundaries=edges,passed=q['passed']and all(v['passed']for v in edges))
 if not q['passed']:
  # Preserve the exact failed predicates in the stopped worker's log. A failed
  # final guard must not discard the location after a costly full search.
  failed_slots=[dict(zone={k:v for k,v in row.items()if k!='entry_walls'},check=check)for row,check in zip(proof['zones'],q['checks'])if not check['passed']]
  failed_boundaries=[dict(group_id=e['group_id'],bank=i%2,lo=proof['zones'][i//2]['lo'],hi=proof['zones'][i//2]['hi'],missing_boundary_mm=e['missing_boundary_mm'],basis=e.get('basis','COMPLETE_STRAIGHT_FACE'))for i,e in enumerate(edges)if not e['passed']]
  raise ValueError('T02_SHARED_NEIGHBOR_UNIFORMITY_FAILED:'+canonical(dict(failed_slots=failed_slots,failed_boundaries=failed_boundaries)).decode())
 return q

def restore(store,scene,*,project_parts=False):
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
  from_entry=spec.get('discovery_geometry')=='SOURCE_GROUPS_WITH_ACCEPTED_T04_OPENINGS'
  if records(before_scene,original,before,from_stage_entry=from_entry)!=spec:raise ValueError('SHARED_GAP_RESTORED_SOURCE_CHANGED')
  if 'shared_gap_state_ref'not in entry:raise ValueError('SHARED_GAP_FROZEN_STATE_MISSING')
  state=store.get_json(entry['shared_gap_state_ref'],kind='shared-gap-state')
  if state.get('source_sha256')!=scene['source_sha256']or state.get('policy')!=policy()or state.get('discovery_geometry')!=spec.get('discovery_geometry'):raise ValueError('SHARED_GAP_FROZEN_STATE_CHANGED')
  if from_entry and state.get('source_group_ids')!=[g['group_id']for g in spec['source_groups']]:raise ValueError('SHARED_GAP_FROZEN_SOURCE_GROUP_CHANGED')
  expected={(g['group_id'],s['lo'],s['hi'])for g in spec['groups']for s in g['slots']}
  actual={(s['group_id'],s['lo'],s['hi'])for s in state['zones']}
  if expected!=actual or len(state['zones'])!=len(expected):raise ValueError('SHARED_GAP_FROZEN_COVERAGE_CHANGED')
  held=spec.get('fixed_entry_holds',{})
  expected_holds=[row for g in spec['groups']if g['group_id'] in held
                  for row in zone_rows(spec,g,g['left'],g['right'],before)]
  if state.get('fixed_entry_holds',{})!=held or [r for r in state['zones']if r.get('held_for_fixed_entry')]!=expected_holds:
   raise ValueError('SHARED_GAP_FROZEN_ENTRY_HOLD_CHANGED')
  ACTIVE=state
  if project_parts:
   from src.shared_gap_projection import complete_parts
   complete_parts(ACTIVE,now.values())
  else:
   complete(ACTIVE,unary_union(list(now.values())))

def remedy(logical,predecessor):
 if ACTIVE is None:return None
 return check(ACTIVE,logical.difference(predecessor))
