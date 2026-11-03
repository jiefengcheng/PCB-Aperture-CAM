"""Host aggregation of complete bounded ABI inspection batches.

The wire ABI keeps its 1,000 explicit IDs per request and 100 records per page.
The trusted U03 host exhausts every batch and binds the exact union for planning.
There is no truncated target list and no widening of the shared wire contract.
"""
from src.stage_abi.store import canonical


def aggregate(store,selected_ids,page_refs):
    if not selected_ids or len(selected_ids)!=len(set(selected_ids)) or not page_refs:
        raise ValueError('U03_INSPECTION_SELECTION_INVALID')
    records=[];seen=set();batches=[];context=None;batch=None;batch_records=[];closed=True
    for ref in page_refs:
        page=store.get_json(ref,kind='inspection')
        identity={k:page[k] for k in ('scene_ref','policy_ref','profile_id')}
        if context is None:context=identity
        if context!=identity or page['selected_finding_ids']!=[] or not 0<len(page['selected_source_ids'])<=1000:
            raise ValueError('U03_INSPECTION_PAGE_BINDING_CHANGED')
        selected=page['selected_source_ids']
        if selected!=batch:
            if not closed:raise ValueError('U03_INSPECTION_BATCH_NOT_EXHAUSTED')
            if batch is not None and set(batch_records)!=set(batch):raise ValueError('U03_INSPECTION_BATCH_INCOMPLETE')
            if any(s in seen for s in selected):raise ValueError('U03_INSPECTION_BATCH_DUPLICATED')
            batch=list(selected);batch_records=[];batches.extend(selected)
        elif closed:raise ValueError('U03_INSPECTION_PAGE_AFTER_EXHAUSTION')
        if page['total_records']!=len(batch) or not 0<len(page['records'])<=100:
            raise ValueError('U03_INSPECTION_PAGE_COUNT_CHANGED')
        for row in page['records']:
            if row['record_type']!='source':raise ValueError('U03_INSPECTION_SOURCE_RECORD_REQUIRED')
            sid=row['record']['source_id']
            if sid not in batch or sid in seen:raise ValueError('U03_INSPECTION_RECORD_DUPLICATED_OR_UNSELECTED')
            seen.add(sid);batch_records.append(sid);records.append(row)
        closed=page['next_cursor'] is None
    if not closed or set(batch_records)!=set(batch) or set(seen)!=set(selected_ids) or batches!=selected_ids:
        raise ValueError('U03_INSPECTION_COMPLETE_COVERAGE_REQUIRED')
    return dict(**context,records=records,selected_source_ids=list(selected_ids),selected_finding_ids=[],
                next_cursor=None,total_records=len(records),acceptance=page['acceptance'],
                u03_complete_inspection_pages=list(page_refs))


def inspect_all(store,selected_ids,call):
    refs=[]
    for offset in range(0,len(selected_ids),1000):
        batch=selected_ids[offset:offset+1000];cursor=None
        while True:
            result=call('inspect',dict(source_ids=batch,finding_ids=[],page_size=100,cursor=cursor))
            ref=result['inspection_ref'];page=store.get_json(ref,kind='inspection')
            if page!={k:v for k,v in result.items() if k!='inspection_ref'}:
                raise ValueError('U03_INSPECTION_RESPONSE_ARTIFACT_CHANGED')
            refs.append(ref);cursor=result['next_cursor']
            if cursor is None:break
    report=aggregate(store,selected_ids,refs)
    return store.put_json('inspection',report),len(refs)


def validate(store,ref):
    value=store.get_json(ref,kind='inspection')
    expected=aggregate(store,value['selected_source_ids'],value['u03_complete_inspection_pages'])
    if canonical(value)!=canonical(expected):raise ValueError('U03_INSPECTION_AGGREGATE_CHANGED')
    return value
