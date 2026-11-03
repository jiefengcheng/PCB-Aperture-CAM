#!/usr/bin/env python3
"""Read-only retained source-union benchmark; no native route or export.

All intermediate geometry fields/gaps and complete solver hashes must match.
Only passing-state chain hashes are excluded for explicitly seeded windows.
"""
import argparse,json,sys,time,traceback,platform
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import shapely
from tools.benchmark_u03_assembly import load,ReadOnlyStore,read
from src.u03_board.assembly import GroupCandidateAssembly
from src.u03_board.dependency import DependencyWidthScene
from src.u03_board.source_union import SourceUnionWidthScene
from src.u03_board.solver import solve
from src.stage_abi.store import canonical,digest
from src.trace_width_clearance import TraceWidthContract


def compare_report(actual,expected,stats,path=''):
    """Strict retained parity, excluding only seeded-window chain authority."""
    if isinstance(actual,dict) and isinstance(expected,dict):
        assert actual.keys()==expected.keys(),('FIELDS_CHANGED',path)
        for k in actual:
            if k not in ('previous_passing_state_sha256','passing_state_sha256'):
                compare_report(actual[k],expected[k],stats,path+'/'+k)
    elif isinstance(actual,list) and isinstance(expected,list):
        assert len(actual)==len(expected),('COVERAGE_CHANGED',path)
        for i,(a,b) in enumerate(zip(actual,expected)):compare_report(a,b,stats,path+'/'+str(i))
    elif actual!=expected:
        raise AssertionError(('WITNESS_CHANGED',path,actual,expected))


def run(root,output,full=False,baseline_results=None):
    if baseline_results is not None:
        assert not full,'PAIRED_BASELINE_IS_FOR_WINDOWS_ONLY'
        previous=read(baseline_results)
        assert Path(previous['case']).resolve()==root.resolve(),'BASELINE_CASE_CHANGED'
        assert previous['source_files']['src/u03_board/dependency.py']==digest((ROOT/'src/u03_board/dependency.py').read_bytes()),'BASELINE_DEPENDENCY_CHANGED'
        assert all(t['all_geometry_fields_equal'] for r in previous['results'] for t in r['trials']),'BASELINE_PARITY_MISSING'
    values,candidate=load(root);rows,current,model=values[:3];store=ReadOnlyStore(root/'runtime')
    fixed=[dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('nominal_width_mm',0.)) for s,g in current.items() if s not in model.chains]
    ledger=candidate['solution']['evaluations'];source=read(root/'u03_t04/t04_admit.json')['binding']['source_sha256'];results=[]
    classes={'reference':DependencyWidthScene,'source_union':SourceUnionWidthScene}
    def setup(mode):
        start=time.monotonic();c=classes[mode](model.build(dict.fromkeys(model.group_ids,1.))[0],fixed,groups=model.assignment,source_binding=source);elapsed=time.monotonic()-start
        original=c.other_original_union;timing=dict(calls=0,seconds=0.)
        def union(sid,g):
            t=time.monotonic();v=original(sid,g);timing['seconds']+=time.monotonic()-t;timing['calls']+=1;return v
        c.other_original_union=union
        return c,elapsed,timing
    def stats():return dict(different_distance_values=0,max_distance_delta_mm=0.)
    def event(**v):print(json.dumps(v),flush=True)
    if full:
        expected=[store.get_json(r,kind='width-check') for r in candidate['check_refs']]
        for mode in ('reference','source_union','source_union','reference'):
            model._construct.cache_clear();c,init,unions=setup(mode);a=GroupCandidateAssembly(model);parity=stats();reports=[];comparison=0.;search=0.
            def evaluate(v):
                nonlocal comparison,search
                start=time.monotonic();q=c.check(a.traces(v),fail_fast=True);search+=time.monotonic()-start
                start=time.monotonic();i=len(reports);compare_report(q,expected[i],parity)
                assert digest(canonical(q))==candidate['check_refs'][i]['sha256'],'COMPLETE_HASH_CHANGED'
                reports.append(digest(canonical(q)));comparison+=time.monotonic()-start;return q
            start=time.monotonic();actual=solve(model.group_ids,evaluate);solve_elapsed=time.monotonic()-start-comparison
            old=candidate['solution']
            for k in old:
                if k!='evaluations':assert actual[k]==old[k],('SOLVER_RESULT_CHANGED',k)
            for i,(ar,er) in enumerate(zip(actual['evaluations'],old['evaluations'],strict=True)):
                assert {k:v for k,v in ar.items() if k!='report_sha256'}=={k:v for k,v in er.items() if k!='report_sha256'},('SOLVER_LEDGER_CHANGED',i)
                assert ar['report_sha256']==reports[i],'NEW_REPORT_HASH_NOT_BOUND'
            assert actual==old,'COMPLETE_SOLVER_LEDGER_CHANGED'
            t=time.monotonic();scales=actual['selected_scales'];envelope=c.check(model.build(scales)[0],materialize_scene=True);nominal=[]
            for sid in sorted(model.chains):
                r,_,_,core,g,_=model.construct(sid,scales[model.assignment[sid]])
                nominal.append(dict(id=sid,original=core,candidate=g,verified_original_width_mm=r['verified_original_width_mm']))
            nominal_check=c.check(nominal,materialize_scene=True)
            assert envelope==candidate['envelope_check'] and nominal_check==candidate['nominal_check'],'FINAL_CHECK_CHANGED'
            final_seconds=time.monotonic()-t
            row=dict(mode=mode,checker_setup_seconds=init,solver_seconds=solve_elapsed,search_evaluation_seconds=search,final_checks_seconds=final_seconds,
                total_with_setup_seconds=init+solve_elapsed+final_seconds,parity_seconds_excluded=comparison,checks=len(reports),parity=parity,
                exact_solver_decisions_and_factors=True,exact_native_final_nominal_envelope=True,report_digests_self_consistent=True,
                source_union_operations=unions,diagnostics=c.diagnostics())
            results.append(row);event(event='FULL_REPLAY',**row)
    else:
        groups=read(root/'u03_t04/t04_plan.json')['plan']['details']['groups'];largest=max(groups,key=lambda g:len(g['members']))
        first_largest=next(r['index'] for r in ledger if r['changes'].get(largest['group_id'])==1.5)
        for w,(label,first,count) in enumerate([('prefix',0,32),('largest',first_largest,6),('middle',len(ledger)//2,6)]):
            vector=dict(candidate['solution']['ledger_initial_scales']);accepted=dict(vector)
            for r in ledger[:first]:
                vector.update(r['changes'])
                if r['passed']:accepted=dict(vector)
            initial=model.build(accepted)[0];trials=[]
            for r in ledger[first:first+count]:
                vector.update(r['changes']);trials.append((dict(vector),r['index']))
            for scales,_ in trials:model.build(scales)
            previous=store.get_json(candidate['check_refs'][first],kind='width-check')['previous_passing_state_sha256']
            modes=('source_union',) if baseline_results is not None else (('reference','source_union') if w%2==0 else ('source_union','reference'))
            for mode in modes:
                c,init,unions=setup(mode)
                for temperature in ('cold','warm'):
                    c.accepted_current=dict(c.original,**{r['id']:r['candidate'] for r in initial}) if first else None
                    c.accepted_results={r['id']:dict(trace_id=r['id'],passed=True,candidate_sha256=c.cached_sha(r['candidate'])) for r in initial} if first else {}
                    c.accepted_hash=previous if first else None
                    a=GroupCandidateAssembly(model);samples=[];before_union=dict(unions);parity=stats()
                    for scales,index in trials:
                        start=time.monotonic();traces=a.traces(scales);assembled=time.monotonic();q=c.check(traces,fail_fast=True);finished=time.monotonic()
                        expected=store.get_json(candidate['check_refs'][index],kind='width-check');compare_report(q,expected,parity)
                        # Reference still matches all geometry fields bit for bit.
                        if mode=='reference':
                            omit=lambda r:{k:v for k,v in r.items() if k not in ('previous_passing_state_sha256','passing_state_sha256')}
                            assert omit(q)==omit(expected),'REFERENCE_GEOMETRY_CHANGED'
                        samples.append(dict(index=index,assembly_seconds=assembled-start,check_seconds=finished-assembled,passed=q['passed']))
                        event(event='TRIAL',window=label,mode=mode,cache=temperature,**samples[-1])
                    drain_start=time.monotonic()
                    if mode=='source_union':c.drain()
                    drain_seconds=time.monotonic()-drain_start
                    row=dict(window=label,mode=mode,cache=temperature,trials=samples,checker_setup_seconds=init,check_seconds=sum(s['check_seconds'] for s in samples)+drain_seconds,drain_seconds=drain_seconds,assembly_seconds=sum(s['assembly_seconds'] for s in samples),parity=parity,
                        source_union_operations={k:unions[k]-before_union[k] for k in unions},diagnostics=c.diagnostics(),all_other_geometry_fields_exact=True)
                    results.append(row);event(event='WINDOW',**{k:v for k,v in row.items() if k!='trials'})
                if mode=='source_union':c.close()
    result=dict(scope='REPLAY retained cases; no native job/export/acceptance',case=str(root),mode='FULL_SOLVER_ABBA' if full else 'BOUNDED_WINDOWS',results=results,
        reference='DependencyWidthScene, previous slice; unchanged source/predicate',optimized='SourceUnionWidthScene; bounded parallel execution of identical ordered unions, search only',
        comparison='All geometry fields/gaps, complete C03 check hashes/solver ledger and full final payloads exact. Only explicitly seeded-window passing-chain digests excluded.',
        timing='Parity comparison and retained report I/O excluded; setup separately recorded. Windows preconstruct identical native geometry; cold/warm are diagnostic cache histories, not whole-run distribution.',
        versions=dict(python=platform.python_version(),shapely=shapely.__version__,geos=shapely.geos_version_string),
        source_files={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted((ROOT/'src/u03_board').glob('*.py'))},benchmark_sha256=digest(Path(__file__).read_bytes()))
    if baseline_results is not None:
        result['paired_reference_results']=dict(path=str(baseline_results.resolve()),sha256=digest(baseline_results.read_bytes()),
            scope='Earlier identical retained windows on previous dependency checker; reference timings reused, not rerun in this measurement')
    with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--full-solver',action='store_true');p.add_argument('--baseline-results',type=Path,help='Pair optimized window reruns with earlier identical-case dependency timings; explicitly hash-link the earlier file');args=p.parse_args()
    assert args.output.resolve().is_relative_to((ROOT/'out/lacie_work').resolve()),'LACIE_OUTPUT_REQUIRED'
    try:run(args.case,args.output,args.full_solver,args.baseline_results)
    except BaseException as e:
        with args.output.with_suffix('.failure.json').open('x') as f:json.dump(dict(error=repr(e),traceback=traceback.format_exc(),scope='Retained diagnostic; no managed route resumed'),f,indent=2)
        raise
