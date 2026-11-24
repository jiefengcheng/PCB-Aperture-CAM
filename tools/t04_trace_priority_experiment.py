#!/usr/bin/env python3
"""T04-only bounded comparison on original versus retained T03 context.

No T01, T02, T03 or T05 construction is called. Retained-T03 custody is read
and verified solely for the current-context reference arm.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.gerber_u05 import pipeline as p, profile_intake as intake, bounded_order as b
from src.gerber_u05 import group_stage, group_board_job as board
from src import hole_acceptance, source_channel_scope as sc
from src.t04_settings import read_snapshot,SNAPSHOT_NAME
from src.gerber_u05.profile_schedule import SCHEDULE


def original_source_only(source_job):
    """Source/policies without reading, inheriting or accepting any T03 proof."""
    run=Path(source_job);reader=intake.EvidenceStore(run);binding=p.load(run/'source.json')
    scene=reader.get_json(binding['scene_ref'],kind='scene')
    reader.get(binding['source_ref'],kind='gerber-source')
    if scene['source_sha256']!=binding['source_ref']['sha256']:raise ValueError('T04_ONLY_SOURCE_CHANGED')
    settings=read_snapshot(run/SNAPSHOT_NAME);schedule=p.load(run/'T04_PASS_SCHEDULE.json')
    if schedule['schema']!='pcb-t04-pass-schedule/1'or tuple(schedule['pass_increments'])!=SCHEDULE:
        raise ValueError('T04_ONLY_SCHEDULE_CHANGED')
    return reader,binding,scene,settings,None


def execute(source_job,scope_file,output,context,trim_pad_ordinals=()):
    started=time.perf_counter();phases={};active='setup';stage=None
    p.configure();output=Path(output)
    if not output.resolve().is_relative_to((p.ROOT/'out/lacie_work').resolve()):
        raise ValueError('T04_ONLY_LACIE_OUTPUT_REQUIRED')
    output.mkdir(parents=True,exist_ok=False)
    def phase(name,function):
        nonlocal active
        active=name;tick=time.perf_counter();print(json.dumps(dict(event='start',phase=name,context=context)),flush=True)
        value=function();phases[name]=time.perf_counter()-tick
        print(json.dumps(dict(event='done',phase=name,wall_s=phases[name],context=context)),flush=True)
        return value
    try:
        from tools.preflight import verify_manifest
        assets=phase('asset_manifest',verify_manifest)
        read=intake.read if context=='retained_t03'else original_source_only
        reader,binding,retained,settings,custody=phase('input_custody',lambda:read(source_job))
        original=reader.get_json(binding['scene_ref'],kind='scene')
        scene=original if context=='original' else retained
        scope=p.load(scope_file);intake.prepare(output,source_job);p.save(output/'source.json',binding)
        from src.trace_growth_policy import capture_job, SNAPSHOT as ELIGIBILITY_SNAPSHOT
        capture_job(output)
        policy_hashes={n:board.file_sha(output/n)for n in intake.POLICIES if(output/n).exists()}
        policy_hashes[ELIGIBILITY_SNAPSHOT]=board.file_sha(output/ELIGIBILITY_SNAPSHOT)
        holes=hole_acceptance.bind(output);store=b.ExperimentStore(output/'runtime',reader)
        phase('source_identity_validation',lambda:b.require_source(store,binding,scene))
        phase('source_context_construction',lambda:p.initialize_t04(store,binding,scene))
        cache=p.ROOT/'out/lacie_work/trace_priority_cache'/output.name
        cache.mkdir(parents=True,exist_ok=False)
        inputs=dict(schema=b.SCHEMA,scope='T04_ONLY',source_sha256=binding['source_ref']['sha256'],
            original_scene_ref=binding['scene_ref'],scene_ref=store.put_json('scene',scene),
            predecessor_scene_sha256=p.digest(p.canonical(scene)),scope_sha256=board.file_sha(scope_file),
            settings_sha256=settings.source_sha256,context=context,
            source_binding_file_sha256=board.file_sha(Path(source_job)/'source.json'),policy_file_sha256=policy_hashes,
            retained_t03_custody=custody if context=='retained_t03' else None,
            accepted_t03=context=='retained_t03',new_predecessor_acceptance=False)
        def progress(event):
            with(output/'PROGRESS.jsonl').open('a')as f:f.write(json.dumps(event)+'\n')
            if event.get('event')!='hybrid_residual'or event.get('index',0)%150==0:
                print(json.dumps(dict(context=context,**event)),flush=True)
        rule=dict(scope='BOUNDED',source_preparation=str(cache/'source_roles'),group_cache=str(cache/'seed'),
            relationship_cache_root=str(cache/'relationships'),member_cache=str(cache/'members'),
            arc_member_cache=str(cache/'arcs'),coverage_cache=str(cache/'coverage'),input_binding=inputs,
            bounded_order_source_binding=binding,hybrid_components=True,residual_end_matching=True,
            residual_chain_matching=True,residual_end_deviation=.1,progress=progress)
        phase('shared_original_preparation',lambda:b.prepare_original(rule['source_preparation'],store,original,binding,sc.ACTIVE.index))
        stage=phase('t04',lambda:group_stage.run(store,scene,route_ids=scope['requested_routes'],settings=settings,rule=rule))
        cleanup=None;cleanup_ids=[]
        if trim_pad_ordinals:
            if context!='original':raise ValueError('PAD_CLEANUP_REQUIRES_ORIGINAL_SOURCE_CONTEXT')
            rows,current,source=p.operands(store,scene)
            requested=set(trim_pad_ordinals)
            cleanup_ids=sorted(s for s,r in rows.items()if r['kind']=='circle'and r['metadata'].get('gerber_ordinal')in requested)
            if {rows[s]['metadata']['gerber_ordinal']for s in cleanup_ids}!=requested:
                raise ValueError('PAD_CLEANUP_SOURCE_ORDINAL_NOT_FOUND')
            from src.gerber_u05.source_pad_cleanup import apply_to_construction
            cleanup=phase('source_pad_protrusion_cleanup',lambda:apply_to_construction(rows,current,source,stage,cleanup_ids))
            p.save(output/'PAD_CLEANUP.json',cleanup)
        artifact=phase('t04_report_write',lambda:board.write_stage(output/'construction.json.gz',stage))
        checks=phase('existing_t04_diagnostic_checks',lambda:board.checked(stage))
        assembly=phase('t04_diagnostic_assembly',lambda:b.assemble(store,scene,stage))
        final=store.get_json(assembly['scene_ref'],kind='scene')
        def terminal_floor():
            b.require_source(store,binding,final)
            rows,before,_=p.operands(store,scene);_,after,_=p.operands(store,final)
            ids=[s for s,r in rows.items()if r['kind']=='circle'or p.t02_land(r)]
            changed=[s for s in ids if p.to_wkb(before[s])!=p.to_wkb(after[s])]
            authorized=set(cleanup_ids)
            unexpected=[s for s in changed if s not in authorized]
            if unexpected:raise ValueError('T04_ONLY_TERMINAL_CONTEXT_CHANGED:'+str(unexpected[:5]))
            if cleanup is not None:
                expected={r['source_id']:r['after_sha256']for r in cleanup['records']}
                if any(p.digest(p.to_wkb(after[s]))!=expected[s]for s in authorized):
                    raise ValueError('PAD_CLEANUP_ASSEMBLY_CHANGED')
            return dict(passed=True,terminal_occurrences_byte_preserved=len(ids)-len(changed),terminal_growth_executed=False,
                        owner_authorized_source_pad_trims=cleanup_ids,changed_terminal_occurrences=len(changed))
        terminal_check=phase('terminal_context_preservation',terminal_floor)
        phase('all_artifact_bytes_revalidated',store.verify_reads)
        if policy_hashes!={n:board.file_sha(output/n)for n in policy_hashes}:raise ValueError('T04_ONLY_POLICY_BYTES_CHANGED')
        p.save(output/'ARTIFACT_READS.json',dict(references=store.read_refs,all_bytes_revalidated=True))
        receipt=dict(schema='t04-only-trace-priority-experiment/1',status='T04_BOUNDED_DIAGNOSTIC_COMPLETE',
            inputs=inputs,source_files=intake.source_inventory(),asset_manifest=assets,
            stage_artifact=artifact,assembly=assembly,checks=checks,terminal_context_check=terminal_check,
            source_pad_cleanup=cleanup,
            phases=phases,hole_policy=holes,requested_entries=len(scope['requested_routes']),
            applicable_native_routes=len(stage['native_trace_source_ids_by_route']),
            later_stage_construction='NOT_RUN; USER_REQUESTED_T04_ONLY',
            complete_t04=False,publication_ready=False,full_board_run=False,replay=False,export=False)
        tick=time.perf_counter();p.save(output/'RECEIPT.json',receipt);write_wall=time.perf_counter()-tick
        p.save(output/'WALL.json',dict(total_including_receipt_write_s=time.perf_counter()-started,
            final_receipt_write_s=write_wall,phase_wall_s=phases,final_wall_receipt_write_excluded=True))
        print(json.dumps(dict(status=receipt['status'],context=context,total_wall_s=time.perf_counter()-started)),flush=True)
    except BaseException as error:
        if stage is not None and not(output/'construction.json.gz').exists():board.write_stage(output/'construction.json.gz',stage)
        p.save(output/'FAILURE.json',dict(status='FAILED_ATTEMPT_RETAINED',phase=active,error=repr(error),
            traceback=traceback.format_exc(),completed_phase_wall_s=phases,total_wall_s=time.perf_counter()-started,
            remaining_operations='NOT_RUN',complete_t04=False,publication_ready=False))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-job',required=True)
    parser.add_argument('--scope',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--context',choices=('original','retained_t03'),required=True)
    parser.add_argument('--trim-pad-ordinal',type=int,action='append',default=[])
    args=parser.parse_args();execute(args.source_job,args.scope,args.output,args.context,args.trim_pad_ordinal)
