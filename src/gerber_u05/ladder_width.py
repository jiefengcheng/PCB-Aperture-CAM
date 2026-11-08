"""Source-bound Gerber T04 route ladder; groups retain dependency metadata."""
from src.t04_settings import capture, read_snapshot, SNAPSHOT_NAME
from src.t04_ladder import solve
from src.t04_incremental import IncrementalRoutes
from src.bounded_route_geometry import VersionedGeometry
from . import pipeline as p


def run(store,scene,*,route_ids=None,settings=None):
    rows,current,original=p.operands(store,scene);admission=p.width_admission(store,scene)
    all_paths={v['path_id']:v for v in admission['admitted']}
    if route_ids is not None and (len(set(route_ids))!=len(route_ids) or not set(route_ids)<=set(all_paths)):
        raise ValueError('T04_REQUESTED_ROUTE_BUNDLE_NOT_ADMITTED')
    paths=all_paths if route_ids is None else {s:all_paths[s]for s in sorted(route_ids)}
    if not paths:raise ValueError('NO_EXPOSED_GERBER_ROUTES')
    if settings is None:settings=read_snapshot(store.root.parent/SNAPSHOT_NAME)
    used={m for v in paths.values()for m in v['source_ids']}
    if any(not current[m].equals_exact(original[m],0)for m in used):
        raise ValueError('T04_ORIGINAL_SOURCE_TRACE_REQUIRED; preceding-stage trace edits cannot be compounded')
    widths={};port_widths={}
    for s,path in paths.items():
        values={rows[m]['metadata']['minimum_caliper_mm']for m in path['source_ids']}
        if len(values)!=1:raise ValueError('T04_UNIFORM_SOURCE_ROUTE_WIDTH_REQUIRED:'+s)
        widths[s]=next(iter(values));port_widths[s]=max(rows[m]['metadata']['source_port_width_mm']for m in path['source_ids'])
    cores={s:p.unary_union([original[m]for m in v['source_ids']])for s,v in paths.items()}
    from .checking_envelopes import NATIVE_HEADROOM_MM
    checking_headroom=NATIVE_HEADROOM_MM if(store.root.parent/'LEGACY_REFERENCE_JOB.json').exists()else 0.
    binding=p.digest(p.canonical([scene['source_sha256'],settings.source_sha256,[[s,rows[s]['original_ref']]for s in sorted(used)],p.OFFSET_FAMILY,checking_headroom]))
    parts=VersionedGeometry(used,binding,limit=32*1024**2)
    routes=VersionedGeometry(paths,binding,limit=128*1024**2)
    def part(s,f,envelope):
        return original[s]if f==1 else parts.get(s,f,envelope,lambda:p.offset_part(original[s],rows[s]['metadata']['minimum_caliper_mm'],f,envelope,extra_envelope_mm=checking_headroom if envelope else 0.))
    def route(s,f,envelope):
        return cores[s]if f==1 else routes.get(s,f,envelope,lambda:p.unary_union([part(m,f,envelope)for m in paths[s]['source_ids']]))
    def trial(factors,envelope):
        return [dict(id=s,original=cores[s],candidate=route(s,factors[s],envelope),verified_original_width_mm=port_widths[s])for s in sorted(paths)]
    baseline=trial(dict.fromkeys(paths,1.),True)
    fixed=[dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('original_width_mm',0.))for s,g in current.items()if s not in used]
    incremental=IncrementalRoutes(baseline,fixed,route,settings,widths,checking_headroom_mm=checking_headroom);evaluations=[]
    def evaluate(s,f):
        q=incremental.evaluate(s,f);evaluations.append(dict(route_id=s,factor=f,report_ref=store.put_json('width-check',q)));return q
    try:
        solution=solve(widths,settings,evaluate,incremental.accept)
        selected=solution['selected_scales'];full=p.PreparedWidthScene(baseline,fixed)
        checks={name:full.check(trial(selected,envelope),materialize_scene=True)
                for name,envelope in (('nominal',False),('envelope',True))}
        for name,envelope in (('nominal',False),('envelope',True)):
            material={s:route(s,selected[s],envelope)for s in paths}
            voids=[dict(scope=d.scope,**d.source_voids.complete(material,selected))for d in incremental.owner_checks]
            checks[name]['original_source_voids']=voids
            if any(not q['passed']for q in voids):
                checks[name]['passed']=False
                checks[name].setdefault('failures',[]).extend(f for q in voids for f in q['failures'])
        if not all(q['passed']for q in checks.values()):
            report=store.put_json('width-final-rejection',dict(schema='t04-complete-final-rejection/1',
                solution=solution,checks=checks,settings=settings.resolved(),qualification='REJECTED_NOT_ACCEPTED'))
            raise ValueError('T04_FRESH_FULL_FINAL_SCENE_REJECTED:'+p.canonical(report).decode('ascii'))
        after=dict(current);factors={}
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
        accepted=p.unary_union(list(after.values()))
        fence.ACTIVE=fence.Rule.from_accepted(p.unary_union(denied),accepted,before,binding)
        ref=p.artifact_scene(store,scene,after,'t04')
        return dict(output_scene_ref=ref,admission=admission,qualification_route_ids=None if route_ids is None else sorted(route_ids),
                    solution=solution,checks=checks,evaluations=evaluations,part_factors=factors,
                    settings_snapshot=dict(source_sha256=settings.source_sha256,resolved=settings.resolved()),
                    checking_only_native_headroom_mm=checking_headroom,
                    incremental=dict(incremental.diagnostics(),route_geometry=routes.diagnostics(),part_geometry=parts.diagnostics()),
                    source_offset_definition='Original-source uniform outward offset; per-route ten-rung ladder; simultaneous factor and total-width caps; unchanged source cores, centreline, smoothing and final checks.',
                    summary=dict(trace_occurrences=admission['trace_occurrences'],routes=len(paths),groups=len(admission['groups']),
                                 grown_parts=sum(f>1 for f in factors.values()),evaluations=solution['evaluation_count'],
                                 geometry_evaluations=solution['geometry_evaluation_count'],passes=len(solution['passes']),
                                 ladder_process_completed=True,maximum_claim='NONE'))
    finally:parts.close();routes.close()
