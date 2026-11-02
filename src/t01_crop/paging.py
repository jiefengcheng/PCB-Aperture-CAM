"""Content-addressed, bound record pages with complete sequence verification."""
from src.stage_abi.store import canonical,digest
from src.stage_abi.contracts import closed,fail
import time

PAGE_SIZE=100

class PageBudget:
    def __init__(self,max_bytes=200000000,max_seconds=3600):
        self.max_bytes=max_bytes;self.max_seconds=max_seconds;self.bytes=0;self.started=time.monotonic()
    def check(self,value):
        self.bytes+=len(canonical(value))
        if self.bytes>self.max_bytes or time.monotonic()-self.started>self.max_seconds:
            fail('BUDGET_EXHAUSTED','Pagination byte/time budget')


def store_pages(store,rows,*,binding,kind,page_size=PAGE_SIZE,budget=None):
    budget=budget or PageBudget()
    if type(page_size)is not int or not 1<=page_size<=PAGE_SIZE:fail('PAGE_LIMIT_INVALID','page_size')
    if not rows:fail('T01_PAGE_COVERAGE_INVALID','Nonempty record inventory required')
    pages=[];previous=None
    for offset in range(0,len(rows),page_size):
        records=rows[offset:offset+page_size];end=offset+len(records)
        page=dict(schema='t01-record-page/1',binding=binding,offset=offset,total_records=len(rows),
                  previous_page_ref=previous,next_offset=end if end<len(rows) else None,records=records)
        budget.check(page);reference=store.put_json(kind+'-page',page)
        pages.append(dict(offset=offset,count=len(records),page_ref=reference));previous=reference
    index=dict(schema='t01-record-pages/1',kind=kind,binding=binding,page_size=page_size,
               total_records=len(rows),records_sha256=digest(canonical(rows)),pages=pages)
    budget.check(index);return store.put_json(kind+'-index',index)


def read_pages(store,reference,*,binding,kind,identity,budget=None):
    budget=budget or PageBudget()
    index=store.get_json(reference,kind=kind+'-index')
    budget.check(index)
    closed(index,{'schema','kind','binding','page_size','total_records','records_sha256','pages'},'T01 page index')
    if (index['schema']!='t01-record-pages/1' or index['kind']!=kind or index['binding']!=binding
        or type(index['page_size'])is not int or not 1<=index['page_size']<=PAGE_SIZE
        or type(index['total_records'])is not int or index['total_records']<=0
        or type(index['pages'])is not list or not index['pages']):fail('T01_PAGE_BINDING_INVALID','index binding/count')
    rows=[];previous=None;seen=set()
    for entry in index['pages']:
        closed(entry,{'offset','count','page_ref'},'T01 page entry')
        page=store.get_json(entry['page_ref'],kind=kind+'-page')
        budget.check(page)
        closed(page,{'schema','binding','offset','total_records','previous_page_ref','next_offset','records'},'T01 page')
        offset=len(rows);records=page['records']
        if (any(type(x)is not int for x in (entry['offset'],entry['count'],page['offset'],page['total_records']))
            or page['schema']!='t01-record-page/1' or page['binding']!=binding or page['total_records']!=index['total_records']
            or page['previous_page_ref']!=previous or type(records)is not list or not records
            or entry['offset']!=offset or page['offset']!=offset or entry['count']!=len(records)
            or len(records)!=min(index['page_size'],index['total_records']-offset)):
            fail('T01_PAGE_COVERAGE_INVALID','Missing, reordered, duplicate or noncontiguous page')
        end=offset+len(records)
        if (page['next_offset'] is not None and type(page['next_offset'])is not int) or page['next_offset']!=(end if end<index['total_records'] else None):fail('T01_PAGE_CURSOR_INVALID','Page continuation')
        for record in records:
            key=identity(record)
            if key in seen:fail('T01_PAGE_COVERAGE_INVALID','Duplicate record identity')
            seen.add(key)
        rows.extend(records);previous=entry['page_ref']
    if len(rows)!=index['total_records'] or digest(canonical(rows))!=index['records_sha256']:
        fail('T01_PAGE_COVERAGE_INVALID','Unexhausted pages or record digest')
    return rows,index


def inspection_binding(request,selection_ref):
    return dict(scene_ref=request['scene_ref'],policy_ref=request['policy_ref'],profile_id=request['profile_id'],selection_ref=selection_ref)
