"""Recheck all outcome-determining width predicates; retain the checked search ledger."""
import functools
from . import pipeline as p
from src import component_clearance as cc
from src.stage_abi.scene import validate_scene

def reconstruct(run,mode):
 from .guard import verify_sources
 verify_sources(run);store=p.Store(run/'runtime');binding=p.load(run/'source.json');before=validate_scene(store,p.load(run/'t03.json')['output_scene_ref']);p.initialize(store,binding,before);raw=store.get(binding['source_ref'],kind='gerber-source')
 if (run/'source_snapshot/top.art.gbr').read_bytes()!=raw or p.canonical(p.build_source(store,raw))!=p.canonical(binding):raise ValueError('WIDTH_PREFIX_FRESH_SOURCE_BINDING_CHANGED')
 value=p.load(run/'RAW_WIDTH_CHECKPOINT.json');rows,current,_=p.operands(store,before);admission=p.width_admission(store,before)
 if p.canonical(admission)!=p.canonical(value['admission']):raise ValueError('WIDTH_PREFIX_ADMISSION_CHANGED')
 paths={v['path_id']:v for v in admission['admitted']};assignment={s:g['group_id']for g in admission['groups']for s in g['members']};used={s for v in paths.values()for s in v['source_ids']};cores={s:p.unary_union([current[m]for m in v['source_ids']])for s,v in paths.items()};widths={s:max(rows[m]['metadata']['source_port_width_mm']for m in v['source_ids'])for s,v in paths.items()}
 @functools.lru_cache(maxsize=800)
 def part(sid,factor,envelope):return p.offset_part(current[sid],rows[sid]['metadata']['minimum_caliper_mm'],factor,envelope)
 def trial(scales,envelope=True):
  return [dict(id=s,original=cores[s],candidate=cores[s]if scales[assignment[s]]==1 else p.unary_union([part(m,scales[assignment[s]],envelope)for m in paths[s]['source_ids']]),verified_original_width_mm=widths[s])for s in sorted(paths)]
 solution=value['solution'];ids=sorted(g['group_id']for g in admission['groups']);selected=solution['selected_scales']
 if solution['geometry_family']!=p.OFFSET_FAMILY or not solution['passed']or not solution['maximum_established']or solution['stable_group_order']!=ids or set(selected)!=set(ids)or any(not 1<=v<=1.5 for v in selected.values())or solution['hard_ceiling']!=1.5:raise ValueError('WIDTH_PREFIX_SCALAR_FAMILY_CHANGED')
 if len(value['evaluations'])!=solution['evaluation_count']or len(solution['evaluations'])!=solution['evaluation_count']:raise ValueError('WIDTH_PREFIX_COMPLETE_SEARCH_LEDGER_MISSING')
 for i,(row,witness)in enumerate(zip(value['evaluations'],solution['evaluations'])):
  report=store.get_json(row['report_ref'],kind='width-check')
  if witness['index']!=i or witness['scales']!=row['scales']or witness['report_sha256']!=row['report_ref']['sha256']or witness['passed']!=report['passed']or witness['failures']!=report['failures']:raise ValueError('WIDTH_PREFIX_SEARCH_WITNESS_CHANGED')
 baseline=trial({g:1. for g in ids});fixed=[dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('original_width_mm',0.))for s,g in current.items()if s not in used];checker=p.PreparedWidthScene(baseline,fixed);checks={}
 for name,envelope in(('nominal',False),('envelope',True)):
  check=checker.check(trial(selected,envelope),materialize_scene=True)
  if not check['passed']or p.canonical(check)!=p.canonical(value['checks'][name]):raise ValueError('WIDTH_PREFIX_FRESH_FINAL_CHECK_CHANGED:'+name)
  checks[name]=check
 maxima=[]
 if {d['group_id']for d in solution['decisions']}!=set(ids):raise ValueError('WIDTH_PREFIX_GROUP_MAXIMUM_INVENTORY_CHANGED')
 for d in solution['decisions']:
  sid=d['group_id'];lo=d['selected_factor'];hi=d['upper_rejected_factor']
  if selected[sid]!=lo:raise ValueError('WIDTH_PREFIX_SELECTED_FACTOR_CHANGED')
  if hi is None:
   if lo!=1.5:raise ValueError('WIDTH_PREFIX_HARD_CEILING_CHANGED')
   maxima.append(dict(group_id=sid,status='HARD_CEILING',passed=True));continue
  if not 0<hi-lo<=solution['scale_tolerance']or d['factor_bracket_width']!=hi-lo:raise ValueError('WIDTH_PREFIX_MAXIMUM_BRACKET_CHANGED')
  upper=dict(selected);upper[sid]=hi;check=checker.check(trial(upper),fail_fast=True)
  if check['passed']:raise ValueError('WIDTH_PREFIX_FRESH_UPPER_REJECTION_CHANGED')
  maxima.append(dict(group_id=sid,status='FRESH_UPPER_REJECTION',passed=True,report_sha256=p.digest(p.canonical(check))))
 after=dict(current);factors={}
 for sid,v in paths.items():
  for m in v['source_ids']:after[m]=part(m,selected[assignment[sid]],False);factors[m]=selected[assignment[sid]]
 output=p.artifact_scene(store,before,after,'t04')
 if output!=value['output_scene_ref']or factors!=value['part_factors']:raise ValueError('WIDTH_PREFIX_FRESH_OUTPUT_GEOMETRY_CHANGED')
 store.verify_reads();verify_sources(run)
 proof=dict(status='PASS',raw_width_checkpoint_sha256=p.digest((run/'RAW_WIDTH_CHECKPOINT.json').read_bytes()),retained_search_reports=len(value['evaluations']),fresh_selected_full_checks=2,fresh_maximum_checks=maxima,source_admission='FRESH_COMPLETE_SOURCE_RECONSTRUCTION',output_scene_ref=output,scope='The original complete binary-search ledger is retained and hash-revalidated. Each worker freshly reconstructs all source admission, selected nominal/envelope geometry and every final upper rejection. No trial or final acceptance predicate removed.')
 p.save(run/'width_prefix_audits'/(mode+'.json'),proof);return value
