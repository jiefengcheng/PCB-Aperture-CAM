#!/usr/bin/env python3
"""Record the exact audited focused land scene under owner standing authority."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hashlib,json,shutil,datetime
from src.crop_circle_sources import verify_assets


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out=Path(sys.argv[1]);assert not out.exists();out.mkdir(parents=True)
    base=ROOT/'out/crop_dynamic_tasks';pre=base/'c02_focused_growth_coverage_20261028_05';prop=base/'c02_four_attachment_diagnostic_20261029_10';packet=base/'c02_t02_t04_batch_audit_20261029_25'
    integrity=verify_assets();verified=[];offline_markers=[]
    for folder in ('src','tools'):
        for p in (packet/'implementation'/folder).rglob('*.py'):
            relative=p.relative_to(packet/'implementation');current=ROOT/relative
            if not current.exists():
                assert p.name=='__init__.py' and p.read_bytes()==b'','MISSING_AUDITED_PRODUCTION_SOURCE'
                offline_markers.append(str(relative));continue
            assert sha(p)==sha(current),('AUDITED_PRODUCTION_CHANGED',relative)
            verified.append(dict(path=str(relative),sha256=sha(p)))
    closure=json.loads((packet/'ADDITIVE_REV26_AUDIT_OBSERVATION.json').read_text())
    assert closure['verdict']=='T02_GEOMETRIC_FREEZE_GATE_CLOSED_PASS' and closure['independent_tests_passed']==95
    source=json.loads((pre/'result.json').read_text());assert sha(pre/'inputs/ORG_source.kicad_pcb')==source['source_sha256']
    replacement=[];(out/'replacements').mkdir()
    circle=json.loads((pre/'t01/decision.json').read_text())
    items=[('C013',circle['source_id'],'CIRCLE',pre/'t01/candidate.wkb')]
    proposed={r['site'] for r in json.loads((prop/'result.json').read_text())['sites']}
    for r in json.loads((pre/'t02/decisions.json').read_text()):
        key=r['key'];src=(prop/f'geometry/{key}_proposal.wkb' if key in proposed else base/'c02_r080_attachment_revision_20261029_06/geometry/proposal.wkb' if key=='R080' else pre/f't02/{key}_candidate.wkb')
        items.append((key,r['source_id'],'RECTANGLE',src))
    for key,sid,kind,src in items:
        path=f'replacements/{key}.wkb';shutil.copyfile(src,out/path)
        replacement.append(dict(key=key,source_id=sid,kind=kind,path=path,sha256=sha(src)))
    assert len(replacement)==75 and len({r['source_id'] for r in replacement})==75
    (out/'REPLACEMENT_MANIFEST.json').write_text(json.dumps(replacement,indent=2,sort_keys=True)+'\n')
    files=[(prop/'geometry/after.wkb','cumulative.wkb'),(pre/'source_baseline/copper.wkb','ORG_crop.wkb'),(pre/'t01/cumulative.wkb','T01_cumulative.wkb'),(base/'c02_predecessor_readiness_20261029_24/READINESS.json','READINESS.json'),(base/'c02_predecessor_readiness_20261029_24/ALL_75_FINAL_CHECKS.json','ALL_75_FINAL_CHECKS.json'),(base/'c02_rev25_test_fixture_correction_20261029_26/TESTS_95.txt','AUTHOR_CORRECTED_TESTS_95.txt'),(packet/'ADDITIVE_AUDIT_OBSERVATION.json','REV25_AUDIT_OBSERVATION.json'),(packet/'ADDITIVE_REV26_AUDIT_OBSERVATION.json','REV26_AUDIT_OBSERVATION.json')]
    for src,name in files:shutil.copyfile(src,out/name)
    assert sha(out/'cumulative.wkb')=='a30f5a5934720e10a0543513b3980ced6f6007444604dcf9bfc49bba7cf41633'
    checks=json.loads((out/'ALL_75_FINAL_CHECKS.json').read_text());assert len(checks)==75 and all(r['check']['passed'] for r in checks)
    readiness=json.loads((out/'READINESS.json').read_text());assert readiness['positive_exposed_rectangle_witnesses']==74
    receipt=dict(schema='focused-land-geometric-freeze/1',status='FROZEN_GEOMETRIC_PREDECESSOR',recorded_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),decision_authority='Codex coordinator under owner standing authorization after designated external gate closure',scope='Exact focused C02 land scene only; geometry-only freeze, not full-board/native/electrical/manufacturing acceptance',audit_verdict_observed=True,audit_observation_sha256=sha(out/'REV26_AUDIT_OBSERVATION.json'),source_sha256=source['source_sha256'],source_manifest_sha256=sha(pre/'inputs/source_manifest.json'),viewport_mm=source['viewport_mm'],cumulative_sha256=sha(out/'cumulative.wkb'),replacement_manifest_sha256=sha(out/'REPLACEMENT_MANIFEST.json'),T01='FROZEN_EXACT_C013_CANDIDATE',T02='FROZEN_74_POSITIVE_RECTANGLE_WITNESSES_6_CONTEXT_UNCHANGED',accepted_rectangle_witnesses=74,cumulative_final_checks=75,source_trace_primitives_unchanged=15858,applicable_growth_caused_geometric_obligations='All discharged by audited exact current scene; no T03 legalization obligations',contract=source['contract'],classification_revision='Source-specific attachment support and four fixed visible-surface diagnostics; two pinned source reconstruction variants; strict failures retained',source_width_proposal_scope='DEFINED_GROUPS_FULL_SOURCE_CHECK',parallel_membership_sha256=sha(base/'c02_parallel_membership_20261029_19/PARALLEL_MEMBERSHIP.json'),chain_qualification_sha256=sha(base/'c02_trace_chain_contacts_20261029_17/CHAIN_CONTACT_QUALIFICATION.json'),prior_13_singleton_trial='Admitted subset; never full T04 coverage/acceptance',current_trace_coverage='Owner marked omissions confirmed; broader source path/group definitions under correction, not frozen or accepted here',source_trace_width_growth='NOT_RUN',T03='DEFERRED_OPTIONAL_VALID_PREDECESSOR',historical_v69_and_ledgers='UNMODIFIED',asset_integrity=integrity,verified_audited_production_sources=verified,offline_only_empty_package_markers=offline_markers)
    (out/'FREEZE_RECEIPT.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    (out/'README.md').write_text('Focused C02 T01/T02 geometry-only freeze. Exact reviewed cumulative WKB and75replacementWKBs retained.74selectedrectangle growthwitnesses,sixcontextunchanged,exactT01C013 preserved. REV25geometricadjudication+REV26independent95/95correctedtestclosure discharge gate. This record is authored by Codex under owner standing authorization; auditor did not modify ledger. Transcribed observed audit is distinguished from original downloaded receipt bytes. Strictsourcefailures,94pass+1errorandfailedlaunch remain retained. No native/electrical/manufacturing acceptance. T04coverage correction OPEN;13singletonsubset is not fullcoverage.\n')
    shutil.copyfile(__file__,out/'freeze_c02_land_scene.py')
    (out/'SHA256SUMS.json').write_text(json.dumps({str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.json'},indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status=receipt['status'],cumulative_sha256=receipt['cumulative_sha256'],accepted_rectangle_witnesses=74,receipt=str((out/'FREEZE_RECEIPT.json').resolve()))))


if __name__=='__main__':main()
