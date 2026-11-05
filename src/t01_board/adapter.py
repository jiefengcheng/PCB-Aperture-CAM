"""Whole-source scope over the unchanged priority/companion geometry kernel."""
from pathlib import Path
from contextvars import ContextVar
from src.stage_abi.store import canonical,digest
from src.stage_abi.contracts import fail
from src.t01_crop.adapter import CropAdapter
from src.t01_crop.paging import store_pages,read_pages
from .policy import HEADER,validate_policy
from .source import context

PORT_STORE=ContextVar('whole_board_port_store',default=None)

class BoardAdapter(CropAdapter):
    def describe(self):
        value=super().describe()
        value.update(implementation=digest(canonical(dict(crop_kernel=value['implementation'],board_sources={p.name:digest(p.read_bytes())for p in sorted(Path(__file__).parent.glob('*.py'))}))),source_support='PCB data ABI complete F.Cu source scope; all eligible source circles and aliases; no screenshot',english_dialect=HEADER)
        return value
    def _context(self,store,scene,policy):
        validate_policy(policy);return context(store,scene,policy)
    def _allocate(self,raw,rows,shapes,sites,policy,binding):
        settings,allocation,targets,square=super()._allocate(raw,rows,shapes,sites,policy,dict(binding,location_uncertainty_mm=0))
        if allocation['boundary_keep_source_ids'] or len(allocation['priority_pool_source_ids'])!=len(sites):fail('T01_BOARD_SELECTION_INCOMPLETE','No crop boundary keeps or partial priority pool')
        allocation['roi_semantics']='Complete original F.Cu source pool; exact source-derived board window; no image or crop membership uncertainty. Ordinary T01 interactions and shared clearance unchanged.'
        # Preserve every exact source-derived port, but do not embed megabytes of
        # hex geometry repeatedly in the plan, journal, candidate and job result.
        # Both fresh planning and reconstruction independently regenerate these
        # bytes. The common geometry/port predicate is unchanged.
        store=PORT_STORE.get()
        if store is None:fail('T01_BOARD_PORT_STORE_REQUIRED','Native allocation context')
        ports=allocation['ports'];records=[]
        for sid,zones in sorted(ports.items()):
            records.append(dict(source_id=sid,ports={oid:store.put('t01-port-geometry',bytes.fromhex(blob))for oid,blob in sorted(zones.items())}))
        page_binding=dict(source_sha256=digest(raw),site_ids_sha256=digest(canonical(sorted(ports))),viewport_mm=allocation['analysis_bounds_mm'])
        reference=store_pages(store,records,binding=page_binding,kind='t01-board-ports')
        checked,index=read_pages(store,reference,binding=page_binding,kind='t01-board-ports',identity=lambda r:r['source_id'])
        if len(checked)!=len(sites) or {r['source_id']:{oid:store.get(ref,kind='t01-port-geometry').hex()for oid,ref in r['ports'].items()}for r in checked}!=ports:fail('T01_BOARD_PORT_COVERAGE_MISMATCH','All exact port geometries and pages')
        allocation['ports']=dict(schema='t01-board-port-pages/1',index_ref=reference,sites=len(records),zones=sum(len(r['ports'])for r in records),pages=len(index['pages']))
        return settings,allocation,targets,square
    def plan(self,store,*args):
        token=PORT_STORE.set(store)
        try:return super().plan(store,*args)
        finally:PORT_STORE.reset(token)
    def _compute(self,store,*args):
        token=PORT_STORE.set(store)
        try:return super()._compute(store,*args)
        finally:PORT_STORE.reset(token)
    def verify(self,store,scene,policy,plan,candidate,proof_scope,checkpoint):
        if proof_scope!={'scope':'complete-board-t01-source-reconstruction'}:fail('PROOF_SCOPE_UNSUPPORTED','Whole-board source reconstruction required')
        result=super().verify(store,scene,policy,plan,candidate,{'scope':'complete-crop-t01-source-reconstruction'},checkpoint)
        result['scope']='Complete original F.Cu board inventory, all eligible circles and aliases, allocation, contour reconstruction and unchanged assembled finite-surface checks; no independent/electrical/manufacturing acceptance'
        return result
