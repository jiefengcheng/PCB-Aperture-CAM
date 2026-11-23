"""Retain approved cuts over original source; qualify the held endpoint-cap cases.

No route growth, recess filling, positive-copper clearance search or export.
"""
import argparse,copy,gzip,json,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shapely import from_wkb,to_wkb
from shapely.geometry import box,LineString
from shapely.ops import unary_union
from src.viewer_abi.live import load_connection,artifact_reader,construction_map,read_bound,enqueue
from src.viewer_abi.publisher import encode,digest
from src.shared_copper_context import for_board
from src.bulk_edge_restore import fit_straight_flanks,topology
from src.gerber_u05.source_edge_cleanup import CleanupBatch
from src.gerber_u05.group_board_job import write_stage
from tools.preflight import verify_manifest


def qualify(args):
    output=args.output.resolve();workspace=Path('out/lacie_work').resolve()
    if not output.is_relative_to(workspace):raise ValueError('LACIE_OUTPUT_REQUIRED')
    output.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
    try:
        assets=verify_manifest();config=load_connection(args.connection);read=artifact_reader(config['legacy'])
        scene=json.loads(read(config['scene_ref']));rows={r['source_id']:r for r in scene['objects']}
        original={s:from_wkb(read(r['geometry_ref'])) for s,r in rows.items()}
        parent_raw=args.parent.read_bytes();parent=json.loads(gzip.decompress(parent_raw));mapping=construction_map(parent,config)
        old={s:from_wkb(bytes.fromhex(mapping[s])) if s in mapping else g for s,g in original.items()}
        inventory=json.loads(args.inventory.read_bytes())
        with for_board(original) as copper:
            before=copper.source.image();old_image=unary_union(list(old.values()))
            cuts=before.difference(old_image)
            # Import subtraction only. The parent's trace growth and the two
            # recess additions are deliberately absent from this construction.
            changed={s:original[s].difference(cuts) for s in copper.source.sources(cuts)
                     if original[s].intersection(cuts).area>1e-12}
            current=copper.acquire(changed)
            features=[];indices=[];deferred=parent['owner_detected_supported_edge_cleanup']['deferred']
            kept=[copy.deepcopy(r) for r in deferred if r.get('reason')=='AREA_RULE_NOT_ESTABLISHED']
            for record in deferred:
                if record.get('reason')=='AREA_RULE_NOT_ESTABLISHED':continue
                i=record['index'];c=inventory['candidates'][i];sid=record['causing_source_id']
                domain=box(*c['domain_bounds_mm']);coord=c['edge_coordinate_mm'];lo,hi=c['tangent_bounds_mm']
                edge=LineString([(coord,lo-.01),(coord,hi+.01)]) if c['axis']==0 else LineString([(lo-.01,coord),(hi+.01,coord)])
                _,evidence=fit_straight_flanks(*c['flanks'],c['backing_point_mm'],domain)
                evidence.update(source_sha256=config['source_sha256'],causing_ordinal=rows[sid]['metadata']['gerber_ordinal'])
                features.append(dict(causing_id=sid,domain=domain,smooth_edge=edge,reference_evidence=evidence,backing_point=c['backing_point_mm']))
                indices.append(i)
            print(json.dumps(dict(event='TRIM_ONLY_PREPARED',prior_removed_mm2=cuts.area,candidates=len(features))),flush=True)
            batch=CleanupBatch(rows,original,current,features,allow_redundant_flashes=True)
            accepted=[]
            for i,f in enumerate(features):
                try:
                    proof=batch.propose(i);accepted.append(dict(index=indices[i],bounds_mm=list(f['domain'].bounds),proof=proof))
                except ValueError as exc:
                    kept.append(dict(index=indices[i],bounds_mm=list(f['domain'].bounds),causing_source_id=f['causing_id'],reason=str(exc)))
            (output/'CANDIDATES.json').write_bytes(encode(dict(accepted=accepted,kept=kept)))
            after,proof=batch.finish();image=after.image()
            positive=image.difference(before)
            if positive.area>1e-12 or topology(image)!=topology(before):raise ValueError('TRIM_ONLY_SOURCE_MATERIAL_OR_TOPOLOGY_CHANGED')
            if not any(r['index']==7 for r in accepted):raise ValueError('OWNER_MARKED_BUMP_NOT_CORRECTED')
            untouched_rectangles=all(to_wkb(after.values[s])==to_wkb(g) for s,g in original.items() if rows[s]['kind']=='rectangle')
            if not untouched_rectangles:raise ValueError('ORIGINAL_RECTANGULAR_TERMINAL_CHANGED')
            bodies={s:dict(wkb_hex=to_wkb(g).hex(),display_treatment='Original source bulk copper trimmed; no widening or additions')
                    for s,g in after.values.items() if to_wkb(g)!=to_wkb(original[s])}
            stage=dict(schema='source-bulk-trim-preview/1',operation='TRIM_ONLY',input_binding=copy.deepcopy(parent['input_binding']),
                hybrid_components=dict(continuous_source_bodies=bodies,changed_bulk_copper={}),
                requested_routes=[],native_trace_source_ids_by_route={},trace_growth_execution=False,
                full_board_run=False,export=False,geometry_audit=False,
                status='BOUNDED_SOURCE_TRIM_ONLY_PREVIEW; NOT_FULL_BOARD_ACCEPTANCE',
                source_pad_cleanup=copy.deepcopy(parent.get('source_pad_cleanup',{})),
                owner_supported_physical_noise_corrections=copy.deepcopy(parent.get('owner_supported_physical_noise_corrections',{})),
                owner_marked_shallow_straight_edges=copy.deepcopy(parent.get('owner_marked_shallow_straight_edges',{})),
                owner_marked_circular_edge_corrections=copy.deepcopy(parent.get('owner_marked_circular_edge_corrections',{})),
                owner_marked_bulk_boundary_corrections=dict(records=[copy.deepcopy(r) for r in parent.get('owner_marked_bulk_boundary_corrections',{}).get('records',[]) if r.get('physical_added_mm2',0)<=1e-12]),
                owner_detected_supported_edge_cleanup=dict(accepted=copy.deepcopy(parent['owner_detected_supported_edge_cleanup']['accepted'])+accepted,deferred=kept),
                trim_only_phase=dict(passed=True,positive_copper_mm2=positive.area,clearance_searches=0,clearance_checks=0,
                    topology_before=list(topology(before)),topology_after=list(topology(image)),
                    original_rectangular_terminals_byte_preserved=untouched_rectangles,
                    imported_approved_cut_mm2=cuts.area,new_batch=proof,source_bytes_changed=False),
                source_preview_parent=dict(path=str(args.parent.resolve()),sha256=digest(parent_raw),role='AUTHORIZED_REMOVAL_MASK_AND_SAVED_RULE_METADATA_ONLY'))
            artifact=write_stage(output/'construction.json.gz',stage)
            marked=next(r for r in accepted if r['index']==7);sid=marked['proof']['causing_source_id']
            result=dict(status='BOUNDED_ORIGINAL_SOURCE_TRIM_ONLY_PASS',input_binding=stage['input_binding'],stage=artifact,
                source_preview_parent=stage['source_preview_parent'],asset_manifest=assets,
                accepted=accepted,kept=kept,proof=stage['trim_only_phase'],context=copper.diagnostics(),
                viewer_source_focus=dict(source_id=sid,route_point_index=0,radius_mm=.35),
                smoothing_additions=False,trace_growth=False,full_board_growth=False,export=False,
                scope='REPLAY OF PREVIOUSLY_AUTHORIZED CUTS PLUS BOUNDED_HELD_CAP_CORRECTIONS',wall_s=time.perf_counter()-start)
            (output/'RESULT.json').write_bytes(encode(result))
            print(json.dumps(dict(status=result['status'],accepted_indices=[r['index'] for r in accepted],
                unresolved=len(kept),added_mm2=positive.area,new_removed_mm2=proof['actual_removed_mm2'],wall_s=result['wall_s'])),flush=True)
        if args.show:
            event=enqueue(args.connection,label='ORIGINAL SOURCE · trimming only · no additions · grey Preview',report=output/'RESULT.json',construction=output/'construction.json.gz')
            (output/'VIEWER_EVENT.json').write_bytes(encode(event))
    except BaseException as exc:
        (output/'FAILED.json').write_bytes(encode(dict(error=repr(exc),traceback=traceback.format_exc())))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--parent',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--connection',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--show',action='store_true')
    qualify(p.parse_args())
