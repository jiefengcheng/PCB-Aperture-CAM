#!/usr/bin/env python3
"""Retained whole-board steady-state kernel experiment, explicitly not run timing.

Prime the actual first twelve recorded trials. Keep the actually checked accepted
state after trial seven; replay the actual rejection/bracket trials eight..eleven
from that authority. Every repetition must reproduce complete retained reports
and hashes. This isolates local updates with hot caches; cold priming is separate.
"""
import sys,types,importlib,json,time,argparse,platform
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
import shapely
from tools.benchmark_u03_assembly import load,ReadOnlyStore,read
from src.u03_board.assembly import GroupCandidateAssembly
from src.u03_board.separators import SeparatorWidthScene
from src.stage_abi.store import canonical,digest


def run(root,reference,output,cycles):
    package=types.ModuleType('u03_warm_reference');package.__path__=[str(reference)];sys.modules[package.__name__]=package
    old=importlib.import_module('u03_warm_reference.source_union').SourceUnionWidthScene
    old_assembly=importlib.import_module('u03_warm_reference.assembly').GroupCandidateAssembly
    values,candidate=load(root);rows,current,model,unused=values[:4];unused.close();store=ReadOnlyStore(root/'runtime')
    fixed=[dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('nominal_width_mm',0.)) for s,g in current.items() if s not in model.chains]
    vector=dict(candidate['solution']['ledger_initial_scales']);vectors=[]
    for r in candidate['solution']['evaluations'][:12]:vector.update(r['changes']);vectors.append(dict(vector))
    expected=[store.get_json(r,kind='width-check') for r in candidate['check_refs'][:12]]
    for v in vectors:model.build(v)
    source=read(root/'u03_t04/t04_admit.json')['binding']['source_sha256'];results=[]
    for order,mode in enumerate(('reference','separator','separator','reference')):
        t=time.monotonic();cls=old if mode=='reference' else SeparatorWidthScene
        c=cls(model.build(dict.fromkeys(model.group_ids,1.))[0],fixed,groups=model.assignment,source_binding=source)
        a=(old_assembly if mode=='reference' else GroupCandidateAssembly)(model);setup=time.monotonic()-t;anchor=None
        try:
            before=time.monotonic()
            for index,v in enumerate(vectors):
                q=c.check(a.traces(v),fail_fast=True);assert q==expected[index] and digest(canonical(q))==candidate['check_refs'][index]['sha256']
                if index==7:
                    assert q['passed'];anchor=(c.accepted_current,c.accepted_results,c.accepted_hash)
            c.drain();priming=time.monotonic()-before;samples=[];parity=0.
            for cycle in range(cycles):
                c.accepted_current,c.accepted_results,c.accepted_hash=anchor
                for index in range(8,12):
                    t=time.monotonic();traces=a.traces(vectors[index]);assembled=time.monotonic();q=c.check(traces,fail_fast=True);finished=time.monotonic()
                    assert q==expected[index] and digest(canonical(q))==candidate['check_refs'][index]['sha256'],f'WARM_REPORT_CHANGED:{mode}:{cycle}:{index}'
                    parity+=time.monotonic()-finished;samples.append(dict(assembly_seconds=assembled-t,checking_seconds=finished-assembled))
            t=time.monotonic();c.close();drain=time.monotonic()-t
            r=dict(mode=mode,order=order,cycles=cycles,evaluations=len(samples),setup_seconds=setup,priming_seconds=priming,
                assembly_seconds=sum(x['assembly_seconds'] for x in samples),checking_seconds=sum(x['checking_seconds'] for x in samples),drain_seconds=drain,
                evaluation_seconds=sum(x['assembly_seconds']+x['checking_seconds'] for x in samples)+drain,parity_seconds_excluded=parity,
                complete_retained_reports_and_hashes_equal=True,diagnostics=c.diagnostics())
            results.append(r);print(json.dumps(dict(stage='warm',**r)),flush=True)
        finally:c.close()
    result=dict(scope='REPLAY steady-state kernel microbenchmark; repeated actual trials, not whole-board search or command timing',case=str(root),recorded_priming_trials=[0,11],repeated_actual_trials=[8,11],anchor_recorded_pass=7,results=results,
        source_files={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted((ROOT/'src/u03_board').glob('*.py'))},benchmark_sha256=digest(Path(__file__).read_bytes()),
        versions=dict(python=platform.python_version(),shapely=shapely.__version__,geos=shapely.geos_version_string))
    with output.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--cycles',type=int,default=32);a=p.parse_args()
    from tools.pcb_workspace import configure
    work=configure();assert a.output.resolve().is_relative_to(work.resolve()) and not a.output.exists() and a.cycles>0
    run(a.case.resolve(),a.reference.resolve(),a.output.resolve(),a.cycles)
