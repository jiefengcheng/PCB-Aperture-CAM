"""Explicit exact-source C03 width selection; never source-hash auto-selection."""
import json
from pathlib import Path
from src.stage_abi.store import digest
from src.c03_recovery import bound_bytes,SOURCE_SHA256,CROP_SHA256
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'contracts/operator/c03_width_recovery.json'
CONTRACT_SHA256='06430c2a3a6d7b52e04026daf1c2e6cd261c55c4c6a1f5fd81f75123cbbc020f'


def marker():
    blob=bound_bytes(ROOT,str(CONTRACT.relative_to(ROOT)),CONTRACT_SHA256);spec=json.loads(blob)
    if (spec['schema']!='c03-exposed-width-recovery/2' or spec['family']!='c03-complete-exposed-native-primary-cohorts/2' or spec['source_sha256']!=SOURCE_SHA256 or spec['crop_sha256']!=CROP_SHA256 or spec['blocked']!=['T01:C028','T02:R304','T02:R305'] or spec['width_scale']!=[1,1.5] or spec['boundary_policy']!='UNCHANGED_COMPLETE_MAXIMUM_ENVELOPE_AND_COMPLETE_COHORT' or spec['original_width_positive']!=94):
        raise ValueError('C03_WIDTH_CONTRACT_CHANGED')
    owner=json.loads(bound_bytes(ROOT,spec['authorization']['path'],spec['authorization']['sha256']))
    if owner['schema']!='c03-width-recovery-owner-authorization/1' or owner['branch']!='codex/c03-coverage-recovery' or owner['blocked']!=spec['blocked']:raise ValueError('C03_WIDTH_AUTHORIZATION_CHANGED')
    for name,h in spec['recipe_sources'].items():bound_bytes(ROOT,name,h)
    if spec['execution_scope']!='APPEND_ONLY_RETAINED_U05_WIDTH_CONTINUATION':raise ValueError('C03_WIDTH_SCOPE_CHANGED')
    predecessor=spec['predecessor'];r=json.loads(bound_bytes(ROOT,predecessor['receipt'],predecessor['receipt_sha256']))
    grouping=spec['grouping_reference'];g=json.loads(bound_bytes(ROOT,grouping['path'],grouping['sha256']))
    if g['grouping_contract']!=grouping['contract']:raise ValueError('C03_NATIVE_GROUPING_CONTRACT_CHANGED')
    snapshot=spec['qualified_predecessor_source'];saved=json.loads(bound_bytes(ROOT,snapshot['path']+'/SOURCE_RECEIPT.json',snapshot['sha256']))
    if saved['native_receipt_sha256']!=predecessor['receipt_sha256'] or saved['files']!=r['producer_files']:raise ValueError('C03_RETAINED_PRODUCER_RECEIPT_CHANGED')
    if r['status']!='PASS_APPEND_ONLY_C03_WIDTH_RECOVERY' or digest(Path(r['kicad']).read_bytes())!=predecessor['native_sha256']:raise ValueError('C03_WIDTH_PREDECESSOR_CHANGED')
    return dict(schema='c03-width-recovery-selected/1',contract=spec,contract_sha256=CONTRACT_SHA256)


def selected(root):
    path=Path(root)/'C03_WIDTH_RECOVERY.json'
    if path.is_symlink():raise ValueError('C03_WIDTH_MARKER_UNSAFE')
    if not path.exists():return False
    from src.c03_input_family import selected as input_selected
    if not input_selected(root):raise ValueError('C03_WIDTH_EXPLICIT_INPUT_FAMILY_REQUIRED')
    if json.loads(path.read_bytes())!=marker():raise ValueError('C03_WIDTH_SELECTION_CHANGED')
    return True
