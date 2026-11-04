"""Add retained source-stream links and reuse the existing C03 visual review.

No native export, geometry construction or new raster rendering occurs here.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.c03_catalogue_stage_a import CONTRACT, digest, evidence_dir, read, require, write


def streams(output):
    cfg = read(output / 'BOUND_INPUTS.json')
    job = Path(cfg['u05_job'])
    start = read(job / 'U05_START.json')
    native = Path(start['predecessor']['root'])
    original = read(Path(cfg['u04_job']) / 'INPUT_DIRECTORY.json')
    qualified = read(native / 'data_board/inputs.json')
    exclusions = {r['relative_path'] for r in qualified['excluded_companions']}
    records = []
    for r in original['files']:
        p = Path(cfg['u04_job']) / 'raw_inputs' / r['relative_path']
        require(p.is_relative_to(Path(cfg['u04_job']) / 'raw_inputs') and not p.is_symlink(),
                'STAGED_SOURCE_PATH_INVALID')
        blob = p.read_bytes()
        require(digest(blob) == r['sha256'] and len(blob) == r['bytes'], 'STAGED_SOURCE_CHANGED')
        excluded = r['relative_path'] in exclusions
        records.append(dict(r, path=str(p),
             qualification='EXCLUDED_COMPANION_LAYER_GEOMETRY_NOT_ESTABLISHED' if excluded else
             'RETAINED_NATIVE_INPUT_CORRESPONDENCE',
             stream_semantics='Original bytes preserve all parameters, aperture definitions, order, polarity and transforms; no new Stage A parser interpretation'))
    exports = read(job / 'data_output/pcb_gerber_export.json')
    plots = []
    for role, layers in exports['exports'].items():
        for layer, name in layers.items():
            p = Path(name)
            require(p.is_relative_to(job) and not p.is_symlink(), 'EXPORTED_SOURCE_PATH_INVALID')
            h = digest(p.read_bytes())
            require(h == exports['output_sha256'][name], 'RETAINED_EXPORT_CHANGED')
            plots.append(dict(role=role, layer=layer, path=name, sha256=h,
                              bytes=p.stat().st_size, evidence='Retained native export/reparse; not freshly exported in Stage A'))
    require(len(plots) == 18, 'NINE_LAYER_PAIR_COVERAGE_CHANGED')
    write(output / 'SOURCE_STREAMS.json', dict(status='PASS_RETAINED_SOURCE_STREAM_BINDINGS',
          staged_inputs=records, exported_streams=plots, excluded_companions=len(exclusions),
          native_inventory=str(native / 'data_board/source_manifest.json'),
          input_correspondence=str(native / 'data_board/inputs.json'),
          limitations=['No external raw directory was opened',
                      'Stage A does not independently materialize Gerber command occurrences/apertures',
                      'Excluded companion geometry and layer identity remain NOT_ESTABLISHED']))


def review(output):
    from tools.visual_report import embed_scene
    cfg = read(output / 'BOUND_INPUTS.json')
    old = Path(cfg['prior_evidence']) / 'review'
    visual_qa = read(old.parent / 'VISUAL_QA.json')
    dest = output / 'review'
    dest.mkdir()
    for name, h in visual_qa['files'].items():
        p = old / name
        require(digest(p.read_bytes()) == h, 'RETAINED_VISUAL_SOURCE_CHANGED:' + name)
        if name in ('index.html', 'scene.json', 'REVIEW_BINDINGS.json'):
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    scene = read(old / 'scene.json')
    scene['measurement_authority'] = ('Stage A REPLAY of retained C03 export evidence. '
                                     'No new native operation, result acceptance or treatment.')
    scene['build']['stage_a'] = dict(status='REPLAY_RETAINED_EXPORTS',
                                   audit_sha256=digest((output / 'AUDIT.json').read_bytes()),
                                   baseline_sha256=digest((output / 'BASELINE.json').read_bytes()),
                                   contract_sha256=digest(CONTRACT.read_bytes()), stage_b='NOT_STARTED')
    for case in scene['cases']:
        case['name'] = 'REPLAY · ' + case['name']
        case['story'] = 'Stage A retained-result review. ' + case.get('story', '')
        case['limitations'].append('Stage A maps representations and measures retained replay only; Stage B NOT_STARTED.')
        for state in case['states']:
            state['label'] = 'REPLAY · ' + state['label']
    for path in (CONTRACT, output / 'AUDIT.json', output / 'BASELINE.json', output / 'SOURCE_STREAMS.json'):
        h = digest(path.read_bytes())
        name = 'evidence/' + h[:16] + '_' + path.name
        shutil.copyfile(path, dest / name)
        scene['provenance'].append(dict(path=str(path), sha256=h, snapshot=name))
    raw = embed_scene(scene)
    app = (old / 'app.syntax.js').read_text()
    template = (ROOT / 'web/workbench.html').read_text()
    page = template.replace('__SCENE__', raw).replace('__DIGEST__', digest(raw.encode())).replace('__APP__', app)
    (dest / 'scene.json').write_text(raw)
    (dest / 'index.html').write_text(page)
    require(read(dest / 'ATTACHMENTS.json')['verified_required_attachments'] == 162,
            'REPLAY_ATTACHMENT_LEDGER_CHANGED')
    require(scene['geometry'] == read(old / 'scene.json')['geometry'], 'REPLAY_GEOMETRY_CHANGED')
    for ref in scene['provenance']:
        require(digest((dest / ref['snapshot']).read_bytes()) == ref['sha256'],
                'REPLAY_PROVENANCE_CHANGED')
    write(dest / 'REVIEW_BINDINGS.json', dict(status='PASS_STAGE_A_REPLAY_PROJECTION',
          original_review=str(old / 'index.html'), original_html_sha256=visual_qa['html_sha256'],
          original_geometry_unchanged=True, original_static_preview_unchanged=True,
          embedded_scene_sha256=digest(raw.encode()),
          files={str(p.relative_to(dest)): digest(p.read_bytes()) for p in dest.rglob('*') if p.is_file()},
          browser_preview='NOT_RUN: existing local-file automatic browser policy block; no workaround',
          no_new_native_render=True, owner='PENDING_USER'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['streams', 'review'])
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    globals()[args.mode](evidence_dir(args.output))
