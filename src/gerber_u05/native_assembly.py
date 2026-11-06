"""Representation-aware assembly, conditional on exact parsed native material.

No union is used to decide whether a partition preserves its parent. Integer
boundary and area proofs precede reconstruction of that same material. Stable
rings/operand order prevent incidental triangulation and floating precision tags
from changing the subsequent whole-image comparison.
"""
from collections import OrderedDict
from shapely import to_wkb,union_all
from shapely.geometry import Polygon
from .native_material import normal_form,equality
from .contours import verify_partition

def canonical_parent(shape,*,grid_mm):
 shell,holes=normal_form(shape,grid_mm=grid_mm)
 return Polygon([(x*grid_mm,y*grid_mm)for x,y in shell],
                [[(x*grid_mm,y*grid_mm)for x,y in ring]for ring in holes])

def assemble(source,parents,*,grid_mm):
 values=sorted((canonical_parent(g,grid_mm=grid_mm)for g in parents),key=to_wkb)
 result=union_all([source,*values],grid_size=grid_mm)
 if result.is_empty or not result.is_valid:raise ValueError('NATIVE_MATERIAL_ASSEMBLY_INVALID')
 return result

def key(row):
 return(row['stage'],row['source_id'],row['component_reference_proof']['partition_parent_reference_proof']['export_reference_sha256'])

def weld(records,decoded,parents,*,grid_mm):
 if len(records)!=len(decoded):raise ValueError('NATIVE_MATERIAL_REGION_COUNT_CHANGED')
 groups=OrderedDict();targets={}
 for identity,shape in parents:
  if identity in targets:raise ValueError('NATIVE_MATERIAL_PARENT_IDENTITY_DUPLICATED')
  targets[identity]=shape
 for row,shape in zip(records,decoded):groups.setdefault(key(row),[]).append((row,shape))
 if set(groups)!=set(targets):raise ValueError('NATIVE_MATERIAL_PARENT_INVENTORY_CHANGED')
 result=[];proofs=[]
 for identity,rows in groups.items():
  target=targets[identity];parts=[g for _,g in rows];statuses={r['component_reference_proof']['serialization_partition']['status']for r,_ in rows}
  if len(statuses)!=1:raise ValueError('NATIVE_MATERIAL_ENCODING_MIXED')
  status=next(iter(statuses));indices=[r['component_reference_proof']['serialization_part']for r,_ in rows]
  if indices!=list(range(len(rows))):raise ValueError('NATIVE_MATERIAL_PART_INVENTORY_CHANGED')
  if status in('EXACT_INTEGER_GRID_PARTITION','EXACT_COALESCED_INTEGER_PARTITION'):
   if any(r['component_reference_proof']['serialization_partition']['parts']!=len(rows)for r,_ in rows):raise ValueError('NATIVE_MATERIAL_PART_COUNT_CHANGED')
   proof=verify_partition(target,parts,grid_mm=grid_mm)
  elif status in('ORIGINAL_CUT_IN_ENCODING','EXACT_AXIAL_CUT_IN_ENCODING')and len(rows)==1:
   proof=equality(target,parts[0],grid_mm=grid_mm)
  else:raise ValueError('NATIVE_MATERIAL_ENCODING_UNQUALIFIED')
  # This parent may be used only after its actual parsed regions have proved
  # the identical material, including every hole and minimum-grid face.
  result.append((identity,canonical_parent(target,grid_mm=grid_mm)))
  proofs.append(dict(stage=identity[0],source_id=identity[1],native_parent_sha256=identity[2],parsed_regions=len(rows),proof=proof))
 return result,dict(status='EXACT_PARSED_NATIVE_MATERIAL',parsed_regions=len(decoded),parents=len(result),grid_mm=grid_mm,tolerance_allowance=False,checks=proofs,basis='Every actual native region accounted for; exact signed atomic boundary and doubled area or integer ring equality before stable physical assembly; source holes and all positive faces retained')
