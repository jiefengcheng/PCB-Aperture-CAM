#!/usr/bin/env python3
"""Source-bound KEEP correction of a saved T04 diagnostic; never runs growth."""
import argparse,gzip,json,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shapely import from_wkb,to_wkb,STRtree
from shapely.ops import unary_union
from src import trace_growth_policy as policy
from src.original_copper_owners import OriginalOwners
from src.viewer_abi.live import load_connection,artifact_reader,read_bound,construction_map
from src.viewer_abi.publisher import read_current,digest,encode
from src.gerber_u05.group_board_job import write_stage
from src.gerber_u05.limiting_math import GUARD,MARGIN
from src.gerber_u05.keep_retraction import preserved_copper_conflict
from src.indexed_polygon_distance import Engine
from tools.pcb_workspace import prepare,WORK


def bound_ancestor(root,manifest,state,wanted):
    """Only a hash-bound committed ancestor may supply optional growth to recover."""
    if wanted is None:return manifest['sha256'],state
    if len(wanted)!=64 or any(c not in'0123456789abcdef'for c in wanted):raise ValueError('INVALID_BASE_PAYLOAD')
    sha=manifest['sha256'];visited=set()
    for _ in range(4096):
        if sha in visited:raise ValueError('BASE_LINEAGE_CYCLE')
        visited.add(sha)
        snapshot=json.loads(read_bound(root/'session/snapshots'/(sha+'.json'),sha))
        if snapshot['revision']!=state['revision']:raise ValueError('BASE_STATE_REVISION_MISMATCH')
        if sha==wanted:return sha,state
        parent=state.get('parent_sha256');proof=state.get('parent_state_sha256')
        if not parent or not proof:raise ValueError('BASE_IS_NOT_COMMITTED_ANCESTOR')
        state=json.loads(read_bound(root/'receipts'/(parent+'.state.json'),proof));sha=parent
    raise ValueError('BASE_LINEAGE_RESOURCE_LIMIT')


def execute(root,output,keep_routes,base_payload=None):
    started=time.perf_counter();output.mkdir(exist_ok=False)
    def log(event,**fields):
        value=dict(event=event,elapsed_s=time.perf_counter()-started,**fields)
        with(output/'PROGRESS.jsonl').open('a')as f:f.write(json.dumps(value)+'\n')
        print(json.dumps(value),flush=True)
    try:
        config=load_connection(root);read=artifact_reader(config['legacy'])
        manifest,snapshot=read_current(root/'session')
        state=json.loads(read_bound(root/'receipts'/(manifest['sha256']+'.state.json'),manifest['producerStateSHA256']))
        displayed_state=state
        base_payload,state=bound_ancestor(root,manifest,state,base_payload)
        events=[json.loads(p.read_bytes())for p in(root/'queue').glob('*.ready.json')]
        events=[e for e in events if e['event_id']==state['event']]
        if len(events)!=1 or events[0]['kind']!='construction':raise ValueError('COMMITTED_CONSTRUCTION_REQUIRED')
        event=events[0]
        if event['connection_id']!=config['connection_id']or digest(encode(dict(connection=config['connection_id'],report=event['report'],geometry=event['geometry'],status=event['display_status'])))!=state['event']:
            raise ValueError('COMMITTED_EVENT_CHANGED')
        read_bound(event['report']['path'],event['report']['sha256'])
        stage=json.loads(gzip.decompress(read_bound(event['geometry']['path'],event['geometry']['sha256'])))
        mapping=construction_map(stage,config);scene=json.loads(read(config['scene_ref']))
        rows={r['source_id']:r for r in scene['objects']};before_bytes={s:read(r['geometry_ref'])for s,r in rows.items()}
        old_bytes={s:bytes.fromhex(mapping[s])if s in mapping else body for s,body in before_bytes.items()}
        if {s:digest(v)for s,v in old_bytes.items()}!=state['fingerprints']:raise ValueError('DISPLAYED_COPPER_FINGERPRINT_CHANGED')
        before={s:from_wkb(v)for s,v in before_bytes.items()};old={s:from_wkb(v)for s,v in old_bytes.items()}
        paths=stage['native_trace_source_ids_by_route'];p=policy.capture()
        (output/'POLICY.json').write_bytes(encode(p.snapshot()))
        log('authenticated',source_occurrences=len(rows),native_routes=len(paths))
        ledger,index=policy.classify(rows,before,paths,p)
        log('policy_classified',large_components=len(ledger['large_filled_components']),kept_routes=len(ledger['kept_routes']))
        if not set(keep_routes)<=set(paths):raise ValueError('OWNER_KEEP_ROUTE_NOT_IN_NATIVE_INVENTORY')
        kept=dict(ledger['kept_routes']);fixed=set(ledger['fixed_source_ids'])
        for route in keep_routes:
            kept.setdefault(route,[]).append('OWNER_REQUESTED_ORIGINAL_WIDTH')
            fixed.update(paths[route])
        after=dict(old);after_bytes=dict(old_bytes)
        def restore():
            for s in fixed:after[s]=before[s];after_bytes[s]=before_bytes[s]
        restore();conflicts=[];distance_engine=Engine()
        # Retain only existing growth that respects restored fixed copper.
        # No clipping, new routing, geometry buffers as output, or growth search.
        for iteration in range(len(paths)+1):
            by_owner={}
            for s in fixed:
                for own in ledger['source_owner_ids'][s]:by_owner.setdefault(own,[]).append(before[s])
            owner_ids=sorted(by_owner);obstacles=[unary_union(by_owner[o])for o in owner_ids];tree=STRtree(obstacles)
            changed=False
            for route,ss in sorted(paths.items()):
                if route in kept:continue
                delta=unary_union([after[s].difference(before[s])for s in ss])
                if delta.is_empty:continue
                own={o for s in ss for o in ledger['source_owner_ids'][s]}
                for i in sorted(map(int,tree.query(delta.envelope.buffer(GUARD+2*MARGIN)))):
                    if owner_ids[i]in own:continue
                    gap=distance_engine.measure(delta,obstacles[i])
                    # Preserve the original native metric at this exact decision boundary.
                    if abs(gap-GUARD)<=4e-12:gap=delta.distance(obstacles[i])
                    if preserved_copper_conflict(gap):
                        kept[route]=['KEEP_TO_RESPECT_PRESERVED_COPPER'];fixed.update(ss);changed=True
                        conflicts.append(dict(route_id=route,fixed_owner=owner_ids[i],gap_mm=gap,iteration=iteration))
                        break
            if not changed:break
            restore();log('dependent_growth_kept',iteration=iteration,kept_routes=len(kept))
        else:raise ValueError('KEEP_DEPENDENCY_CLOSURE_DID_NOT_TERMINATE')
        distance_engine.close();restore()
        native=[]
        for number,(route,ss)in enumerate(sorted(paths.items())):
            entry_count=len(OriginalOwners(unary_union([before[s]for s in ss])).owners)
            final_count=len(OriginalOwners(unary_union([after[s]for s in ss])).owners)
            native.append(dict(route_id=route,entry_components=entry_count,current_components=final_count,passed=final_count<=entry_count))
            if number%300==0:log('native_connections',checked=number+1)
        if not all(r['passed']for r in native):raise ValueError('CORRECTED_NATIVE_CONNECTION_FAILURE')
        if any(after_bytes[s]!=before_bytes[s]for s in fixed):raise ValueError('PROTECTED_ENTRY_CONTOUR_CHANGED')
        if any(after_bytes[s]!=old_bytes[s]for s in rows if s not in fixed):raise ValueError('UNSELECTED_OPERAND_CHANGED')
        terminals=[s for s,r in rows.items()if r['kind']in('circle','rectangle')]
        if any(after_bytes[s]!=old_bytes[s]for s in terminals):raise ValueError('TERMINAL_CONTEXT_CHANGED')
        protected=set(ledger['protected_large_fill_source_ids'])
        restored_bulk=set(stage['hybrid_components']['changed_bulk_copper']).intersection(protected)
        changed={s for s in rows if after_bytes[s]!=old_bytes[s]}
        corrections=[]
        for s in sorted(changed):
            corrections.append(dict(source_id=s,ordinal=rows[s]['metadata'].get('gerber_ordinal'),
                before_sha256=digest(old_bytes[s]),after_sha256=digest(after_bytes[s]),
                removed_t04_area_mm2=old[s].difference(after[s]).area,
                restored_entry_area_mm2=after[s].difference(old[s]).area,
                exact_entry_bytes=True,protected_large_fill=s in protected))
        ledger.update(effective_kept_routes=kept,effective_fixed_source_ids=sorted(fixed),dependent_rejections=conflicts)
        (output/'ELIGIBILITY.json').write_bytes(encode(ledger));(output/'CORRECTIONS.json').write_bytes(encode(corrections))
        (output/'NATIVE_CONNECTIONS.json').write_bytes(encode(native))
        bodies={s:dict(wkb_hex=after_bytes[s].hex(),display_treatment='Kept at exact T04-entry geometry'if s in fixed else'Retained saved T04 diagnostic geometry')for s in stage['hybrid_components']['continuous_source_bodies']}
        bulk={s:dict(wkb_hex=after_bytes[s].hex())for s in stage['hybrid_components']['changed_bulk_copper']}
        candidate=dict(schema='t04-source-bound-keep-correction/1',status='KEEP_POLICY_CORRECTED_PREVIEW; NOT_COMPLETE_T04',
            input_binding=stage['input_binding'],full_board_run=False,complete_t04=False,publication_ready=False,
            native_trace_source_ids_by_route=paths,trace_eligibility_policy=ledger,
            hybrid_components=dict(continuous_source_bodies=bodies,changed_bulk_copper=bulk),
            provenance=dict(base_construction=event['geometry'],base_report=event['report'],base_viewer_payload_sha256=base_payload,
                            displayed_predecessor_sha256=manifest['sha256'],
                            new_growth_execution=False,corrected_source_count=len(changed),policy_sha256=p.sha256))
        artifact=write_stage(output/'construction.json.gz',candidate)
        result=dict(status=candidate['status'],input_binding=stage['input_binding'],stage=artifact,
            correction_tool_sha256=digest(Path(__file__).read_bytes()),indexed_distance_library_sha256=distance_engine.library_sha256,
            base_construction=event['geometry'],base_viewer_payload_sha256=base_payload,displayed_predecessor_sha256=manifest['sha256'],policy=p.snapshot(),
            scope='FULL_SAVED_BOARD_CONTEXT; SOURCE_BOUND_KEEP_CORRECTION_ONLY',full_board_run=False,
            complete_t04=False,publication_ready=False,export=False,new_growth_execution=False,
            checks=dict(native_connections_checked=len(native),native_connections_passed=True,
                complete_large_fill_source_contours_kept=len(protected),restored_bulk_sources=len(restored_bulk),
                terminal_occurrences_unchanged=len(terminals),unselected_source_bytes_preserved=True,
                no_synthesized_growth=True,minimum_clearance_to_preserved_foreign_copper_mm=GUARD,
                construction_broad_phase_reserve_mm=GUARD+2*MARGIN,
                changed_source_occurrences_vs_displayed=sum(digest(after_bytes[s])!=displayed_state['fingerprints'][s]for s in rows)),
            counts=dict(large_filled_components=len(ledger['large_filled_components']),native_routes=len(paths),
                kept_native_routes=len(kept),width_excluded_routes=sum('SOURCE_WIDTH_EXCEEDS_GLOBAL_LIMIT'in why for why in ledger['kept_routes'].values()),
                attached_fill_routes=sum('CONNECTED_TO_LARGE_FILLED_COPPER'in why for why in ledger['kept_routes'].values()),
                dependent_keep_routes=len(conflicts),changed_source_occurrences=len(changed)),
            wall_s=time.perf_counter()-started,limitations=['The base full-board construction remains diagnostic.',
                'This retracts old growth and restores protected T04-entry copper; it is not a fresh full-board optimization.',
                'The 0.25 mm width cutoff was selected by the owner. Large-fill broad-core detection remains provisional.',
                'Original source irregularities are preserved; no arbitrary contour smoothing or electrical/manufacturing acceptance.'])
        if read_current(root/'session')[0]!=manifest:raise ValueError('VIEWER_REVISION_CHANGED_DURING_CORRECTION')
        (output/'RESULT.json').write_bytes(encode(result));log('correction_ready',**result['counts'])
        return result
    except BaseException as error:
        (output/'FAILED.json').write_bytes(encode(dict(status='FAILED_ATTEMPT_RETAINED',error=repr(error),traceback=traceback.format_exc())))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--connection',required=True);parser.add_argument('--output',required=True);parser.add_argument('--keep-route',action='append',default=[]);parser.add_argument('--base-payload-sha256')
    args=parser.parse_args();prepare();root=Path(args.connection).resolve();output=Path(args.output).resolve()
    if not root.is_relative_to(WORK.resolve())or not output.is_relative_to(WORK.resolve()):raise ValueError('LACIE_WORKSPACE_REQUIRED')
    execute(root,output,args.keep_route,args.base_payload_sha256)
