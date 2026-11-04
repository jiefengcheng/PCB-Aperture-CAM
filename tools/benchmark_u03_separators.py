#!/usr/bin/env python3
"""Strict retained-evidence replay: no managed jobs, native operations or exports.

Reference code is frozen separately from Git before edits. Seeded windows compare
all geometry/report fields but not chain hashes. Full solver replay requires the
entire retained ledger, report digests and final nominal/envelope reports exactly.
"""
import argparse,importlib,json,sys,time,types,hashlib,statistics,traceback,platform
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import shapely
from src.stage_abi.store import canonical,digest
from src.u03_board.separators import SeparatorWidthScene
from src.u03_board.assembly import GroupCandidateAssembly
from src.u03_board.solver import solve
from tools.benchmark_u03_assembly import load,ReadOnlyStore,read


def run(root,output,reference,full=False):
    start=time.monotonic();package=types.ModuleType('u03_frozen_reference');package.__path__=[str(reference)];sys.modules[package.__name__]=package
    old=importlib.import_module('u03_frozen_reference.source_union').SourceUnionWidthScene
    old_assembly=importlib.import_module('u03_frozen_reference.assembly').GroupCandidateAssembly
    load_start=time.monotonic();values,candidate=load(root);loading=time.monotonic()-load_start
    rows,current,model,unused=values[:4];unused.close();store=ReadOnlyStore(root/'runtime')
    fixed=[dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('nominal_width_mm',0.)) for s,g in current.items() if s not in model.chains]
    source=read(root/'u03_t04/t04_admit.json')['binding']['source_sha256'];solution=candidate['solution'];ledger=solution['evaluations'];results=[]
    def event(**x):print(json.dumps(x,sort_keys=True),flush=True)
    def setup(mode):
        before=time.monotonic();base=model.build(dict.fromkeys(model.group_ids,1.))[0]
        cls=old if mode=='reference' else SeparatorWidthScene;c=cls(base,fixed,groups=model.assignment,source_binding=source)
        return c,time.monotonic()-before,(old_assembly if mode=='reference' else GroupCandidateAssembly)(model)
    def final(c):
        scales=solution['selected_scales'];envelope=c.check(model.build(scales)[0],materialize_scene=True);nominal=[]
        for sid in sorted(model.chains):
            r,_,_,core,g,_=model.construct(sid,scales[model.assignment[sid]])
            nominal.append(dict(id=sid,original=core,candidate=g,verified_original_width_mm=r['verified_original_width_mm']))
        check=c.check(nominal,materialize_scene=True)
        assert envelope==candidate['envelope_check'] and check==candidate['nominal_check'],'FULL_FINAL_CHECK_CHANGED'
    if full:
        expected=[store.get_json(ref,kind='width-check') for ref in candidate['check_refs']]
        for order,mode in enumerate(('reference','separator','separator','reference')):
            model._construct.cache_clear();c,init,a=setup(mode);count=0;parity_seconds=0.;evaluation_seconds=0.;assembly_seconds=0.;checking_seconds=0.;last_notice=time.monotonic()
            def evaluate(v):
                nonlocal count,parity_seconds,evaluation_seconds,assembly_seconds,checking_seconds,last_notice
                t=time.monotonic();traces=a.traces(v);assembled=time.monotonic();q=c.check(traces,fail_fast=True);finished=time.monotonic()
                assembly_seconds+=assembled-t;checking_seconds+=finished-assembled;evaluation_seconds+=finished-t
                assert q==expected[count],f'RETAINED_REPORT_CHANGED:{count}'
                h=digest(canonical(q));assert h==candidate['check_refs'][count]['sha256'],f'RETAINED_HASH_CHANGED:{count}'
                count+=1;parity_seconds+=time.monotonic()-finished
                if time.monotonic()-last_notice>20:event(stage='progress',mode=mode,evaluations=count);last_notice=time.monotonic()
                return q
            try:
                t=time.monotonic();actual=solve(model.group_ids,evaluate);wall=time.monotonic()-t
                assert actual==solution,'SOLVER_ORDER_FACTORS_OR_LEDGER_CHANGED'
                t=time.monotonic();final(c);closure=time.monotonic()-t
                r=dict(mode=mode,order=order,evaluations=count,setup_seconds=init,solver_seconds=wall-parity_seconds,solver_wall_including_parity=wall,parity_seconds=parity_seconds,
                    assembly_seconds=assembly_seconds,checking_seconds=checking_seconds,evaluation_seconds=evaluation_seconds,final_checks_seconds=closure,
                    total_seconds_excluding_parity=init+wall-parity_seconds+closure,all_report_hashes_and_solver_ledger_exact=True,final_nominal_and_envelope_exact=True)
                if mode=='separator':r['diagnostics']=c.diagnostics()
                results.append(r);event(stage='full_replay',**r)
            finally:c.close()
    else:
        groups=read(root/'u03_t04/t04_plan.json')['plan']['details']['groups'];largest=max(groups,key=lambda g:len(g['members']))
        first_largest=next(r['index'] for r in ledger if r['changes'].get(largest['group_id'])==1.5)
        # The two balanced-root boundary variables from the retained study are
        # benchmark selection only. Runtime partition authority is rebuilt fresh.
        study=ROOT/'out/lacie_work/evidence/u03_dependency_decomposition_20261104_final/TIGHT_DECOMPOSITION.json'
        graph=ROOT/'out/lacie_work/evidence/u03_dependency_graph_20261104_final/GRAPH.json'
        separators=read(study)['components'][0]['separator']['vertices'];names=[read(graph)['groups'][i]['group_id'] for i in separators]
        first_boundary=next(r['index'] for r in ledger if any(g in r['changes'] and r['changes'][g]==1.5 for g in names))
        windows=[('prefix',0,12),('largest_group',first_largest,4),('middle',len(ledger)//2,4),('separator_boundary',first_boundary,4),('upper_proofs',solution['final_check_index']+1,4)]
        for label,first,count in windows:
            v=dict(solution['ledger_initial_scales']);accepted=dict(v)
            for record in ledger[:first]:
                v.update(record['changes'])
                if record['passed']:accepted=dict(v)
            initial=model.build(accepted)[0];trials=[]
            for record in ledger[first:first+count]:v.update(record['changes']);trials.append((dict(v),record['index']))
            assert trials
            expected=[store.get_json(candidate['check_refs'][i],kind='width-check') for _,i in trials]
            previous=expected[0]['previous_passing_state_sha256']
            # Same warmed geometry construction, independent cold checker caches.
            for vector,_ in trials:model.build(vector)
            for order,mode in enumerate(('reference','separator','separator','reference')):
                c,init,a=setup(mode);samples=[]
                try:
                    if first:
                        c.accepted_current=dict(c.original,**{r['id']:r['candidate'] for r in initial})
                        c.accepted_results={r['id']:dict(trace_id=r['id'],passed=True,candidate_sha256=c.cached_sha(r['candidate'])) for r in initial};c.accepted_hash=previous
                    for (vector,index),retained in zip(trials,expected,strict=True):
                        t=time.monotonic();traces=a.traces(vector);assembled=time.monotonic();q=c.check(traces,fail_fast=True);finished=time.monotonic()
                        omit=lambda x:{k:v for k,v in x.items() if k not in ('previous_passing_state_sha256','passing_state_sha256')}
                        assert omit(q)==omit(retained),f'WINDOW_REPORT_CHANGED:{label}:{index}'
                        samples.append(dict(index=index,assembly_seconds=assembled-t,check_seconds=finished-assembled,passed=q['passed']))
                    t=time.monotonic();c.close();drain=time.monotonic()-t
                    r=dict(window=label,first=first,mode=mode,order=order,setup_seconds=init,trials=samples,assembly_seconds=sum(x['assembly_seconds'] for x in samples),check_seconds=sum(x['check_seconds'] for x in samples),drain_seconds=drain,all_geometry_report_fields_exact=True)
                    r['evaluation_seconds']=r['assembly_seconds']+r['check_seconds']+drain;r['total_with_setup_seconds']=r['evaluation_seconds']+init
                    if mode=='separator':r['diagnostics']=c.diagnostics()
                    results.append(r);event(stage='window',**r)
                finally:c.close()
    result=dict(mode='FULL_RETAINED_SOLVER_ABBA' if full else 'BOUNDED_RETAINED_WINDOWS_ABBA',scope='REPLAY; zero U03/native jobs, exports or acceptance changes',case=str(root),loading_seconds=loading,elapsed_seconds=time.monotonic()-start,results=results,
        reference_files={p.name:digest(p.read_bytes()) for p in reference.glob('*.py')},source_files={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted((ROOT/'src/u03_board').glob('*.py'))},
        versions=dict(python=platform.python_version(),shapely=shapely.__version__,geos=shapely.geos_version_string),timing_limits='Windows prewarm identical geometry; caches are cold per mode. Setup and final worker drainage are included separately. Parity/report I/O excluded from evaluation timing, and concurrent union work can overlap those intervals; bounded timing is not whole-command speedup.')
    with output.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    event(stage='complete',output=str(output),elapsed_seconds=result['elapsed_seconds'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--full-solver',action='store_true');a=p.parse_args()
    from tools.pcb_workspace import configure
    work=configure();assert a.output.resolve().is_relative_to(work.resolve()) and not a.output.exists(),'FRESH_LACIE_OUTPUT_REQUIRED'
    try:run(a.case.resolve(),a.output.resolve(),a.reference.resolve(),a.full_solver)
    except BaseException as error:
        with a.output.with_suffix('.failure.json').open('x') as f:json.dump(dict(error=repr(error),traceback=traceback.format_exc(),scope='Retained benchmark failed; no U03 job ran'),f,indent=2)
        raise
