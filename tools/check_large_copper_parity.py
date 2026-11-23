"""Compare an authenticated saved cleanup job with an explicit saved reference.

This qualification tool is not an execution input. Neither its reference masks
nor its reviewed windows/ordinals are consumed by the source processing runner.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from shapely import from_wkb,to_wkb
from shapely.geometry import box
from src.large_copper_runner import authenticate,workspace_path,read_file
from src.shared_copper_context import for_board
from src.bulk_edge_restore import topology
from src.viewer_abi.publisher import encode


def changed(stage):
    out={}
    for key in ('continuous_source_bodies','changed_bulk_copper'):
        for sid,item in stage['hybrid_components'].get(key,{}).items():
            if sid in out:raise ValueError('REFERENCE_DUPLICATE_SOURCE_OVERLAY')
            out[sid]=from_wkb(bytes.fromhex(item if isinstance(item,str) else item['wkb_hex']))
    return out


def compare(job,reference,sha,output):
    from src.gerber_u05.workspace import configure
    configure();output=workspace_path(output);output.mkdir(parents=True,exist_ok=False)
    try:
        raw=read_file(reference,1024**3)
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('REFERENCE_HASH_MISMATCH')
        ref=json.loads(gzip.decompress(raw));result,stage,rows,original=authenticate(job)
        if (ref.get('operation')!='TRIM_ONLY' or ref['input_binding']['source_sha256']!=stage['input_binding']['source_sha256']):
            raise ValueError('REFERENCE_SOURCE_OR_OPERATION_MISMATCH')
        for binding in ('scene_ref','original_scene_ref'):
            if binding in ref['input_binding'] and binding in stage['input_binding'] and ref['input_binding'][binding]['sha256']!=stage['input_binding'][binding]['sha256']:
                raise ValueError('REFERENCE_ORIGINAL_SCENE_MISMATCH')
        previous=changed(ref);new=changed(stage)
        if not set(previous)|set(new)<=set(original):raise ValueError('REFERENCE_FOREIGN_SOURCE_ID')
        with for_board(original) as context:
            before=context.source.image();reference_revision=context.acquire(previous)
            candidate_revision=context.acquire(new)
            old=reference_revision.image();after=candidate_revision.image()
            if old.difference(before).area>1e-12 or topology(old)!=topology(before):
                raise ValueError('REFERENCE_NOT_A_TOPOLOGY_PRESERVING_SUBTRACTION')
            required=before.difference(old);actual=before.difference(after)
            witnesses=[]
            for index,g in enumerate([g for g in getattr(required,'geoms',[required]) if g.area>1e-12]):
                missing=g.difference(actual).area
                witnesses.append(dict(index=index,bounds_mm=list(g.bounds),required_area_mm2=g.area,
                    missing_area_mm2=missing,exact_required_removal_covered=missing<=1e-12,
                    reference_wkb_sha256=hashlib.sha256(to_wkb(g)).hexdigest()))
            keeps=[]
            for r in ref.get('owner_unresolved_place_review',{}).get('records',[]):
                if r['status'] not in ('unresolved','ignored'):continue
                removed=actual.intersection(box(*r['bounds_mm'])).area
                keeps.append(dict(review_number=r['review_number'],source_ordinal=r['ordinal'],
                    saved_status=r['status'],new_removal_mm2=removed,unchanged=removed<=1e-12))
            same=sum(to_wkb(reference_revision.values[s])==to_wkb(candidate_revision.values[s]) for s in original)
            passed=(all(w['exact_required_removal_covered'] for w in witnesses) and all(k['unchanged'] for k in keeps)
                    and after.difference(before).area<=1e-12 and topology(after)==topology(before))
            report=dict(schema='large-copper-reviewed-reference-comparison/1',
                status='REVIEWED_REMOVAL_COVERAGE_PASS' if passed else 'REVIEWED_REMOVAL_COVERAGE_FAIL',
                reference=dict(path=str(Path(reference).resolve()),sha256=sha),candidate=result['stage'],
                source_sha256=stage['input_binding']['source_sha256'],source_occurrences=len(original),
                reviewed_removal_witnesses=witnesses,covered_witnesses=sum(w['exact_required_removal_covered'] for w in witnesses),
                total_witnesses=len(witnesses),reviewed_keep_or_ignored=keeps,
                exact_reference_contribution_byte_parity=same==len(original),matching_reference_contributions=same,
                comparison_scope='REQUIRED_REVIEWED_REMOVAL_COVERAGE_IS_DISTINCT_FROM_COMPLETE_RESULT_BYTE_EQUALITY',
                reference_removed_mm2=required.area,candidate_removed_mm2=actual.area,
                missing_reference_removal_mm2=required.difference(actual).area,
                additional_generic_removal_mm2=actual.difference(required).area,
                added_relative_to_original_mm2=after.difference(before).area,
                topology_before=topology(before),topology_after=topology(after),
                candidate_counts=result['counts'],candidate_timings=result['timings'],
                owner='PENDING_USER',electrical_manufacturing='NOT_ESTABLISHED')
            (output/'PARITY.json').write_bytes(encode(report))
            text=f'''# Reviewed-removal comparison\n\n**{report['status']}**\n\n{report['covered_witnesses']} / {report['total_witnesses']} exact reviewed removal witnesses covered.\nAll reviewed KEEP/ignored windows unchanged: {all(k['unchanged'] for k in keeps)}.\n\nComplete source-contribution byte equality to the reviewed result: **{report['exact_reference_contribution_byte_parity']}** ({same}/{len(original)}).\nThe generic survey has additional removals; required-case coverage is not whole-result byte parity.\n\nCandidate removed {actual.area:.17g} mm²; added relative to original {report['added_relative_to_original_mm2']:.17g} mm².\nPhysical topology {topology(before)} → {topology(after)}.\n\nSource SHA-256: `{report['source_sha256']}`.\nCandidate construction SHA-256: `{result['stage']['sha256']}`.\nReference construction SHA-256: `{sha}`.\n\n[Full comparison](PARITY.json). Original source and reference evidence remain unchanged.\nOwner review pending; no electrical/manufacturing acceptance.\n'''
            (output/'REPORT.md').write_text(text)
        return report
    except BaseException as exc:
        (output/'FAILED.json').write_bytes(encode(dict(status='FAILED_RETAINED',error=repr(exc),traceback=traceback.format_exc())))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True);parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--reference-sha256',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();r=compare(args.job,args.reference,args.reference_sha256,args.output)
    print(json.dumps({k:r[k] for k in ('status','covered_witnesses','total_witnesses','exact_reference_contribution_byte_parity','missing_reference_removal_mm2','candidate_counts')}))
    return 0 if r['status']=='REVIEWED_REMOVAL_COVERAGE_PASS' else 1


if __name__=='__main__':sys.exit(main())
