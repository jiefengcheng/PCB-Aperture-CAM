"""Source-bound local pin separation, independent of global copper ownership.

Ordinary growth is checked against the complete local branch surfaces. Remedies
are checked as complete logical proposals before clipping, smoothing or splitting.
Rejected proposals remain a shared exclusion across later stages and radii.
"""
from dataclasses import dataclass
from collections import OrderedDict
from shapely import STRtree,from_wkb,to_wkb,union_all
from shapely.geometry import Polygon
from src.component_voids import surface_parts
from src.indexed_polygon_distance import distance
from src.stage_abi.store import canonical,digest

ACTIVE=None
SCHEMA='source-bound-local-pin-separation/1'

def joined(items):return union_all(items)if items else Polygon()

@dataclass(frozen=True)
class Slot:
 source_sha256:str
 slot_id:str
 pin_ids:tuple
 domain:object
 source:object
 seeds:tuple
 attachments:tuple=()
 protected_void:object=None
 spacing_domain:object=None

 def __post_init__(self):
  if len(self.pin_ids)!=2 or len(set(self.pin_ids))!=2 or len(self.seeds)!=2:raise ValueError('PIN_SLOT_TWO_ORIGINAL_BRANCHES_REQUIRED')
  if self.domain.is_empty or not self.domain.is_valid or self.domain.geom_type!='Polygon':raise ValueError('PIN_SLOT_VALID_COMPLETE_DOMAIN_REQUIRED')
  pieces=surface_parts(self.source.intersection(self.domain));hits=[[i for i,g in enumerate(pieces)if g.intersection(seed).area>0]for seed in self.seeds]
  if any(len(h)!=1 for h in hits)or hits[0]==hits[1]:raise ValueError('PIN_SLOT_SOURCE_BRANCHES_NOT_LOCALLY_DISTINCT')
  object.__setattr__(self,'spacing',self.domain if self.spacing_domain is None else self.spacing_domain)
  if not self.domain.covers(self.spacing):raise ValueError('PIN_SPACING_DOMAIN_OUTSIDE_COMPLETE_TRANSITION')
  object.__setattr__(self,'source_parts',pieces);object.__setattr__(self,'source_hits',tuple(h[0]for h in hits))
  object.__setattr__(self,'void',self.domain.difference(self.source)if self.protected_void is None else self.protected_void)
  if self.void.intersection(self.source).area>1e-12:raise ValueError('PIN_PROTECTED_SLOT_MUST_BE_ORIGINAL_EMPTY_SPACE')
  object.__setattr__(self,'binding',digest(canonical(dict(schema=SCHEMA,source_sha256=self.source_sha256,slot_id=self.slot_id,pin_ids=list(self.pin_ids),domain_sha256=digest(to_wkb(self.domain)),source_sha=digest(to_wkb(self.source)),seed_sha256=[digest(to_wkb(g))for g in self.seeds],attachments=list(self.attachments),protected_void_sha256=digest(to_wkb(self.void)),spacing_domain_sha256=digest(to_wkb(self.spacing))))))

 def check(self,material,gap,predecessor=None):
  # The complete domain reaches the original common attachment boundary.
  # The original narrowing into that attachment is retained, never a licence
  # for new copper to bridge or narrow an already close transition.
  local=material.intersection(self.domain);pieces=surface_parts(local);hits=[[i for i,g in enumerate(pieces)if g.intersection(seed).area>0]for seed in self.seeds];failures=[];measured=None;full_gap=None
  if any(len(h)!=1 for h in hits):failures.append('PIN_BRANCH_MISSING_OR_SPLIT')
  elif hits[0]==hits[1]:failures.append('PIN_BRANCH_LOCAL_BRIDGE')
  else:
   branches=[pieces[h[0]]for h in hits];full_gap=distance(*branches)
   spacing_branches=[g.intersection(self.spacing)for g in branches]
   if any(g.is_empty for g in spacing_branches):failures.append('PIN_SPACING_BRANCH_MISSING')
   else:
    measured=distance(*spacing_branches)
    if predecessor is None and measured+1e-12<gap:failures.append('PIN_BRANCH_SPACING')
   reference=self.source if predecessor is None else predecessor
   oldpieces=surface_parts(reference.intersection(self.domain));oldhits=[[i for i,g in enumerate(oldpieces)if g.intersection(seed).area>0]for seed in self.seeds]
   if any(len(h)!=1 for h in oldhits)or oldhits[0]==oldhits[1]:failures.append('PIN_RETAINED_PREDECESSOR_BRIDGED')
   else:
    for side in (0,1):
     delta=branches[side].difference(oldpieces[oldhits[side][0]])
     if delta.area>0:
      # Independent Boolean assembly can produce source-boundary slivers a
      # few ulps wide. Use the existing 1e-12mm comparison epsilon to classify
      # that reconstruction noise, without changing material or spacing gates.
      # Branch connectivity was checked above and never receives this exclusion.
      checked=delta.difference(oldpieces[oldhits[side][0]].buffer(1e-12,quad_segs=16))
      if not checked.is_empty and distance(checked,branches[1-side])+1e-12<gap:failures.append('PIN_NEW_GROWTH_SPACING')
  original=self.source.intersection(self.domain)
  if original.difference(local).area>1e-12:failures.append('PIN_SOURCE_COPPER_REMOVED')
  for g in pieces:
   if not any(g.intersection(old).area>0 for old in self.source_parts):failures.append('PIN_SLOT_NEW_UNBOUND_COPPER')
  return dict(slot_id=self.slot_id,pin_source_ids=list(self.pin_ids),passed=not failures,failures=sorted(set(failures)),gap_mm=measured,complete_transition_minimum_gap_mm=full_gap,required_gap_mm=gap,domain_sha256=digest(to_wkb(self.domain)),spacing_domain_sha256=digest(to_wkb(self.spacing)),scope='Complete finger and transition surfaces; unchanged original common-attachment taper retained; every new copper delta checked across the complete transition',same_net_or_owner_exemption=False)

class Rule:
 def __init__(self,slots,*,construction_gap,finished_gap,state=None):
  self.slots=tuple(slots);self.construction_gap=construction_gap;self.finished_gap=finished_gap
  if not self.slots or construction_gap<finished_gap or finished_gap<=0:raise ValueError('PIN_SEPARATION_BOUND_SPACING_REQUIRED')
  if len({s.source_sha256 for s in self.slots})!=1 or len({s.slot_id for s in self.slots})!=len(self.slots):raise ValueError('PIN_SEPARATION_SOURCE_OR_SLOT_IDENTITY_CHANGED')
  self.source_sha256=self.slots[0].source_sha256;self.binding=digest(canonical([s.binding for s in self.slots]));self.tree=STRtree([s.domain for s in self.slots]);self.remedy_tree=STRtree([s.void for s in self.slots]);self.rejected=Polygon();self.rejected_count=0;self.prior_local={};self.prior_binding=None
  for slot in self.slots:
   if not slot.check(slot.source,finished_gap)['passed']:raise ValueError('PIN_SOURCE_SPACING_NOT_ESTABLISHED:'+slot.slot_id)
  if state is not None:
   if state['binding']!=self.binding:raise ValueError('PIN_REJECTION_STATE_SOURCE_CHANGED')
   self.rejected=state['rejected_geometry'];self.rejected_count=state['rejected_count']

 def check(self,material,*,finished=False,indices=None):
  ids=range(len(self.slots))if indices is None else sorted(indices);checks=[self.slots[i].check(material,self.finished_gap if finished else self.construction_gap)for i in ids]
  return dict(schema=SCHEMA,passed=all(r['passed']for r in checks),checks=checks,source_binding=self.binding,source_sha256=self.source_sha256,same_net_or_owner_exemption=False)

 def check_parts(self,material,*,finished=False):
  # Streaming local projection does not hold a second full-board union or
  # defeat the existing disk-backed T05 owner-surface snapshot budget.
  buckets={i:[]for i in range(len(self.slots))}
  for g in material:
   for i in map(int,self.tree.query(g.envelope)):
    local=g.intersection(self.slots[i].domain)
    if not local.is_empty:buckets[i].append(local)
  checks=[self.slots[i].check(joined(buckets[i]),self.finished_gap if finished else self.construction_gap)for i in range(len(self.slots))]
  return dict(schema=SCHEMA,passed=all(r['passed']for r in checks),checks=checks,source_binding=self.binding,source_sha256=self.source_sha256,same_net_or_owner_exemption=False)

 def reserve(self,material,generated_sha256):
  buckets=self._project(material);checks=[self.slots[i].check(buckets[i],self.finished_gap)for i in range(len(self.slots))]
  if not all(r['passed']for r in checks):raise ValueError('PIN_SEPARATION_RETAINED_PRIOR_FAILED:'+str([r for r in checks if not r['passed']]))
  self.prior_local=buckets;self.prior_binding=digest(canonical(dict(generated_sha256=generated_sha256,local_geometry_sha256={str(i):digest(to_wkb(g))for i,g in buckets.items()})))
  return dict(passed=True,checks=checks,source_binding=self.binding,prior_binding=self.prior_binding)

 def _project(self,material):
  buckets={i:[]for i in range(len(self.slots))}
  for g in material:
   for i in map(int,self.tree.query(g.envelope)):
    local=g.intersection(self.slots[i].domain)
    if not local.is_empty:buckets[i].append(local)
  return {i:joined(parts)for i,parts in buckets.items()}

 def growth_parts(self,before,after):
  old=self._project(before);new=self._project(after);checks=[]
  for i,slot in enumerate(self.slots):
   prior=self.prior_local.get(i,Polygon());predecessor=joined([old[i],prior]);candidate=joined([new[i],prior])
   baseline=slot.check(predecessor,self.finished_gap)
   if not baseline['passed']:raise ValueError('PIN_SEPARATION_COMBINED_PRIOR_FAILED:'+str(baseline))
   checks.append(slot.check(candidate,self.construction_gap,predecessor=predecessor))
  return dict(schema=SCHEMA,passed=all(r['passed']for r in checks),checks=checks,source_binding=self.binding,prior_binding=self.prior_binding)

 def require(self,material,*,finished=True,scope='current'):
  proof=self.check(material,finished=finished)
  if not proof['passed']:raise ValueError('PIN_SEPARATION_'+scope.upper()+'_FAILED:'+str([r for r in proof['checks']if not r['passed']][:3]))
  return proof

 def remedy(self,logical,predecessor,*,record=True):
  # The complete raw logical proposal must arrive here before any foreign mask,
  # partial-rim fallback, output partition, or representation-only absorption.
  delta=logical.difference(predecessor);violations=[]
  for i in sorted(map(int,self.remedy_tree.query(logical))):
   slot=self.slots[i]
   if delta.intersection(slot.void).area>0:violations.append(dict(slot_id=slot.slot_id,reason='PROTECTED_PIN_SLOT'))
  sticky=not self.rejected.is_empty and delta.intersection(self.rejected).area>0
  if sticky:violations.append(dict(reason='PREVIOUSLY_REJECTED_LOGICAL_FILL_FRAGMENT'))
  accepted=not violations
  if not accepted and record:
   self.rejected=joined([self.rejected,delta]);self.rejected_count+=1
  return dict(passed=accepted,status='ELIGIBLE_FOR_EXISTING_CHECKS'if accepted else'REJECT_ENTIRE_LOGICAL_FILL',reasons=violations,logical_fill_sha256=digest(to_wkb(logical)),logical_fill_area_mm2=logical.area,fragments_accepted=False,rejection_state_sha256=digest(to_wkb(self.rejected)))

 def state(self,store):
  return dict(schema=SCHEMA,binding=self.binding,rejected_count=self.rejected_count,rejected_ref=store.put('geometry',to_wkb(self.rejected)))

 def restore(self,store,state):
  if state['schema']!=SCHEMA or state['binding']!=self.binding:raise ValueError('PIN_REJECTION_STATE_SOURCE_CHANGED')
  self.rejected=from_wkb(store.get(state['rejected_ref'],kind='geometry'));self.rejected_count=state['rejected_count']

class Prepared:
 """Only changed domain dependencies are recomputed; all slots remain covered."""
 def __init__(self,parent,rule):
  self.parent=parent;self.rule=rule;self.binding=(rule.binding,rule.prior_binding);self.ids=sorted(parent.original);self.tree=STRtree([parent.original[s]for s in self.ids]);self.cache=OrderedDict();self.weight=0;self.limit=32*1024**2
  self.local_ids={i:[self.ids[int(j)]for j in self.tree.query(slot.domain)]for i,slot in enumerate(rule.slots)};self.baseline={};self.baseline_material={}
  for i,slot in enumerate(rule.slots):
   material=joined([*[parent.original[s].intersection(slot.domain)for s in self.local_ids[i]],rule.prior_local.get(i,Polygon())]);proof=slot.check(material,rule.finished_gap)
   if not proof['passed']:raise ValueError('PIN_SEPARATION_RETAINED_PREDECESSOR_FAILED:'+str(proof))
   self.baseline[i]=proof;self.baseline_material[i]=material

 def check(self,rows,*,materialize_scene=False):
  if ACTIVE is not self.rule or self.binding!=(self.rule.binding,self.rule.prior_binding):raise ValueError('PIN_SEPARATION_CONTEXT_CHANGED')
  proposed={r['id']:r['candidate']for r in rows};changed={s:g for s,g in proposed.items()if to_wkb(g)!=to_wkb(self.parent.original[s])};affected=set()
  for sid,g in changed.items():
   affected.update(map(int,self.rule.tree.query(g.envelope.union(self.parent.original[sid].envelope))))
  if materialize_scene:affected=set(range(len(self.rule.slots)))
  proofs=dict(self.baseline)
  for i in sorted(affected):
   slot=self.rule.slots[i];ids=sorted(set(self.local_ids[i])|{s for s,g in changed.items()if g.intersects(slot.domain)});key=(i,tuple((s,digest(to_wkb(proposed.get(s,self.parent.original[s]))))for s in ids))
   if key in self.cache:proof=self.cache[key][0];self.cache.move_to_end(key)
   else:
    material=joined([*[proposed.get(s,self.parent.original[s]).intersection(slot.domain)for s in ids],self.rule.prior_local.get(i,Polygon())]);proof=slot.check(material,self.rule.construction_gap,predecessor=self.baseline_material[i]);size=len(canonical(proof))+len(canonical([key[0],[[s,h]for s,h in key[1]]]))+256
    if size<=self.limit:
     while self.cache and(self.weight+size>self.limit or len(self.cache)>=4096):self.weight-=self.cache.popitem(last=False)[1][1]
     self.cache[key]=(proof,size);self.weight+=size
   proofs[i]=proof
  return dict(schema=SCHEMA,passed=all(v['passed']for v in proofs.values()),checks=[proofs[i]for i in sorted(proofs)],complete_protected_slot_coverage=True,checked_slots=len(proofs),reevaluated_slots=len(affected),source_binding=self.rule.binding,prior_binding=self.rule.prior_binding)

def remedy(logical,predecessor):
 return None if ACTIVE is None else ACTIVE.remedy(logical,predecessor)

def require(material,*,finished=True,scope='current'):
 return None if ACTIVE is None else ACTIVE.require(material,finished=finished,scope=scope)

def require_remedy(logical,predecessor,*,scope='encoded_remedy'):
 if ACTIVE is None:return None
 proof=ACTIVE.remedy(logical,predecessor,record=False)
 if not proof['passed']:raise ValueError('PIN_SEPARATION_'+scope.upper()+'_FAILED:'+str(proof))
 return proof


def encoded_remedy(logical,encoded,predecessor):
 """Reject the whole logical proposal if its complete native parent intrudes."""
 if ACTIVE is None:return None
 proof=ACTIVE.remedy(encoded,predecessor)
 if not proof['passed']:
  ACTIVE.rejected=joined([ACTIVE.rejected,logical.difference(predecessor)])
  proof=dict(proof,logical_fill_sha256=digest(to_wkb(logical)),native_parent_sha256=digest(to_wkb(encoded)),rejection_state_sha256=digest(to_wkb(ACTIVE.rejected)))
 return proof

def native_parent(reference,*,grid_mm):
 """Drop transient precision metadata only in the declared pin source profile.

Undeclared-source construction retains its prior operand and choice sequence.
The pin profile needs coordinate-identical material without GEOS grid tags so
source arcs cannot be snapped while unioning a new grid parent.
 """
 if ACTIVE is None:return reference
 from src.gerber_u05.native_assembly import canonical_parent
 return canonical_parent(reference,grid_mm=grid_mm)
