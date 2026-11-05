"""Source identities and declared obligations, never historical candidate copper."""
import copy,json
from pathlib import Path
from shapely import from_wkb,to_wkb,STRtree
from shapely.geometry import box
from shapely.ops import unary_union
from src.stage_abi.store import canonical,digest
from src.junction_spindle_stage import CONTRACT
from .junctions import parameters
from .scene import prepare
from .custody import ROOT
from tools.t01_operator_host import read
from src.stage_abi.preparation import decode_geometry as from_wkb

PROFILE=ROOT/'contracts/operator/u05_attachment_profile.json'

def reference_binding(path,predecessor):
    path=Path(path);policy=read(PROFILE)
    if not path.is_absolute() or path.resolve()!=ROOT/policy['reference'] or path.is_symlink():raise ValueError('U05_EXPLICIT_QUALIFIED_REFERENCE_REQUIRED')
    if predecessor['source_sha256']!=policy['source_sha256']:raise ValueError('U05_REFERENCE_SOURCE_MISMATCH')
    for name,h in policy['files'].items():
        if digest((path/name).read_bytes())!=h:raise ValueError('U05_REFERENCE_CHANGED:'+name)
    if read(path/'T05/STAGE_CONTRACT.json')!=parameters():raise ValueError('U05_REFERENCE_SPINDLE_POLICY_CHANGED')
    if policy.get('scope_exception'):
        p=ROOT/policy['scope_exception']['path']
        if digest(p.read_bytes())!=policy['scope_exception']['sha256']:raise ValueError('U05_APPROVED_SCOPE_GEOMETRY_CHANGED')
    return dict(root=str(path),profile_sha256=digest(PROFILE.read_bytes()),files=policy['files'],source_sha256=policy['source_sha256'])

def verify_reference(value,predecessor):
    if reference_binding(Path(value['root']),predecessor)!=value:raise ValueError('U05_REFERENCE_BINDING_CHANGED')
    return Path(value['root'])

def work_scene(store,predecessor,bound):
    reference=verify_reference(bound,predecessor);scene,facts=prepare(store,predecessor,contributions_only=True)
    original_rows={r['source_id']:r for r in scene['objects']};current={s:from_wkb(store.get(r['geometry_ref'],kind='geometry')) for s,r in original_rows.items()};original={s:from_wkb(store.get(r['original_ref'],kind='geometry')) for s,r in original_rows.items()}
    paths=read(Path(predecessor['root'])/'u03_t04/t04_inspect.json')['path_records'];parent={s:p for p in paths for s in p['path']['source_ids']}
    inclusive={r['candidate']:r for r in read(reference/'T02/INCLUSIVE_CANDIDATES.json')}
    definitions=read(reference/'T05/DECISIONS.json')
    if len(definitions)!=97 or sum(d['status']=='GROWN' for d in definitions)!=85 or sum(len(d['land_ids']) for d in definitions if d['status']=='GROWN')!=162:raise ValueError('U05_REFERENCE_OBLIGATION_COVERAGE_CHANGED')
    # Source contributors remain distinct; engineering trace clusters are views.
    # prepare produced private deep-copied rows. Transfer those owned rows;
    # immutable predecessor artifacts and constructor inputs remain untouched.
    rows=scene['objects']
    for r in rows:
        if r['kind']=='trace':r['kind']='fixed_source'
    byid={r['source_id']:r for r in rows};land_aliases={}
    for r in rows:
        if r['metadata'].get('qualified_land'):
            key=(r['kind'],r['original_ref']['sha256']);land_aliases.setdefault(key,[]).append(r)
    for alias_rows in land_aliases.values():
        if len({r['geometry_ref']['sha256'] for r in alias_rows})!=1:raise ValueError('U05_LAND_ALIAS_CONFLICT')
        ids=sorted(r['source_id'] for r in alias_rows)
        for r in alias_rows:r['metadata']['alias_source_ids']=ids
    inclusive_index={}
    for s,r in byid.items():
        if r['kind']=='inclusive_rectangle':inclusive_index.setdefault(frozenset(r['metadata']['members']),[]).append(s)
    def map_land(lid):
        if lid.startswith('inclusive:'):
            want=set(inclusive[lid.split(':',1)[1]]['rectangle_members']);found=inclusive_index.get(frozenset(want),[])
            if len(found)!=1:raise ValueError('U05_REFERENCE_INCLUSIVE_MEMBERSHIP_UNQUALIFIED:'+lid)
            lid=found[0]
        if lid not in byid or not byid[lid]['metadata'].get('qualified_land'):raise ValueError('U05_REFERENCE_LAND_UNQUALIFIED:'+lid)
        return min(byid[lid]['metadata']['alias_source_ids'])
    clusters=[];attachment_ids=set()
    for definition in definitions:
        members=definition['source_ids'];ps={parent[s]['path']['path_id']:parent[s] for s in members}
        if len(ps)!=1 or any(s not in original_rows for s in members):raise ValueError('U05_CLUSTER_COMPLETE_PARENT_UNQUALIFIED')
        p=next(iter(ps.values()))
        if not p['path']['original_native_source_members_retained']:raise ValueError('U05_NATIVE_PARENT_MEMBERSHIP_LOST')
        sid='route:'+definition['route_id'];refid=definition.get('id',definition['route_id']);land_ids=list(dict.fromkeys(map_land(l) for l in definition['land_ids']))
        core=unary_union([original[s] for s in members]);now=unary_union([current[s] for s in members]);contacts=[]
        for ordinal,lid in enumerate(definition['land_ids']):
            mapped=map_land(lid)
            if core.intersection(original[mapped]).area<=CONTRACT.area_epsilon_mm2 or now.intersection(current[mapped]).area<=CONTRACT.area_epsilon_mm2:raise ValueError('U05_REFERENCE_CONTACT_NOT_QUALIFIED:'+refid+':'+lid)
            aid=refid+':attachment:'+str(ordinal);attachment_ids.add(aid)
            contacts.append(dict(id=aid,reference_land_id=lid,land_id=mapped,required_reference=definition['status']=='GROWN',basis='ORIGINAL_AND_CURRENT_POSITIVE_AREA_CONTACT'))
        qualification=dict(reference_binding=bound,reference_route=definition['route_id'],source_ids=members,parent_path=p['path'],T04_disposition=p['disposition'],authority='T05 local additive view only; no native width edit')
        md=dict(native_source_ids=[],native_route_ref=store.put_json('u05-cluster-source',qualification),reference_source_ids=members,parent_path_id=p['path']['path_id'],parent_source_ids=p['path']['source_ids'],T04_disposition=p['disposition'],reference_id=refid,reference_status=definition['status'],attachments=contacts,land_ids=land_ids,native_part_refs={s:original_rows[s]['geometry_ref'] for s in members},native_part_kinds={s:original_rows[s]['metadata']['native_node_kinds'][0] for s in members},native_node_indices=[original_rows[s]['metadata']['native_node_indices'][0] for s in members],native_node_kinds=[original_rows[s]['metadata']['native_node_kinds'][0] for s in members])
        row=dict(source_id=sid,kind='trace',original_ref=store.put('geometry',to_wkb(core)),geometry_ref=store.put('geometry',to_wkb(now)),metadata=md);rows.append(row);clusters.append(row)
    from src.u03_board.selection import for_root,window
    selected=for_root(Path(predecessor['root']));write=window(selected) if selected else box(*scene['viewport_mm'])
    source_lands=sorted(s for s,r in byid.items() if r['metadata'].get('qualified_land') and s==min(r['metadata']['alias_source_ids']))
    tree=STRtree([original[s] for s in source_lands]);inclusive_members={s for r in byid.values() if r['kind']=='inclusive_rectangle' for s in r['metadata']['members']};context_contacts=[];extra=[]
    for cluster in clusters:
        md=cluster['metadata'];core=from_wkb(store.get(cluster['original_ref'],kind='geometry'));now=from_wkb(store.get(cluster['geometry_ref'],kind='geometry'))
        for i in sorted(map(int,tree.query(core))):
            lid=source_lands[i]
            if lid in md['land_ids'] or lid in inclusive_members or core.intersection(original[lid]).area<=CONTRACT.area_epsilon_mm2:continue
            if now.intersection(current[lid]).area<=CONTRACT.area_epsilon_mm2:raise ValueError('U05_DISCOVERED_SOURCE_CONTACT_LOST:'+lid)
            record=dict(parent_cluster=cluster['source_id'],land_id=lid,basis='ADDITIONAL_ORIGINAL_AND_CURRENT_CONTACT')
            if not write.covers(core.intersection(original[lid]).representative_point()):context_contacts.append(dict(record,status='OUTSIDE_WRITE_CONTEXT'));continue
            eid='extra:'+digest(canonical(record))[:24];a=dict(id=eid+':attachment:0',reference_land_id=lid,land_id=lid,required_reference=False,basis=record['basis'])
            view=copy.deepcopy(cluster);view['source_id']='route:'+eid;view['metadata'].update(reference_id=eid,reference_status='ADDITIONAL',attachments=[a],land_ids=[lid],parent_reference_cluster=cluster['source_id']);extra.append(view)
    rows+=extra
    facts.update(reference_clusters=len(clusters),additional_clusters=len(extra),context_contacts=context_contacts,reference_positive_clusters=85,required_reference_attachments=sum(a['required_reference'] for r in clusters for a in r['metadata']['attachments']),physical_source_partition='Original contributors once; derived engineering views carry empty native membership')
    return dict(scene,objects=rows,lineage=scene['lineage']+[dict(stage='u05-attachment-views',reference=bound)]),facts

def admission(store,scene,selection):
    from src.u03_board.selection import window
    write=window(selection) if selection else box(*scene['viewport_mm']);records=[];target_ids=[]
    for r in scene['objects']:
        if r['kind']!='trace':continue
        md=r['metadata'];records.append(dict(source_id=r['source_id'],native_source_ids=md['reference_source_ids'],land_ids=md['land_ids'],disposition='ADMIT_SOURCE_CONTACTS',original_ref=r['original_ref'],current_ref=r['geometry_ref'],reference_id=md['reference_id'],reference_status=md['reference_status'],attachments=md['attachments'],T04_disposition=md['T04_disposition']));target_ids.append(r['source_id'])
    members=sorted(s for r in scene['objects'] for s in r['metadata']['native_source_ids'])
    return scene,dict(routes=records,target_ids=target_ids,source_ids=sorted(r['source_id'] for r in scene['objects']),native_source_ids=members,selection=selection,write_bounds=list(write.bounds),reference_clusters=97,required_reference_attachments=162)
