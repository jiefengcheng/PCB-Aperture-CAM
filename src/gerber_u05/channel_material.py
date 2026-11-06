"""Actual parsed native contours assigned by frozen source identities.

A preserved common bar is not subtracted from a whole-image union to guess
ownership. Full native pad/trace contours retain their original channel identity,
including the original parts that overlap that temporary bar.
"""
from shapely import STRtree
from . import pipeline as p
from . import legacy_export as legacy
from src import component_clearance as cc
from src.component_distance import distance

def check_owned(scope,owned,*,gap=None):
 if gap is None:gap=p.HARD_GAP_MM
 if gap not in(p.HARD_GAP_MM,p.CONSTRUCTION_GAP_MM):raise ValueError('FUNCTIONAL_NATIVE_GAP_POLICY_CHANGED')
 if set(owned)!=set(scope.cores):raise ValueError('FUNCTIONAL_NATIVE_CHANNEL_INVENTORY_CHANGED')
 ids=list(owned);tree=STRtree([owned[o]for o in ids]);pairs=[];failures=[]
 for own,g in owned.items():
  if g.is_empty or not g.is_valid or g.geom_type not in('Polygon','MultiPolygon'):raise ValueError('FUNCTIONAL_NATIVE_MATERIAL_INVALID')
  added=g.difference(scope.cores[own])
  if added.is_empty:continue
  for j in sorted(map(int,tree.query(added.buffer(gap+.000002).envelope))):
   other=ids[j]
   if other==own:continue
   measured=distance(added,owned[other]);passed=measured+1e-12>=gap;pairs.append(dict(source_channel_id=own,foreign_source_channel_id=other,gap_mm=measured,passed=passed))
   if not passed:failures.append(dict(reason='NATIVE_FUNCTIONAL_CHANNEL_CLEARANCE_FAILED',source_channel_id=own,foreign_source_channel_id=other,gap_mm=measured))
 from src.pin_separation import require as require_pin
 pin_proof=require_pin(cc.joined(list(owned.values())),finished=(gap==p.HARD_GAP_MM),scope='native_channel_material')
 return dict(schema='actual-native-functional-channel-clearance/1',passed=not failures,failures=failures,pairs=pairs,nominal_gap_mm=gap,source_sha256=scope.source_hash,channel_certificate_sha256=p.digest(p.canonical(scope.certificate)),channels=len(ids),ownership='FROZEN_ORIGINAL_NON_FRAME_OCCURRENCES; no new contact exemption',**({}if pin_proof is None else{'pin_separation':pin_proof}))

def legacy_channels(scope,store,binding,stage_results,body,ledger,proofs):
 if len(proofs)!=2 or p.canonical(proofs[0])!=p.canonical(proofs[1])or proofs[0]['status']!='PASS':raise ValueError('PAIRED_NATIVE_CHANNEL_BASELINE_PROOFS_REQUIRED')
 owned,proof=current_legacy_channels(scope,store,binding,stage_results,body,ledger,proofs[0])
 return owned,dict(proof,evaluation_count=2,paired_native_proof_sha256=p.digest(p.canonical(proofs[0])))

def current_legacy_channels(scope,store,binding,stage_results,body,ledger,native_evaluation):
 if native_evaluation['status']!='PASS':raise ValueError('COMPLETED_NATIVE_CHANNEL_EVALUATION_REQUIRED')
 sha=p.digest(body)
 if ledger['generated_sha256']!=sha or native_evaluation['generated_sha256']!=sha or ledger['source_sha256']!=scope.source_hash:raise ValueError('NATIVE_CHANNEL_FILE_BINDING_CHANGED')
 raw=store.get(binding['source_ref'],kind='gerber-source')
 if p.digest(raw)!=scope.source_hash:raise ValueError('NATIVE_CHANNEL_ORIGINAL_SOURCE_CHANGED')
 prefix,_=legacy.canonical_base(raw)
 if not body.startswith((prefix+'\n').encode('ascii')):raise ValueError('NATIVE_CHANNEL_ORIGINAL_PREFIX_CHANGED')
 native=legacy.parse(body);n=binding['source_objects'];records=ledger['records'];contours=native_evaluation['contour_proofs']
 if native_evaluation['source_objects_preserved']!=n or len(native.objects)!=n+len(records)or len(contours)!=len(records):raise ValueError('NATIVE_CHANNEL_COMPLETE_REGION_INVENTORY_CHANGED')
 for value in stage_results:
  scope.register_scene(store,store.get_json(value['output_scene_ref'],kind='scene'))
  if 'plan'in value and value['plan'].get('stage')=='t05':scope.register_scene(store,store.get_json(value['plan']['scene_ref'],kind='scene'))
 buckets={o:[g]for o,g in scope.cores.items()};inventory=[]
 for i,(obj,row,verified)in enumerate(zip(native.objects[n:],records,contours)):
  if verified['ordinal']!=n+i or any(verified[k]!=row[k]for k in('stage','source_id')):raise ValueError('NATIVE_CHANNEL_SOURCE_ID_OR_STAGE_CHANGED')
  if not obj.polarity_dark or not isinstance(obj,p.go.Region):raise ValueError('NATIVE_CHANNEL_REGION_ROLE_CHANGED')
  sid=row['source_id']
  if not scope.ids.get(sid):raise ValueError('TEMPORARY_FRAME_NATIVE_ADDITION_NOT_ALLOWED:'+sid)
  own=scope.owner(sid);actual=p.affine_scale(p.source_profile.object_geometry(obj)[0],1,-1,origin=(0,0));reference=p.geometry(store,row['geometry_ref']);fidelity=legacy.fidelity(reference,actual);buckets[own].append(actual)
  inventory.append(dict(ordinal=n+i,stage=row['stage'],source_id=sid,source_channel_id=own,actual_native_geometry_sha256=p.digest(p.to_wkb(actual)),fidelity=fidelity))
 owned={o:cc.joined(values)for o,values in buckets.items()};check=check_owned(scope,owned)
 return owned,dict(status='PASS'if check['passed']else'FAIL',source_sha256=scope.source_hash,generated_sha256=sha,evaluation_count=1,native_evaluation_sha256=p.digest(p.canonical(native_evaluation)),ledger_sha256=p.digest(p.canonical(ledger)),native_positive_regions=len(records),inventory=inventory,physical_clearance=check,source_retention='Exact unchanged canonical source prefix and complete actual parsed positive region inventory; source roles independently checked by paired native proofs',frame='All original frame source occurrences retained; no appended frame growth permitted')
