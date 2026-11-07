"""Isolated Gerber-source U05 trial; no supplied KiCad source is invented.

Reuses the production geometry policies. Gerber occurrence/prefix identities
replace KiCad node custody, which is explicitly inapplicable in this profile.
"""
import collections,copy,functools,hashlib,json,math,re,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from .workspace import configure
from src.stage_abi.store import ArtifactStore,canonical,digest
from src.stage_abi.scene import geometry,composed,validate_scene
from src.clearance_policy import HARD_GAP_MM,CONSTRUCTION_GAP_MM,CONTACT_BUFFER_MM
from src.crop_balanced_t01 import CropSettings,WorkingScene,execute
from src.t01_canonical import allocate,specification,marker
from .channel_surface_guard import ChannelSurfaceGuard as SurfaceGuard
from src.prepared_land_scene import PreparedLandScene
from src.prepared_width_scene import PreparedWidthScene
from src.u03_board.dependency import DependencyWidthScene
from src.u03_board.source import route_evidence
from src.source_junction_paths import junction_source_paths
from src.parallel_trace_relations import parallel_relation,relation_groups
from src.source_offset_width import FAMILY as OFFSET_FAMILY
from src.native_inventory import steps,ERROR_MM
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM
from src.u02_board.adapter import pair_check
from src.u04_board.search import FastRectangleAdapter
from .component_rectangles import ComponentRectangleAdapter as FastRectangleAdapter
from src.stage_abi.lands import land_parameters
from .prior_copper import CoverageAdapter
from src.u05_board.junctions import parameters as spindle_parameters
from shapely import from_wkb,to_wkb,STRtree
from shapely.affinity import scale as affine_scale
from shapely.geometry import Point,LineString,box,Polygon,GeometryCollection
from shapely.ops import unary_union
from gerbonara import graphic_objects as go
from gerbonara.apertures import CircleAperture,RectangleAperture
from . import gerber_source_profile as source_profile

PACKET=Path(__file__).resolve().parent
EPS=1e-12

class Store(ArtifactStore):
    def __init__(self,root):super().__init__(root);self.read_refs={}
    def _prepare_new_artifact(self,path,blob):
        from .storage_encoding import prepare_pending
        return prepare_pending(path,blob)
    def get(self,reference,*,kind=None):
        raw=super().get(reference,kind=kind);self.read_refs[reference['artifact_id']]=dict(reference);return raw
    def verify_reads(self):
        for ref in self.read_refs.values():super().get(ref)

def geomref(store,g):return store.put('geometry',to_wkb(g))
def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('IMMUTABLE_RESULT_EXISTS:'+str(path))
    body=canonical(value)
    from .storage_encoding import write_new
    if not write_new(path,body):path.write_bytes(body)
def load(path):return json.loads(Path(path).read_bytes())
def bounds(scene):return dict(max_source_objects=max(10000,len(scene['objects'])*3),max_targets=max(10000,len(scene['objects'])*3),max_evaluations=200000,max_output_bytes=1024**3,max_seconds=3600)
def offset_part(core,minimum_width,factor,envelope=False,*,extra_envelope_mm=0.):
    if type(factor)not in(float,int)or not math.isfinite(factor)or not 1<=factor<=1.5 or not math.isfinite(minimum_width)or minimum_width<=0:raise ValueError('SOURCE_OFFSET_SCALAR_OR_WIDTH_INVALID')
    if extra_envelope_mm not in(0.,2*POLYGON_TOLERANCE_MM)or(extra_envelope_mm and not envelope):raise ValueError('CHECKING_ONLY_NATIVE_HEADROOM_REQUIRED')
    delta=minimum_width*(factor-1)/2;q=2*steps(minimum_width*.5/2)
    g=core if factor==1 else core.buffer(delta+(ERROR_MM+extra_envelope_mm if envelope else 0.),quad_segs=q)
    if not g.is_valid or not g.covers(core):raise ValueError('SOURCE_OFFSET_CORE_OR_GEOMETRY_CHANGED')
    return g
def operands(store,scene):
    rows={r['source_id']:r for r in scene['objects']};current={s:geometry(store,r['geometry_ref'])for s,r in rows.items()};original={s:geometry(store,r['original_ref'])for s,r in rows.items()};return rows,current,original
def artifact_scene(store,scene,current,stage,metadata=None,additions=()):
    objects=[]
    for r in scene['objects']:
        q=dict(r);sid=r['source_id']
        if sid in current:q['geometry_ref']=r['geometry_ref']if to_wkb(current[sid])==store.get(r['geometry_ref'],kind='geometry')else geomref(store,current[sid])
        if metadata and sid in metadata:q['metadata']=metadata[sid]
        objects.append(q)
    value=dict(scene,objects=objects+list(additions),lineage=scene['lineage']+[dict(stage=stage,source='GERBER_ORIGINAL_OCCURRENCES')])
    from src import pin_separation as pin
    if pin.ACTIVE is not None:value['lineage'][-1]['pin_separation_state']=pin.ACTIVE.state(store)
    from src import t04_width_fence as width_fence
    if width_fence.ACTIVE is not None:value['lineage'][-1]['t04_width_fence']=width_fence.ACTIVE.state(store)
    return store.put_json('scene',value)

def build_source(store,raw):
    parsed,parser,oracle=source_profile.parse_source(raw);all_shapes=[];residual=0.
    for o in parsed.objects:
        g,r=source_profile.object_geometry(o);all_shapes.append(g);residual=max(residual,r)
    clear=Polygon();effective={};ledger=[]
    for i in reversed(range(len(parsed.objects))):
        o=parsed.objects[i]
        if o.polarity_dark:
            g=all_shapes[i]if clear.is_empty else all_shapes[i].difference(clear)
            if not g.is_empty:effective[i]=g
        else:clear=clear.union(all_shapes[i])
    objects=[];width_text=[];offset=0;physical=[];source_hash=digest(raw)
    for i,o in enumerate(parsed.objects):
        span=parser.spans[i];sid=f'{source_hash}:bytes:{span[0]}:{span[1]}'
        if i not in effective:
            ledger.append(dict(source_id=sid,ordinal=i,polarity_dark=o.polarity_dark,disposition='CLEAR_OPERATION_APPLIED'if not o.polarity_dark else'FULLY_CLEARED_SOURCE'));continue
        g=affine_scale(effective[i],1,-1,origin=(0,0));kind='fixed_source';md=dict(gerber_ordinal=i,source_span=span,prefix_sha256=digest(raw[:span[1]]),source_kind=type(o).__name__,qualified_land=False)
        width=0.;minimum=0.;family=None
        if isinstance(o,(go.Line,go.Arc)):
            a=o.aperture
            if isinstance(a,CircleAperture):minimum=width=float(a.diameter);family=['C',minimum]
            elif isinstance(a,RectangleAperture):minimum=min(a.w,a.h);width=math.hypot(a.w,a.h);family=['R',a.w,a.h]
            else:raise ValueError('UNQUALIFIED_STROKE_APERTURE')
            if not effective[i].equals(all_shapes[i]):raise ValueError('CLEAR_CLIPPED_TRACE_NEEDS_SEPARATE_FAMILY')
            kind='stroke';ends=[[o.x1,-o.y1],[o.x2,-o.y2]]
            if isinstance(o,go.Arc):
                points,_=source_profile.arc_points((o.x1,o.y1),(o.x2,o.y2),(o.x1+o.cx,o.y1+o.cy),o.clockwise);points=[[x,-y]for x,y in points]
            else:points=ends
            md.update(route_points_mm=points,endpoints_decimal_mm=[[format(x,'.12f'),format(y,'.12f')]for x,y in ends],minimum_caliper_mm=minimum,source_port_width_mm=width,aperture_family=family,route_kind='arc'if isinstance(o,go.Arc)else'segment')
        elif isinstance(o,go.Flash):
            if not effective[i].equals(all_shapes[i]):raise ValueError('CLEAR_CLIPPED_FLASH_NEEDS_SEPARATE_FAMILY')
            if isinstance(o.aperture,CircleAperture):
                kind='circle';md.update(center_mm=[o.x,-o.y],radius_mm=float(o.aperture.diameter)/2,qualified_land=True)
            elif isinstance(o.aperture,RectangleAperture):kind='rectangle';md['qualified_land']=True
        elif isinstance(o,go.Region)and g.equals(box(*g.bounds)):kind='rectangle';md['qualified_land']=True
        if kind=='rectangle'and not g.equals(box(*g.bounds)):raise ValueError('RECTANGLE_SOURCE_NOT_AXIS_ALIGNED')
        md.update(nominal_width_mm=width,original_width_mm=width)
        ref=geomref(store,g);objects.append(dict(source_id=sid,kind=kind,original_ref=ref,geometry_ref=ref,metadata=md))
        token=f'(width {width:.17g})\n'.encode();width_text.append(token);physical.append(dict(id=sid,kind='segment'if kind=='stroke'and md['route_kind']=='segment'else'arc'if kind=='stroke'else'gr_circle'if kind=='circle'else'gr_poly',trace_width_mm=width,source_span=[offset,offset+len(token)],geometry_sha256=ref['sha256']));offset+=len(token)
        if isinstance(o,go.Region):
            from src.t01_region_contacts import source_marker
            physical[-1]['t01_original_region']=source_marker(source_hash,sid,ref['sha256'])
        ledger.append(dict(source_id=sid,ordinal=i,polarity_dark=True,disposition='PHYSICAL_SOURCE_CONTRIBUTION',geometry_sha256=ref['sha256']))
    image=unary_union([geometry(store,r['geometry_ref'])for r in objects]);source_image=affine_scale(source_profile.ordered(zip(all_shapes,(o.polarity_dark for o in parsed.objects))),1,-1,origin=(0,0))
    if image.symmetric_difference(source_image).area>1e-10:raise ValueError('ORDERED_POLARITY_CONTRIBUTION_ASSEMBLY_MISMATCH')
    aliases=collections.defaultdict(list)
    for r in objects:
        if r['metadata']['qualified_land']:aliases[(r['kind'],r['original_ref']['sha256'])].append(r['source_id'])
    for r in objects:
        if r['metadata']['qualified_land']:r['metadata']['alias_source_ids']=sorted(aliases[(r['kind'],r['original_ref']['sha256'])])
    x0,y0,x1,y1=image.bounds;scene=dict(source_sha256=source_hash,frame='gerber-source-mm-y-down',units='mm',layer='F.Cu',viewport_mm=[x0-.5,y0-.5,x1+.5,y1+.5],objects=objects,findings=[],lineage=[dict(stage='gerber-source-intake',representation='Original Gerber occurrences; F.Cu is only the selected computation surface, not an inferred X2 stack role')],acceptance=dict(owner='PENDING_USER',independent='NOT_RUN',electrical_manufacturing='NOT_ESTABLISHED'))
    ref=store.put_json('scene',scene);binding=dict(source_ref=store.put('gerber-source',raw),scene_ref=ref,source_ledger=ledger,coordinate_oracle=oracle,max_arc_radius_residual_mm=residual,source_objects=len(parsed.objects),width_metadata_encoding_ref=store.put('kernel-width-data',b''.join(width_text)),width_metadata_rows=physical,KiCad='NOT_APPLICABLE_NO_SOURCE_CREATED',clear_operations=sum(not o.polarity_dark for o in parsed.objects))
    return binding

def t01_sites(store,scene):
    rows,current,_=operands(store,scene);ids=[r['source_id']for r in scene['objects']];shapes=[current[s]for s in ids];tree=STRtree(shapes);groups={};component=0
    for i in range(len(ids)):
        if i in groups:continue
        pending=[i];groups[i]=component
        while pending:
            j=pending.pop()
            for k in map(int,tree.query(shapes[j],predicate='intersects')):
                if k not in groups:groups[k]=component;pending.append(k)
        component+=1
    sites=[];seen=set()
    for i,r in enumerate(scene['objects']):
        if r['kind']!='circle'or r['source_id']in seen:continue
        md=r['metadata'];aliases=md['alias_source_ids'];seen.update(aliases);indexes=[ids.index(s)for s in aliases];core=current[r['source_id']];center=[core.centroid.x,core.centroid.y];radius=(core.bounds[2]-core.bounds[0]+core.bounds[3]-core.bounds[1])/4
        from src import source_channel_scope
        contact_group='GERBER-PHYSICAL-'+str(groups[i])
        if source_channel_scope.ACTIVE is not None:contact_group='FUNCTIONAL-SOURCE-'+source_channel_scope.ACTIVE.owner(min(aliases),core)
        sites.append(dict(source_id=min(aliases),aliases=aliases,indexes=indexes,core=core,center=center,radius=radius,enlarged_radius=1.5*radius,geometry_sha256=digest(to_wkb(core)),physical_contact_group=contact_group))
    return sorted(sites,key=lambda s:(s['center'][1],s['center'][0],s['source_id']))

def run_t01(store,scene,binding):
    sites=t01_sites(store,scene);_,current,_=operands(store,scene);rows=binding['width_metadata_rows'];shapes=[current[r['id']]for r in rows];raw=store.get(binding['width_metadata_encoding_ref'],kind='kernel-width-data');spec=specification();policy=dict(canonical_t01=marker(),family=marker()['family'],settings=spec['settings'],diameter_classes_mm=spec['diameter_classes_mm'])
    settings,allocation,targets,square=allocate(raw,rows,shapes,sites,policy,dict(reviewed_pairs=[],recess_source_ids=[]))
    result=execute(raw,rows,shapes,sites,allocation['groups'],allocation['priorities_by_physical_component'],dynamic=True,settings=settings,counterfactuals=True,targets=targets,square_guided_ids=square,surface_guard=SurfaceGuard(rows,shapes,sites))
    after=dict(current)
    for s in sites:
        for sid in s['aliases']:after[sid]=result['scene'].accepted[s['source_id']]
    lands=[dict(id=s['source_id'],original=s['core'],candidate=after[s['source_id']],native_source_kind='gr_circle',native_stroke_width_mm=0.)for s in sites];omit={a for s in sites for a in s['aliases']};fixed=[dict(id=s,geometry=g,trace_width_mm=next(r['trace_width_mm']for r in rows if r['id']==s))for s,g in current.items()if s not in omit]
    checker=PreparedLandScene(lands,fixed)
    from src.t01_region_contacts import install_prepared_ports
    region_ports=install_prepared_ports(checker,rows)
    full=checker.check(lands,materialize_scene=True)
    if region_ports:full['original_region_attachment_ports']=region_ports
    if not full['passed']or any(not d['verification']['passed']for d in result['decisions']):raise ValueError('T01_FULL_SCENE_CHECK_FAILED')
    for s in sites:
        if s['source_id']in allocation['contained_keep_source_ids']and to_wkb(after[s['source_id']])!=to_wkb(s['core']):raise ValueError('T01_CONTAINED_SOURCE_CHANGED')
        if s['source_id']in allocation['circle_overlap_keep_source_ids']and to_wkb(after[s['source_id']])!=to_wkb(s['core']):raise ValueError('T01_OVERLAP_KEEP_SOURCE_CHANGED')
    ref=artifact_scene(store,scene,after,'t01')
    return dict(output_scene_ref=ref,allocation=allocation,decisions=result['decisions'],events=[{k:v for k,v in e.items()if k not in('counterfactual','earlier_copper')}for e in result['events']],rejected_hypotheses=[{k:v for k,v in e.items()if k!='candidate'}for e in result['failed_patches']],full_surface_check=full,summary=dict(circle_sites=len(sites),circle_occurrences=sum(len(s['aliases'])for s in sites),grown=sum(d['added_area_mm2']>1e-10 for d in result['decisions']),contained_keep=len(allocation['contained_keep_source_ids'])))

def run_t03(store,scene,binding,t01):
    original=store.get_json(binding['scene_ref'],kind='scene');rows,before,_=operands(store,original);_,current,_=operands(store,scene);sites=t01_sites(store,original);meta=binding['width_metadata_rows'];raw=store.get(binding['width_metadata_encoding_ref'],kind='kernel-width-data');ws=WorkingScene(raw,meta,[before[r['id']]for r in meta],sites,CropSettings());tree=STRtree([before[s['source_id']]for s in sites]);records=[];policy=dict(hard_gap_mm=HARD_GAP_MM,quad_segs=128,area_epsilon_mm2=1e-10)
    for sid,r in sorted(rows.items()):
        if r['kind']!='stroke':continue
        if to_wkb(before[sid])!=to_wkb(current[sid]):raise ValueError('T03_SOURCE_TRACE_CHANGED')
        pairs=[]
        for i in sorted(map(int,tree.query(before[sid].buffer(HARD_GAP_MM+.000001)))):
            s=sites[i];q=pair_check(s['core'],current[s['source_id']],before[sid],ws.ports[s['source_id']].get(sid),policy);pairs.append(dict(target=s['source_id'],**q))
        records.append(dict(source_id=sid,pairs=pairs))
    if any(not p['passed']or not p['original_contact_preserved']for r in records for p in r['pairs']):raise ValueError('GERBER_T03_MOVEMENT_NOT_QUALIFIED')
    return dict(output_scene_ref=store.put_json('scene',scene),records=records,summary=dict(trace_occurrences=len(records),pairs=sum(len(r['pairs'])for r in records),moved=0,disposition='NO_CHANGE_REQUIRED'))

def width_admission(store,scene):
    rows,current,original=operands(store,scene);native=[];families=collections.defaultdict(list)
    from src import source_channel_scope
    frame_ids=source_channel_scope.ACTIVE.frame_ids if source_channel_scope.ACTIVE is not None else frozenset()
    for sid,r in rows.items():
        if r['kind']!='stroke':continue
        md=r['metadata'];n=dict(source_id=sid,kind=md['route_kind'],width_mm=md['minimum_caliper_mm'],endpoints_decimal_mm=md['endpoints_decimal_mm'],route_points_mm=md['route_points_mm'],source_wkb_sha256=r['original_ref']['sha256']);native.append(n);families[tuple(md['aperture_family'])].append(n)
    paths=[]
    for family,records in sorted(families.items()):paths.extend(route_evidence(junction_source_paths(records,[r['source_id']for r in records])))
    ids=sorted(current);tree=STRtree([current[s]for s in ids]);admitted=[];decisions=[]
    for p in sorted(paths,key=lambda p:p['path_id']):
        members=set(p['source_ids'])
        if members&frame_ids:
            if not members<=frame_ids:raise ValueError('SOURCE_PATH_MIXES_TEMPORARY_FRAME_AND_FUNCTIONAL_CHANNEL')
            decisions.append(dict(path=p,disposition='KEEP_PROTECTED_TEMPORARY_COMMON_FRAME',coverage_source_ids=sorted(members),exposed_area_mm2=0.));continue
        core=unary_union([current[s]for s in sorted(members)]);near=[ids[int(i)]for i in tree.query(core,predicate='intersects')if ids[int(i)]not in members];cover=unary_union([current[s]for s in near]);covered=cover.covers(core)
        if not covered and p['route_type']=='DEGENERATE_SOURCE_STROKE_CONTEXT':raise ValueError('EXPOSED_DEGENERATE_ROUTE_NOT_QUALIFIED')
        decisions.append(dict(path=p,disposition='KEEP_FULLY_COVERED'if covered else'ADMIT_COMPLETE_GERBER_ROUTE',coverage_source_ids=near,exposed_area_mm2=core.difference(cover).area))
        if not covered:admitted.append(p)
    owner={s:p['path_id']for p in admitted for s in p['source_ids']};entries=[n for n in native if n['kind']=='segment'and n['source_id']in owner];lines=[LineString(n['route_points_mm'])for n in entries];lt=STRtree(lines);edges=set();relations=[];blocked=[];members={p['path_id']:set(p['source_ids'])for p in admitted}
    for i,a in enumerate(entries):
        for j in sorted(int(j)for j in lt.query(lines[i].buffer(.5))if int(j)>i):
            b=entries[j];aid=a['source_id'];bid=b['source_id'];pa=owner[aid];pb=owner[bid]
            if pa==pb or current[aid].intersects(current[bid]):continue
            relation=parallel_relation(a['route_points_mm'],b['route_points_mm'])
            if relation is None:continue
            cross=LineString(relation['midpoint_cross_section_mm']).difference(current[aid].union(current[bid]));excluded=members[pa]|members[pb];obstacles=sorted(ids[int(k)]for k in tree.query(cross,predicate='intersects')if ids[int(k)]not in excluded);record=dict(source_a=aid,source_b=bid,path_a=pa,path_b=pb,blocker_source_ids=obstacles,**relation);(blocked if obstacles else relations).append(record)
            if not obstacles:edges.add(tuple(sorted((pa,pb))))
    groups=[dict(group_id='WG-'+digest(canonical(p))[:20],members=p)for p in relation_groups([p['path_id']for p in admitted],sorted(edges))];all_members=[s for p in paths for s in p['source_ids']]
    if sorted(all_members)!=sorted(n['source_id']for n in native)or len(set(all_members))!=len(all_members):raise ValueError('GERBER_TRACE_PARTITION_INCOMPLETE')
    return dict(paths=decisions,admitted=admitted,groups=groups,relations=relations,blocked_relations=blocked,trace_occurrences=len(native))

def run_t04(store,scene):
    from .ladder_width import run
    return run(store,scene)


def empty_t02(store,scene):
    """A complete empty native-rectangle inventory is a verified identity step."""
    if any(row['kind']=='rectangle'for row in scene['objects']):raise ValueError('T02_EMPTY_INVENTORY_HAS_ELIGIBLE_TARGET')
    scene_ref=store.put_json('scene',scene);validate_scene(store,scene_ref)
    rows,current,original=operands(store,scene)
    inventory=dict(source_objects=len(rows),validated_current_geometries=len(current),validated_original_geometries=len(original),eligible_rectangles=0,objects_sha256=digest(canonical(scene['objects'])),source_sha256=scene['source_sha256'])
    policy=dict(stage='t02',parameters=land_parameters('t02'));proof=dict(passed=True,failures=[],status='NOT_APPLICABLE_EMPTY_NATIVE_RECTANGLE_INVENTORY',inventory=inventory,scene_identity_ref=scene_ref,source_geometry_unchanged=True)
    candidate=dict(status='NO_CHANGE_REQUIRED',output_scene_ref=scene_ref,decisions=[],inclusive_candidates=[],protected_source_refs={row['source_id']:row['geometry_ref']for row in scene['objects']})
    plan=dict(stage='t02',scene_ref=scene_ref,policy_ref=store.put_json('policy',policy),implementation='complete-empty-native-rectangle-inventory/1',details=dict(targets=[],parameters={},family=policy['parameters']['family'],bounds=bounds(scene),containment={},inventory=inventory))
    return dict(output_scene_ref=scene_ref,candidate=candidate,plan=plan,verification=proof,summary=dict(rectangles=0,grown=0,contained_keep=0,inclusive=0))

def run_t02(store,scene):
    ids=[r['source_id']for r in scene['objects']if r['kind']=='rectangle']
    if not ids:return empty_t02(store,scene)
    from src import component_clearance as ownership
    previous_context=ownership.ACTIVE
    if previous_context is None:
        source_ref=dict(artifact_id='gerber-source:'+scene['source_sha256'],sha256=scene['source_sha256']);raw=store.get(source_ref,kind='gerber-source');binding_file=store.root.parent/'source.json';binding=load(binding_file)if binding_file.exists()else build_source(store,raw)
        if binding['source_ref']!=source_ref:raise ValueError('T02_ORIGINAL_OWNER_SOURCE_CHANGED')
        source_scene=store.get_json(binding['scene_ref'],kind='scene');source_rows,source_current,_=operands(store,source_scene);parsed,_,_=source_profile.parse_source(raw)
        physical=affine_scale(source_profile.ordered((source_profile.object_geometry(obj)[0],obj.polarity_dark)for obj in parsed.objects),1,-1,origin=(0,0))
        ownership.ACTIVE=ownership.Context(physical,binding['source_ref']['sha256'],source_current)
        from .checking_envelopes import initialize as initialize_checking
        initialize_checking(store,binding,scene,physical=ownership.ACTIVE)
    try:
        adapter=FastRectangleAdapter('t02');scene_ref=store.put_json('scene',scene);policy=dict(stage='t02',parameters=land_parameters('t02'));details=adapter.plan(store,scene,policy,dict(stage='t02',scene_ref=scene_ref,source_ids=ids),bounds(scene));plan=dict(stage='t02',scene_ref=scene_ref,policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details);candidate=adapter.run(store,scene,policy,plan,lambda _:None);check=adapter.verify(store,scene,policy,plan,candidate,dict(scope='complete-source-land-and-inclusive'),lambda _:None)
        if not check['passed']:raise ValueError('T02_RECONSTRUCTION_FAILED')
        return dict(output_scene_ref=candidate['output_scene_ref'],candidate=candidate,plan=plan,verification=check,summary=dict(rectangles=len(ids),grown=sum(r['status']=='GROWN'for r in candidate['decisions']),contained_keep=sum(r['status']=='COVERED_SKIP'for r in candidate['decisions']),inclusive=sum(r['status']=='MERGED'for r in candidate['inclusive_candidates'])))
    finally:ownership.ACTIVE=previous_context

def run_t05(store,scene,t04):
    from src import source_channel_scope
    functional=source_channel_scope.ACTIVE
    from .prior_copper import prepare as prepare_prior
    scene,prior_floor=prepare_prior(store,scene)
    rows,current,original=operands(store,scene);objects=copy.deepcopy(scene['objects']);byid={r['source_id']:r for r in objects};lands=[s for s,r in rows.items()if r['metadata'].get('qualified_land')or r['kind']=='inclusive_rectangle']
    for sid in lands:
        r=byid[sid]
        if r['kind']=='inclusive_rectangle':
            support=unary_union([original[m]for m in r['metadata']['members']]);r['original_ref']=geomref(store,support);original[sid]=support;r['metadata'].update(qualified_land=True,alias_source_ids=[sid])
    tree=STRtree([original[s]for s in lands]);targets=[];contacts=[]
    # T05 contacts are independently admitted from all complete source paths,
    # including T04's covered/held paths. Width eligibility does not select T05.
    for record in t04['admission']['paths']:
        p=record['path'];members=p['source_ids'];sid='route:'+p['path_id'];old=unary_union([original[m]for m in members]);now=unary_union([current[m]for m in members]);ids=[lands[int(i)]for i in tree.query(old,predicate='intersects')if old.intersection(original[lands[int(i)]]).area>EPS and now.intersection(current[lands[int(i)]]).area>EPS];ids=sorted(ids);attachments=[dict(id=sid+':'+lid,land_id=lid,reference_land_id=lid,required_reference=False)for lid in ids]
        from src import source_channel_scope
        functional=source_channel_scope.ACTIVE
        if functional is not None and set(members)&functional.frame_ids:
            if not set(members)<=functional.frame_ids:raise ValueError('T05_SOURCE_PATH_MIXES_FRAME_AND_FUNCTIONAL_CHANNEL')
            contacts.append(dict(route=sid,lands=ids,T04_disposition=record['disposition'],t05_disposition='KEEP_PROTECTED_TEMPORARY_COMMON_FRAME',source_contacts_retained_unchanged=True));continue
        metadata=dict(native_route_ref=store.put_json('gerber-route',p),reference_source_ids=members,land_ids=ids,attachments=attachments,reference_id=p['path_id'],reference_status='GERBER_SOURCE_CONTACTS_NO_HISTORICAL_REFERENCE')
        objects.append(dict(source_id=sid,kind='trace',original_ref=geomref(store,old),geometry_ref=geomref(store,now),metadata=metadata));targets.append(sid);contacts.append(dict(route=sid,lands=ids,T04_disposition=record['disposition']))
    prepared=dict(scene,objects=objects);scene_ref=store.put_json('scene',prepared);policy=dict(stage='t05',parameters=spindle_parameters());adapter=CoverageAdapter(box(*scene['viewport_mm']));details=adapter.plan(store,prepared,policy,dict(stage='t05',scene_ref=scene_ref,source_ids=targets),bounds(prepared));plan=dict(stage='t05',scene_ref=scene_ref,policy_ref=store.put_json('policy',policy),implementation=adapter.describe()['implementation'],details=details);candidate=adapter.run(store,prepared,policy,plan,lambda _:None);check=adapter.verify(store,prepared,policy,plan,candidate,dict(scope='complete-source-and-all-patches'),lambda _:None);adapter.close()
    if not check['passed']:raise ValueError('T05_COMPLETE_ATTACHMENT_RECONSTRUCTION_FAILED')
    return dict(output_scene_ref=candidate['output_scene_ref'],candidate=candidate,plan=plan,verification=check,contacts=contacts,**({}if prior_floor is None else{'prior_positive_floor':prior_floor}),summary=dict(routes=len(targets),**(dict(protected_frame_routes=sum(c.get('t05_disposition')=='KEEP_PROTECTED_TEMPORARY_COMMON_FRAME'for c in contacts),protected_frame_source_contacts=sum(len(c['lands'])for c in contacts if c.get('t05_disposition')=='KEEP_PROTECTED_TEMPORARY_COMMON_FRAME'))if functional is not None else{}),source_attachments=sum(len(c['lands'])for c in contacts),grown=candidate['coverage']['grown'],attachment_outcomes=candidate['coverage']['attachment_outcomes']))

def stage(run,name):
    store=Store(run/'runtime');binding=load(run/'source.json');order=['t01','t03','t04','t02','t05'];index=order.index(name);scene_ref=binding['scene_ref']if index==0 else load(run/(order[index-1]+'.json'))['output_scene_ref'];scene=validate_scene(store,scene_ref)
    initialize(store,binding,scene)
    source=store.get(binding['source_ref'],kind='gerber-source')
    if (run/'source_snapshot/top.art.gbr').read_bytes()!=source or canonical(build_source(store,source))!=canonical(binding):raise ValueError('GERBER_SOURCE_BINDING_OR_CALIPER_CHANGED')
    if name=='t01':result=run_t01(store,scene,binding)
    elif name=='t03':result=run_t03(store,scene,binding,load(run/'t01.json'))
    elif name=='t04':result=run_t04(store,scene)
    elif name=='t02':result=run_t02(store,scene)
    else:result=run_t05(store,scene,load(run/'t04.json'))
    from src import source_channel_scope
    if source_channel_scope.ACTIVE is not None:result=dict(result,functional_source_channels=dict(certificate_sha256=digest(canonical(source_channel_scope.ACTIVE.certificate)),policy=source_channel_scope.ACTIVE.certificate['policy'],source_channels=len(source_channel_scope.ACTIVE.cores),protected_frame_occurrences=len(source_channel_scope.ACTIVE.frame_ids)))
    store.verify_reads();return result

legacy_run_t01=run_t01
legacy_run_t03=run_t03
from .component_stages import initialize,run_t01,run_t03
