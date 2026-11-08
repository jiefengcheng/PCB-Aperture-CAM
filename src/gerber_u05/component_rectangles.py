"""Original-owner clearance for T02 inclusive rectangles; legacy mode unchanged."""
from pathlib import Path
import copy
from shapely.geometry import box
from shapely import to_wkb
from shapely.ops import unary_union
from src import component_clearance as cc
from src.u04_board.search import FastRectangleAdapter
from src.stage_abi.lands import merge_groups,exposure_eligible
from src.crop_stage_growth import check_proposal,GrowthContract
from src.component_voids import holes,joined
from src.indexed_polygon_distance import distance
from src.stage_abi.store import digest
from .checking_envelopes import constraint
from src import t02_shared_gaps as shared_gaps

class ComponentRectangleAdapter(FastRectangleAdapter):
 def verify(self,*args,**kwargs):
  self._replaying_merges=True
  try:return super().verify(*args,**kwargs)
  finally:self._replaying_merges=False
 def _merges(self,store,scene,plan,rows,current,budget):
  from src import pin_separation as pin
  rule=pin.ACTIVE
  if rule is None:return self._owner_merges(store,scene,plan,rows,current,budget)
  state=lambda r:(r.binding,r.prior_binding,to_wkb(r.rejected),r.rejected_count)
  if not getattr(self,'_replaying_merges',False):
   # The verifier must replay the same ordered fill proposals from their entry
   # state. Reusing the construction's final rejection memory adds a spurious
   # "previously rejected fragment" reason to the first rejected proposal.
   self._merge_pin_entry=copy.copy(rule)
   value=self._owner_merges(store,scene,plan,rows,current,budget)
   self._merge_pin_exit=state(rule)
   return value
  entry=getattr(self,'_merge_pin_entry',None)
  if entry is None or state(rule)!=self._merge_pin_exit:
   raise ValueError('T02_PIN_MERGE_REPLAY_CONTEXT_CHANGED')
  replay=copy.copy(entry);pin.ACTIVE=replay
  try:
   value=self._owner_merges(store,scene,plan,rows,current,budget)
   if state(replay)!=self._merge_pin_exit:raise ValueError('T02_PIN_MERGE_REJECTION_HISTORY_CHANGED')
   return value
  finally:
   # Construction's complete sticky rejection history remains authoritative
   # for subsequent fills, radii and stages. Verification never clears it.
   pin.ACTIVE=rule
 def describe(self):
  value=super().describe()
  if cc.ACTIVE is not None:value=dict(value,implementation=digest(Path(__file__).read_bytes()),ownership_policy=cc.POLICY)
  return value
 def _owner_merges(self,store,scene,plan,rows,current,budget):
  if cc.ACTIVE is None:return super()._merges(store,scene,plan,rows,current,budget)
  ctx=cc.ACTIVE;crop=box(*scene['viewport_mm']);ids=[s for s in plan['details']['targets']if not plan['details']['containment'][s]['contained']and exposure_eligible(plan['details'],s)];cores={s:ctx.originals[s]for s in ids};groups=merge_groups(ids,cores);before=unary_union([current[s]for s in sorted(current)]).intersection(crop);owned=ctx.project(current);claimed=set();accepted=[];decisions=[];additions=[];contract=GrowthContract()
  from src import source_channel_scope
  functional=source_channel_scope.ACTIVE;functional_owned=functional.project(current)if functional is not None else{}
  for ordinal,(axis,members)in enumerate(groups):
   channel=None;channel_ids=set();functional_pairs=[];functional_shortage=None
   budget.evaluation();rect=box(*unary_union([current[s]for s in members]).bounds);span=before.intersection(rect);shortage=rect.difference(span).area/rect.area;owners={ctx.owner(s)for s in members};delta=rect.difference(before);reasons=[];pairs=[]
   from src.growth_remedy_constraints import remedy as pin_remedy
   pin_check=pin_remedy(rect,before)
   shared_check=shared_gaps.fill_check(plan['details'],current,rect)
   if shared_check is not None and not shared_check['passed']:reasons.append('SHARED_NEIGHBOR_GAP_ENTIRE_FILL')
   if pin_check is not None and not pin_check['passed']:reasons.append('PROTECTED_PIN_SEPARATION_ENTIRE_FILL')
   if shortage>.20:reasons.append('SHORTAGE_ABOVE_20_PERCENT')
   if span.geom_type!='Polygon':reasons.append('SPAN_NOT_ONE_CONNECTED_SURFACE')
   if claimed.intersection(members):reasons.append('SOURCE_ALREADY_MERGED')
   if len(owners)!=1:
    reasons.append('MIXED_ORIGINAL_COPPER_OWNERS');q=dict(passed=False,failures=[dict(reason='MIXED_ORIGINAL_COPPER_OWNERS')],pairs=[])
   else:
    own=next(iter(owners));owner_span=owned[own].intersection(rect)
    if span.difference(owned[own]).area>0:reasons.append('FOREIGN_COMPONENT_IN_SPAN')
    original_void_core=ctx.cores[own]
    if functional is not None:
     channel_ids={functional.owner(s)for s in members}
     if len(channel_ids)!=1:reasons.append('MIXED_FUNCTIONAL_SOURCE_CHANNELS')
     else:
      channel=next(iter(channel_ids));original_void_core=functional.cores[channel];local_span=functional_owned[channel].intersection(rect);functional_shortage=rect.difference(local_span).area/rect.area
      if functional_shortage>.20:reasons.append('FUNCTIONAL_SHORTAGE_ABOVE_20_PERCENT')
      if local_span.geom_type!='Polygon':reasons.append('FUNCTIONAL_SPAN_NOT_ONE_CONNECTED_SURFACE')
      logical_delta=rect.difference(functional_owned[channel]);window=rect.buffer(contract.construction_gap_mm+contract.comparison_epsilon_mm).envelope
      for other,g in sorted(functional_owned.items()):
       if other==channel:continue
       g=constraint(functional,other,g)
       if logical_delta.is_empty or not g.intersects(window):continue
       measured=distance(logical_delta,g);passed=measured+contract.comparison_epsilon_mm>=contract.construction_gap_mm;functional_pairs.append(dict(foreign_source_channel_id=other,gap_mm=measured,passed=passed))
       if not passed:reasons.append('FUNCTIONAL_SOURCE_CHANNEL_CLEARANCE_FAILED')
    from src.hole_acceptance import required as holes_required
    if holes_required()and delta.intersection(joined(holes(original_void_core))).area>0:reasons.append('INHERITED_SOURCE_VOID')
    foreign={o:constraint(ctx,o,owned[o])for o in owned if o!=own}
    nearby=[dict(source_id='original-owner:'+o,original=ctx.cores[o],geometry=g,trace_width_mm=0.)for o,g in sorted(foreign.items())if g.intersects(rect.buffer(contract.construction_gap_mm+.001))]
    q=check_proposal(owner_span,rect,nearby,crop=crop,cap=rect,contract=contract)
    for other,g in sorted(foreign.items()):
     if delta.is_empty or not g.intersects(delta.buffer(contract.construction_gap_mm+contract.comparison_epsilon_mm).envelope):continue
     gap=distance(delta,g);passed=gap+contract.comparison_epsilon_mm>=contract.construction_gap_mm;pairs.append(dict(foreign_original_owner=other,gap_mm=gap,passed=passed))
     if not passed:reasons.append('FOREIGN_COMPONENT_CLEARANCE_FAILED')
    if any(oldown!=own and not old.difference(owner_span).is_empty and distance(delta,old.difference(owner_span))<contract.construction_gap_mm for oldown,old in accepted):reasons.append('PRIOR_MERGE_CLEARANCE_FAILED')
   if not q['passed']:reasons.append('FOREIGN_CLEARANCE_FAILED')
   if delta.area<=1e-12:reasons.append('NO_VISIBLE_ADDITION')
   record=dict(ordinal=ordinal,members=list(members),axis=axis,shortage=shortage,status='REJECTED'if reasons else'MERGED',reasons=reasons,check=q,original_component_owners=sorted(owners),foreign_component_pairs=pairs,ownership_policy=cc.POLICY)
   if pin_check is not None:record['pin_separation']=pin_check
   if shared_check is not None:record['shared_neighbor_gaps']=shared_check
   if functional is not None:record.update(functional_source_channel_ids=sorted(channel_ids),functional_shortage=functional_shortage,functional_channel_pairs=functional_pairs,source_void_basis='Frozen functional source channel; temporary frame excluded analytically')
   if not reasons:
    blob=to_wkb(rect);budget.output(blob);reference=store.put('geometry',blob);sid='t02-inclusive:'+reference['sha256'];md=dict(origin='t02-inclusive-fill',members=list(members),original_component_owner_id=own,original_source_sha256=ctx.source_hash,original_member_wkb_sha256={s:digest(to_wkb(ctx.originals[s]))for s in members})
    if functional is not None:md.update(original_channel_id=channel,original_channel_witness_sha256=digest(to_wkb(functional.cores[channel])))
    additions.append(dict(source_id=sid,kind='inclusive_rectangle',original_ref=reference,geometry_ref=reference,metadata=md));record['candidate_ref']=reference;accepted.append((own,rect));owned[own]=owned[own].union(rect);before=before.union(rect);claimed.update(members);ctx.assign(sid,rect,[own])
    if functional is not None:functional.assign(sid,None,[channel]);functional_owned[channel]=functional_owned[channel].union(rect)
   decisions.append(record)
  return decisions,additions
