#!/usr/bin/env python3
"""Reconcile four unchanged targets from sealed records; never run geometry/search."""
from pathlib import Path
import hashlib
import html
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'out/crop_dynamic_tasks'
ARCHIVE = BASE / 'C02-FOCUSED-RECTANGLE-COVERAGE-20261028-REV05.zip'
ARCHIVE_SHA = '0b5ab41c6abc3b1bf3d914f4e3d32fbaa4616e38b430cc0d7f10e648aa5b5824'
OUT = BASE / 'c02_four_target_disposition_20261029_09'
SITES = ('R003', 'R005', 'R006', 'R012')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def main():
    assert sha(ARCHIVE.read_bytes()) == ARCHIVE_SHA
    assert not OUT.exists(), 'FRESH_OUTPUT_REQUIRED'
    OUT.mkdir()
    (OUT/'evidence').mkdir()
    (OUT/'visuals').mkdir()
    with zipfile.ZipFile(ARCHIVE) as z:
        assert z.testzip() is None
        names = z.namelist()
        manifest = next(n for n in names if n == 'SHA256SUMS.txt' or n.endswith('/SHA256SUMS.txt'))
        prefix = manifest.removesuffix('SHA256SUMS.txt')
        entries = {}
        for line in z.read(manifest).decode().splitlines():
            digest, name = line.split(maxsplit=1)
            entries[name.strip().lstrip('*')] = digest

        def read(name):
            data = z.read(prefix+name)
            assert sha(data) == entries[name], name
            return data

        bank = json.loads(read('inputs/source_manifest.json'))
        source_rows = {r['id']: r for r in bank['objects']}
        (OUT/'evidence/run_c02_growth_coverage.py').write_bytes(read('implementation/tools/run_c02_growth_coverage.py'))
        (OUT/'evidence/crop_stage_growth.py').write_bytes(read('implementation/src/crop_stage_growth.py'))
        decisions = []
        for site in SITES:
            blob = read(f'sites/{site}.json')
            d = json.loads(blob)
            (OUT/'evidence'/f'{site}.json').write_bytes(blob)
            assert not d['objective_completed']
            assert d['axis_factors_xy'] == [1.0, 1.0]
            assert d['target_added_area_mm2'] == d['new_exposed_copper_area_mm2'] == 0.0
            assert d['check']['passed'] and not d['check']['failures']
            original = source_rows[d['source_id']]
            assert d['candidate_sha256'] == original['geometry_sha256']
            original_blob = read(f"inputs/source_wkb/{original['geometry_sha256']}.wkb")
            assert original_blob == read(f't02/{site}_candidate.wkb')
            (OUT/'evidence'/f'{site}_unchanged.wkb').write_bytes(original_blob)
            for ext in ('png', 'svg'):
                (OUT/'visuals'/f'{site}.{ext}').write_bytes(read(f'sites/{site}.{ext}'))
            probes = [dict(name='FULL_CAP', factors_xy=[1.25, 1.25], check=d['full_1p25_cap_check'])]
            probes += [dict(name=axis, factors_xy=([1.001, 1.0] if axis == 'X' else [1.0, 1.001]), check=q)
                       for axis, q in d['next_axis_increment_diagnostics'].items()]
            assert len(probes) == 3
            assert all(not p['check']['passed'] and p['check']['failures'] for p in probes)
            decisions.append(dict(site=site, source_id=d['source_id'], source_geometry_sha256=original['geometry_sha256'],
                disposition='BLOCKED_WITHIN_TESTED_DOMAIN', objective_completed=False,
                completion_denominator_exclusion=False, accepted_growth_area_mm2=0.0,
                source_candidate_byte_identical=True, saved_proposals=probes,
                tested_domain='Three explicitly retained proposals: full 1.25x cap, +0.001 X factor, +0.001 Y factor. '
                    'The prior generator also returned unchanged after two axis orders with 36-step bisections; '
                    'individual bisection trials were not retained, so they are not an exhaustive feasibility certificate.',
                limitations=['No global infeasibility proof.', 'Rejections establish behavior of the sealed checker, not necessarily physical impossibility.',
                             'No new search, source parsing, candidate construction or policy change in this slice.']))
        readme = '''# C02 four-target read-only disposition / REV09

This packet reuses sealed REV05 source-specific decisions, geometry bytes and actual rendered views. It makes no copper change. R080 separately passed model-space replay in the designated REV08 audit; no geometry from that revision is regenerated here.

All four targets remain unmet objectives in the 74-target denominator. No owner exclusion or positive-growth waiver is inferred. The current count is 70/74 positive-growth witnesses, four unchanged unmet targets, and six unselected context rectangles. T02 remains NOT_FROZEN. T03 is conditionally deferred, T04 NOT_RUN.

Each target is BLOCKED_WITHIN_TESTED_DOMAIN: its three explicitly retained probes fail the sealed checker; its accepted candidate is byte-identical to its original source geometry. This is not proof of global physical infeasibility. R003/R005/R006 have original overlapping, partly visible circles. R012's raw source pair gap is covered by an original feed according to the separately retained read-only source facts. Those facts are context, not a qualified new attachment exemption. No R080 exception is automatically transferred to these targets.

The saved +0.001 factors are isolated axis increments from the unchanged result, not a new search performed here. The prior generator used two fixed axis orders and 36 bisection steps, but did not retain every trial. Do not claim that all combinations in [1,1.25]^2 were proved infeasible. There is no source-centered positive-growth witness for these four in this packet.

Visuals are unchanged copies of the source-bound REV05 views, including their original captions. The full-C02 proposed image is unchanged REV06 evidence and retains its historical proposed caption; only its R080 model-space status changed under REV08. These copies are not a newly rendered or native exported scene.

Requested audit decision: verify the four dispositions against retained REV05 and confirm the unchanged denominator. Then identify the smallest bounded attachment-applicability/positive-witness slice needed to finish these objectives without silently waiving them, repairing unrelated original copper, modifying trace routes, or reopening the full construction campaign. No T02 freeze is requested on the basis of 70/74.
'''
        (OUT/'README.md').write_text(readme)
        save(OUT/'dispositions.json', dict(schema='c02-four-target-disposition/1', predecessor_sha256=ARCHIVE_SHA,
            source_sha256=bank.get('source_sha256'), disposition_basis='RETAINED_RECORDS_ONLY',
            positive_growth_witness_count=70, completion_denominator=74, unmet_targets=list(SITES),
            waiver_or_exclusion_requested=False, geometry_changed=False, new_search_run=False,
            t02_status='NOT_FROZEN', t03_status='CONDITIONAL_DEFERRAL_PENDING_VALID_PREDECESSOR', t04_status='NOT_RUN',
            decisions=decisions))
    facts = BASE/'c02_focused_growth_coverage_20261028_05/ADDITIVE_NO_GROWTH_SOURCE_FACTS.json'
    shutil.copy2(facts, OUT/'evidence/CONTEXT_ADDITIVE_NO_GROWTH_SOURCE_FACTS.json')
    full = BASE/'c02_r080_attachment_revision_20261029_06/visuals/full_c02_proposed.png'
    shutil.copy2(full, OUT/'visuals/full_c02_proposed_REV06.png')
    shutil.copy2(__file__, OUT/'build_c02_four_target_disposition.py')
    title = 'C02 / four unchanged T02 objectives — read-only disposition'
    page = f'<html><meta charset="utf-8"><title>{title}</title><body style="font:18px system-ui;max-width:1600px;margin:auto"><h1>{title}</h1>'
    page += '<p>70/74 positive-growth witnesses; four retained unmet objectives. T02 NOT FROZEN. No new geometry or search.</p><p>Full scene below is unchanged REV06 evidence; R080 now has REV08 model-space credit. Historical caption retained.</p><img width="100%" src="visuals/full_c02_proposed_REV06.png">'
    for d in decisions:
        page += f'<h2>{d["site"]}: BLOCKED_WITHIN_TESTED_DOMAIN</h2><p>Zero growth; original source retained. Required objective remains unmet. No global infeasibility claim.</p>'
        page += f'<p>{html.escape(d["tested_domain"])}</p><img width="100%" src="visuals/{d["site"]}.png">'
    page += '<p><a href="dispositions.json">Exact saved checks and source identities</a> · <a href="README.md">Scope and limitations</a></p></body></html>'
    (OUT/'index.html').write_text(page)
    paths = sorted(p for p in OUT.rglob('*') if p.is_file())
    (OUT/'SHA256SUMS.txt').write_text(''.join(f'{sha(p.read_bytes())}  {p.relative_to(OUT)}\n' for p in paths))
    archive = BASE/'C02-FOUR-TARGET-DISPOSITION-20261029-REV09.zip'
    assert not archive.exists()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file():
                z.write(p, f'{OUT.name}/{p.relative_to(OUT)}')
    print(json.dumps(dict(archive=str(archive), sha256=sha(archive.read_bytes()), bytes=archive.stat().st_size,
                         entries=len(paths), disposition_count=len(decisions), geometry_changed=False), indent=2))


if __name__ == '__main__':
    main()
