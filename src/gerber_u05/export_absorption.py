"""Apply the same owner-surface absorption to construction and native reference."""
from . import pipeline as p
from src import component_clearance as cc
from src.u05_board.export import export_region
from .component_finish import prepare_region

def supported_region(addition,owner,domain):
 try:
  region,support=export_region(addition,owner,domain)
  return region,support,'ORIGINAL_SUPPORT'
 except ValueError as error:
  if str(error)!='U05_NATIVE_SUPPORT_CHANGES_QUALIFIED_COPPER':raise
 region,support=export_region(addition,owner,domain,support_from_owner=True)
 return region,support,'CHECKED_OWNER_FIRST_ALTERNATE'

def prepare_export_region(store,value,adapter,owner,domain,decision,foreign):
 addition=p.geometry(store,decision['patch_ref'])
 if cc.ACTIVE is None:return export_region(addition,owner,domain)
 region,support,support_mode=supported_region(addition,owner,domain)
 own=adapter.owner_for_route(decision['source_id']);all_foreign=list(foreign)
 for row in value['candidate']['decisions']:
  if row['status']=='GROWN'and cc.ACTIVE.owner(row['source_id'])!=own:all_foreign.append(('selected-foreign:'+row['source_id'],p.geometry(store,row['patch_ref'])))
 region,receipt=prepare_region(store,region,owner,own,foreign=all_foreign)
 return region,dict(base_export_support=support,support_assembly=support_mode,owner_surface_absorption=receipt)
