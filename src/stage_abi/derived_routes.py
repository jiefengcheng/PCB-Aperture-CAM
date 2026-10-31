"""Bind T03's actual replacement paths as fresh native segment sources for T04.

These are derived route authorities, never relabelled original board bytes.
The original board and pre-replacement footprints remain bound separately.
"""
from shapely import to_wkb
from shapely.geometry import LineString
from .store import digest


def route_authorities(store,scene,plan,paths,rows):
 fragments=[];ranges={};position=0
 for sid in sorted(paths):
  width=rows[sid]['metadata']['nominal_width_mm'];spans=[]
  for a,b in zip(paths[sid],paths[sid][1:]):
   text=f'(segment (start {a[0]:.17g} {a[1]:.17g}) (end {b[0]:.17g} {b[1]:.17g}) (width {width:.17g}) (layer F.Cu) (net 0))';blob=text.encode();spans.append((position,position+len(blob),a,b));fragments.append(blob);position+=len(blob)+1
  ranges[sid]=spans
 raw=b'\n'.join(fragments);h=digest(raw);source_ref=store.put('native-source',raw);result={};plan_ref=store.put_json('plan',plan)
 for sid,spans in ranges.items():
  width=rows[sid]['metadata']['nominal_width_mm'];members=[];manifest={};geometries={}
  for start,end,a,b in spans:
   member=f'{h}:bytes:{start}:{end}';blob=to_wkb(LineString([a,b]).buffer(width/2,quad_segs=rows[sid]['metadata'].get('route_quad_segs',128)));reference=store.put('geometry',blob);members.append(member);manifest[member]=dict(id=member,kind='segment',trace_width_mm=width,geometry_sha256=digest(blob));geometries[member]=reference
  native=store.put_json('native-route',dict(source_ref=source_ref,chain=dict(component_id=sid,source_ids=members,source_sha256=h),manifest_rows=manifest,geometry_refs=geometries,parent_source_sha256=scene['source_sha256'],generated_by_plan_ref=plan_ref,geometry_family='bounded-parallel-polyline-miter/1'));result[sid]=dict(rows[sid]['metadata'],route_points_mm=paths[sid],route_family='bounded-parallel-polyline-miter/1',native_route_ref=native,board_original_geometry_ref=rows[sid]['metadata'].get('board_original_geometry_ref',rows[sid]['original_ref']))
 return result
