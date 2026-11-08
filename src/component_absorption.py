"""Absorb new sub-grid thin voids into their existing shape before storage."""
from shapely import from_wkb,to_wkb,set_precision
from shapely.geometry import Polygon
from src.component_voids import parts,holes,joined,proposal_check

def absorb(region,physical_owner,original,foreign,contract):
 from src.hole_acceptance import required
 protected=joined(holes(original))if required()else Polygon();pieces=[];records=[]
 for piece in parts(region):
  retained=[]
  for ring in piece.interiors:
   hole=Polygon(ring);thin=hole.buffer(-contract.file_uncertainty_mm).is_empty
   collapses=set_precision(from_wkb(to_wkb(hole)),contract.grid_mm,mode='valid_output').is_empty
   if not thin or not collapses:retained.append(ring);continue
   if hole.intersection(protected).area>0:
    retained.append(ring);records.append(dict(status='KEEP_ORIGINAL_SOURCE_VOID',area_mm2=hole.area));continue
   from src.growth_remedy_constraints import remedy as pin_remedy
   pin_check=pin_remedy(hole,physical_owner)
   if pin_check is not None and not pin_check['passed']:
    retained.append(ring);records.append(dict(status='KEEP_PROTECTED_PIN_SEPARATION',area_mm2=hole.area,check=pin_check));continue
   new=hole.difference(physical_owner)
   if new.is_empty:
    check=dict(passed=True,reason='Already copper in the same original physical owner; representation-only duplication')
   else:check=proposal_check(hole,physical_owner,original,foreign,contract,kind='hole')
   if not check['passed']:
    retained.append(ring);records.append(dict(status='KEEP_CHECKED_BOUNDARY',area_mm2=hole.area,check=check));continue
   physical_owner=physical_owner.union(hole)
   records.append(dict(status='ABSORBED_INTO_EXISTING_SHAPE',area_mm2=hole.area,new_physical_copper_mm2=new.area,check=check))
  grown=Polygon(piece.exterior,retained)
  if not grown.is_valid or not piece.difference(grown).is_empty:raise ValueError('ABSORPTION_REMOVED_EXISTING_COPPER')
  pieces.append(grown)
 return joined(pieces),dict(policy='Default original-owner surface absorption. No dedicated hole geometry/material object.',records=records,holes_absorbed=sum(r['status']=='ABSORBED_INTO_EXISTING_SHAPE'for r in records),absorbed_area_mm2=sum(r['area_mm2']for r in records if r['status']=='ABSORBED_INTO_EXISTING_SHAPE'))
