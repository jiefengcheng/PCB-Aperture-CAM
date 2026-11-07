"""Shared bounded execution and exact scene-output custody for stage adapters."""
import time
from shapely import to_wkb
from .contracts import closed,fail
from .scene import geometry,composed,validate_scene
from .store import canonical
from .journal import ACTIVE

BASE_BOUNDS={'max_source_objects','max_targets','max_evaluations','max_output_bytes','max_seconds'}
def bounds_check(bounds,scene,selection,*,extra=()):
 closed(bounds,BASE_BOUNDS|set(extra),'execution bounds')
 if any(type(bounds[k]) is not int or bounds[k]<=0 for k in BASE_BOUNDS):fail('FINITE_POSITIVE_BOUNDS_REQUIRED','execution bounds')
 ids=selection['source_ids']
 if type(ids) is not list or any(type(x) is not str for x in ids) or not ids or len(set(ids))!=len(ids) or len(ids)>bounds['max_targets'] or len(scene['objects'])>bounds['max_source_objects']:fail('SCOPE_LIMIT_REACHED','selection/source count')
 if not set(ids)<={r['source_id'] for r in scene['objects']}:fail('SELECTION_NOT_FOUND','source_ids')

class Budget:
 def __init__(self,bounds):self.bounds=bounds;self.started=time.monotonic();self.evaluations=0;self.output_bytes=0;self.journal=ACTIVE.get()
 def evaluation(self):
  if (self.journal.elapsed() if self.journal is not None else time.monotonic()-self.started)>self.bounds['max_seconds']:fail('BUDGET_EXHAUSTED','wall time')
  if self.evaluations>=self.bounds['max_evaluations']:fail('BUDGET_EXHAUSTED','evaluations')
  self.evaluations+=1
 def output(self,blob):
  self.output_bytes+=len(blob)
  if self.output_bytes>self.bounds['max_output_bytes']:fail('BUDGET_EXHAUSTED','output bytes')

def operands(store,scene):
 rows={r['source_id']:r for r in scene['objects']}
 return rows,{k:geometry(store,r['geometry_ref']) for k,r in rows.items()},{k:geometry(store,r['original_ref']) for k,r in rows.items()}

def output_scene(store,scene,plan,*,replacements=None,additions=(),metadata=None,shared_gap_state_ref=None):
 replacements=replacements or {};metadata=metadata or {};objects=[];known={r['source_id'] for r in scene['objects']}
 if not set(replacements)<=known or not set(metadata)<=known:fail('SOURCE_IDENTITIES_INVALID','replacement/metadata')
 for row in scene['objects']:
  updated=dict(row);sid=row['source_id']
  if sid in replacements:store.get(replacements[sid],kind='geometry');updated['geometry_ref']=replacements[sid]
  if sid in metadata:updated['metadata']=metadata[sid]
  objects.append(updated)
 for row in additions:
  if row['source_id'] in known:fail('DERIVED_SOURCE_ID_CONFLICT',row['source_id'])
  known.add(row['source_id']);objects.append(row)
 lineage=dict(stage=plan['stage'],predecessor_ref=plan['scene_ref'],policy_ref=plan['policy_ref'],implementation=plan['implementation'],plan_ref=store.put_json('plan',plan))
 if shared_gap_state_ref is not None:
  if plan['stage']!='t02':fail('SHARED_GAP_STATE_STAGE_INVALID','Only T02 establishes shared gaps')
  state=store.get_json(shared_gap_state_ref,kind='shared-gap-state')
  if state.get('source_sha256')!=scene['source_sha256']:fail('SHARED_GAP_STATE_SOURCE_CHANGED','Frozen T02 source')
  lineage['shared_gap_state_ref']=shared_gap_state_ref
 result=dict(scene,objects=objects,lineage=scene['lineage']+[lineage],acceptance=dict(owner='PENDING',independent='NOT_RUN',native_electrical_manufacturing='NOT_ESTABLISHED'))
 reference=store.put_json('scene',result);return reference,result

def check_output(store,scene,plan,candidate,*,replacements=None,additions=(),metadata=None,shared_gap_state_ref=None):
 expected_ref,expected=output_scene(store,scene,plan,replacements=replacements,additions=additions,metadata=metadata,shared_gap_state_ref=shared_gap_state_ref)
 actual=validate_scene(store,candidate['output_scene_ref'])
 if actual!=expected or candidate['output_scene_ref']!=expected_ref:fail('OUTPUT_SCENE_BINDING_MISMATCH','complete source map and lineage')
 if store.get(candidate['before_ref'],kind='geometry')!=to_wkb(composed(store,scene)) or store.get(candidate['after_ref'],kind='geometry')!=to_wkb(composed(store,expected)):fail('SOURCE_RECONSTRUCTION_MISMATCH','cumulative scenes')
 return expected
