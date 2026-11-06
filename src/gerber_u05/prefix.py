"""Strict adoption of completed native stages for incremental qualification."""
import ast,hashlib,json
from pathlib import Path
STAGES=('t01','t03','t04','t02')
DOWNSTREAM={'src/gerber_u05/guard.py','src/gerber_u05/contours.py','src/gerber_u05/exporter.py','src/gerber_u05/render.py','src/gerber_u05/remaining_defects.py'}
EQUIVALENT={
 'src/component_voids.py':('46f6afbfd029e97a6409ecdc4b20a3c1511f394e02187ea72c9fd2ed762d49b7','db0dbae5d433b02dbe10715f772e0c46bc4144ea96050f62a8ed836d1d28246a','Only alternate global-overlay diagnostic counting uses existing areal-context extraction. Every physical geometry/source/clearance/topology check is unchanged. Valid polygon reports are identical; retained upstream reports prove that path. All positive faces retained; actual candidate remains strict polygonal copper.'),
 'src/native_boundary_metric.py':('b9a1eae932ed66667de7adf52d307b3577c0175c7d2173b29112803dc6e61b83','d84e8392b7b4f3d28c7aa5df3838532902ff99e87dc53038c0a794ac17a84cc7','Valid identical-WKB Hausdorff is exactly zero; all other indexed/native metric paths unchanged. Dedicated valid/invalid and native parity tests retained.'),
 'tools/pcb_workspace.py':('82005433b3d08a17ae9c89c4d8c022602cab4ac754e8688afdc583112a98b291','068fc453f38f86984860adb4f553a9b0f05fd10172e6f5b9ae6660afd6329ecd','Verified external source-snapshot storage namespace only; 88 native app regressions and explicit no-fallback tests retained.')}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())

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
 allowed=ast.dump(ast.parse("if name=='t05':p.save(run/'raw_checkpoints'/('t05_'+os.environ.get('U05_WORKER_MODE','unit')+'.json'),value)").body[0],include_attributes=False)
 tree=ast.parse(after)
 for node in tree.body:
  if isinstance(node,ast.FunctionDef)and node.name=='compute':
   node.body=[statement for statement in node.body if ast.dump(statement,include_attributes=False)!=allowed]
 if ast.dump(ast.parse(before),include_attributes=False)!=ast.dump(tree,include_attributes=False):raise ValueError('REUSED_UPSTREAM_WORKER_CHANGED')
 return dict(status='UNCHANGED_UPSTREAM_AST',changed_scope='T05-only raw-result evidence capture after its complete native geometry verification')

def verify_code(original,root,old_root):
 results=[];root=Path(root);old_root=Path(old_root)
 for name,expected in original['files'].items():
  path=Path(name)
  if not path.is_relative_to(old_root):raise ValueError('REUSED_PRODUCER_OUTSIDE_DECLARED_SOURCE')
  if sha(path)!=expected:raise ValueError('REUSED_ORIGINAL_PRODUCER_CHANGED:'+name)
  relative=path.relative_to(old_root).as_posix();current=root/relative
  if relative=='SOURCE_REVISION.json':continue
  actual=sha(current)
  if actual==expected:continue
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
   if upstream(path.read_text())!=upstream(current.read_text()):raise ValueError('REUSED_UPSTREAM_EXPORT_SUPPORT_CHANGED')
   results.append(dict(path=relative,scope='Only supported_region changed; called exclusively for T05 junctions'));continue
  if relative in DOWNSTREAM:
   results.append(dict(path=relative,scope='T05/export/verification only; not an upstream generation dependency'));continue
  proof=EQUIVALENT.get(relative)
  if proof is not None and(expected,actual)==proof[:2]:
   results.append(dict(path=relative,proof=proof[2],before_sha256=expected,after_sha256=actual));continue
  raise ValueError('REUSED_UPSTREAM_DEPENDENCY_CHANGED:'+relative)
 return results

def verify(run):
 from . import pipeline as p
 from .guard import ROOT
 run=Path(run);path=run/'REUSED_PREFIX_BINDING.json'
 if not path.exists():return None
 binding=load(path);original=load(run/'prefix_evidence/ORIGINAL_PRODUCER_BINDING.json')
 if sha(run/'prefix_evidence/ORIGINAL_PRODUCER_BINDING.json')!=binding['original_producer_binding_sha256']:raise ValueError('REUSED_PRODUCER_BINDING_CHANGED')
 verify_code(original,ROOT,binding['original_source_root'])
 if sha(run/'source.json')!=original['source_binding_sha256']:raise ValueError('REUSED_PREFIX_SOURCE_CHANGED')
 for relative,expected in binding['files'].items():
  file=run/relative
  if not file.is_relative_to(run)or sha(file)!=expected:raise ValueError('REUSED_PREFIX_EVIDENCE_CHANGED:'+relative)
 for stage in STAGES:
  candidate=sha(run/(stage+'.json'));proofs=[load(run/'audits'/stage/(mode+'.json'))for mode in('construct','1','2')]
  if proofs[0]!=proofs[1]or proofs[0]!=proofs[2]:raise ValueError('REUSED_PAIRED_PROOFS_DIFFER:'+stage)
  if proofs[0]['status']!='PASS'or proofs[0]['candidate_sha256']!=candidate or proofs[0]['producer_binding_sha256']!=binding['original_producer_binding_sha256']:raise ValueError('REUSED_STAGE_PROOF_CHANGED:'+stage)
  for mode in('construct','1','2'):
   key='connected_'+stage+'_'+mode;record=binding['original_checks'][key]
   if record['status']!='PASS'or record['returncode']!=0:raise ValueError('REUSED_NATIVE_PROCESS_DID_NOT_PASS:'+key)
  if binding['original_checks']['connected_'+stage+'_1']['pid']==binding['original_checks']['connected_'+stage+'_2']['pid']:raise ValueError('REUSED_EVALUATIONS_NOT_SEPARATE_PROCESSES')
 # Preserve and hash-revalidate every original search witness, without solving
 # unchanged geometry again. All new T05 and actual-file predicates stay fresh.
 value=load(run/'t04.json');solution=value['solution'];evaluations=value['evaluations'];store=p.Store(run/'runtime')
 if len(evaluations)!=solution['evaluation_count']or len(solution['evaluations'])!=len(evaluations):raise ValueError('REUSED_COMPLETE_WIDTH_SEARCH_LEDGER_MISSING')
 for index,(row,witness)in enumerate(zip(evaluations,solution['evaluations'])):
  report=store.get_json(row['report_ref'],kind='width-check')
  if witness['index']!=index or witness['scales']!=row['scales']or witness['report_sha256']!=row['report_ref']['sha256']or witness['passed']!=report['passed']or witness['failures']!=report['failures']:raise ValueError('REUSED_WIDTH_SEARCH_WITNESS_CHANGED')
 return binding
