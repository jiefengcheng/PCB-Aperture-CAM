#!/usr/bin/env python3
"""Run one explicit bounded comparison arm; no default pipeline integration."""
import argparse
import gzip
import json
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.gerber_u05 import pipeline as p, profile_intake as intake, bounded_order as b
from src.gerber_u05 import group_stage, group_board_job as board
from src.t04_settings import read_snapshot, SNAPSHOT_NAME
from src import hole_acceptance, source_channel_scope as sc


def execute(source_job, scope_file, output, order):
    started=time.perf_counter(); phases={}; active='setup';stage=None
    p.configure(); output=Path(output)
    if not output.resolve().is_relative_to((p.ROOT/'out/lacie_work').resolve()):
        raise ValueError('ORDER_EXPERIMENT_REQUIRES_OWN_LACIE_NAMESPACE')
    output.mkdir(parents=True,exist_ok=False)
    def phase(name, function):
        nonlocal active
        active=name;tick=time.perf_counter();print(json.dumps(dict(event='start',phase=name,order=order)),flush=True)
        value=function();phases[name]=time.perf_counter()-tick
        print(json.dumps(dict(event='done',phase=name,wall_s=phases[name],order=order)),flush=True)
        return value
    try:
        from tools.preflight import verify_manifest
        assets=phase('asset_manifest',verify_manifest)
        source_job=Path(source_job);scope=p.load(scope_file)
        binding=p.load(source_job/'source.json');reader=intake.EvidenceStore(source_job)
        intake.prepare(output,source_job);p.save(output/'source.json',binding)
        hole_policy=hole_acceptance.bind(output)
        settings=read_snapshot(output/SNAPSHOT_NAME)
        store=b.ExperimentStore(output/'runtime',reader)
        original=phase('original_source_reads',lambda:reader.get_json(binding['scene_ref'],kind='scene'))
        phase('source_identity_validation',lambda:b.require_source(store,binding,original))
        phase('source_context_construction',lambda:p.initialize_t04(store,binding,original))
        sites,prepared=phase('canonical_original_allocation',lambda:b.allocate_original(store,binding,original))
        def validate_scope():
            rows,source,_=p.operands(store,original)
            actual=b.terminal_scope(rows,source,scope['native_paths'],sites,prepared[1])
            if any(actual[k]!=scope[k] for k in ('circle_sites','rectangles')):
                raise ValueError('ORDER_ORIGINAL_TERMINAL_SCOPE_CHANGED')
        phase('original_scope_validation',validate_scope)
        input_binding=dict(schema=b.SCHEMA,source_sha256=binding['source_ref']['sha256'],
            original_scene_ref=binding['scene_ref'],scene_ref=binding['scene_ref'],source_binding_sha256=p.digest(p.canonical(binding)),
            settings_sha256=settings.source_sha256,scope_sha256=board.file_sha(scope_file),
            accepted_t03=False,complete_t04=False)
        cache=p.ROOT/'out/lacie_work/order_cache'/output.name
        cache.mkdir(parents=True,exist_ok=False)
        def progress(event):
            with (output/'PROGRESS.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
            if event.get('event')!='hybrid_residual' or event.get('index',0)%150==0:
                print(json.dumps(dict(order=order,**event)),flush=True)
        rule=dict(scope='BOUNDED',source_preparation=str(cache/'source_roles'),
            group_cache=str(cache/'group_seed'),relationship_cache_root=str(cache/'relationships'),
            member_cache=str(cache/'members'),arc_member_cache=str(cache/'arcs'),coverage_cache=str(cache/'coverage'),
            input_binding=input_binding,bounded_order_source_binding=binding,
            hybrid_components=True,residual_end_matching=True,residual_chain_matching=True,
            residual_end_deviation=.1,progress=progress)
        phase('shared_source_preparation_construction',lambda:b.prepare_original(
            rule['source_preparation'],store,original,binding,sc.ACTIVE.index))
        current=original
        wanted=set(scope['circle_sites'])
        terminals=sorted(set(scope['rectangles'])|{a for site in sites if site['source_id'] in wanted for a in site['aliases']})
        if order=='current':
            t01=phase('t01',lambda:b.circles(store,current,binding,sites,prepared,scope['circle_sites']))
            p.save(output/'t01.json',t01);current=store.get_json(t01['output_scene_ref'],kind='scene')
            t03=phase('t03_original_trace_and_port_check',lambda:p.run_t03(store,current,binding,t01))
            p.save(output/'t03_check_only.json',t03)
        # Bind the actual stage entry, never the retained job's T03 acceptance.
        input_binding=dict(input_binding,scene_ref=store.put_json('scene',current),
                           predecessor_scene_sha256=p.digest(p.canonical(current)))
        rule['input_binding']=input_binding
        stage=phase('t04',lambda:group_stage.run(store,current,route_ids=scope['requested_routes'],settings=settings,rule=rule))
        artifact=phase('t04_report_write',lambda:board.write_stage(output/'construction.json.gz',stage))
        handoff=phase('assembled_scene_handoff',lambda:b.assemble(store,current,stage))
        p.save(output/'ASSEMBLY.json',handoff)
        current=store.get_json(handoff['scene_ref'],kind='scene');trace_scene=current
        if order=='trace_first':
            t01=phase('t01',lambda:b.circles(store,current,binding,sites,prepared,scope['circle_sites']))
            p.save(output/'t01.json',t01);current=store.get_json(t01['output_scene_ref'],kind='scene')
        t02=phase('t02',lambda:b.rectangles(store,current,binding,scope['rectangles']))
        p.save(output/'t02.json',t02);current=store.get_json(t02['output_scene_ref'],kind='scene')
        proof=phase('trace_floor_connection_reconciliation',lambda:b.reconcile(
            store,binding,original,trace_scene,current,stage,terminals))
        p.save(output/'RECONCILIATION.json',proof)
        if not proof['passed']:raise ValueError('ORDER_RECONCILIATION_FAILED')
        phase('input_artifact_revalidation',store.verify_reads)
        p.save(output/'ARTIFACT_READS.json',dict(references=store.read_refs,all_bytes_revalidated=True))
        receipt=dict(schema=b.SCHEMA,status='BOUNDED_EXPERIMENT_COMPLETE',order=order,
            source_files=intake.source_inventory(),inputs=input_binding,asset_manifest=assets,
            scope=scope,stages=phases,stage_artifact=artifact,assembly=handoff,
            output_scene_ref=t02['output_scene_ref'],checks=dict(
                route_connections=len(proof['route_connections']),terminal_attachments=len(proof['terminal_attachments']),
                endpoints_unresolved=len(proof['inherited_endpoint_diagnostics']['failures']),
                corner_diagnostics=proof['inherited_corner_diagnostics']),
            hole_policy=hole_policy,publication_ready=False,complete_t04=False,
            full_board_run=False,replay=False,export=False,total_wall_before_final_report_s=time.perf_counter()-started)
        tick=time.perf_counter();p.save(output/'RECEIPT.json',receipt);write_wall=time.perf_counter()-tick
        p.save(output/'WALL.json',dict(total_including_receipt_write_s=time.perf_counter()-started,
            final_receipt_write_s=write_wall,phase_wall_s=phases,final_wall_receipt_write_excluded=True))
        print(json.dumps(dict(status=receipt['status'],order=order,wall_s=time.perf_counter()-started)),flush=True)
    except BaseException as error:
        if stage is not None and not (output/'construction.json.gz').exists():
            board.write_stage(output/'construction.json.gz',stage)
        p.save(output/'FAILURE.json',dict(status='FAILED_ATTEMPT_RETAINED',phase=active,error=repr(error),
            traceback=traceback.format_exc(),phase_wall_s=phases,total_wall_s=time.perf_counter()-started,
            remaining_operations='NOT_RUN',complete_t04=False,publication_ready=False))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-job',required=True)
    parser.add_argument('--scope',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--order',choices=('current','trace_first'),required=True)
    args=parser.parse_args();execute(args.source_job,args.scope,args.output,args.order)
