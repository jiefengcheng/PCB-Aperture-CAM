"""Immutable source copper roles, resolved before mutable-route selection.

A role table binds the complete accepted predecessor, original owner geometry,
exact classifier implementation and GEOS backend. It never contains accepted
T04 widths. Role projection preserves the original native path inventory while
identifying which source occurrences remain trace growth cores.
"""
from collections import Counter
import ast,copy,gzip,hashlib,json
from pathlib import Path
import shapely
from src.filled_copper_source_role import PreparedBulkBoundary

ROLE_SCHEMA='t04-source-role-preparation/1'
PROJECTION_SCHEMA='t04-native-trace-bulk-projection/1'


def classifier_signature():
    module=Path(__file__).resolve().parents[1]/'filled_copper_source_role.py'
    return hashlib.sha256(module.read_bytes()).hexdigest()


def admission_signature():
    root=Path(__file__).resolve().parents[1]
    source=Path(__file__).with_name('pipeline.py').read_text()
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='width_admission')
    lines=source.splitlines()
    parts=['\n'.join(lines[node.lineno-1:node.end_lineno])]
    for name in ('source_junction_paths.py','parallel_trace_relations.py','u03_board/source.py','gerber_u05/source_catalogue.py'):
        parts.append((root/name).read_text())
    return hashlib.sha256('\n'.join(parts).encode()).hexdigest()


def classify(rows,original,index,outline_area):
    large={i for i,g in enumerate(index.owners) if g.area>outline_area*.05}
    prepared={i:PreparedBulkBoundary(index.owners[i]) for i in large}
    roles={}
    for sid,row in sorted(rows.items()):
        if row['kind']!='stroke':continue
        for i in sorted(large.intersection(map(int,index.tree.query(original[sid],predicate='intersects')))):
            md=row['metadata']
            witness=prepared[i].witness(sid,md['route_points_mm'],md['minimum_caliper_mm'])
            if witness is not None:
                roles[sid]=dict(owner_id=index.ids[i],**witness)
                break
    return roles


def path_class(members,roles):
    hits=sum(s in roles for s in members)
    return 'bulk_only' if hits==len(members) else 'mixed' if hits else 'trace_only'


def trace_edges(path,roles):
    result=[]
    for edge in path.get('ordered_source_edges',[]):
        ids=[s for s in edge['source_alias_ids'] if s not in roles]
        if not ids:continue
        value=copy.deepcopy(edge);value['source_alias_ids']=ids
        if value['representative_source_id'] not in ids:value['representative_source_id']=ids[0]
        result.append(value)
    return result


def project(admission,roles):
    """Keep native identity and inventory; grow only non-bulk source members."""
    result=copy.deepcopy(admission)
    dispositions={}
    for decision in result['paths']:
        path=decision['path'];members=path['source_ids']
        decision['source_role']=path_class(members,roles)
        decision['growth_source_ids']=[s for s in members if s not in roles]
        decision['growth_source_edges']=trace_edges(path,roles)
        decision['editable_bulk_source_ids']=[s for s in members if s in roles]
        dispositions[path['path_id']]=decision['source_role']
    projected=[]
    for path in admission['admitted']:
        members=path['source_ids'];trace=[s for s in members if s not in roles]
        if not trace:continue
        value=copy.deepcopy(path)
        value.update(native_source_ids=list(members),source_ids=trace,
                     role_projection=PROJECTION_SCHEMA,source_role=path_class(members,roles),growth_source_edges=trace_edges(path,roles))
        projected.append(value)
    result['admitted']=projected
    # These remain source metadata, not a dynamic clearance exemption.
    result['native_groups']=result['groups']
    real={v['path_id'] for v in projected}
    result['groups']=[dict(g,members=[r for r in g['members'] if r in real]) for g in result['groups']]
    result['groups']=[g for g in result['groups'] if g['members']]
    result['role_projection_schema']=PROJECTION_SCHEMA
    result['source_role_dispositions']=dispositions
    raw=[s for d in admission['paths'] for s in d['path']['source_ids']]
    retained=[s for d in result['paths'] for s in d['path']['source_ids']]
    if raw!=retained or len(raw)!=len(set(raw)):raise ValueError('T04_ROLE_SOURCE_INVENTORY_CHANGED')
    return result


def load_preparation(directory,scene_sha,source_sha,index_fingerprint):
    """Exact cache binding; stale or altered data is an explicit miss/error."""
    root=Path(directory)
    binding=json.loads((root/'BINDING.json').read_text())
    expected=dict(schema=ROLE_SCHEMA,scene_sha256=scene_sha,source_sha256=source_sha,
        owner_fingerprint=index_fingerprint,classifier_sha256=classifier_signature(),admission_sha256=admission_signature(),
        shapely_version=shapely.__version__,geos_version=shapely.geos_version_string)
    if any(binding.get(k)!=v for k,v in expected.items()):raise ValueError('T04_SOURCE_ROLE_PREPARATION_BINDING_CHANGED')
    data={}
    for name in ('ROLES.json.gz','admission.json.gz'):
        raw=(root/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=binding['files'][name]:raise ValueError('T04_SOURCE_ROLE_PREPARATION_BYTES_CHANGED')
        data[name]=json.loads(gzip.decompress(raw))
    return data['ROLES.json.gz']['roles'],data['admission.json.gz'],binding


def prepare_or_load(directory,store,scene,loaded,index):
    """Build source-only preparation once in the caller, or verify its cache.

    The exclusive directory and binding-last publication keep incomplete builds
    visibly failed. No accepted growth decisions are stored in this artifact.
    All file and native geometry bindings are checked again on the first read.
    """
    from . import pipeline as p
    root=Path(directory)
    scene_sha=p.digest(p.canonical(scene));source_sha=scene['source_sha256']
    if not root.exists():
        root.mkdir(parents=False,exist_ok=False)
        rows,current,original=loaded
        admission=p.width_admission(store,scene,loaded=loaded)
        area=(scene['viewport_mm'][2]-scene['viewport_mm'][0])*(scene['viewport_mm'][3]-scene['viewport_mm'][1])
        roles=classify(rows,original,index,area)
        classes={v['path_id']:path_class(v['source_ids'],roles) for v in admission['admitted']}
        files={'ROLES.json.gz':dict(roles=roles,classes=classes),'admission.json.gz':admission}
        hashes={}
        for name,value in files.items():
            raw=gzip.compress(p.canonical(value),mtime=0)
            (root/name).write_bytes(raw);hashes[name]=hashlib.sha256(raw).hexdigest()
        binding=dict(schema=ROLE_SCHEMA,scene_sha256=scene_sha,source_sha256=source_sha,
            owner_fingerprint=index.fingerprint,classifier_sha256=classifier_signature(),admission_sha256=admission_signature(),
            shapely_version=shapely.__version__,geos_version=shapely.geos_version_string,files=hashes)
        (root/'BINDING.json').write_text(json.dumps(binding,indent=2,sort_keys=True)+'\n')
    return load_preparation(root,scene_sha,source_sha,index.fingerprint)
