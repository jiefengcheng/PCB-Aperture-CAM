#!/usr/bin/env python3
"""Read-only retained U03 dependency study. Never starts/resumes any U03 job."""
import argparse,hashlib,json,sys,time,subprocess,html
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from shapely import from_wkb
import shapely
from src.u03_analysis.dependency import dependencies
from src.u03_analysis.graph import analyze


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--job',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    from tools.pcb_workspace import configure
    work=configure();output=args.output.resolve()
    if not output.is_relative_to(work) or output.exists():raise ValueError('FRESH_LACIE_OUTPUT_REQUIRED')
    output.mkdir(parents=True);start=time.monotonic();root=args.job.absolute()/'native';used={}
    def raw(p):
        p=Path(p);data=p.read_bytes();h=hashlib.sha256(data).hexdigest()
        if str(p) in used and used[str(p)]!=h:raise ValueError('INPUT_CHANGED:'+str(p))
        used[str(p)]=h;return data
    def read(p):return json.loads(raw(p))
    def artifact(ref):
        data=raw(root/'runtime/artifacts'/ref['artifact_id'])
        if hashlib.sha256(data).hexdigest()!=ref['sha256'] or ref['artifact_id'].split(':',1)[1]!=ref['sha256']:raise ValueError('ARTIFACT_CHANGED')
        return data
    def obj(ref):return json.loads(artifact(ref))
    def save(n,x):
        with (output/n).open('x') as stream:json.dump(x,stream,indent=2,sort_keys=True);stream.write('\n')
    def progress(stage,**kw):print(json.dumps(dict(stage=stage,elapsed_seconds=round(time.monotonic()-start,2),**kw)),flush=True)
    receipt=read(root/'U03_RECEIPT.json');cp=Path(receipt['checkpoint']);data=raw(cp)
    assert receipt['status']=='PASS_FRESH_U03_EXPORT' and hashlib.sha256(data).hexdigest()==receipt['checkpoint_sha256']
    checkpoint=json.loads(data)
    for name,h in checkpoint['files'].items():assert hashlib.sha256(raw(root/name)).hexdigest()==h,name
    machine=read(root/'MACHINE_RECEIPT.json');assert len(machine['proofs'])==len(checkpoint['operations'])==33
    for name,h in machine['proofs'].items():
        data=raw(root/name);assert hashlib.sha256(data).hexdigest()==h;p=json.loads(data);assert p['status']=='PASS' and all(c['passed'] for c in p['checks'])
    # This analytic envelope is pinned to the exact retained constructor/predicate.
    for name in ('src/source_offset_width.py','src/prepared_width_scene.py','src/trace_width_clearance.py','src/native_inventory.py'):
        assert raw(ROOT/name)==raw(root/'u03_code_snapshot'/name),'BOUND_FAMILY_CHANGED:'+name
    admit=read(root/'u03_t04/t04_admit.json');inspect=read(root/'u03_t04/t04_inspect.json');report=obj(inspect['report_ref']);scene=obj(admit['imported']['scene_ref']);assert scene['source_sha256']==inspect['binding']['source_sha256']==admit['binding']['source_sha256']
    profile=next(iter(admit['registry']['profiles'].values()));policy=obj(profile['policy_ref']);contract=policy['parameters']['surface_contract']
    from src.native_inventory import ERROR_MM
    from src.source_offset_width import FAMILY
    assert policy['parameters']['ceiling']==1.5 and policy['parameters']['family']==FAMILY,'UNSUPPORTED_WIDTH_DOMAIN'
    groups=sorted(report['groups'],key=lambda x:x['group_id']);membership={}
    for i,g in enumerate(groups):
        for sid in g['members']:
            if sid in membership:raise ValueError('SOURCE_PARTITION_CHANGED')
            membership[sid]=i
    assert set(membership)==set(admit['imported']['target_ids']);assert len(groups)==inspect['facts']['groups']==2931
    rows=[];fixed=0;all_objects={}
    for row in scene['objects']:
        sid=row['source_id'];data=artifact(row['geometry_ref']);geometry=from_wkb(data);assert geometry.is_valid and not geometry.is_empty
        all_objects[sid]=row
        if sid in membership:
            assert row['geometry_ref']==row['original_ref'];native=obj(row['metadata']['native_route_ref']);assert native['chain']['source_ids']==row['metadata']['native_source_ids'] or set(native['chain']['source_ids'])==set(row['metadata']['native_source_ids'])
            rows.append(dict(id=sid,group=membership[sid],core=geometry,width=row['metadata']['nominal_width_mm']))
        else:fixed+=1
    assert len(rows)==3123 and len(rows)+fixed==admit['imported']['scene_objects']
    progress('retained_evidence_verified',groups=len(groups),routes=len(rows),fixed_objects=fixed)
    graph=dependencies(rows,envelope_margin_mm=ERROR_MM,guard_mm=contract['construction_gap_mm']+contract['comparison_epsilon_mm'])
    save('GRAPH.json',dict(schema='u03-conservative-width-dependency/1',groups=groups,rows=[dict(id=r['id'],group=r['group'],width_mm=r['width'],original_core_bounds_mm=list(r['core'].bounds),max_offset_envelope_radius_mm=pad) for r,pad in zip(rows,graph['pads_mm'])],broad_edges=[[g,h] for g,n in graph['broad'].items() for h in sorted(n) if g<h],edges=[[g,h] for g,n in graph['tight'].items() for h in sorted(n) if g<h],witnesses=graph['witnesses'],candidate_route_pairs=graph['candidate_route_pairs'],retained_route_pairs=graph['retained_route_pairs']))
    progress('graph_built',broad_edges=sum(map(len,graph['broad'].values()))//2,refined_edges=sum(map(len,graph['tight'].values()))//2)
    measurements={}
    for label in ('broad','tight'):
        measurements[label]=analyze(graph[label]);save(label.upper()+'_MEASUREMENTS.json',measurements[label]);progress(label+'_measured',components=measurements[label]['component_count'],largest=measurements[label]['component_sizes'][0],lower=max(c['treewidth_lower'] for c in measurements[label]['components']),upper=max(c['treewidth_upper'] for c in measurements[label]['components']))
    # Check every retained failed variable-variable clearance witness against bound.
    run=read(root/'u03_t04/t04_run.json');candidate=run['result']['candidate'];count=0;cross=0;missed=[];observed=set()
    for ref in candidate['check_refs']:
        q=obj(ref);count+=1
        for failure in q.get('failures',[]):
            a=failure.get('trace_id');b=failure.get('neighbor_id')
            if a in membership and b in membership and membership[a]!=membership[b]:
                g,h=sorted((membership[a],membership[b]));cross+=1;observed.add((g,h))
                if h not in graph['tight'][g]:missed.append(failure)
    assert not missed,missed
    progress('retained_rejection_witnesses_checked',evaluations=count,cross_group_failures=cross,unique_edges=len(observed))
    # Re-read all actual analysis operands; no mutation of old job permitted.
    for name,h in list(used.items()):assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,'INPUT_CHANGED:'+name
    summary=dict(schema='u03-dependency-study/1',mode='RETAINED_EVIDENCE_ANALYSIS_NOT_FRESH_QUALIFICATION',job=str(args.job.absolute()),source_sha256=scene['source_sha256'],retained_operations=33,u03_operations_executed=0,source_routes=len(rows),variable_groups=len(groups),fixed_scene_objects=fixed,contract=contract,envelope_margin_mm=ERROR_MM,numerical_reserve_mm=graph['numerical_reserve_mm'],bound='Edge retained when original core distance <= .25*width_i + .25*width_j + 2*ERROR_MM + construction_gap + comparison_epsilon + analysis numerical reserve; AABB graph is unpruned broadphase superset',factorization='Original masks/ports/predecessor are immutable. Unary core/width/fixed-obstacle predicates and pairwise moving-route clearance predicates; groups share a scalar. Shared fixed obstacles do not introduce variable-variable edges.',limitations=['Conservative supergraph, not minimal semantic interaction graph','Separator is a validated BFS-layer heuristic, not a minimum separator','Treewidth lower uses minor contractions; upper uses verified elimination tree decomposition; exact treewidth generally not established','Structural DP measurements do not supply a finite-state width reformulation or preserve the sequential solver automatically','Dense conservative edges can be harmless due to fixed original contact ports/visibility; absence of a useful separator here does not prove absence in a tighter graph'],rejection_coverage=dict(evaluations=count,cross_group_failures=cross,unique_edges=len(observed),missing=missed),inputs_verified=len(used),input_files=used,implementation_files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__).resolve(),ROOT/'src/u03_analysis/graph.py',ROOT/'src/u03_analysis/dependency.py']},versions=dict(python=sys.version,shapely=shapely.__version__,geos=shapely.geos_version_string),git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),elapsed_seconds=time.monotonic()-start)
    for label,m in measurements.items():
        summary[label]={k:v for k,v in m.items() if k not in ('components','blocks')}
        summary[label]['component_treewidth_bounds']=[dict(size=c['size'],lower=c['treewidth_lower'],upper=c['treewidth_upper'],separator=c['separator']['size'],remaining=c['separator']['remaining_component_sizes']) for c in m['components']]
    save('SUMMARY.json',summary)
    # Small standalone visual report: graph statistics, no PCB rendering.
    lines=['<!doctype html><meta charset="utf-8"><title>U03 dependency graph study</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;color:#173044}table{border-collapse:collapse;width:100%}td,th{padding:9px;border-bottom:1px solid #cdd9e0;text-align:left}.bar{background:#287d98;height:12px;display:inline-block}code{background:#eef4f6}</style><h1>U03 retained whole-board dependency study</h1><p>RETAINED evidence analysis. Zero U03 operations executed. No geometry or acceptance changes.</p>']
    for label,m in measurements.items():
        lines.append(f'<h2>{label}: {m["nodes"]} groups, {m["edges"]} edges</h2><p>{m["component_count"]} components; {m["articulation_count"]} articulation vertices; {m["bridge_count"]} bridges.</p><table><tr><th>Component size</th><th>Treewidth lower–upper</th><th>Balanced separator</th><th>Remaining largest</th></tr>')
        for c in m['components'][:30]:lines.append(f'<tr><td>{c["size"]} <span class="bar" style="width:{300*c["size"]/m["nodes"]:.2f}px"></span></td><td>{c["treewidth_lower"]}–{c["treewidth_upper"]}</td><td>{c["separator"]["size"]}</td><td>{max(c["separator"]["remaining_component_sizes"],default=0)}</td></tr>')
        lines.append('</table>')
    lines.append('<p>Heuristic separators and conservative dependencies: neither minimum separators nor exact semantic independence claimed. DP additionally needs justified finite domains.</p><p><a href="SUMMARY.json">Summary and provenance</a> · <a href="GRAPH.json">Graph with edge witnesses</a> · <a href="TIGHT_MEASUREMENTS.json">Decomposition certificates</a></p>')
    (output/'index.html').write_text('\n'.join(lines));progress('complete',output=str(output));return 0
if __name__=='__main__':raise SystemExit(main())
