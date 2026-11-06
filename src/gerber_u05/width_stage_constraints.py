"""Keep qualified T02 pads separate from frozen trace-width decisions.

Ordinary source rectangles retain their existing, independently verified T02
contract. Every pre-existing trace body stays byte-identical. Inclusive fills
remain complete logical proposals under the same frozen width guard.
"""
from shapely.affinity import scale
from shapely.geometry import box
from src import t04_width_fence as fence
from . import pipeline as p


def require_t02(store,predecessor_ref,value):
 if fence.ACTIVE is None:raise ValueError('T04_FROZEN_WIDTH_RULE_REQUIRED_FOR_T02')
 before=store.get_json(predecessor_ref,kind='scene')
 states=[r['t04_width_fence']for r in before['lineage']if 't04_width_fence'in r]
 if not states or states[-1]['binding']!=fence.ACTIVE.binding:raise ValueError('T02_FROZEN_WIDTH_SOURCE_BINDING_CHANGED')
 if value['plan']['scene_ref']!=predecessor_ref or not value['verification']['passed']:
  raise ValueError('T02_WIDTH_ATTRIBUTION_REQUIRES_VERIFIED_PREDECESSOR')
 policy=store.get_json(value['plan']['policy_ref'],kind='policy')
 if policy!=dict(stage='t02',parameters=p.land_parameters('t02')):
  raise ValueError('T02_WIDTH_ATTRIBUTION_LAND_POLICY_CHANGED')
 after=store.get_json(value['output_scene_ref'],kind='scene')
 rows,current,original=p.operands(store,before);out,material,_=p.operands(store,after)
 if len(out)!=len(after['objects'])or not set(rows)<=set(out):raise ValueError('T02_SOURCE_INVENTORY_CHANGED')
 # Match the existing FastRectangleAdapter's source-centroid order. Source
 # occurrence IDs are byte-span identities, not the spatial visit order.
 pads=sorted((s for s,r in rows.items()if r['kind']=='rectangle'),
             key=lambda s:(original[s].centroid.y,original[s].centroid.x,s))
 decisions=value['candidate']['decisions']
 if value['plan']['details']['targets']!=pads or [r['source_id']for r in decisions]!=pads:
  raise ValueError('T02_ORDINARY_PAD_AUTHORITY_CHANGED')
 if value['candidate']['protected_source_refs']!={s:r['geometry_ref']for s,r in rows.items()if s not in pads}:
  raise ValueError('T02_PROTECTED_TRACE_REFERENCES_CHANGED')
 for sid,row in rows.items():
  if {k:v for k,v in row.items()if k!='geometry_ref'}!={k:v for k,v in out[sid].items()if k!='geometry_ref'}:
   raise ValueError('T02_SOURCE_IDENTITY_CHANGED:'+sid)
  if sid not in pads and out[sid]['geometry_ref']!=row['geometry_ref']:
   raise ValueError('T02_PROTECTED_TRACE_OR_PREDECESSOR_CHANGED:'+sid)
 records=[]
 for decision in decisions:
  sid=decision['source_id'];g=material[sid];core=current[sid]
  if out[sid]['geometry_ref']!=decision['candidate_ref']:raise ValueError('T02_PAD_DECISION_GEOMETRY_CHANGED')
  if decision['status']=='GROWN':
   sx,sy=decision['shape']['factors']
   if not 1<=sx<=1.25 or not 1<=sy<=1.25:raise ValueError('T02_ORDINARY_PAD_CAP_CHANGED')
   declared=scale(core,sx,sy,origin=core.centroid)
  elif decision['status']in('KEEP','COVERED_SKIP'):declared=core
  else:raise ValueError('T02_ORDINARY_PAD_DECISION_CHANGED')
  cap=scale(original[sid],1.25,1.25,origin=original[sid].centroid)
  if (not g.equals(box(*g.bounds))or not g.covers(core)or not cap.covers(g)
      or g.centroid.distance(core.centroid)>1e-12 or p.to_wkb(g)!=p.to_wkb(declared)):
   raise ValueError('T02_ORDINARY_PAD_RECONSTRUCTION_CHANGED:'+sid)
  records.append(dict(source_id=sid,status=decision['status'],original_ref=rows[sid]['original_ref'],candidate_ref=decision['candidate_ref']))
 # Actual, already verified ordinary pads are predecessor copper for remedy
 # checks. No potential envelope or same-net/component exemption is used.
 ordinary=p.unary_union([*current.values(),*[material[s]for s in pads]])
 accepted={}
 for decision in value['candidate']['inclusive_candidates']:
  if decision['status']!='MERGED':continue
  ref=decision['candidate_ref'];sid='t02-inclusive:'+ref['sha256'];members=decision['members']
  if sid in accepted or len(members)<2 or len(set(members))!=len(members)or not set(members)<=set(pads):
   raise ValueError('T02_COMPLETE_FILL_SOURCE_MEMBERS_CHANGED')
  accepted[sid]=decision
 if set(out)-set(rows)!=set(accepted):raise ValueError('T02_UNQUALIFIED_ADDED_CONTRIBUTION')
 fills=[]
 for sid,decision in sorted(accepted.items()):
  row=out[sid];ref=decision['candidate_ref'];g=material[sid]
  expected=box(*p.unary_union([material[m]for m in decision['members']]).bounds)
  if (row['kind']!='inclusive_rectangle'or row['geometry_ref']!=ref or row['original_ref']!=ref
      or row['metadata']['members']!=decision['members']or not g.equals(expected)):
   raise ValueError('T02_COMPLETE_LOGICAL_FILL_CHANGED_OR_FRAGMENTED')
  check=fence.ACTIVE.remedy(g,ordinary)
  if not check['passed']:raise ValueError('T04_REMEDY_BYPASSES_FROZEN_WIDTH:t02_complete_logical_fill')
  fills.append(dict(source_id=sid,check=check))
 complete=fence.ACTIVE.remedy(p.unary_union(list(material.values())),ordinary)
 if not complete['passed']:raise ValueError('T04_REMEDY_BYPASSES_FROZEN_WIDTH:t02_complete')
 return dict(passed=True,schema='source-attributed-t02-width-guard/1',
             protected_predecessor_rows=len(rows)-len(pads),ordinary_source_pads=records,
             complete_logical_fills=fills,complete_scene_check=complete,
             authority='Verified existing T02 source-pad contract only; trace bodies unchanged; no fill clipping or exemption')
