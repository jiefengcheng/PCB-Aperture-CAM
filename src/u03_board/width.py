"""U03 host adapter: existing T04 family/policy, bounded whole-board ledger."""
import functools
from pathlib import Path
from shapely import to_wkb
from src.stage_abi.width import WidthAdapter
from src.stage_abi.scene import composed
from src.stage_abi.runtime import Budget, output_scene
from src.stage_abi.store import canonical, digest
from .separators import SeparatorWidthScene
from .solver import solve
from .assembly import GroupCandidateAssembly
from .templates import install_route_templates


class WholeBoardWidthAdapter(WidthAdapter):
    def describe(self):
        base = super().describe()
        graph_source=Path(__file__).parents[1]/'u03_analysis/graph.py'
        base['implementation'] = digest(canonical(dict(base=base, files={p.name:digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')},separator_graph=digest(graph_source.read_bytes()))))
        return base

    def _model(self, store, scene, policy, details):
        class SourceCache:
            def __init__(self):self.sources={}
            def __getattr__(self,name):return getattr(store,name)
            def get(self,ref,*,kind=None):
                if kind!='native-source':return store.get(ref,kind=kind)
                key=canonical(ref)
                if key not in self.sources:self.sources[key]=store.get(ref,kind=kind)
                return self.sources[key]
        rows,current,model,checker,raw,chains,meta,blobs = super()._model(SourceCache(),scene,policy,details)
        # The historical 800-entry cache thrashes on this whole-board source.
        # Bound it to two full current vectors plus a finite search margin.
        model._construct = functools.lru_cache(maxsize=2*len(chains)+128)(model._construct.__wrapped__)
        install_route_templates(model,raw,meta,blobs)
        baseline = model.build(dict.fromkeys(model.group_ids,1.))[0]
        fixed = [dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('nominal_width_mm',0.)) for s,g in current.items() if s not in chains]
        return rows,current,model,SeparatorWidthScene(baseline,fixed,groups=model.assignment,source_binding=scene['source_sha256']),raw,chains,meta,blobs

    def run(self,store,scene,policy,plan,checkpoint):
        details=plan['details'];rows,current,model,checker,*_=self._model(store,scene,policy,details)
        budget=Budget(details['bounds']);reports=[]
        assembly=GroupCandidateAssembly(model)
        def evaluate(scales):
            budget.evaluation(); traces=assembly.traces(scales)
            q=checker.check(traces,fail_fast=True);blob=canonical(q);budget.output(blob)
            ref=store.put('width-check',blob);reports.append(ref)
            checkpoint(dict(evaluation=budget.evaluations,scale_vector_sha256=digest(canonical(scales)),check_ref=ref))
            return q
        solution=solve(model.group_ids,evaluate)
        if not solution['passed'] or not solution['maximum_established']:
            raise ValueError('U03_WIDTH_MODEL_MAXIMUM_NOT_ESTABLISHED')
        scales=solution['selected_scales'];traces,records,envelopes,nominal=model.build(scales)
        budget.evaluation();envelope_check=checker.check(traces,materialize_scene=True)
        nominal_traces=[];replacements={};metadata={};parts={}
        for sid in sorted(model.chains):
            factor=scales[model.assignment[sid]]
            record,np,ep,core,g,_=model.construct(sid,factor)
            nominal_traces.append(dict(id=sid,original=core,candidate=g,verified_original_width_mm=record['verified_original_width_mm']))
            blob=to_wkb(g);budget.output(blob)
            replacements[sid]=rows[sid]['geometry_ref'] if factor==1 else store.put('geometry',blob)
            metadata[sid]=dict(rows[sid]['metadata'],nominal_width_mm=record['uniform_nominal_width_mm'],width_scale=factor,width_family=record['geometry_family'])
            for member,part in np.items():
                nb,eb=to_wkb(part),to_wkb(ep[member]);budget.output(nb);budget.output(eb)
                parts[member]=dict(nominal_ref=store.put('geometry',nb),envelope_ref=store.put('geometry',eb))
        budget.evaluation();nominal_check=checker.check(nominal_traces,materialize_scene=True)
        if not envelope_check['passed'] or not nominal_check['passed']:
            raise ValueError('U03_FINAL_WIDTH_SCENE_REJECTED')
        out_ref,out=output_scene(store,scene,plan,replacements=replacements,metadata=metadata)
        return dict(status='CONSTRUCTED',solution=solution,construction=records,parts=parts,replacement_refs=replacements,
                    nominal_check=nominal_check,envelope_check=envelope_check,check_refs=reports,
                    before_ref=store.put('geometry',to_wkb(composed(store,scene))),after_ref=store.put('geometry',to_wkb(composed(store,out))),
                    output_scene_ref=out_ref,protected_source_refs={s:r['geometry_ref'] for s,r in rows.items() if s not in details['targets']})
