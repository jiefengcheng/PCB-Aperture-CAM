"""Additional C03 predicates; never replaces the existing native gate proof."""
from pathlib import Path
from src.stage_abi.store import digest
from src.c03_baseline_custody import ROOT,CONTRACT,CONTRACT_SHA256,specification,check
from src.c03_input_family import selected,FAMILY
from tools.t01_operator_host import HANDOFF,read


def augment(root,proof):
    root=Path(root)
    if not selected(root):raise ValueError('C03_CUSTODY_EXPLICIT_FAMILY_REQUIRED')
    spec,baseline=specification()
    actual=check(ROOT,root,HANDOFF/'CODE_BASELINE_SHA256.json')
    proof['checks'].extend([
        dict(predicate='c03_all_484_baseline_entries_checked',observed=actual['baseline_files'],expected=484,passed=actual['baseline_files']==484),
        dict(predicate='c03_exact_committed_successor_custody',observed=actual['effective_status'],expected='PASS',passed=actual['effective_status']=='PASS'),
        dict(predicate='c03_historical_mismatch_retained',observed=actual['retained_historical_mismatches'],expected=[dict(path=r['path'],historical_expected_sha256=r['historical_sha256'],current_sha256=r['successor_sha256'],historical_status='FAIL_RETAINED') for r in spec['successors']],passed=actual['retained_historical_mismatches']==[dict(path=r['path'],historical_expected_sha256=r['historical_sha256'],current_sha256=r['successor_sha256'],historical_status='FAIL_RETAINED') for r in spec['successors']]),
    ])
    files=[CONTRACT,HANDOFF/'CODE_BASELINE_SHA256.json',root/'C03_BASELINE_CUSTODY.json',root/'C03_INPUT_FAMILY.json']
    files += [ROOT/p for p in baseline]
    files += [ROOT/spec[k]['path'] for k in ('authorization','source_provenance')]
    files += [ROOT/r[k]['path'] for r in spec['successors'] for k in ('historical_copy','successor_copy')]
    for p in files:proof['evidence'][str(p)]=digest(p.read_bytes())
    proof['c03_baseline_reconciliation']=actual
    if proof['operation'] in ('t01_run','t01_verify'):
        # Original coverage and scoped execution are separate verdicts.
        response=read(root/'attempts'/proof['attempt_id']/'abi/stdout.json')['result']['result']
        if proof['operation']=='t01_run':coverage=response['candidate']['original_coverage']
        else:
            verification=response['verification']['check']
            coverage=dict(scoped_execution_pass=verification['passed'],original_full_coverage_pass=verification['original_full_coverage_pass'],blocked_original_positive=verification['blocked_original_positives'])
        for name,value,expected in [('scoped_round_execution',coverage['scoped_execution_pass'],True),('original_full_coverage_remains_unmet',coverage['original_full_coverage_pass'],False),('owner_blocked_round_retained',coverage['blocked_original_positive'],1)]:
            proof['checks'].append(dict(predicate='c03_'+name,observed=value,expected=expected,passed=type(value)is type(expected) and value==expected))
    if proof['operation'].startswith('t03_'):
        inspection=read(root/'u02_t03/t03_inspect.json');coverage=inspection['coverage']
        raw=coverage['retained_generic_source_port_failures']
        checks=[('explicit_input_contact_family',coverage['input_contact_family'],FAMILY),
                ('retained_generic_failed_pairs',len(raw),49),
                ('generic_failed_results_not_promoted',all(not r['passed'] or not r['original_contact_preserved'] for r in raw),True),
                ('scoped_round_coverage',coverage['original_obligations']['scoped_execution_pass'],True),
                ('original_full_coverage',coverage['original_obligations']['original_full_coverage_pass'],False)]
        from src.stage_abi.store import canonical
        checks.append(('complete_inspection_coverage_bound',inspection['facts']['complete_coverage_sha256'],digest(canonical(coverage))))
        for name,value,expected in checks:
            proof['checks'].append(dict(predicate='c03_'+name,observed=value,expected=expected,passed=type(value)is type(expected) and value==expected))
    proof['status']='PASS' if all(r['passed'] for r in proof['checks']) else 'FAIL'
    return proof
