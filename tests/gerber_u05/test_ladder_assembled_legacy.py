"""Assembly channel ownership must not remove the legacy primitive predicate."""
from src.gerber_u05 import pipeline as p,source_assembly
from src.t04_settings import capture_job
from src import source_channel_scope as functional


def test_integral_legacy_reference_ladder_retains_all_final_predicates(tmp_path,monkeypatch):
 from test_source_assembly import RAW
 loop=b'''D11*
X0004000000Y0004000000D02*
X0007000000Y0004000000D01*
X0007000000Y0007000000D01*
X0004000000Y0007000000D01*
X0004000000Y0004100000D01*
X0007000000Y0004000000D02*
X0008000000Y0004000000D01*
'''
 store=p.Store(tmp_path/'runtime')
 assembled,_=source_assembly.reconstruct(RAW.replace(b'M02*',loop+b'M02*'),store)
 binding=p.build_source(store,assembled);scene=store.get_json(binding['scene_ref'],kind='scene')
 # The two flags select the same independently checked policies as the route;
 # managed source-assembly custody is separately covered by native route tests.
 p.save(tmp_path/'LEGACY_REFERENCE_JOB.json',{})
 p.save(tmp_path/'SOURCE_ASSEMBLY_BINDING.json',{})
 capture_job(tmp_path)
 old=functional.ACTIVE
 try:
  p.initialize(store,binding,scene)
  assert functional.ACTIVE is not None
  result=p.run_t04(store,scene)
  assert result['checks']['nominal']['passed']
  assert result['checks']['envelope']['passed']
  assert any('NEW_EXPOSED_COPPER_BELOW_CONSTRUCTION_GUARD'in [f['reason']for f in e['failures']]
             for e in result['solution']['evaluations'])
 finally:functional.ACTIVE=old
