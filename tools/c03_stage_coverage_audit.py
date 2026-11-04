"""Read-only source-bound coverage reconciliation; never a treatment gate."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shapely import from_wkb
from tools.c03_catalogue_stage_a import digest, evidence_dir, inputs, require, write


def audit(output):
    bindings = {}
    def body(path):
        path = Path(path)
        value = path.read_bytes()
        bindings[str(path)] = digest(value)
        return value
    def read(path):return json.loads(body(path))
    cfg, job, native, _, _, _, _, _, _ = inputs(output)
    historical = Path(cfg['reference'])
    from src.u05_board.store import ReadOnlyStore
    store = ReadOnlyStore(native / 'runtime')
    def get(ref):
        value = store.get(ref)
        bindings[str(native / 'runtime/artifacts' / ref['artifact_id'])] = digest(value)
        return value
    def obj(ref):return json.loads(get(ref))
    receipt = read(native / 'RECEIPT.json')
    candidate = obj(receipt['candidate_ref'])
    old_scene = obj(candidate['scene_ref'])
    scene = obj(candidate['output_scene_ref'])
    rows = {r['source_id']:r for r in scene['objects']}
    original = {r['source_id']:r for r in old_scene['objects']}
    old_results = {s:read(historical / s / 'RESULT.json') for s in ('T01','T02','T03','T04','T05')}
    require(all(r['source_sha256'] == scene['source_sha256'] for r in old_results.values()), 'REFERENCE_SOURCE_REVISION_MISMATCH')
    current = {alias:d for d in candidate['decisions'] for alias in d['aliases']}
    inventory = {alias:r for r in candidate['allocation']['crop_site_inventory'] for alias in r['aliases']}

    def geometric(old_blob, new_ref):
        new_blob = get(new_ref)
        a, b = from_wkb(old_blob), from_wkb(new_blob)
        return dict(reference_sha256=digest(old_blob), current_sha256=digest(new_blob),
                    exact_wkb_match=old_blob == new_blob,
                    missing_reference_extent_mm2=a.difference(b).area,
                    additional_current_extent_mm2=b.difference(a).area)

    t01 = []
    for old in read(historical / 'T01/DECISIONS.json'):
        sid = old['source_id'];require(sid in rows and sid in inventory, 'T01_SOURCE_UNMAPPED')
        d = current.get(sid)
        blob = body(historical / 'T01/candidates' / (old['key'] + '.wkb'))
        require(digest(blob) == old['candidate_sha256'], 'T01_REFERENCE_GEOMETRY_CHANGED')
        limits = [] if d is None else d.get('size_class', {}).get('limits', [])
        t01.append(dict(source_id=sid, historical_key=old['key'], reference_positive=old['positive_growth'],
            reference_factor=old['radius_factor'], current_decision=None if d is None else d['decision'],
            admission=inventory[sid]['disposition'], current_added_area_mm2=0 if d is None else d['added_area_mm2'],
            current_factor=None if d is None else d.get('factor'),
            rejection_reasons=sorted(set(x.get('reason', 'UNSPECIFIED') for x in limits)),
            detailed_current_decision=d, **geometric(blob, rows[sid]['geometry_ref'])))
    t02_candidate = read(native / 'u04_t02/t02_run.json')['candidate']
    t02_admission = obj(read(native / 'u04_t02/t02_inspect.json')['report_ref'])
    current = {r['source_id']:r for r in t02_candidate['decisions']}
    admission = {r['source_id']:r for r in t02_admission['sources']}
    t02 = []
    for old in read(historical / 'T02/DECISIONS.json'):
        sid = old['source_id'];require(sid in admission, 'T02_SOURCE_UNMAPPED')
        d = current.get(sid)
        blob = body(historical / 'T02/rectangle_parts' / (old['key'] + '.wkb'))
        require(digest(blob) == old['candidate_sha256'], 'T02_REFERENCE_GEOMETRY_CHANGED')
        t02.append(dict(source_id=sid, historical_key=old['key'], reference_positive=old['status']=='GROWN',
                        reference_factors=old['factors'], current_decision=None if d is None else d['status'],
                        current_factors=None if d is None else d['shape']['factors'],
                        admission=admission[sid]['disposition'],
                        **geometric(blob, admission[sid]['current_ref'] if d is None else d['candidate_ref'])))
    merges = []
    cm = {tuple(sorted(r['members'])):r for r in t02_candidate['inclusive_candidates'] if r['status']=='MERGED'}
    for old in read(historical / 'T02/INCLUSIVE_CANDIDATES.json'):
        if old['status'] != 'MERGED':continue
        d = cm.get(tuple(sorted(old['rectangle_members'])))
        require(d is not None, 'T02_REFERENCE_INCLUSIVE_MEMBERS_UNMAPPED')
        blob = body(historical / 'T02/merges' / (old['candidate'] + '.wkb'))
        require(digest(blob) == old['inclusive_wkb_sha256'], 'T02_REFERENCE_MERGE_CHANGED')
        merges.append(dict(members=old['rectangle_members'], **geometric(blob,d['candidate_ref'])))
    t04 = read(ROOT / 'out/lacie_work/evidence/t04_coverage_diagnosis_20261104T042653Z/SOURCE_BOUND_MAPPING.json')
    t05 = read(job / 'u05_t05/t05_run.json')['candidate']
    def summary(records):
        positive = [r for r in records if r['reference_positive']]
        return dict(reference_records=len(records), reference_positive=len(positive),
                    positive_reference_records_admissions=dict(Counter(r['admission'] for r in positive)),
                    positive_reference_records_current_decisions=dict(Counter(str(r['current_decision']) for r in positive)),
                    positive_reference_records_missing_extent=sum(r['missing_reference_extent_mm2']>1e-12 for r in positive),
                    positive_reference_records_exact_wkb=sum(r['exact_wkb_match'] for r in positive))
    result = dict(status='READ_ONLY_COVERAGE_DIAGNOSIS_NOT_ACCEPTANCE',source_sha256=scene['source_sha256'],
        T0=dict(interpretation='Source intake/representation; no separate T00 treatment contract found',
                original_occurrences=len(rows), historical_occurrences=old_results['T04']['all_source_objects'],
                source_occurrence_loss=len(original.keys()-rows.keys())),
        T01=dict(summary(t01), current_all_decisions=candidate['counts'], rows=t01),
        T02=dict(summary(t02), current_total=len(t02_candidate['decisions']), rows=t02,
                 inclusive_merges=merges, exact_reference_merge_geometry=sum(r['exact_wkb_match'] for r in merges)),
        T03=dict(reference=old_results['T03'], current=read(native/'u02_t03/t03_inspect.json')['facts'],
                 comparison=read(native/'u02_t03/t03_compare.json')['facts']),
        T04=t04,
        T05=dict(current_coverage=t05['coverage'], reference=old_results['T05'],
                 restored_attachment_receipt=str(job/'U05_RECEIPT.json')),
        qualification='Stage-model member/extent comparison, not new actual-export equivalence; historical proposal statuses preserved',
        geometry_or_eligibility_changes=0, historical_custody='Stage A FAIL remains; writer NOT_ESTABLISHED; no waiver')
    # Re-read all consulted files, even those outside artifact stores.
    require(all(digest(Path(p).read_bytes())==h for p,h in bindings.items()), 'COVERAGE_AUDIT_INPUT_CHANGED')
    result['input_sha256'] = bindings
    write(output / 'STAGE_COVERAGE_AUDIT.json', result)
    print(json.dumps({k:({a:b for a,b in v.items() if a not in ('rows','input_sha256','inclusive_merges','reference')} if isinstance(v,dict) else v)
                      for k,v in result.items() if k not in ('input_sha256','T04')},indent=2))


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    audit(evidence_dir(ap.parse_args().output))
