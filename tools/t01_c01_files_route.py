"""Operator-driven C01 file-export profile over the existing local transport."""
from pathlib import Path
import sys
from src.stage_abi.store import digest
from src.pcb_data_abi import ABI_VERSION
from tools.t01_native_route import NativeRoute,RouteError
from tools.t01_c01_route import C01Route
from tools.t01_operator_host import ROOT,read,fresh


class C01FilesRoute(C01Route):
    def __init__(self,session,**kwargs):
        NativeRoute.__init__(self,session,**kwargs)
        self.contract=read(ROOT/'contracts/t01/c01_files.json');self.operations=self.contract['operations']
        self.position=0;self.pending=None;self.responses={};self.accepted=[];self.audit_hashes={}
        for name in ('audits','operator'):(self.session/name).mkdir()
        fresh(self.session/'DECISION_POLICY.json',self.contract)
        predecessor=ROOT/'out/crop_dynamic_tasks/t01_c01_macos_recovery_20261031_305/run'
        edit=ROOT/'dataset/szu-comm_3020301113B_intake_ready_20261021_v1/raw/EDIT/top_layer.kicad_pcb'
        host=dict(schema='pcb-c01-file-host/1',predecessor=str(predecessor),predecessor_receipt_sha256=digest((predecessor/'RECEIPT.json').read_bytes()),source_sha256=self.contract['source_sha256'],edit_reference=str(edit),edit_sha256=self.contract['edit_sha256'],output=str(self.session/'data_output'),authority=self.contract['authority'])
        reg=self.session/'data_host.json';fresh(reg,host)
        self.cap=dict(self.cap,registry_path=str(reg),registry_sha256=digest(reg.read_bytes()))

    def tools(self):
        return [t for t in C01Route.tools(self) if t['name'] not in ('native_route.conformance','t01_describe')]

    def info(self):
        v=C01Route.info(self);v['scope']='C01 KiCad/Gerber file materialization from verified session305 geometry; T02-T05 not executed'
        v['status']='COMPLETE_AUDITED_FILE_SEQUENCE' if self.position==len(self.operations) else 'READY_FOR_AUDIT' if self.pending else 'READY_FOR_OPERATION'
        v['setup_status']='BOUND_FILE_PROFILE';return v

    def _request_for(self,operation,rid):return dict(abi_version=ABI_VERSION,request_id=rid,operation=operation)

    def _argv(self,input_path):
        return [sys.executable,'-B',str(ROOT/'tools/pcb_data_abi.py'),'--registry',self.cap['registry_path'],'--registry-sha256',self.cap['registry_sha256'],'--input',str(input_path)]

    def _facts(self,operation,response,code,path):
        if code!=0 or response['status']!='OK' or response.get('error'):
            raise RouteError('PCB_FILE_OPERATION_FAILED',str(response.get('error')))
        facts=response['result']['facts']
        if facts.get('passed')is not True:raise RouteError('PCB_FILE_CHECKS_FAILED',operation)
        if operation in ('pcb_kicad_write','pcb_kicad_verify','pcb_gerber_verify') and (facts.get('canonical_sites')!=51 or facts.get('source_occurrences')!=53):raise RouteError('PCB_FILE_COVERAGE_FAILED',operation)
        if operation=='pcb_kicad_write' and facts['modified_occurrences']!=43:raise RouteError('PCB_NATIVE_SCOPE_FAILED',operation)
        if operation=='pcb_gerber_export' and (facts['native_export_exit']!=0 or facts['layers']!=9):raise RouteError('PCB_NATIVE_EXPORT_FAILED',operation)
        if operation=='pcb_gerber_verify' and (facts['added_target_regions']!=43 or facts['protected_fcu_atoms_equal']is not True or facts['protected_other_layers']!=8):raise RouteError('PCB_PLOT_SCOPE_FAILED',operation)
        if operation=='pcb_export_controls' and (facts['deliberate_controls']!=3 or facts['all_rejected_for_expected_reason']is not True):raise RouteError('PCB_EXPORT_CONTROLS_FAILED',operation)
        return facts

    def call(self,name,args,caller):
        if name in ('native_route.conformance','t01_describe'):raise RouteError('TOOL_NOT_EXPOSED',name)
        return C01Route.call(self,name,args,caller)
