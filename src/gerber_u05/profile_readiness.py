"""Bind bounded native evidence to the explicit T04-only full-board entry."""
import gzip
import json
from pathlib import Path
import tarfile
from . import pipeline as p, profile_intake as intake
from .profile_schedule import SCHEDULE

STATUS = 'QUALIFIED_T04_SOURCE_BUILT_PROFILE_ENTRY'


def bound(path, sha):
    raw = Path(path).read_bytes()
    if p.digest(raw) != sha:
        raise ValueError('T04_PROFILE_QUALIFICATION_EVIDENCE_CHANGED:'+str(path))
    return json.loads(raw)


def reports(case, stage):
    needed = {row['report_ref']['artifact_id'] for row in stage['evaluations']}
    needed.add(stage['source_built_profile']['baseline_stage_ref']['artifact_id'])
    objects = {}
    # Retained qualification archives are read without extraction or mutation.
    with tarfile.open(case/'runtime.tar.gz', 'r|gz') as archive:
        for member in archive:
            key = member.name.removeprefix('artifacts/')
            if member.isfile() and key in needed:
                raw = archive.extractfile(member).read()
                if p.digest(raw) != key.split(':', 1)[1]:
                    raise ValueError('T04_PROFILE_NATIVE_ARTIFACT_CHANGED')
                objects[key] = json.loads(raw)
    if set(objects) != needed:
        raise ValueError('T04_PROFILE_NATIVE_ARTIFACT_MISSING')
    first = objects[stage['source_built_profile']['baseline_stage_ref']['artifact_id']]
    extra = {r['report_ref']['artifact_id'] for r in first['evaluations']}
    with tarfile.open(case/'runtime.tar.gz', 'r|gz') as archive:
        for member in archive:
            key = member.name.removeprefix('artifacts/')
            if member.isfile() and key in extra:
                raw = archive.extractfile(member).read()
                if p.digest(raw) != key.split(':', 1)[1]:
                    raise ValueError('T04_PROFILE_NATIVE_ARTIFACT_CHANGED')
                objects[key] = json.loads(raw)
    if not extra <= set(objects):
        raise ValueError('T04_PROFILE_NATIVE_ARTIFACT_MISSING')
    for phase in (first, stage):
        if (phase['solution']['pass_increments'] != list(SCHEDULE) or not phase['motion_validation']['passed']
                or phase['motion_validation']['terminal_owner_splits'] or phase['motion_validation']['terminal_owner_merges']
                or set(phase['checks']) != {'nominal', 'envelope'}):
            raise ValueError('T04_PROFILE_NATIVE_FINAL_SCOPE_CHANGED')
        for check in phase['checks'].values():
            if (not check['passed'] or check['failures'] or not check['evaluation_complete']
                    or not check['scene_union_materialized'] or not check['functional_channels']['passed']
                    or any(not v['passed'] for v in check['original_source_voids'])):
                raise ValueError('T04_PROFILE_NATIVE_FINAL_CHECK_FAILED')
        chain = None
        for row in phase['evaluations']:
            report = objects[row['report_ref']['artifact_id']]
            physical = next((q for q in report.get('checks', ()) if q.get('schema') == 'u03-incremental-width-check/1'), None)
            if physical is None:
                raise ValueError('T04_PROFILE_NATIVE_PROOF_MISSING')
            if chain is None:
                chain = physical['previous_passing_state_sha256']
            if chain != physical['previous_passing_state_sha256']:
                raise ValueError('T04_PROFILE_NATIVE_CHAIN_BROKEN')
            if physical['passed']:
                successor = p.digest(p.canonical(dict(previous=chain, updates=physical['updates'])))
                if successor != physical['passing_state_sha256']:
                    raise ValueError('T04_PROFILE_NATIVE_CHAIN_CHANGED')
                if report['passed']:
                    chain = successor
    return first


def require(path, rule):
    qualification = p.load(path)
    code = intake.source_inventory()
    if qualification.get('status') != STATUS or qualification['source_files'] != code:
        raise ValueError('T04_PROFILE_QUALIFIED_CODE_REQUIRED')
    for key in ('source_sha256', 't03_sha256', 'scene_ref'):
        if qualification['inputs'][key] != rule['input_binding'][key]:
            raise ValueError('T04_PROFILE_QUALIFIED_INPUT_CHANGED')
    if qualification['inputs']['policy_sha256'] != rule['policy_sha256']:
        raise ValueError('T04_PROFILE_QUALIFIED_POLICY_CHANGED')
    tests = bound(qualification['tests']['path'], qualification['tests']['sha256'])
    if tests['exit_code'] != 0 or tests['failed'] != 0 or tests['source_files'] != code:
        raise ValueError('T04_PROFILE_QUALIFICATION_TEST_FAILED')
    log = Path(tests['log']).read_bytes()
    if p.digest(log) != tests['log_sha256']:
        raise ValueError('T04_PROFILE_QUALIFICATION_TEST_LOG_CHANGED')
    kinds = set()
    for evidence in qualification['cases']:
        case = Path(evidence['directory'])
        receipt = bound(case/'RESULT.json', evidence['receipt_sha256'])
        if (receipt['status'] != 'PASS' or receipt['full_board_run'] or receipt['replay']
                or receipt['source_files'] != code or receipt['inputs'] != qualification['inputs']):
            raise ValueError('T04_PROFILE_QUALIFICATION_CASE_CHANGED')
        raw = gzip.decompress((case/'t04.json.gz').read_bytes())
        if p.digest(raw) != receipt['stage_sha256']:
            raise ValueError('T04_PROFILE_QUALIFICATION_STAGE_CHANGED')
        stage = json.loads(raw)
        if not stage['source_built_profile']['all_baseline_copper_preserved']:
            raise ValueError('T04_PROFILE_QUALIFICATION_RETENTION_FAILED')
        reports(case, stage)
        kinds.add(evidence['kind'])
    if kinds != {'five', '64'}:
        raise ValueError('T04_PROFILE_QUALIFICATION_COHORTS_MISSING')
    return qualification
