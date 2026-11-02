"""Single-slice full C01 route, with audited fresh-result handoffs."""
import sys
from types import SimpleNamespace
from src.stage_abi.store import digest
from src.c01_pipeline.bindings import T01, ORACLE, FILES, RENDER, STEPS, checkpoint
from tools.t01_native_route import RouteError
from tools.t01_c01_route import C01Route
from tools.t01_c01_files_route import C01FilesRoute
from tools.t01_c01_render_route import C01RenderRoute, render_fingerprint
from tools.t01_operator_host import ROOT, fresh, read

class C01FullRoute(C01Route):
    def __init__(self, session, **kwargs):
        super().__init__(session, **kwargs)
        self.operations = list(STEPS)
        self.identity = dict(self.identity, render_implementation=render_fingerprint())
        self.bound_outputs = {}
        self.t01_cap = None
        self.data_cap = None
        self.render_cap = None
        self.render_contract = None
        fresh(self.session/'FULL_WORKFLOW_POLICY.json', read(ROOT/'contracts/operator/c01_full.json'))

    def tools(self):
        return [t for t in super().tools() if t['name'] not in ('native_route.conformance','t01_describe')]

    def info(self):
        v=super().info()
        v.update(scope='Bound C01 T01 reproduction → fresh KiCad/Gerber export → display; no T02-T05',
                 setup_status='BOUND_FULL_C01_PROFILE',
                 status='COMPLETE_AUDITED_C01_FULL_SEQUENCE' if self.position==len(STEPS) else 'READY_FOR_AUDIT' if self.pending else 'READY_FOR_OPERATION')
        return v

    def _prior_integrity(self):
        super()._prior_integrity()
        for path, sha in self.bound_outputs.items():
            file=ROOT/path
            if file.is_symlink() or not file.is_file() or digest(file.read_bytes()) != sha:
                raise RouteError('C01_FULL_DELIVERY_CHANGED',path)

    def _request_for(self, operation, rid):
        if operation in T01:
            return super()._request_for(operation,rid)
        version='pcb-c01-handoff/1' if operation==ORACLE else 'pcb-data-abi/1' if operation in FILES else 'pcb-render-abi/1'
        return dict(abi_version=version,request_id=rid,operation=operation)

    def _argv(self, path):
        operation=self.operations[self.position]
        if operation in T01:return super()._argv(path)
        if operation==ORACLE:
            return [sys.executable,'-B',str(ROOT/'tools/pcb_c01_reproduction_check.py'),'--session',str(self.session),'--input',str(path)]
        script='pcb_data_abi.py' if operation in FILES else 'pcb_render_abi.py'
        return [sys.executable,'-B',str(ROOT/'tools'/script),'--registry',self.cap['registry_path'],
                '--registry-sha256',self.cap['registry_sha256'],'--input',str(path)]

    def _bind(self, folder):
        for p in folder.rglob('*'):
            if p.is_file():
                if p.is_symlink():raise RouteError('C01_FULL_DELIVERY_SYMLINK',str(p))
                self.bound_outputs[str(p.relative_to(ROOT))]=digest(p.read_bytes())

    def _facts(self, operation, response, code, path):
        if operation in T01:return super()._facts(operation,response,code,path)
        if operation==ORACLE:
            if code!=0 or response.get('status')!='OK' or response.get('error'):
                raise RouteError('C01_ORACLE_CHECK_FAILED',str(response.get('error')))
            facts=response['result']['facts']
            expected=dict(passed=True,canonical_sites=51,aliases=53,contour_bytes_equal=True,
                          source_semantics_equal=True,allocation_groups_equal=True,
                          oracle_opened_after_construction=True,owner_status='PENDING_USER')
            if facts!=expected:raise RouteError('C01_ORACLE_CHECK_FAILED','All source/semantic checks required')
            for name in ('RECEIPT.json','C01_SOURCE_MATCHES.json'):
                self.bound_outputs[str((self.session/name).relative_to(ROOT))]=digest((self.session/name).read_bytes())
            return facts
        if operation in FILES:
            facts=C01FilesRoute._facts(self,operation,response,code,path)
            self._prior_integrity();self._bind(self.session/'data_output')
            return facts
        checker=SimpleNamespace(contract=self.render_contract,_prior_integrity=self._prior_integrity,
                                session=self.session,bound_outputs=self.bound_outputs)
        return C01RenderRoute._facts(checker,operation,response,code,path)

    def _audit(self,args,caller):
        operation=self.pending['operation'] if self.pending else None
        result=super()._audit(args,caller)
        # Handoffs happen only after the predecessor's separate observation audit.
        if operation==ORACLE:
            self.t01_cap=dict(self.cap)
            proof=checkpoint(self.session,'T01_CHECKPOINT.json',(*T01,ORACLE),
                             [self.session/'RECEIPT.json',self.session/'C01_SOURCE_MATCHES.json'])
            contract=read(ROOT/'contracts/t01/c01_files.json')
            host=dict(schema='pcb-c01-file-host/2',predecessor=str(self.session),
                predecessor_receipt_sha256=digest((self.session/'RECEIPT.json').read_bytes()),
                source_sha256=contract['source_sha256'],edit_sha256=contract['edit_sha256'],
                edit_reference=str(ROOT/'dataset/szu-comm_3020301113B_intake_ready_20261021_v1/raw/EDIT/top_layer.kicad_pcb'),
                output=str(self.session/'data_output'),authority=contract['authority'],**proof)
            reg=self.session/'pipeline_data_host.json';fresh(reg,host)
            self.cap=dict(self.cap,registry_path=str(reg),registry_sha256=digest(reg.read_bytes()))
            self.data_cap=dict(self.cap)
        elif operation==FILES[-1]:
            proof=checkpoint(self.session,'EXPORT_CHECKPOINT.json',(*T01,ORACLE,*FILES),
                             [p for p in (self.session/'data_output').rglob('*') if p.is_file()]+[self.session/'RECEIPT.json',self.session/'T01_CHECKPOINT.json'])
            self.render_contract=read(ROOT/'contracts/render/c01.json')
            paths=dict(kicad=self.session/'data_output/candidate/board.kicad_pcb',
                       gerber=self.session/'data_output/candidate/gerbers/board-F_Cu.gbr')
            self.render_contract['inputs']={k:dict(path=str(p.relative_to(ROOT)),sha256=digest(p.read_bytes())) for k,p in paths.items()}
            self.render_contract['authority']='Read-only C01 rendering of this fresh audited full-workflow export; no other-stage execution or acceptance promotion.'
            cp=self.session/'pipeline_render_contract.json';fresh(cp,self.render_contract)
            host=dict(schema='pcb-c01-render-host/2',contract_path=str(cp),contract_sha256=digest(cp.read_bytes()),
                      output=str(self.session/'render_output'),**proof)
            reg=self.session/'pipeline_render_host.json';fresh(reg,host)
            self.cap=dict(self.cap,registry_path=str(reg),registry_sha256=digest(reg.read_bytes()))
            self.render_cap=dict(self.cap)
        return result

    def call(self,name,args,caller):
        allowed={'native_route.info','native_route.verify_receipt','native_route.audit',*STEPS}
        if name not in allowed:raise RouteError('TOOL_NOT_EXPOSED',name)
        return super().call(name,args,caller)
