"""Receipt-bound common-context projection for the existing read-only workbench."""
import copy
import json
import re
from pathlib import Path
import shutil
from shapely import from_wkb
from .common_catalogue import retrieve,validate_positive,require
from .ingestion_files import local,sha,verify,write_json


def semantic_result(result):
    return {k:v for k,v in result.items() if k!='reader_pid'}


def storage_themes(catalog,revision,result):
    """Describe actual persisted structures; distinguish rebuilt spatial indexes."""
    envelope=json.loads(catalog.read_payload(revision))
    artifacts=[]
    for role,artifact in sorted(envelope['artifacts'].items()):
        manifest=catalog.snapshot(artifact['revision'])
        artifacts.append({'role':role,'revision':artifact['revision'],'source_sha256':artifact['source_sha256'],
                          'path':artifact.get('path'),'source_bytes':len(catalog.read_payload(artifact['source_sha256'])),
                          'objects':len(manifest['objects'])})
    counts={table:catalog.db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('revisions','objects','relations')}
    indexes=[dict(row) for row in catalog.db.execute("SELECT name,tbl_name,sql FROM sqlite_master WHERE type='index' ORDER BY name")]
    payloads=list(catalog.payloads.iterdir())
    geometry_keys={r[key]['geometry_sha256'] for r in result['roles'] for key in ('native','plotted')}
    return {'schema':'pcb-storage-themes/1','artifacts':artifacts,'sqlite':{'path':'common_context/selection/store/catalog.sqlite',
            'sha256':sha(catalog.root/'catalog.sqlite'),'counts':counts,'indexes':indexes},
            'payloads':{'path':'common_context/selection/store/payloads/','count':len(payloads),
                        'bytes':sum(p.stat().st_size for p in payloads),'selected_geometry_payloads':len(geometry_keys)},
            'sidecars':{key:envelope[key] for key in ('links','qualifications','relationships')},
            'spatial':{'persistence':'REBUILT_IN_MEMORY_ON_REOPEN','backend':result['relationships']['contact']['backend'],
                       'indexed_native_shapes':sum(bool(r.get('geometry_sha256')) for r in catalog.snapshot(envelope['artifacts']['native']['revision'])['objects'])},
            'scope':'Counts describe the exported bounded store; spatial indexes are rebuilt, not persisted R-tree files.'}


def project(bundle, acceptance, *, themes=False):
    result=retrieve(bundle,acceptance['dataset_revision']);validate_positive(result)
    require(acceptance.get('status')=='PASS' and acceptance.get('schema')=='pcb-common-context/1','INVALID_REOPEN_ACCEPTANCE')
    require(result['result_sha256']==acceptance.get('result_sha256'),'REOPEN_RESULT_MISMATCH')
    pids=[acceptance.get(k) for k in ('writer_pid','reader_pid','export_reader_pid')]
    require(all(isinstance(p,int) and p>0 for p in pids) and len(set(pids))==3,'MISSING_FRESH_PROCESS_EXECUTION')
    from .revision_catalog import RevisionCatalog
    paths={}
    with RevisionCatalog(Path(bundle)/'store',read_only=True) as cat:
        for row in result['roles']:
            for record in (row['native'],row['plotted']):
                key=record['geometry_sha256']
                # SVG path comes directly from stored WKB; no scene-authored measurements.
                paths[key]=' '.join(re.findall(r' d="([^"]+)"',from_wkb(cat.read_payload(key)).svg(scale_factor=.01)))
        infrastructure=storage_themes(cat,acceptance['dataset_revision'],result) if themes else None
    projection={'mode':'REPLAY','dataset_id':result['dataset_id'],'result':semantic_result(result),'geometry_svg':paths,
            'execution':{k:acceptance[k] for k in ('writer_pid','reader_pid','export_reader_pid','dataset_revision','result_sha256','scope')},
            'evidence':{'acceptance':'common_context/acceptance.json','selection':'common_context/selection/dataset.json',
                        'receipt':'common_context/selection/receipt.json','result':'common_context/result.json'},
            'source_run':acceptance['run'],'export_scope':'8 selected source occurrences and complete original artifacts; diagnostic only'}
    if infrastructure is not None:projection['themes']=infrastructure
    return projection


def copy_projection(root,config,scene,stage):
    binding=config.get('common_context')
    if not binding:return []
    acceptance_path=local(root,binding['path']);verify(root,[binding])
    acceptance=json.loads(acceptance_path.read_text())
    # A removed dropdown registration stays removed. Retain the binding so +
    # can reconstruct the view from inputs without deleting catalogue history.
    if not any(d['id']=='client:vme-wren:20261016:v1' for d in config['datasets']):return [binding]
    source=acceptance_path.parent/'selection'
    require(source.is_relative_to(root/'out'),'CONTEXT_SELECTION_OUTSIDE_OUTPUTS')
    target=stage/'common_context';target.mkdir()
    shutil.copytree(source,target/'selection');shutil.copyfile(acceptance_path,target/'acceptance.json')
    scene['common_context']=project(target/'selection',acceptance,themes=config.get('common_context_presentation')=='storage-themes-v1')
    write_json(target/'result.json',scene['common_context']['result'])
    return [binding]


def verify_projection(bundle,config,scene):
    binding=config.get('common_context');shown=scene.get('common_context')
    expected=binding and any(d['id']=='client:vme-wren:20261016:v1' for d in config['datasets'])
    require(bool(shown)==bool(expected),'MISSING_OR_UNEXPECTED_COMMON_CONTEXT')
    if not expected:return
    acceptance_path=Path(bundle)/'common_context/acceptance.json'
    require(sha(acceptance_path)==binding['sha256'],'COMMON_CONTEXT_ACCEPTANCE_BINDING_MISMATCH')
    acceptance=json.loads(acceptance_path.read_text())
    profile=config.get('common_context_presentation')
    require(profile in (None,'storage-themes-v1'),'UNSUPPORTED_COMMON_CONTEXT_PRESENTATION')
    require(shown==project(Path(bundle)/'common_context/selection',acceptance,themes=profile=='storage-themes-v1'),'COMMON_CONTEXT_PROJECTION_MISMATCH')
    require(shown['result']==json.loads((Path(bundle)/'common_context/result.json').read_text()),'COMMON_CONTEXT_RESULT_FILE_MISMATCH')
