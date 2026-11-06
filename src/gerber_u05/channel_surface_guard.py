"""Additional channel constraints after the unchanged canonical source guard."""
import hashlib
from shapely import to_wkb
from shapely.ops import unary_union
from src.t01_canonical_surface import SurfaceGuard
from src.crop_square_neighbor_experiment import retain_attached
from src import source_channel_scope

class ChannelSurfaceGuard(SurfaceGuard):
 def limit(self,site,proposal,scene,*,priority=False,record=True,overrides=None):
  functional=source_channel_scope.ACTIVE
  if functional is None:
   candidate=super().limit(site,proposal,scene,priority=priority,record=record,overrides=overrides)
   from src import pin_separation as pin
   if pin.ACTIVE is not None:
    material={r['id']:scene.shapes[i]for i,r in enumerate(self.rows)};material.update(overrides or {});proposed=dict(material);proposed[site['source_id']]=candidate
    if not pin.ACTIVE.growth_parts(material.values(),proposed.values())['passed']:candidate=site['core']
   return candidate
  # The canonical kernel and its pinned source hash remain unchanged. Run its
  # complete guard, then constrain optional copper by functional neighbours.
  canonical=super().limit(site,proposal,scene,priority=priority,record=False,overrides=overrides);sid=site['source_id'];core=site['core'];owner=functional.owner(sid,core);material={r['id']:scene.shapes[i]for i,r in enumerate(self.rows)}
  for source_id,shape in (overrides or {}).items():
   if source_id in material:material[source_id]=shape
  owned=functional.project(material);radius=self.contract.construction_gap_mm+self.reserve;window=proposal.buffer(radius).envelope;foreign={}
  for other,shape in owned.items():
   if other==owner:continue
   from .checking_envelopes import constraint
   shape=constraint(functional,other,shape)
   if shape.intersects(window):foreign[other]=shape
  forbidden=unary_union([g.buffer(radius,quad_segs=128)for g in foreign.values()]);optional=canonical.difference(core).difference(forbidden);candidate,_=retain_attached(optional,core,scene.settings.kernel());candidate=unary_union([candidate,core.buffer(1e-10,quad_segs=128)])
  # Recheck the final, potentially clipped shape through the same canonical
  # surface predicate; priority is measured against the original round target.
  candidate=super().limit(site,candidate,scene,priority=False,record=False,overrides=overrides);held=[]
  if priority and candidate.symmetric_difference(proposal).area>scene.settings.area_epsilon:held.append('COMPLETE_ROUND_REQUIRED')
  if not candidate.covers(core):held.append('EXACT_CORE_CONTAINMENT')
  added=candidate.difference(owned[owner])
  if any(not added.is_empty and added.distance(g)+self.contract.comparison_epsilon_mm<self.contract.construction_gap_mm for g in foreign.values()):held.append('FUNCTIONAL_SOURCE_CHANNEL_CLEARANCE')
  if held or candidate.difference(core).area<=scene.settings.area_epsilon:candidate=core
  from src import pin_separation as pin
  if pin.ACTIVE is not None:
   proposed=dict(material);proposed[sid]=candidate
   proof=pin.ACTIVE.growth_parts(material.values(),proposed.values())
   if not proof['passed']:held.append('PROTECTED_PIN_SEPARATION_GROWTH');candidate=core
  if record:self.records.append(dict(source_id=sid,proposal_sha256=hashlib.sha256(to_wkb(proposal)).hexdigest(),candidate_sha256=hashlib.sha256(to_wkb(candidate)).hexdigest(),removed_optional_area_mm2=proposal.difference(candidate).area,held_reasons=held,construction_reserve_mm=self.reserve,functional_channel_id=owner,checked_foreign_functional_channels=sorted(foreign),unchanged_canonical_guard_candidate_sha256=hashlib.sha256(to_wkb(canonical)).hexdigest()))
  return candidate
