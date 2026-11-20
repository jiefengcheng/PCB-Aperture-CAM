"""Fresh native T04 checks shared by source-built and retained-floor profiles."""
from src.t04_settings import read_snapshot, SNAPSHOT_NAME
from src.t04_incremental import IncrementalRoutes
from src.bounded_route_geometry import VersionedGeometry
from . import pipeline as p
from .profile_schedule import SCHEDULE


def run(store,scene,*,route_ids=None,settings=None,rule):
    from .t04_edge_entry import reject_unqualified_predecessor
    from .translated_profile import prepared
    from .motion_final_validation import verify
    reject_unqualified_predecessor(scene)
    if settings is None:settings=read_snapshot(store.root.parent/SNAPSHOT_NAME)
    with prepared(store,scene,route_ids,settings,rule) as (entry,construction):
        result=checked(store,entry,route_ids=construction.mutable_route_ids,settings=settings,construction=construction)
        result['motion_validation']=verify(store,result,construction)
        return result


def checked(store,scene,*,route_ids,settings,construction):
    rows,current,original=p.operands(store,scene)
    admission=construction.admission
    all_paths={v['path_id']:v for v in admission['admitted']}
    if route_ids is not None and (len(set(route_ids))!=len(route_ids) or not set(route_ids)<=set(all_paths)):
        raise ValueError('T04_REQUESTED_ROUTE_BUNDLE_NOT_ADMITTED')
    paths=all_paths if route_ids is None else {s:all_paths[s]for s in sorted(route_ids)}
    if not paths:raise ValueError('NO_EXPOSED_GERBER_ROUTES')
    if settings is None:settings=read_snapshot(store.root.parent/SNAPSHOT_NAME)
    used={m for v in paths.values()for m in v['source_ids']}
    relocation=construction is not None and getattr(construction,'relocation',False)
    if relocation:construction.validate_input(current)
    if not relocation and any(not current[m].equals_exact(original[m],0)for m in used):
        raise ValueError('T04_ORIGINAL_SOURCE_TRACE_REQUIRED; preceding-stage trace edits cannot be compounded')
    widths={};port_widths={}
    for s,path in paths.items():
        values={rows[m]['metadata']['minimum_caliper_mm']for m in path['source_ids']}
        if len(values)!=1:raise ValueError('T04_UNIFORM_SOURCE_ROUTE_WIDTH_REQUIRED:'+s)
        widths[s]=next(iter(values));port_widths[s]=max(rows[m]['metadata']['source_port_width_mm']for m in path['source_ids'])
    cores=construction.cores if relocation else {s:p.unary_union([original[m]for m in v['source_ids']])for s,v in paths.items()}
    from .checking_envelopes import NATIVE_HEADROOM_MM
    checking_headroom=NATIVE_HEADROOM_MM if(store.root.parent/'LEGACY_REFERENCE_JOB.json').exists()else 0.
    binding=p.digest(p.canonical([scene['source_sha256'],settings.source_sha256,[[s,rows[s]['original_ref']]for s in sorted(used)],p.OFFSET_FAMILY,checking_headroom]))
    routes=VersionedGeometry(paths,binding,limit=128*1024**2)
    part_builds=0
    def part(s,f,envelope):
        nonlocal part_builds
        if f==1:return original[s]
        # Route cache hits already reuse the combined shape. Keeping a second
        # cache of the intermediate offsets added churn across complete passes.
        part_builds+=1
        if construction is not None:return construction.part(s,f,envelope)
        return p.offset_part(original[s],rows[s]['metadata']['minimum_caliper_mm'],f,envelope,extra_envelope_mm=checking_headroom if envelope else 0.)
    def build_route(s,f,envelope):
        if relocation:return construction.route(s,f,envelope)
        return cores[s]if f==1 else routes.get(s,f,envelope,lambda:p.unary_union([part(m,f,envelope)for m in paths[s]['source_ids']]))
    route = build_route
    def trial(factors,envelope):
        return [dict(id=s,original=cores[s],candidate=route(s,factors[s],envelope),verified_original_width_mm=port_widths[s])for s in sorted(paths)]
    baseline=trial(dict.fromkeys(paths,1.),True)
    fixed=[dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('original_width_mm',0.))for s,g in current.items()if s not in used and (not relocation or s not in paths) and not g.is_empty]
    schedule=list(SCHEDULE)
    schedule_file=store.root.parent/'T04_PASS_SCHEDULE.json'
    if schedule_file.exists():
        captured=p.load(schedule_file)
        if captured.get('schema')!='pcb-t04-pass-schedule/1' or captured.get('pass_increments')!=schedule:
            raise ValueError('T04_PROFILE_SCHEDULE_CHANGED')
    # The source-width symmetric radius cannot bound one-sided growth.
    # Include the entire optional operand, even pieces omitted by finite union
    # certification, since a smaller progress value may retain another subset.
    from shapely.geometry import box
    from .limiting_math import MARGIN
    route_bounds={}
    for r in paths:
        d=construction.data[r]
        operands=[construction.cores[r],d['baseline_body'],d['maximum_body'],d['allowed_extension']]
        shapes=[g for g in operands if not g.is_empty]
        bounds=[g.bounds for g in shapes]
        radius=max(widths[r]*(settings.maximum_factor-1)/2,settings.maximum_total_width_increase_mm/2)+2*MARGIN
        old=construction.cores[r].envelope.buffer(radius).bounds
        route_bounds[r]=(min(old[0],*(b[0]-2*MARGIN for b in bounds)),min(old[1],*(b[1]-2*MARGIN for b in bounds)),
                         max(old[2],*(b[2]+2*MARGIN for b in bounds)),max(old[3],*(b[3]+2*MARGIN for b in bounds)))
    incremental=IncrementalRoutes(baseline,fixed,route,settings,widths,checking_headroom_mm=checking_headroom,
                                  reuse_accepted_pairs=True,route_bounds=route_bounds)
    evaluations=[]
    def evaluate(s,f):
        q=incremental.evaluate(s,f)
        evaluations.append(dict(route_id=s,factor=f,report_ref=store.put_json('width-check',q)))
        return q
    try:
        solution=construction.solve(widths,settings,evaluate,incremental.accept,pass_increments=schedule)
        selected=solution['selected_scales'];full=p.PreparedWidthScene(baseline,fixed)
        checks={}
        for name,envelope in (('nominal',False),('envelope',True)):
            selected_rows=trial(selected,envelope)
            checks[name]=full.check(selected_rows,materialize_scene=True)
            selected_geometry={row['id']:row['candidate'] for row in selected_rows}
            material={s:selected_geometry[s] for s in paths}
            voids=[dict(scope=d.scope,**d.source_voids.complete(material,selected))for d in incremental.owner_checks]
            checks[name]['original_source_voids']=voids
            if any(not q['passed']for q in voids):
                checks[name]['passed']=False
                checks[name].setdefault('failures',[]).extend(f for q in voids for f in q['failures'])
            del material,selected_geometry,selected_rows
        if not all(q['passed']for q in checks.values()):
            report=store.put_json('width-final-rejection',dict(schema='t04-complete-final-rejection/1',
                solution=solution,checks=checks,settings=settings.resolved(),qualification='REJECTED_NOT_ACCEPTED'))
            raise ValueError('T04_FRESH_FULL_FINAL_SCENE_REJECTED:'+p.canonical(report).decode('ascii'))
        after=dict(current);factors={};publication_metadata=None;additions=[];motion_ref=None
        if relocation:
            after,publication_metadata,additions,motion_ref=construction.publication(store,current,selected)
            factors={m:selected[s] for s,path in paths.items() for m in path['source_ids']}
        else:
            for s,path in paths.items():
                for m in path['source_ids']:after[m]=part(m,selected[s],False);factors[m]=selected[s]
        # Freeze denied widening material before any remedy can consider it.
        from src import t04_width_fence as fence
        before=p.unary_union(list(current.values()));denied=[]
        for s in sorted(paths):
            # Include the unsupported side of the cap as well as rejected
            # rungs. Extra padding covers native encoding uncertainty only.
            extent=max(widths[s]*(settings.maximum_factor-1)/2,
                       settings.maximum_total_width_increase_mm/2)+.000004
            denied.append(cores[s].buffer(extent,quad_segs=128))
        # A neighbouring route's independently approved copper is legitimate
        # material even where source-bound dependency corridors overlap. Freeze
        # the complete accepted scene, not a separate subtraction per corridor.
        # Only the existing native polygon fidelity allowance surrounds it;
        # the larger conservative clearance envelope is not remedy authority.
        accepted=p.unary_union(list(after.values())+[p.geometry(store,r['geometry_ref']) for r in additions])
        fence.ACTIVE=fence.Rule.from_accepted(p.unary_union(denied),accepted,before,binding)
        publication_scene=scene
        if relocation:publication_scene=dict(scene,lineage=scene['lineage']+[dict(stage='t04-translated-profile-published',receipt_ref=motion_ref)])
        ref=p.artifact_scene(store,publication_scene,after,'t04',metadata=publication_metadata,additions=additions)
        result=dict(output_scene_ref=ref,admission=admission,qualification_route_ids=None if route_ids is None else sorted(route_ids),
                    solution=solution,checks=checks,evaluations=evaluations,part_factors=factors,
                    settings_snapshot=dict(source_sha256=settings.source_sha256,resolved=settings.resolved()),
                    checking_only_native_headroom_mm=checking_headroom,
                    incremental=dict(incremental.diagnostics(),route_geometry=routes.diagnostics(),
                                     part_geometry=dict(requests=part_builds,builds=part_builds,hits=0,
                                                        retained_estimated_bytes=0,limit_bytes=0)),
                    source_offset_definition='Original-source uniform outward offset; per-route ten-rung ladder; simultaneous factor and total-width caps; unchanged source cores, centreline, smoothing and final checks.',
                    summary=dict(trace_occurrences=admission['trace_occurrences'],routes=len(paths),groups=len(admission['groups']),
                                 grown_parts=sum(f>1 for f in factors.values()),evaluations=solution['evaluation_count'],
                                 geometry_evaluations=solution['geometry_evaluation_count'],passes=len(solution['passes']),
                                 ladder_process_completed=True,maximum_claim='NONE'))
        if construction is not None:
            result['limiting_construction']=construction.receipt
            result['source_offset_definition']='Uniform per-route limiting-segment construction; stored effective widths; ladder factors denote progress to the route default.'
            if relocation:result['source_offset_definition']='One rigid translation per complete source route; aggregate variable-width body; explicit vacated-trace ledger and source aliases; effective factors are width ceilings.'
            if getattr(construction,'profiles',None):result['source_offset_definition']='Local outward profiles with exact original cores, 10% route width band and 0.05 mm cap transitions; effective factors are nominal width ceilings.'
            result['part_effective_factors']={m:construction.effective(m,selected[r]) for r,path in paths.items() for m in path['source_ids']}
            result['summary']['grown_parts']=sum(v>1 for v in result['part_effective_factors'].values())
        result['settings_snapshot']['pass_increments']=schedule
        return result
    finally:
        routes.close()
