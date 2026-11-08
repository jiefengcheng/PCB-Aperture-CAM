"""The qualified T02 predecessor is authoritative for connected T05."""
from . import pipeline as p
from src import component_clearance as cc,t02_shared_gaps as gaps
from shapely.ops import unary_union


def bind(store):
 ctx=cc.ACTIVE
 if ctx is None:return None
 if getattr(ctx,'stage_entry_prior',None)is not None:return ctx.stage_entry_prior
 run=store.root.parent;path=run/'t02.json'
 # Standalone historical helpers and legacy stages keep their original contract.
 if not path.exists():return None
 value=p.load(path);proofs=[p.load(run/'audits/t02'/(mode+'.json'))for mode in('construct','1','2')]
 if any(proof!=proofs[0]for proof in proofs)or proofs[0]['status']!='PASS'or proofs[0]['candidate_sha256']!=p.digest(p.canonical(value)):raise ValueError('T05_QUALIFIED_T02_PREDECESSOR_REQUIRED')
 scene=p.validate_scene(store,value['output_scene_ref'])
 if scene['source_sha256']!=ctx.source_hash:raise ValueError('T05_ENTRY_SOURCE_CHANGED')
 _,material,_=p.operands(store,scene);owned=ctx.project(material)
 if set(owned)!=set(ctx.cores):raise ValueError('T05_ENTRY_OWNER_COVERAGE_CHANGED')
 for owner,g in owned.items():
  if not g.is_valid or g.is_empty or ctx.cores[owner].difference(g).area>1e-12:raise ValueError('T05_ENTRY_SOURCE_CORE_MISSING')
 from .native_component_checks_final import clearance
 physical=clearance(ctx.cores,owned);image=unary_union(list(owned.values()))
 from src.pin_separation import require
 pins=require(image,finished=True,scope='qualified_t05_stage_entry')
 shared=None if gaps.ACTIVE is None else gaps.complete(gaps.ACTIVE,image)
 proof=dict(schema='qualified-t05-stage-entry/1',source_sha256=ctx.source_hash,t02_candidate_sha256=p.digest(p.canonical(value)),scene_ref=value['output_scene_ref'],scene_sha256=p.digest(p.canonical(scene)),old_reference_binding_sha256=ctx.reservation_sha256,physical_clearance=physical,pin_separation=pins,shared_neighbor_gaps=shared,policy='Accepted T02 copper is mandatory. Older reference candidates are provenance only; no restoration of superseded growth.',geometry_changed=False)
 scope=getattr(ctx,'functional',None)
 if scope is not None:
  scope.register_scene(store,scene);channels=scope.project(material)
  from .channel_material import check_owned
  proof['functional_clearance']=check_owned(scope,channels)
  if not proof['functional_clearance']['passed']or scope.partial_pocket_failures(channels):raise ValueError('T05_ENTRY_FUNCTIONAL_CHECK_FAILED')
 if ctx.partial_pocket_failures(owned):raise ValueError('T05_ENTRY_PARTIAL_POCKET_FAILED')
 identity=p.digest(p.canonical(proof));ctx.reserved=owned;ctx.reservation_sha256=identity;ctx.binding=p.digest(p.canonical([ctx.binding,identity]));ctx.stage_entry_prior=proof
 if scope is not None:
  scope.reserved=channels;scope.reservation_sha256=identity;scope.binding=p.digest(p.canonical([scope.binding,identity]))
 return proof
