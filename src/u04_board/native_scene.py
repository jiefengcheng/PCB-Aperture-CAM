"""T02 sees every native predecessor contribution and original contact width."""
from shapely import from_wkb
from src.stage_abi.scene import composed,validate_scene
from src.stage_abi.store import digest,canonical
from src.stage_abi.preparation import decode_geometry as from_wkb


def materialize(store,width,candidate,grouped_ref):
    grouped=validate_scene(store,grouped_ref);meta={r['id']:r for r in width.manifest['objects']}
    actual_members=[s for r in grouped['objects'] for s in r['metadata']['native_source_ids']]
    if len(actual_members)!=len(set(actual_members)) or set(actual_members)!=set(meta):raise ValueError('U04_NATIVE_SOURCE_PARTITION_CHANGED')
    native_widths={p['source_id']:r['uniform_nominal_width_mm'] for r in candidate['construction'] for p in r['primitives']}
    objects=[]
    for sid in sorted(meta):
        m=meta[sid];original=store.put('geometry',width.original[sid]);current=store.put('geometry',width.current[sid])
        if sid in candidate['parts']:current=candidate['parts'][sid]['nominal_ref']
        core=from_wkb(width.original[sid])
        from shapely.geometry import box
        kind='trace' if m['kind'] in ('segment','arc') else 'circle' if m['kind']=='gr_circle' else 'rectangle' if m['kind']=='gr_poly' and core.equals(box(*core.bounds)) else 'fixed_source'
        objects.append(dict(source_id=sid,kind=kind,original_ref=original,geometry_ref=current,metadata=dict(native_source_ids=[sid],native_source_kind=m['kind'],original_width_mm=m['trace_width_mm'],nominal_width_mm=native_widths.get(sid,m['trace_width_mm']))))
    scene=dict(grouped,objects=objects,lineage=grouped['lineage']+[dict(stage='u04-native-part-view',predecessor_ref=grouped_ref,source_sha256=digest(width.raw),original_width_authority='Complete fresh native manifest')])
    a=composed(store,grouped);b=composed(store,scene)
    if a.symmetric_difference(b).area>1e-10:raise ValueError('U04_NATIVE_PART_VIEW_COPPER_CHANGED')
    return store.put_json('scene',scene),scene
