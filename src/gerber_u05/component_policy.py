"""Capture replaceable registries once; workers consume immutable job settings."""
from pathlib import Path
from . import pipeline as p
from src.clearance_settings import capture,read_snapshot
from src.component_voids import RemedyContract
q=Path(__file__).resolve().parents[2]

def capture_job(run):
 clearance=capture(q/'contracts/clearance/settings.json');clearance.write_snapshot(run/'CLEARANCE_SNAPSHOT.json');raw=(q/'contracts/component_remedy/settings.json').read_bytes();settings=p.load(q/'contracts/component_remedy/settings.json')
 value=dict(schema='connected-copper-remedy-job-policy/1',clearance=clearance.resolved(),settings=settings,registry_json=raw.decode(),registry_sha256=p.digest(raw))
 joint=p.load(q/'contracts/t05_joint/settings.json');value.update(t05_joint_profiles=joint,t05_joint_profiles_sha256=p.digest(p.canonical(joint)))
 p.save(run/'REMEDY_POLICY_SNAPSHOT.json',value);return read_job(run)

def read_job(run):
 value=p.load(run/'REMEDY_POLICY_SNAPSHOT.json');clearance=read_snapshot(run/'CLEARANCE_SNAPSHOT.json')
 if 't05_joint_profiles'in value:
  joint=value['t05_joint_profiles']
  if (p.digest(p.canonical(joint))!=value['t05_joint_profiles_sha256']or joint['schema']!='source-bound-t05-joint-profiles/1'or not 0<joint['radius_fraction']<=.5 or type(joint['maximum_export_regions_per_attachment'])is not int or joint['maximum_export_regions_per_attachment']<1):raise ValueError('T05_JOINT_PROFILE_POLICY_CHANGED')
 if value['clearance']!=clearance.resolved()or p.digest(value['registry_json'].encode())!=value['registry_sha256']:raise ValueError('COMPONENT_JOB_POLICY_CHANGED')
 settings=value['settings']
 from src.partial_pocket_remedy import STRATEGY
 if settings.get('large_pocket_strategy')not in(None,STRATEGY):raise ValueError('PARTIAL_POCKET_POLICY_UNSUPPORTED')
 if settings.get('large_pocket_budget')not in(None,'ONE_CUMULATIVE_ALLOWANCE_PER_FROZEN_POCKET_ACROSS_ALL_LATER_RADII_AND_STAGES'):raise ValueError('PARTIAL_POCKET_CUMULATIVE_BUDGET_POLICY_REQUIRED')
 if p.canonical(settings)!=p.canonical(__import__('json').loads(value['registry_json'])):raise ValueError('COMPONENT_REGISTRY_BINDING_CHANGED')
 if settings['schema']!='original-copper-component-remedy-settings/1'or settings['ownership']!='FROZEN_ORIGINAL_CONNECTED_COPPER'or settings['source_voids']not in('PRESERVE_INHERITED_SOURCE_VOIDS','FOLLOW_CAPTURED_HOLE_ACCEPTANCE_POLICY')or settings['ordering']!='FROZEN_CONSECUTIVE_COMPONENTS_NO_REVISIT':raise ValueError('COMPONENT_REMEDY_POLICY_UNSUPPORTED')
 radii=settings['radii_mm']
 if not radii or radii!=sorted(set(radii)):raise ValueError('ORDERED_UNIQUE_RADII_REQUIRED')
 if (p.HARD_GAP_MM,p.CONSTRUCTION_GAP_MM,p.CONTACT_BUFFER_MM)!=(clearance.nominal_mm,clearance.construction_gap_mm,clearance.contact_buffer_mm):raise ValueError('LEGACY_ALLOCATION_AND_CAPTURED_CLEARANCE_DISAGREE')
 contracts=[]
 for radius in radii:
  contract=RemedyContract(hard_gap_mm=clearance.nominal_mm,construction_gap_mm=clearance.construction_gap_mm,notch_radius_mm=radius,maximum_notch_radius_mm=settings['maximum_radius_mm'],maximum_shortage=settings['maximum_shortage_fraction'],local_reach_factor=settings['local_reach_factor'],minimum_notch_boundary_support=settings['minimum_notch_boundary_support'],grid_mm=settings['file_grid_mm'],file_uncertainty_mm=settings['native_uncertainty_mm'],area_epsilon_mm2=settings['area_epsilon_mm2']);contract.validate();contracts.append(contract)
 return value,contracts
