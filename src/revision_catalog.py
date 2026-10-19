"""PCB-owned revision catalog. Immutable payloads precede transactional publication.

SQLite is the reference catalog; spatial/graph indexes are rebuildable derivatives.
Committed SQLite transactions establish consistency, not power-loss durability.
"""
from pathlib import Path
import copy
import hashlib
import json
import math
import sqlite3
import time

class CatalogError(ValueError):
    pass

def digest(payload):
    return hashlib.sha256(payload).hexdigest()

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

class RevisionCatalog:
    SCHEMA='pcb-catalog/1'
    QUERY_CONTRACT='pcb-catalog-query/2'
    MAX_MANIFEST_BYTES=256*1024*1024
    MAX_PAYLOAD_BYTES=128*1024*1024
    CACHE_REVISIONS=2
    def __init__(self,root,*,read_only=False):
        self._validated_cache={}
        self.read_only=read_only
        self.root=Path(root)
        self.payloads=self.root/'payloads'
        if read_only:
            self.db=sqlite3.connect((self.root/'catalog.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
        else:
            self.root.mkdir(parents=True,exist_ok=True);self.payloads.mkdir(exist_ok=True)
            self.db=sqlite3.connect(self.root/'catalog.sqlite')
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        if read_only:return
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS revisions(
          revision TEXT PRIMARY KEY, source_hash TEXT NOT NULL,
          manifest_hash TEXT NOT NULL, manifest_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS objects(
          revision TEXT NOT NULL REFERENCES revisions(revision),
          object_id TEXT NOT NULL, parent_id TEXT, native_id TEXT,
          record_json TEXT NOT NULL, PRIMARY KEY(revision,object_id),
          FOREIGN KEY(revision,parent_id) REFERENCES objects(revision,object_id)
          DEFERRABLE INITIALLY DEFERRED);
        CREATE INDEX IF NOT EXISTS native_lookup ON objects(revision,native_id);
        CREATE TABLE IF NOT EXISTS relations(
          revision TEXT NOT NULL REFERENCES revisions(revision),
          occurrence TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
          relation_type TEXT NOT NULL, record_json TEXT NOT NULL,
          PRIMARY KEY(revision,occurrence),
          FOREIGN KEY(revision,source_id) REFERENCES objects(revision,object_id),
          FOREIGN KEY(revision,target_id) REFERENCES objects(revision,object_id));
        CREATE INDEX IF NOT EXISTS relation_lookup ON relations(revision,source_id,relation_type);
        CREATE TABLE IF NOT EXISTS published(
          name TEXT PRIMARY KEY, revision TEXT NOT NULL REFERENCES revisions(revision));
        ''')
    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    def put_payload(self,payload):
        if self.read_only:raise CatalogError('READ_ONLY_CATALOGUE')
        if len(payload)>self.MAX_PAYLOAD_BYTES:raise CatalogError('PAYLOAD_BUDGET_EXCEEDED')
        key=digest(payload);path=self.payloads/key
        if path.exists():
            if path.read_bytes()!=payload:raise CatalogError('CORRUPT_CONTENT_ADDRESS')
        else:
            # Atomic filename publication. Orphan payloads after a failed catalog
            # transaction are harmless; published revisions are never redirected.
            temporary=path.with_suffix('.pending')
            temporary.write_bytes(payload);temporary.replace(path)
        return key

    def read_payload(self,key):
        if len(key)!=64 or any(c not in '0123456789abcdef' for c in key):raise CatalogError('INVALID_PAYLOAD_KEY')
        try:
            if (self.payloads/key).stat().st_size>self.MAX_PAYLOAD_BYTES:raise CatalogError('PAYLOAD_BUDGET_EXCEEDED')
            payload=(self.payloads/key).read_bytes()
        except OSError as exc:raise CatalogError('PAYLOAD_UNAVAILABLE') from exc
        if digest(payload)!=key:raise CatalogError('PAYLOAD_HASH_MISMATCH')
        return payload

    def import_revision(self,source,objects,relations,config,*,publish_as=None,fail_after=None):
        if self.read_only:raise CatalogError('READ_ONLY_CATALOGUE')
        if len(objects)>100000 or len(relations)>1000000:raise CatalogError('REVISION_RECORD_BUDGET_EXCEEDED')
        source_hash=self.put_payload(source)
        objects=sorted(objects,key=lambda r:r['id']);relations=sorted(relations,key=lambda r:r['occurrence'])
        ids={r['id'] for r in objects}
        if len(ids)!=len(objects):raise CatalogError('DUPLICATE_OBJECT_OCCURRENCE')
        for r in objects:
            span=r['source_span'];start,end=span
            if not isinstance(start,int) or not isinstance(end,int) or not 0<=start<end<=len(source):raise CatalogError('INVALID_SOURCE_LOCATOR')
            if r['id']!=f'{source_hash}:bytes:{start}:{end}':raise CatalogError('OBJECT_SOURCE_MISMATCH')
            if r.get('parent_id') is not None and r['parent_id'] not in ids:raise CatalogError('MISSING_PARENT')
            bounds=r.get('bounds_mm')
            if bounds is not None:
                if len(bounds)!=4 or not all(math.isfinite(v) for v in bounds) or bounds[0]>bounds[2] or bounds[1]>bounds[3]:raise CatalogError('INVALID_BOUNDS')
            if r.get('geometry_sha256'):self.read_payload(r['geometry_sha256'])
        manifest={'schema':self.SCHEMA,'source_sha256':source_hash,'config':config,'objects':objects,'relations':relations}
        manifest_bytes=canonical(manifest)
        if len(manifest_bytes)>self.MAX_MANIFEST_BYTES:raise CatalogError('MANIFEST_BUDGET_EXCEEDED')
        revision=digest(manifest_bytes)
        try:
            with self.db:
                existing=self.db.execute('SELECT manifest_hash FROM revisions WHERE revision=?',(revision,)).fetchone()
                if not existing:
                    self.db.execute('INSERT INTO revisions VALUES(?,?,?,?)',(revision,source_hash,revision,manifest_bytes.decode()))
                    for index,r in enumerate(objects):
                        self.db.execute('INSERT INTO objects VALUES(?,?,?,?,?)',(revision,r['id'],r.get('parent_id'),r.get('native_id'),canonical(r).decode()))
                        if fail_after is not None and index+1>=fail_after:raise CatalogError('INJECTED_PARTIAL_IMPORT_FAILURE')
                    for r in relations:
                        self.db.execute('INSERT INTO relations VALUES(?,?,?,?,?,?)',(revision,r['occurrence'],r['source'],r['target'],r['type'],canonical(r).decode()))
                if publish_as is not None:
                    self.db.execute('INSERT INTO published VALUES(?,?) ON CONFLICT(name) DO UPDATE SET revision=excluded.revision',(publish_as,revision))
        except sqlite3.Error as exc:raise CatalogError('CATALOG_WRITE_ERROR: '+str(exc)) from exc
        return revision

    def _database_token(self):
        return (self.db.total_changes,self.db.execute('PRAGMA data_version').fetchone()[0],self.db.execute('PRAGMA schema_version').fetchone()[0])

    def _source_token(self,key):
        if len(key)!=64 or any(c not in '0123456789abcdef' for c in key):raise CatalogError('INVALID_PAYLOAD_KEY')
        try:stat=(self.payloads/key).stat()
        except OSError as exc:raise CatalogError('PAYLOAD_UNAVAILABLE') from exc
        return (stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_ino)

    def snapshot(self,revision):
        # Do not expose the validation cache to mutable caller-owned dictionaries.
        return copy.deepcopy(self._validated_snapshot(revision))

    def _validated_snapshot(self,revision):
        started=time.perf_counter()
        try:
            token=self._database_token();cached=self._validated_cache.get(revision)
            if cached and cached['database_token']==token and cached['source_token']==self._source_token(cached['manifest']['source_sha256']):
                self._last_verification={'cache_hit':True,'elapsed_seconds':time.perf_counter()-started,'policy':'Connection changes, SQLite data/schema generations and immutable-source file metadata checked; no concurrent writer supported.'}
                return cached['manifest']
            size=self.db.execute('SELECT length(cast(manifest_json AS blob)) FROM revisions WHERE revision=?',(revision,)).fetchone()
            if not size:raise CatalogError('REVISION_UNAVAILABLE')
            if size[0]>self.MAX_MANIFEST_BYTES:raise CatalogError('MANIFEST_BUDGET_EXCEEDED')
            row=self.db.execute('SELECT * FROM revisions WHERE revision=?',(revision,)).fetchone();encoded=row['manifest_json'].encode()
            if digest(encoded)!=row['manifest_hash'] or row['manifest_hash']!=revision:raise CatalogError('MANIFEST_HASH_MISMATCH')
            source_token=self._source_token(row['source_hash'])
            self.read_payload(row['source_hash']);manifest=json.loads(encoded)
            for table,key,order in [('objects','objects','object_id'),('relations','relations','occurrence')]:
                columns='record_json,object_id,parent_id,native_id' if table=='objects' else 'record_json,occurrence,source_id,target_id,relation_type'
                cursor=self.db.execute(f'SELECT {columns} FROM {table} WHERE revision=? ORDER BY {order}',(revision,))
                expected=iter(manifest[key]);count=0
                for r in cursor:
                    record=json.loads(r[0])
                    if record!=next(expected,None):raise CatalogError('CATALOG_MANIFEST_MISMATCH')
                    fields=(record['id'],record.get('parent_id'),record.get('native_id')) if table=='objects' else (record['occurrence'],record['source'],record['target'],record['type'])
                    if tuple(r)[1:]!=fields:raise CatalogError('CATALOG_INDEX_COLUMN_MISMATCH')
                    count+=1
                cursor.close()
                if count!=len(manifest[key]):raise CatalogError('CATALOG_MANIFEST_MISMATCH')
            if self._database_token()!=token:raise CatalogError('CATALOG_CHANGED_DURING_VERIFICATION')
            if self._source_token(row['source_hash'])!=source_token:raise CatalogError('SOURCE_CHANGED_DURING_VERIFICATION')
            if len(self._validated_cache)>=self.CACHE_REVISIONS:self._validated_cache.pop(next(iter(self._validated_cache)))
            self._validated_cache[revision]={'manifest':manifest,'database_token':token,'source_token':source_token}
            self._last_verification={'cache_hit':False,'elapsed_seconds':time.perf_counter()-started,'manifest_bytes':len(encoded),'manifest_budget_bytes':self.MAX_MANIFEST_BYTES,'source_budget_bytes':self.MAX_PAYLOAD_BYTES,'cache_revision_limit':self.CACHE_REVISIONS,'policy':'Full source/manifest/table verification once per stable generation; file metadata + SQLite generations invalidate cache.'}
            return manifest
        except (sqlite3.Error,json.JSONDecodeError) as exc:raise CatalogError('CATALOG_READ_ERROR: '+str(exc)) from exc

    def published(self,name):
        row=self.db.execute('SELECT revision FROM published WHERE name=?',(name,)).fetchone()
        if not row:raise CatalogError('PUBLISHED_REVISION_UNAVAILABLE')
        self.snapshot(row[0]);return row[0]

    def query(self,revision,*,ids=None,native_id=None,relation_type=None,source_id=None,limit=1000,cancel=None,expected_snapshot=None,after_id=None,before_id=None,properties=None,layer=None,work_limit=1000000,result_byte_limit=32*1024*1024):
        start=time.perf_counter()
        if not isinstance(limit,int) or isinstance(limit,bool) or not 0<=limit<=100000:raise CatalogError('INVALID_QUERY_LIMIT')
        if expected_snapshot is not None and expected_snapshot!=revision:raise CatalogError('STALE_MIXED_SNAPSHOT')
        validated=self._validated_snapshot(revision)
        source_token=self._source_token(validated['source_sha256'])
        verification=dict(self._last_verification)
        relation_query=relation_type is not None
        if source_id is not None and not relation_query:raise CatalogError('SOURCE_REQUIRES_RELATION_TYPE')
        if relation_query and (ids is not None or native_id is not None):raise CatalogError('INCOMPATIBLE_QUERY_SELECTORS')
        if relation_query and any(v is not None for v in (after_id,before_id,properties,layer)):raise CatalogError('INCOMPATIBLE_QUERY_SELECTORS')
        table='relations' if relation_query else 'objects';where=['revision=?'];params=[revision]
        if ids is not None:
            ids=sorted(set(ids))
            if len(ids)>10000:raise CatalogError('SELECTOR_BUDGET_EXCEEDED')
            if ids:where.append('object_id IN ('+','.join('?' for _ in ids)+')');params.extend(ids)
            else:where.append('0')
        if native_id is not None:where.append('native_id=?');params.append(native_id)
        if relation_query:where.append('relation_type=?');params.append(relation_type)
        if source_id is not None:where.append('source_id=?');params.append(source_id)
        if after_id is not None:where.append('object_id>?');params.append(after_id)
        if before_id is not None:where.append('object_id<?');params.append(before_id)
        if properties:
            for key,value in sorted(properties.items()):
                if key not in {'kind','net_name','net_code','pin','reference','coverage','group_name'}:raise CatalogError('UNSUPPORTED_PROPERTY_QUERY')
                where.append('json_extract(record_json,?) IS ?');params.extend(['$.'+key,value])
        if layer is not None:
            where.append("EXISTS(SELECT 1 FROM json_each(objects.record_json,'$.layers') WHERE value=?)");params.append(layer)
        order='occurrence' if relation_query else 'object_id'
        if not isinstance(work_limit,int) or not 0<=work_limit<=100000000 or not isinstance(result_byte_limit,int) or not 0<=result_byte_limit<=32*1024*1024:raise CatalogError('INVALID_QUERY_WORK_BUDGET')
        rows=[];status='COMPLETE';bytes_returned=0;vm_steps=0;cancelled=False;progress_interval=min(1000,max(1,work_limit))
        def progress():
            nonlocal vm_steps,cancelled
            vm_steps+=progress_interval;cancelled=bool(cancel and cancel())
            return int(cancelled or vm_steps>work_limit)
        generation=self._database_token()
        try:
            if cancel and cancel():status='CANCELLED'
            elif work_limit==0:status='WORK_BUDGET_EXCEEDED'
            if status!='COMPLETE':return {'revision':revision,'backend':'sqlite-reference','schema':self.SCHEMA,'query_contract':self.QUERY_CONTRACT,'status':status,'complete':False,'records':[],'result_sha256':digest(canonical([])),'elapsed_seconds':time.perf_counter()-start,'verification':verification,'query':{'ids':ids,'native_id':native_id,'relation_type':relation_type,'source_id':source_id,'after_id':after_id,'before_id':before_id,'properties':properties,'layer':layer,'limit':limit,'work_limit':work_limit,'result_byte_limit':result_byte_limit}}
            self.db.set_progress_handler(progress,progress_interval)
            cursor=self.db.execute(f'SELECT record_json FROM {table} WHERE '+ ' AND '.join(where)+f' ORDER BY {order} LIMIT ?',(*params,limit+1))
            for row in cursor:
                if cancel and cancel():status='CANCELLED';break
                if len(rows)==limit:status='TRUNCATED';break
                encoded_size=len(row[0].encode())
                if bytes_returned+encoded_size>result_byte_limit:status='TRUNCATED_BYTE_BUDGET';break
                bytes_returned+=encoded_size;rows.append(json.loads(row[0]))
            cursor.close()
        except sqlite3.OperationalError as exc:
            if 'interrupted' not in str(exc):raise CatalogError('CATALOG_QUERY_ERROR: '+str(exc)) from exc
            status='CANCELLED' if cancelled else 'WORK_BUDGET_EXCEEDED'
        except (sqlite3.Error,ValueError) as exc:raise CatalogError('CATALOG_QUERY_ERROR: '+str(exc)) from exc
        finally:self.db.set_progress_handler(None,0)
        if self._database_token()!=generation:raise CatalogError('CATALOG_CHANGED_DURING_QUERY')
        if self._source_token(validated['source_sha256'])!=source_token:raise CatalogError('SOURCE_CHANGED_DURING_QUERY')
        return {'revision':revision,'backend':'sqlite-reference','schema':self.SCHEMA,'query_contract':self.QUERY_CONTRACT,'status':status,'complete':status=='COMPLETE','records':rows,'result_sha256':digest(canonical(rows)),'elapsed_seconds':time.perf_counter()-start,'verification':verification,'vm_steps_observed_approx':vm_steps,'vm_steps_max_unobserved':progress_interval-1,'returned_json_bytes':bytes_returned,'next_after_id':rows[-1].get('id') if rows else None,'query':{'after_id':after_id,'before_id':before_id,'properties':properties,'layer':layer,'work_limit':work_limit,'result_byte_limit':result_byte_limit,'ids':ids,'native_id':native_id,'relation_type':relation_type,'source_id':source_id,'limit':limit}}

    def source_record(self,revision,object_id):
        manifest=self.snapshot(revision);result=self.query(revision,ids=[object_id],limit=2)
        if len(result['records'])!=1:raise CatalogError('OBJECT_UNAVAILABLE')
        record=result['records'][0];a,b=record['source_span'];source=self.read_payload(manifest['source_sha256'])
        return record,source[a:b]

    def region_query(self,revision,bounds_mm,layer,**kwargs):
        from .catalog_selection import region_query
        return region_query(self,revision,bounds_mm,layer,**kwargs)

    def select(self,revision,**kwargs):
        from .catalog_selection import select
        return select(self,revision,**kwargs)
