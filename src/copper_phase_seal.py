"""Immutable, hash-pinned phase I/O. No geometry construction or acceptance.

The producer owns its job. Consumers read only the declared artifact closure.
Shared native search preparation stays with CopperContext, outside both jobs.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import uuid

from src.large_copper_runner import workspace_path, read_file
from src.viewer_abi.publisher import encode, digest

SCHEMA = 'pcb-copper-phase-seal/2'
POLICIES = ('LEGACY_REFERENCE_JOB.json', 'SOURCE_ASSEMBLY_BINDING.json',
            'PIN_SEPARATION_POLICY.json', 'T04_SETTINGS_SNAPSHOT.json',
            'TRACE_GROWTH_ELIGIBILITY_SNAPSHOT.json', 'T04_PASS_SCHEDULE.json',
            'HOLE_ACCEPTANCE_SNAPSHOT.json', 'STORAGE_ENCODING.json')


def file_sha(path):
    path=Path(path)
    if path.is_symlink():raise ValueError('PHASE_SEAL_LINK_FORBIDDEN')
    h=hashlib.sha256()
    with path.open('rb')as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def reference(path):
    path=workspace_path(path)
    return dict(path=str(path),sha256=file_sha(path))


def _path(root,name):
    p=Path(name)
    if p.is_absolute()or p.as_posix()!=name or '..'in p.parts:
        raise ValueError('PHASE_SEAL_RELATIVE_FILE_REQUIRED')
    target=root/p
    if not target.resolve().is_relative_to(root)or any(q.is_symlink()for q in [target,*target.parents]if q!=root and q.is_relative_to(root)):
        raise ValueError('PHASE_SEAL_LINK_OR_ESCAPE')
    return target


def _inspect(job,phase,parent=None):
    """Reconstruct the reachable byte closure and ordered geometry identities."""
    job=workspace_path(job);files={}
    def local(name,maximum=1024**3):
        path=_path(job,name);raw=read_file(path,maximum)
        files[name]=digest(raw);return raw
    def artifact(ref,kind=None):
        sha=ref['sha256'];kind=kind or ref['artifact_id'].split(':',1)[0]
        if len(sha)!=64 or any(c not in '0123456789abcdef'for c in sha)or ref['artifact_id']!=kind+':'+sha:
            raise ValueError('PHASE_SEAL_ARTIFACT_REFERENCE_INVALID')
        name='runtime/artifacts/'+ref['artifact_id'];path=_path(job,name)
        if kind=='geometry'and files.get(name)==sha:return b''
        if path.exists():raw=local(name)
        elif parent is not None:
            if parent['files'].get(name)!=sha:raise ValueError('PHASE_SEAL_PARENT_ARTIFACT_NOT_DECLARED')
            raw=read_file(_path(Path(parent['job']),name),1024**3)
        else:raise ValueError('PHASE_SEAL_ARTIFACT_MISSING')
        if digest(raw)!=sha:raise ValueError('PHASE_SEAL_ARTIFACT_CHANGED')
        return raw
    result=json.loads(local('RESULT.json'));binding=json.loads(local('source.json'))
    source=artifact(binding['source_ref'],'gerber-source');source_sha=digest(source)
    scene=json.loads(artifact(binding['scene_ref'],'scene'))
    if scene['source_sha256']!=source_sha:raise ValueError('PHASE_SEAL_SOURCE_BINDING_CHANGED')
    def identities(value):
        if value['source_sha256']!=source_sha:raise ValueError('PHASE_SEAL_SCENE_SOURCE_CHANGED')
        ids=[];seen=set()
        for row in value['objects']:
            sid=row['source_id']
            if sid in seen:raise ValueError('PHASE_SEAL_DUPLICATE_SOURCE')
            seen.add(sid)
            artifact(row['geometry_ref'],'geometry');artifact(row['original_ref'],'geometry')
            ids.append([sid,row['geometry_ref']['sha256']])
        return ids
    original=identities(scene)
    visited=set()
    def closure(value):
        if isinstance(value,dict):
            if 'artifact_id'in value and 'sha256'in value:
                identity=value['artifact_id']
                if identity in visited:return
                visited.add(identity);raw=artifact(value)
                if raw[:1]in(b'{',b'['):closure(json.loads(raw))
            else:
                for item in value.values():closure(item)
        elif isinstance(value,list):
            for item in value:closure(item)
    # Width metadata/catalogue refs are source inputs too, even when their
    # native geometry refs already occurred in the original scene.
    closure(binding);closure(scene)
    ref=result['stage'];path=Path(ref['path']).resolve()
    if not path.is_relative_to(job):raise ValueError('PHASE_SEAL_CONSTRUCTION_OUTSIDE_PRODUCER')
    name=path.relative_to(job).as_posix()
    if file_sha(path)!=ref['sha256']:raise ValueError('PHASE_SEAL_CONSTRUCTION_CHANGED')
    files[name]=ref['sha256'];canonical=hashlib.sha256()
    with gzip.open(path,'rb')as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):canonical.update(block)
    if canonical.hexdigest()!=ref['stage_sha256']:raise ValueError('PHASE_SEAL_CANONICAL_CONSTRUCTION_CHANGED')
    if phase=='large_copper':
        if parent is not None or result.get('schema')!='large-copper-execution/1'or result['status']not in('COMPLETED_FOR_PROFILE','COMPLETED_WITH_UNRESOLVED'):
            raise ValueError('PHASE_SEAL_COMPLETED_CLEANUP_REQUIRED')
        stage=json.loads(gzip.decompress(read_file(path,1024**3)))
        if binding.get('input_assembly')is not None:
            from src.large_copper_runner import authenticate_assembly
            from src.gerber_u05.pipeline import Store
            assembly=authenticate_assembly(job,binding,result,Store(job/'runtime'))
            raw_path=Path(result['original_input']['path']).resolve()
            local(raw_path.relative_to(job).as_posix())
        else:assembly=None
        proof=stage['trim_only_phase']
        if (stage['operation']!='TRIM_ONLY'or stage['input_binding']['scene_ref']!=binding['scene_ref']or
            stage['input_binding']['source_sha256']!=source_sha or proof['passed']is not True or
            proof['positive_copper_mm2']!=0 or stage['batch_proof']['passed']is not True or
            proof['all_rectangles_preserved']is not True or proof['topology_before']!=proof['topology_after']or
            any(r.get('passed')is not True for r in stage['large_copper_cleanup']['records'])):
            raise ValueError('PHASE_SEAL_TRIM_ONLY_PROOF_REQUIRED')
        if stage['ordered_source_ids']!=[s for s,_ in original]:raise ValueError('PHASE_SEAL_SOURCE_ORDER_CHANGED')
        changes=dict(stage['hybrid_components']['continuous_source_bodies']);changes.update(stage['hybrid_components']['changed_bulk_copper'])
        if not set(changes)<={s for s,_ in original}:raise ValueError('PHASE_SEAL_FOREIGN_SOURCE')
        output=[[s,digest(bytes.fromhex(changes[s]['wkb_hex']))if s in changes else h]for s,h in original]
        for field in('source','source_binding'):
            bound=result[field];p=Path(bound['path']).resolve()
            if not p.is_relative_to(job)or digest(local(p.relative_to(job).as_posix()))!=bound['sha256']:
                raise ValueError('PHASE_SEAL_CLEANUP_REFERENCE_CHANGED')
        preparation=result.get('diagnostics',{}).get('context')
        summary=dict(status=result['status'],counts=result['counts'],unresolved_preserved=True,
                     treatment_complete=result.get('treatment_complete',False))
        if assembly is not None:summary['input_assembly']=dict(policy=assembly['policy'],
            removed_objects=assembly['removed_objects'],raw_source_sha256=assembly['raw_source_sha256'])
    elif phase=='t04':
        if parent is None or parent['phase']!='large_copper'or parent['source_sha256']!=source_sha:
            raise ValueError('PHASE_SEAL_T04_CLEANUP_PARENT_REQUIRED')
        if result['status']not in('FULL_BOARD_T04_AFTER_CLEANUP_DIAGNOSTIC_COMPLETE','BOUNDED_T04_PARITY_ARM_COMPLETE'):
            raise ValueError('PHASE_SEAL_COMPLETED_T04_REQUIRED')
        if 'completion'in result:
            if (result['completion']not in('COMPLETED','COMPLETED_WITH_REVIEW_FINDINGS')or
                    result.get('output_valid')is not True or result['checks'].get('output_valid')is not True or
                    result.get('board_outline')is not None and result['board_outline'].get('output_valid')is not True):
                raise ValueError('PHASE_SEAL_VALID_T04_OUTPUT_REQUIRED')
        if result['inputs']['cleanup'].get('seal')!=parent['_reference']:
            raise ValueError('PHASE_SEAL_T04_PARENT_CHANGED')
        entry=identities(json.loads(artifact(result['inputs']['trimmed_entry_scene_ref'],'scene')))
        if digest(encode(entry))!=parent['output_geometry_sha256']:
            raise ValueError('PHASE_SEAL_T04_ENTRY_DIFFERS_FROM_CLEANUP_OUTPUT')
        output=identities(json.loads(artifact(result['assembly']['scene_ref'],'scene')))
        closure(json.loads(artifact(result['inputs']['trimmed_entry_scene_ref'],'scene')))
        closure(json.loads(artifact(result['assembly']['scene_ref'],'scene')))
        # Revision-4 comparisons are saved phase operands too. Authenticate
        # their WKB closure along with the serialized source assembly. Older
        # seals retain their historical file inventory unchanged.
        if (result.get('board_outline')or{}).get('shoulder_baseline_ref'):
            closure(result['board_outline'])
        local('JOB.json')
        if [s for s,_ in output]!=[s for s,_ in original]:raise ValueError('PHASE_SEAL_SOURCE_ORDER_CHANGED')
        preparation=(result.get('shared_copper')or{}).get('context')
        summary=dict(status=result['status'],scope=result['scope'],checks=result['checks'],
                     complete_t04=result['complete_t04'],export=result['export'])
        if 'completion'in result:
            summary.update(completion=result['completion'],review_finding_count=len(result['review_findings']),
                           output_valid=result['output_valid'])
    else:raise ValueError('PHASE_SEAL_UNKNOWN_PHASE')
    policy_presence={name:(_path(job,name).exists())for name in POLICIES}
    for name,present in policy_presence.items():
        if present:local(name)
    return dict(schema=SCHEMA,phase=phase,job=str(job),source_sha256=source_sha,
        original_scene_ref=binding['scene_ref'],source_order_sha256=digest(encode([s for s,_ in original])),
        coordinate_contract=dict(frame=scene['frame'],units=scene['units'],selected_layer=scene['layer'],
                                 oracle=binding.get('coordinate_oracle')),
        artifact_closure='RECURSIVE_BINDING_AND_SCENES',
        original_geometry_sha256=digest(encode(original)),output_geometry_sha256=digest(encode(output)),
        occurrence_count=len(original),files=dict(sorted(files.items())),policy_presence=policy_presence,
        parent=None if parent is None else parent['_reference'],shared_preparation_key=preparation,
        native_handles='PROCESS_LOCAL; RECONSTRUCT_ONCE_PER_PHASE_WORKER',
        summary=summary,acceptance='SAVED_PHASE_CUSTODY_ONLY; NO_PROMOTION')


def verify(path,sha256,*,phase=None):
    """Authenticate a caller-pinned closure, without replaying producer checks."""
    path=workspace_path(path);raw=read_file(path)
    if digest(raw)!=sha256:raise ValueError('PHASE_SEAL_DIGEST_CHANGED')
    saved=json.loads(raw)
    if saved.get('schema')!=SCHEMA or phase is not None and saved['phase']!=phase:
        raise ValueError('PHASE_SEAL_TYPE_CHANGED')
    parent=None
    if saved['phase']=='t04':
        ref=saved['parent'];parent=verify(ref['path'],ref['sha256'],phase='large_copper')
    elif saved['phase']!='large_copper'or saved['parent']is not None:
        raise ValueError('PHASE_SEAL_PARENT_INVALID')
    job=workspace_path(saved['job'])
    if not {'RESULT.json','source.json'}<=set(saved['files']):raise ValueError('PHASE_SEAL_INCOMPLETE_FILE_CLOSURE')
    for name,sha in saved['files'].items():
        if file_sha(_path(job,name))!=sha:raise ValueError('PHASE_SEAL_DEPENDENCY_CHANGED:'+name)
    if {name:_path(job,name).exists()for name in POLICIES}!=saved['policy_presence']:
        raise ValueError('PHASE_SEAL_POLICY_INVENTORY_CHANGED')
    if parent is not None and (saved['source_sha256']!=parent['source_sha256']or saved['source_order_sha256']!=parent['source_order_sha256']):
        raise ValueError('PHASE_SEAL_PARENT_BINDING_CHANGED')
    return dict(saved,_reference=dict(path=str(path),sha256=sha256))


def publish(job,path,*,phase='large_copper',parent_ref=None):
    """Atomic create-only commit. Interrupted partial files are retained."""
    target=workspace_path(path)
    if target.exists():raise FileExistsError('PHASE_SEAL_ALREADY_EXISTS')
    parent=None if parent_ref is None else verify(parent_ref['path'],parent_ref['sha256'],phase='large_copper')
    payload=_inspect(job,phase,parent);raw=encode(payload)
    for name,sha in payload['files'].items():
        if file_sha(_path(Path(payload['job']),name))!=sha:raise ValueError('PHASE_SEAL_PRODUCER_CHANGED_DURING_PUBLICATION')
    target.parent.mkdir(parents=True,exist_ok=True)
    partial=target.with_name('.'+target.name+'.'+uuid.uuid4().hex+'.partial')
    with partial.open('xb')as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    # Link publishes a complete file without replacing another producer's seal.
    os.link(partial,target);partial.unlink()
    fd=os.open(target.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(path=str(target),sha256=digest(raw))
