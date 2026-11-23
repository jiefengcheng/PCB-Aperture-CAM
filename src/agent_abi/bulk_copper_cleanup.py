"""Read-only, revision-bound continuation ABI. No geometry kernel or writer."""
import base64
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONTRACT=ROOT/'contracts/agent_abi/bulk_copper_cleanup_v1.json'
OPERATIONS={'describe','status','list_places','inspect_place','check_saved'}
FILTERS={'all','corrected','unresolved','ignored','reviewed','circular'}


def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(data):return hashlib.sha256(data).hexdigest()


def request(operation,filter=None,place_id=None,revision=None):
    return dict(abi_version='1',operation=operation,filter=filter,place_id=place_id,revision=revision)


def validate_request(v):
    if (not isinstance(v,dict) or set(v)!={'abi_version','operation','filter','place_id','revision'} or
            v['abi_version']!='1' or v['operation']not in OPERATIONS):raise ValueError('INVALID_CLEANUP_REQUEST')
    op=v['operation']
    if op=='list_places':
        if v['filter']not in FILTERS or v['place_id']is not None or v['revision']is not None:raise ValueError('INVALID_LIST_SELECTOR')
    elif op=='inspect_place':
        if (v['filter']is not None or not isinstance(v['place_id'],str) or not v['place_id'].startswith('cleanup:') or
                not isinstance(v['revision'],str) or not v['revision']):raise ValueError('REVISION_BOUND_PLACE_REQUIRED')
    elif any(v[k]is not None for k in ('filter','place_id','revision')):raise ValueError('IRRELEVANT_CLEANUP_SELECTOR')
    return v


class SavedCleanup:
    def __init__(self,connection,work,expected):
        self.work=Path(work).resolve(strict=True);self.root=self.path(connection);self.expected=expected
        self.cfg=self.json(self.root/'connection.json')
        if (self.cfg.get('context')!='original' or self.cfg.get('source_sha256')!=expected['source_sha256'] or
                self.cfg.get('connection_id')!=expected['connection_id'] or self.cfg.get('scene_ref')!=expected['original_scene_ref']):
            raise ValueError('CLEANUP_ORIGINAL_SOURCE_CONNECTION_CHANGED')
        self.manifest_bytes=self.read(self.root/'session/current.json');m=json.loads(self.manifest_bytes);self.manifest=m
        if m['payload']!=m['sha256']+'.json':raise ValueError('INVALID_CURRENT_PAYLOAD_NAME')
        self.snapshot=json.loads(self.bound(self.root/'session/snapshots'/m['payload'],m['sha256']))
        self.state=json.loads(self.bound(self.root/'receipts'/(m['sha256']+'.state.json'),m['producerStateSHA256']))
        s=self.snapshot
        if (self.state['revision']!=s['revision'] or len(s['sources'])!=1 or s['sources'][0]['sha256']!=expected['source_sha256']):
            raise ValueError('CLEANUP_SNAPSHOT_STATE_SOURCE_MISMATCH')
        events=[self.json(p)for p in sorted((self.root/'queue').glob('*.ready.json'))]
        matches=[e for e in events if e.get('event_id')==self.state['event']]
        if len(matches)!=1:raise ValueError('UNIQUE_COMMITTED_CLEANUP_EVENT_REQUIRED')
        e=matches[0];self.event=e
        event_key=sha(encoded(dict(connection=self.cfg['connection_id'],report=e['report'],geometry=e['geometry'],status=e['display_status'])))
        if (e['connection_id']!=expected['connection_id'] or e['kind']!='construction' or e['display_status']!='Preview' or
                e.get('completion')!='PRODUCER_SEALED_AFTER_SLICE_COMPLETION' or event_key!=self.state['event']):
            raise ValueError('CLEANUP_PRODUCER_EVENT_MISMATCH')
        envelope=self.json(self.root/'session/presentations'/(m['sha256']+'.json'))
        payload=base64.b64decode(envelope['payloadBase64'],validate=True)
        if envelope['schema']!=1 or len(payload)>64*1024**2 or sha(payload)!=envelope['sha256']:
            raise ValueError('CLEANUP_PRESENTATION_CHECKSUM_MISMATCH')
        p=json.loads(payload);self.presentation=p
        if any(p.get(k)!=v for k,v in dict(schema=1,job=s['job'],revision=s['revision'],sceneSHA256=m['sha256'],
               sourceSHA256=expected['source_sha256'],constructionSHA256=e['geometry']['sha256']).items()):
            raise ValueError('CLEANUP_PRESENTATION_REVISION_MISMATCH')
        c=p['cleanup'];self.cleanup=c
        if c.get('operation')!='TRIM_ONLY' or type(p['addedAreaMM2'])not in(int,float) or not math.isfinite(p['addedAreaMM2']) or not 0<=p['addedAreaMM2']<=1e-12:
            raise ValueError('TRIM_ONLY_SAVED_PRESENTATION_REQUIRED')
        cases=c['cases']
        if (len({v['id']for v in cases})!=len(cases) or any(v['status']not in('corrected','unresolved','ignored')for v in cases) or
                any(v['kind']!='bump'for v in cases) or c.get('areaLimitFraction')!=.1 or c.get('areaComparison')!='STRICTLY_LESS_THAN' or
                c.get('areaBasis')!='ORIGINAL_CAUSING_PAD_OR_TRACE'):
            raise ValueError('INVALID_SAVED_CLEANUP_INVENTORY')
        if any(not s['sourceID'].startswith(expected['source_sha256']+':')for v in cases for s in v.get('sources',[])):
            raise ValueError('CLEANUP_PLACE_SOURCE_CHANGED')
        self.ack=self.json(self.root/'session/outbox/display.json')if (self.root/'session/outbox/display.json').exists()else None
        self.stable()

    def path(self,path):
        p=Path(path).resolve(strict=True)
        if not p.is_relative_to(self.work):raise ValueError('CLEANUP_PATH_OUTSIDE_LACIE')
        return p

    def read(self,path,limit=96*1024**2):
        p=self.path(path)
        with p.open('rb')as stream:data=stream.read(limit+1)
        if len(data)>limit:raise ValueError('CLEANUP_ARTIFACT_RESOURCE_LIMIT')
        return data

    def json(self,path):return json.loads(self.read(path))

    def bound(self,path,expected):
        data=self.read(path)
        if sha(data)!=expected:raise ValueError('CLEANUP_ARTIFACT_CHECKSUM_MISMATCH:'+str(path))
        return data

    def stable(self):
        if self.read(self.root/'session/current.json')!=self.manifest_bytes:raise ValueError('CLEANUP_REVISION_CHANGED_DURING_READ')

    def status(self):
        counts={status:sum(c['status']==status for c in self.cleanup['cases'])for status in ('corrected','unresolved','ignored')}
        ack=self.ack
        return dict(revision=self.snapshot['revision'],source_sha256=self.cfg['source_sha256'],context='original',
            construction=self.event['geometry'],report=self.event['report'],counts=counts,
            checkpoint_match=self.snapshot['revision']==self.expected['revision'] and self.event['geometry']['sha256']==self.expected['construction_sha256'],
            added_area_mm2=self.presentation['addedAreaMM2'],removed_area_mm2=self.presentation['removedAreaMM2'],
            display_current=bool(ack and ack.get('revision')==self.snapshot['revision'] and ack.get('payloadSHA256')==self.manifest['sha256'] and
                                 ack.get('presentation')=='BULK_COPPER_CLEANUP' and ack.get('status')=='DISPLAY_DOM_UPDATED'),
            checks_scope='AUTHENTICATED_PRESENTATION_AND_COMMIT_CHAIN; USE_CHECK_SAVED_FOR_CONSTRUCTION_BYTES')

    def places(self,filter):
        cases=[c for c in self.cleanup['cases']if filter=='all' or c['status']==filter or
               filter=='reviewed'and c.get('reviewNumber')is not None or filter=='circular'and c.get('boundaryKind')=='circular']
        if filter=='reviewed':cases=sorted(cases,key=lambda c:c['reviewNumber'])
        return [{k:v for k,v in c.items()if k not in('path','referencePath')}for c in cases]

    def check_saved(self):
        report=json.loads(self.bound(self.event['report']['path'],self.event['report']['sha256']))
        compressed=self.bound(self.event['geometry']['path'],self.event['geometry']['sha256'])
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(compressed))as stream:raw=stream.read(512*1024**2+1)
        if len(raw)>512*1024**2:raise ValueError('CLEANUP_STAGE_RESOURCE_LIMIT')
        stage=json.loads(raw);binding=stage['input_binding'];cfg=self.cfg
        if (binding.get('context')!='original' or binding.get('accepted_t03')is not False or 't03_sha256'in binding or
                binding.get('source_sha256')!=cfg['source_sha256'] or binding.get('scene_ref')!=cfg['scene_ref'] or
                binding.get('original_scene_ref')!=cfg['scene_ref']):raise ValueError('CLEANUP_CONSTRUCTION_LINEAGE_CHANGED')
        proof=stage.get('trim_only_phase',{})
        positive=proof.get('positive_copper_mm2')
        if (stage.get('operation')!='TRIM_ONLY' or proof.get('passed')is not True or proof.get('rectangular_bumps_considered')is not False or
                proof.get('source_bytes_changed')is not False or type(positive)not in(int,float) or not math.isfinite(positive) or not 0<=positive<=1e-12 or
                proof.get('topology_before')!=self.expected['component_hole_counts'] or proof.get('topology_after')!=proof['topology_before']):
            raise ValueError('CLEANUP_PHASE_POLICY_CHANGED')
        if report.get('stage',{}).get('sha256')!=self.event['geometry']['sha256']:raise ValueError('CLEANUP_REPORT_STAGE_CHANGED')
        legacy=self.path(cfg['legacy']);source=json.loads(self.bound(legacy/'source.json',cfg['source_binding_sha256']))
        def artifact(ref):
            p=legacy/'runtime/artifacts'/ref['artifact_id']
            if self.path(p).parent!=(legacy/'runtime/artifacts').resolve():raise ValueError('CLEANUP_SOURCE_ARTIFACT_ESCAPE')
            return self.bound(p,ref['sha256'])
        if sha(artifact(source['source_ref']))!=cfg['source_sha256']:raise ValueError('CLEANUP_ORIGINAL_SOURCE_BYTES_CHANGED')
        catalogue=json.loads(artifact(cfg['scene_ref']));h=stage['hybrid_components']
        changed=dict(h['continuous_source_bodies']);changed.update(h['changed_bulk_copper'])
        ids={r['source_id']for r in catalogue['objects']}
        if not set(changed)<=ids or set(self.state['fingerprints'])!=ids:raise ValueError('CLEANUP_SOURCE_OCCURRENCE_COVERAGE_CHANGED')
        checked=set()
        for row in catalogue['objects']:
            for key in ('geometry_ref','original_ref'):
                ref=row.get(key)
                if ref is not None and ref['sha256']not in checked:
                    artifact(ref);checked.add(ref['sha256'])
            sid=row['source_id'];expected=sha(bytes.fromhex(changed[sid]['wkb_hex']))if sid in changed else row['geometry_ref']['sha256']
            if expected!=self.state['fingerprints'][sid]:raise ValueError('CLEANUP_SAVED_WKB_FINGERPRINT_CHANGED:'+sid)
        self.stable()
        # Keep the inspection response small; full local witnesses remain in the
        # authenticated construction, not duplicated in every agent startup.
        summary={key:proof[key]for key in ('passed','positive_copper_mm2','rectangular_bumps_considered',
                 'source_bytes_changed','topology_before','topology_after')}
        summary.update({key:proof[key]for key in ('all_rectangles_preserved','total_removed_mm2','clearance_searches','clearance_checks')if key in proof})
        return dict(saved_artifacts='AUTHENTICATED',source_occurrences=len(ids),changed_occurrences=len(changed),original_geometry_artifacts_checked=len(checked),
            geometry_verification='SAVED_ONLY_NOT_RERUN',phase_proof=summary,construction=self.event['geometry'],
            checkpoint_match=self.status()['checkpoint_match'],fresh_treatment=False)


def execute(value):
    value=validate_request(value);contract=json.loads(CONTRACT.read_bytes());op=value['operation']
    if op=='describe':result=contract
    else:
        from tools.pcb_workspace import require_storage
        work=require_storage();view=SavedCleanup(ROOT/contract['connection'],work,contract['checkpoint'])
        if op=='status':result=view.status()
        elif op=='list_places':result=dict(revision=view.snapshot['revision'],places=view.places(value['filter']))
        elif op=='inspect_place':
            if value['revision']!=view.snapshot['revision']:raise ValueError('STALE_CLEANUP_PLACE_REVISION')
            matches=[c for c in view.cleanup['cases']if c['id']==value['place_id']]
            if len(matches)!=1:raise ValueError('UNKNOWN_CLEANUP_PLACE')
            result=dict(revision=value['revision'],place=matches[0])
        else:result=view.check_saved()
        view.stable()
    return dict(abi_version='1',operation=op,status='OK',result=result,writes=False,geometry_execution=False,
                acceptance_change=False,full_board_execution=False)
