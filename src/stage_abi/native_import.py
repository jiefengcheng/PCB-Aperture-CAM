"""Host-only source-bound native scene import; no ABI request can call this.

Chains are externally qualified complete routes. Their original native member
identities remain bound in metadata even when a route is represented atomically.
"""
from shapely import to_wkb,from_wkb
from shapely.geometry import box
from src.source_offset_width import construct_source_offset_width
from .contracts import fail
from .store import digest


def import_width_scene(store,*,source,manifest,original_blobs,current_blobs,chains,viewport_mm,qualification,current_widths=None):
 if digest(source)!=manifest['source_sha256']:fail('SOURCE_BINDING_MISMATCH','manifest/source')
 meta={r['id']:r for r in manifest['objects']};current_widths=current_widths or {}
 if not set(current_widths)<=set(meta) or any(type(v) not in (int,float) or v<=0 for v in current_widths.values()):fail('CURRENT_WIDTH_AUTHORITY_INVALID','source widths')
 if len(meta)!=len(manifest['objects']) or set(original_blobs)!=set(meta) or not set(current_blobs)<=set(meta):fail('SOURCE_COVERAGE_MISMATCH','complete native cache/replacement inventory')
 for sid,m in meta.items():
  if digest(original_blobs[sid])!=m['geometry_sha256']:fail('SOURCE_GEOMETRY_HASH_MISMATCH',sid)
 used=set();source_ref=store.put('native-source',source);rows=[];targets=[]
 for index,chain in enumerate(chains):
  members=chain['source_ids']
  if used.intersection(members):fail('TRACE_SOURCE_PARTITION_INVALID','duplicate native members')
  used.update(members);sid='route:'+chain['component_id'];native_chain=dict(chain,component_id=sid)
  record,_,_,core,_,_=construct_source_offset_width(source,native_chain,meta,original_blobs,1.)
  if any(s in current_blobs and current_blobs[s]!=original_blobs[s] for s in members):fail('TRACE_PREDECESSOR_UNSUPPORTED','source trace already changed')
  original_ref=store.put('geometry',to_wkb(core));native_ref=store.put_json('native-route',dict(source_ref=source_ref,chain=native_chain,manifest_rows={s:meta[s] for s in members},geometry_refs={s:store.put('geometry',original_blobs[s]) for s in members}));rows.append(dict(source_id=sid,kind='trace',original_ref=original_ref,geometry_ref=original_ref,metadata=dict(native_route_ref=native_ref,nominal_width_mm=record['verified_original_width_mm'],native_source_ids=members,complete_route_qualification=qualification)));targets.append(sid)
 for sid in sorted(set(meta)-used):
  m=meta[sid];original_ref=store.put('geometry',original_blobs[sid]);current_ref=original_ref if sid not in current_blobs else store.put('geometry',current_blobs[sid]);kind='circle' if m['kind']=='gr_circle' else 'rectangle' if m['kind']=='gr_poly' and from_wkb(original_blobs[sid]).equals(box(*from_wkb(original_blobs[sid]).bounds)) else 'fixed_source'
  if m['trace_width_mm']>0 and current_ref!=original_ref and sid not in current_widths:fail('CURRENT_WIDTH_AUTHORITY_REQUIRED',sid)
  rows.append(dict(source_id=sid,kind=kind,original_ref=original_ref,geometry_ref=current_ref,metadata=dict(native_source_kind=m['kind'],nominal_width_mm=current_widths.get(sid,m['trace_width_mm']),native_source_ids=[sid])))
 scene_ref=store.put_json('scene',dict(source_sha256=manifest['source_sha256'],frame='native-kicad-mm',units='mm',layer='F.Cu',viewport_mm=list(viewport_mm),objects=rows,findings=[],lineage=[dict(stage='host-qualified-input',qualification=qualification,native_member_count=len(meta))],acceptance=dict(owner='NOT_GRANTED_FOR_NEW_SCENE',independent='NOT_RUN')))
 return dict(scene_ref=scene_ref,target_ids=targets,source_objects=len(meta),scene_objects=len(rows),selected_native_members=len(used),unchanged_native_members=len(meta)-len(used))
