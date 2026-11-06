"""Deterministic original-stroke perimeter discovery for analytical exclusions.

No input/output copper is edited. Only an unambiguous uniform closed source
perimeter enclosing the complete source may supply a common-frame certificate.
"""
from collections import defaultdict
from decimal import Decimal
from shapely import from_wkb,to_wkb
from shapely.geometry import Polygon
from src.component_voids import joined,surface_parts,sha,RemedyContract
from src.original_copper_owners import OriginalOwners
from src.source_channel_guard import POLICY
from src.stage_abi.store import digest

def discover(source,source_sha256,scene,store):
 if scene['source_sha256']!=source_sha256 or scene['units']!='mm':raise ValueError('COMMON_FRAME_SOURCE_BINDING_CHANGED')
 contract=RemedyContract();families=defaultdict(dict)
 for row in scene['objects']:
  if row['kind']!='stroke':continue
  md=row['metadata'];family=tuple(md['aperture_family']);shape=from_wkb(store.get(row['original_ref'],kind='geometry'));key=sha(shape);group=families[family]
  if key in group:
   group[key]['aliases'].append(row['source_id']);continue
  ends=[tuple(Decimal(value)for value in point)for point in md['endpoints_decimal_mm']]
  group[key]=dict(shape=shape,ends=ends,aliases=[row['source_id']],original_ref=row['original_ref'])
 candidates=[]
 for family,group in sorted(families.items()):
  adjacency=defaultdict(list)
  for key,item in group.items():
   for end in item['ends']:adjacency[end].append(key)
  visited=set()
  for seed in sorted(group):
   if seed in visited:continue
   todo=[seed];component=set();closed=True
   while todo:
    key=todo.pop()
    if key in component:continue
    component.add(key)
    for end in group[key]['ends']:
     if len(adjacency[end])!=2:closed=False
     todo.extend(adjacency[end])
   visited.update(component)
   if not closed:continue
   frame=joined([group[key]['shape']for key in sorted(component)])
   if frame.geom_type!='Polygon'or len(frame.interiors)!=1:continue
   outer=Polygon(frame.exterior);outside=source.difference(outer)
   if not source.difference(outer.buffer(contract.file_uncertainty_mm,quad_segs=64)).is_empty:continue
   aliases={sid for key in component for sid in group[key]['aliases']}
   # Remove the verified frame occurrences before source assembly, not by
   # subtracting two independently tessellated whole-board unions. This also
   # retains exact trace ends where they originally overlap the shared bar.
   channels=joined([from_wkb(store.get(r['original_ref'],kind='geometry'))for r in scene['objects']if r['source_id']not in aliases]);index=OriginalOwners(channels)
   if len(index.ids)<2:continue
   certificate=dict(status='UNAMBIGUOUS_ORIGINAL_COMMON_FRAME',policy=POLICY,source_sha256=source_sha256,source_geometry_sha256=digest(to_wkb(source)),analytic_source_ref=store.put('geometry',to_wkb(channels)),analytic_source_sha256=digest(to_wkb(channels)),frame_geometry_sha256=digest(to_wkb(frame)),frame_geometry_ref=store.put('geometry',to_wkb(frame)),frame_parts=len(component),all_occurrences=sum(len(group[key]['aliases'])for key in component),aperture_family=list(family),frame_source_rows=[dict(original_ref=group[key]['original_ref'],source_ids=sorted(group[key]['aliases']))for key in sorted(component)],source_channels=len(index.ids),enclosure=dict(native_classification_bound_mm=contract.file_uncertainty_mm,outside_overlay_diagnostic_mm2=outside.area),material_edit=False)
   candidates.append((frame,certificate))
 if len(candidates)>1:raise ValueError('MULTIPLE_OUTER_COMMON_FRAME_CANDIDATES')
 if not candidates:return None,dict(status='NO_UNAMBIGUOUS_COMMON_FRAME',policy=POLICY,source_sha256=source_sha256,material_edit=False)
 return candidates[0]
