"""Original-owner clearance for T02 inclusive rectangles; legacy mode unchanged."""
from pathlib import Path
from shapely.geometry import box
from shapely import to_wkb
from shapely.ops import unary_union
from src import component_clearance as cc
from src.u04_board.search import FastRectangleAdapter
from src.stage_abi.lands import merge_groups
from src.crop_stage_growth import check_proposal,GrowthContract
from src.component_voids import holes,joined
from src.indexed_polygon_distance import distance
from src.stage_abi.store import digest

class ComponentRectangleAdapter(FastRectangleAdapter):
 def describe(self):
  value=super().describe()
  if cc.ACTIVE is not None:value=dict(value,implementation=digest(Path(__file__).read_bytes()),ownership_policy=cc.POLICY)
  return value
 def _merges(self,store,scene,plan,rows,current,budget):
  if cc.ACTIVE is None:return super()._merges(store,scene,plan,rows,current,budget)
  ctx=cc.ACTIVE;crop=box(*scene['viewport_mm']);ids=[s for s in plan['details']['targets']if not plan['details']['containment'][s]['contained']];cores={s:ctx.originals[s]for s in ids};groups=merge_groups(ids,cores);before=unary_union([current[s]for s in sorted(current)]).intersection(crop);owned=ctx.project(current);claimed=set();accepted=[];decisions=[];additions=[];contract=GrowthContract()
  for ordinal,(axis,members)in enumerate(groups):
   budget.evaluation();rect=box(*unary_union([current[s]for s in members]).bounds);span=before.intersection(rect);shortage=rect.difference(span).area/rect.area;owners={ctx.owner(s)for s in members};delta=rect.difference(before);reasons=[];pairs=[]
   if shortage>.20:reasons.append('SHORTAGE_ABOVE_20_PERCENT')
   if span.geom_type!='Polygon':reasons.append('SPAN_NOT_ONE_CONNECTED_SURFACE')
   if claimed.intersection(members):reasons.append('SOURCE_ALREADY_MERGED')
   if len(owners)!=1:
    reasons.append('MIXED_ORIGINAL_COPPER_OWNERS');q=dict(passed=False,failures=[dict(reason='MIXED_ORIGINAL_COPPER_OWNERS')],pairs=[])
   else:
    own=next(iter(owners));owner_span=owned[own].intersection(rect)
    if span.difference(owned[own]).area>0:reasons.append('FOREIGN_COMPONENT_IN_SPAN')
    if delta.intersection(joined(holes(ctx.cores[own]))).area>0:reasons.append('INHERITED_SOURCE_VOID')
    foreign={o:owned[o].union(ctx.reserved[o])if o in ctx.reserved else owned[o]for o in owned if o!=own}
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
   if not reasons:
    blob=to_wkb(rect);budget.output(blob);reference=store.put('geometry',blob);sid='t02-inclusive:'+reference['sha256'];md=dict(origin='t02-inclusive-fill',members=list(members),original_component_owner_id=own,original_source_sha256=ctx.source_hash,original_member_wkb_sha256={s:digest(to_wkb(ctx.originals[s]))for s in members});additions.append(dict(source_id=sid,kind='inclusive_rectangle',original_ref=reference,geometry_ref=reference,metadata=md));record['candidate_ref']=reference;accepted.append((own,rect));owned[own]=owned[own].union(rect);before=before.union(rect);claimed.update(members);ctx.assign(sid,rect,[own])
   decisions.append(record)
  return decisions,additions
