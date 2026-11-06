"""Verify completion of the selected one-pass remedies on the actual native file.

A further admissible growth proposal is an optional edit, not evidence that the
selected construction lost copper. Every selected owner surface must be present;
resolvable new empty pockets, source-void loss and foreign-clearance failures
remain hard failures. Original optional-search inventories remain unchanged.
"""
import sys,json,collections
from pathlib import Path
from dataclasses import asdict
from . import exporter as e
from .qualification_tail import required_coverage
from .component_policy import read_job
from .native_component_checks_final import decoded_groups,clearance,final_inventory
from src import component_clearance as cc
from src.component_voids import sha
p=e.p;run=Path(sys.argv[1]);p.configure()
from .guard import install_read_fence
install_read_fence(run.parent);e.verify_sources(run);store,binding=e.context(run)
proofs=[p.load(run/'export'/('proof_'+m+'.json'))for m in('1','2')]
if p.canonical(proofs[0])!=p.canonical(proofs[1])or proofs[0]['status']!='PASS':raise ValueError('PAIRED_NATIVE_PROOFS_REQUIRED')
body=(run/'export/top.art.gbr').read_bytes();ledger=p.load(run/'export/ledger.json');parsed=e.parse(body);n=binding['source_objects']
if p.digest(body)!=proofs[0]['generated_sha256']or len(parsed.objects)!=n+proofs[0]['appended_positive_regions']or len(ledger['records'])!=proofs[0]['appended_positive_regions']:raise ValueError('NATIVE_AUDITED_MATERIAL_BYTES_CHANGED')
raw=store.get(binding['source_ref'],kind='gerber-source')
if not body.startswith((e.canonical_base(raw)[0]+'\n').encode()):raise ValueError('ORIGINAL_CANONICAL_COMMAND_PREFIX_CHANGED')
if any(not obj.polarity_dark or not isinstance(obj,p.go.Region)for obj in parsed.objects[n:]):raise ValueError('NATIVE_AUDITED_APPEND_ROLE_CHANGED')
material=proofs[0]['native_material_assembly']
if material['status']!='EXACT_PARSED_NATIVE_MATERIAL'or len(material['material_parents'])!=material['parents']or material['parsed_regions']!=len(ledger['records']):raise ValueError('NATIVE_EXACT_MATERIAL_PROOF_CHANGED')
observed={}
for row in material['material_parents']:observed.setdefault(row['source_id'],[]).append(p.geometry(store,row['geometry_ref']))
source=cc.ACTIVE.index.source;groups=decoded_groups(source,observed);current=cc.joined(groups.values());policy,contracts=read_job(run)
if policy['settings']['ordering']!='FROZEN_CONSECUTIVE_COMPONENTS_NO_REVISIT':raise ValueError('FROZEN_ONE_PASS_REMEDY_POLICY_REQUIRED')
coverage=required_coverage(store,{stage:p.load(run/(stage+'.json'))for stage in('t04','t05')},groups,contracts)
physical=clearance(decoded_groups(source,{}),groups);inventory=final_inventory(source,groups)
qualified=p.geometry(store,proofs[0]['actual_material_image_ref'])
if current.symmetric_difference(qualified).area>contracts[0].area_epsilon_mm2:raise ValueError('NATIVE_AUDIT_MATERIAL_ASSEMBLY_CHANGED')
retained_file=run/'prefix_evidence/ORIGINAL_OPTIONAL_GROWTH_AUDIT.json';optional=dict(status='NOT_REOPENED_AFTER_FROZEN_STAGE',basis='All captured radii were already executed once and verified in the owning stages; final verification does not restart growth search')
if retained_file.exists():
 old=p.load(retained_file)
 if old['generated_sha256']!=p.digest(body):raise ValueError('OPTIONAL_GROWTH_INVENTORY_DIFFERENT_FILE')
 if [r['radius_mm']for r in old['radii']]!=policy['settings']['radii_mm']:raise ValueError('OPTIONAL_GROWTH_INVENTORY_COVERAGE_CHANGED')
 for row,contract in zip(old['radii'],contracts):
  if row['plan']['source_sha256']!=sha(source)or row['plan']['predecessor_sha256']!=sha(current)or row['plan']['contract']!=asdict(contract):raise ValueError('OPTIONAL_GROWTH_INVENTORY_INPUT_OR_POLICY_CHANGED')
 optional=dict(status='RETAINED_OPTIONAL_FURTHER_GROWTH_PROPOSALS',original_status=old['status'],proposals=len(old['eligible']),inventory_sha256=p.digest(retained_file.read_bytes()),radii=old['radii'],candidates=old['eligible'],acceptance_role='Not missing selected copper; applying these proposals would reopen the frozen growth result. Original failed audit remains unchanged.')
result=dict(status='PASS',generated_sha256=p.digest(body),eligible=[],required_remedy_coverage=coverage,
 whole_board_owner_clearance=physical,whole_board_void_inventory=inventory,
 optional_further_growth=optional,source_voids='Preserved under the unchanged native source-void checks',
 policy_scope='All selected frozen one-pass owner remedies are present; no new resolvable empty pockets; no requirement for unlimited further geometric closing',
 native_file_uncertainty_mm=contracts[0].file_uncertainty_mm,nominal_clearance_mm=contracts[0].hard_gap_mm,
 code_binding_sha256=p.digest((run/'PRODUCER_BINDING.json').read_bytes()),integration='NOT_INTEGRATED',
 historical_failed_findings='Preserved; no historical failure is relabelled or waived')
store.verify_reads();e.verify_sources(run);p.save(run/'REMAINING_DEFECT_AUDIT.json',result)
print(json.dumps(dict(status='PASS',required_surface_updates=coverage['planned_owner_surface_updates'],new_resolvable_empty_pockets=inventory['new_resolvable_empty_pockets'],optional_proposals=optional.get('proposals','NOT_REOPENED'))),flush=True)
