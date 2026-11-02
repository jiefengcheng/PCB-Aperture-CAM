"""Bounded native commands, immutable inputs, and independent raster audit."""

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from importlib.metadata import version

from PIL import Image, ImageOps
from src.stage_abi.store import canonical, digest
from src.pcb_data_abi.service import CLI
from .geometry import native_copper, gerber_copper
from .presentation import present
from .view import crop_svg, verify_svg_view, raster_fidelity, FOREGROUND, BACKGROUND

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT/'contracts/render/c01.json'
SIPS = Path('/usr/bin/sips')


def read(path):
    return json.loads(path.read_bytes())


def fresh(path, value):
    with path.open('xb') as stream:
        stream.write(canonical(value))


def local(path):
    path = Path(path).absolute()
    if not path.resolve().is_relative_to(ROOT) or any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(ROOT)):
        raise ValueError('RENDER_PROJECT_PATH_REQUIRED')
    return path.resolve()


def bound_bytes(path, expected):
    blob = local(path).read_bytes()
    if digest(blob) != expected:
        raise ValueError('RENDER_INPUT_HASH_MISMATCH')
    return blob


class RenderService:
    presenter=staticmethod(present)
    def __init__(self, host):
        self.contract_path = CONTRACT
        if type(host) is dict and host.get('schema') == 'pcb-c01-render-host/2':
            from src.c01_pipeline.bindings import validate_render_host
            self.contract_path = validate_render_host(host)
        elif (type(host) is not dict or set(host) != {'schema', 'contract_sha256', 'output'}
                or host['schema'] != 'pcb-c01-render-host/1'):
            raise ValueError('RENDER_HOST_INVALID')
        self.contract_blob = bound_bytes(self.contract_path, host['contract_sha256'])
        self.contract = json.loads(self.contract_blob)
        self.versions = {name: version(name) for name in self.contract['dependencies']}
        if self.versions != self.contract['dependencies']:
            raise ValueError('RENDER_DEPENDENCY_VERSION_CHANGED')
        self.out = local(Path(host['output']))
        if not self.out.is_relative_to(ROOT/'out'):
            raise ValueError('RENDER_OUTPUT_SCOPE_INVALID')
        self.inputs = {k: local(ROOT/v['path']) for k,v in self.contract['inputs'].items()}
        self.bounds = self.contract['bounds_mm']
        self.size = self.contract['pixels']
        self.check_inputs()
        if digest(CLI.read_bytes()) != self.contract['cli_sha256']:
            raise ValueError('RENDER_KICAD_EXECUTABLE_CHANGED')

    def check_inputs(self):
        bound_bytes(self.contract_path, digest(self.contract_blob))
        for name, path in self.inputs.items():
            bound_bytes(path, self.contract['inputs'][name]['sha256'])

    def command(self, argv, stem):
        argv = list(map(str, argv))
        metadata = dict(argv=argv, started_at=datetime.now(timezone.utc).isoformat(),
                        executable_sha256=digest(Path(argv[0]).read_bytes()),
                        environment={'KICAD_RUN_FROM_BUILD_DIR': '1'})
        try:
            result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=75,
                                    env=dict(os.environ, KICAD_RUN_FROM_BUILD_DIR='1'))
        except subprocess.TimeoutExpired as error:
            (self.out/(stem+'.stdout')).write_bytes(error.stdout or b'')
            (self.out/(stem+'.stderr')).write_bytes(error.stderr or b'')
            fresh(self.out/(stem+'.command.json'), dict(metadata, exit_status=None, timed_out=True))
            raise ValueError('RENDER_NATIVE_TIMEOUT:' + stem) from error
        except OSError as error:
            fresh(self.out/(stem+'.command.json'), dict(metadata, exit_status=None, launch_error=str(error)))
            raise ValueError('RENDER_NATIVE_LAUNCH_FAILED:' + stem) from error
        (self.out/(stem+'.stdout')).write_bytes(result.stdout)
        (self.out/(stem+'.stderr')).write_bytes(result.stderr)
        fresh(self.out/(stem+'.command.json'), dict(metadata, exit_status=result.returncode,
              stdout_sha256=digest(result.stdout), stderr_sha256=digest(result.stderr),
              completed_at=datetime.now(timezone.utc).isoformat()))
        self.check_inputs()
        if result.returncode:
            raise ValueError('RENDER_NATIVE_COMMAND_FAILED:' + stem)
        return result.stdout.decode().strip()

    def render(self):
        self.out.mkdir()
        if self.command([CLI, 'version'], 'kicad_version') != self.contract['cli_version']:
            raise ValueError('RENDER_KICAD_VERSION_CHANGED')
        if self.command([SIPS, '--version'], 'sips_version') != self.contract['sips_version']:
            raise ValueError('RENDER_SIPS_VERSION_CHANGED')
        # Qualify role/units/polarity before plotting. No unknown input semantics.
        gerber_copper(self.inputs['gerber'], self.bounds)
        self.command([CLI, 'pcb', 'export', 'svg', '--layers', 'F.Cu', '--exclude-drawing-sheet',
                      '--page-size-mode', '0', '--mode-single', '-o', self.out/'native_board.svg',
                      self.inputs['kicad']], 'kicad_svg')
        crop_svg(self.out/'native_board.svg', self.out/'kicad.svg', self.bounds, self.size)
        self.command([SIPS, '-s', 'format', 'png', self.out/'kicad.svg', '--out', self.out/'kicad.png'], 'svg_png')
        x0, y0, x1, y1 = self.bounds
        self.command([CLI, 'gerber', 'convert', 'png', '--strict', '--units', 'mm',
                      '--origin-x', x0, '--origin-y', -y1, '--window-width', x1-x0,
                      '--window-height', y1-y0, '--width', self.size[0], '--height', self.size[1],
                      '--foreground', FOREGROUND, '--background', BACKGROUND,
                      '-o', self.out/'gerber.png', self.inputs['gerber']], 'gerber_png')
        self.presenter(self.out, self.contract)
        self.check_inputs()
        files = {p.name: digest(p.read_bytes()) for p in sorted(self.out.iterdir()) if p.is_file()}
        facts = dict(passed=True, panels=2, dimensions=self.size, layer='F.Cu',
                     native_commands=5, common_viewport=True, geometry_edited=False,
                     owner_status='PENDING_USER', construction_status='NOT_RUN')
        result = dict(facts=facts, input_files=self.contract['inputs'], bounds_mm=self.bounds,
                      dependencies=self.versions,
                      coordinate_mapping=self.contract['coordinate_mapping'], files=files,
                      display=str(self.out/'index.html'), comparison_png=str(self.out/'comparison.png'),
                      render_verification='PENDING_SEPARATE_OPERATION')
        fresh(self.out/'render.json', result)
        return result

    def integrity(self):
        saved = read(self.out/'render.json')
        if saved['input_files'] != self.contract['inputs'] or saved['bounds_mm'] != self.bounds:
            raise ValueError('RENDER_RECEIPT_BINDING_MISMATCH')
        for name, sha in saved['files'].items():
            if Path(name).name != name or digest(local(self.out/name).read_bytes()) != sha:
                raise ValueError('RENDER_OUTPUT_HASH_MISMATCH:' + name)
        self.check_inputs()
        return saved

    def audit_rasters(self):
        verify_svg_view(self.out/'kicad.svg', self.bounds, self.size)
        surfaces = dict(kicad=native_copper(self.inputs['kicad'], self.bounds),
                        gerber=gerber_copper(self.inputs['gerber'], self.bounds))
        audits = {name: raster_fidelity(self.out/(name+'.png'), geometry, self.bounds, self.size,
                                      self.contract['raster_boundary_error_mm'][name])
                  for name, geometry in surfaces.items()}
        return audits, surfaces

    def verify(self):
        saved = self.integrity()
        audits, _ = self.audit_rasters()
        result = dict(facts=dict(passed=True, panels_checked=2, all_pixels_checked=True,
                      input_hashes_unchanged=True, output_hashes_unchanged=True,
                      common_frame_verified=True, svg_viewport_verified=True,
                      owner_status='PENDING_USER'), audits=audits,
                      rendered_file_manifest_sha256=digest(canonical(saved['files'])),
                      limits=self.contract['limits'])
        fresh(self.out/'verification.json', result)
        return result

    def controls(self):
        self.integrity()
        if not read(self.out/'verification.json')['facts']['passed']:
            raise ValueError('RENDER_VERIFICATION_REQUIRED')
        folder = self.out/'controls'
        folder.mkdir()
        reports = []
        def expect(name, prefix, action):
            try:
                action()
            except ValueError as error:
                if not str(error).startswith(prefix):
                    raise ValueError('RENDER_WRONG_CONTROL_REJECTION:' + str(error)) from error
                reports.append(dict(name=name, status='PASS_EXPECTED_REJECTION', error=str(error)))
            else:
                raise ValueError('RENDER_CONTROL_NOT_REJECTED:' + name)
        surface = gerber_copper(self.inputs['gerber'], self.bounds)
        with Image.open(self.out/'gerber.png') as image:
            ImageOps.mirror(image).save(folder/'mirrored_gerber.png')
        expect('mirrored_gerber', 'RASTER_FIDELITY_EXCEEDED', lambda: raster_fidelity(
               folder/'mirrored_gerber.png', surface, self.bounds, self.size, .005))
        Image.new('RGB', self.size, BACKGROUND).save(folder/'blank_kicad.png')
        expect('blank_kicad', 'RASTER_EMPTY_OR_SOLID', lambda: raster_fidelity(
               folder/'blank_kicad.png', surface, self.bounds, self.size, .005))
        root = ET.fromstring((self.out/'kicad.svg').read_bytes())
        root.set('viewBox', '0 0 3 3')
        (folder/'wrong_viewport.svg').write_bytes(ET.tostring(root))
        expect('wrong_svg_viewport', 'SVG_VIEWPORT_MISMATCH', lambda: verify_svg_view(
               folder/'wrong_viewport.svg', self.bounds, self.size))
        (folder/'changed_input.gbr').write_bytes(self.inputs['gerber'].read_bytes()+b'\nG04 changed copy*\n')
        expect('changed_input_hash', 'RENDER_INPUT_HASH_MISMATCH', lambda: bound_bytes(
               folder/'changed_input.gbr', self.contract['inputs']['gerber']['sha256']))
        self.check_inputs()
        result = dict(facts=dict(passed=True, deliberate_controls=4,
                                all_rejected_for_expected_reason=True), controls=reports)
        fresh(self.out/'controls.json', result)
        return result

    def dispatch(self, operation):
        handlers = dict(render_c01_compare=self.render, render_c01_verify=self.verify,
                        render_c01_controls=self.controls)
        if operation not in handlers:
            raise ValueError('RENDER_OPERATION_NOT_EXPOSED')
        return handlers[operation]()
