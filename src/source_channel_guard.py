"""Source-bound channel checks with temporary common copper excluded analytically.

The frame remains actual source copper. Its remote connections cannot create a
clearance or merge exemption between distinct functional source channels.
"""
from shapely import to_wkb,from_wkb,STRtree
from src.original_copper_owners import OriginalOwners
from src.component_voids import surface_parts,joined
from src.component_distance import distance
from src.stage_abi.store import digest
from src.clearance_policy import HARD_GAP_MM
POLICY='EXCLUDE_TEMPORARY_FRAME_FROM_GROUPING_PRESERVE_ORIGINAL_GERBER'
ASSEMBLED_POLICY='INTEGRAL_CHANNELS_OF_CLIENT_ASSEMBLED_SOURCE/1'

class SourceChannels:
 def __init__(self,source,source_sha256,frame,certificate,*,store=None):
  if certificate.get('source_sha256')!=source_sha256 or certificate.get('frame_geometry_sha256')!=digest(to_wkb(frame)):raise ValueError('SOURCE_CHANNEL_FRAME_BINDING_CHANGED')
  integral=certificate.get('policy')==ASSEMBLED_POLICY
  if certificate.get('policy')not in(POLICY,ASSEMBLED_POLICY):raise ValueError('SOURCE_CHANNEL_FRAME_POLICY_REQUIRED')
  if integral and(not frame.is_empty or certificate.get('source_geometry_sha256')!=digest(to_wkb(source))):raise ValueError('ASSEMBLED_CHANNEL_SOURCE_BINDING_CHANGED')
  self.policy=certificate['policy']
  if source.is_empty or not source.is_valid or(not integral and(frame.is_empty or not frame.is_valid or frame.geom_type!='Polygon'or len(frame.interiors)!=1)):raise ValueError('SOURCE_CHANNEL_VALID_CLOSED_FRAME_REQUIRED')
  # This witness only recognizes the existing source frame. It grants no
  # file-fidelity or copper-change allowance to generated output.
  if not frame.difference(source.buffer(.000002,quad_segs=64)).is_empty:raise ValueError('SOURCE_CHANNEL_FRAME_OUTSIDE_SOURCE')
  self.source=source;self.frame=frame;self.source_sha256=source_sha256
  if 'analytic_source_ref'in certificate:
   if store is None:raise ValueError('VERIFIED_FUNCTIONAL_SOURCE_ARTIFACT_REQUIRED')
   body=store.get(certificate['analytic_source_ref'],kind='geometry')
   if digest(body)!=certificate['analytic_source_sha256']or certificate['source_geometry_sha256']!=digest(to_wkb(source)):raise ValueError('FUNCTIONAL_SOURCE_ASSEMBLY_BINDING_CHANGED')
   self.analytic_source=from_wkb(body)
  else:self.analytic_source=source if integral else joined(surface_parts(source.difference(frame)))
  self.index=OriginalOwners(self.analytic_source)
  if not integral and len(self.index.ids)<2:raise ValueError('SOURCE_FRAME_EXCLUSION_DOES_NOT_SEPARATE_CHANNELS')
  self.original=dict(zip(self.index.ids,self.index.owners))
 def check(self,actual,*,gap=HARD_GAP_MM):
  if gap!=HARD_GAP_MM:raise ValueError('SOURCE_CHANNEL_PRODUCTION_FLOOR_CHANGED')
  if actual.is_empty or not actual.is_valid or actual.geom_type not in('Polygon','MultiPolygon'):raise ValueError('SOURCE_CHANNEL_VALID_ACTUAL_COPPER_REQUIRED')
  # The immutable non-frame source operands are the source authority; add
  # only genuinely new copper from actual material. Original frame aliases
  # cannot leave fictitious sub-grid channel islands after a Boolean cut.
  # The actual original Gerber image is the preservation authority. A
  # separately re-unioned source subset can have tiny overlay residues that
  # are absent even from that untouched image. Require actual source loss
  # before attributing any missing copper to a functional channel. No area
  # threshold, snap, or new tolerance is introduced.
  source_missing=self.source.difference(actual)
  missing=[own for own,core in self.original.items()if source_missing.intersection(core).area>0]
  added=actual.difference(self.source);cut=joined([self.analytic_source,*surface_parts(added.difference(self.frame))]);current=OriginalOwners(cut);mapping={};failures=[]
  if missing:failures.append(dict(reason='FROZEN_SOURCE_CHANNEL_MISSING',source_channel_ids=missing))
  for n,g in enumerate(current.owners):
   ids=self.index.membership(g)
   if len(ids)!=1:
    failures.append(dict(reason='CHANNELS_MERGED_OUTSIDE_TEMPORARY_FRAME'if ids else'NEW_UNBOUND_COPPER_OUTSIDE_TEMPORARY_FRAME',source_channel_ids=ids,component=n,bounds_mm=list(g.bounds)));continue
   own=ids[0]
   if own in mapping:failures.append(dict(reason='FROZEN_SOURCE_CHANNEL_SPLIT',source_channel_id=own))
   mapping[own]=g
  missing=sorted(set(self.original)-set(mapping))
  if missing and not any(r['reason']=='CHANNELS_MERGED_OUTSIDE_TEMPORARY_FRAME'for r in failures):failures.append(dict(reason='FROZEN_SOURCE_CHANNEL_MISSING',source_channel_ids=missing))
  pairs=[]
  if not failures:
   ids=list(mapping);tree=STRtree([mapping[o]for o in ids])
   for own,g in mapping.items():
    added=g.difference(self.original[own])
    if added.is_empty:continue
    for j in sorted(map(int,tree.query(added.buffer(gap+.000002).envelope))):
     other=ids[j]
     if other==own:continue
     measured=distance(added,mapping[other]);passed=measured+1e-12>=gap;pairs.append(dict(source_channel_id=own,foreign_source_channel_id=other,gap_mm=measured,passed=passed))
     if not passed:failures.append(dict(reason='NEW_COPPER_TO_DIFFERENT_SOURCE_CHANNEL_CLEARANCE',source_channel_id=own,foreign_source_channel_id=other,gap_mm=measured))
  return dict(schema='source-channel-separation/1',passed=not failures,failures=failures,source_sha256=self.source_sha256,frame_geometry_sha256=digest(to_wkb(self.frame)),source_channels=len(self.original),current_components_after_analytic_exclusion=len(current.owners),pairs=pairs,policy=self.policy,material_change_by_check=False,scope='Additional source-channel merge and clearance checks. Original source prefix, physical-owner checks, local remedy cap and complete native export checks remain independently mandatory.')
