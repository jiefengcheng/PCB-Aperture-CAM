"""Check uniform-width prior material before any T05 floor is transferred.

The source-derived reference also contains intentional T05 junction surfaces.
Those remain separately checked T05 work. This guard specifically prevents its
uniform T04 route bodies from overriding a lower connected-scene ladder choice.
"""
from . import pipeline as p
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM


def check_parts(prior_parts,accepted):
 buffered=accepted.buffer(POLYGON_TOLERANCE_MM,quad_segs=128)
 records=[]
 for sid,g in sorted(prior_parts.items()):
  missing=g.difference(buffered)
  records.append(dict(source_id=sid,missing_area_mm2=missing.area,
                      passed=missing.is_empty or missing.area<=p.EPS))
 return dict(passed=all(r['passed']for r in records),parts=records,
             tolerance_mm=POLYGON_TOLERANCE_MM,area_epsilon_mm2=p.EPS,
             scope='Only uniform T04 bodies; T05 joint surfaces remain separately qualified')


def verify(legacy,connected):
 old=p.load(legacy/'RAW_WIDTH_CHECKPOINT.json');new=p.load(connected/'RAW_WIDTH_CHECKPOINT.json')
 if old['settings_snapshot']!=new['settings_snapshot']:raise ValueError('T04_PRIOR_LADDER_POLICY_CHANGED')
 previous=p.Store(legacy/'runtime');current=p.Store(connected/'runtime')
 old_scene=previous.get_json(old['output_scene_ref'],kind='scene')
 completed=p.load(connected/'t04.json')
 if completed.get('raw_output_scene_ref',completed['output_scene_ref'])!=new['output_scene_ref']:raise ValueError('T04_PRIOR_COMPLETED_RAW_BINDING_CHANGED')
 for mode in('construct','1','2'):
  audit=p.load(connected/'audits/t04'/(mode+'.json'))
  if audit['status']!='PASS'or audit['candidate_sha256']!=p.digest(p.canonical(completed)):raise ValueError('T04_PRIOR_COMPLETED_AUDIT_CHANGED')
 new_scene=current.get_json(completed['output_scene_ref'],kind='scene')
 if old_scene['source_sha256']!=new_scene['source_sha256']:raise ValueError('T04_PRIOR_SOURCE_CHANGED')
 old_rows={r['source_id']:r for r in old_scene['objects']}
 _,accepted,_=p.operands(current,new_scene)
 from src.t04_width_fence import restore,require
 restore(current,new_scene)
 width_check=require(p.unary_union(list(accepted.values())),scope='prior_completed_t04_coverage')
 if width_check is None:raise ValueError('T04_PRIOR_COMPLETED_WIDTH_FENCE_MISSING')
 parts={sid:p.geometry(previous,old_rows[sid]['geometry_ref'])
        for sid,factor in old['part_factors'].items()if factor>1}
 proof=check_parts(parts,p.unary_union(list(accepted.values())))
 proof.update(schema='t04-uniform-width-prior-compatibility/1',
              legacy_checkpoint_sha256=p.digest(p.canonical(old)),
              connected_checkpoint_sha256=p.digest(p.canonical(new)),
              completed_t04_sha256=p.digest(p.canonical(completed)),
              completed_width_fence=width_check,
              coverage_basis='Completed T04 material with three matching audits and mandatory frozen width fence; no rejected widening restored')
 previous.verify_reads();current.verify_reads()
 p.save(connected/'T04_PRIOR_WIDTH_COMPATIBILITY.json',proof)
 if not proof['passed']:raise ValueError('T04_PRIOR_WOULD_BYPASS_REJECTED_UNIFORM_WIDTH')
 return proof
