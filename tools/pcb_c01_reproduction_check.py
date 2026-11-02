#!/usr/bin/env python3
"""Post-construction C01 oracle/checkpoint operation; never constructs geometry."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.c01_pipeline.bindings import T01, ORACLE, accepted, local
from src.stage_abi.store import ArtifactStore, digest
from src.trace_first_pipeline import verify_files
from tools.t01_operator_host import check, read, fresh

def reproduce_check(session):
    session = local(session); custody = check(session)
    responses = accepted(session, T01)
    cap = read(session/'capsule_02.json')
    run = responses['t01_run']['result']['result']
    verified = responses['t01_verify']['result']['result']
    store = ArtifactStore(session/'runtime')
    candidate = store.get_json(run['candidate_ref'], kind='candidate')
    verification = store.get_json(verified['verification_ref'], kind='verification')
    if (verification['candidate_ref'] != run['candidate_ref'] or
            verification['geometric_status'] != 'PASS' or not verification['check']['passed']):
        raise ValueError('C01_FRESH_VERIFICATION_REQUIRED')
    # Only here, after all nine constructed/reconstructed results and observations.
    hist = ROOT/'out/crop_dynamic_tasks/c01_existing_t01_freeze_20261029_239'
    historical = read(hist/'FREEZE_RECEIPT.json')
    verify_files(hist/'frozen', historical['file_bindings'])
    old = read(hist/'frozen/report.json'); oldmap = {d['source_id']:d for d in old['decisions']}
    matches = []
    for row in candidate['decisions']:
        previous = oldmap[row['source_id']]
        actual = store.get(row['candidate_ref'], kind='geometry')
        expected = (hist/'frozen'/previous['geometry']['dynamic']).read_bytes()
        same = all(row[k] == previous[k] for k in ('proposed_radius_mm','decision','priority','aliases'))
        matches.append(dict(key=row['key'],source_id=row['source_id'],aliases=row['aliases'],
                            actual_sha256=digest(actual),expected_sha256=digest(expected),
                            bytes_equal=actual == expected,semantics_equal=same))
    if (len(matches) != 51 or any(not m['bytes_equal'] or not m['semantics_equal'] for m in matches)
            or candidate['allocation']['groups'] != old['groups']):
        raise ValueError('C01_FROZEN_REPRODUCTION_MISMATCH')
    # Retain the working legacy receipt shape expected by the unchanged data ABI.
    receipt = dict(status='PASS_BOUNDED_C01_MACOS_NATIVE_ROUTE_REPRODUCTION',
        **{k:cap[k] for k in ('binding_ref','policy_ref','scene_ref','plan_ref')},
        candidate_ref=run['candidate_ref'],verification_ref=verified['verification_ref'],
        source_sha256=read(ROOT/'contracts/t01/c01.binding.json')['source_sha256'],
        matched_canonical_sites=51,matched_alias_occurrences=candidate['source_occurrences'],
        all_51_candidate_bytes_equal=True,counts=candidate['counts'],
        neighbor_response_controls=len(candidate['events']),neighbor_response_sites=candidate['neighbor_response_sites'],
        square_disabled_controls=candidate['square_disabled_controls'],
        minimum_unexempted_addition_gap_mm=min(d['check']['minimum_unexempted_addition_gap_mm'] for d in candidate['final_checks'] if d['check'].get('minimum_unexempted_addition_gap_mm') is not None),
        verification=verification,owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',
        native_electrical_manufacturing='NOT_ESTABLISHED',
        T02_T03_T04_T05='UNCHANGED_AND_NOT_EXECUTED',
        oracle_scope='Post-construction exact source contours, decisions, priorities, aliases, radii and groups; not construction input')
    fresh(session/'C01_SOURCE_MATCHES.json', matches)
    fresh(session/'RECEIPT.json', receipt)
    return dict(facts=dict(passed=True,canonical_sites=51,aliases=candidate['source_occurrences'],
        contour_bytes_equal=True,source_semantics_equal=True,allocation_groups_equal=True,
        oracle_opened_after_construction=True,owner_status='PENDING_USER'),
        receipt=str(session/'RECEIPT.json'),receipt_sha256=digest((session/'RECEIPT.json').read_bytes()),custody=custody)

def main():
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--input',type=Path,required=True);args=p.parse_args()
    req={}
    try:
        req=read(args.input)
        if set(req)!={'abi_version','request_id','operation'} or req['abi_version']!='pcb-c01-handoff/1' or req['operation']!=ORACLE:
            raise ValueError('C01_HANDOFF_REQUEST_INVALID')
        result=reproduce_check(args.session);status='OK';error=None;code=0
    except Exception as e:
        result=None;status='REJECTED';error=dict(code='C01_HANDOFF_REJECTED',message=str(e));code=2
    print(json.dumps(dict(abi_version='pcb-c01-handoff/1',request_id=req.get('request_id'),operation=req.get('operation'),status=status,result=result,error=error),allow_nan=False))
    return code

if __name__=='__main__':raise SystemExit(main())
