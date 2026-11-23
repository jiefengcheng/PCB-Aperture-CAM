"""Bounded replay of saved cleanup operands, never a full-board growth run."""
import argparse
import gzip
import json
from pathlib import Path
import sys
import time
import resource

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shapely import from_wkb,to_wkb
from shapely.geometry import box,LineString
from src.shared_copper_context import CopperContext
from src.viewer_abi.live import load_connection,artifact_reader,construction_map,read_bound
from src.bulk_edge_restore import fit_straight_flanks
from src.gerber_u05.source_edge_cleanup import CleanupBatch
from src.viewer_abi.publisher import encode
from tools.preflight import verify_manifest


def qualify(output, warm_only=False, boundary_only=False):
    output.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();verify_manifest()
    root=Path('out/lacie_work/t04_source_corner_endpoint_fix_20261122')
    cfg=load_connection(Path('out/lacie_work/t04_large_fill_audit_20261122/source_viewer'))
    read=artifact_reader(cfg['legacy']);scene=json.loads(read(cfg['scene_ref']))
    rows={r['source_id']:r for r in scene['objects']}
    original={s:from_wkb(read(r['geometry_ref'])) for s,r in rows.items()}
    inventory=json.loads((root/'supported_cap_inventory_01/RESULT.json').read_bytes())
    stage=json.loads(gzip.decompress(read_bound(inventory['stage']['path'],inventory['stage']['sha256'])))
    mapping=construction_map(stage,cfg)
    current={s:from_wkb(bytes.fromhex(mapping[s])) if s in mapping else g for s,g in original.items()}
    target=json.loads(gzip.decompress((root/'detected_cap_corrections_02/construction.json.gz').read_bytes()))
    target_map=construction_map(target,cfg)
    expected={s:from_wkb(bytes.fromhex(target_map[s])) if s in target_map else g for s,g in original.items()}
    features=[]
    for i,c in enumerate(inventory['candidates']):
        if not c['causing_sources']:continue
        domain=box(*c['domain_bounds_mm'])
        sid=max((s['source_id'] for s in c['causing_sources']),key=lambda s:(original[s].intersection(domain).area,s))
        coord=c['edge_coordinate_mm'];lo,hi=c['tangent_bounds_mm']
        edge=LineString([(coord,lo-.01),(coord,hi+.01)]) if c['axis']==0 else LineString([(lo-.01,coord),(hi+.01,coord)])
        _,evidence=fit_straight_flanks(*c['flanks'],c['backing_point_mm'],domain)
        features.append(dict(causing_id=sid,domain=domain,smooth_edge=edge,reference_evidence=evidence,backing_point=c['backing_point_mm']))
    prepared=time.perf_counter()
    with CopperContext(original,source_binding=dict(source_sha256=cfg['source_sha256']),
                       frame=dict(units='mm',axes='X_RIGHT_Y_DOWN',layer='SOURCE_BOUND_COPPER'),
                       role='native-stage' if boundary_only else 'cleanup') as context:
        revision=context.source if boundary_only else context.acquire({s:g for s,g in current.items() if to_wkb(g)!=to_wkb(original[s])})
        after_prepare=time.perf_counter()
        if boundary_only:
            from src import indexed_polygon_distance as distance
            from src.component_clearance import Context
            from src.gerber_u05 import pipeline
            from src.shared_copper_context import digest
            raw=Path('dataset/szu-comm_3020301113B_intake_ready_20261021_v2/raw/ORG/top_layer.gdo.gbr').read_bytes()
            if digest(raw)!=cfg['source_sha256']:raise ValueError('ORIGINAL_RAW_SOURCE_CHANGED')
            parsed,_,_=pipeline.source_profile.parse_source(raw)
            native_source=pipeline.affine_scale(pipeline.source_profile.ordered(
                (pipeline.source_profile.object_geometry(o)[0],o.polarity_dark) for o in parsed.objects),1,-1,origin=(0,0))
            reference=Context(native_source,cfg['source_sha256'],original)
            expected_owner_fingerprint=reference.index.fingerprint
            expected_memberships=pipeline.digest(pipeline.canonical(reference.ids))
            body=max(reference.cores.values(),key=lambda g:len(to_wkb(g)))
            x,y,right,top=body.bounds;query=box(right+.2,top+.2,right+.3,top+.3)
            distance.clear();expected=distance.distance(query,body);distance.clear()
            del reference
            measured=time.perf_counter()
            with context.activate():
                physical=Context(native_source,cfg['source_sha256'],original)
                assert physical.index is context.original_owner_index(native_source)
                assert physical.index.fingerprint==expected_owner_fingerprint
                assert pipeline.digest(pipeline.canonical(physical.ids))==expected_memberships
                body=max(physical.cores.values(),key=lambda g:len(to_wkb(g)))
                first=distance.distance(query,body)
                tree=distance.boundary_index(body)[0]
                assert tree is context.boundary_index(body)[0] and distance.measurement_engine() is context.native_engine
                if first.hex()!=expected.hex():raise ValueError('EXACT_BIG_COPPER_DISTANCE_CHANGED')
                native_handles=len(context.native_engine.handles)
                assert native_handles==1
            result=dict(status='EXISTING_T02_T05_LARGE_COPPER_STRUCTURE_SHARED',context=context.diagnostics(),
                        exact_distance_hex=first.hex(),retained_native_handles=native_handles,
                        original_owner_fingerprint=expected_owner_fingerprint,original_memberships_sha256=expected_memberships,
                        seconds=time.perf_counter()-measured,full_board_growth=False,export=False)
        elif warm_only:
            result=dict(status='AUTHENTICATED_REOPEN',context=context.diagnostics(),seconds=time.perf_counter()-prepared)
        else:
            batch=CleanupBatch(rows,original,revision,features)
            before_construct=dict(context.stats)
            local_start=time.perf_counter()
            for i in range(len(features)):
                try:batch.propose(i)
                except ValueError as exc:batch.failures.append(dict(index=i,reason=str(exc)))
            local_seconds=time.perf_counter()-local_start
            assert context.stats['affected_owner_unions']==before_construct.get('affected_owner_unions',0)
            assert context.stats['assembled_board_unions']==before_construct.get('assembled_board_unions',0)
            verify_start=time.perf_counter();revision,proof=batch.finish();verification_seconds=time.perf_counter()-verify_start
            residuals={s:revision.values[s].symmetric_difference(g).area for s,g in expected.items()
                       if to_wkb(revision.values[s])!=to_wkb(g)}
            if any(a>1e-12 for a in residuals.values()) or len(proof['records'])!=14 or len(proof['kept'])!=3:
                raise ValueError('SAVED_CLEANUP_PARITY_FAILED:'+str(residuals))
            result=dict(status='BOUNDED_SAVED_CLEANUP_PARITY_PASS',records=proof['records'],kept=proof['kept'],
                parity_residuals_mm2=residuals,context=context.diagnostics(),
                timing=dict(intake_s=prepared-start,prepare_s=after_prepare-prepared,local_construction_s=local_seconds,
                            assembled_verification_s=verification_seconds,total_s=time.perf_counter()-start),
                peak_process_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                full_board_growth=False,export=False,independent_review='NOT_RUN: CHANNEL_UNAVAILABLE',
                electrical_manufacturing='NOT_ESTABLISHED')
        (output/'RESULT.json').write_bytes(encode(result))
        print(json.dumps({k:v for k,v in result.items() if k not in ('records','kept','parity_residuals_mm2')}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--warm-only',action='store_true');parser.add_argument('--boundary-only',action='store_true')
    args=parser.parse_args()
    workspace=Path('out/lacie_work').resolve()
    if not args.output.resolve().is_relative_to(workspace):raise ValueError('LACIE_OUTPUT_REQUIRED')
    try:qualify(args.output,args.warm_only,args.boundary_only)
    except BaseException as exc:
        if args.output.exists():(args.output/'FAILED.json').write_bytes(encode(dict(error=repr(exc))))
        raise
