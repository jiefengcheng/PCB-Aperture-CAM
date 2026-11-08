"""Hash-bound incremental qualification from completed legacy predecessor stages."""
import argparse,ast,datetime,hashlib,importlib.util,json,os,subprocess,uuid
from pathlib import Path
from . import pipeline as p
from .guard import ROOT,seal
from .run import Coordinator,ORDER
from .workspace import configure

sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
load=lambda f:json.loads(Path(f).read_bytes())
DOWNSTREAM={'src/gerber_u05/guard.py','src/gerber_u05/run.py','src/gerber_u05/render.py','src/gerber_u05/legacy_export.py','src/gerber_u05/reference_recipe.py','src/u05_board/coverage.py','src/gerber_u05/legacy_prefix.py'}
DOWNSTREAM.update({'src/gerber_u05/prefix.py','src/gerber_u05/incremental.py'})
CONNECTED_COMPLETION={'src/component_clearance.py','src/component_voids.py','src/growth_void_remedy_v09.py','src/partial_pocket_remedy.py','src/gerber_u05/component_finish.py','src/gerber_u05/component_policy.py','src/gerber_u05/component_stages.py','src/gerber_u05/native_component_checks_final.py','src/gerber_u05/remaining_defects.py','src/gerber_u05/prior_copper.py','contracts/component_remedy/settings.json','contracts/growth_void/settings.json','src/u05_board/attachment_export.py','src/gerber_u05/width_adoption.py'}

def source_namespace(root,work):
 """A frozen app release has the same source authority as an evidence snapshot.

 The original native producer still hash-binds every executable dependency.
 This additionally checks the complete release manifest, including assets.
 """
 if '..'in root.parts:raise ValueError('LEGACY_ORIGINAL_SOURCE_NAMESPACE_INVALID')
 if root.is_relative_to(work/'evidence'):return
 if root.name!='source'or root.parent.parent!=work/'releases':raise ValueError('LEGACY_ORIGINAL_SOURCE_NAMESPACE_INVALID')
 manifest=root.parent/'SOURCE_MANIFEST.json'
 if not manifest.is_file():raise ValueError('LEGACY_RELEASE_MANIFEST_REQUIRED')
 value=load(manifest)
 if value.get('root')!=str(root)or not value.get('files'):raise ValueError('LEGACY_RELEASE_MANIFEST_CHANGED')
 for name,expected in value['files'].items():
  relative=Path(name)
  if relative.is_absolute()or'..'in relative.parts or sha(root/relative)!=expected:raise ValueError('LEGACY_RELEASE_SOURCE_CHANGED:'+name)

def t02_only_before_stage(stages,old):
 """Shared-gap geometry is first used by T02, never an adopted T02 result."""
 if any(stage in('t02','t05')for stage in stages):raise ValueError('SHARED_GAP_CHANGE_REQUIRES_FRESH_T02_T05')
 for stage in stages:
  ref=load(old/(stage+'.json'))['output_scene_ref'];file=old/'runtime/artifacts'/ref['artifact_id']
  if sha(file)!=ref['sha256']:raise ValueError('LEGACY_PRE_T02_SCENE_CHANGED')
  scene=load(file)
  if any(row.get('stage')=='t02'or row.get('shared_gap_state_ref')is not None for row in scene.get('lineage',[])):raise ValueError('LEGACY_PRE_T02_HAS_SHARED_GAP_STATE')

def preparation_class_delta_only(before,after,kind):
 """T05-only classes may change; shared constants and helpers may not."""
 classes={'GeometrySnapshot','OperandView'}if kind=='loaded_geometry'else{'SpatialQueries'}
 imports={'Mapping','MappingProxyType'}if kind=='loaded_geometry'else{'box','geometry_checksum'}
 def reduced(text):
  tree=ast.parse(text);nodes=[]
  for node in tree.body:
   if isinstance(node,ast.ClassDef)and node.name in classes:continue
   if isinstance(node,ast.ImportFrom):
    node.names=[name for name in node.names if name.name not in imports]
    if not node.names:continue
   nodes.append(node)
  tree.body=nodes;return ast.dump(tree,include_attributes=False)
 if reduced(before)!=reduced(after):raise ValueError('LEGACY_PREPARATION_POLICY_OR_HELPER_CHANGED:'+kind)

def export_metric_delta_only(before,after):
 """Only substitute the already-qualified complete native boundary metric."""
 class Indexed(ast.NodeTransformer):
  def visit_Call(self,node):
   self.generic_visit(node)
   if isinstance(node.func,ast.Attribute)and node.func.attr=='hausdorff_distance'and len(node.args)==1 and not node.keywords:
    return ast.Call(func=ast.Name(id='boundary_distance',ctx=ast.Load()),args=[node.func.value,*node.args],keywords=[])
   return node
 def reduced(text,convert):
  tree=ast.parse(text);tree.body=[n for n in tree.body if not(isinstance(n,ast.ImportFrom)and n.module=='src.native_boundary_metric'and len(n.names)==1 and n.names[0].name=='distance'and n.names[0].asname=='boundary_distance')]
  return ast.dump(Indexed().visit(tree)if convert else tree,include_attributes=False)
 if reduced(before,True)!=reduced(after,False):raise ValueError('LEGACY_EXPORT_METRIC_POLICY_OR_GEOMETRY_CHANGED')

def pipeline_same(before,after,through='t02'):
 def reduced(text):
  tree=ast.parse(text);tree.body=[n for n in tree.body if not(isinstance(n,ast.FunctionDef)and(n.name=='empty_t02'or(through=='t04'and n.name=='run_t02')))]
  for node in tree.body:
   if isinstance(node,ast.FunctionDef)and node.name=='run_t02':
    node.body=[n for n in node.body if ast.dump(n,include_attributes=False)!=ast.dump(ast.parse('if not ids:return empty_t02(store,scene)').body[0],include_attributes=False)]
  return ast.dump(tree,include_attributes=False)
 if reduced(before)!=reduced(after):raise ValueError('LEGACY_PREFIX_PIPELINE_CHANGED')

def partial_reload_delta_only(before,after):
 old="if channel not in scope.cores or scope.owner(sid)!=channel:raise ValueError('PARTIAL_POCKET_FUNCTIONAL_OWNER_BINDING_CHANGED')"
 new="if channel not in scope.cores or md.get('original_channel_id')!=channel or scope.ids.get(sid,(channel,))!=(channel,) or md.get('original_channel_witness_sha256')!=digest(to_wkb(scope.cores[channel])):raise ValueError('PARTIAL_POCKET_FUNCTIONAL_OWNER_BINDING_CHANGED')"
 if before.count(old)!=1 or ast.dump(ast.parse(before.replace(old,new)),include_attributes=False)!=ast.dump(ast.parse(after),include_attributes=False):raise ValueError('LEGACY_PARTIAL_RELOAD_DELTA_NOT_ISOLATED')

def reservation_witness_delta_only(before,after):
 old="metadata=dict(original_owner_id=own,original_channel_id=channel,original_source_sha256=ctx.source_hash,approved_partial_pockets=[spec])"
 new="metadata=dict(original_owner_id=own,original_channel_id=channel,original_channel_witness_sha256=p.digest(p.to_wkb(ctx.functional.cores[channel])),original_source_sha256=ctx.source_hash,approved_partial_pockets=[spec])"
 if before.count(old)!=1 or ast.dump(ast.parse(before.replace(old,new)),include_attributes=False)!=ast.dump(ast.parse(after),include_attributes=False):raise ValueError('LEGACY_RESERVATION_WITNESS_DELTA_NOT_ISOLATED')

def t04_eviction_delta_only(before,after):
 old='self.bytes -= self.cache.popitem(last=False)[1]'
 new='self.bytes -= self.cache.popitem(last=False)[1][1]'
 if before.count(old)!=1 or ast.dump(ast.parse(before.replace(old,new)),include_attributes=False)!=ast.dump(ast.parse(after),include_attributes=False):raise ValueError('LEGACY_T04_EVICTION_DELTA_NOT_ISOLATED')

def pin_eviction_delta_only(before,after):
 old='self.weight-=self.cache.popitem(last=False)[1]'
 new='self.weight-=self.cache.popitem(last=False)[1][1]'
 if before.count(old)!=1 or ast.dump(ast.parse(before.replace(old,new)),include_attributes=False)!=ast.dump(ast.parse(after),include_attributes=False):raise ValueError('LEGACY_PIN_EVICTION_DELTA_NOT_ISOLATED')

def t02_attribution_worker_delta_only(before,after):
 old=""" if name in('t04','t02'):
  store=p.Store(run/'runtime');checked_scene=store.get_json(value['output_scene_ref'],kind='scene');_,material,_=p.operands(store,checked_scene)
  width_proof=require_width_fence(p.unary_union(list(material.values())),scope=name+'_complete')
  if width_proof is not None:value=dict(value,t04_width_fence=width_proof)
"""
 new=old.replace("if name in('t04','t02'):","if name=='t04':")+""" elif name=='t02':
  from .width_stage_constraints import require_t02
  store=p.Store(run/'runtime');width_proof=require_t02(store,p.load(run/'t04.json')['output_scene_ref'],value)
  if width_proof is not None:value=dict(value,t04_width_fence=width_proof)
"""
 if before.count(old)!=1 or after.count(new)!=1 or ast.dump(ast.parse(before),include_attributes=False)!=ast.dump(ast.parse(after.replace(new,old)),include_attributes=False):raise ValueError('LEGACY_T02_ATTRIBUTION_DELTA_NOT_ISOLATED')

def t05_support_delta_only(before,after):
 old=""" support=owner.intersection(domain.buffer(-NATIVE_OWNER_OVERLAP_MM,quad_segs=64))
 region=support.union(addition);target=owner.union(addition)
"""
 new=""" window=domain.buffer(-NATIVE_OWNER_OVERLAP_MM,quad_segs=64)
 support=owner.intersection(window);target=owner.union(addition)
 region=target.intersection(window).union(addition)
"""
 if before.count(old)!=1 or ast.dump(ast.parse(before.replace(old,new)),include_attributes=False)!=ast.dump(ast.parse(after),include_attributes=False):raise ValueError('LEGACY_T05_SUPPORT_DELTA_NOT_ISOLATED')

def prove_no_retained_partials(old,stages):
 # Inspect every retained stage-entry/output scene, not only raw source rows.
 # The changed registration branch is unreachable in all retained operations.
 refs=[]
 for stage in stages:
  value=load(old/(stage+'.json'));refs.append(value['output_scene_ref'])
  if 'plan'in value:refs.append(value['plan']['scene_ref'])
 for ref in refs:
  scene=load(old/'runtime/artifacts'/ref['artifact_id'])
  if sha(old/'runtime/artifacts'/ref['artifact_id'])!=ref['sha256']:raise ValueError('LEGACY_PARTIAL_SCENE_BINDING_CHANGED')
  if any(row['metadata'].get('approved_partial_pockets')for row in scene['objects']):raise ValueError('LEGACY_PARTIAL_RELOAD_REQUIRES_FRESH_STAGE')
 return dict(status='NO_APPROVED_PARTIAL_BRANCH_EXECUTED',scene_refs_checked=len(refs))

def original_routes(code,rows):
 spec=importlib.util.spec_from_file_location('qualified_prefix_route_definition',code);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 families={}
 for row in rows:
  if row['kind']!='stroke':continue
  md=row['metadata'];families.setdefault(tuple(md['aperture_family']),[]).append(dict(source_id=row['source_id'],kind=md['route_kind'],width_mm=md['minimum_caliper_mm'],endpoints_decimal_mm=md['endpoints_decimal_mm'],route_points_mm=md['route_points_mm'],source_wkb_sha256=row['original_ref']['sha256']))
 return sorted([path for values in families.values()for path in module.junction_source_paths(values,[v['source_id']for v in values])],key=lambda x:x['path_id'])

def inspect(old,through):
 old=Path(old);work=configure()
 if not old.is_absolute()or'..'in old.parts or old.name!='legacy'or not any(old.is_relative_to(work/'operator_routes'/namespace)for namespace in('gerber_u05','gerber_u05_incremental_legacy','gerber_u05_ladder_combined')):raise ValueError('EXPLICIT_NATIVE_LEGACY_PREFIX_REQUIRED')
 if through not in('t03','t04','t02','t05'):raise ValueError('LEGACY_PREFIX_BOUNDARY_UNSUPPORTED')
 stages=ORDER[:ORDER.index(through)+1];binding=load(old/'PRODUCER_BINDING.json');state=load(old.parent/'STATUS.current.json');producer_sha=sha(old/'PRODUCER_BINDING.json');original_root=Path(os.path.commonpath(list(binding['files'])))
 inherited=None;inherited_stages=[];inherited_producers={};records=dict(state['checks']);source_roots=[str(original_root)]
 if(old/'REUSED_LEGACY_BINDING.json').exists():
  if binding['job_inputs'].get(str(old/'REUSED_LEGACY_BINDING.json'))!=sha(old/'REUSED_LEGACY_BINDING.json'):raise ValueError('INHERITED_LEGACY_AUTHORITY_CHANGED')
  inherited=load(old/'REUSED_LEGACY_BINDING.json')['original'];fresh=inspect(inherited['original_run'],inherited['through'])
  if {k:fresh.get(k)for k in inherited if k!='code_dependency_changes'}!={k:v for k,v in inherited.items()if k!='code_dependency_changes'}:raise ValueError('INHERITED_LEGACY_PREFIX_CHANGED')
  for name,expected in inherited['files'].items():
   if sha(old/name)!=expected:raise ValueError('INHERITED_LEGACY_COPY_CHANGED')
  inherited_producers=fresh['stage_producer_bindings']
  records=dict(inherited['original_checks'],**records);inherited_stages=inherited['stages'];source_roots.extend(fresh.get('original_source_roots',[fresh['original_source_root']]))
 source_namespace(Path(original_root),work)
 for name,expected in {**binding['files'],**binding['job_inputs']}.items():
  if sha(name)!=expected:raise ValueError('LEGACY_ORIGINAL_PRODUCER_OR_INPUT_CHANGED:'+name)
 if sha(old/'source.json')!=binding['source_binding_sha256']:raise ValueError('LEGACY_ORIGINAL_SOURCE_BINDING_CHANGED')
 keys=[];files={'source.json',*(stage+'.json'for stage in stages)};stage_producers={}
 if 't04'in stages:
  raw=load(old/'RAW_WIDTH_CHECKPOINT.json');final=load(old/'t04.json')
  if raw!={k:v for k,v in final.items()if k not in('t04_width_fence','pin_separation')}:raise ValueError('LEGACY_RAW_WIDTH_CHECKPOINT_CHANGED')
  files.add('RAW_WIDTH_CHECKPOINT.json')
 for stage in stages:
  proofs=[load(old/'audits'/stage/(m+'.json'))for m in('construct','1','2')]
  expected_producer=inherited_producers[stage]if stage in inherited_stages else producer_sha
  if proofs[0]!=proofs[1]or proofs[0]!=proofs[2]or proofs[0]['status']!='PASS'or proofs[0]['producer_binding_sha256']!=expected_producer or proofs[0]['candidate_sha256']!=sha(old/(stage+'.json')):raise ValueError('LEGACY_PREFIX_STAGE_PROOF_CHANGED:'+stage)
  stage_producers[stage]=expected_producer
  for mode in('construct','1','2'):
   key='legacy_'+stage+'_'+mode;record=records.get(key,{})
   if record.get('status')!='PASS'or record.get('returncode')!=0:raise ValueError('LEGACY_PREFIX_NATIVE_OPERATION_INCOMPLETE:'+key)
   keys.append(key);files.add('audits/'+stage+'/'+mode+'.json')
  if records['legacy_'+stage+'_1']['pid']==records['legacy_'+stage+'_2']['pid']:raise ValueError('LEGACY_PREFIX_EVALUATIONS_NOT_SEPARATE')
  files.add('audits/'+stage+'/proof.json')
 supplements=[load(old/'audits/t01'/('supplement_'+m+'.json'))for m in('1','2')]
 if supplements[0]!=supplements[1]or supplements[0]['status']!='PASS'or supplements[0]['stage_result_sha256']!=sha(old/'t01.json')or supplements[0]['source_sha256']!=load(old/'source.json')['source_ref']['sha256']or supplements[0]['addendum_producer_sha256']!=sha(original_root/'src/gerber_u05/t01_complete_audit.py'):raise ValueError('LEGACY_PREFIX_T01_SUPPLEMENT_CHANGED')
 if records['legacy_t01_supplement_1']['pid']==records['legacy_t01_supplement_2']['pid']:raise ValueError('LEGACY_PREFIX_SUPPLEMENTS_NOT_SEPARATE')
 for mode in('1','2'):
  key='legacy_t01_supplement_'+mode;record=records[key]
  if record['status']!='PASS'or record['returncode']!=0:raise ValueError('LEGACY_PREFIX_T01_SUPPLEMENT_INCOMPLETE')
  keys.append(key);files.add('audits/t01/supplement_'+mode+'.json')
 # Retain every reachable immutable native operand and search witness.
 seen=set()
 def visit(value):
  if isinstance(value,dict):
   if set(value)=={'artifact_id','sha256'}:
    aid=value['artifact_id']
    if aid in seen:return
    if aid.split(':',1)[-1]!=value['sha256']or'/'in aid:raise ValueError('LEGACY_ARTIFACT_REFERENCE_INVALID')
    file=old/'runtime/artifacts'/aid;body=file.read_bytes()
    if p.digest(body)!=value['sha256']:raise ValueError('LEGACY_PREFIX_ARTIFACT_CHANGED:'+aid)
    seen.add(aid);files.add('runtime/artifacts/'+aid)
    if body[:1]in(b'{',b'['):
     try:visit(json.loads(body))
     except json.JSONDecodeError:pass
   else:
    for item in value.values():visit(item)
  elif isinstance(value,list):
   for item in value:visit(item)
 for name in list(files):visit(load(old/name))
 source=load(old/'source.json');scene=json.loads((old/'runtime/artifacts'/source['scene_ref']['artifact_id']).read_bytes());known=set();changes=[]
 for name,expected in binding['files'].items():
  file=Path(name)
  if not file.is_relative_to(original_root):raise ValueError('LEGACY_PRODUCER_OUTSIDE_SOURCE')
  relative=file.relative_to(original_root).as_posix();known.add(relative)
  if relative=='SOURCE_REVISION.json':continue
  current=ROOT/relative;actual=sha(current)
  if actual==expected:continue
  from .prefix import WIDTH_CORRECTION
  if relative in WIDTH_CORRECTION and WIDTH_CORRECTION[relative]==(expected,actual):
   # Only the exact qualified positive-operand subtraction/report correction.
   # Above, every retained stage already proved PASS under the old checker;
   # all candidate geometry, source identities and native stage proofs remain
   # unchanged. Connected T04 is always freshly constructed after this legacy
   # reference. This is not permission to retain a failed width decision.
   changes.append(dict(path=relative,before_sha256=expected,after_sha256=actual,scope='EXACT_E10FCE9_CHECKER_DELTA; ORIGINAL_PASS_GEOMETRY_UNCHANGED'));continue
  if relative=='src/gerber_u05/pipeline.py':
   pipeline_same(file.read_text(),current.read_text(),through=through)
   if through=='t02'and not any(r['kind']=='rectangle'for r in scene['objects']):raise ValueError('EMPTY_T02_REQUIRES_FRESH_T02_VERIFICATION')
  elif relative=='src/t02_shared_gaps.py':
   t02_only_before_stage(stages,old)
  elif relative=='src/gerber_u05/source_assembly.py':
   # Assembly runs fresh in three workers before prepare() compares the exact
   # prepared source and its complete native build to this retained prefix.
   if not(old/'SOURCE_ASSEMBLY_BINDING.json').exists():raise ValueError('LEGACY_SOURCE_ASSEMBLY_AUTHORITY_REQUIRED')
  elif relative=='src/source_junction_paths.py':
   if original_routes(file,scene['objects'])!=original_routes(current,scene['objects']):raise ValueError('LEGACY_PREFIX_SOURCE_ROUTES_CHANGED')
  elif relative=='src/gerber_u05/worker.py':
   if through in('t03','t04'):t02_attribution_worker_delta_only(file.read_text(),current.read_text())
   else:
    from .width_adoption import worker_same
    worker_same(file.read_text(),current.read_text())
  elif relative=='src/component_clearance.py'and through in('t02','t05'):
   partial_reload_delta_only(file.read_text(),current.read_text());prove_no_retained_partials(old,stages)
  elif relative=='src/gerber_u05/component_stages.py'and through in('t02','t05'):
   reservation_witness_delta_only(file.read_text(),current.read_text());prove_no_retained_partials(old,stages)
  elif relative=='src/u05_board/coverage.py'and through=='t05':raise ValueError('LEGACY_T05_ADAPTER_CHANGE_REQUIRES_FRESH_T05')
  elif relative=='src/stage_abi/loaded_geometry.py':
   # The legacy pipeline first constructs a GeometrySnapshot inside T05.
   # No T01/T03/T04/T02 geometry or completed T05 result may be replaced by
   # a decoded-cache correction. T05 is freshly constructed and evaluated.
   if through=='t05':raise ValueError('LEGACY_T05_SNAPSHOT_CHANGE_REQUIRES_FRESH_T05')
   preparation_class_delta_only(file.read_text(),current.read_text(),'loaded_geometry')
  elif relative=='src/stage_abi/spatial_queries.py':
   # Earlier preparation imports this module's unchanged budget constants;
   # the SpatialQueries class itself is instantiated by T05 only.
   if through=='t05':raise ValueError('LEGACY_T05_SPATIAL_CHANGE_REQUIRES_FRESH_T05')
   preparation_class_delta_only(file.read_text(),current.read_text(),'spatial_queries')
  elif relative in('src/pcb_data_abi/board_geometry.py','src/gerber_u05/exporter.py'):
   # Gerber geometry stages retain no native encoding operation. Quantization,
   # every contour, all tolerances and metric definitions stay identical; only
   # the established all-vertex distance service evaluates export comparisons.
   export_metric_delta_only(file.read_text(),current.read_text())
  elif relative=='src/t04_incremental.py'and through=='t03':
   # This module is first called by T04. Retain only T01/T03 after the exact
   # cache-accounting correction; no geometry/policy change receives reuse.
   t04_eviction_delta_only(file.read_text(),current.read_text())
  elif relative=='src/pin_separation.py'and through=='t03':
   # The original bookkeeping branch unconditionally raised if eviction ran.
   # Completed PASS operations therefore did not execute that branch. Only
   # its exact size-index correction is allowed; all slot geometry is identical.
   pin_eviction_delta_only(file.read_text(),current.read_text())
  elif relative=='src/gerber_u05/export_absorption.py'and through in('t03','t04','t02'):
   # Only the T05 support recipe changes. It is called by T05 completion and
   # export; neither operation belongs to this retained predecessor prefix.
   t05_support_delta_only(file.read_text(),current.read_text())
  elif relative in CONNECTED_COMPLETION:
   # Legacy stages through T04 initialize ACTIVE=None and never execute the
   # connected owner completion, partial-pocket policy or export obligations.
   # T02/T05 remain fresh under this extension; no broad later reuse is allowed.
   if through!='t04':raise ValueError('CONNECTED_POLICY_CHANGE_REQUIRES_FRESH_LEGACY_T02_T05')
  elif relative not in DOWNSTREAM:raise ValueError('LEGACY_PREFIX_UPSTREAM_DEPENDENCY_CHANGED:'+relative)
  changes.append(dict(path=relative,before_sha256=expected,after_sha256=actual))
 from .guard import producer_files
 extras={file.relative_to(ROOT).as_posix()for file in producer_files()}-known
 allowed_extras={'src/gerber_u05/legacy_prefix.py','src/gerber_u05/width_adoption.py','src/partial_pocket_remedy.py','SOURCE_REVISION.json'}
 # A new intake-only helper cannot authorize changed retained geometry: all
 # three fresh source-assembly workers and the exact prepared-source/build
 # comparison in prepare() still precede adoption of the old native prefix.
 if(old/'SOURCE_ASSEMBLY_BINDING.json').exists():allowed_extras.add('src/gerber_u05/pcb_artwork_scope.py')
 if through in('t03','t04'):allowed_extras.add('src/gerber_u05/width_stage_constraints.py')
 if extras-allowed_extras:raise ValueError('LEGACY_PREFIX_UNDECLARED_PRODUCER')
 return dict(schema='verified-legacy-native-prefix/1',through=through,stages=list(stages),stage_producer_bindings=stage_producers,retained_operation_count=len(keys),original_run=str(old),original_source_root=str(original_root),original_source_roots=sorted(set(source_roots)),original_producer_binding_sha256=producer_sha,source_binding_sha256=binding['source_binding_sha256'],source_sha256=source['source_ref']['sha256'],original_checks={key:records[key]for key in keys},files={name:sha(old/name)for name in sorted(files)},code_dependency_changes=changes,original_route_completion='NOT_CLAIMED; only completed prefix operations retained')

def verify(run):
 run=Path(run);path=run/'REUSED_LEGACY_BINDING.json'
 if not path.exists():return None
 bound=load(path);current=inspect(bound['original']['original_run'],bound['original']['through'])
 if current!=bound['original']:raise ValueError('RETAINED_LEGACY_PREFIX_CHANGED')
 if sha(run/'source.json')!=current['source_binding_sha256']:raise ValueError('RETAINED_LEGACY_SOURCE_CHANGED')
 for name,expected in current['files'].items():
  if sha(run/name)!=expected:raise ValueError('RETAINED_LEGACY_COPY_CHANGED:'+name)
 return bound

class IncrementalCoordinator(Coordinator):
 def __init__(self,job,old,through):
  super().__init__(job);self.old=Path(old);self.prefix=inspect(old,through);self.legacy_authority=dict(original_run=str(old),through=through)
  self.state.update(source_only=False,qualification_mode='INCREMENTAL_REUSED_LEGACY_PREFIX',reused_operations=self.prefix['retained_operation_count'])
 def prepare(self,run,raw,inventory,legacy=False):
  inventory=dict(inventory,qualification_mode='INCREMENTAL_REUSED_LEGACY_PREFIX',reused_native_operations=self.prefix['retained_operation_count'])
  if not legacy:return super().prepare(run,raw,inventory,False)
  if p.digest(raw)!=self.prefix['source_sha256']:raise ValueError('FRESH_INTAKE_DIFFERS_FROM_RETAINED_PREFIX')
  previous_inventory=load(self.old/'input_inventory.json')
  if any(inventory[key]!=previous_inventory[key]for key in('input_directory','files','ignored','selected')):raise ValueError('FRESH_INPUT_DIRECTORY_CUSTODY_DIFFERS_FROM_PREFIX')
  run.mkdir();subprocess.run(['cp','-cR',str(self.old/'runtime'),str(run/'runtime')],check=True)
  (run/'source_snapshot').mkdir();(run/'source_snapshot/top.art.gbr').write_bytes(raw);p.save(run/'input_inventory.json',inventory)
  if p.canonical(p.build_source(p.Store(run/'runtime'),raw))!=p.canonical(load(self.old/'source.json')):raise ValueError('FRESH_SOURCE_RECONSTRUCTION_DIFFERS')
  for name in self.prefix['files']:
   if name.startswith('runtime/'):continue
   target=run/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((self.old/name).read_bytes())
  p.save(run/'LEGACY_REFERENCE_JOB.json',dict(schema='fresh-legacy-reservation-reference/1',scope='Fresh source intake with explicitly retained verified native predecessor stages'))
  from .storage_encoding import policy as storage_policy
  p.save(run/'STORAGE_ENCODING.json',storage_policy())
  # Fresh assembly and pin intent remain explicit job inputs after prefix
  # adoption. Omitting these would silently change the following T04 profile.
  if(self.job/'assembly').exists():
   from .source_assembly import attach
   attach(run,self.job/'assembly')
  from .pin_policy import capture as capture_pin
  capture_pin(run,inventory)
  p.save(run/'REUSED_LEGACY_BINDING.json',dict(original=self.prefix));seal(run,'fresh-legacy-reservation-reference/1');verify(run)
 def stages(self,run,legacy=False):
  if not legacy:return super().stages(run,False)
  for stage in ORDER:
   if stage not in self.prefix['stages']:
    self.execute(run,stage,['construct']);self.execute(run,stage,['1','2'])
   proofs=[p.load(run/'audits'/stage/(m+'.json'))for m in('construct','1','2')]
   if len({p.digest(p.canonical(v))for v in proofs})!=1:raise ValueError('PAIRED_STAGE_PROOFS_DIFFER:'+stage)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--input-dir',required=True,type=Path);parser.add_argument('--gerber',required=True);parser.add_argument('--retained-legacy-run',required=True,type=Path);parser.add_argument('--through',required=True,choices=['t03','t04','t02','t05']);args=parser.parse_args()
 if not args.input_dir.is_absolute():parser.error('explicit absolute input directory required')
 prefix=inspect(args.retained_legacy_run,args.through)
 if load(args.retained_legacy_run.parent/'STATUS.current.json')['status']=='HALTED'and not any(row['path']in{'src/gerber_u05/pipeline.py','src/source_junction_paths.py','src/u05_board/coverage.py','src/gerber_u05/reference_recipe.py','src/gerber_u05/legacy_export.py','src/component_clearance.py','src/t04_incremental.py','src/gerber_u05/worker.py','src/t02_shared_gaps.py'}for row in prefix['code_dependency_changes']):raise ValueError('SAME_IMPLEMENTATION_FAILED_JOB_CANNOT_RETRY')
 work=configure();parent=work/'operator_routes/gerber_u05_incremental_legacy';parent.mkdir(exist_ok=True);job=parent/(datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex);job.mkdir();coordinator=IncrementalCoordinator(job,args.retained_legacy_run,args.through)
 try:coordinator.generate(args.input_dir,args.gerber)
 except BaseException as error:
  coordinator.state.update(status='HALTED',error=str(error),remaining_operations='NOT_RUN; retained original job unchanged');coordinator.record();p.save(job/'HALTED.json',coordinator.state);raise

if __name__=='__main__':main()
