"""Apply the same owner-surface absorption to construction and native reference."""
from . import pipeline as p
from src import component_clearance as cc
from src.u05_board.export import export_region
from .component_finish import prepare_region

def polygonal_support(region):
 """Keep every copper face; clipped zero-area support is not material."""
 if not region.is_valid or region.is_empty:
  raise ValueError('T05_EXPORT_SUPPORT_POLYGONAL_REQUIRED')
 if region.geom_type in('Polygon','MultiPolygon'):return region
 if region.geom_type!='GeometryCollection':
  raise ValueError('T05_EXPORT_SUPPORT_POLYGONAL_REQUIRED')
 from src.component_voids import surface_parts
 from shapely.geometry import MultiPolygon
 faces=surface_parts(region)
 if not faces:raise ValueError('T05_EXPORT_SUPPORT_POLYGONAL_REQUIRED')
 # Reuse exact rings, holes and islands. No union, grid snapping, buffer,
 # area threshold, repair or change to the qualified addition is permitted.
 result=faces[0]if len(faces)==1 else MultiPolygon(faces)
 if not result.is_valid or result.is_empty:
  raise ValueError('T05_EXPORT_SUPPORT_POLYGONAL_REQUIRED')
 return result

def compact_supported_region(addition,owner,domain):
 """One local joint surface; duplicate only already-present owner copper.

All original export_region predicates are retained. If the exact existing
Boolean proof does not hold, use the original qualified support construction.
 """
 from src.junction_spindle_stage import CONTRACT
 from src.u05_board.export import NATIVE_OWNER_OVERLAP_MM
 # Inset redundant support only; retain the complete qualified addition.
 window=domain.buffer(-NATIVE_OWNER_OVERLAP_MM,quad_segs=64)
 support=owner.intersection(window);target=owner.union(addition)
 # Form the physical surface before clipping its redundant owner support.
 # Re-unioning separately clipped owner/addition boundaries can manufacture
 # ULP slivers. The qualified addition stays complete; all original predicates
 # below still apply with their original area epsilon.
 region=target.intersection(window).union(addition)
 region=polygonal_support(region)
 if (region.is_valid and not region.is_empty
     and support.difference(owner).area<=CONTRACT.area_epsilon_mm2
     and addition.difference(region).area<=CONTRACT.area_epsilon_mm2
     and owner.union(region).symmetric_difference(target).area<=CONTRACT.area_epsilon_mm2
     and region.difference(domain).area<=CONTRACT.area_epsilon_mm2):
  return region,support,'CHECKED_COMPLETE_LOCAL_JOINT_SURFACE'
 return supported_region(addition,owner,domain)

def supported_region(addition,owner,domain):
 try:
  region,support=export_region(addition,owner,domain)
  region=polygonal_support(region)
  return region,support,'ORIGINAL_SUPPORT'
 except ValueError as error:
  if str(error)!='U05_NATIVE_SUPPORT_CHANGES_QUALIFIED_COPPER':raise
 try:
  region,support=export_region(addition,owner,domain,support_from_owner=True)
  region=polygonal_support(region)
  return region,support,'CHECKED_OWNER_FIRST_ALTERNATE'
 except ValueError as error:
  if str(error)!='U05_NATIVE_SUPPORT_CHANGES_QUALIFIED_COPPER':raise
 # The Gerber-only serializer can encode the qualified addition directly.
 # Overlap was introduced for KiCad clipping of razor tips; it is redundant
 # material, not additional growth. Avoid introducing intersection vertices
 # when both overlap constructions fail. Keep all four original predicates,
 # their original epsilon, and the downstream actual-file fidelity checks.
 from src.junction_spindle_stage import CONTRACT
 region=addition;support=addition.difference(addition);target=owner.union(addition)
 if (not region.is_valid or region.is_empty
     or support.difference(owner).area>CONTRACT.area_epsilon_mm2
     or addition.difference(region).area>CONTRACT.area_epsilon_mm2
     or owner.union(region).symmetric_difference(target).area>CONTRACT.area_epsilon_mm2
     or region.difference(domain).area>CONTRACT.area_epsilon_mm2):
  raise ValueError('U05_NATIVE_SUPPORT_CHANGES_QUALIFIED_COPPER')
 return region,support,'EXACT_ADDITION_WITHOUT_REDUNDANT_SUPPORT'

def prepare_export_region(store,value,adapter,owner,domain,decision,foreign):
 addition=p.geometry(store,decision['patch_ref'])
 if cc.ACTIVE is None:return export_region(addition,owner,domain)
 region,support,support_mode=compact_supported_region(addition,owner,domain)
 from src.u05_board.coverage import integral_context
 context=integral_context();own=adapter.owner_for_route(decision['source_id']);all_foreign=list(foreign)
 for row in value['candidate']['decisions']:
  if row['status']=='GROWN'and context.owner(row['source_id'])!=own:all_foreign.append(('selected-foreign:'+row['source_id'],p.geometry(store,row['patch_ref'])))
 region,receipt=prepare_region(store,region,owner,own,foreign=all_foreign)
 return region,dict(base_export_support=support,support_assembly=support_mode,owner_surface_absorption=receipt)
