"""Attachment-complete spindle execution over a bounded immutable scene snapshot."""
import copy,time
from contextlib import contextmanager
from functools import wraps
from shapely import from_wkb,to_wkb
from shapely.geometry import box,Polygon,MultiPolygon
from shapely.ops import unary_union
from src.stage_abi.store import canonical,digest
from src.stage_abi.scene import validate_scene,composed
from src.junction_spindle_stage import CONTRACT,prepare_spindle_context
from src.junction_spindle_blend import spindle_addition,spindle_blend,check_spindle
from .junctions import NativeSpindleAdapter
from src import component_clearance as cc
from src.stage_abi.loaded_geometry import GeometrySnapshot,GeometryMemo,SNAPSHOT_BYTES,MEMO_BYTES,MEMO_ENTRIES,SIGNATURE_ENTRIES,MEASUREMENT_ENTRIES,budget
from src.stage_abi.spatial_queries import SpatialQueries
from src.t05_local_obstacles import LocalObstacles
from src.t05_bounded_kernels import ACTIVE as BOUNDED_KERNELS

def integral_context():
    from src import source_channel_scope
    return source_channel_scope.ACTIVE if source_channel_scope.ACTIVE is not None else cc.ACTIVE

EPS=CONTRACT.area_epsilon_mm2
VISIBLE=CONTRACT.minimum_visible_addition_mm2

def filled_patch(shape,before):
    """Keep every positive face; omit only already-covered zero-area remnants."""
    if not shape.is_valid:raise ValueError('U05_PATCH_INVALID')
    if shape.is_empty or shape.geom_type in ('Polygon','MultiPolygon'):return shape
    faces=[];boundaries=[]
    def collect(g):
        if g.is_empty:return
        if g.geom_type=='Polygon':faces.append(g)
        elif g.geom_type in ('MultiPolygon','GeometryCollection'):
            for part in g.geoms:collect(part)
        elif g.geom_type in ('Point','MultiPoint','LineString','LinearRing','MultiLineString')and g.area==0:boundaries.append(g)
        else:raise ValueError('U05_PATCH_UNSUPPORTED_GEOMETRY')
    collect(shape)
    result=faces[0]if len(faces)==1 else MultiPolygon(faces)if faces else Polygon()
    if not result.is_valid:raise ValueError('U05_PATCH_POSITIVE_FACES_INVALID')
    retained=[result]if result.geom_type=='Polygon'and not result.is_empty else list(result.geoms)if result.geom_type=='MultiPolygon'else[]
    if sorted(to_wkb(g)for g in retained)!=sorted(to_wkb(g)for g in faces):raise ValueError('U05_PATCH_POSITIVE_FACE_CHANGED')
    context=before.union(result)
    # Collinear overlay boundaries can make covers=False although exact set
    # subtraction is empty. Either proof establishes the same containment;
    # uncovered points/lines remain nonempty and still fail, with no tolerance.
    if any(not context.covers(g)and not g.difference(context).is_empty for g in boundaries):raise ValueError('U05_PATCH_NONAREAL_SCOPE_NOT_PROVED')
    return result

def addition_source_id(decision):
    # Distinct route obligations may share immutable geometry on one owner.
    if integral_context() is None:return 't05-addition:'+decision['patch_ref']['sha256']
    return 't05-addition:'+digest(canonical([decision['source_id'],decision['patch_ref']]))

def verify_assembled_output(snapshot,store,scene,expected_rows,output,after_ref):
    # Rebuild the declared leaf operands in the scene's canonical order.
    # A cached union of unions is not the scene composition contract.
    after=snapshot.composed(store,dict(scene,objects=expected_rows))
    if store.get(after_ref,kind='geometry')!=to_wkb(after):raise ValueError('U05_ATTACHMENT_AFTER_CHANGED')
    # The caller validates complete output binding before entering here. Also
    # bind the shortcut locally: identical ordered rows and viewport give the
    # very same canonical leaf union and clipping operation, not just a similar
    # copper outline. Changed/reordered rows or a changed crop use the original
    # second composition and geometric comparison below.
    if output['objects']==expected_rows and output['viewport_mm']==scene['viewport_mm']:
        # Preserve the second pass over actual artifact bytes, including store
        # hashes, decoded-geometry validity and cached-shape integrity checks.
        # Only the duplicate union/clip and self symmetric difference disappear.
        # No result survives this call, so changed copper cannot hit stale state.
        for row in output['objects']:snapshot.geometry(store,row['geometry_ref'])
    elif snapshot.composed(store,output).symmetric_difference(after).area>EPS:
        raise ValueError('U05_ATTACHMENT_ASSEMBLY_CHANGED')
    return after

def loaded_execution(fn):
    @wraps(fn)
    def invoke(self,store,scene,policy,*args,**kwargs):
        if BOUNDED_KERNELS.get():
            raise ValueError('T05_BOUNDED_KERNELS_REQUIRE_PROPOSAL_REPLAY')
        certified=getattr(self,'certificate_consumption',False)
        if certified and fn.__name__=='verify':
            if getattr(self,'_certificate_run',None)is None:raise ValueError('T05_FRESH_CERTIFIED_CONSTRUCTION_REQUIRED')
            if self._certificate_run.store is not store:raise ValueError('T05_CERTIFIED_ARTIFACT_STORE_CHANGED')
            plan,candidate,proof_scope,checkpoint=args
            return self._certificate_run.verify(scene,policy,plan,candidate,proof_scope)
        with self.execution(store,scene,policy):
            if certified and fn.__name__=='run':
                from src.t05_certified_execution import CertifiedExecution
                self._certificate_run=CertifiedExecution(self,store,scene,policy,args[0])
            result=fn(self,store,scene,policy,*args,**kwargs)
        # Seal only AFTER all original source/snapshot/index/artifact closing
        # guards completed. Final verification does not reopen this context.
        if certified and fn.__name__=='run':self._certificate_run.seal(result)
        return result
    return invoke

class CoverageAdapter(NativeSpindleAdapter):
    # T05 alternates large rolling-disc intermediates with fixed foreign-clearance
    # offsets. A 32 MiB shared LRU evicted unchanged offsets before their reuse;
    # partitioning that budget instead evicted the rolling-disc intermediates.
    # Reserve up to 64 MiB for this adapter, preserving the shared LRU and exact
    # operand/parameter keys. This bounds estimated retained geometry, not RSS.
    # Explicit smaller/zero budgets still recompute safely, and no verdict is
    # cached. Each execution owns and closes its memo, so reuse cannot cross a
    # changed scene/policy binding. Other stage adapters keep their own defaults.
    def __init__(self,write,exceptions=None,*,snapshot_bytes=SNAPSHOT_BYTES,memo_bytes=2*MEMO_BYTES,memo_entries=MEMO_ENTRIES,signature_entries=SIGNATURE_ENTRIES,measurement_bytes=0,measurement_entries=MEASUREMENT_ENTRIES):
        self.write=write;self.exceptions=exceptions or {}
        self.geometry_budgets=dict(snapshot_bytes=budget(snapshot_bytes,'snapshot'),memo_bytes=budget(memo_bytes,'memo'),memo_entries=budget(memo_entries,'entries'),signature_entries=budget(signature_entries,'signatures'))
        # Bounded profiling may reserve an independent owner/obstacle scalar
        # LRU inside memo_bytes. This is opt-in; legacy callers keep their shared
        # LRU. Each run/verify execution gets a fresh context-bound cache and
        # closes it even on failure. Never retain a previous scene's verdicts.
        self.geometry_budgets.update(measurement_bytes=budget(measurement_bytes,'measurement'),measurement_entries=budget(measurement_entries,'measurement-entries'))
        if measurement_bytes > memo_bytes:raise ValueError('LOADED_GEOMETRY_MEASUREMENT_BUDGET')
        self._geometry=None;self._snapshot=None
    def describe(self):
        from pathlib import Path
        result=super().describe();result['geometry_budgets']=self.geometry_budgets
        if getattr(self,'certificate_consumption',False):
            from src.t05_certified_execution import PROFILE
            result['certificate_execution']=PROFILE
        result['implementation']=digest(canonical(result)+Path(__file__).read_bytes()+Path(__file__).parents[1].joinpath('stage_abi/loaded_geometry.py').read_bytes()+Path(__file__).parents[1].joinpath('stage_abi/spatial_queries.py').read_bytes()+Path(__file__).parents[1].joinpath('t05_local_obstacles.py').read_bytes());return result
    def enable_certificate_consumption(self):
        """Select before planning; production default remains the old profile."""
        if getattr(self,'_hot',None)is not None:raise ValueError('T05_CERTIFICATE_OPTION_MUST_PRECEDE_PLANNING')
        from src.t05_certified_execution import MEMO_BYTES
        self.certificate_consumption=True
        self.geometry_budgets.update(memo_bytes=MEMO_BYTES,memo_entries=65536)
        from src.t05_outer_observer import ACTIVE,RESERVED_BYTES
        if ACTIVE.get()is not None:self.geometry_budgets['memo_bytes']-=RESERVED_BYTES
    def _certificate_region(self,addition):
        # The normal source profile certifies the exact physically checked
        # deposit. No saved trapezoid/reference material grants authority.
        return addition
    def _proposal_check(self,row,owner,addition,window,foreign):
        if getattr(self,'certificate_consumption',False):
            return self._certificate_run.proposal(row,owner,addition,window,foreign)
        return self._check(owner,owner.union(addition),addition,window,foreign)
    def _compose_output(self,store,output):
        actual=self._snapshot.composed(store,output)
        if getattr(self,'certificate_consumption',False):self._certificate_run.consumer.observe_composition(output,to_wkb(actual))
        return actual
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
                self._snapshot=GeometrySnapshot(store,scene,limit=self.geometry_budgets['snapshot_bytes'],bounded_operands=True,pin_current=False);s=self._snapshot
                self._hot=(s.objects,s.current,s.original,s.crop);self._hot_key=key
                self._ids=sorted(sid for sid in s.current if s.objects[sid]['kind']!='trace')
                self._spatial=SpatialQueries({sid:s.current[sid] for sid in self._ids},context=key[1],versions={sid:s.objects[sid]['geometry_ref']['sha256'] for sid in self._ids},envelopes_only=True)
                self._before=s.retain_derived(unary_union([s.current[sid] for sid in self._ids]))
                context=integral_context()
                if cc.ACTIVE is not None:cc.ACTIVE.register_scene(store,scene)
                if context is not None:
                    context.register_scene(store,scene)
                    self._integral_context=context
                    from .owner_surfaces import OwnerSurfaces
                    owner_limit=s.optional_capacity()//2
                    s.reserve_external(owner_limit)
                    self._copper_owners=OwnerSurfaces(context,{sid:s.current[sid]for sid in self._ids},store,limit=owner_limit)
                    self._surface_owners={}
            except BaseException:
                self.close();raise
        return self._hot
    def close(self):
        if getattr(self,'_active_execution',None) is not None:raise ValueError('U05_ATTACHMENT_EXECUTION_ACTIVE')
        if self._geometry is not None:self._geometry.close();self._geometry=None
        if getattr(self,'_spatial',None) is not None:self._spatial.close()
        if getattr(self,'_copper_owners',None)is not None:self._copper_owners.close()
        if self._snapshot is not None:self._snapshot.close();self._snapshot=None
        for field in ('_hot','_hot_key','_ids','_spatial','_before','_copper_owners','_surface_owners','_integral_context','_certificate_run'):
            self.__dict__.pop(field,None)
    def _scope_binding(self):
        return digest(canonical([to_wkb(self.write).hex(),{k:to_wkb(v).hex() for k,v in sorted(self.exceptions.items())}]))
    @contextmanager
    def execution(self,store,scene,policy):
        if getattr(self,'_active_execution',None) is not None:raise ValueError('U05_ATTACHMENT_NESTED_EXECUTION')
        self._context(store,scene,policy,None);key=digest(canonical([scene,policy]));metadata=digest(canonical(self._hot[0]));scope=self._scope_binding();budgets=digest(canonical(self.geometry_budgets));self._active_execution=(id(store),id(scene),id(policy),key)
        self._geometry=GeometryMemo(digest(canonical([key,metadata,scope,self.geometry_budgets])),limit=self.geometry_budgets['memo_bytes'],entries=self.geometry_budgets['memo_entries'],signatures=self.geometry_budgets['signature_entries'],measurement_bytes=self.geometry_budgets['measurement_bytes'],measurement_entries=self.geometry_budgets['measurement_entries'])
        if getattr(self,'certificate_consumption',False):
            self._geometry.exact_distance_reuse=True
            self._geometry.reuse_immutable_outputs=True
        try:
            yield
            if key!=digest(canonical([scene,policy])) or metadata!=digest(canonical(self._hot[0])) or scope!=self._scope_binding() or budgets!=digest(canonical(self.geometry_budgets)):raise ValueError('U05_ATTACHMENT_EXECUTION_INPUT_CHANGED')
            self._snapshot.validate_bindings()
            if getattr(self,'_copper_owners',None)is not None:self._copper_owners.validate_bindings()
            self._spatial.validate_bindings({s:self._snapshot.current[s] for s in self._ids},{s:self._snapshot.objects[s]['geometry_ref']['sha256'] for s in self._ids},context=key)
            store.verify_reads()
        finally:
            self.last_execution_statistics=dict(snapshot=self._snapshot.diagnostics(),memo=self._geometry.diagnostics(),spatial=self._spatial.diagnostics())
            if getattr(self,'_copper_owners',None)is not None:self.last_execution_statistics['owner_surfaces']=self._copper_owners.diagnostics()
            self._geometry.close();self._geometry=None;self._active_execution=None
    def _difference(self,a,b):return a.difference(b) if self._geometry is None else self._geometry.difference(a,b)
    def _difference_empty(self,a,b):return a.difference(b).is_empty if self._geometry is None else self._geometry.difference_empty(a,b)
    def _buffer(self,g,r):return g.buffer(r,quad_segs=64) if self._geometry is None else self._geometry.buffer(g,r,quad_segs=64)
    def _local_obstacles(self,owner,foreign,domain):
        # Preserve the legacy owner exclusion and complete ordered obstacles.
        # Only barrier construction is localized; _check still receives all
        # original foreign copper. A contact lazily builds the canonical mask.
        obstacles = [g for _, g in foreign if not self._difference_empty(g, owner)]
        if BOUNDED_KERNELS.get():
            from src.t05_bounded_local_obstacles import BoundedLocalObstacles
            return BoundedLocalObstacles(domain, obstacles, CONTRACT.barrier_gap_mm, self._buffer)
        return LocalObstacles(domain, obstacles, CONTRACT.barrier_gap_mm, self._buffer)
    def _blend(self,owner,radius,domain):
        candidate,addition=spindle_blend(owner,radius,domain,geometry=self._geometry)
        if integral_context() is None:return candidate,addition
        addition=self._exclude_blend_voids(owner,addition)
        return owner.union(addition),addition
    def _blend_addition(self,owner,radius,domain):
        # Needs and patch reconstruction consume only added copper. Assemble
        # the owner later, when validation has the actual barrier-trimmed patch.
        build = spindle_addition
        if BOUNDED_KERNELS.get():
            from src.t05_windowed_spindle import spindle_addition as window_first
            build = window_first
        addition=build(owner,radius,domain,geometry=self._geometry)
        return self._exclude_blend_voids(owner,addition)
    def _exclude_blend_voids(self,owner,addition):
        context=integral_context()
        if context is not None:
            from shapely.geometry import Polygon
            own=self._surface_owners[digest(to_wkb(owner))]
            source_core=context.cores[own]
            def original_voids():return unary_union([Polygon(r)for g in cc.surfaces(source_core)for r in g.interiors])
            source_void=original_voids()if self._geometry is None else self._geometry.construct('frozen-original-owner-voids',[source_core],(),original_voids)
            partial_voids=[v['remaining']for v in context.approved_partial_pockets.values()if v['spec'].get('original_channel_id',v['spec']['original_owner_id'])==own]
            if partial_voids:source_void=unary_union([source_void,*partial_voids])
            addition=addition.difference(source_void)
        return addition
    def owner_for_route(self,sid):return integral_context().owner(sid,self._hot[2][sid])
    def _foreign_for(self,owner,foreign):
        context=integral_context()
        if context is None:return foreign
        own=self._surface_owners[digest(to_wkb(owner))];out=[]
        for sid,g in foreign:
            other=sid[6:]if sid.startswith('owner:')else (context.ids.get(sid)or[None])[0]
            if other!=own:out.append((sid,g))
        return out
    def _check(self,owner,candidate,addition,window,foreign):
        result=check_spindle(owner,candidate,addition,window,self._foreign_for(owner,foreign),gap=CONTRACT.construction_gap_mm,geometry=self._geometry)
        from src import t02_shared_gaps as shared_gaps
        gap_proof=shared_gaps.remedy(addition,owner)
        if gap_proof is not None:
            result=dict(result,shared_neighbor_gaps=gap_proof)
            if not gap_proof['passed']:result=dict(result,passed=False,failures=[*result.get('failures',[]),'FROZEN_SHARED_NEIGHBOR_GAP'])
        from src import pin_separation as pin
        if pin.ACTIVE is not None:
            context=getattr(self,'_integral_context',None)
            def material():
                if context is not None:yield from context.reserved.values()
                if hasattr(self,'_copper_owners'):yield from self._copper_owners.values()
                for _,g in foreign:yield g
            import itertools
            proof=pin.ACTIVE.growth_parts(material(),itertools.chain(material(),[candidate]))
            if not proof['passed']:result=dict(result,passed=False,failures=[*result.get('failures',[]),'PROTECTED_PIN_SEPARATION'],pin_separation=proof)
        if result['passed']:
            from src.t05_trapped_voids import check as closure_check
            from src.growth_remedy_constraints import remedy as whole_fill_rule
            closure=closure_check(owner,candidate,whole_fill_rule,area_epsilon_mm2=EPS)
            result=dict(result,trapped_void_closure=closure)
            if not closure['passed']:
                result=dict(result,passed=False,failures=[*result.get('failures',[]),'TRAPPED_VOID_FILL_CONFLICTS_WITH_FROZEN_RULES'])
        return result
    def plan(self,store,scene,policy,selection,bounds):
        from .junctions import parameters
        if policy!={'stage':'t05','parameters':parameters()} or set(selection)!={'stage','scene_ref','source_ids'} or selection['stage']!='t05' or set(bounds)!={'max_source_objects','max_targets','max_evaluations','max_output_bytes','max_seconds'} or any(type(v) is not int or v<=0 for k,v in bounds.items() if k!='max_seconds' or v is not None) or len(scene['objects'])>bounds['max_source_objects']:raise ValueError('U05_ATTACHMENT_POLICY_OR_BOUNDS_INVALID')
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
        if integral_context() is not None:
            own=self.owner_for_route(sid);whole=self._copper_owners[own]
            pieces=[g for g in cc.surfaces(whole)if g.intersection(current[sid]).area>EPS]
            if len(pieces)!=1:raise ValueError('QUALIFIED_ROUTE_OWNER_NOT_ONE_FILLED_SURFACE')
            owner=pieces[0];self._surface_owners[digest(to_wkb(owner))]=own
            query=domain.buffer(CONTRACT.barrier_gap_mm)
            foreign=[]
            for o in self._copper_owners.query(query):
                if o==own:continue
                g=self._copper_owners[o]
                if g.intersects(query):foreign.append(('owner:'+o,g))
            return owner,radius,domain,foreign
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
        deadline=bounds['max_seconds']
        for ordinal,row in enumerate(plan['details']['routes']):
            if deadline is not None and time.monotonic()-started>deadline:raise ValueError('U05_ATTACHMENT_TIME_BUDGET')
            d=dict(row,status='KEEP',attempts=[])
            if not row['land_ids']:d.update(reason='NO_DECLARED_SOURCE_CONTACT',attachment_outcomes=[]);decisions.append(d);continue
            owner,radius,domain,foreign=self._operands(store,scene,policy,plan['details'],row);desired=self._blend_addition(owner,radius,domain).difference(before);needs=self.needs(current,row,radius,desired)
            if not any(a['needed'] for a in needs):d.update(reason='PREDECESSOR_ALREADY_SATISFIES',attachment_outcomes=self.outcomes(needs,Polygon(),row));decisions.append(d);continue
            all_foreign=self._foreign_for(owner,foreign+[(a['id'],a['addition']) for a in accepted]);barriers=self._local_obstacles(owner,all_foreign,domain);scope=self.scope(row)
            for scale in CONTRACT.radius_scales:
                used+=1
                if used>bounds['max_evaluations']:raise ValueError('U05_ATTACHMENT_EVALUATION_BUDGET')
                raw=barriers.trim(self._blend_addition(owner,radius*scale,domain));physical=raw.difference(before);check=self._proposal_check(row,owner,raw,domain,all_foreign);outcomes=self.outcomes(needs,physical,row)
                failures=list(check['failures'])
                if physical.difference(scope).area>EPS:failures.append('WRITE_BOUNDARY')
                if any(a['status']=='MISSING_TREATMENT' for a in outcomes):failures.append('ATTACHMENT_NO_EFFECT')
                passed=not failures and physical.area>VISIBLE;d['attempts'].append(dict(scale=scale,passed=passed,failures=failures,added_area_mm2=physical.area))
                if passed:
                    raw=filled_patch(raw,before);physical=raw.difference(before);outcomes=self.outcomes(needs,physical,row)
                    blob=to_wkb(raw);written+=len(blob)
                    if written>bounds['max_output_bytes']:raise ValueError('U05_ATTACHMENT_OUTPUT_BUDGET')
                    d.update(status='GROWN',scale=scale,patch_ref=store.put('geometry',blob),attachment_outcomes=outcomes)
                    if getattr(self,'certificate_consumption',False):self._certificate_run.accept(d,owner,domain,raw,physical,needs,scope)
                    accepted.append(dict(id=row['source_id'],owner=owner,window=domain,addition=raw,foreign=foreign));break
                if getattr(self,'certificate_consumption',False):self._certificate_run.decline(row['source_id'])
            if d['status']=='KEEP':d.update(reason='BLOCKED_REQUIRED_TREATMENT',attachment_outcomes=[dict(a,status='BLOCKED_CLEARANCE_OR_BOUNDARY') for a in self.outcomes(needs,Polygon(),row)])
            decisions.append(d);checkpoint(dict(next_ordinal=ordinal+1,evaluations_used=used))
        checks=[]
        for ordinal,a in enumerate(accepted):
            q=(self._certificate_run.final(a,ordinal) if getattr(self,'certificate_consumption',False)else self._check(a['owner'],a['owner'].union(a['addition']),a['addition'],a['window'],a['foreign']+[(b['id'],b['addition']) for b in accepted if b['id']!=a['id']]))
            if not q['passed']:raise ValueError('U05_ATTACHMENT_SIMULTANEOUS_FAILURE:'+str(q['failures']))
            checks.append(dict(id=a['id'],check=q))
        after=before.union(unary_union([a['addition'] for a in accepted]));output=dict(scene,objects=list(scene['objects']),lineage=scene['lineage']+[dict(stage='t05',predecessor_ref=plan['scene_ref'],policy_ref=plan['policy_ref'],implementation=plan['implementation'],plan_ref=store.put_json('plan',plan))],acceptance=dict(owner='PENDING_USER',independent='NOT_RUN',native_electrical_manufacturing='NOT_ESTABLISHED'))
        for d in decisions:
            if d['status']=='GROWN':output['objects'].append(dict(source_id=addition_source_id(d),kind='junction_addition',geometry_ref=d['patch_ref'],original_ref=d['patch_ref'],metadata=dict(origin='t05-derived-addition',owner_trace=d['source_id'],predecessor_ref=plan['scene_ref'])))
        after=self._compose_output(store,output)
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
            owner,radius,domain,foreign=self._operands(store,scene,policy,plan['details'],row);desired=self._blend_addition(owner,radius,domain).difference(before);needs=self.needs(current,row,radius,desired)
            if d['status']=='GROWN':
                if d['scale'] not in CONTRACT.radius_scales:raise ValueError('U05_ATTACHMENT_SCALE_CHANGED')
                barriers=self._local_obstacles(owner,self._foreign_for(owner,foreign+[(a['id'],a['addition']) for a in patches]),domain);expected=filled_patch(barriers.trim(self._blend_addition(owner,radius*d['scale'],domain)),before)
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
        output=validate_scene(store,candidate['output_scene_ref']);expected_rows=list(scene['objects'])
        for d in candidate['decisions']:
            if d['status']=='GROWN':expected_rows.append(dict(source_id=addition_source_id(d),kind='junction_addition',geometry_ref=d['patch_ref'],original_ref=d['patch_ref'],metadata=dict(origin='t05-derived-addition',owner_trace=d['source_id'],predecessor_ref=plan['scene_ref'])))
        expected_lineage=scene['lineage']+[dict(stage='t05',predecessor_ref=plan['scene_ref'],policy_ref=plan['policy_ref'],implementation=plan['implementation'],plan_ref=store.put_json('plan',plan))]
        if output['objects']!=expected_rows or output['lineage']!=expected_lineage or any(output[k]!=scene[k] for k in ('source_sha256','frame','units','layer','viewport_mm','findings')):raise ValueError('U05_ATTACHMENT_OUTPUT_BINDING_CHANGED')
        after=verify_assembled_output(self._snapshot,store,scene,expected_rows,output,candidate['after_ref'])
        return dict(passed=True,failures=[],reconstructed_patches=len(patches),removed_area_mm2=before.difference(after).area,verified_attachments=sum(len(d['attachment_outcomes']) for d in candidate['decisions']))
