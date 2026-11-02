"""C01 read-only render profile over the existing native runner and Mac mailbox."""

import sys
from src.stage_abi.store import canonical, digest
from tools.t01_native_route import NativeRoute, RouteError
from tools.t01_c01_route import C01Route
from tools.t01_operator_host import ROOT, read, fresh


def render_fingerprint():
    files = [*sorted((ROOT/'src/render_abi').glob('*.py')), ROOT/'tools/pcb_render_abi.py',
             ROOT/'tools/t01_c01_render_route.py', *sorted((ROOT/'contracts/render').glob('*.json'))]
    return digest(canonical({str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in files}))


class C01RenderRoute(C01Route):
    OPERATION_STATUS = 'PASS_RENDER_OPERATION_CHECKS'
    OPERATION_AUTHORITY = 'Read-only C01 rendering; technical gate, no owner acceptance'

    def __init__(self, session, **kwargs):
        NativeRoute.__init__(self, session, **kwargs)
        self.contract = read(ROOT/'contracts/render/c01.json')
        self.operations = self.contract['operations']
        self.position = 0
        self.pending = None
        self.responses = {}
        self.accepted = []
        self.audit_hashes = {}
        self.bound_outputs = {}
        self.identity = dict(self.identity, render_implementation=render_fingerprint())
        for name in ('audits', 'operator'):
            (self.session/name).mkdir()
        fresh(self.session/'DECISION_POLICY.json', self.contract)
        host = dict(schema='pcb-c01-render-host/1',
                    contract_sha256=digest((ROOT/'contracts/render/c01.json').read_bytes()),
                    output=str(self.session/'render_output'))
        registry = self.session/'render_host.json'
        fresh(registry, host)
        self.cap = dict(self.cap, registry_path=str(registry), registry_sha256=digest(registry.read_bytes()))

    def tools(self):
        tools = [t for t in C01Route.tools(self) if t['name'] not in ('native_route.conformance', 't01_describe')]
        for tool in tools:
            if tool['name'] in self.operations:
                tool['description'] = 'One read-only C01 render operation; audit its actual response before continuation.'
        return tools

    def info(self):
        info = C01Route.info(self)
        info.update(scope='Read-only C01 file rendering; no T01 construction or T02-T05 execution',
                    setup_status='BOUND_RENDER_PROFILE',
                    display=str(self.session/'render_output/index.html'),
                    status='COMPLETE_AUDITED_RENDER_SEQUENCE' if self.position == len(self.operations)
                    else 'READY_FOR_AUDIT' if self.pending else 'READY_FOR_OPERATION')
        return info

    def _request_for(self, operation, request_id):
        return dict(abi_version='pcb-render-abi/1', request_id=request_id, operation=operation)

    def _argv(self, path):
        return [sys.executable, '-B', str(ROOT/'tools/pcb_render_abi.py'), '--registry',
                self.cap['registry_path'], '--registry-sha256', self.cap['registry_sha256'], '--input', str(path)]

    def _prior_integrity(self):
        C01Route._prior_integrity(self)
        for path, sha in self.bound_outputs.items():
            file = ROOT/path
            if file.is_symlink() or not file.is_file() or digest(file.read_bytes()) != sha:
                raise RouteError('RENDER_DELIVERY_CHANGED', path)

    def _facts(self, operation, response, code, path):
        if code != 0 or response.get('status') != 'OK' or response.get('error'):
            raise RouteError('RENDER_OPERATION_FAILED', str(response.get('error')))
        facts = response['result']['facts']
        if facts.get('passed') is not True:
            raise RouteError('RENDER_CHECKS_FAILED', operation)
        if operation == 'render_c01_compare':
            if (facts.get('panels') != 2 or facts.get('dimensions') != self.contract['pixels']
                    or facts.get('layer') != 'F.Cu' or facts.get('native_commands') != 5
                    or facts.get('common_viewport') is not True or facts.get('geometry_edited') is not False
                    or facts.get('construction_status') != 'NOT_RUN' or facts.get('owner_status') != 'PENDING_USER'):
                raise RouteError('RENDER_DISPLAY_SCOPE_FAILED', operation)
        elif operation == 'render_c01_verify':
            if (facts.get('panels_checked') != 2 or facts.get('owner_status') != 'PENDING_USER'
                    or any(facts.get(k) is not True for k in ('all_pixels_checked', 'input_hashes_unchanged',
                           'output_hashes_unchanged', 'common_frame_verified', 'svg_viewport_verified'))):
                raise RouteError('RENDER_FIDELITY_FAILED', operation)
        elif facts.get('deliberate_controls') != 4 or facts.get('all_rejected_for_expected_reason') is not True:
            raise RouteError('RENDER_CONTROLS_FAILED', operation)
        self._prior_integrity()
        out = self.session/'render_output'
        name = dict(render_c01_compare='render.json', render_c01_verify='verification.json',
                    render_c01_controls='controls.json')[operation]
        if digest((out/name).read_bytes()) != digest(canonical(response['result'])):
            raise RouteError('RENDER_RECEIPT_RESPONSE_MISMATCH', name)
        for file in out.rglob('*'):
            if file.is_file():
                if file.is_symlink():
                    raise RouteError('RENDER_DELIVERY_SYMLINK', str(file))
                self.bound_outputs[str(file.relative_to(ROOT))] = digest(file.read_bytes())
        return facts

    def call(self, name, args, caller):
        if name in ('native_route.conformance', 't01_describe'):
            raise RouteError('TOOL_NOT_EXPOSED', name)
        return C01Route.call(self, name, args, caller)
