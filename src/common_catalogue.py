"""Bounded, durable multi-artifact context over the existing revision catalogue.

Dataset links/qualifications are CAS sidecars. Same-artifact SQL foreign keys
remain unchanged. Retrieval opens SQLite read-only and never invokes extraction.
"""
import copy
import json
import math
import os
from pathlib import Path
import shutil
import uuid

from shapely import from_wkb
import shapely
from .revision_catalog import RevisionCatalog, CatalogError, canonical, digest
from .ingestion_files import local, sha, verify, write_json
from .spatial_context import SpatialContext

SCHEMA='pcb-common-context/1'
PROFILE_PATH='contracts/common_catalogue_r140_v1.json'
CORE_SOURCES=(
    'src/common_catalogue.py','src/catalogue_build.py','src/catalogue_native.py',
    'src/catalogue_gerber.py','src/revision_catalog.py','src/source_locators.py',
    'src/catalog_selection.py','src/spatial_context.py','src/native_inventory.py',
    'src/native_reference.py','src/gerber_image.py','src/validator.py',
    'tools/common_catalogue.py',PROFILE_PATH,'requirements.lock.txt',
    'src/directory_intake.py','src/ingestion_files.py','contracts/ingestion_packages_v1.json',
    'src/catalogue_qualifications.py',
)


def require(condition, reason):
    if not condition:raise CatalogError(reason)


def geometry(catalog, record):
    key=record.get('geometry_sha256')
    require(key is not None,'GEOMETRY_UNAVAILABLE')
    shape=from_wkb(catalog.read_payload(key))
    require(not shape.is_empty and shape.is_valid,'INVALID_GEOMETRY')
    require(list(shape.bounds)==record['bounds_mm'],'GEOMETRY_BOUNDS_MISMATCH')
    return shape


def match_witness(catalog, native, plotted, tolerance):
    """Nominal shape and anchors; source annotations are corroborating only."""
    a=geometry(catalog,native);b=geometry(catalog,plotted)
    error=native['geometry_error_mm']+plotted['geometry_error_mm']
    require(0<=error<tolerance,'INVALID_GEOMETRY_ERROR_BUDGET')
    hausdorff=a.hausdorff_distance(b)
    if native.get('position_mm') is not None and plotted.get('position_mm') is not None:
        anchor=math.dist(native['position_mm'],plotted['position_mm'])
    elif native.get('endpoints_mm') and plotted.get('endpoints_mm'):
        x=native['endpoints_mm'];y=plotted['endpoints_mm']
        anchor=min(max(math.dist(x[0],y[0]),math.dist(x[1],y[1])),max(math.dist(x[0],y[1]),math.dist(x[1],y[0])))
    else:anchor=math.inf
    return {'status':'VERIFIED_IN_SCOPE' if max(hausdorff,anchor)+error<=tolerance else 'MISMATCH',
            'predicate':'Unique source candidates; anchor/endpoints and GEOS Hausdorff plus approximation budget <= tolerance',
            'tolerance_mm':tolerance,'composition_error_mm':error,'hausdorff_mm':hausdorff,
            'anchor_or_endpoints_mm':anchor,'symmetric_difference_mm2':a.symmetric_difference(b).area}


def relationships(catalog, native_revision, rows, roles, nearby):
    payloads={r['geometry_sha256']:catalog.read_payload(r['geometry_sha256']) for r in rows if r.get('geometry_sha256')}
    index=SpatialContext(native_revision,rows,payloads)
    target=roles['R140.1'];trace=roles['connected_trace'];neighbor=roles['R140.2']
    contact=index.query(target,'B.Cu');proximity=index.query(target,'B.Cu',distance_mm=nearby)
    topology=index.topology()
    group=next(c for c in topology['components'] if target in c['members'])
    require(contact['complete'] and proximity['complete'],'INCOMPLETE_RELATION_QUERY')
    require({h['id'] for h in contact['matches']}=={trace},'REQUIRED_TRACE_CONTACT_OR_NEIGHBOR_SEPARATION_FAILED')
    require(set(group['members'])=={target,trace},'INVALID_CONTACT_GROUP')
    require(neighbor in {h['id'] for h in proximity['matches']},'NEIGHBOR_OUTSIDE_CONTEXT_DISTANCE')
    return {'contact':contact,'proximity':proximity,'group':group,'topology':topology,
            'footprint_ownership':'Parent dependency; distinct from physical contact and native PCB_GROUP',
            'writable_ids':[],'scope':'Selected nominal B.Cu objects only; no independent electrical intent or full-board connectivity'}


def stable_relationships(value):
    # Runtime cost is execution evidence, not semantic selection identity.
    if isinstance(value,dict):return {k:stable_relationships(v) for k,v in value.items() if k!='elapsed_seconds'}
    if isinstance(value,list):return [stable_relationships(v) for v in value]
    return value


def verify_bundle(bundle, expected_revision=None):
    """Fail closed on failed/empty receipts, missing files and changed payloads."""
    bundle=Path(bundle).resolve();receipt=json.loads((bundle/'receipt.json').read_text())
    require(receipt.get('schema')==SCHEMA and receipt.get('status')=='PASS','INVALID_CONTEXT_RECEIPT')
    outputs=receipt.get('outputs')
    require(isinstance(outputs,dict) and {'dataset.json','store/catalog.sqlite'}<=outputs.keys(),'MISSING_CONTEXT_OUTPUTS')
    actual={str(p.relative_to(bundle)) for p in bundle.rglob('*') if p.is_file()}
    require(actual==set(outputs)|{'receipt.json'},'CONTEXT_INVENTORY_MISMATCH')
    verify(bundle,[{'path':p,'sha256':h} for p,h in outputs.items()])
    pointer=json.loads((bundle/'dataset.json').read_text());revision=pointer.get('dataset_revision')
    require(revision==receipt.get('dataset_revision'),'CONTEXT_REVISION_MISMATCH')
    if expected_revision is not None:require(revision==expected_revision,'STALE_MIXED_DATASET_REVISION')
    with RevisionCatalog(bundle/'store',read_only=True) as catalog:
        envelope=json.loads(catalog.read_payload(revision))
        require(canonical(envelope)==catalog.read_payload(revision),'NONCANONICAL_DATASET_MANIFEST')
        require(envelope.get('schema')==SCHEMA,'INVALID_DATASET_SCHEMA')
        require(catalog.read_payload(envelope['profile_sha256'])==canonical(envelope['profile']),'DATASET_PROFILE_HASH_MISMATCH')
        require(envelope['dataset_id']==envelope['profile'].get('dataset_id',envelope['dataset_id']),'DATASET_ID_MISMATCH')
        require(isinstance(envelope.get('artifacts'),dict) and {'native','copper','mask'}<=envelope['artifacts'].keys(),'MISSING_ARTIFACTS')
        for artifact in envelope['artifacts'].values():
            manifest=catalog.snapshot(artifact['revision'])
            require(manifest['source_sha256']==artifact['source_sha256'],'MIXED_ARTIFACT_SOURCE')
            for record in manifest['objects']:
                if record.get('geometry_sha256'):geometry(catalog,record)
        for name in ('links','qualifications','relationships'):
            require(name in envelope,'MISSING_'+name.upper())
            value=json.loads(catalog.read_payload(envelope[name]))
            require(bool(value),'EMPTY_'+name.upper())
        require(receipt.get('implementation')==envelope.get('implementation') and bool(receipt.get('implementation')),'MISSING_IMPLEMENTATION_BINDINGS')
    return envelope


def retrieve(bundle, expected_revision=None):
    """Four-role query by persisted fields. No source parser or write connection."""
    envelope=verify_bundle(bundle,expected_revision);bundle=Path(bundle)
    with RevisionCatalog(bundle/'store',read_only=True) as catalog:
        profile=envelope['profile'];artifacts=envelope['artifacts'];roles=envelope['roles'];objects={};selections={}
        require(set(roles)==set(profile['roles']),'OMITTED_OR_UNEXPECTED_CONTEXT_ROLE')
        for name in ('native','copper','mask'):
            artifact=artifacts[name];snapshot=catalog.snapshot(artifact['revision'])
            require(snapshot['config']['profile_sha256']==envelope['profile_sha256'],'MIXED_ARTIFACT_PROFILE')
            objects[name]={r['id']:r for r in snapshot['objects']}
        def unique(name,props,layer):
            q=catalog.query(artifacts[name]['revision'],properties=props,layer=layer,limit=2)
            require(q['complete'] and len(q['records'])==1,'AMBIGUOUS_OR_MISSING_CONTEXT_REFERENCE')
            return q['records'][0]
        reference=profile['component']
        native_roles={'R140.1':unique('native',{'kind':'pad','reference':reference,'pin':'1'},'B.Cu'),
                      'R140.2':unique('native',{'kind':'pad','reference':reference,'pin':'2'},'B.Cu')}
        trace=catalog.query(artifacts['native']['revision'],native_id=profile['trace_uuid'],limit=2,layer='B.Cu')
        require(trace['complete'] and len(trace['records'])==1,'AMBIGUOUS_OR_MISSING_CONTEXT_TRACE')
        native_roles['connected_trace']=trace['records'][0];native_roles['mask_opening']=native_roles['R140.1']
        for role,row in native_roles.items():require(row['id']==roles[role]['native'],'ROLE_RESOLUTION_MISMATCH')
        parent=unique('native',{'kind':'footprint','reference':reference},'B.Cu')
        require(all(native_roles[r]['parent_id']==parent['id'] for r in ('R140.1','R140.2')),'MISSING_CONTEXT_PARENT')
        require(set(objects['native'])=={parent['id'],*(r['id'] for r in native_roles.values())},'UNEXPECTED_NATIVE_SLICE')
        links=json.loads(catalog.read_payload(envelope['links']));quals=json.loads(catalog.read_payload(envelope['qualifications']))
        require(set(links)==set(roles),'MISSING_CORRESPONDENCE')
        from .catalogue_qualifications import validate_qualifications
        validate_qualifications(catalog,envelope,quals)
        result=[]
        for role in profile['roles']:
            binding=roles[role];name='mask' if role=='mask_opening' else 'copper';native=native_roles[role]
            require(binding['plotted'] in objects[name],'MISSING_PLOTTED_ROLE')
            plotted=objects[name][binding['plotted']];link=links[role]
            require(link['native_revision']==artifacts['native']['revision'] and link['plotted_revision']==artifacts[name]['revision'],'MIXED_CORRESPONDENCE_REVISION')
            require(link['native']==native['id'] and link['plotted']==plotted['id'],'CORRESPONDENCE_ENDPOINT_MISMATCH')
            deps=plotted['state_dependencies'];source=catalog.read_payload(plotted['source_sha256'])
            require(deps['source_sha256']==plotted['source_sha256'] and deps['interpretation_prefix_span']==[0,plotted['source_span'][1]],'INVALID_GERBER_DEPENDENCY')
            require(digest(source[:plotted['source_span'][1]])==deps['prefix_sha256'],'GERBER_STATE_PREFIX_MISMATCH')
            if role=='mask_opening':
                require('B.Mask' in native['layers'] and envelope.get('mask_expectation',{}).get('resolved_margin_mm')==0,'MASK_GEOMETRY_NOT_QUALIFIED')
                require(link['type']=='opening_for','INVALID_OPENING_RELATION')
            witness=match_witness(catalog,native,plotted,profile['match_tolerance_mm'])
            require(witness==link['witness'],'STALE_MATCH_WITNESS')
            record={'role':role,'native_revision':artifacts['native']['revision'],'plotted_revision':artifacts[name]['revision'],
                    'native':native,'plotted':plotted,'match':copy.deepcopy(link),'qualifications':[q for q in quals if 'native' in q['artifact_roles'] or name in q['artifact_roles']],
                    'native_excerpt':catalog.source_record(artifacts['native']['revision'],native['id'])[1].decode(),
                    'plotted_trigger':source[slice(*plotted['source_span'])].decode('ascii')}
            result.append(record)
        require(len({r['plotted']['id'] for r in result})==4,'DUPLICATE_PLOTTED_CONTEXT_ROLE')
        # Check unique source-declared pad references independently of the role map.
        for role,pin in [('R140.1','1'),('R140.2','2')]:
            require(unique('copper',{'kind':'gerber_flash','reference':reference,'pin':pin},'B.Cu')['id']==roles[role]['plotted'],'AMBIGUOUS_PLOTTED_PAD')
        require(len(objects['copper'])==3 and len(objects['mask'])==1,'AMBIGUOUS_PLOTTED_CONTEXT')
        native_ids={r['native'] for r in roles.values()}
        for name in ('native','copper','mask'):
            ids=native_ids if name=='native' else {r['plotted'] for role,r in roles.items() if (role=='mask_opening')==(name=='mask')}
            selection=catalog.select(artifacts[name]['revision'],object_ids=ids)
            require(selection['complete'] and not selection['writable_ids'],'INCOMPLETE_OR_WRITABLE_CONTEXT_SELECTION')
            selections[name]={k:selection[k] for k in ('selected_ids','dependency_ids','writable_ids','result_sha256','complete','diagnostic_only')}
        rel=relationships(catalog,artifacts['native']['revision'],list(objects['native'].values()),
                          {role:r['native'] for role,r in roles.items()},profile['nearby_distance_mm'])
        require(stable_relationships(rel)==json.loads(catalog.read_payload(envelope['relationships'])),'STALE_RELATION_WITNESS')
        content={'schema':SCHEMA,'dataset_id':envelope['dataset_id'],'dataset_revision':digest(canonical(envelope)),
                 'status':'COMPLETE_IN_DECLARED_SCOPE','complete':True,'roles':result,'parent_dependency':parent,
                 'relationships':stable_relationships(rel),'qualifications':quals,'selections':selections,
                 'query':{'reference':reference,'pin':'1','layer':'B.Cu','bounds_mm':profile['region_mm'],'scope':profile['coverage']},
                 'engineering_acceptance':'NOT_ESTABLISHED: no independent net intent, full-board equivalence or manufacturing acceptance'}
        return {**content,'result_sha256':digest(canonical(content)),'reader_pid':os.getpid(),'backend':'sqlite-reference + CAS; read-only reopened connection'}


def validate_positive(result):
    require(result['complete'] and len(result['roles'])==4,'INCOMPLETE_ACCEPTANCE_RESULT')
    require({r['role'] for r in result['roles']}=={'R140.1','R140.2','connected_trace','mask_opening'},'INVALID_ACCEPTANCE_ROLES')
    require(all(r['match']['witness']['status']=='VERIFIED_IN_SCOPE' for r in result['roles']),'CONTEXT_MATCH_NOT_QUALIFIED')
    content={k:v for k,v in result.items() if k not in ('result_sha256','reader_pid','backend')}
    require(digest(canonical(content))==result['result_sha256'],'ACCEPTANCE_RESULT_DIGEST_MISMATCH')


def export_context(bundle, destination, expected_revision):
    result=retrieve(bundle,expected_revision);validate_positive(result)
    destination=Path(destination).resolve();require(not destination.exists(),'EXPORT_DESTINATION_EXISTS')
    # Only this bounded record store is copied; full originals preserve state and
    # source excerpts. This is selective in objects, not a source-size reduction.
    shutil.copytree(bundle,destination)
    return {'schema':SCHEMA,'status':'PASS','dataset_revision':expected_revision,'result_sha256':result['result_sha256'],
            'destination':str(destination),'selected_objects':8,'source_artifacts':'Complete original bytes retained',
            'purpose':'Portable read-only diagnostic selection; not a standalone native board or manufacturing export'}


def finalize_bundle(stage, envelope, implementation):
    stage=Path(stage)
    with RevisionCatalog(stage/'store') as catalog:revision=catalog.put_payload(canonical(envelope))
    write_json(stage/'dataset.json',{'dataset_revision':revision,'schema':SCHEMA})
    receipt={'schema':SCHEMA,'status':'PASS','dataset_revision':revision,'writer_pid':os.getpid(),
             'implementation':implementation,'outputs':{str(p.relative_to(stage)):sha(p) for p in sorted(stage.rglob('*')) if p.is_file()},
             'power_loss_durability':'NOT_ESTABLISHED; committed SQLite and atomic local publication only'}
    write_json(stage/'receipt.json',receipt)
    return revision


def publish(root, destination, *, fail_before_publish=False):
    from .catalogue_build import build
    root=Path(root).resolve();destination=Path(destination).resolve()
    require(destination.is_relative_to(root/'out'),'CATALOGUE_OUTPUT_OUTSIDE_CHECKOUT_OUT')
    destination.mkdir(parents=True,exist_ok=True);stage=destination/('.staging-'+uuid.uuid4().hex);stage.mkdir()
    try:
        implementation={p:sha(root/p) for p in CORE_SOURCES}
        envelope=build(root,stage,implementation)
        revision=finalize_bundle(stage,envelope,implementation)
        result=retrieve(stage,revision);validate_positive(result)
        verify(root,[{'path':p,'sha256':h} for p,h in implementation.items()])
        if fail_before_publish:raise CatalogError('INJECTED_PARTIAL_PUBLICATION_FAILURE')
        target=destination/('run-'+uuid.uuid4().hex);stage.rename(target)
        pointer=destination/('.current-'+uuid.uuid4().hex)
        write_json(pointer,{'run':target.name,'dataset_revision':revision})
        os.replace(pointer,destination/'current.json')
        return target,revision
    finally:
        if stage.exists():shutil.rmtree(stage)
