#!/usr/bin/env python3
"""Explicit original-source full-board T04 diagnostic after saved cleanup.

No accepted-T03 custody, later stage, export or completed-T04 claim is created.
The accepted-T03 group_board_job entry and its readiness contract are unchanged.
"""
import argparse
import json
import sys
import time
import traceback
from contextlib import nullcontext
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shapely import to_wkb
from shapely.ops import unary_union
from src.gerber_u05 import pipeline as p, profile_intake as intake, bounded_order as b
from src.gerber_u05 import group_stage, group_board_job as board
from src.gerber_u05.trimmed_entry import load_cleanup, bind_floor
from src.shared_copper_context import for_board
from src.t04_settings import capture_job, read_snapshot, SNAPSHOT_NAME
from src import hole_acceptance


def verify_preserved_contributions(before, after, fixed_ids, terminal_ids, admitted_ids, removed=None):
    """Preserve fixed cleanup objects without inventing a permanent keep-out.

    The saved subtractive predecessor is an input, not an additional obstacle
    policy. Eligible T04 widening may enter previously removed space. Account
    for it explicitly while rejecting any restoration by a fixed/unadmitted
    contribution. Only local overlaps are unioned, not the whole board again.
    """
    if tuple(before)!=tuple(after):raise ValueError('T04_PRESERVATION_INVENTORY_CHANGED')
    fixed_ids=set(fixed_ids);terminal_ids=set(terminal_ids);admitted_ids=set(admitted_ids)
    changed={s for s in before if to_wkb(before[s])!=to_wkb(after[s])}
    if changed&fixed_ids:raise ValueError('T04_FIXED_CLEANUP_CONTRIBUTION_CHANGED')
    if changed&terminal_ids:raise ValueError('T04_TRIMMED_TERMINAL_CONTEXT_CHANGED')
    if changed-admitted_ids:raise ValueError('T04_UNADMITTED_CONTRIBUTION_CHANGED:'+min(changed-admitted_ids))
    overlaps=[];records=[]
    for s in sorted(changed)if removed is not None else():
        g=after[s]
        if g.is_empty or not removed.intersects(g):continue
        overlap=g.intersection(removed)
        if overlap.area<=p.EPS:continue
        if s not in admitted_ids:raise ValueError('T04_UNADMITTED_CLEANUP_RESTORATION:'+s)
        overlaps.append(overlap);records.append(dict(source_id=s,area_mm2=overlap.area,
            geometry_sha256=p.digest(to_wkb(g))))
    return dict(passed=True,fixed_occurrences_byte_preserved=len(fixed_ids),
        terminal_occurrences_byte_preserved=len(terminal_ids),
        changed_occurrences=len(changed),all_changes_admitted=True,
        cleanup_removed_mm2=None if removed is None else removed.area,
        eligible_growth_reentry_mm2=None if removed is None else unary_union(overlaps).area if overlaps else 0.,
        eligible_growth_reentry=records,
        reentry_measurement='NOT_RUN_INFORMATIONAL_ONLY'if removed is None else'INFORMATIONAL_ONLY',
        policy='FIXED_CLEANUP_CONTRIBUTIONS_RETAINED; ELIGIBLE_T04_GROWTH_ALLOWED; NO_PERMANENT_KEEPOUT')



def execute(source_job, cleanup_result, output, preparation_from=None, *, control='trimmed',route_ids=None,finalize_from=None):
    p.configure()
    output = Path(output).resolve()
    if not output.is_relative_to((p.ROOT/'out/lacie_work').resolve()):
        raise ValueError('T04_AFTER_CLEANUP_REQUIRES_LACIE')
    output.mkdir(parents=True, exist_ok=False)
    started=time.perf_counter(); phases={}; active='setup'; stage=None
    def phase(name, fn):
        nonlocal active
        active=name; tick=time.perf_counter()
        print(json.dumps(dict(event='start',phase=name)),flush=True)
        result=fn(); phases[name]=time.perf_counter()-tick
        print(json.dumps(dict(event='done',phase=name,wall_s=phases[name])),flush=True)
        return result
    try:
        from tools.preflight import verify_manifest
        assets=phase('asset_manifest',verify_manifest)
        reader=intake.EvidenceStore(source_job)
        binding=p.load(Path(source_job)/'source.json')
        original=reader.get_json(binding['scene_ref'],kind='scene')
        reader.get(binding['source_ref'],kind='gerber-source')
        if control=='trimmed':
            cleanup, changes, custody=load_cleanup(cleanup_result,binding['source_ref']['sha256'])
            if cleanup['input_binding']['original_scene_ref'] != binding['scene_ref']:
                raise ValueError('T04_CLEANUP_ORIGINAL_SCENE_CHANGED')
        elif control in ('baseline','identity'):
            changes={};custody=dict(source_sha256=binding['source_ref']['sha256'],control=control,
                counts=dict(corrected=0,unresolved=0,ignored=0),scope='ORIGINAL_SOURCE_PARITY_CONTROL; NO_CLEANUP_EXECUTED')
        else:raise ValueError('T04_ENTRY_CONTROL_REQUIRED')
        intake.prepare(output, source_job)
        # Capture current settings/nominal eligibility together, rather than
        # using an old retained ladder snapshot with a different width policy.
        old=output/SNAPSHOT_NAME
        if old.exists(): old.rename(output/'RETAINED_T04_SETTINGS_SNAPSHOT.json')
        capture_job(output); settings=read_snapshot(output/SNAPSHOT_NAME)
        from src.trace_growth_policy import capture_job as capture_eligibility
        capture_eligibility(output)
        holes=hole_acceptance.bind(output)
        p.save(output/'source.json',binding)
        store=b.ExperimentStore(output/'runtime',reader)
        rows, source, raw_original=p.operands(store,original)
        if not changes.keys() <= source.keys(): raise ValueError('T04_CLEANUP_UNKNOWN_SOURCE')
        current=dict(source); current.update(changes)
        floor=bind_floor(rows,current,raw_original,custody)
        if control=='baseline':entry=original;entry_ref=binding['scene_ref']
        else:
            entry_ref=p.artifact_scene(store,original,current,'verified-large-copper-trim-entry')
            entry=store.get_json(entry_ref,kind='scene')
            entry['lineage'][-1]['receipt_ref']=store.put_json('t04-trimmed-entry',floor)
            entry_ref=store.put_json('scene',entry)
        phase('source_identity_validation',lambda:b.require_source(store,binding,entry))
        p.save(output/'TRIMMED_ENTRY.json',floor)
        inputs=dict(schema='t04-after-cleanup/1',scope='T04_ONLY',context='original',accepted_t03=False,
            source_sha256=binding['source_ref']['sha256'],original_scene_ref=binding['scene_ref'],
            scene_ref=binding['scene_ref'],trimmed_entry_scene_ref=entry_ref,cleanup=custody,
            predecessor_scene_sha256=entry_ref['sha256'],new_predecessor_acceptance=False)
        full_board=route_ids is None
        scope='FULL_BOARD_DIAGNOSTIC' if full_board else 'BOUNDED'
        p.save(output/'JOB.json',dict(inputs=inputs,scope=scope,control=control,
            source_files=intake.source_inventory(),full_board_run=full_board,complete_t04=False))
        def progress(event):
            value=dict(event,elapsed_s=time.perf_counter()-started)
            with (output/'PROGRESS.jsonl').open('a') as stream:stream.write(json.dumps(value)+'\n')
            if event.get('event')!='hybrid_residual' or event.get('index',0)%100==0:
                print(json.dumps(value),flush=True)
        cache=Path(preparation_from).resolve() if preparation_from else output/'preparation'
        if not cache.is_relative_to((p.ROOT/'out/lacie_work').resolve()):
            raise ValueError('T04_PREPARATION_REQUIRES_LACIE')
        if preparation_from:
            if not cache.is_dir():raise ValueError('T04_PREPARATION_MISSING')
        else:cache.mkdir()
        rule=dict(scope=scope,full_board_diagnostic=full_board,hybrid_components=True,
            input_binding=inputs,source_preparation=str(cache/'roles'),
            relationship_cache_root=str(cache/'relationships'),member_cache=str(cache/'members'),
            arc_member_cache=str(cache/'arcs'),coverage_cache=str(cache/'coverage'),
            group_cache=str(cache/'groups'),residual_end_matching=True,residual_chain_matching=True,
            residual_end_deviation=.1,progress=progress)
        if control!='baseline':rule['trimmed_entry']=floor
        # T04's established distance engine/lifetime remains untouched. Shared
        # source preparation is an explicit dependency of the input/pocket
        # boundary, not a process-wide override of all T04 measurements.
        from src import indexed_polygon_distance as distance
        if distance.measurement_engine().owner is not None:
            raise ValueError('T04_BASELINE_DISTANCE_LIFETIME_REQUIRED')
        engine=distance.measurement_engine()
        with (nullcontext(None) if control=='baseline' else for_board(raw_original,role='native-stage')) as copper:
            retained_execution=None
            if finalize_from is None:
                phase('source_context_construction',lambda:p.initialize_t04(store,binding,entry))
                stage=phase('full_board_t04' if full_board else 'bounded_t04',lambda:group_stage.run(
                    store,entry,route_ids=route_ids,settings=settings,rule=rule,copper=copper))
            else:
                # Separate finalization of the completed, unchanged T04 code.
                # Never resume or rewrite the failed job, or accept any other
                # failed operation. The old integration-only zero-overlap guard
                # incorrectly introduced an unrequested permanent keep-out.
                def authenticate_completed_construction():
                    prior=Path(finalize_from).resolve()
                    if not prior.is_relative_to((p.ROOT/'out/lacie_work').resolve()):raise ValueError('T04_FINALIZATION_REQUIRES_LACIE')
                    job=p.load(prior/'JOB.json');failure=p.load(prior/'FAILURE.json')
                    from src.trace_growth_policy import read_snapshot as read_eligibility_snapshot, SNAPSHOT as ELIGIBILITY_SNAPSHOT
                    if (control!='trimmed' or not full_board or job['inputs']!=inputs or
                        job['source_files']!=intake.source_inventory() or
                        read_snapshot(prior/SNAPSHOT_NAME).resolved()!=settings.resolved() or
                        read_eligibility_snapshot(prior/ELIGIBILITY_SNAPSHOT)!=read_eligibility_snapshot(output/ELIGIBILITY_SNAPSHOT) or
                        failure['phase']!='cleanup_and_terminal_preservation' or
                        not failure['error'].startswith("ValueError('T04_REGREW_APPROVED_CLEANUP:") or
                        'full_board_t04'not in failure['phases'] or
                        'existing_component_checks'not in failure['phases']):
                        raise ValueError('T04_COMPLETED_CONSTRUCTION_FINALIZATION_BINDING_CHANGED')
                    import gzip
                    data=gzip.decompress((prior/'construction.json.gz').read_bytes());saved=json.loads(data)
                    if saved['input_binding']!=inputs or not saved['full_board_run']:raise ValueError('T04_FINALIZATION_FULL_BOARD_REQUIRED')
                    board.checked(saved)
                    return saved,dict(job=str(prior),job_sha256=board.file_sha(prior/'JOB.json'),
                        failure_sha256=board.file_sha(prior/'FAILURE.json'),construction_sha256=board.file_sha(prior/'construction.json.gz'),
                        stage_sha256=p.digest(data),source_files_identical=True,
                        construction_wall_s=failure['phases']['full_board_t04'],prior_attempt_wall_s=failure['wall_s'],
                        operation='FINALIZE_COMPLETED_FULL_BOARD_CONSTRUCTION; NO_TREATMENT_REEXECUTION')
                stage,retained_execution=phase('retained_construction_authentication',authenticate_completed_construction)
            if distance.measurement_engine() is not engine or engine.owner is not None:
                raise ValueError('T04_DISTANCE_ENGINE_CHANGED_BY_INPUT_HANDOFF')
            checks=phase('existing_component_checks',lambda:board.checked(stage))
            assembly=phase('diagnostic_assembly',lambda:b.assemble(store,entry,stage))
            final=store.get_json(assembly['scene_ref'],kind='scene')
            _, after, _=p.operands(store,final)
            def preservation():
                b.require_source(store,binding,final)
                terminals=[s for s,r in rows.items()if r['kind']=='circle' or p.t02_land(r)]
                eligibility=stage['trace_eligibility_policy']
                proof=verify_preserved_contributions(current,after,eligibility['fixed_source_ids'],terminals,
                    {s for ss in stage['growth_source_ids_by_route'].values()for s in ss})
                proof['protected_large_fill_occurrences_byte_preserved']=len(eligibility['protected_large_fill_source_ids'])
                return proof
            proof=phase('cleanup_and_terminal_preservation',preservation)
            # Serialize a complete map relative to RAW original, including
            # unchanged cleanup contributions not emitted by the T04 caller.
            h=stage['hybrid_components']; h['continuous_source_bodies']={
                s:dict(wkb_hex=to_wkb(g).hex(),display_treatment='Full-board T04 after large-copper trimming')
                for s,g in after.items()if to_wkb(g)!=to_wkb(source[s])}
            h['changed_bulk_copper']={}
            stage['trimmed_predecessor']=custody; stage['cleanup_preservation']=proof
            artifact=phase('construction_write',lambda:board.write_stage(output/'construction.json.gz',stage))
            phase('artifact_revalidation',store.verify_reads)
            if copper is not None:copper.validate()
            result=dict(status='FULL_BOARD_T04_AFTER_CLEANUP_DIAGNOSTIC_COMPLETE' if full_board else 'BOUNDED_T04_PARITY_ARM_COMPLETE',scope=scope,control=control,
                inputs=inputs,stage=artifact,assembly=assembly,checks=checks,cleanup_preservation=proof,
                summary=stage['summary'],requested_admitted_routes=len(stage['requested_routes']),
                accounted_native_routes=len(stage.get('native_route_dispositions',[])),
                settings=settings.resolved(),asset_manifest=assets,hole_policy=holes,
                phases=phases,wall_s=time.perf_counter()-started,shared_copper=None if copper is None else copper.diagnostics(),
                distance_lifetime=dict(baseline_engine_preserved=True,shared_engine_override=False,
                    native_handle_bytes=engine.weight,limit_bytes=distance.LIMIT),
                retained_execution=retained_execution,
                full_board_run=full_board,complete_t04=False,publication_ready=False,replay=retained_execution is not None,export=False)
            p.save(output/'RESULT.json',result)
            print(json.dumps({k:result[k]for k in ('status','summary','checks','cleanup_preservation','wall_s')}),flush=True)
    except BaseException as exc:
        try:operands=board.failure_operands(exc,output)
        except BaseException as capture_error:
            operands=dict(status='CAPTURE_FAILED_PRIMARY_ERROR_PRESERVED',error=repr(capture_error))
        if stage is not None and not (output/'construction.json.gz').exists():
            try:board.write_stage(output/'construction.json.gz',stage)
            except BaseException as archive_error:
                operands=dict(primary_capture=operands,construction_archive_error=repr(archive_error))
        p.save(output/'FAILURE.json',dict(status='FAILED_ATTEMPT_RETAINED',phase=active,error=repr(exc),
            traceback=traceback.format_exc(),failure_operands=operands,phases=phases,
            wall_s=time.perf_counter()-started,remaining_operations='NOT_RUN'))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-job',type=Path,required=True)
    parser.add_argument('--cleanup-result',type=Path)
    parser.add_argument('--control',choices=('trimmed','baseline','identity'),default='trimmed')
    parser.add_argument('--scope',type=Path,help='Engineering parity cohort; omit for the full board')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preparation-from',type=Path)
    parser.add_argument('--finalize-from',type=Path,help='Finalize only a same-code completed construction stopped by the obsolete zero-overlap guard')
    args=parser.parse_args()
    if args.control=='trimmed' and args.cleanup_result is None:parser.error('--cleanup-result is required for trimmed input')
    routes=None if args.scope is None else p.load(args.scope)['requested_routes']
    execute(args.source_job,args.cleanup_result,args.output,args.preparation_from,control=args.control,route_ids=routes,finalize_from=args.finalize_from)
