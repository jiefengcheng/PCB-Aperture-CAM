"""Read-only diagnostic subset resolution from one explicit stored revision."""
from pathlib import Path
from .common_catalogue import retrieve,validate_positive,require
from .revision_catalog import RevisionCatalog


def diagnostic_selection(bundle,revision,roles):
    result=retrieve(bundle,revision);validate_positive(result)
    require(isinstance(roles,list) and 0<len(roles)<=4 and all(isinstance(r,str) for r in roles),'INVALID_SELECTION_ROLES')
    requested=set(roles);known={r['role'] for r in result['roles']}
    require(requested<=known,'UNKNOWN_SELECTION_ROLE')
    rows=[r for r in result['roles'] if r['role'] in requested]
    selectors={}
    for row in rows:
        selectors.setdefault(row['native_revision'],set()).add(row['native']['id'])
        selectors.setdefault(row['plotted_revision'],set()).add(row['plotted']['id'])
    selected={};dependencies={};receipts=[]
    with RevisionCatalog(Path(bundle)/'store',read_only=True) as catalog:
        for artifact_revision,ids in sorted(selectors.items()):
            selection=catalog.select(artifact_revision,object_ids=ids)
            require(selection['complete'] and not selection['writable_ids'],'INCOMPLETE_OR_WRITABLE_DIAGNOSTIC_SELECTION')
            for row in selection['records']:
                target=selected if row['id'] in selection['selected_ids'] else dependencies
                target[row['id']]=row
            receipts.append({k:selection[k] for k in ('revision','selected_ids','dependency_ids','writable_ids','complete','result_sha256')})
    for uid in selected:dependencies.pop(uid,None)
    native_ids={uid for uid,row in selected.items() if row['representation']=='native'}
    relationships=result['relationships'];proximity=relationships['proximity']
    retained={'physical_contacts':[r for r in relationships['topology']['relations'] if {r['source'],r['target']}<=native_ids],
              'recorded_group_membership':[{'group_id':c['id'],'layer':c['layer'],'selected_members':sorted(native_ids.intersection(c['members'])),
                'recorded_member_count':len(c['members']),'complete_within_recorded_group':set(c['members'])<=native_ids}
                for c in relationships['topology']['components'] if native_ids.intersection(c['members'])],
              'proximity':{'original_result_sha256':proximity['result_sha256'],'original_query':proximity['query'],
                'selected_matches':[r for r in proximity['matches'] if r['id'] in native_ids]} if proximity['query']['object'] in native_ids else None,
              'scope':'Filtered witnesses/membership from the recorded bounded topology; connectivity is not recomputed for this selection.'}
    return {'schema':'pcb-diagnostic-selection/1','mode':'SERVER_SELECTION_FROM_VERIFIED_CATALOGUE',
            'dataset_revision':result['dataset_revision'],'from_result_sha256':result['result_sha256'],
            'roles':rows,'native_records':[r for r in selected.values() if r['representation']=='native'],
            'gerber_records':[r for r in selected.values() if r['representation']=='gerber'],
            'dependencies':list(dependencies.values()),'object_count':len(selected)+len(dependencies),
            'qualifications':result['qualifications'],'relationships':retained,'writable_ids':[],'selection_receipts':receipts,
            'purpose':'Diagnostic records and saved-payload references; the full recorded store retains complete original bytes.'}
