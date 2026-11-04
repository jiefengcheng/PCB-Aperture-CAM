"""Fresh U03 crop handoff; all source coverage and protected-map checks retained."""
from src.stage_abi.store import ArtifactStore,digest
from src.pcb_data_abi.board_custody import accepted,ROI,T01
from tools.t01_operator_host import read,fresh,state
from pathlib import Path
from .crop_t01 import context
from .custody import verify_prefix,operation_steps

def execute(session):
    from src.c03_input_family import selected
    context_factory=context
    if selected(session):
        from src.c03_round_adapter import context as context_factory
    steps=operation_steps(session);rs=verify_prefix(session,steps[:steps.index('board_candidate_check')]);cap=state(session);store=ArtifactStore(Path(cap['store_path']))
    candidate_ref=rs['t01_run']['result']['result']['candidate_ref'];candidate=store.get_json(candidate_ref,kind='candidate')
    verification_ref=rs['t01_verify']['result']['result']['verification_ref'];v=store.get_json(verification_ref,kind='verification')
    policy=store.get_json(cap['policy_ref'],kind='policy');scene=store.get_json(cap['scene_ref'],kind='scene')
    from src.t01_board.policy import HEADER,validate_policy
    if policy.get('dialect')==HEADER:
        validate_policy(policy)
        from src.t01_board.source import context as context_factory
        from .selection import for_root,validate
        validate(for_root(session),scene['source_sha256'])
    b,raw,rows,shapes,sites=context_factory(store,scene,policy);ids={s['source_id'] for s in sites};aliases={a for s in sites for a in s['aliases']}
    if (v['geometric_status']!='PASS' or v['candidate_ref']!=candidate_ref or not v['check']['passed'] or v['check']['failures'] or
        {d['source_id'] for d in candidate['decisions']}!=ids or set(candidate['replacements'])!=aliases or
        len(candidate['final_checks'])!=len(ids) or not all(r['check']['passed'] for r in candidate['final_checks']) or
        b['scope_sha256']!=digest((session/'data_board/verified.json').read_bytes()) or candidate['owner_status']!='PENDING' or candidate['independent_status']!='NOT_RUN'):raise ValueError('BOARD_CANDIDATE_HANDOFF_FAILED')
    facts=dict(passed=True,canonical_sites=len(ids),aliases=len(aliases),complete_source_coverage=True,full_reconstruction_passed=True,protected_sources_unchanged=True,historical_candidate_read=False,owner_status='PENDING_USER')
    receipt=dict(status='PASS_BOARD_T01_VERIFIED',facts=facts,binding_ref=cap['binding_ref'],scene_ref=cap['scene_ref'],candidate_ref=candidate_ref,verification_ref=verification_ref,source_sha256=b['source_sha256'],scope_sha256=b['scope_sha256'],owner_status='PENDING_USER',independent_status='NOT_RUN',electrical_manufacturing='NOT_ESTABLISHED')
    fresh(session/'RECEIPT.json',receipt);return dict(facts=facts,receipt_sha256=digest((session/'RECEIPT.json').read_bytes()))

