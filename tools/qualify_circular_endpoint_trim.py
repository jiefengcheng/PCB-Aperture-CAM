"""Bounded owner-marked curved-edge trim at a native round stroke end."""
import argparse,copy,gzip,json,math,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shapely import from_wkb,to_wkb
from shapely.geometry import box,Point
from src.viewer_abi.live import load_connection,artifact_reader,construction_map,read_bound,enqueue
from src.viewer_abi.publisher import encode,digest
from src.shared_copper_context import for_board
from src.bulk_edge_restore import fit_circular_stroke_end_flanks,topology
from src.gerber_u05.source_edge_cleanup import CleanupBatch
from src.gerber_u05.group_board_job import write_stage
from tools.preflight import verify_manifest


def run(args):
    out=args.output.resolve()
    if not out.is_relative_to(Path('out/lacie_work').resolve()):raise ValueError('LACIE_OUTPUT_REQUIRED')
    out.mkdir(parents=True,exist_ok=False);started=time.perf_counter()
    try:
        assets=verify_manifest();cfg=load_connection(args.connection);read=artifact_reader(cfg['legacy'])
        scene=json.loads(read(cfg['scene_ref']));rows={r['source_id']:r for r in scene['objects']}
        original={s:from_wkb(read(r['geometry_ref']))for s,r in rows.items()}
        byordinal={r['metadata']['gerber_ordinal']:s for s,r in rows.items()}
        prior=json.loads(args.parent_result.read_bytes());ref=prior['stage']
        raw=read_bound(ref['path'],ref['sha256']);stage=json.loads(gzip.decompress(raw));mapping=construction_map(stage,cfg)
        if stage.get('operation')!='TRIM_ONLY' or stage['trim_only_phase'].get('rectangular_bumps_considered')is not False:
            raise ValueError('TRIM_ONLY_WITH_RECTANGLES_DEFERRED_REQUIRED')
        anchor=byordinal[15673];cause=byordinal[14440];center=rows[anchor]['metadata']['route_points_mm'][0]
        domain=box(45.49,-15.06,45.59,-14.65)
        with for_board(original) as copper:
            before=copper.acquire({s:from_wkb(bytes.fromhex(w))for s,w in mapping.items()})
            owner,body=before.owner(cause);fixed_owner,fixed=before.owner(anchor)
            if owner==fixed_owner:raise ValueError('INDEPENDENT_FIXED_ROUND_STROKE_REQUIRED')
            # Reuse the existing T02/T05 ordered 32-edge preparation. The
            # two admitted angular sectors are pinned bounded source supports;
            # this is not a whole-board circular-defect discovery claim.
            sections=copper.boundary_sections(body,Point(center).buffer(.65).envelope)
            points=list(dict.fromkeys(p for _,part in sections for p in part.coords))
            flanks=[]
            for low,high in [(-44,-31),(32,65)]:
                flanks.append([p for p in points if low<=math.degrees(math.atan2(p[1]-center[1],p[0]-center[0]))<=high
                               and .395<math.dist(p,center)<.405])
            _,edge,evidence=fit_circular_stroke_end_flanks(*flanks,rows[anchor],original[anchor],0,domain)
            evidence.update(source_sha256=cfg['source_sha256'],source_boundary_section_ids=[i for i,_ in sections],
                source_boundary_section_sha256=digest(b''.join(to_wkb(g)for _,g in sections)),
                bounded_angular_sectors_degrees=[[-44,-31],[32,65]],window_mm=list(domain.bounds))
            mask=Point(center).buffer(evidence['radius_mm'],quad_segs=512).intersection(domain)
            feature=dict(causing_id=cause,domain=domain,removal_mask=mask,smooth_edge=edge,
                         reference_evidence=evidence,backing_point=(45.7,-14.85))
            batch=CleanupBatch(rows,original,before,[feature],protected_domains=[fixed])
            record=batch.propose(0)
            (out/'LOCAL_PROPOSAL.json').write_bytes(encode(record))
            if record['owner_authorized_free_source_end_retreats']:
                raise ValueError('CURVED_EDGE_TRIM_CHANGES_ORIGINAL_STROKE_CENTERLINE')
            after,proof=batch.finish();copper.validate()
            if any(to_wkb(after.values[s])!=to_wkb(before.values[s])for s in before.owner_sources[fixed_owner]):
                raise ValueError('FIXED_REFERENCE_ROUND_STROKE_OWNER_CHANGED')
            if any(to_wkb(after.values[s])!=to_wkb(before.values[s])for s,r in rows.items()if r['kind']=='rectangle'):
                raise ValueError('DEFERRED_RECTANGLE_CHANGED')
            source=copper.source.image();material=after.image()
            if material.difference(source).area>1e-12 or topology(material)!=topology(source):
                raise ValueError('ADDITION_OR_ASSEMBLED_TOPOLOGY_CHANGED')
            cut=before.image().difference(material);checks=[]
            for sid in record['changed_source_ids']:
                # The complete physical numerator is qualified against its
                # causing original trace by CleanupBatch. Tiny overlapping
                # plotting fragments are not independent denominators.
                if before.values[sid].difference(after.values[sid]).area<=1e-12:continue
                checks.append(dict(case='round_endpoint_15673',source_id=sid,ordinal=rows[sid]['metadata']['gerber_ordinal'],
                    original_feature_area_mm2=original[sid].area,protrusion_area_mm2=cut.area,
                    area_fraction=cut.area/original[sid].area,is_noise=True,
                    area_basis='WHOLE_PHYSICAL_BUMP / ORIGINAL_CAUSING_TRACE; OVERLAPS_NOT_SUMMED'))
            circular=stage['owner_marked_circular_edge_corrections']
            circular['noise_area_checks']+=checks
            circular['records'].append(dict(case='round_endpoint_15673',window_mm=list(domain.bounds),source_ordinal=14440,
                reference_stroke_ordinal=15673,proof=record['geometry_checks'],source_contribution_checks=checks,
                assembled_added_area_mm2=proof['actual_added_mm2'],assembled_removed_area_mm2=cut.area,
                native_center_paths_preserved=True,reference_stroke_owner_bytes_preserved=True))
            stage['hybrid_components']=dict(continuous_source_bodies={s:dict(wkb_hex=to_wkb(g).hex(),display_treatment='Saved original-source trim only; no widening')
                for s,g in after.values.items()if to_wkb(g)!=to_wkb(original[s])},changed_bulk_copper={})
            stage['trim_only_phase']=dict(passed=True,positive_copper_mm2=material.difference(source).area,
                total_removed_mm2=source.difference(material).area,new_batch=proof,
                topology_before=list(topology(source)),topology_after=list(topology(material)),
                rectangular_bumps_considered=False,all_rectangles_preserved=True,clearance_searches=0,clearance_checks=0,
                fixed_round_endpoint_owner_bytes_preserved=True,source_bytes_changed=False)
            stage['source_preview_parent']=dict(path=ref['path'],sha256=ref['sha256'],role='VERIFIED_TRIM_ONLY_PARENT_WITH_RECTANGLES_DEFERRED')
            artifact=write_stage(out/'construction.json.gz',stage)
            result=dict(status='BOUNDED_CIRCULAR_ENDPOINT_TRIM_PASS',stage=artifact,input_binding=stage['input_binding'],
                proof=stage['trim_only_phase'],source_checks=checks,anchor=evidence,source_preview_parent=stage['source_preview_parent'],
                asset_manifest=assets,context=copper.diagnostics(),wall_s=time.perf_counter()-started,
                full_board_growth=False,export=False,viewer_source_focus=dict(source_id=anchor,route_point_index=0,radius_mm=.6))
            (out/'RESULT.json').write_bytes(encode(result));print(json.dumps(dict(status=result['status'],removed_mm2=cut.area,
                fractions=[r['area_fraction']for r in checks],fit_error_mm=evidence['maximum_radial_fit_error_mm'],
                wall_s=result['wall_s'])),flush=True)
        if args.show:
            event=enqueue(args.connection,label='ORIGINAL SOURCE · circular stroke-end edge trimmed · rectangles ignored · grey Preview',
                          report=out/'RESULT.json',construction=out/'construction.json.gz')
            (out/'VIEWER_EVENT.json').write_bytes(encode(event))
    except BaseException as exc:
        (out/'FAILED.json').write_bytes(encode(dict(error=repr(exc),traceback=traceback.format_exc())))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--connection',type=Path,required=True);p.add_argument('--parent-result',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--show',action='store_true');run(p.parse_args())
