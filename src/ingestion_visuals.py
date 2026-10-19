"""Receipt-driven display derivatives. Measurements remain historical REPLAY."""
import copy
import json
from shapely import affinity
from .client_gerber import read_region
from .visual_scene import svg_path
from .ingestion_files import local, verify


def receipt_records(dataset, read_json):
    """Pure projection from named, verified receipts; used by builder and verifier."""
    presentation = dataset.get('presentation')
    if not presentation:
        return []
    if presentation.get('profile') != 'client-correspondence-v1':
        raise ValueError('Unsupported ingestion presentation profile')
    refs = presentation['receipts']
    if set(refs) != {'local', 'discrepancy', 'drills'}:
        raise ValueError('Incomplete correspondence receipt selection')
    evidence = {(r['path'], r['sha256']) for r in dataset['evidence']}
    rows = []
    for role, ref in refs.items():
        if (ref['path'], ref['sha256']) not in evidence:
            raise ValueError('Unbound presentation receipt')
        rows.append({'role': role, 'evidence': copy.deepcopy(ref), 'metrics': read_json(ref)})
    return rows


def comparison_specs(dataset, records):
    metrics = {r['role']: r['metrics'] for r in records}
    if not metrics:
        return []
    by_hash = {}
    for row in dataset['sources']:
        by_hash.setdefault(row['sha256'], []).append(row)

    def source(digest):
        matches = by_hash.get(digest, [])
        if len(matches) != 1:
            raise ValueError('Missing/ambiguous registered comparison input: ' + digest)
        return copy.deepcopy(matches[0])

    output = []
    local_report, discrepancy = metrics['local'], metrics['discrepancy']
    for layer in ['B.Cu', 'B.Mask']:
        row = local_report['layers'][layer]
        output.append({'label': 'R140.1 ' + layer, 'roi_mm': local_report['roi_mm'],
                       'receipt_role': 'local', 'inputs': {'source': source(row['source_sha256']),
                       'native': source(row['native_plot_sha256'])}})
    output.append({'label': 'L2GND discrepancy', 'roi_mm': discrepancy['roi_mm'],
                   'receipt_role': 'discrepancy', 'inputs': {'source': source(discrepancy['client_sha256']),
                   'native': source(discrepancy['native_plot_sha256'])}})
    return output


def comparison_views(root, dataset):
    """Use only registered source copies matching hashes in verified receipts.
    Reject missing/stale inputs both before and after composition.
    """
    def read_json(ref):
        verify(root, [ref])
        return json.loads(local(root, ref['path']).read_text())

    records = receipt_records(dataset, read_json)
    specs = comparison_specs(dataset, records)
    bindings = [r['evidence'] for r in records]
    bindings += [b for spec in specs for b in spec['inputs'].values()]
    verify(root, bindings)
    output = []
    for spec in specs:
        roi = spec['roi_mm']
        a = read_region(local(root, spec['inputs']['source']['path']), roi)['geometry']
        b = read_region(local(root, spec['inputs']['native']['path']), roi)['geometry']
        transform = lambda g: svg_path(affinity.scale(g, 1, -1, origin=(0, 0)))
        output.append({**spec, 'view_box': [roi[0], -roi[3], roi[2]-roi[0], roi[3]-roi[1]],
                       'source_path': transform(a), 'native_path': transform(b),
                       'source_only_path': transform(a.difference(b)),
                       'native_only_path': transform(b.difference(a)),
                       'basis': 'REPLAY display derivative; verified registered input hashes; 0.001 mm simplification; bound receipts remain measurement authority'})
    verify(root, bindings)
    return {'records': records, 'comparisons': output}
