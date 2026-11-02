"""Render frame/fidelity falsification and closed wire/custody boundaries."""

import json
from pathlib import Path
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageOps
import pytest
from shapely import contains_xy
from shapely.geometry import box

from src.render_abi.view import crop_svg, verify_svg_view, raster_fidelity
from src.render_abi.service import RenderService, local, bound_bytes, ROOT
from src.stage_abi.store import digest
from tools.t01_c01_render_route import C01RenderRoute
from tools.t01_native_route import RouteError
from types import SimpleNamespace
from tools.t01_macos_adapter import MacOSAdapter


def picture(path):
    geometry = box(.1, -.9, .3, -.4).union(box(.5, -.7, .9, -.6))
    coords = (np.arange(100)+.5)/100
    mask = contains_xy(geometry, coords[None, :], (coords-1)[:, None])
    pixels = np.zeros((100, 100, 3), dtype=np.uint8)
    pixels[:] = [6, 23, 39]
    pixels[mask] = [221, 34, 51]
    Image.fromarray(pixels).save(path)
    return geometry


def test_asymmetric_mm_view_checks_every_pixel_and_rejects_mirror(tmp_path):
    path = tmp_path/'copper.png'
    geometry = picture(path)
    audit = raster_fidelity(path, geometry, [0, -1, 1, 0], [100, 100], .005)
    assert audit['pixels_checked'] == 10000 and audit['mismatch_pixels'] == 0
    with Image.open(path) as image:
        ImageOps.mirror(image).save(tmp_path/'wrong.png')
    with pytest.raises(ValueError, match='RASTER_FIDELITY_EXCEEDED'):
        raster_fidelity(tmp_path/'wrong.png', geometry, [0, -1, 1, 0], [100, 100], .005)


@pytest.mark.parametrize('mutation', ['flip_y', 'shift_origin', 'blank', 'size', 'alpha'])
def test_wrong_frame_blank_dimensions_and_transparency_are_explicit(tmp_path, mutation):
    path = tmp_path/'copper.png'
    geometry = picture(path)
    bounds, size = [0, -1, 1, 0], [100, 100]
    with Image.open(path) as image:
        if mutation == 'flip_y':
            ImageOps.flip(image).save(path)
        if mutation == 'blank':
            Image.new('RGB', image.size, '#061727').save(path)
        if mutation == 'alpha':
            image.convert('RGBA').point(lambda x: x).save(path)
    if mutation == 'shift_origin':
        bounds = [.2, -1, 1.2, 0]
    if mutation == 'size':
        size = [101, 100]
    if mutation == 'alpha':
        with Image.open(path) as image:
            image.putalpha(127)
            image.save(path)
    with pytest.raises(ValueError):
        raster_fidelity(path, geometry, bounds, size, .005)


def test_native_svg_keeps_coordinates_and_rejects_wrong_crop(tmp_path):
    raw = tmp_path/'native.svg'
    raw.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210"><path style="fill:#C83434" d="M 2,-15 L 3,-15 L 3,-14 Z"/></svg>')
    out = tmp_path/'crop.svg'
    crop_svg(raw, out, [1, -16, 4, -12], [300, 400])
    verify_svg_view(out, [1, -16, 4, -12], [300, 400])
    assert ET.fromstring(out.read_bytes())[-1].attrib['d'] == 'M 2,-15 L 3,-15 L 3,-14 Z'
    with pytest.raises(ValueError, match='SVG_VIEWPORT_MISMATCH'):
        verify_svg_view(out, [1, 12, 4, 16], [300, 400])


@pytest.mark.parametrize('child', ['<image href="https://invalid.example/x"/>', '<script/>', '<path style="fill:url(x)"/>'])
def test_svg_external_content_is_not_silently_rendered(tmp_path, child):
    path = tmp_path/'input.svg'
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg">'+child+'</svg>')
    with pytest.raises(ValueError):
        crop_svg(path, tmp_path/'out.svg', [0, 0, 1, 1], [100, 100])


def test_registry_cannot_select_output_outside_out():
    contract = ROOT/'contracts/render/c01.json'
    with pytest.raises(ValueError, match='RENDER_OUTPUT_SCOPE_INVALID'):
        RenderService(dict(schema='pcb-c01-render-host/1', contract_sha256=digest(contract.read_bytes()), output=str(ROOT/'assets/fake-output')))


def test_symlink_and_changed_input_are_rejected(tmp_path):
    contract = ROOT/'contracts/render/c01.json'
    with pytest.raises(ValueError, match='RENDER_INPUT_HASH_MISMATCH'):
        bound_bytes(contract, '0'*64)
    link = tmp_path/'linked-contract.json'
    link.symlink_to(contract)
    with pytest.raises(ValueError, match='RENDER_PROJECT_PATH_REQUIRED'):
        local(link)
    with pytest.raises(ValueError, match='RENDER_PROJECT_PATH_REQUIRED'):
        local(ROOT.parent/'not-opened-by-this-test')


@pytest.mark.parametrize('blob', [b'[]', b'{"abi_version":NaN}', b'{"operation":"a","operation":"b"}',
    b'{"abi_version":"pcb-render-abi/1","request_id":"bad","operation":"t02_run"}',
    b'{"abi_version":"pcb-render-abi/1","request_id":"bad","operation":"render_c01_compare","output":"assets"}'])
def test_real_render_cli_closed_rejections(tmp_path, blob):
    request = tmp_path/'request.json'
    request.write_bytes(blob)
    result = subprocess.run([str(ROOT/'.venv/bin/python'), '-B', str(ROOT/'tools/pcb_render_abi.py'),
        '--registry', str(tmp_path/'missing'), '--registry-sha256', '0'*64, '--input', str(request)], capture_output=True)
    response = json.loads(result.stdout)
    assert result.returncode == 2 and response['status'] == 'REJECTED' and response['result'] is None
    assert not (tmp_path/'missing').exists()


def test_render_gate_blocks_stale_bound_delivery(tmp_path):
    route = C01RenderRoute.__new__(C01RenderRoute)
    route.receipt_hashes = {}; route.audit_hashes = {}; route.bound_outputs = {'contracts/render/c01.json': '0'*64}
    route.session = tmp_path
    with pytest.raises(RouteError) as error:
        route._prior_integrity()
    assert error.value.code == 'RENDER_DELIVERY_CHANGED'


def test_render_profile_does_not_expose_construction():
    route = C01RenderRoute.__new__(C01RenderRoute)
    route.operations = ['render_c01_compare', 'render_c01_verify', 'render_c01_controls']
    route.lock = threading.RLock()
    names = {item['name'] for item in route.tools()}
    assert names == {'native_route.info', 'native_route.verify_receipt', 'native_route.audit', *route.operations}
    for name in ['t01_describe', 'native_route.conformance', 't01_run', 'pcb_kicad_write', 't02_run']:
        with pytest.raises(RouteError):
            route.call(name, {}, {})


def test_output_mutation_is_rejected_before_render_audit(tmp_path):
    service = RenderService.__new__(RenderService)
    service.out = tmp_path; service.contract = {'inputs': {'fixed': 'identity'}}
    service.bounds = [0, 0, 1, 1]; service.check_inputs = lambda: None
    image = tmp_path/'kicad.png'; image.write_bytes(b'original')
    (tmp_path/'render.json').write_text(json.dumps(dict(input_files=service.contract['inputs'],
        bounds_mm=service.bounds, files={'kicad.png': digest(b'original')})))
    image.write_bytes(b'changed')
    with pytest.raises(ValueError, match='RENDER_OUTPUT_HASH_MISMATCH'):
        service.integrity()


def test_native_render_failure_preserves_actual_logs(tmp_path, monkeypatch):
    service = RenderService.__new__(RenderService)
    service.out = tmp_path; service.check_inputs = lambda: None
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=13, stdout=b'partial', stderr=b'failed'))
    with pytest.raises(ValueError, match='RENDER_NATIVE_COMMAND_FAILED'):
        service.command([Path(__file__).resolve()], 'failed-command')
    assert (tmp_path/'failed-command.stdout').read_bytes() == b'partial'
    assert (tmp_path/'failed-command.stderr').read_bytes() == b'failed'
    assert json.loads((tmp_path/'failed-command.command.json').read_bytes())['exit_status'] == 13


def test_real_cli_rejects_wrong_registry_hash(tmp_path):
    registry = tmp_path/'host.json'; registry.write_bytes(b'{}')
    request = tmp_path/'request.json'; request.write_text(json.dumps(dict(abi_version='pcb-render-abi/1', request_id='hash-control', operation='render_c01_compare')))
    result = subprocess.run([str(ROOT/'.venv/bin/python'), '-B', str(ROOT/'tools/pcb_render_abi.py'),
        '--registry', str(registry), '--registry-sha256', '0'*64, '--input', str(request)], capture_output=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)['error']['message'] == 'RENDER_HOST_HASH_MISMATCH'


def test_bare_standard_client_discovers_bound_profile_without_setup_calls(tmp_path):
    class InfoOnlyRoute:
        session = tmp_path
        route_id = 'read-only-render'
        identity = {'test': 'native'}
        calls = []
        def tools(self):
            return [dict(name='native_route.info'), dict(name='render_c01_compare')]
        def info(self):
            return dict(scope='read-only render', status='READY_FOR_OPERATION',
                        next_operation='render_c01_compare', native=self.identity)
        def call(self, name, args, caller):
            self.calls.append(name)
            assert name == 'native_route.info' and args == {}
            return self.info()
    (tmp_path/'START.json').write_bytes(b'{}')
    route = InfoOnlyRoute(); adapter = MacOSAdapter(route)
    command = [str(ROOT/'.venv/bin/python'), '-B', str(ROOT/'tools/t01_route_client.py'),
               '--setup', str(tmp_path/'agent_setup.json'), '--agent', 'LocalCode']
    with ThreadPoolExecutor(max_workers=1) as executor:
        task = executor.submit(subprocess.run, command, capture_output=True, timeout=10)
        while not task.done():
            adapter.drain()
            time.sleep(.01)
        result = task.result()
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['next_operation'] == 'render_c01_compare'
    assert route.calls == ['native_route.info']
    assert not (tmp_path/'attempts').exists()
