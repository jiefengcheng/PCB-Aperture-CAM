"""Qualify the eight retained cleanup places over the saved original-source revision."""
import argparse,copy,gzip,json,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shapely import from_wkb,to_wkb
from shapely.geometry import box,LineString
from src.viewer_abi.live import load_connection,artifact_reader,construction_map,read_bound,enqueue
from src.viewer_abi.publisher import encode,digest
from src.shared_copper_context import for_board
from src.bulk_edge_restore import fit_straight_flanks,topology
from src.gerber_u05.source_edge_cleanup import CleanupBatch
from src.gerber_u05.group_board_job import write_stage
from tools.preflight import verify_manifest


def run(args):
    out=args.output.resolve()
    if not out.is_relative_to(Path('out/lacie_work').resolve()):raise ValueError('LACIE_OUTPUT_REQUIRED')
    out.mkdir(exist_ok=False,parents=True);started=time.perf_counter()
    try:
        assets=verify_manifest();cfg=load_connection(args.connection);read=artifact_reader(cfg['legacy'])
        scene=json.loads(read(cfg['scene_ref']));rows={r['source_id']:r for r in scene['objects']}
        original={s:from_wkb(read(r['geometry_ref'])) for s,r in rows.items()}
        parent_result=json.loads(args.parent_result.read_bytes());parent_ref=parent_result['stage']
        parent_raw=read_bound(parent_ref['path'],parent_ref['sha256']);stage=json.loads(gzip.decompress(parent_raw))
        if stage.get('operation')!='TRIM_ONLY':raise ValueError('TRIM_ONLY_PARENT_REQUIRED')
        inventory=json.loads(args.inventory.read_bytes());mapping=construction_map(stage,cfg)
        byordinal={r['metadata']['gerber_ordinal']:s for s,r in rows.items()}
        order=[4,5,6,20,21,22,13,18]
        # Each denominator belongs to the source actually forming this bump.
        # The adjacent rectangle is not a valid denominator for cases 5/6.
        causes={4:14249,5:4100,6:4105,20:14455,21:14467,22:15598,13:1226,18:17569}
        if {r['index'] for r in stage['owner_detected_supported_edge_cleanup']['deferred']}!=set(order):
            raise ValueError('EXPECTED_EIGHT_RETAINED_PLACES_CHANGED')
        with for_board(original) as copper:
            current=copper.acquire({s:from_wkb(bytes.fromhex(w)) for s,w in mapping.items()})
            before=current.image();features=[];review=[]
            for number,index in enumerate(order,1):
                c=inventory['candidates'][index];sid=byordinal[causes[index]];domain=box(*c['domain_bounds_mm'])
                _,body=current.owner(sid);cut=body.intersection(domain)
                _,evidence=fit_straight_flanks(*c['flanks'],c['backing_point_mm'],domain)
                coord=c['edge_coordinate_mm'];lo,hi=c['tangent_bounds_mm']
                edge=LineString([(coord,lo-.01),(coord,hi+.01)]) if c['axis']==0 else LineString([(lo-.01,coord),(hi+.01,coord)])
                features.append(dict(causing_id=sid,domain=domain,smooth_edge=edge,reference_evidence=evidence,backing_point=c['backing_point_mm']))
                axis=c['axis'];depth=(coord-cut.bounds[axis]) if c['inside_sign']>0 else (cut.bounds[axis+2]-coord)
                review.append(dict(review_number=number,index=index,bounds_mm=list(domain.bounds),causing_source_id=sid,
                    ordinal=causes[index],original_feature_area_mm2=original[sid].area,
                    whole_physical_protrusion_area_mm2=cut.area,area_fraction=cut.area/original[sid].area,
                    depth_mm=depth,reference_evidence=evidence,original_reason=next(r['reason']for r in stage['owner_detected_supported_edge_cleanup']['deferred']if r['index']==index)))
            protected={s for s,r in rows.items() if any(r['metadata'].get(k) for k in
                ('rectangle_terminal','declared_terminal','declared_pin','protected_pin','terminal_intent_declared'))}
            batch=CleanupBatch(rows,original,current,features,allow_redundant_flashes=True,
                               allow_causing_pads=True,protected_source_ids=protected)
            accepted=[];deferred=[]
            for i,r in enumerate(review):
                if rows[r['causing_source_id']]['kind']=='rectangle':
                    r.update(status='ignored',reason='RECTANGULAR_BUMPS_DEFERRED_BY_OWNER')
                    continue
                try:
                    proof=batch.propose(i);accepted.append(dict(index=r['index'],bounds_mm=r['bounds_mm'],proof=proof));r.update(status='corrected',proof=proof)
                except ValueError as exc:
                    r.update(status='unresolved',reason=str(exc));deferred.append(dict(index=r['index'],bounds_mm=r['bounds_mm'],causing_source_id=r['causing_source_id'],reason=str(exc)))
            (out/'CANDIDATES.json').write_bytes(encode(review))
            after,proof=batch.finish();image=after.image();source_image=copper.source.image()
            if topology(image)!=topology(source_image) or image.difference(source_image).area>1e-12:
                raise ValueError('ORIGINAL_SOURCE_TOPOLOGY_OR_ADDITION_CHANGED')
            if to_wkb(after.values[byordinal[15344]])!=to_wkb(original[byordinal[15344]]):
                raise ValueError('NOMINAL_0250_TRACE_CHANGED')
            approved_pad_ids={r['causing_source_id'] for r in review if r['status']=='corrected' and rows[r['causing_source_id']]['kind'] in ('circle','rectangle')}
            if any(to_wkb(after.values[s])!=to_wkb(current.values[s]) for s,r in rows.items() if r['kind']=='rectangle' and s not in approved_pad_ids):
                raise ValueError('UNSELECTED_RECTANGULAR_PAD_CHANGED')
            for r in review:
                pct=100*r['area_fraction'];n=r['review_number']
                if r['status']=='ignored':
                    r['explanation']=f'Place {n}/8: rectangular bumps are deferred at the owner\'s request. Original rectangle {r["ordinal"]} and its overlapping source contributions remain exactly as in the verified trim-only parent; no rectangular trim is applied.'
                elif r['status']=='corrected':
                    cause=('source pad' if r['index']!=13 else 'source trace')
                    why=('The pad was omitted by the trace-only cause search.' if r['index']in(20,21,22) else
                         'The rectangle was protected before its own pad-area rule was tested.' if r['index']==18 else
                         'A single plotting flash at two matching stroke endpoints was treated as a terminal.')
                    r['explanation']=f'Place {n}/8: {why} Complete bump = {pct:.4f}% of original {cause} {r["ordinal"]}; depth {r["depth_mm"]:.6f} mm. Trimmed after retained centre/contact and assembled topology checks; no copper added.'
                elif r['index']==4:
                    r['explanation']=f'Place {n}/8: cap from pad 14249 is {pct:.4f}% of its original area. It exceeds the strictly-under-10% rule. The separate shallow-trace rule does not apply to a pad cap. Kept unchanged.'
                elif r['index']in(5,6):
                    r['explanation']=f'Place {n}/8: compound trace-end cap is {pct:.4f}% of the largest intersecting source stroke ({r["ordinal"]}), depth {r["depth_mm"]:.6f} mm. Other stroke denominators are smaller. Shallow-edge depth/path checks also fail. Adjacent rectangular pads only graze the window and cannot supply the denominator. Kept unchanged.'
                else:r['explanation']=f'Place {n}/8: still held by {r["reason"]}; under-10% area alone does not override this contact/protection or geometry check. Kept unchanged.'
            stage['owner_detected_supported_edge_cleanup']['accepted']+=accepted
            stage['owner_detected_supported_edge_cleanup']['deferred']=deferred
            stage['owner_unresolved_place_review']=dict(schema=1,records=review,source_sha256=cfg['source_sha256'],clearance_searches=0)
            stage['hybrid_components']=dict(continuous_source_bodies={s:dict(wkb_hex=to_wkb(g).hex(),display_treatment='Original source trim only; saved correction') for s,g in after.values.items() if to_wkb(g)!=to_wkb(original[s])},changed_bulk_copper={})
            stage['trim_only_phase']=dict(passed=True,positive_copper_mm2=image.difference(source_image).area,
                total_removed_mm2=source_image.difference(image).area,new_batch=proof,
                topology_before=list(topology(source_image)),topology_after=list(topology(image)),
                explicit_causing_pad_exceptions=sorted(approved_pad_ids),unselected_rectangles_preserved=True,
                rectangular_bumps_considered=False,ignored_rectangular_indices=[r['index']for r in review if r['status']=='ignored'],
                nominal_0250_trace_preserved=True,clearance_searches=0,clearance_checks=0,source_bytes_changed=False)
            stage['source_preview_parent']=dict(path=parent_ref['path'],sha256=parent_ref['sha256'],role='VERIFIED_TRIM_ONLY_PARENT')
            artifact=write_stage(out/'construction.json.gz',stage)
            result=dict(status='BOUNDED_EIGHT_PLACE_REVIEW_PASS',stage=artifact,review=review,proof=stage['trim_only_phase'],
                asset_manifest=assets,input_binding=stage['input_binding'],source_preview_parent=stage['source_preview_parent'],
                context=copper.diagnostics(),full_board_growth=False,export=False,wall_s=time.perf_counter()-started)
            (out/'RESULT.json').write_bytes(encode(result))
            print(json.dumps(dict(status=result['status'],corrected=[r['index']for r in review if r['status']=='corrected'],kept=[(r['index'],r.get('reason'))for r in review if r['status']=='unresolved'],wall_s=result['wall_s'])),flush=True)
        if args.show:
            event=enqueue(args.connection,label='ORIGINAL SOURCE · eight-place review · trimming only · grey Preview',report=out/'RESULT.json',construction=out/'construction.json.gz')
            (out/'VIEWER_EVENT.json').write_bytes(encode(event))
    except BaseException as exc:
        (out/'FAILED.json').write_bytes(encode(dict(error=repr(exc),traceback=traceback.format_exc())))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--connection',type=Path,required=True);p.add_argument('--parent-result',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--show',action='store_true')
    run(p.parse_args())
