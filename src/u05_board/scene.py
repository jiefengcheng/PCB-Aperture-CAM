from .worker_preparation import native_view as native_loads
"""Complete actual native U04 predecessor, original contacts and source aliases."""
import copy
import sexpdata
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import box
from shapely.ops import unary_union
from src.stage_abi.store import digest
from src.stage_abi.scene import validate_scene,composed
from src.stage_abi.spindle import filled_circle
from src.native_inventory import geometry
from src.native_reference import one
from src.source_locators import locate
from src.pcb_data_abi.board_geometry import fidelity
from src.u03_board.selection import for_root,window
from src.junction_spindle_stage import CONTRACT,prepare_spindle_context
from tools.t01_operator_host import read
from src.stage_abi.preparation import decode_geometry as from_wkb


def bound_original_node(tree,positions,spans,source_id,record):
    index=positions.get(source_id);span=spans.get(source_id)
    if index is None or span is None:raise ValueError('U05_TOP_LEVEL_NATIVE_SOURCE_REQUIRED:'+source_id)
    if record['id']!=source_id or record['source_span']!=[span.start,span.end]:raise ValueError('U05_ORIGINAL_SOURCE_SPAN_BINDING:'+source_id)
    node=tree[index]
    if not node or str(node[0])!=span.head or str(node[0])!=record['kind']:raise ValueError('U05_ORIGINAL_SOURCE_NODE_BINDING:'+source_id)
    return node

def prepare(store,predecessor,*,contributions_only=False):
    root=__import__('pathlib').Path(predecessor['root']);t02=read(root/'u04_t02/t02_run.json')['candidate'];native_scene=validate_scene(store,t02['output_scene_ref'])
    manifest=read(root/'data_board/source_manifest.json');meta={r['id']:r for r in manifest['objects']}
    receipt=read(root/'RECEIPT.json');binding=store.get_json(receipt['binding_ref'],kind='t01-binding');raw=store.get(binding['source_ref'],kind='native-source')
    if digest(raw)!=manifest['source_sha256']:raise ValueError('U05_ORIGINAL_SOURCE_CHANGED')
    # Original source is single-use here; keep one owned legacy parse and
    # reuse its exact source-bound nodes rather than encoding a cache entry.
    original_tree=sexpdata.loads(raw.decode());actual_tree=native_loads(__import__('pathlib').Path(predecessor['kicad']).read_text());spans=locate(raw)
    top_spans=[s for s in spans if s.parent_start==spans[0].start]
    if len(original_tree)!=len(top_spans)+1:raise ValueError('U05_ORIGINAL_SOURCE_NODE_COUNT')
    positions={s.identity:i+1 for i,s in enumerate(top_spans)}
    original_spans={s.identity:s for s in top_spans}
    inclusives=sorted(r['source_id'] for r in native_scene['objects'] if r['kind']=='inclusive_rectangle')
    if len(actual_tree)!=len(original_tree)+len(inclusives):raise ValueError('U05_NATIVE_U04_NODE_COVERAGE_CHANGED')
    rows=[];changed=0
    for item in native_scene['objects']:
        row=copy.deepcopy(item);sid=row['source_id'];derived=row['kind']=='inclusive_rectangle'
        index=len(original_tree)+inclusives.index(sid) if derived else positions.get(sid)
        if index is None:raise ValueError('U05_TOP_LEVEL_NATIVE_SOURCE_REQUIRED:'+sid)
        node=actual_tree[index];kind=str(node[0]);g=geometry(node,kind);old=from_wkb(store.get(row['geometry_ref'],kind='geometry'))
        if to_wkb(g)!=to_wkb(old):fidelity(old,g);changed+=1
        row['geometry_ref']=store.put('geometry',to_wkb(g));md=row['metadata'];md.update(native_source_ids=[] if derived else [sid],native_node_indices=[index],native_node_kinds=[kind],u04_math_ref=item['geometry_ref'])
        if derived:
            members=md['members'];support=unary_union([from_wkb(store.get(next(r for r in native_scene['objects'] if r['source_id']==s)['original_ref'],kind='geometry')) for s in sorted(members)])
            row['original_ref']=store.put('geometry',to_wkb(support));md['original_contact_support_ids']=members;md['qualified_land']=True;md['alias_source_ids']=[sid]
        else:
            m=meta[sid];source_node=bound_original_node(original_tree,positions,original_spans,sid,m);fill=str(one(source_node,'fill',['none'])[0]);core=from_wkb(store.get(row['original_ref'],kind='geometry'))
            md['qualified_land']=fill in ('yes','solid') and ((m['kind']=='gr_circle' and filled_circle(core)) or (m['kind']=='gr_poly' and core.equals(box(*core.bounds)) and g.equals(box(*g.bounds))))
            md['alias_source_ids']=[sid]
        rows.append(row)
    if contributions_only:
        scene=dict(native_scene,objects=rows)
        members=[s for r in rows for s in r['metadata']['native_source_ids']]
        if len(members)!=len(set(members)) or set(members)!=set(meta):raise ValueError('U05_COMPLETE_NATIVE_SOURCE_PARTITION_REQUIRED')
        return scene,dict(native_source_objects=len(meta),actual_native_nodes=len(actual_tree)-1,native_quantization_reconstructions=changed)
    actual_byid={r['source_id']:r for r in rows};width=read(root/'u03_t04/t04_run.json')['result']['candidate'];grouped=validate_scene(store,width['output_scene_ref']);routes=[r for r in grouped['objects'] if r['kind']=='trace']
    used=set();new_routes=[]
    for original_route in routes:
        row=copy.deepcopy(original_route);members=row['metadata']['native_source_ids']
        if used.intersection(members):raise ValueError('U05_ROUTE_SOURCE_PARTITION_DUPLICATED')
        used.update(members);parts={s:actual_byid[s]['geometry_ref'] for s in sorted(members)}
        current=unary_union([from_wkb(store.get(ref,kind='geometry')) for ref in parts.values()]);row['geometry_ref']=store.put('geometry',to_wkb(current))
        row['metadata'].update(native_part_refs=parts,native_part_kinds={s:str(actual_tree[positions[s]][0]) for s in sorted(members)},native_node_indices=[positions[s] for s in sorted(members)],native_node_kinds=[str(actual_tree[positions[s]][0]) for s in sorted(members)],land_ids=[])
        new_routes.append(row)
    rows=[r for r in rows if r['source_id'] not in used]
    for r in rows:
        if r['kind']=='trace':r['kind']='fixed_source';r['metadata']['t05_disposition']='KEEP_NO_QUALIFIED_COMPLETE_PATH'
    rows+=new_routes;rows.sort(key=lambda r:r['source_id'])
    aliases={}
    for r in rows:
        if r['metadata'].get('qualified_land') and r['kind']!='inclusive_rectangle':aliases.setdefault((r['kind'],r['original_ref']['sha256']),[]).append(r)
    for group in aliases.values():
        if len({r['geometry_ref']['sha256'] for r in group})!=1 or len({r['metadata']['native_node_kinds'][0] for r in group})!=1:raise ValueError('U05_LAND_ALIAS_CURRENT_CONFLICT')
        names=sorted(r['source_id'] for r in group)
        for r in group:r['metadata']['alias_source_ids']=names
    scene=dict(native_scene,objects=rows,lineage=native_scene['lineage']+[dict(stage='u05-actual-native-predecessor',retained_U04_scene_ref=predecessor['scene_ref'],native_U04_sha256=predecessor['kicad_sha256'],original_contact_basis='Fresh original native source; inclusive supports are original member rectangles')])
    native_members=[s for r in rows for s in r['metadata']['native_source_ids']]
    if len(native_members)!=len(set(native_members)) or set(native_members)!=set(meta):raise ValueError('U05_COMPLETE_NATIVE_SOURCE_PARTITION_REQUIRED')
    return scene,dict(native_source_objects=len(meta),actual_native_nodes=len(actual_tree)-1,source_routes=len(routes),native_quantization_reconstructions=changed,all_U04_native_nodes_preserved=True)


def admit(store,scene,selection):
    objects={r['source_id']:r for r in scene['objects']};current={s:from_wkb(store.get(r['geometry_ref'],kind='geometry')) for s,r in objects.items()};original={s:from_wkb(store.get(r['original_ref'],kind='geometry')) for s,r in objects.items()}
    crop=window(selection) if selection else box(*scene['viewport_mm']);lands=sorted(s for s,r in objects.items() if r['metadata'].get('qualified_land') and s==min(r['metadata']['alias_source_ids']));tree=STRtree([original[s] for s in lands]);imported=copy.deepcopy(scene);byid={r['source_id']:r for r in imported['objects']};records=[];targets=[]
    for sid,row in sorted(objects.items()):
        if row['kind']!='trace':continue
        if not row['metadata'].get('native_route_ref') or not row['metadata']['native_source_ids']:raise ValueError('U05_COMPLETE_NATIVE_ROUTE_REQUIRED')
        contacts=[]
        for i in sorted(map(int,tree.query(original[sid]))):
            lid=lands[i]
            if original[sid].intersection(original[lid]).area<=CONTRACT.area_epsilon_mm2:continue
            if current[sid].intersection(current[lid]).area<=CONTRACT.area_epsilon_mm2:raise ValueError('U05_ORIGINAL_CONTACT_LOST')
            contacts.append(lid)
        status='KEEP_NO_SOURCE_CONTACT'
        if contacts:
            owner,radius,_=prepare_spindle_context(current[sid],[current[l] for l in contacts],box(*scene['viewport_mm']))
            full_window=unary_union([current[l].buffer(CONTRACT.window_land_radii*radius,quad_segs=CONTRACT.buffer_quad_segs) for l in contacts])
            if not crop.covers(current[sid]) or not crop.covers(full_window):status='KEEP_COMPLETE_WINDOW_BOUNDARY'
            else:status='ADMIT_SOURCE_CONTACTS';targets.append(sid)
        byid[sid]['metadata']['land_ids']=contacts if sid in targets else []
        records.append(dict(source_id=sid,native_source_ids=row['metadata']['native_source_ids'],land_ids=contacts,disposition=status,original_ref=row['original_ref'],current_ref=row['geometry_ref']))
    return imported,dict(routes=records,target_ids=targets,source_ids=sorted(objects),native_source_ids=sorted(s for r in objects.values() for s in r['metadata']['native_source_ids']),selection=selection)
