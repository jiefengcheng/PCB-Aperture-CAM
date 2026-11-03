#!/usr/bin/env python3
"""Read-only retained dependency/checker benchmark. Never starts native jobs.

Use a pre-change checker source snapshot as the reference. Window comparisons
exclude passing-state chain hashes when seeding from retained prior authority;
full solver replays require exact complete check hashes and ledger equality.
"""
import argparse,importlib.util,json,sys,time,traceback
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.benchmark_u03_assembly import load,ReadOnlyStore,read
from src.u03_board.assembly import GroupCandidateAssembly
from src.u03_board.dependency import DependencyWidthScene
from src.u03_board.solver import solve
from src.stage_abi.store import canonical,digest


def run(root,output,reference_path,full=False,baseline_results=None):
    spec=importlib.util.spec_from_file_location('u03_reference_checker',reference_path)
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    classes={'reference':reference.IncrementalWidthScene,'dependency':DependencyWidthScene}
    if baseline_results is not None:
        previous=read(baseline_results)
        assert previous['case']==str(root) and previous['reference_source_sha256']==digest(reference_path.read_bytes()),'REFERENCE_CASE_MISMATCH'
    values,candidate=load(root);rows,current,model=values[:3];store=ReadOnlyStore(root/'runtime')
    fixed=[dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('nominal_width_mm',0.)) for s,g in current.items() if s not in model.chains]
    solution=candidate['solution'];ledger=solution['evaluations'];results=[]
    source=read(root/'u03_t04/t04_admit.json')['binding']['source_sha256']
    def checker(mode):
        kwargs=dict(groups=model.assignment,source_binding=source) if mode=='dependency' else {}
        return classes[mode](model.build(dict.fromkeys(model.group_ids,1.))[0],fixed,**kwargs)
    def event(**v):print(json.dumps(v),flush=True)
    if full:
        modes=('dependency','dependency') if baseline_results is not None else ('reference','dependency','dependency','reference')
        for order,mode in enumerate(modes):
            before=time.monotonic();c=checker(mode);setup=time.monotonic()-before
            a=GroupCandidateAssembly(model);hashes=[];t=time.monotonic()
            def evaluate(v):
                q=c.check(a.traces(v),fail_fast=True);h=digest(canonical(q));index=len(hashes)
                assert h==candidate['check_refs'][index]['sha256'],f'CHECK_HASH_MISMATCH:{index}'
                hashes.append(h);return q
            actual=solve(model.group_ids,evaluate)
            assert actual==solution,'SOLVER_LEDGER_MISMATCH'
            scales=actual['selected_scales'];envelope=c.check(model.build(scales)[0],materialize_scene=True);nominal=[]
            for sid in sorted(model.chains):
                r,_,_,core,g,_=model.construct(sid,scales[model.assignment[sid]])
                nominal.append(dict(id=sid,original=core,candidate=g,verified_original_width_mm=r['verified_original_width_mm']))
            nominal_check=c.check(nominal,materialize_scene=True)
            assert envelope==candidate['envelope_check'] and nominal_check==candidate['nominal_check'],'FINAL_CHECK_MISMATCH'
            elapsed=time.monotonic()-t
            row=dict(mode=mode,order=order,seconds=elapsed,checker_setup_seconds=setup,total_with_checker_setup_seconds=setup+elapsed,checks=len(hashes),all_hashes_ledger_and_final_checks_equal=True)
            if mode=='dependency':row['diagnostics']=c.diagnostics()
            results.append(row);event(event='FULL_REPLAY',**row)
    else:
        groups=read(root/'u03_t04/t04_plan.json')['plan']['details']['groups'];largest=max(groups,key=lambda g:len(g['members']))
        start=next(r['index'] for r in ledger if r['changes'].get(largest['group_id'])==1.5)
        for label,first,count in [('prefix',0,32),('largest',start,6),('middle',len(ledger)//2,6)]:
            vector=dict(solution['ledger_initial_scales']);accepted=dict(vector)
            for record in ledger[:first]:
                vector.update(record['changes'])
                if record['passed']:accepted=dict(vector)
            initial=model.build(accepted)[0];trials=[]
            for record in ledger[first:first+count]:
                vector.update(record['changes']);trials.append((dict(vector),record['index']))
            previous=store.get_json(candidate['check_refs'][first],kind='width-check')['previous_passing_state_sha256']
            # Both checker variants receive the same preconstructed native
            # geometry. Report assembly and checking separately as well.
            for scales,_ in trials:model.build(scales)
            modes=('dependency',) if baseline_results is not None else ('reference','dependency')
            for mode in modes:
                before=time.monotonic();c=checker(mode);setup=time.monotonic()-before
                for temperature in ('cold','warm'):
                    # Explicit retained state only; no independent prefix verdict.
                    c.accepted_current=dict(c.original,**{r['id']:r['candidate'] for r in initial}) if first else None
                    c.accepted_results={r['id']:dict(trace_id=r['id'],passed=True,candidate_sha256=c.cached_sha(r['candidate'])) for r in initial} if first else {}
                    c.accepted_hash=previous if first else None
                    a=GroupCandidateAssembly(model);samples=[];t=time.monotonic()
                    for scales,index in trials:
                        before=time.monotonic();traces=a.traces(scales);assembled=time.monotonic()
                        q=c.check(traces,fail_fast=True);finished=time.monotonic();elapsed=finished-before
                        expected=store.get_json(candidate['check_refs'][index],kind='width-check')
                        comparable=lambda q:{k:v for k,v in q.items() if k not in ('previous_passing_state_sha256','passing_state_sha256')}
                        assert comparable(q)==comparable(expected),f'WINDOW_GEOMETRY_REPORT_MISMATCH:{label}:{mode}:{temperature}:{index}'
                        samples.append(dict(index=index,seconds=elapsed,assembly_seconds=assembled-before,check_seconds=finished-assembled,passed=q['passed'],all_geometry_fields_equal=True))
                        event(event='TRIAL',label=label,mode=mode,temperature=temperature,**samples[-1])
                    row=dict(label=label,first=first,mode=mode,temperature=temperature,seconds=time.monotonic()-t,
                        evaluation_seconds=sum(s['seconds'] for s in samples),check_seconds=sum(s['check_seconds'] for s in samples),
                        checker_setup_seconds=setup,trials=samples)
                    if mode=='dependency':
                        row['diagnostics']=c.diagnostics()
                        # Additive inspectable sample; never fed back into native evidence.
                        certificates=[json.loads(p.payload) for p,_ in list(c.routes.entries.values())[:3]]
                        sample=output.with_name(output.stem+'_'+label+'_'+temperature+'_certificates.json')
                        with sample.open('x') as f:json.dump(dict(scope='REPLAY proof examples',certificates=certificates),f,indent=2)
                    results.append(row);event(event='WINDOW',**{k:v for k,v in row.items() if k!='trials'})
    result=dict(scope='Read-only retained REPLAY; no native job/export/acceptance',case=str(root),mode='FULL_SOLVER' if full else 'BOUNDED_WINDOWS',reference_source_sha256=digest(reference_path.read_bytes()),results=results,
        source_files={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted((ROOT/'src/u03_board').glob('*.py'))})
    if baseline_results is not None:result['paired_reference_results']=dict(path=str(baseline_results),sha256=digest(baseline_results.read_bytes()))
    with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--reference-checker',required=True,type=Path);p.add_argument('--full-solver',action='store_true');p.add_argument('--baseline-results',type=Path,help='Recheck optimized runs only, paired with retained reference timing from the identical case/checker');args=p.parse_args()
    assert args.output.resolve().is_relative_to((ROOT/'out/lacie_work').resolve()),'LACIE_OUTPUT_REQUIRED'
    try:run(args.case,args.output,args.reference_checker,args.full_solver,args.baseline_results)
    except BaseException as error:
        failure=dict(error=repr(error),traceback=traceback.format_exc(),scope='Retained diagnostic failed; no native job was resumed',source_files={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in (ROOT/'src/u03_board').glob('*.py')})
        with args.output.with_suffix('.failure.json').open('x') as f:json.dump(failure,f,indent=2)
        raise
