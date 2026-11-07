"""Retained ladder witnesses and support-only changes stay narrowly bound."""
import ast,copy
from pathlib import Path
import pytest
from src.gerber_u05 import pipeline as p
from src.gerber_u05.prefix import support_normalization_same,verify_width_ledger,legacy_support_identity


def ledger(tmp_path,count=1,width=.05):
 from src.t04_settings import capture_job
 from src.t04_ladder import solve
 settings=capture_job(tmp_path);store=p.Store(tmp_path/'runtime');rows=[]
 def evaluate(sid,factor):
  report=dict(passed=count!=1,failures=[]if count!=1 else[dict(reason='TEST_BLOCK')]);ref=store.put_json('width-check',report)
  rows.append(dict(route_id=sid,factor=factor,report_ref=ref));return report
 solution=solve({'route':width},settings,evaluate)
 if count==11:
  rows.append(copy.deepcopy(rows[-1]));solution['evaluations'].append(copy.deepcopy(solution['evaluations'][-1]));solution['evaluation_count']+=1;solution['geometry_evaluation_count']+=1
 return store,dict(evaluations=rows,solution=solution)


def test_completed_ladder_has_no_continuous_maximum_requirement(tmp_path):
 store,value=ledger(tmp_path,10)
 assert verify_width_ledger(value,store)['attempts']==10
 assert 'maximum_established'not in value['solution']


@pytest.mark.parametrize('mutation',[
 lambda v:v['solution'].update(process_completed=False),
 lambda v:v['solution'].update(passes=11),
 lambda v:v['solution'].update(evaluation_count=2),
 lambda v:v['solution']['evaluations'][0].update(route_id='another'),
 lambda v:v['solution']['evaluations'][0]['candidate'].update(factor=1.10),
 lambda v:v['solution']['evaluations'][0].update(check_sha256='0'*64),
 lambda v:v['solution']['evaluations'][0].update(passed=True),
 lambda v:v['solution']['evaluations'][0].update(failures=['forged']),
])
def test_missing_or_changed_process_evidence_rejects(tmp_path,mutation):
 store,value=ledger(tmp_path);mutation(value)
 with pytest.raises(ValueError,match='REUSED_'):verify_width_ledger(value,store)


def test_more_than_ten_attempts_per_route_rejects(tmp_path):
 store,value=ledger(tmp_path,11)
 with pytest.raises(ValueError,match='ATTEMPT_LIMIT'):verify_width_ledger(value,store)


def test_parameter_rejections_are_verified_without_fake_geometry_checks(tmp_path):
 store,value=ledger(tmp_path,10,width=.08)
 assert value['solution']['evaluation_count']==8 and len(value['evaluations'])==7
 assert verify_width_ledger(value,store)['geometry_checks']==7
 value['solution']['evaluations'][-1]['passed']=True
 with pytest.raises(ValueError,match='WITNESS_CHANGED'):verify_width_ledger(value,store)


def test_legacy_search_witness_format_is_still_verified(tmp_path):
 store,value=ledger(tmp_path);row=value['evaluations'][0];w=value['solution']['evaluations'][0]
 value['solution'].pop('schema');row['scales']={'g':1.1};w.update(scales={'g':1.1},report_sha256=row['report_ref']['sha256'])
 assert verify_width_ledger(value,store)['schema']=='legacy-continuous-search'
 w['scales']={'g':1.2}
 with pytest.raises(ValueError,match='WITNESS_CHANGED'):verify_width_ledger(value,store)


def test_only_exact_qualified_normalization_and_its_three_calls_are_allowed():
 import src.gerber_u05.export_absorption as module
 after=Path(module.__file__).read_text();tree=ast.parse(after)
 tree.body=[n for n in tree.body if not(isinstance(n,ast.FunctionDef)and n.name=='polygonal_support')]
 expected=ast.dump(ast.parse('region=polygonal_support(region)').body[0],include_attributes=False)
 class Remove(ast.NodeTransformer):
  def visit_Assign(self,node):return None if ast.dump(node,include_attributes=False)==expected else self.generic_visit(node)
 before=ast.unparse(Remove().visit(tree))
 assert support_normalization_same(before,after)['added_calls']==3
 with pytest.raises(ValueError,match='NORMALIZER_CHANGED'):
  support_normalization_same(before,after.replace("if region.geom_type in('Polygon','MultiPolygon'):return region","if region.geom_type in('Polygon','MultiPolygon'):return region.buffer(.1)"))
 with pytest.raises(ValueError,match='DELTA_CHANGED'):
  support_normalization_same(before,after.replace('CONTRACT.area_epsilon_mm2','1.'))


def test_retained_legacy_export_requires_identity_not_new_normalization(tmp_path):
 from shapely.geometry import box,GeometryCollection,LineString
 good=tmp_path/'good';store=p.Store(good/'runtime');ref=p.geomref(store,box(0,0,1,1))
 p.save(good/'export/ledger.json',dict(records=[dict(stage='t05',raw_qualified_ref=ref)]))
 assert legacy_support_identity(good)['unique_operands']==1
 bad_run=tmp_path/'bad';bad_store=p.Store(bad_run/'runtime')
 bad=p.geomref(bad_store,GeometryCollection([box(0,0,1,1),LineString([(2,0),(2,1)])]))
 p.save(bad_run/'export/ledger.json',dict(records=[dict(stage='t05',raw_qualified_ref=bad)]))
 with pytest.raises(ValueError,match='finite valid filled copper required'):legacy_support_identity(bad_run)


def test_retained_legacy_export_rejects_a_nonidentity_normalizer(tmp_path,monkeypatch):
 from shapely.geometry import box
 import src.gerber_u05.export_absorption as module
 store=p.Store(tmp_path/'runtime');ref=p.geomref(store,box(0,0,1,1))
 p.save(tmp_path/'export/ledger.json',dict(records=[dict(stage='t05',raw_qualified_ref=ref)]))
 monkeypatch.setattr(module,'polygonal_support',lambda g:g.buffer(.01))
 with pytest.raises(ValueError,match='REQUIRES_FRESH_EXPORT'):legacy_support_identity(tmp_path)
