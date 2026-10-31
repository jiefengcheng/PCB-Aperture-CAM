#!/usr/bin/env python3
"""Publish compact, reproducible ABI evidence without copying native caches."""
from pathlib import Path
import gzip
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shapely import from_wkb
from shapely.geometry import box
from src.stage_abi.scene import geometry
from src.stage_abi.store import ArtifactStore
from src.trace_first_pipeline import read, write, digest
from tools.render_c03_source_frame import render_source_frame

OUTPUT = ROOT / 'docs/agent_abi/results/20261031'
INPUTS = dict(t01='stage_abi_native_t01_20261031_285', t03='stage_abi_native_t03_20261031_287', t04='stage_abi_native_t04_20261031_289', t02='stage_abi_native_t02_20261031_286', t05='stage_abi_native_t05_20261031_288', bundle_model='stage_abi_bundle_composition_20261031_290')


def main():
    if OUTPUT.exists():
        raise ValueError('FRESH_DELIVERY_REQUIRED')
    OUTPUT.mkdir(parents=True)
    provenance = {}
    for stage, name in INPUTS.items():
        source = ROOT / 'out/crop_dynamic_tasks' / name
        target = OUTPUT / stage
        target.mkdir()
        store = ArtifactStore(source / 'runtime')
        receipt = read(source / 'RECEIPT.json')
        shutil.copyfile(source / 'RECEIPT.json', target / 'RECEIPT.json')
        transcript = source / ('RESULT.json' if stage == 'bundle_model' else 'TRANSCRIPT.json')
        (target / (transcript.name + '.gz')).write_bytes(gzip.compress(transcript.read_bytes(), mtime=0))
        manifest = {str(p.relative_to(source)): digest(p) for p in sorted(source.rglob('*')) if p.is_file()}
        note='Full native cache/runtime artifacts remain local. This manifest binds them; it is not a substitute for executing geometry verification.'
        body=json.dumps(dict(source_path=str(source.relative_to(ROOT)),files=manifest,note=note),indent=2,sort_keys=True).encode()+b'\n'
        archive=target/'LOCAL_EVIDENCE_MANIFEST.json.gz';archive.write_bytes(gzip.compress(body,mtime=0))
        write(target/'LOCAL_EVIDENCE_MANIFEST.json',dict(source_path=str(source.relative_to(ROOT)),file_count=len(manifest),uncompressed_manifest_sha256=hashlib.sha256(body).hexdigest(),full_manifest_ref=dict(path=archive.name,sha256=digest(archive)),note=note))
        if stage == 'bundle_model':
            images = ['before', 'after']
        else:
            for label in ('before', 'after'):
                shutil.copyfile(source / (label + '.wkb'), target / (label + '.wkb'))
            if stage == 't04':
                records = read(source / 'TRANSCRIPT.json')
                candidate = next(x['response']['result']['result']['candidate'] for x in records if x['request']['operation'] == 't04_run')
                scene = store.get_json(receipt['imported']['scene_ref'], kind='scene')
                sid = receipt['imported']['target_ids'][0]
                row = next(r for r in scene['objects'] if r['source_id'] == sid)
                bounds = list(box(*geometry(store, row['geometry_ref']).buffer(.4).bounds).intersection(box(*scene['viewport_mm'])).bounds)
                before, after = [from_wkb((source / (x + '.wkb')).read_bytes()) for x in ('before', 'after')]
                for label, copper in [('before', before), ('after', after)]:
                    for view, viewport in [('full', scene['viewport_mm']), ('detail', bounds)]:
                        image = target / (view + '_' + label + '.svg')
                        render_source_frame(image, 'C03 / source-bound ABI T04 / ' + view + ' ' + label, copper, after.difference(before) if label == 'after' else before.difference(before), viewport, notes=['One complete native route, two original source parts, full original/T01 context. Group factor 1.5x.', 'Local nominal/envelope replay PASS. Frozen accepted C01/C02/C03 unchanged.', 'Not all-route or new owner/native/electrical/manufacturing acceptance. C03 localization remains provisional.'])
                        subprocess.run(['sips', '-s', 'format', 'png', str(image), '--out', str(image.with_suffix('.png'))], check=True, capture_output=True)
            images = ['full_before', 'full_after', 'detail_before', 'detail_after']
        if stage != 't04':
            for name in images:
                for suffix in ('.svg', '.png'):
                    shutil.copyfile(source / (name + suffix), target / (name + suffix))
        (target / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>ABI qualification evidence</title><style>body{font:18px system-ui;margin:24px}img{max-width:100%}</style><h1>' + stage.upper() + ' ABI evidence</h1><p>' + ('Explicit synthetic model; not board geometry.' if stage == 'bundle_model' else 'One operation with actual C03 source/predecessor geometry. No new accepted crop.') + '</p><a href="../index.html">All suites</a> · <a href="RECEIPT.json">Receipt</a> · <a href="LOCAL_EVIDENCE_MANIFEST.json">Local full evidence bindings</a>' + ''.join('<h2>' + name.replace('_', ' ') + '</h2><img src="' + name + '.png">' for name in images))
        provenance[stage] = dict(source=str(source.relative_to(ROOT)), receipt_sha256=digest(source / 'RECEIPT.json'), transcript_sha256=digest(transcript), source_manifest_sha256=digest(target / 'LOCAL_EVIDENCE_MANIFEST.json'), runtime_fingerprint=receipt['runtime_fingerprint'])
    log = ROOT / 'out/crop_dynamic_tasks/stage_abi_implementation_20261031_278/DELIVERY_REGRESSION.log'
    shutil.copyfile(log, OUTPUT / 'REGRESSION.log')
    write(OUTPUT / 'PROVENANCE.json', dict(schema='stage-abi-delivery/1', qualifications=provenance, independent='NOT_RUN', owner_acceptance='NOT_GRANTED_BY_RUNTIME', native_electrical_manufacturing='NOT_ESTABLISHED'))
    (OUTPUT / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Five executable ABI suites</title><style>body{font:18px system-ui;max-width:1450px;margin:24px auto}img{width:100%}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:20px}article{border:1px solid #9ba;padding:16px}small{display:block}</style><h1>T01 → T03 → T04 → T02 → T05: executable local ABI evidence</h1><p>35 implemented JSON operations. C01/C02/C03 accepted results remain frozen. These are separate bounded ABI qualifications, not a newly accepted sequence on the board.</p><p>Actual source qualifications include 17,849 native objects. T03 native case requires no movement. The separate synthetic model demonstrates positive adaptive two-trace movement followed by shared-scale width growth. Local same-assistant verification only; independent/native/electrical/manufacturing qualification remains separate.</p><p><a href="../../STAGE_RUNTIME.md">Runtime documentation</a> · <a href="PROVENANCE.json">Provenance</a> · <a href="REGRESSION.log">Focused regression</a></p><div class="grid">' + ''.join('<article><h2><a href="' + stage + '/index.html">' + stage.upper() + '</a></h2><small>' + ('Synthetic model, not original-board geometry' if stage == 'bundle_model' else 'Actual source; selected operation only') + '</small><a href="' + stage + '/index.html"><img src="' + stage + '/' + ('after' if stage == 'bundle_model' else 'detail_after') + '.png"></a></article>' for stage in INPUTS) + '</div>')
    write(OUTPUT / 'SHA256SUMS.json', {str(p.relative_to(OUTPUT)): digest(p) for p in sorted(OUTPUT.rglob('*')) if p.is_file()})
    print(json.dumps(dict(path=str(OUTPUT), files=len(list(OUTPUT.rglob('*'))))))


if __name__ == '__main__':
    main()
