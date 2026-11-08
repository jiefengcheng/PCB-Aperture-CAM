"""Retained corruptions of actual Gerber, with named native predicate rejection."""
import sys,time,copy,json,re
from pathlib import Path
from . import exporter as e
p=e.p;run=Path(sys.argv[1])
from .native_component_checks_final import NativeGroups,decoded_groups,clearance,completion
from src.component_voids import holes,joined
from src import component_clearance as cc
from src.indexed_polygon_distance import distance
from shapely.geometry import box,LineString
from shapely.ops import nearest_points
p.configure();
from .guard import install_read_fence
install_read_fence(run.parent);e.verify_sources(run);folder=run/'negative_controls';folder.mkdir();store,binding=e.context(run)
proofs=[p.load(run/'export'/('proof_'+m+'.json'))for m in('1','2')]
if p.canonical(proofs[0])!=p.canonical(proofs[1])or proofs[0]['status']!='PASS':raise ValueError('PAIRED_NATIVE_PROOFS_REQUIRED')
body=(run/'export/top.art.gbr').read_bytes();ledger=p.load(run/'export/ledger.json');raw=store.get(binding['source_ref'],kind='gerber-source');original,_,_=p.source_profile.parse_source(raw);n=len(original.objects);source=p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in original.objects),1,-1,origin=(0,0));actual=e.parse(body);observed={}
if p.digest(body)!=proofs[0]['generated_sha256']or len(actual.objects)!=n+proofs[0]['appended_positive_regions']:raise ValueError('CONTROL_BASELINE_BYTES_CHANGED')
material=proofs[0]['native_material_assembly']
if material['status']!='EXACT_PARSED_NATIVE_MATERIAL'or len(material['material_parents'])!=material['parents']:raise ValueError('CONTROL_BASELINE_MATERIAL_PROOF_CHANGED')
# The same exact parsed-parent proof used by the positive verifier and the
# remaining-defect audit defines the baseline copper. Re-unioning unwelded
# triangles here would reintroduce artificial seams before testing a corruption.
for row in material['material_parents']:observed.setdefault(row['source_id'],[]).append(p.geometry(store,row['geometry_ref']))
groups=decoded_groups(source,observed);whole=joined(list(groups.values()));results=[]
def expect(name,fn,reason,payload):
 (folder/(name+'.gbr')).write_bytes(payload);started=time.monotonic()
 try:fn()
 except Exception as ex:
  if reason not in str(ex):raise ValueError('WRONG_CONTROL_REASON:'+name+':'+str(ex))
  record=dict(control=name,status='EXPECTED_REJECTION',reason=str(ex),actual_corruption_sha256=p.digest(payload),seconds=time.monotonic()-started);results.append(record);print(json.dumps(record),flush=True)
 else:raise ValueError('CORRUPTION_ACCEPTED:'+name)
expect('EOF_REMOVED',lambda:e.parse(body[:-5]),'missing mandatory M02',body[:-5])
from .source_prefix_control import mutate_source_coordinate
mutated=mutate_source_coordinate(body)
expect('SOURCE_PREFIX_CHANGED',lambda:e.check(run,mutated,ledger),'ORIGINAL_CANONICAL_COMMAND_PREFIX_CHANGED',mutated)
prefix=(e.canonical_base(raw)[0]+'\n').encode();start=len(prefix);end=body.index(b'G37*',start)+len(b'G37*\n')
missing=body[:start]+body[end:];changed=copy.deepcopy(ledger);changed['generated_sha256']=p.digest(missing)
expect('POSITIVE_REGION_REMOVED',lambda:e.check(run,missing,changed),'GERBER_COUNT_OR_HASH_CHANGED',missing)
pos=body.index(b'%LPD*%',start);mutant=body[:pos]+body[pos:].replace(b'%LPD*%',b'%LPC*%',1);changed=copy.deepcopy(ledger);changed['generated_sha256']=p.digest(mutant)
expect('REGION_POLARITY_CHANGED',lambda:e.check(run,mutant,changed),'REGION_ROLE_OR_POLARITY_CHANGED',mutant)
block=body[start:end];moved=re.sub(rb'(?m)^X(-?\d+)',lambda m:b'X'+str(int(m[1])+1000).encode(),block);mutant=body[:start]+moved+body[end:];changed=copy.deepcopy(ledger);changed['generated_sha256']=p.digest(mutant)
expect('CONTOUR_TRANSLATED_1UM',lambda:e.check(run,mutant,changed),'CONTOUR_FIDELITY_FAILED',mutant)
def parsed_extra(shape,name):
 records=[];blocks=[];e.append_regions(shape,'negative_control',name,records,blocks,store);payload=body[:-5]+''.join(blocks).encode()+b'M02*\n';native=e.parse(payload);pieces=[p.affine_scale(p.source_profile.object_geometry(obj)[0],1,-1,origin=(0,0))for obj in native.objects[len(actual.objects):]];return joined(pieces),payload
from src.component_hole_lineage import classify as hole_lineage,identity as hole_identity
void_context=getattr(cc.ACTIVE,'functional',None)or cc.ACTIVE;void_groups=groups.channels if hasattr(groups,'channels')else groups
from src.hole_acceptance import required as holes_required
if holes_required():
 for own,g in void_context.cores.items():
  keepers=set(hole_lineage(g,void_groups[own])['keeper_ids'])
  for hole in [h for h in holes(void_groups[own])if hole_identity(h)in keepers]:
   empty=hole.difference(whole).buffer(-.00001)
   if empty.is_empty:continue
   pt=empty.representative_point();shape=box(pt.x-.000001,pt.y-.000001,pt.x+.000001,pt.y+.000001)
   if not empty.covers(shape):continue
   bad,payload=parsed_extra(shape,'SOURCE_VOID_FILLED');after=dict(groups);physical_owner=own;fill=dict(source_id='SOURCE_VOID_FILLED',original_owner_id=own,logical_patch_ref=p.geomref(store,bad),kind='hole')
   if hasattr(groups,'channels'):
    from src.source_channel_scope import physical_owner as resolve_physical_owner
    physical_owner=resolve_physical_owner(void_context,own,cc.ACTIVE);channels=dict(groups.channels);channels[own]=channels[own].union(bad);after=NativeGroups(after,channels);fill.update(original_owner_id=physical_owner,original_channel_id=own)
   after[physical_owner]=groups[physical_owner].union(bad);fake={'intra':{'fills':[fill]}}
   expect('SOURCE_VOID_FILLED',lambda:completion(store,fake,{'SOURCE_VOID_FILLED':[bad]},groups,after),'NATIVE_INHERITED_SOURCE_VOID_FILLED',payload);break
  else:continue
  break
 else:raise ValueError('SOURCE_VOID_CONTROL_NOT_FOUND')
else:
 results.append(dict(control='SOURCE_VOID_FILLED',status='NOT_REQUIRED_BY_CAPTURED_POLICY',policy='ACCEPT_WITHOUT_SOURCE_ANCESTRY',strict_control='Retained in strict-policy branch and regressions; no source ancestry lookup under current policy'))
ids=list(groups);pairs=[]
from shapely import STRtree
tree=STRtree([groups[o]for o in ids])
for own,g in groups.items():
 for i in tree.query(g.buffer(.15).envelope):
  other=ids[int(i)]
  if own>=other:continue
  d=distance(g,groups[other])
  if .039<d<.15:pairs.append((d,own,other))
if not pairs:raise ValueError('BRIDGE_CONTROL_NOT_FOUND')
_,own,other=min(pairs);a,b=nearest_points(groups[own],groups[other]);bad,payload=parsed_extra(LineString([a,b]).buffer(.001,cap_style=2),'FOREIGN_BRIDGE');after=dict(groups);after[own]=groups[own].union(bad)
expect('FOREIGN_BRIDGE',lambda:clearance(groups,after),'NATIVE_FOREIGN_ORIGINAL_COMPONENT_CLEARANCE_FAILED',payload)
if hasattr(groups,'channels'):
 from src.source_channel_scope import physical_owner as resolve_physical_owner
 channels=groups.channels;ids=list(channels);tree=STRtree([channels[o]for o in ids]);pairs=[]
 for own,g in channels.items():
  for i in tree.query(g.buffer(.15).envelope):
   other=ids[int(i)]
   if own>=other or(cc.ACTIVE.functional.frame_ids and resolve_physical_owner(cc.ACTIVE.functional,own,cc.ACTIVE)!=resolve_physical_owner(cc.ACTIVE.functional,other,cc.ACTIVE)):continue
   d=distance(g,channels[other])
   if .039<d<.15:pairs.append((d,own,other))
 if not pairs:raise ValueError('REMOTE_FRAME_CHANNEL_BRIDGE_CONTROL_NOT_FOUND')
 _,own,other=min(pairs);a,b=nearest_points(channels[own],channels[other]);bad,payload=parsed_extra(LineString([a,b]).buffer(.001,cap_style=2),'REMOTE_FRAME_CHANNEL_BRIDGE');physical=resolve_physical_owner(cc.ACTIVE.functional,own,cc.ACTIVE);physical_after=dict(groups);physical_after[physical]=physical_after[physical].union(bad);channels_after=dict(channels);channels_after[own]=channels_after[own].union(bad);after=NativeGroups(physical_after,channels_after)
 expect('REMOTE_FRAME_CHANNEL_BRIDGE',lambda:clearance(groups,after),'NATIVE_FOREIGN_ORIGINAL_COMPONENT_CLEARANCE_FAILED',payload)
e.verify_sources(run);p.save(folder/'RESULT.json',dict(status='PASS',controls=results,generated_sha256=p.digest(body),producer_sha256=p.digest(Path(__file__).read_bytes()),scope='Corrupted actual Gerber; format/source/role/contour checks plus native parsed-patch void/foreign guards. Candidate unchanged.'))
