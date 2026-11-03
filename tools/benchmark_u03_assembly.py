#!/usr/bin/env python3
"""Read-only retained-case assembly benchmark; no native job or export is run.

The assembly microbenchmark precomputes actual native geometry at every sampled
factor, then supplies identical cache hits to both assemblers. It excludes
geometry construction, checks and I/O from assembly timings. Optional solver
replay executes every existing check on C03, without writing retained stores.
"""
import argparse,hashlib,json,statistics,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import to_wkb
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.u03_board.width import WholeBoardWidthAdapter
from src.u03_board.assembly import GroupCandidateAssembly
from src.u03_board.solver import solve
from src.u03_board.checker import IncrementalWidthScene


def read(p):return json.loads(p.read_bytes())
class ReadOnlyStore(ArtifactStore):
    def __init__(self,root):self.root=root
    def put(self,*a,**kw):raise AssertionError('RETAINED_STORE_WRITE_FORBIDDEN')
    def _lock(self,*a,**kw):raise AssertionError('RETAINED_STORE_WRITE_FORBIDDEN')


def load(root):
    store=ReadOnlyStore(root/'runtime');a=read(root/'u03_t04/t04_admit.json');p=read(root/'u03_t04/t04_plan.json')
    profile=next(iter(a['registry']['profiles'].values()))
    scene=store.get_json(a['imported']['scene_ref'],kind='scene');policy=store.get_json(profile['policy_ref'],kind='policy')
    model=WholeBoardWidthAdapter()._model(store,scene,policy,p['plan']['details'])
    candidate=read(root/'u03_t04/t04_run.json')['result']['candidate']
    return model,candidate


def sig(rows):return digest(b''.join(r['id'].encode()+to_wkb(r['original'])+to_wkb(r['candidate'])+canonical(r['verified_original_width_mm']) for r in rows))


def benchmark(root,out,replay=False):
    started=time.monotonic();values,candidate=load(root);rows,current,model=values[:3]
    solution=candidate['solution'];vector=dict(solution['ledger_initial_scales']);vectors=[]
    for row in solution['evaluations'][:256]:
        vector.update(row['changes']);vectors.append(dict(vector))
    # Exact actual geometry for all sampled (route,factor) cache keys.
    original=model.construct;memo={}
    def cached(sid,factor):
        key=(sid,factor)
        if key not in memo:memo[key]=original(sid,factor)
        return memo[key]
    model.construct=cached
    for v in vectors:model.build(v)
    model.construct=lambda sid,factor:memo[(sid,factor)]
    assembly=GroupCandidateAssembly(model)
    for v in vectors:
        assert sig(model.build(v)[0])==sig(assembly.traces(v)), 'ASSEMBLY_WKB_MISMATCH'
    samples={'baseline':[],'incremental':[]}
    for repetition in range(4):
        for mode in (['baseline','incremental'] if repetition%2==0 else ['incremental','baseline']):
            a=GroupCandidateAssembly(model);start=time.perf_counter()
            for v in vectors:
                traces=model.build(v)[0] if mode=='baseline' else a.traces(v)
                assert len(traces)==len(model.chains)
            samples[mode].append(time.perf_counter()-start)
    result=dict(scope='REPLAY retained geometry; isolated warm-cache assembly benchmark, not command runtime',root=str(root),groups=len(model.group_ids),routes=len(model.chains),trial_vectors=len(vectors),geometry_keys=len(memo),samples_seconds=samples,baseline_median=statistics.median(samples['baseline']),incremental_median=statistics.median(samples['incremental']),route_updates=assembly.updated_routes,baseline_route_visits=len(vectors)*len(model.chains),all_sampled_trace_WKB_equal=True)
    result['assembly_speedup']=result['baseline_median']/result['incremental_median']
    model.construct=original
    if replay:
        fixed=[dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('nominal_width_mm',0.)) for s,g in current.items() if s not in model.chains]
        replay_results={};expected=None
        for mode in ('baseline','incremental'):
            baseline=model.build(dict.fromkeys(model.group_ids,1.))[0];checker=IncrementalWidthScene(baseline,fixed);assembly=GroupCandidateAssembly(model);reports=[];start=time.monotonic()
            def evaluate(v):
                q=checker.check(model.build(v)[0] if mode=='baseline' else assembly.traces(v),fail_fast=True)
                reports.append(digest(canonical(q)));return q
            actual=solve(model.group_ids,evaluate)
            assert actual==solution,'RETAINED_SOLVER_LEDGER_MISMATCH'
            assert reports==[r['sha256'] for r in candidate['check_refs']],'RETAINED_CHECK_REPORT_MISMATCH'
            # Existing full checker on final envelope and nominal, unchanged.
            scales=actual['selected_scales'];traces=model.build(scales)[0]
            envelope=checker.check(traces,materialize_scene=True)
            nominal=[]
            for sid in sorted(model.chains):
                r,_,_,core,g,_=model.construct(sid,scales[model.assignment[sid]])
                nominal.append(dict(id=sid,original=core,candidate=g,verified_original_width_mm=r['verified_original_width_mm']))
            nominal_check=checker.check(nominal,materialize_scene=True)
            assert envelope==candidate['envelope_check'] and nominal_check==candidate['nominal_check'],'FINAL_CHECK_MISMATCH'
            replay_results[mode]=dict(seconds=time.monotonic()-start,evaluations=len(reports),all_check_hashes_and_solver_ledger_equal=True,full_nominal_and_envelope_equal=True)
        result['solver_replay']=replay_results
    result['elapsed_seconds']=time.monotonic()-started
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--solver-replay',action='store_true');a=p.parse_args()
    work=(ROOT/'out/lacie_work').resolve();assert a.output.resolve().is_relative_to(work),'LACIE_OUTPUT_REQUIRED'
    benchmark(a.case,a.output,a.solver_replay)
