#!/usr/bin/env python3
"""Capture all nine native/cache operands without weakening exact source identity.

Exit 3 means evidence was captured but strict binding identity failed. It never
means that an approximate match, candidate, clearance or stage was accepted.
"""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import argparse,hashlib,importlib.metadata,json,math,platform
import shapely
from shapely import from_wkb,to_wkb,get_coordinates
import sexpdata
from src.crop_attachment_diagnostic import _decode
from src import native_inventory,crop_attachment_diagnostic

SOURCE_SHA='850c4c74d55717a721d4bbed7ec876ee086f475efd97f69bb5b5164ef77533a0'


def sha(blob):return hashlib.sha256(blob).hexdigest()


def compare(cached_blob,reconstructed_blob):
    cached,reconstructed=map(from_wkb,(cached_blob,reconstructed_blob))
    a,b=get_coordinates(cached).tolist(),get_coordinates(reconstructed).tolist()
    delta=[]
    if len(a)==len(b):
        for i,(av,bv) in enumerate(zip(a,b,strict=True)):
            if av!=bv:
                delta.append(dict(index=i,cached_mm=av,reconstructed_mm=bv,
                    cached_hex=[float(x).hex() for x in av],reconstructed_hex=[float(x).hex() for x in bv],
                    delta_mm=[bv[j]-av[j] for j in (0,1)],euclidean_delta_mm=math.dist(av,bv)))
    return dict(byte_identical=cached_blob==reconstructed_blob,cached_wkb_sha256=sha(cached_blob),
        reconstructed_wkb_sha256=sha(reconstructed_blob),cached_type=cached.geom_type,reconstructed_type=reconstructed.geom_type,
        cached_valid=cached.is_valid,reconstructed_valid=reconstructed.is_valid,
        cached_coordinate_count=len(a),reconstructed_coordinate_count=len(b),
        coordinate_order_comparison='INDEX_ALIGNED_ONLY; different ring order is not normalized',
        coordinate_differences=delta if len(a)==len(b) else None,
        cached_coordinates_mm=a,reconstructed_coordinates_mm=b,
        cached_bounds_mm=list(cached.bounds),reconstructed_bounds_mm=list(reconstructed.bounds),
        cached_area_mm2=cached.area,reconstructed_area_mm2=reconstructed.area,
        topological_equals=cached.equals(reconstructed),hausdorff_distance_mm=cached.hausdorff_distance(reconstructed),
        symmetric_difference_area_mm2=cached.symmetric_difference(reconstructed).area,
        numerical_tolerance_applied='NONE; these are raw diagnostics, not acceptance predicates')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--predecessor',type=Path,required=True)
    ap.add_argument('--packet',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();out=a.output.resolve();assert not out.exists(),'FRESH_OUTPUT_REQUIRED'
    raw=(a.predecessor/'inputs/ORG_source.kicad_pcb').read_bytes();assert sha(raw)==SOURCE_SHA
    manifest_blob=(a.predecessor/'inputs/source_manifest.json').read_bytes();bank=json.loads(manifest_blob)
    assert bank['source_sha256']==SOURCE_SHA
    rows={r['id']:r for r in bank['objects']};assert len(rows)==len(bank['objects'])
    result=json.loads((a.packet/'result.json').read_text());assert result['source_sha256']==SOURCE_SHA
    assert [s['site'] for s in result['sites']]==['R003','R005','R006','R012']
    out.mkdir(parents=True);records=[]
    for site in result['sites']:
        for role,sid in [('target',site['source_id']),('obstacle',site['obstacle_source_id']),('feed',site['feed_source_id'])]:
            if sid is None:continue
            original=rows[sid];cached=(a.predecessor/f'inputs/source_wkb/{original["geometry_sha256"]}.wkb').read_bytes()
            assert sha(cached)==original['geometry_sha256']
            digest,(record,)=_decode(raw,[sid]);assert digest==SOURCE_SHA
            kind,attrs,g,fragment_digest=record;reconstructed=to_wkb(g)
            prefix=f'{site["site"]}_{role}'
            (out/f'{prefix}_cached.wkb').write_bytes(cached)
            (out/f'{prefix}_reconstructed.wkb').write_bytes(reconstructed)
            start,end=map(int,sid.rsplit(':',2)[1:]);fragment=raw[start:end]
            assert sha(fragment)==fragment_digest
            (out/f'{prefix}.source').write_bytes(fragment)
            details=compare(cached,reconstructed)
            if kind=='gr_circle':
                center=tuple(map(float,attrs['center']));end=tuple(map(float,attrs['end']))
                radius=math.dist(center,end)
                details['native_circle_semantics']=dict(center_mm=list(center),end_mm=list(end),radius_mm=radius,
                    radius_hex=radius.hex(),quad_segs=native_inventory.steps(radius),
                    declared_curve_approximation_error_mm=native_inventory.ERROR_MM,
                    cached_vertex_radial_residuals_mm=[math.dist(v,center)-radius for v in details['cached_coordinates_mm']],
                    reconstructed_vertex_radial_residuals_mm=[math.dist(v,center)-radius for v in details['reconstructed_coordinates_mm']])
            records.append(dict(site=site['site'],role=role,source_id=sid,kind=kind,
                                original_fragment_sha256=fragment_digest,comparison=details))
    assert len(records)==9
    same=all(r['comparison']['byte_identical'] for r in records)
    modules={name:dict(path=str(Path(module.__file__).resolve()),sha256=sha(Path(module.__file__).read_bytes()))
             for name,module in [('native_inventory',native_inventory),('crop_attachment_diagnostic',crop_attachment_diagnostic),('sexpdata',sexpdata)]}
    evidence=dict(schema='c02-native-binding-mismatch-capture/1',
        status='CAPTURED_STRICT_IDENTITY_PASS' if same else 'CAPTURED_STRICT_IDENTITY_FAIL',
        acceptance='NONE; capture only. Exact REV10 binding condition is unchanged.',
        runtime=dict(python=sys.version,platform=platform.platform(),machine=platform.machine(),
            shapely=shapely.__version__,geos=shapely.geos_version_string,sexpdata=importlib.metadata.version('sexpdata')),
        modules=modules,source_sha256=SOURCE_SHA,source_manifest_sha256=sha(manifest_blob),
        operand_count=9,all_operands_byte_identical=same,operands=records,
        prohibited_inferences=['No cause attribution from Python/OS/version alone.',
            'No coordinate rounding, source replacement or numerical-tolerance waiver.',
            'No candidate rerun, positive-growth credit, T02 freeze, T03/T04 or native export.'])
    (out/'NATIVE_BINDING_CAPTURE.json').write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status=evidence['status'],operands=9,mismatching_operands=[r['source_id'] for r in records if not r['comparison']['byte_identical']],receipt=str(out/'NATIVE_BINDING_CAPTURE.json'))))
    return 0 if same else 3


if __name__=='__main__':sys.exit(main())
