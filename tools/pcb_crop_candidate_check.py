#!/usr/bin/env python3
"""Post-T01 source/coverage handoff. Never opens a historical candidate oracle."""
from pathlib import Path
import argparse,json,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.stage_abi.store import ArtifactStore,digest
from src.pcb_data_abi.crop_custody import accepted,ROI,T01
from src.t01_crop.source import context
from tools.t01_operator_host import read,fresh,state

def execute(session):
    rs=accepted(session,(*ROI,*T01));cap=state(session);store=ArtifactStore(Path(cap['store_path']))
    candidate_ref=rs['t01_run']['result']['result']['candidate_ref'];candidate=store.get_json(candidate_ref,kind='candidate')
    verification_ref=rs['t01_verify']['result']['result']['verification_ref'];v=store.get_json(verification_ref,kind='verification')
    policy=store.get_json(cap['policy_ref'],kind='policy');scene=store.get_json(cap['scene_ref'],kind='scene')
    b,raw,rows,shapes,sites=context(store,scene,policy);ids={s['source_id'] for s in sites};aliases={a for s in sites for a in s['aliases']}
    if (v['geometric_status']!='PASS' or v['candidate_ref']!=candidate_ref or not v['check']['passed'] or v['check']['failures'] or
        {d['source_id'] for d in candidate['decisions']}!=ids or set(candidate['replacements'])!=aliases or
        len(candidate['final_checks'])!=len(ids) or not all(r['check']['passed'] for r in candidate['final_checks']) or
        b['roi_sha256']!=digest((session/'data_roi/roi_verified.json').read_bytes()) or candidate['owner_status']!='PENDING' or candidate['independent_status']!='NOT_RUN'):raise ValueError('CROP_CANDIDATE_HANDOFF_FAILED')
    facts=dict(passed=True,canonical_sites=len(ids),aliases=len(aliases),complete_source_coverage=True,full_reconstruction_passed=True,protected_sources_unchanged=True,historical_candidate_read=False,owner_status='PENDING_USER')
    receipt=dict(status='PASS_CROP_T01_VERIFIED',facts=facts,binding_ref=cap['binding_ref'],scene_ref=cap['scene_ref'],candidate_ref=candidate_ref,verification_ref=verification_ref,source_sha256=b['source_sha256'],roi_sha256=b['roi_sha256'],owner_status='PENDING_USER',independent_status='NOT_RUN',electrical_manufacturing='NOT_ESTABLISHED')
    fresh(session/'RECEIPT.json',receipt);return dict(facts=facts,receipt_sha256=digest((session/'RECEIPT.json').read_bytes()))

def main():
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--input',type=Path,required=True);a=p.parse_args();r={}
    try:
        r=read(a.input)
        if set(r)!={'abi_version','request_id','operation'} or r['abi_version']!='pcb-crop-handoff/1' or r['operation']!='crop_candidate_check':raise ValueError('CROP_CHECK_REQUEST_INVALID')
        session=a.session.absolute()
        if not session.is_relative_to(ROOT/'out') or '..' in session.parts:raise ValueError('CROP_CHECK_SCOPE_INVALID')
        result=execute(session);error=None;code=0
    except Exception as e:result=None;error=dict(code='CROP_CHECK_REJECTED',message=str(e));code=2
    print(json.dumps(dict(abi_version='pcb-crop-handoff/1',request_id=r.get('request_id'),operation=r.get('operation'),status='OK' if not error else 'REJECTED',result=result,error=error),sort_keys=True));return code
if __name__=='__main__':raise SystemExit(main())
