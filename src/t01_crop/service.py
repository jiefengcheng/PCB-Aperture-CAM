"""T01-only service registration; shared five-suite dispatcher remains unchanged."""
from src.stage_abi import ABI_VERSION
from src.stage_abi.service import StageService
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.contracts import fail,StageABIError
from src.t01_abi.service import InteractionService
from .protocol import validate
from . import PROFILE
from .adapter import CropAdapter
from .policy import compile_policy,validate_binding
from .paging import store_pages,read_pages,inspection_binding
from src.stage_abi.contracts import closed
from src.stage_abi.store import canonical

class CropService(InteractionService):
    def __init__(self,store,host):
        fail('T01_CROP_WRITE_RETIRED','Use canonical complete-source T01; old ROI writes cannot select an alternate construction')
        if set(host)!={'schema','compiler_binding_refs','stage_registry'} or host['schema']!='t01-crop-host/1':fail('T01_HOST_INVALID','Crop host')
        self.host=host
        StageService.__init__(self,store,TrustedRegistry(store,host['stage_registry']),{PROFILE:CropAdapter()})
    def dispatch(self,request):
        if type(request)is not dict or request.get('operation') not in ('t01_compile','t01_inspect_all','t01_compare_all'):return super().dispatch(request)
        try:
            validate(request,'request');p=request['payload']
            if request['operation']=='t01_compile':
                if p['binding_ref'] not in self.host['compiler_binding_refs']:fail('T01_BINDING_NOT_REGISTERED','Source/ROI binding')
                validate_binding(self.store.get_json(p['binding_ref'],kind='t01-binding'))
                text=p['english'] if 'english' in p else self.store.get(p['english_ref'],kind='english-spec').decode()
                policy=compile_policy(text,p['binding_ref'])
                result=dict(policy_ref=self.store.put_json('policy',policy),policy=policy,construction_status='NOT_RUN')
            else:
                profile,scene,policy,adapter=self._context(request,'t01')
                result=self._inspect_all(request,scene) if request['operation']=='t01_inspect_all' else self._compare_all(request,scene)
            status='OK';error=None
        except (StageABIError,ValueError,TypeError,KeyError,IndexError,OSError) as e:
            result=None;status='REJECTED';error=dict(code=e.code if isinstance(e,StageABIError) else 'T01_INPUT_OR_ARTIFACT_INVALID',message=str(e))
        return validate(dict(abi_version=ABI_VERSION,request_id=request.get('request_id'),operation=request.get('operation'),status=status,result=result,error=error),'response')


    def _selection(self,reference,scene_ref):
        selection=self.store.get_json(reference,kind='selection')
        closed(selection,{'stage','scene_ref','source_ids'},'Crop selection')
        ids=selection['source_ids']
        if (selection['stage']!='t01' or selection['scene_ref']!=scene_ref or type(ids)is not list or not ids
            or any(type(s)is not str or not s or len(s)>512 for s in ids) or len(set(ids))!=len(ids)):
            fail('T01_SELECTION_BINDING_MISMATCH','Complete unique source selection')
        return ids

    def _inspect_all(self,r,scene):
        ids=self._selection(r['payload']['selection_ref'],r['scene_ref']);selected=set(ids)
        records=[dict(record_type='source',record=row) for row in scene['objects'] if row['source_id'] in selected]
        if len(records)!=len(ids):fail('SELECTION_NOT_FOUND','Inspection source selection')
        records.sort(key=lambda row:(row['record_type'],canonical(row['record'])))
        binding=inspection_binding(r,r['payload']['selection_ref'])
        pages=store_pages(self.store,records,binding=binding,kind='t01-inspection',page_size=r['payload']['page_size'])
        checked,index=read_pages(self.store,pages,binding=binding,kind='t01-inspection',identity=lambda x:x['record']['source_id'])
        if checked!=records:fail('T01_PAGE_COVERAGE_INVALID','Inspection records')
        report=dict(scene_ref=r['scene_ref'],policy_ref=r['policy_ref'],profile_id=r['profile_id'],records=checked,
                    selected_source_ids=ids,selected_finding_ids=[],next_cursor=None,total_records=len(records),acceptance=scene['acceptance'],
                    pagination_ref=pages,page_count=len(index['pages']))
        return dict(inspection_ref=self.store.put_json('inspection',report),**report)

    def _plan(self,r,stage,p,scene,policy,adapter):
        # The shared planner checks selected IDs; this crop gate also proves that
        # every corresponding record page was actually inspected and exhausted.
        inspection=self.store.get_json(r['payload']['inspection_ref'],kind='inspection')
        ids=self._selection(r['payload']['selection_ref'],r['scene_ref'])
        if 'pagination_ref' not in inspection:fail('T01_COMPLETE_INSPECTION_REQUIRED','All record pages required')
        rows,index=read_pages(self.store,inspection['pagination_ref'],binding=inspection_binding(r,r['payload']['selection_ref']),
                              kind='t01-inspection',identity=lambda x:x['record']['source_id'])
        source={row['source_id']:row for row in scene['objects']}
        if (rows!=inspection['records'] or inspection['selected_source_ids']!=ids or inspection['selected_finding_ids']!=[]
            or inspection['next_cursor'] is not None or inspection['total_records']!=len(ids)
            or inspection['page_count']!=len(index['pages']) or {x['record']['source_id'] for x in rows}!=set(ids)
            or any(x['record_type']!='source' or x['record']!=source[x['record']['source_id']] for x in rows)):
            fail('T01_COMPLETE_INSPECTION_REQUIRED','Inspection page and native scene coverage')
        return super()._plan(r,stage,p,scene,policy,adapter)

    def _compare_all(self,r,scene):
        payload=r['payload'];selection=self.store.get_json(payload['evidence_selection_ref'],kind='evidence-selection')
        closed(selection,{'source_ids'},'Crop evidence selection');ids=selection['source_ids']
        if (type(ids)is not list or not ids or any(type(s)is not str or not s or len(s)>512 for s in ids)
            or len(set(ids))!=len(ids)):fail('EXPLICIT_BOUNDED_SELECTION_REQUIRED','Unique explicit comparison selection')
        # Reuse the unchanged common geometric comparison once for the common
        # viewport/delta/visuals. Page the source-change inventory separately.
        first=self.store.put_json('evidence-selection',dict(source_ids=ids[:payload['page_size']]))
        mapped=dict(r,payload={k:v for k,v in payload.items() if k!='page_size'})
        mapped['payload']=dict(mapped['payload'],evidence_selection_ref=first)
        base=StageService._compare(self,mapped,scene)
        left=self.store.get_json(payload['left_ref'],kind='scene');right=self.store.get_json(payload['right_ref'],kind='scene')
        lm={row['source_id']:row for row in left['objects']};rm={row['source_id']:row for row in right['objects']};changes=[]
        for sid in sorted(ids):
            if sid not in lm and sid not in rm:fail('SELECTION_NOT_FOUND',sid)
            changes.append(dict(source_id=sid,left_ref=lm.get(sid,{}).get('geometry_ref'),right_ref=rm.get(sid,{}).get('geometry_ref')))
        binding=dict(scene_ref=r['scene_ref'],policy_ref=r['policy_ref'],profile_id=r['profile_id'],
                     **{k:v for k,v in payload.items() if k!='page_size'})
        pages=store_pages(self.store,changes,binding=binding,kind='t01-comparison',page_size=payload['page_size'])
        checked,index=read_pages(self.store,pages,binding=binding,kind='t01-comparison',identity=lambda x:x['source_id'])
        if checked!=changes:fail('T01_PAGE_COVERAGE_INVALID','Comparison records')
        report={k:v for k,v in base.items() if k!='comparison_ref'}
        report.update(source_changes=checked,pagination_ref=pages,page_count=len(index['pages']))
        return dict(comparison_ref=self.store.put_json('comparison',report),**report)
