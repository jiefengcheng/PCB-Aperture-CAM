"""Strict adoption of completed native stages for incremental qualification."""
import ast,hashlib,json
from pathlib import Path
STAGES=('t01','t03','t04','t02')
EXPORT_PREFIX=(*STAGES,'t05')
NATIVE_GAP_ENDPOINT_DELTA=(
 'b8b29720d76273d21c562bab69e64326d77ead3272031ff8c97250a24b25217f',
 '73ff237cfc1898bdaaad63fdb09efbb9736e03616680c0fd41ab5dae08f94633',
)
WIDTH_CORRECTION={
 'src/component_clearance.py':('957f90407b119660bffd6946320b0af398b3ee1d6402a1cfb8b1a9694dd0b904','8a705db3911686d2bb760cde74c484a16243487013e2798148bdf038886fb72d'),
 'src/prepared_width_scene.py':('6ed21e7cebd6395f8a7e29215282832a81bdbb8dd16386202e58fe019bd4ce2d','6c3f5a1d8f3ab2eb2e5482e7227af14339a4cd57fcae488d5d6b3acefd516782')}

SOURCE_VOID_T04_ONLY={
 'src/t04_topology.py':(('f7e98a25a9e15de213454946af2cb340479696cc67c92dbd88ca22b54d8a1872',),'82f73006c10d9e2f31e140b3a6b889d56f9666f704c7b4aa7714984a3489a10c'),
 'src/t04_incremental.py':(('047a49cf09ad0a276336154c68100c8c66d0ea958f3264c1cb09c04324046f98',),'2d9587e9c361c4dfbb50b4e25018a3c77607fa3865b73d52c4ea2a1d3161be41'),
 'src/gerber_u05/ladder_width.py':(('e97b3bc77b97f292194b196d4e5bd7e2164745bb6b747c10e5003905bca1a112', '5ba74cca9e73802c00444f3289ebca455254156eceaf3874a48040d930b33f95'),'71d51adff9848eb7340aed62bf27cb6a60ee7e2b5a068fbe28dfb0c79fc6af85'),
}

def source_void_t04_delta(relative,before,after):
 known=SOURCE_VOID_T04_ONLY.get(relative)
 return known is not None and before in known[0]and after==known[1]

CONNECTED_PREPARATION={'src/gerber_u05/channel_finish.py':('9eb20e39363b8eeea25fce0872619373547967a4d9bc08d096c2431f41e91dd6','b9ff517b1c48fae0604f2c753a91d3252bccfb77bd1dd87851b10a4b15fadf8b')}

def retained_stages(stages):
 stages=tuple(stages)
 if stages not in ((),STAGES[:2],STAGES[:3],STAGES,EXPORT_PREFIX):raise ValueError('REUSED_CONNECTED_PREFIX_BOUNDARY_UNSUPPORTED')
 return stages

def operation_keys(stages):
 stages=retained_stages(stages)
 return (['legacy_'+s+'_'+m for s in('t01','t03','t04','t02','t05')for m in('construct','1','2')]
         +['legacy_t01_supplement_'+m for m in('1','2')]
         +['legacy_legacy_export_'+m for m in('construct','1','2')]
         +['reference_remedy_'+m for m in('construct','1','2')]
         +['connected_'+s+'_'+m for s in stages for m in('construct','1','2')])

def connected_visual_evidence(binding):
 stages=retained_stages(binding['reused_stages'])
 count=len(operation_keys(stages))
 if binding['retained_operation_count']!=count:raise ValueError('VISUAL_REUSED_EVIDENCE_SCOPE_CHANGED')
 if stages==():
  return 'Incremental qualification: 23 source/reference operations are retained with original native proofs and hashes. T01, T03, T04, T02 and T05 are freshly constructed and reconstructed twice; final export/reparse, controls, remaining-defect audit and rendering are new.'
 if stages==('t01','t03'):
  return 'Incremental qualification: 29 unchanged source/reference/T01/T03 operations are retained with original native proofs and hashes. T04, T02 and T05 are freshly constructed and reconstructed twice; final export/reparse, controls, remaining-defect audit and rendering are new.'
 if stages==STAGES[:3]:
  return 'Incremental qualification: 32 source/reference/T01/T03/T04 operations retain their original native proofs and hashes. T02 and T05 are freshly constructed and reconstructed twice. Final export/reparse, controls, remaining-defect audit and rendering are new.'
 if stages==EXPORT_PREFIX:
  return 'Incremental export qualification: 38 source/reference and connected growth operations retain their original native proofs and hashes. Export construction, both actual-file evaluations, controls, remaining-defect audit and rendering are new.'
 return 'Incremental qualification: 35 unchanged source/reference/T01/T03/T04/T02 operations are retained with original native proofs and hashes. T05 is newly constructed and reconstructed twice; final export/reparse, controls, remaining-defect audit and rendering are new.'

def require_retained_t03(run):
 summary=load(Path(run)/'t03.json')['summary']
 if summary.get('moved')!=0 or summary.get('disposition')!='NO_CHANGE_REQUIRED':raise ValueError('REUSED_T03_MOVEMENT_REQUIRES_FRESH_QUALIFICATION')
DOWNSTREAM={'src/gerber_u05/guard.py','src/gerber_u05/contours.py','src/gerber_u05/exporter.py','src/gerber_u05/render.py','src/gerber_u05/remaining_defects.py','src/gerber_u05/controls.py','src/gerber_u05/delivery.py'}
DOWNSTREAM.update({'src/gerber_u05/incremental.py','src/gerber_u05/prefix.py','src/gerber_u05/tail.py','src/gerber_u05/qualification_tail.py','src/gerber_u05/legacy_prefix.py'})
RAW_OVERLAY_QUERY_DELTA=(
 'f2416ca81633d247f5bf8cc65bd4085dbf5e02dd7897d09eb157b975118935ee',
 'e7fc68d32a64652e406cc4758c3f3a983b8dbba8bf7e9ba752c466216fd711af')
RAW_OVERLAY_QUERY_SCOPE='Exact bounded query sharding, enabled only for the raw overlay diagnostic. Default qualification retains its existing metric and budget.'
NATIVE_FLOOR_CHECK={
 'src/gerber_u05/prior_copper.py':('f1280dc37961373a01cf578f6b5815ee694c2462b3f5aeb2045294eb1d187cf1','5bcd448cb7e231c518ad737072d5feccacb489dd7bab1dc797c29cd9e46743bf'),
 'src/gerber_u05/channel_prior.py':('665a57635e20fb8ddc86dbb036e6fa4c1002b45ea95d906b0ae8a7db9a9b28fa','cdbfc5d1e69211b303dbcb0556b8806a66baf89bf78b1137dcb84fadf1acf73f')}

STAGE_ENTRY_T05_ONLY={'src/gerber_u05/prior_copper.py': ('5bcd448cb7e231c518ad737072d5feccacb489dd7bab1dc797c29cd9e46743bf', '8e9b7da8352e41212f6887ecf3c4ee4685adf40cf742f10cc836408b8246c13e'), 'src/gerber_u05/channel_prior.py': ('cdbfc5d1e69211b303dbcb0556b8806a66baf89bf78b1137dcb84fadf1acf73f', '77e0e73cccdd51adcdfc7b1e687816770ef3e35bbaa25962d151a2a4bbac8dfc')}

def stage_entry_delta(relative,before,after):
 known=STAGE_ENTRY_T05_ONLY.get(relative);native=NATIVE_FLOOR_CHECK.get(relative)
 return known is not None and native is not None and before in(native[0],known[0])and after==known[1]and native[1]==known[0]

REFERENCE_BOUNDARY_COORDINATOR={'src/gerber_u05/hole_policy_prefix.py': ('a0b7226c83fea9cb035ca0801eda224a1b5470b414aff724c1480275bf6b0600', 'b83b92a5f3f82af03e18dd9c48092c072fc86df9745dfd5638de5b7e1d59eccf')}

def native_floor_check_delta(relative,before,after):
 return NATIVE_FLOOR_CHECK.get(relative)==(before,after)

EQUIVALENT={
 'src/gerber_u05/prior_copper.py':('6b9858d2fa67c3917b79d7ceaecdf0f1588e751231c2a3398127bf946f354676','f1280dc37961373a01cf578f6b5815ee694c2462b3f5aeb2045294eb1d187cf1','Move the unchanged strict shared-gap predicate to the complete actually adopted T05 floor. local_floor, all geometry and numerical predicates, CoverageAdapter and the cc.ACTIVE=None legacy early return are unchanged. Upstream T01/T03/T04/T02 do not call this preparation; legacy T05 retains its original adapter descriptor. The actual retained T02 case passes all 20 gap spans / 40 boundaries with identical adopted geometry.'),
 'src/gerber_u05/channel_prior.py':('b35cc910bce1c94208d9e6a678828912b5400edfcd27509dc46c8e7a0193f478','665a57635e20fb8ddc86dbb036e6fa4c1002b45ea95d906b0ae8a7db9a9b28fa','Move only the strict gap check after existing T05 channel-floor selection. Every owner, channel, physical, source and floor check remains; no geometry or tolerance change. This module is called only by connected T05 prior preparation, never the retained legacy/reference or T01-through-T02 construction. Exact hash pair only; arbitrary changes remain rejected.'),
 'src/component_voids.py':('46f6afbfd029e97a6409ecdc4b20a3c1511f394e02187ea72c9fd2ed762d49b7','db0dbae5d433b02dbe10715f772e0c46bc4144ea96050f62a8ed836d1d28246a','Only alternate global-overlay diagnostic counting uses existing areal-context extraction. Every physical geometry/source/clearance/topology check is unchanged. Valid polygon reports are identical; retained upstream reports prove that path. All positive faces retained; actual candidate remains strict polygonal copper.'),
 'src/native_boundary_metric.py':('b9a1eae932ed66667de7adf52d307b3577c0175c7d2173b29112803dc6e61b83','d84e8392b7b4f3d28c7aa5df3838532902ff99e87dc53038c0a794ac17a84cc7','Valid identical-WKB Hausdorff is exactly zero; all other indexed/native metric paths unchanged. Dedicated valid/invalid and native parity tests retained.'),
 'tools/pcb_workspace.py':('82005433b3d08a17ae9c89c4d8c022602cab4ac754e8688afdc583112a98b291','068fc453f38f86984860adb4f553a9b0f05fd10172e6f5b9ae6660afd6329ecd','Verified external source-snapshot storage namespace only; 88 native app regressions and explicit no-fallback tests retained.')}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())

def shared_gap_restore_same(before,after):
 """An export opt-in may change only restoration's complete-material overlay."""
 dump=lambda node:ast.dump(node,include_attributes=False)
 old=ast.parse('complete(ACTIVE,unary_union(list(now.values())))').body[0]
 projected=ast.parse('if project_parts:\n from src.shared_gap_projection import complete_parts\n complete_parts(ACTIVE,now.values())\nelse:\n complete(ACTIVE,unary_union(list(now.values())))').body[0]
 tree=ast.parse(after);found=False
 for node in tree.body:
  if not isinstance(node,ast.FunctionDef)or node.name!='restore':continue
  args=node.args
  if len(args.kwonlyargs)!=1 or dump(args.kwonlyargs[0])!=dump(ast.arg(arg='project_parts'))or dump(args.kw_defaults[0])!=dump(ast.Constant(False)):raise ValueError('REUSED_SHARED_GAP_RESTORE_SIGNATURE_CHANGED')
  args.kwonlyargs=[];args.kw_defaults=[]
  class Normalize(ast.NodeTransformer):
   count=0
   def visit_If(self,item):
    if dump(item)==dump(projected):self.count+=1;return old
    return self.generic_visit(item)
  normalizer=Normalize();normalizer.visit(node)
  if normalizer.count!=1:raise ValueError('REUSED_SHARED_GAP_RESTORE_PROJECTION_CHANGED')
  found=True
 if not found or dump(tree)!=dump(ast.parse(before)):raise ValueError('REUSED_SHARED_GAP_ALGORITHM_CHANGED')
 return dict(status='UNCHANGED_GROWTH_AND_DEFAULT_RESTORE_AST',changed_scope='Exact export-only opt-in to complete protected-gap projections; all existing default geometry and predicates unchanged')

def pipeline_prefix_same(before,after):
 def filtered(text):
  tree=ast.parse(text);result=[]
  for node in tree.body:
   if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))and node.name=='run_t05':continue
   if isinstance(node,ast.ImportFrom)and len(node.names)==1 and node.names[0].name=='CoverageAdapter'and node.names[0].asname is None and ((node.level==0 and node.module=='src.u05_board.coverage')or(node.level==1 and node.module=='prior_copper')):continue
   result.append(ast.dump(node,include_attributes=False))
  return result
 if filtered(before)!=filtered(after):raise ValueError('REUSED_UPSTREAM_PIPELINE_ALGORITHM_CHANGED')
 return dict(status='UNCHANGED_UPSTREAM_AST',changed_scope='run_t05 and its isolated CoverageAdapter import only')

def worker_prefix_same(before,after):
 dump=lambda node:ast.dump(node,include_attributes=False)
 allowed={dump(ast.parse(text).body[0])for text in(
  "if name=='t05':p.save(run/'raw_checkpoints'/('t05_'+os.environ.get('U05_WORKER_MODE','unit')+'.json'),value)",
  "if name=='t05':p.save(run/'completion_checkpoints'/('t05_'+os.environ.get('U05_WORKER_MODE','unit')+'_geometry.json'),value)",
  "if name=='t05':\n from .t05_pin_check import require_parts")}
 old=ast.parse("pin.ACTIVE.require(p.unary_union(list(material.values())),scope=name+'_complete')",mode='eval').body
 projected=ast.parse("require_parts(pin.ACTIVE,material.values(),scope=name+'_complete')if name=='t05'else pin.ACTIVE.require(p.unary_union(list(material.values())),scope=name+'_complete')",mode='eval').body
 class Normalize(ast.NodeTransformer):
  def visit_If(self,node):
   if dump(node)in allowed:return None
   return self.generic_visit(node)
  def visit_IfExp(self,node):
   if dump(node)==dump(projected):return old
   return self.generic_visit(node)
 def normalized(text):
  tree=ast.parse(text)
  for node in tree.body:
   if isinstance(node,ast.FunctionDef)and node.name=='compute':Normalize().visit(node)
  return dump(tree)
 if normalized(before)!=normalized(after):raise ValueError('REUSED_UPSTREAM_WORKER_CHANGED')
 return dict(status='UNCHANGED_UPSTREAM_AST',changed_scope='Exact T05-only evidence capture and complete pin-domain projection; every non-T05 statement and check is unchanged')

def support_normalization_same(before,after):
 """The qualified correction adds only three material-container conversions."""
 tree=ast.parse(after);helpers=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='polygonal_support']
 if len(helpers)!=1 or hashlib.sha256(ast.dump(helpers[0],include_attributes=False).encode()).hexdigest()!='1adce06ee62ee35f9d388b7d5f1430fbac6876a9a58714c7703d0be780fe66a5':raise ValueError('REUSED_SUPPORT_NORMALIZER_CHANGED')
 tree.body.remove(helpers[0]);allowed=ast.dump(ast.parse('region=polygonal_support(region)').body[0],include_attributes=False)
 class Remove(ast.NodeTransformer):
  count=0
  def visit_Assign(self,node):
   if ast.dump(node,include_attributes=False)==allowed:self.count+=1;return None
   return self.generic_visit(node)
 remove=Remove();tree=remove.visit(tree)
 if remove.count!=3 or ast.dump(tree,include_attributes=False)!=ast.dump(ast.parse(before),include_attributes=False):raise ValueError('REUSED_SUPPORT_NORMALIZATION_DELTA_CHANGED')
 return dict(status='EXACT_QUALIFIED_SUPPORT_NORMALIZATION_DELTA',added_calls=3,unchanged_geometry_predicates=True)

def legacy_export_encoding_same(before,after):
 qualified='1bd12fe90f262396d3f8e5295bbe8a4ff3056b1a9da2860f4ad6050f606c2299'
 originals={'b4d505217f86e501b93493278a3ff3bea51069cf7cbdbf299ef5508b798337ac','3cf905d4b53fbb020469b36cff67983d1349b048b33bd35d593828ee84fc62b1','fae75a9de50cd6c824168e92f34e9ff195ce122c222398e34550ca53775b73b0','a97d41322b176d22d9d505bb3e6a5dc1021fcd063a4347dc70e0d30a53299abc'}
 if hashlib.sha256(before.encode()).hexdigest()in originals and hashlib.sha256(after.encode()).hexdigest()==qualified:
  return dict(status='EXACT_QUALIFIED_NATIVE_POSITIVE_OPERAND_ENCODING_DELTA',scope='Only legacy export support, exact hole-preserving integer-material encoding/assembly, independently rebuilt bounded one-grid supports, parsed-positive spindle operands and exact already-satisfied attachment classification differ. Existing native reference bytes/ledger/paired proofs remain immutable. Parsing, source identity, stage geometry and numerical budgets unchanged.')
 dump=lambda node:ast.dump(node,include_attributes=False)
 old=ast.parse('from .export_absorption import supported_region').body[0]
 new=ast.parse('from .export_absorption import compact_supported_region as supported_region').body[0]
 tree=ast.parse(after);matches=[i for i,node in enumerate(tree.body)if dump(node)==dump(new)]
 if len(matches)!=1:raise ValueError('REUSED_LEGACY_EXPORT_ENCODING_DELTA_CHANGED')
 tree.body[matches[0]]=old
 if dump(tree)!=dump(ast.parse(before)):raise ValueError('REUSED_LEGACY_EXPORT_ENCODING_DELTA_CHANGED')
 return dict(status='EXACT_CONSTRUCTION_AND_NATIVE_MODEL_SUPPORT_IMPORT_ONLY',scope='Retained reference Gerber, ledger and paired native proofs remain unchanged; parsing, source identity, every metric and all other functions are unchanged.')

def verify_code(original,root,old_root,*,stages=STAGES):
 stages=retained_stages(stages);results=[];root=Path(root);old_root=Path(old_root)
 for name,expected in original['files'].items():
  path=Path(name)
  if not path.is_relative_to(old_root):raise ValueError('REUSED_PRODUCER_OUTSIDE_DECLARED_SOURCE')
  if sha(path)!=expected:raise ValueError('REUSED_ORIGINAL_PRODUCER_CHANGED:'+name)
  relative=path.relative_to(old_root).as_posix();current=root/relative
  if relative=='SOURCE_REVISION.json':continue
  actual=sha(current)
  if actual==expected:continue
  if (stages==STAGES[:3] and relative=='src/u04_board/search.py' and (expected,actual)==(
      'd167df45391eed64adf9b17db0bbee760c20e48d8158e5766b1fd7c6e7794129',
      '89f1333a99e015979bdecd8601e920d799880c61cbd95bd63d324270bdffcaed')):
   results.append(dict(path=relative,before_sha256=expected,after_sha256=actual,scope='Bounded reuse of byte-identical T02 trial results within one fixed pad search. Retain complete legacy proofs and connected proofs through T04. Reconstruct T02 and T05 fresh.'));continue
  if relative=='src/indexed_hausdorff.py' and (expected,actual)==RAW_OVERLAY_QUERY_DELTA:
   results.append(dict(path=relative,before_sha256=expected,after_sha256=actual,scope=RAW_OVERLAY_QUERY_SCOPE));continue
  if REFERENCE_BOUNDARY_COORDINATOR.get(relative)==(expected,actual):
   results.append(dict(path=relative,scope='Exact proof-only reference boundary extension; existing T01/T03 policy transition and all geometry code unchanged.',before_sha256=expected,after_sha256=actual));continue
  if relative=='src/gerber_u05/component_stages.py':
   from .t01_delta_compat import known,prove
   if known(expected,actual):
    results.append(dict(path=relative,proof=prove(path.read_text(),current.read_text()),scope='Retained PASS geometry unchanged; corrected positive-material predicate runs for fresh connected T01 only.'));continue
  if stage_entry_delta(relative,expected,actual):
   results.append(dict(path=relative,scope='Exact T05-only qualified T02 entry authority. Upstream stages unchanged; T05 and export run fresh.',before_sha256=expected,after_sha256=actual));continue
  if native_floor_check_delta(relative,expected,actual):
   results.append(dict(path=relative,scope='Exact T05-only adopted native-floor check: use existing final-reparse fidelity for native-grid boundary comparison. local_floor geometry, exact model default, CoverageAdapter and legacy cc.ACTIVE=None behavior unchanged. Retained T01/T03/T04/T02 generation is unchanged; every T05 and final native check runs fresh.',before_sha256=expected,after_sha256=actual));continue
  from .hole_policy_prefix import allowed_delta as hole_policy_delta
  if hole_policy_delta(relative,expected,actual,stages,root):
   results.append(dict(path=relative,scope=('Exact owner-authorized ordinary-hole policy relaxation. Retain only previously qualified T01 and zero-movement T03 geometry; T04 and later run fresh. Source ancestry is optional; all non-hole constraints remain mandatory.'if stages else'Exact owner-authorized ordinary-hole policy relaxation. Only verified source/legacy/reference evidence is retained; every connected stage runs fresh. Source ancestry is optional; all non-hole constraints remain mandatory.'),before_sha256=expected,after_sha256=actual));continue
  if relative=='src/gerber_u05/legacy_export.py':
   results.append(dict(path=relative,proof=legacy_export_encoding_same(path.read_text(),current.read_text())));continue
  if stages==('t01','t03')and WIDTH_CORRECTION.get(relative)==(expected,actual):
   results.append(dict(path=relative,scope='Exact e10fce9 positive-operand width delta correction and rejection evidence only. Retain connected T01 and zero-movement T03; T04 and every downstream operation run fresh. Previously passed legacy geometry and its native export remain immutable.',before_sha256=expected,after_sha256=actual));continue
  if stages==('t01','t03')and source_void_t04_delta(relative,expected,actual):
   results.append(dict(path=relative,scope='Exact source-void T04-only correction. Retain only T01/zero-movement T03; every T04 attempt and complete scene runs fresh.',before_sha256=expected,after_sha256=actual));continue
  if stages==('t01','t03')and CONNECTED_PREPARATION.get(relative)==(expected,actual):
   results.append(dict(path=relative,scope='Exact coordinate-preserving native precision-metadata reset inside connected T04/T05 completion only. Retain T01 and zero-movement T03; no connected T04/T02 completion reused.',before_sha256=expected,after_sha256=actual));continue
  if stages==EXPORT_PREFIX and relative=='src/t02_shared_gaps.py' and (expected,actual)==NATIVE_GAP_ENDPOINT_DELTA:
   results.append(dict(path=relative,before_sha256=expected,after_sha256=actual,scope='Exact default-off native straight-wall endpoint comparison. Retain growth proofs; run all export and report checks fresh.'));continue
  if relative=='src/t02_shared_gaps.py':
   results.append(dict(path=relative,proof=shared_gap_restore_same(path.read_text(),current.read_text())));continue
  if relative=='src/gerber_u05/pipeline.py':
   results.append(dict(path=relative,proof=pipeline_prefix_same(path.read_text(),current.read_text())));continue
  if relative=='src/gerber_u05/worker.py':
   results.append(dict(path=relative,proof=worker_prefix_same(path.read_text(),current.read_text())));continue
  if relative=='src/gerber_u05/export_absorption.py':
   # Upstream completion calls native_before with junction_result=None and
   # never invokes supported_region. Bind every other statement unchanged.
   def upstream(text):
    return [ast.dump(n,include_attributes=False)for n in ast.parse(text).body
            if not(isinstance(n,ast.FunctionDef)and n.name=='supported_region')]
   if upstream(path.read_text())==upstream(current.read_text()):
    results.append(dict(path=relative,scope='Only supported_region changed; called exclusively for T05 junctions'));continue
   try:proof=support_normalization_same(path.read_text(),current.read_text())
   except ValueError as error:raise ValueError('REUSED_UPSTREAM_EXPORT_SUPPORT_CHANGED')from error
   results.append(dict(path=relative,proof=proof,scope='Exact T05 support normalization only; upstream completion has no junction result. Retained legacy export operands must separately prove identity.'));continue
  if relative in DOWNSTREAM:
   results.append(dict(path=relative,scope='T05/export/verification only; not an upstream generation dependency'));continue
  proof=EQUIVALENT.get(relative)
  if proof is not None and(expected,actual)==proof[:2]:
   results.append(dict(path=relative,proof=proof[2],before_sha256=expected,after_sha256=actual));continue
  raise ValueError('REUSED_UPSTREAM_DEPENDENCY_CHANGED:'+relative)
 return results

def verify_width_ledger(value,store):
 solution=value['solution'];evaluations=value['evaluations']
 if solution.get('schema')=='source-route-ten-step-width-ladder/1':
  from src.t04_ladder import solve
  from src.t04_settings import read_snapshot,SNAPSHOT_NAME
  from . import pipeline as p
  settings=read_snapshot(store.root.parent/SNAPSHOT_NAME)
  widths={row['route_id']:row['original_width_mm']for row in solution['decisions']}
  if len(solution['evaluations'])!=solution['evaluation_count']or len(evaluations)!=solution['geometry_evaluation_count']:raise ValueError('REUSED_COMPLETE_WIDTH_SEARCH_LEDGER_MISSING')
  if solution['evaluation_count']>settings.step_count*len(widths):raise ValueError('REUSED_LADDER_ATTEMPT_LIMIT_CHANGED')
  remaining=iter(evaluations);consumed=0
  def recorded_check(sid,factor):
   nonlocal consumed
   try:row=next(remaining)
   except StopIteration as error:raise ValueError('REUSED_COMPLETE_WIDTH_SEARCH_LEDGER_MISSING')from error
   if row['route_id']!=sid or row['factor']!=factor:raise ValueError('REUSED_WIDTH_SEARCH_WITNESS_CHANGED')
   consumed+=1;return store.get_json(row['report_ref'],kind='width-check')
  # Replay discrete arithmetic and every cap rejection, using all immutable
  # geometry reports already qualified by the three original native workers.
  # This is evidence validation, not a new geometry evaluation or search.
  actual=solve(widths,settings,recorded_check)
  if consumed!=len(evaluations)or p.canonical(actual)!=p.canonical(solution):raise ValueError('REUSED_WIDTH_SEARCH_WITNESS_CHANGED')
  return dict(schema=solution['schema'],attempts=solution['evaluation_count'],geometry_checks=consumed,routes=len(widths))
 if len(evaluations)!=solution['evaluation_count']or len(solution['evaluations'])!=len(evaluations):raise ValueError('REUSED_COMPLETE_WIDTH_SEARCH_LEDGER_MISSING')
 for index,(row,witness)in enumerate(zip(evaluations,solution['evaluations'])):
  report=store.get_json(row['report_ref'],kind='width-check')
  matched=witness['index']==index and witness['scales']==row['scales']and witness['report_sha256']==row['report_ref']['sha256']
  if not matched or witness['passed']!=report['passed']or witness['failures']!=report['failures']:raise ValueError('REUSED_WIDTH_SEARCH_WITNESS_CHANGED')
 return dict(schema=solution.get('schema','legacy-continuous-search'),attempts=len(evaluations))

def legacy_support_identity(run):
 """The new normalizer must be identity on every retained legacy T05 region."""
 from . import pipeline as p
 from .export_absorption import polygonal_support
 run=Path(run);store=p.Store(run/'runtime');ledger=load(run/'export/ledger.json');refs={r['raw_qualified_ref']['artifact_id']:r['raw_qualified_ref']for r in ledger['records']if r['stage']=='t05'}
 for ref in refs.values():
  region=p.geometry(store,ref)
  if region.geom_type not in('Polygon','MultiPolygon')or not region.is_valid or region.is_empty or polygonal_support(region)is not region:raise ValueError('REUSED_LEGACY_SUPPORT_NORMALIZATION_REQUIRES_FRESH_EXPORT')
 store.verify_reads();return dict(status='IDENTITY_ON_EVERY_RETAINED_T05_SUPPORT',unique_operands=len(refs))

def verify_predecessor_families(run,binding):
 evidence=Path(run)/'prefix_evidence';legacy=evidence/'legacy';reference=evidence/'reference';records=binding['original_checks']
 legacy_seal=load(legacy/'PRODUCER_BINDING.json');source=load(legacy/'source.json')['source_ref']['sha256']
 if source!=binding['source_sha256']or sha(legacy/'source.json')!=legacy_seal['source_binding_sha256']:raise ValueError('REUSED_LEGACY_SOURCE_BINDING_CHANGED')
 reference_seal=load(reference/'PRODUCER_BINDING.json')
 if sha(reference/'source.json')!=reference_seal['source_binding_sha256']or load(reference/'source.json')['source_ref']['sha256']!=source:raise ValueError('REUSED_REFERENCE_SOURCE_BINDING_CHANGED')
 inherited=None;path=legacy/'REUSED_LEGACY_BINDING.json'
 if path.exists():
  expected=[v for k,v in legacy_seal['job_inputs'].items()if Path(k).name==path.name]
  if expected!=[sha(path)]:raise ValueError('REUSED_LEGACY_AUTHORITY_CHANGED')
  inherited=load(path)['original']
 stage_producers=None
 if inherited is not None:
  # prepare() obtains this by executing the frozen producer's recursive
  # inspector, then seals it with every copied operand. Do not attribute all
  # inherited stages to the immediate parent's producer: each may have a
  # different, recursively verified producer several generations back.
  proof=load(evidence/'ORIGINAL_LEGACY_PREFIX_PROOF.json')
  authority=binding.get('legacy_authority_run',str(Path(binding['original_run']).parent/'legacy'))
  if proof['original_run']!=authority or proof['original_producer_binding_sha256']!=sha(legacy/'PRODUCER_BINDING.json')or proof['source_binding_sha256']!=sha(legacy/'source.json')or proof['source_sha256']!=source or proof['stages']!=['t01','t03','t04','t02','t05']or proof['retained_operation_count']!=17:raise ValueError('REUSED_LEGACY_INSPECTION_BINDING_CHANGED')
  for key,record in proof['original_checks'].items():
   if records.get(key)!=record:raise ValueError('REUSED_LEGACY_INSPECTION_RECORD_CHANGED')
  for relative,expected in proof['files'].items():
   part=Path(relative)
   if part.is_absolute()or'..'in part.parts:raise ValueError('REUSED_LEGACY_INSPECTION_PATH_INVALID')
   file=legacy/part
   if not file.is_file():file=Path(run).parent/'legacy'/part
   if sha(file)!=expected:raise ValueError('REUSED_LEGACY_INSPECTION_OPERAND_CHANGED:'+relative)
  stage_producers=proof['stage_producer_bindings']
  if set(stage_producers)!=set(proof['stages']):raise ValueError('REUSED_LEGACY_STAGE_PRODUCERS_INCOMPLETE')
 for stage in('t01','t03','t04','t02','t05'):
  proofs=[load(legacy/'audits'/stage/(m+'.json'))for m in('construct','1','2')]
  producer=stage_producers[stage]if stage_producers is not None else sha(legacy/'PRODUCER_BINDING.json')
  if any(p!=proofs[0]for p in proofs)or proofs[0]['status']!='PASS'or proofs[0]['producer_binding_sha256']!=producer or proofs[0]['source_sha256']!=source or proofs[0]['candidate_sha256']!=sha(legacy/(stage+'.json')):raise ValueError('REUSED_LEGACY_STAGE_PROOF_CHANGED:'+stage)
  if records['legacy_'+stage+'_1']['pid']==records['legacy_'+stage+'_2']['pid']:raise ValueError('REUSED_LEGACY_EVALUATIONS_NOT_SEPARATE')
 supplements=[load(legacy/'audits/t01'/('supplement_'+m+'.json'))for m in('1','2')]
 if supplements[0]!=supplements[1]or supplements[0]['status']!='PASS'or supplements[0]['source_sha256']!=source or supplements[0]['stage_result_sha256']!=sha(legacy/'t01.json')or records['legacy_t01_supplement_1']['pid']==records['legacy_t01_supplement_2']['pid']:raise ValueError('REUSED_T01_SUPPLEMENT_CHANGED')
 for folder,modes,operation in((legacy,('1','2'),'legacy_legacy_export'),(reference,('construct','1','2'),'reference_remedy')):
  proofs=[load(folder/'export'/('proof_'+m+'.json'))for m in modes]
  if any(p!=proofs[0]for p in proofs)or proofs[0]['status']!='PASS'or proofs[0]['generated_sha256']!=sha(folder/'export/top.art.gbr'):raise ValueError('REUSED_NATIVE_REFERENCE_PROOF_CHANGED')
  if records[operation+'_1']['pid']==records[operation+'_2']['pid']:raise ValueError('REUSED_NATIVE_REFERENCE_EVALUATIONS_NOT_SEPARATE')
 required=operation_keys(binding['reused_stages'])
 if set(records)!=set(required)or binding['retained_operation_count']!=len(required)or any(records[k]['status']!='PASS'or records[k]['returncode']!=0 for k in required):raise ValueError('REUSED_COMPLETE_NATIVE_PREFIX_REQUIRED')
 return dict(status='PASS',retained_operations=len(required))

def verify(run):
 from . import pipeline as p
 from .guard import ROOT
 run=Path(run);path=run/'REUSED_PREFIX_BINDING.json'
 if not path.exists():return None
 binding=load(path);original=load(run/'prefix_evidence/ORIGINAL_PRODUCER_BINDING.json')
 stages=retained_stages(binding['reused_stages'])
 if sha(run/'prefix_evidence/ORIGINAL_PRODUCER_BINDING.json')!=binding['original_producer_binding_sha256']:raise ValueError('REUSED_PRODUCER_BINDING_CHANGED')
 verify_code(original,ROOT,binding['original_source_root'],stages=stages)
 if stages==('t01','t03'):require_retained_t03(run)
 if sha(run/'source.json')!=original['source_binding_sha256']:raise ValueError('REUSED_PREFIX_SOURCE_CHANGED')
 for relative,expected in binding['files'].items():
  file=run/relative
  if not file.is_relative_to(run)or sha(file)!=expected:raise ValueError('REUSED_PREFIX_EVIDENCE_CHANGED:'+relative)
 verify_predecessor_families(run,binding)
 producers=binding.get('stage_producer_bindings')
 if producers is not None and set(producers)!=set(stages):raise ValueError('REUSED_STAGE_PRODUCER_INVENTORY_CHANGED')
 for stage in stages:
  candidate=sha(run/(stage+'.json'));proofs=[load(run/'audits'/stage/(mode+'.json'))for mode in('construct','1','2')]
  if proofs[0]!=proofs[1]or proofs[0]!=proofs[2]:raise ValueError('REUSED_PAIRED_PROOFS_DIFFER:'+stage)
  producer=binding['original_producer_binding_sha256']if producers is None else producers[stage]
  if proofs[0]['status']!='PASS'or proofs[0]['candidate_sha256']!=candidate or proofs[0]['producer_binding_sha256']!=producer:raise ValueError('REUSED_STAGE_PROOF_CHANGED:'+stage)
  for mode in('construct','1','2'):
   key='connected_'+stage+'_'+mode;record=binding['original_checks'][key]
   if record['status']!='PASS'or record['returncode']!=0:raise ValueError('REUSED_NATIVE_PROCESS_DID_NOT_PASS:'+key)
  if binding['original_checks']['connected_'+stage+'_1']['pid']==binding['original_checks']['connected_'+stage+'_2']['pid']:raise ValueError('REUSED_EVALUATIONS_NOT_SEPARATE_PROCESSES')
 # Preserve and hash-revalidate every original search witness, without solving
 # unchanged geometry again. All new T05 and actual-file predicates stay fresh.
 store=p.Store(run/'runtime');value=None
 if 't04'in stages:
  value=load(run/'t04.json');verify_width_ledger(value,store)
 if binding.get('checked_legacy_files'):
  legacy=run.parent/'legacy'
  for relative,expected in binding['checked_legacy_files'].items():
   file=legacy/relative
   if not file.resolve().is_relative_to(legacy.resolve())or sha(file)!=expected:raise ValueError('REUSED_CHECKING_ENVELOPE_EVIDENCE_CHANGED')
  if legacy_support_identity(run/'prefix_evidence/legacy')!=binding['legacy_support_identity']:raise ValueError('REUSED_LEGACY_SUPPORT_IDENTITY_CHANGED')
 if value is not None and value['solution'].get('schema')=='source-route-ten-step-width-ladder/1':
  proof=load(run/'T04_PRIOR_WIDTH_COMPATIBILITY.json')
  if not proof['passed']or not proof['completed_width_fence']['passed']or proof['completed_t04_sha256']!=sha(run/'t04.json')or proof['connected_checkpoint_sha256']!=sha(run/'RAW_WIDTH_CHECKPOINT.json')or proof['legacy_checkpoint_sha256']!=sha(run.parent/'legacy/RAW_WIDTH_CHECKPOINT.json')or any(not row['passed']for row in proof['parts']):raise ValueError('REUSED_T04_PRIOR_COMPATIBILITY_CHANGED')
 store.verify_reads()
 return binding
