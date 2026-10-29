"""Source-bound fixed bulk-copper roles from explicitly identified regions.

A physical component label is used only to identify an unchanged bulk object.
It provides no electrical assertion and no clearance/contact exemption.
"""
import hashlib,math
from shapely import to_wkb
from shapely.geometry import Point
from shapely.ops import unary_union


def bind_bulk_regions(original_geometries, seeds, *, scope=None):
    copper=unary_union(original_geometries)
    if scope is not None:
        copper=copper.intersection(scope)
    parts=list(copper.geoms) if hasattr(copper,'geoms') else [copper]
    selected={};bindings=[]
    for seed in seeds:
        p=seed['point_mm']
        if len(p)!=2 or not all(math.isfinite(v) for v in p):raise ValueError('FINITE_BULK_REGION_SEED_REQUIRED')
        hits=[i for i,g in enumerate(parts) if g.covers(Point(p))]
        if len(hits)!=1:raise ValueError('UNAMBIGUOUS_ORIGINAL_BULK_REGION_REQUIRED')
        i=hits[0];key=hashlib.sha256(to_wkb(parts[i])).hexdigest();selected[key]=parts[i]
        bindings.append(dict(name=seed['name'],point_mm=p,original_component_wkb_sha256=key,area_mm2=parts[i].area,
                             role='FIXED_OWNER_IDENTIFIED_BULK_COPPER',electrical_claim='NONE',clearance_exemption='NONE'))
    return selected,bindings


def source_bulk_role(source_id, geometry, bulk_regions, *, scope=None):
    local=geometry if scope is None else geometry.intersection(scope)
    if local.is_empty or local.geom_type!='Polygon':
        return None # disconnected source objects need their own classification
    point=local.representative_point()
    hits=[key for key,g in bulk_regions.items() if g.covers(point)]
    if not hits:return None
    if len(hits)!=1:raise ValueError('AMBIGUOUS_SOURCE_BULK_MEMBERSHIP')
    return dict(source_id=source_id,source_geometry_sha256=hashlib.sha256(to_wkb(geometry)).hexdigest(),
                original_component_wkb_sha256=hits[0],source_interior_point_mm=[point.x,point.y],
                membership_scope='ORIGINAL_SOURCE_CROP' if scope is not None else 'FULL_ORIGINAL_SCENE',
                role='FIXED_SOURCE_CONTRIBUTOR_TO_OWNER_IDENTIFIED_BULK_REGION',
                source_copper_modified=False,component_role_only=True,electrical_claim='NONE',clearance_exemption='NONE')
