"""Attachment-complete spindle execution over a bounded immutable scene snapshot."""
import copy,time
from contextlib import contextmanager
from functools import wraps
from shapely import from_wkb,to_wkb
from shapely.geometry import box,Polygon
from shapely.ops import unary_union
from src.stage_abi.store import canonical,digest
from src.stage_abi.scene import validate_scene,composed
from src.junction_spindle_stage import CONTRACT,prepare_spindle_context
from src.junction_spindle_blend import spindle_blend,check_spindle
from .junctions import NativeSpindleAdapter
from src.stage_abi.loaded_geometry import GeometrySnapshot,GeometryMemo,SNAPSHOT_BYTES,MEMO_BYTES,MEMO_ENTRIES,SIGNATURE_ENTRIES,budget
from src.stage_abi.spatial_queries import SpatialQueries

EPS=CONTRACT.area_epsilon_mm2
VISIBLE=CONTRACT.minimum_visible_addition_mm2

def loaded_execution(fn):
    @wraps(fn)
    def invoke(self,store,scene,policy,*args,**kwargs):
        with self.execution(store,scene,policy):return fn(self,store,scene,policy,*args,**kwargs)
    return invoke

class CoverageAdapter(NativeSpindleAdapter):
    def __init__(self,write,exceptions=None,*,snapshot_bytes=SNAPSHOT_BYTES,memo_bytes=MEMO_BYTES,memo_entries=MEMO_ENTRIES,signature_entries=SIGNATURE_ENTRIES):
        self.write=write;self.exceptions=exceptions or {}
        self.geometry_budgets=dict(snapshot_bytes=budget(snapshot_bytes,'snapshot'),memo_bytes=budget(memo_bytes,'memo'),memo_entries=budget(memo_entries,'entries'),signature_entries=budget(signature_entries,'signatures'))
        self._geometry=None;self._snapshot=None
    def describe(self):
        from pathlib import Path
        result=super().describe();result['geometry_budgets']=self.geometry_budgets
        result['implementation']=digest(canonical(result)+Path(__file__).read_bytes()+Path(__file__).parents[1].joinpath('stage_abi/loaded_geometry.py').read_bytes()+Path(__file__).parents[1].joinpath('stage_abi/spatial_queries.py').read_bytes());return result
    def _context(self,store,scene,policy,details):
        if getattr(self,'_active_execution',None) is not None:
            if self._active_execution[:3]!=(id(store),id(scene),id(policy)):raise ValueError('U05_ATTACHMENT_EXECUTION_CONTEXT_CHANGED')
            return self._hot
        key=(id(store),digest(canonical([scene,policy])))
        if getattr(self,'_hot_key',None)!=key:
            from .junctions import parameters
            if policy!={'stage':'t05','parameters':parameters()}:raise ValueError('U05_ATTACHMENT_POLICY_OR_BOUNDS_INVALID')
            self.close()
            try:
                self._snapshot=GeometrySnapshot(store,scene,limit=self.geometry_budgets['snapshot_bytes']);s=self._snapshot
                self._hot=(s.objects,s.current,s.original,s.crop);self._hot_key=key
                self._ids=sorted(sid for sid in s.current if s.objects[sid]['kind']!='trace')
                self._spatial=SpatialQueries({sid:s.current[sid] for sid in self._ids},context=key[1],versions={sid:s.objects[sid]['geometry_ref']['sha256'] for sid in self._ids})
                self._before=s.retain_derived(unary_union([s.current[sid] for sid in self._ids]))
            except BaseException:
                self.close();raise
        return self._hot
    def close(self):
        if getattr(self,'_active_execution',None) is not None:raise ValueError('U05_ATTACHMENT_EXECUTION_ACTIVE')
        if self._geometry is not None:self._geometry.close();self._geometry=None
        if getattr(self,'_spatial',None) is not None:self._spatial.close()
        if self._snapshot is not None:self._snapshot.close();self._snapshot=None
        for field in ('_hot','_hot_key','_ids','_spatial','_before'):
            self.__dict__.pop(field,None)
    def _scope_binding(self):
        return digest(canonical([to_wkb(self.write).hex(),{k:to_wkb(v).hex() for k,v in sorted(self.exceptions.items())}]))
    @contextmanager
    def execution(self,store,scene,policy):
        if getattr(self,'_active_execution',None) is not None:raise ValueError('U05_ATTACHMENT_NESTED_EXECUTION')
        self._context(store,scene,policy,None);key=digest(canonical([scene,policy]));metadata=digest(canonical(self._hot[0]));scope=self._scope_binding();budgets=digest(canonical(self.geometry_budgets));self._active_execution=(id(store),id(scene),id(policy),key)
        self._geometry=GeometryMemo(digest(canonical([key,metadata,scope,self.geometry_budgets])),limit=self.geometry_budgets['memo_bytes'],entries=self.geometry_budgets['memo_entries'],signatures=self.geometry_budgets['signature_entries'])
        try:
            yield
            if key!=digest(canonical([scene,policy])) or metadata!=digest(canonical(self._hot[0])) or scope!=self._scope_binding() or budgets!=digest(canonical(self.geometry_budgets)):raise ValueError('U05_ATTACHMENT_EXECUTION_INPUT_CHANGED')
            self._snapshot.validate_bindings()
            self._spatial.validate_bindings({s:self._snapshot.current[s] for s in self._ids},{s:self._snapshot.objects[s]['geometry_ref']['sha256'] for s in self._ids},context=key)
            store.verify_reads()
        finally:
            self.last_execution_statistics=dict(snapshot=self._snapshot.diagnostics(),memo=self._geometry.diagnostics(),spatial=self._spatial.diagnostics())
            self._geometry.close();self._geometry=None;self._active_execution=None
    def _difference(self,a,b):return a.difference(b) if self._geometry is None else self._geometry.difference(a,b)
    def _difference_empty(self,a,b):return a.difference(b).is_empty if self._geometry is None else self._geometry.difference_empty(a,b)
    def _buffer(self,g,r):return g.buffer(r,quad_segs=64) if self._geometry is None else self._geometry.buffer(g,r,quad_segs=64)
    def _blend(self,owner,radius,domain):return spindle_blend(owner,radius,domain,geometry=self._geometry)
    def _check(self,owner,candidate,addition,window,foreign):return check_spindle(owner,candidate,addition,window,foreign,gap=CONTRACT.construction_gap_mm,geometry=self._geometry)
    def plan(self,store,scene,policy,selection,bounds):
        from .junctions import parameters
        if policy!={'stage':'t05','parameters':parameters()} or set(selection)!={'stage','scene_ref','source_ids'} or selection['stage']!='t05' or set(bounds)!={'max_source_objects','max_targets','max_evaluations','max_output_bytes','max_seconds'} or any(type(v) is not int or v<=0 for v in bounds.values()) or len(scene['objects'])>bounds['max_source_objects']:raise ValueError('U05_ATTACHMENT_POLICY_OR_BOUNDS_INVALID')
        objects,current,original,_=self._context(store,scene,policy,None);routes=[]
        if len(selection['source_ids'])!=len(set(selection['source_ids'])) or len(selection['source_ids'])>bounds['max_targets']:raise ValueError('U05_ATTACHMENT_SELECTION_INVALID')
        for sid in selection['source_ids']:
            r=objects[sid];md=r['metadata'];lands=md['land_ids']
            if r['kind']!='trace' or not md['native_route_ref']:raise ValueError('U05_ATTACHMENT_TRACE_UNQUALIFIED')
            for lid in lands:
                if not objects[lid]['metadata'].get('qualified_land') or original[sid].intersection(original[lid]).area<=EPS or current[sid].intersection(current[lid]).area<=EPS:raise ValueError('U05_ATTACHMENT_CONTACT_UNQUALIFIED:'+sid+':'+lid)
                from src.stage_abi.spindle import filled_circle
                land=objects[lid]
                if land['kind']=='circle' and not filled_circle(original[lid]):raise ValueError('U05_ATTACHMENT_CIRCLE_UNQUALIFIED')
                if land['kind'] in ('rectangle','inclusive_rectangle') and not current[lid].equals(box(*current[lid].bounds)):raise ValueError('U05_ATTACHMENT_RECTANGLE_UNQUALIFIED')
                if land['kind'] not in ('circle','rectangle','inclusive_rectangle') or any(not original[a].equals(original[lid]) or not current[a].equals(current[lid]) for a in land['metadata']['alias_source_ids']):raise ValueError('U05_ATTACHMENT_ALIAS_UNQUALIFIED')
            routes.append(dict(source_id=sid,land_ids=list(lands),covered_lands=[],attachments=md['attachments'],reference_id=md['reference_id'],reference_status=md['reference_status']))
        return dict(routes=routes,bounds=bounds,protected_source_ids=sorted(objects),family=CONTRACT.family)
    def scope(self,row):return self.write.union(self.exceptions.get(row['reference_id'],Polygon()))
    def _operands(self,store,scene,policy,details,row):
        objects,current,original,crop=self._context(store,scene,policy,details);sid=row['source_id']
        for lid in row['land_ids']:
            if original[sid].intersection(original[lid]).area<=EPS or current[sid].intersection(current[lid]).area<=EPS:raise ValueError('U05_ATTACHMENT_SOURCE_CONTACT_CHANGED')
        owner,radius,domain=prepare_spindle_context(current[sid],[current[l] for l in row['land_ids']],crop)
        allowed={sid,*row['land_ids'],*objects[sid]['metadata']['reference_source_ids']}
        for lid in row['land_ids']:
            allowed.update(objects[lid]['metadata']['alias_source_ids'])
            if objects[lid]['kind']=='inclusive_rectangle':allowed.update(objects[lid]['metadata']['members'])
        query=domain.buffer(CONTRACT.barrier_gap_mm)
        foreign=[(sid,current[sid]) for sid in self._spatial.query(query) if sid not in allowed and current[sid].intersects(query)]
        return owner,radius,domain,foreign
    def needs(self,current,row,radius,desired):
        return [dict(a,window=self._buffer(current[a['land_id']],2*radius),needed=desired.intersection(self._buffer(current[a['land_id']],2*radius)).area>VISIBLE) for a in row['attachments']]
    def outcomes(self,needs,physical,reference):
        rows=[]
        for a in needs:
            area=physical.intersection(a['window']).area
            rows.append(dict(id=a['id'],land_id=a['land_id'],reference_land_id=a['reference_land_id'],required_reference=a['required_reference'],status='TREATED_VERIFIED' if a['needed'] and area>VISIBLE else 'MISSING_TREATMENT' if a['needed'] else 'ALREADY_SATISFIED_VERIFIED',added_area_mm2=area,needed=a['needed']))
        return rows
    @loaded_execution
    def run(self,store,scene,policy,plan,checkpoint):
        objects,current,_,crop=self._context(store,scene,policy,plan['details']);before=self._before.intersection(crop);accepted=[];decisions=[];used=0;started=time.monotonic();bounds=plan['details']['bounds'];written=0
        for ordinal,row in enumerate(plan['details']['routes']):
            if time.monotonic()-started>bounds['max_seconds']:raise ValueError('U05_ATTACHMENT_TIME_BUDGET')
            d=dict(row,status='KEEP',attempts=[])
            if not row['land_ids']:d.update(reason='NO_DECLARED_SOURCE_CONTACT',attachment_outcomes=[]);decisions.append(d);continue
            owner,radius,domain,foreign=self._operands(store,scene,policy,plan['details'],row);desired=self._blend(owner,radius,domain)[1].difference(before);needs=self.needs(current,row,radius,desired)
            if not any(a['needed'] for a in needs):d.update(reason='PREDECESSOR_ALREADY_SATISFIES',attachment_outcomes=self.outcomes(needs,Polygon(),row));decisions.append(d);continue
            all_foreign=foreign+[(a['id'],a['addition']) for a in accepted];barriers=unary_union([self._buffer(g,CONTRACT.barrier_gap_mm) for _,g in all_foreign if not self._difference_empty(g,owner)]);scope=self.scope(row)
            for scale in CONTRACT.radius_scales:
                used+=1
                if used>bounds['max_evaluations']:raise ValueError('U05_ATTACHMENT_EVALUATION_BUDGET')
                raw=self._blend(owner,radius*scale,domain)[1].difference(barriers);physical=raw.difference(before);check=self._check(owner,owner.union(raw),raw,domain,all_foreign);outcomes=self.outcomes(needs,physical,row)
                failures=list(check['failures'])
                if physical.difference(scope).area>EPS:failures.append('WRITE_BOUNDARY')
                if any(a['status']=='MISSING_TREATMENT' for a in outcomes):failures.append('ATTACHMENT_NO_EFFECT')
                passed=not failures and physical.area>VISIBLE;d['attempts'].append(dict(scale=scale,passed=passed,failures=failures,added_area_mm2=physical.area))
                if passed:
                    blob=to_wkb(raw);written+=len(blob)
                    if written>bounds['max_output_bytes']:raise ValueError('U05_ATTACHMENT_OUTPUT_BUDGET')
                    d.update(status='GROWN',scale=scale,patch_ref=store.put('geometry',blob),attachment_outcomes=outcomes);accepted.append(dict(id=row['source_id'],owner=owner,window=domain,addition=raw,foreign=foreign));break
            if d['status']=='KEEP':d.update(reason='BLOCKED_REQUIRED_TREATMENT',attachment_outcomes=[dict(a,status='BLOCKED_CLEARANCE_OR_BOUNDARY') for a in self.outcomes(needs,Polygon(),row)])
            decisions.append(d);checkpoint(dict(next_ordinal=ordinal+1,evaluations_used=used))
        checks=[]
        for a in accepted:
            q=self._check(a['owner'],a['owner'].union(a['addition']),a['addition'],a['window'],a['foreign']+[(b['id'],b['addition']) for b in accepted if b['id']!=a['id']])
            if not q['passed']:raise ValueError('U05_ATTACHMENT_SIMULTANEOUS_FAILURE:'+str(q['failures']))
            checks.append(dict(id=a['id'],check=q))
        after=before.union(unary_union([a['addition'] for a in accepted]));output=dict(scene,objects=list(scene['objects']),lineage=scene['lineage']+[dict(stage='t05',predecessor_ref=plan['scene_ref'],policy_ref=plan['policy_ref'],implementation=plan['implementation'],plan_ref=store.put_json('plan',plan))],acceptance=dict(owner='PENDING_USER',independent='NOT_RUN',native_electrical_manufacturing='NOT_ESTABLISHED'))
        for d in decisions:
            if d['status']=='GROWN':output['objects'].append(dict(source_id='t05-addition:'+d['patch_ref']['sha256'],kind='junction_addition',geometry_ref=d['patch_ref'],original_ref=d['patch_ref'],metadata=dict(origin='t05-derived-addition',owner_trace=d['source_id'],predecessor_ref=plan['scene_ref'])))
        return dict(status='CONSTRUCTED',before_ref=store.put('geometry',to_wkb(before)),after_ref=store.put('geometry',to_wkb(after)),output_scene_ref=store.put_json('scene',output),decisions=decisions,checks=checks,protected_source_refs={s:r['geometry_ref'] for s,r in objects.items()},evaluations=used,coverage=dict(targets=len(decisions),grown=len(accepted),attachment_outcomes=sum(len(d['attachment_outcomes']) for d in decisions)))
    @loaded_execution
    def verify(self,store,scene,policy,plan,candidate,proof_scope,checkpoint):
        if proof_scope!={'scope':'complete-source-and-all-patches'}:raise ValueError('U05_ATTACHMENT_PROOF_SCOPE')
        objects,current,_,crop=self._context(store,scene,policy,plan['details']);before=self._before.intersection(crop);patches=[]
        if candidate['protected_source_refs']!={s:r['geometry_ref'] for s,r in objects.items()} or store.get(candidate['before_ref'],kind='geometry')!=to_wkb(before):raise ValueError('U05_ATTACHMENT_PREDECESSOR_CHANGED')
        if [d['source_id'] for d in candidate['decisions']]!=[r['source_id'] for r in plan['details']['routes']]:raise ValueError('U05_ATTACHMENT_MISSING_CLUSTER')
        for row,d in zip(plan['details']['routes'],candidate['decisions']):
            if any(d[k]!=row[k] for k in row):raise ValueError('U05_ATTACHMENT_MEMBERSHIP_CHANGED')
            if not row['land_ids']:
                if d['status']!='KEEP' or d['attachment_outcomes']:raise ValueError('U05_ATTACHMENT_NO_CONTACT_FORGED')
                continue
            owner,radius,domain,foreign=self._operands(store,scene,policy,plan['details'],row);desired=self._blend(owner,radius,domain)[1].difference(before);needs=self.needs(current,row,radius,desired)
            if d['status']=='GROWN':
                if d['scale'] not in CONTRACT.radius_scales:raise ValueError('U05_ATTACHMENT_SCALE_CHANGED')
                barriers=unary_union([self._buffer(g,CONTRACT.barrier_gap_mm) for _,g in foreign+[(a['id'],a['addition']) for a in patches] if not self._difference_empty(g,owner)]);expected=self._blend(owner,radius*d['scale'],domain)[1].difference(barriers)
                if store.get(d['patch_ref'],kind='geometry')!=to_wkb(expected):raise ValueError('U05_ATTACHMENT_DIRECT_PATCH_REPLAY_FAILED')
                physical=expected.difference(before)
                if physical.difference(self.scope(row)).area>EPS:raise ValueError('U05_ATTACHMENT_WRITE_BOUNDARY')
                outcomes=self.outcomes(needs,physical,row)
                if outcomes!=d['attachment_outcomes'] or any(a['status']=='MISSING_TREATMENT' for a in outcomes):raise ValueError('U05_ATTACHMENT_MISSING_TREATMENT')
                patches.append(dict(id=row['source_id'],owner=owner,window=domain,addition=expected,foreign=foreign))
            else:
                if any(a['needed'] for a in needs):
                    if row['reference_status']=='GROWN':raise ValueError('U05_REQUIRED_REFERENCE_ATTACHMENT_BLOCKED:'+row['reference_id'])
                elif d['attachment_outcomes']!=self.outcomes(needs,Polygon(),row):raise ValueError('U05_ALREADY_SATISFIED_NOT_PROVED')
        for a in patches:
            q=self._check(a['owner'],a['owner'].union(a['addition']),a['addition'],a['window'],a['foreign']+[(b['id'],b['addition']) for b in patches if b['id']!=a['id']])
            if not q['passed']:raise ValueError('U05_ATTACHMENT_FINAL_GEOMETRY_FAILED')
        after=before.union(unary_union([a['addition'] for a in patches]))
        if store.get(candidate['after_ref'],kind='geometry')!=to_wkb(after):raise ValueError('U05_ATTACHMENT_AFTER_CHANGED')
        output=validate_scene(store,candidate['output_scene_ref']);expected_rows=list(scene['objects'])
        for d in candidate['decisions']:
            if d['status']=='GROWN':expected_rows.append(dict(source_id='t05-addition:'+d['patch_ref']['sha256'],kind='junction_addition',geometry_ref=d['patch_ref'],original_ref=d['patch_ref'],metadata=dict(origin='t05-derived-addition',owner_trace=d['source_id'],predecessor_ref=plan['scene_ref'])))
        expected_lineage=scene['lineage']+[dict(stage='t05',predecessor_ref=plan['scene_ref'],policy_ref=plan['policy_ref'],implementation=plan['implementation'],plan_ref=store.put_json('plan',plan))]
        if output['objects']!=expected_rows or output['lineage']!=expected_lineage or any(output[k]!=scene[k] for k in ('source_sha256','frame','units','layer','viewport_mm','findings')):raise ValueError('U05_ATTACHMENT_OUTPUT_BINDING_CHANGED')
        if self._snapshot.composed(store,output).symmetric_difference(after).area>EPS:raise ValueError('U05_ATTACHMENT_ASSEMBLY_CHANGED')
        return dict(passed=True,failures=[],reconstructed_patches=len(patches),removed_area_mm2=before.difference(after).area,verified_attachments=sum(len(d['attachment_outcomes']) for d in candidate['decisions']))
