"""Source-role-first T04 construction with an explicitly qualified full scope.

Bulk roles never depend on the mutable set. Mixed native paths retain their
identity while only non-bulk occurrences become trace growth cores. All source
occurrences, including zero-contribution bulk tombstones, remain in the ledger.
"""
from collections import Counter
from contextlib import contextmanager,redirect_stdout
import copy,gzip,hashlib,io,json,runpy,shutil
from pathlib import Path
from time import perf_counter
from shapely import STRtree
from shapely.geometry import Polygon
from shapely.ops import unary_union
from src import component_clearance as cc,source_channel_scope as sc,pin_separation as pin
from src.trace_width_clearance import TraceWidthContract
from . import pipeline as p
from .limiting_growth import Construction as BaseConstruction,local_allowance,split_budget,preserve_connections,working_scope
from .limiting_math import collect_proposals,GUARD,MARGIN
from .source_roles import prepare_or_load,project

SCHEMA='t04-source-role-limiting-growth/2'
ENTRY_STAGE='t04-limiting-entry-v2'


def validate_scope(rule,route_ids):
    if rule.get('schema')!=SCHEMA:raise ValueError('T04_ROLE_GROWTH_SCHEMA_CHANGED')
    mode=rule.get('scope')
    if mode=='BOUNDED':
        if not route_ids or len(route_ids)>128 or len(route_ids)!=len(set(route_ids)):
            raise ValueError('T04_ROLE_GROWTH_BOUNDED_SCOPE_REQUIRED')
    elif mode=='FULL_BOARD':
        if route_ids is not None:raise ValueError('T04_FULL_BOARD_MUST_USE_COMPLETE_SOURCE_SCOPE')
        if not rule.get('qualification_manifest'):raise ValueError('T04_FULL_SOURCE_QUALIFICATION_REQUIRED')
        from .profile_readiness import require
        require(rule['qualification_manifest'],rule)
    else:raise ValueError('T04_ROLE_GROWTH_EXPLICIT_SCOPE_REQUIRED')


def catalogue(store,scene,rows,admission,roles,rule):
    """One source-wide catalogue, independent of the chosen mutable routes."""
    root=Path(rule['group_cache']);body=Path(__file__).read_bytes()
    templates=[Path(__file__).with_name(n).read_bytes() for n in ('_parallel_catalogue.py','_curve_catalogue.py')]
    from .source_roles import classifier_signature
    signature=hashlib.sha256(body+b''.join(templates)).hexdigest()
    source_key=dict(scene_sha256=p.digest(p.canonical(scene)),role_table_sha256=rule['role_table_sha256'],algorithm_sha256=signature,projection_sha256=hashlib.sha256(Path(__file__).with_name('source_roles.py').read_bytes()).hexdigest(),minimum_shared_length_mm=.05,noise_fraction=.01)
    if (root/'BINDING.json').exists():
        binding=json.loads((root/'BINDING.json').read_text())
        if binding['source_key']!=source_key:raise ValueError('T04_GROUP_CACHE_BINDING_CHANGED')
        result=[]
        for name in ('GROUPS.json.gz','CURVE_GROUPS.json.gz'):
            raw=(root/name).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=binding['files'][name]:raise ValueError('T04_GROUP_CACHE_BYTES_CHANGED')
            result.append(json.loads(gzip.decompress(raw)))
        return (*result,binding)
    root.mkdir(exist_ok=False)
    folder=store.root.parent/'group_build';folder.mkdir()
    segments=[dict(source_id=s,original_ref=r['original_ref'],metadata=r['metadata']) for s,r in sorted(rows.items()) if r['kind']=='stroke' and s not in roles]
    grouped=copy.deepcopy(admission)
    grouped['paths']=[]
    for decision in admission['paths']:
        ids=decision['growth_source_ids']
        if ids:grouped['paths'].append(dict(decision,path=dict(decision['path'],source_ids=ids,ordered_source_edges=decision['growth_source_edges'])))
    (folder/'segments.json.gz').write_bytes(gzip.compress(p.canonical(segments),mtime=0))
    (folder/'admission.json.gz').write_bytes(gzip.compress(p.canonical(grouped),mtime=0))
    inputs=dict(source_sha256=scene['source_sha256'],scene_ref=rule['input_binding']['scene_ref'],cohort_routes=sorted(v['path_id'] for v in admission['admitted']))
    inputs['selection_input_hashes']={n:hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in ('segments.json.gz','admission.json.gz')}
    (folder/'INPUTS.json').write_text(json.dumps(inputs))
    code=templates[0].decode().replace('(.05,.1,.25)','(.05,)').replace('(.05, .1, .25)','(.05,)')
    with redirect_stdout(io.StringIO()):
        exec(compile(code,str(folder/'assess.py'),'exec'),{'__file__':str(folder/'assess.py')})
        inputs['selection_input_hashes']['GROUPS.json.gz']=hashlib.sha256((folder/'GROUPS.json.gz').read_bytes()).hexdigest()
        (folder/'INPUTS.json').write_text(json.dumps(inputs))
        curve=runpy.run_path(str(Path(__file__).with_name('_curve_catalogue.py')))
        curve['main'].__globals__.update(ROOT=folder,BASE=folder,MINIMUMS=(.05,));curve['main']()
    for name in ('GROUPS.json.gz','CURVE_GROUPS.json.gz'):shutil.copyfile(folder/name,root/name)
    binding=dict(source_key=source_key,files={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('GROUPS.json.gz','CURVE_GROUPS.json.gz')})
    (root/'BINDING.json').write_text(json.dumps(binding,indent=2,sort_keys=True)+'\n')
    shutil.rmtree(folder)
    return (*(json.loads(gzip.decompress((root/n).read_bytes())) for n in ('GROUPS.json.gz','CURVE_GROUPS.json.gz')),binding)


class Construction(BaseConstruction):
    def __init__(self,*args,settings,progress=None,**kwargs):
        super().__init__(*args,settings=settings,**kwargs)
        # This is progress toward a bounded profile, not a discrete physical
        # factor. Effective widths separately obey BOTH numeric source caps.
        self.maximum=dict.fromkeys(self.paths,settings.maximum_factor)
        self.mutable_route_ids=sorted(self.paths);self.progress=progress
    def effective(self,s,f):
        if not getattr(self,'profiles',None):return super().effective(s,f)
        r=self.owner[s];w=self.rows[s]['metadata']['minimum_caliper_mm']
        return 1+2*self.profiles[s]['radial_mm']*(f-1)/(self.maximum[r]-1)/w
    def part(self,s,f,envelope):
        if not getattr(self,'profiles',None):return super().part(s,f,envelope)
        from .local_profile import profile_part
        r=self.owner[s];w=self.rows[s]['metadata']['minimum_caliper_mm']
        return profile_part(self.original[s],self.rows[s]['metadata']['route_points_mm'],w,self.profiles[s],(f-1)/(self.maximum[r]-1),envelope)
    def solve(self,widths,settings,evaluate,accept,**kwargs):
        count=0
        def measured(s,f):
            nonlocal count
            if self.progress:self.progress(dict(event='proposal_start',route=s,index=count+1))
            q=evaluate(s,f);count+=1
            if self.progress:self.progress(dict(event='proposal_done',route=s,index=count,passed=q['passed']))
            return q
        value=super().solve(widths,settings,measured,accept,**kwargs)
        value['schema']=SCHEMA;value['geometry_family']='uniform-projected-trace-route-minimum'
        value['scope']=self.receipt['scope']
        if getattr(self,'profiles',None):value['geometry_family']='original-core-preserving-local-profile; effective factors are width ceilings'
        return value


@contextmanager
def prepared(store,scene,route_ids,settings,rule):
    validate_scope(rule,route_ids)
    started=perf_counter();rows,current,original=p.operands(store,scene)
    context=sc.ACTIVE if sc.ACTIVE is not None else cc.ACTIVE
    if context is None:raise ValueError('T04_SOURCE_OWNER_CONTEXT_REQUIRED')
    index=context.index
    roles,native,source_binding=prepare_or_load(rule['source_preparation'],store,scene,(rows,current,original),index)
    actual_role_sha=hashlib.sha256((Path(rule['source_preparation'])/'ROLES.json.gz').read_bytes()).hexdigest()
    if rule.get('role_table_sha256') is None:rule['role_table_sha256']=actual_role_sha
    if actual_role_sha!=rule['role_table_sha256']:
        raise ValueError('T04_SOURCE_ROLE_TABLE_CHANGED')
    forbidden=set(getattr(context,'frame_ids',()))
    if pin.ACTIVE is not None:forbidden.update(s for slot in pin.ACTIVE.slots for s in slot.pin_ids)
    if forbidden&set(roles):raise ValueError('T04_PROTECTED_SOURCE_HAS_BULK_ROLE')
    admission=project(native,roles)
    from src import trace_growth_policy
    eligibility,_=trace_growth_policy.prepare(
        p.ROOT/'out/lacie_work/source_artifacts/t04_trace_eligibility',scene,rows,current,
        {v['path_id']:v['source_ids']for v in admission['admitted']},trace_growth_policy.for_job(store))
    protected_by_policy=set(eligibility['fixed_source_ids'])
    raw_paths={v['path_id']:v for v in native['admitted']}
    requested=sorted(raw_paths) if route_ids is None else sorted(route_ids)
    if not set(requested)<=set(raw_paths):raise ValueError('T04_NATIVE_REQUESTED_PATH_CHANGED')
    admitted={v['path_id']:v['source_ids'] for v in admission['admitted']}
    paths={r:admitted[r] for r in requested if r in admitted and r not in eligibility['kept_routes']}
    if not paths:raise ValueError('T04_NO_TRACE_GROWTH_CORES_IN_REQUEST')
    used={s for members in paths.values() for s in members}
    if used&set(roles):raise ValueError('T04_EDITABLE_BULK_USED_AS_TRACE_CORE')
    cores={r:unary_union([original[s] for s in ss]) for r,ss in paths.items()}
    straight,curves,group_binding=catalogue(store,scene,rows,admission,roles,rule)
    roles={s:v for s,v in roles.items()if s not in protected_by_policy}
    parallel,_,_,_=collect_proposals(rows,paths,straight,curves,original,roles)
    caps={r:min(settings.maximum_total_width_increase_mm/2,*(rows[s]['metadata']['minimum_caliper_mm']*(settings.maximum_factor-1)/2 for s in ss)) for r,ss in paths.items()}
    targets={r:min(parallel.get(r,caps[r]),caps[r]) for r in paths}
    initial=dict(targets);limits=[];contract=TraceWidthContract()
    hard=set(rows)-set(roles);hard|=forbidden
    # Coupled allocation replaces these targets and limits completely.
    # Do not first perform the independent per-segment allowance search.
    if not rule.get('coupled_allocation'):
        fixedids=sorted(hard-used)
        obstacle_ids=fixedids+sorted(paths)
        obstacles=[current[s] for s in fixedids]+[cores[r] for r in sorted(paths)]
        tree=STRtree(obstacles)
        maximum=max(initial.values(),default=0.)
        for r,seed in sorted(initial.items()):
            if seed<=0:continue
            width=rows[paths[r][0]]['metadata']['minimum_caliper_mm']
            port_width=max(rows[s]['metadata']['source_port_width_mm'] for s in paths[r])
            for i in sorted(map(int,tree.query(cores[r],predicate='dwithin',distance=seed+maximum+GUARD+2*MARGIN))):
                oid=obstacle_ids[i]
                if oid==r:continue
                other=obstacles[i];mutable=oid in initial
                otherwidth=rows[paths[oid][0]]['metadata']['minimum_caliper_mm'] if mutable else None
                otherport=max(rows[s]['metadata']['source_port_width_mm'] for s in paths[oid]) if oid in paths else rows[oid]['metadata'].get('original_width_mm',0.)
                overlap=cores[r].intersection(other)
                port=None if overlap.is_empty else overlap.buffer(max(port_width,otherport)+contract.original_port_buffer_gap_mm,quad_segs=contract.port_quad_segs)
                radius=max(seed,initial.get(oid,0.))
                for sid in paths[r]:
                    budget=local_allowance(original[sid],other,radius,port)
                    if budget is None:continue
                    a,b=split_budget(budget,width,otherwidth)
                    if a<targets[r] or mutable and b<targets[oid]:limits.append(dict(route=r,segment=sid,neighbor=oid,budget_mm=budget,own_radial_mm=a,neighbor_radial_mm=b,mutable_neighbor=mutable,original_contact=port is not None))
                    targets[r]=min(targets[r],a)
                    if mutable:targets[oid]=min(targets[oid],b)
    allocation=None
    if rule.get('coupled_allocation'):
        from .coupled_growth import allocate
        targets,allocation=allocate(rows,current,original,paths,roles,context,straight,curves,caps)
        limits=[]  # Superseded by the coupled constraint graph, not individual shares.
    protected=unary_union([current[s] for s in sorted(hard)])
    if pin.ACTIVE is not None:protected=unary_union([protected,*[s.domain for s in pin.ACTIVE.slots]])
    grown={r:cores[r].buffer(d,quad_segs=128) if d>0 else cores[r] for r,d in targets.items()}
    corridors=unary_union([g.buffer(GUARD+2*MARGIN,quad_segs=128) for g in grown.values()])
    # Preserve every original bulk attachment, including contacts inside a
    # native segment, rather than only checking its two endpoints.
    bulk_ids=sorted(roles);bulk_geoms=[original[s] for s in bulk_ids];btree=STRtree(bulk_geoms);ports=[]
    for r,core in cores.items():
        width=max(rows[s]['metadata']['source_port_width_mm'] for s in paths[r])
        for i in sorted(map(int,btree.query(core,predicate='intersects'))):
            sid=bulk_ids[i];overlap=core.intersection(bulk_geoms[i])
            if not overlap.is_empty:
                w=max(width,rows[sid]['metadata'].get('original_width_mm',0.))
                ports.append(overlap.buffer(w+contract.original_port_buffer_gap_mm,quad_segs=contract.port_quad_segs))
    corridor=corridors.difference(unary_union(ports))
    area=(scene['viewport_mm'][2]-scene['viewport_mm'][0])*(scene['viewport_mm'][3]-scene['viewport_mm'][1])
    large=[g for g in index.owners if g.area>area*.05]
    bulk=unary_union(large)
    removal=bulk.difference(protected).intersection(corridor)
    changed={s:(g.difference(removal) if s in roles and g.intersects(removal.envelope) else g) for s,g in current.items()}
    if any(not changed[s].equals_exact(current[s],0) for s in hard):raise ValueError('T04_PROTECTED_SOURCE_CHANGED')
    changed,retained,components=preserve_connections(context,current,changed)
    empty={s for s,g in changed.items() if g.is_empty}
    if not empty<=set(roles):raise ValueError('T04_NON_BULK_SOURCE_REMOVED')
    ledger=dict(schema=SCHEMA,scope=rule['scope'],source_sha256=scene['source_sha256'],input_scene_ref=rule['input_binding']['scene_ref'],source_preparation_sha256=hashlib.sha256((Path(rule['source_preparation'])/'BINDING.json').read_bytes()).hexdigest(),group_binding=group_binding,
        requested_native_route_ids=requested,growth_source_ids_by_route=paths,
        source_role_dispositions={r:admission['source_role_dispositions'][r] for r in requested},
        native_path_source_ids={r:raw_paths[r]['source_ids'] for r in requested},bulk_roles=roles,
        protected_source_ids=sorted(hard),parallel_seeds_radial_mm=parallel,targets_radial_mm=targets,
        default_basis={r:'PARALLEL_MINIMUM' if r in parallel else 'SOURCE_CAP_WITH_ALL_NEIGHBOR_ALLOWANCES' for r in paths},limits=limits,
        removal_ref=p.geomref(store,removal),requested_removal_mm2=removal.area,
        connectivity_retained_source_ids=retained,baseline_owner_components=components,
        width_tolerance=.10,within_route_width_variation=0.,shared_parallel_length_mm=.05,
        removed_bulk_sources={})
    if allocation is not None:
        ledger['coupled_allocation']=allocation
        ledger['default_basis']=dict.fromkeys(paths,'COUPLED_PROPORTIONAL_MAX_MIN')
        if rule.get('local_profile'):
            from .local_profile import local_targets
            ledger['local_profiles']=local_targets(paths,rows,targets,allocation)
            ledger['within_route_width_variation_bound']=.10
            ledger['within_route_width_variation']='VARIABLE_PROFILE_WITH_BOUNDED_WIDTH_CEILING'
    refs={s:p.geomref(store,g) for s,g in changed.items() if not g.equals_exact(current[s],0)}
    objects=[]
    for row in scene['objects']:
        sid=row['source_id'];value=dict(row)
        if sid in refs:value['geometry_ref']=refs[sid]
        if sid in empty:
            marker=dict(schema=SCHEMA,source_id=sid,original_ref=row['original_ref'],before_ref=row['geometry_ref'],after_ref=refs[sid],role_witness_sha256=p.digest(p.canonical(roles[sid])))
            ledger['removed_bulk_sources'][sid]=marker
            value['metadata']=dict(row['metadata'],removed_bulk_source=marker)
        objects.append(value)
    old_cc,old_sc=cc.ACTIVE,sc.ACTIVE
    working_cc=working_scope(old_cc,removal,ledger,changed,components);working_sc=working_scope(old_sc,removal,ledger,changed,components)
    if working_cc is not None:working_cc.functional=working_sc
    if working_sc is not None:working_sc.physical_context=working_cc
    if pin.ACTIVE is not None:
        proof=pin.ACTIVE.check_parts(changed.values())
        if not proof['passed']:raise ValueError('T04_ROLE_ENTRY_PIN_REJECTED')
        ledger['entry_pin_check']=proof
    receipt_ref=store.put_json('t04-source-projection-entry',ledger)
    entry=dict(scene,objects=objects,lineage=scene['lineage']+[dict(stage=ENTRY_STAGE,receipt_ref=receipt_ref)])
    construction=Construction(paths,original,rows,targets,settings=settings,receipt=ledger,admission=admission,progress=rule.get('progress'))
    construction.profiles=ledger.get('local_profiles')
    construction.preparation_seconds=perf_counter()-started
    cc.ACTIVE,sc.ACTIVE=working_cc,working_sc
    try:yield entry,construction
    finally:cc.ACTIVE,sc.ACTIVE=old_cc,old_sc;construction.cache.clear()
