from .contours import contours as serializable_contours
from .export_absorption import prepare_export_region
from .native_spindle_operand import operand as native_spindle_operand
"""Gerber-only serialization: retain original atoms, append qualified positive copper."""
import collections,copy,json,os,re,sys,math
from pathlib import Path
from . import pipeline as p
from shapely import set_precision,union_all
from shapely.ops import nearest_points
from .guard import verify_sources as verify_core_sources
from src import component_clearance as cc
from src.native_boundary_metric import distance as boundary_distance
from .native_component_checks_final import decoded_groups,clearance as native_clearance,completion as native_completion,final_inventory

def verify_sources(run):
    seal=verify_core_sources(run)
    if seal.get("profile")!="original-connected-copper-growth-and-intra-step-completion/1":raise ValueError("CONNECTED_PROFILE_REQUIRED")
    for stage in ORDER:
        value=p.load(run/(stage+".json"));candidate=p.digest(p.canonical(value))
        for mode in ("construct","1","2"):
            proof=p.load(run/"audits"/stage/(mode+".json"))
            if proof["status"]!="PASS"or proof["candidate_sha256"]!=candidate:raise ValueError("GEOMETRY_RECONSTRUCTION_PROOF_CHANGED:"+stage)
    return seal

def context(run):
    store=p.Store(run/"runtime");binding=p.load(run/"source.json");p.initialize(store,binding)
    from .component_stages import reserve_prior
    reserve_prior(cc.ACTIVE,store)
    for name in ORDER:
        value=p.load(run/(name+".json"));scene=store.get_json(value["output_scene_ref"],kind="scene");cc.ACTIVE.register_scene(store,scene)
    return store,binding
from gerbonara.rs274x import GerberFile
from gerbonara.utils import MM
from src.gerber_image import CompletionParser
from src.pcb_data_abi.board_geometry import bridge_contour
from src.native_grid_reference import reference as export_reference,normalize as native_grid,fidelity
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM,GRID_MM
from src.indexed_hausdorff import distance as image_hausdorff
from src.u05_board.export import export_region,actual_spindle_check
from src.junction_spindle_stage import prepare_spindle_context
from src.junction_spindle_blend import spindle_blend
from src.u05_board.attachment_export import obligation_check

ORDER=['t01','t03','t04','t02','t05']

def canonical_base(raw):
    text,_,oracle=p.source_profile.normalize(raw);out=[];fields=0
    if oracle.get('source_format')=='MM_L46_ABSOLUTE':
        if text.count('M02*')!=1:raise ValueError('CANONICAL_SOURCE_EOF_CHANGED')
        return text[:text.index('M02*')],dict(source_coordinate_fields=oracle['coordinate_fields'],source_grid_mm=.000001,output_grid_mm=.000001,exact_integer_conversion=True)
    for token in p.source_profile.TOKEN.finditer(text):
        command=token[0]
        if command.strip()=='%FSTAX35Y35*%':command=command.replace('FSTAX35Y35','FSLAX46Y46')
        elif not command.strip().startswith(('%','G04')):
            def replace(m):
                nonlocal fields
                fields+=1;value=p.source_profile.decode_coordinate(m[2])*10
                return m[1]+('-'if value<0 else'')+str(abs(value)).zfill(10)
            command=p.source_profile.FIELD.sub(replace,command)
        out.append(command)
    result=''.join(out)
    if fields!=oracle['coordinate_fields']or result.count('M02*')!=1:raise ValueError('CANONICAL_SOURCE_COORDINATE_INVENTORY_CHANGED')
    return result[:result.index('M02*')],dict(source_coordinate_fields=fields,source_grid_mm=.00001,output_grid_mm=.000001,exact_integer_conversion=True)

def parse(raw):
    g=GerberFile();parser=CompletionParser(g);parser.parse(raw.decode('ascii'),filename='generated:'+p.digest(raw))
    if not parser.eof_found or parser.current_region is not None or parser.block_frame is not None or parser.file_settings.unit!=MM or parser.file_settings.number_format!=(4,6)or parser.file_settings.notation!='absolute'or parser.inventory['MO']!=1 or parser.inventory['FS']!=1:raise ValueError('GENERATED_GERBER_FORMAT_OR_COMPLETENESS_FAILED')
    return g

def append_regions(shape,stage,sid,records,blocks,store):
    qualified=shape
    # Nominal nearest-grid contours: inward padding changes overlap topology.
    # Construction margins remain in the source-stage proofs; actual native
    # clearance is checked separately against the production hard floor.
    encoding_guard=0.
    if encoding_guard:shape=shape.buffer(encoding_guard,quad_segs=8)
    normalized=native_grid(shape);area=shape.symmetric_difference(normalized).area;bound=2*shape.length*.000001+3.141592653589793e-12
    if normalized.is_empty or not normalized.is_valid or normalized.geom_type not in('Polygon','MultiPolygon')or area>bound:raise ValueError('EXPORT_FILE_GRID_NORMALIZATION_FAILED')
    raw_ref=p.geomref(store,qualified);normalization=dict(encoding_guard_mm=encoding_guard,qualified_reference_unchanged=True,grid_mm=.000001,mode='valid_output',area_change_mm2=area,area_bound_mm2=bound,raw_type=shape.geom_type,normalized_type=normalized.geom_type,raw_components=1 if shape.geom_type=='Polygon'else len(shape.geoms),normalized_components=1 if normalized.geom_type=='Polygon'else len(normalized.geoms))
    encoding_distance=boundary_distance(qualified,normalized);encoding_area=qualified.symmetric_difference(normalized).area;encoding_bound=2*qualified.length*POLYGON_TOLERANCE_MM+math.pi*POLYGON_TOLERANCE_MM**2
    # Isolated contribution normalization may collapse sub-grid tips already
    # covered by other original copper. Preserve these metrics; the unchanged
    # check() enforces 2 nm on the complete physical union, all stage clearance
    # checks, every region contour and every attachment extent.
    if not all(math.isfinite(v)for v in (encoding_distance,encoding_area)):raise ValueError('ENCODED_QUALIFIED_GEOMETRY_NONFINITE')
    normalization.update(qualified_hausdorff_mm=encoding_distance,qualified_symmetric_difference_mm2=encoding_area,qualified_area_bound_mm2=encoding_bound)
    pieces=[normalized]if normalized.geom_type=='Polygon'else list(normalized.geoms)
    for piece in sorted(pieces,key=p.to_wkb):
        if piece.is_empty or piece.area<=0:raise ValueError('INVALID_EXPORT_COMPONENT')
        reference,proof=export_reference(piece)
        serialized,partition_proof=serializable_contours(reference,bridge_contour,grid_mm=GRID_MM)
        for part_index,(q,points)in enumerate(serialized):
            points=points+[points[0]]
            xy=[(round(x*1e6),round(-y*1e6))for x,y in points]
            if any(a==b for a,b in zip(xy,xy[1:])):raise ValueError('EXPORT_ZERO_LENGTH_GRID_EDGE')
            block=['G04 qualified '+stage+' '+str(len(records))+'*','%LPD*%','G01*','G75*','D10*','G36*']
            block+=['X'+str(x)+'Y'+str(y)+('D02*'if i==0 else'D01*')for i,(x,y)in enumerate(xy)];block+=['G37*']
            serialized_reference,serialized_proof=export_reference(q)
            component_proof=dict(serialized_proof,partition_parent_reference_proof=proof,serialization_partition=partition_proof,serialization_part=part_index)
            blocks.append('\n'.join(block)+'\n');records.append(dict(stage=stage,source_id=sid,geometry_ref=p.geomref(store,q),reference_ref=p.geomref(store,serialized_reference),raw_qualified_ref=raw_ref,normalization=normalization,component_reference_proof=component_proof))


def preserve_point_contacts(owner,pieces,sid,records,blocks,store):
    before=owner.union(p.unary_union(pieces))
    if before.geom_type=='Polygon' and before.is_valid:return []
    if before.geom_type!='MultiPolygon' or not before.is_valid:raise ValueError('EXPORT_JUNCTION_INVALID_BEFORE_ENCODING_SUPPORT')
    grid=.000001;caps=[]
    for part in before.geoms:
        if part.intersection(owner).area>0:continue
        gap=part.distance(owner)
        if part.area>grid*grid or gap>grid:raise ValueError('EXPORT_JUNCTION_COMPONENT_NOT_FILE_GRID_POINT_CONTACT')
        point=nearest_points(owner,part)[0];x,y=round(point.x,6),round(point.y,6)
        cap=p.Polygon([(round(x-grid,6),y),(x,round(y-grid,6)),(round(x+grid,6),y),(x,round(y+grid,6))])
        first=len(records);append_regions(cap,'t05',sid,records,blocks,store)
        proof=dict(reason='One-grid cap at minimum-grid component point contact; triangle retained, no topology/tolerance waiver',component_sha256=p.digest(p.to_wkb(part)),component_area_mm2=part.area,gap_to_encoded_owner_mm=gap,cap_radius_mm=grid)
        for row in records[first:]:row['encoding_support']=proof;caps.append(p.geometry(store,row['geometry_ref']))
    after=owner.union(p.unary_union([*pieces,*caps]));distance=before.hausdorff_distance(after);area=before.symmetric_difference(after).area;bound=2*before.length*POLYGON_TOLERANCE_MM+math.pi*POLYGON_TOLERANCE_MM**2
    if after.geom_type!='Polygon' or not after.is_valid or not math.isfinite(distance)or distance>POLYGON_TOLERANCE_MM or area>bound:raise ValueError('EXPORT_POINT_CONTACT_SUPPORT_NOT_QUALIFIED')
    return caps


def construct(run):
    verify_sources(run)
    store,binding=context(run);raw=store.get(binding['source_ref'],kind='gerber-source');base,oracle=canonical_base(raw);scene=store.get_json(binding['scene_ref'],kind='scene');_,current,_=p.operands(store,scene);encoded_current=dict(current);records=[];blocks=[]
    for stage in ORDER[:-1]:
        value=p.load(run/(stage+'.json'));scene=store.get_json(value['output_scene_ref'],kind='scene');rows,after,_=p.operands(store,scene)
        for sid,g in sorted(after.items()):
            if sid not in current or p.to_wkb(g)!=p.to_wkb(current[sid]):
                first=len(records);append_regions(g,stage+'_finish'if rows[sid]['kind']=='component_remedy'else stage,sid,records,blocks,store);parts=[p.geometry(store,row['geometry_ref'])for row in records[first:]];encoded_current[sid]=p.unary_union([*([encoded_current[sid]]if sid in encoded_current else[]),*parts])
        current=after
    value=p.load(run/'t05.json');prepared=store.get_json(value['plan']['scene_ref'],kind='scene');policy=store.get_json(value['plan']['policy_ref'],kind='policy');adapter=p.CoverageAdapter(p.box(*prepared['viewport_mm']))
    objects={row['source_id']:row for row in prepared['objects']}
    for row in sorted(prepared['objects'],key=lambda row:row['source_id']):
        sid=row['source_id']
        if row['kind']!='component_remedy':continue
        g=p.geometry(store,row['geometry_ref'])
        if sid not in current or p.to_wkb(g)!=p.to_wkb(current[sid]):
            first=len(records);append_regions(g,'t05_floor',sid,records,blocks,store);parts=[p.geometry(store,row['geometry_ref'])for row in records[first:]];encoded_current[sid]=p.unary_union([*([encoded_current[sid]]if sid in encoded_current else[]),*parts]);current[sid]=g
    for d in value['candidate']['decisions']:
        if d['status']!='GROWN':continue
        owner,radius,domain,foreign=adapter._operands(store,prepared,policy,value['plan']['details'],d);addition=p.geometry(store,d['patch_ref']);region,support=prepare_export_region(store,value,adapter,owner,domain,d,foreign);first=len(records);append_regions(region,'t05',d['source_id'],records,blocks,store)
        own=adapter.owner_for_route(d['source_id']);encoded_owner=cc.ACTIVE.project(encoded_current)[own];pieces=[p.geometry(store,row['geometry_ref'])for row in records[first:]];preserve_point_contacts(encoded_owner,pieces,d['source_id'],records,blocks,store)
    adapter.close()
    final=store.get_json(value['output_scene_ref'],kind='scene');finalrows={r['source_id']:r for r in final['objects']}
    for fill in value['intra']['fills']:
        sid=fill['source_id'];append_regions(p.geometry(store,finalrows[sid]['geometry_ref']),'t05_finish',sid,records,blocks,store)
    body=(base+'\n'+''.join(blocks)+'M02*\n').encode('ascii');store.verify_reads();verify_sources(run)
    return body,dict(geometry_producer_binding_sha256=p.digest((run/'PRODUCER_BINDING.json').read_bytes()),remedy_policy_snapshot_sha256=p.digest((run/'REMEDY_POLICY_SNAPSHOT.json').read_bytes()),original_ownership_sha256=cc.ACTIVE.index.fingerprint,source_sha256=binding['source_ref']['sha256'],coordinate_oracle=oracle,records=records,generated_sha256=p.digest(body),producer_sha256=p.digest(Path(__file__).read_bytes()),profile='GERBER_SOURCE_ONLY; KiCad source/write/plot N/A; positive appended contours, original ordered clear operations retained')

def original_contact_port(overlap,width,contact):
    if not contact:return None,None
    raw=overlap.buffer(width,quad_segs=128)
    # Model-bound source permission, represented in a file whose existing
    # contour uncertainty is 2 nm. Never grant a new contact to a source pair.
    port=raw.buffer(POLYGON_TOLERANCE_MM,quad_segs=128)
    return port,dict(original_contact=True,raw_source_port_sha256=p.digest(p.to_wkb(raw)),native_port_sha256=p.digest(p.to_wkb(port)),file_uncertainty_mm=POLYGON_TOLERANCE_MM)


def native_model_reference(run,store,before,*,include_parents=False):
    binding=p.load(run/'source.json');source=store.get_json(binding['scene_ref'],kind='scene');source_rows={r['source_id']:r for r in source['objects']};value=p.load(run/'t05.json');final=store.get_json(value['output_scene_ref'],kind='scene');references=[];inventory=[]
    def prepare(shape,sid,stage):
        normalized=native_grid(shape);area=shape.symmetric_difference(normalized).area;bound=2*shape.length*GRID_MM+math.pi*GRID_MM**2
        if normalized.is_empty or not normalized.is_valid or normalized.geom_type not in('Polygon','MultiPolygon')or area>bound:raise ValueError('NATIVE_MODEL_REFERENCE_NORMALIZATION_FAILED:'+sid)
        parts=[normalized]if normalized.geom_type=='Polygon'else list(normalized.geoms)
        for part in parts:
            reference,proof=export_reference(part);references.append(reference);inventory.append(dict(stage=stage,source_id=sid,qualified_sha256=p.digest(p.to_wkb(shape)),native_reference_sha256=p.digest(p.to_wkb(reference)),normalization_area_mm2=area,normalization_area_bound_mm2=bound))
    if not set(source_rows)<={r['source_id']for r in final['objects']}:raise ValueError('NATIVE_REFERENCE_SOURCE_OCCURRENCE_MISSING')
    aliases=sum(row['kind']=='trace'for row in final['objects'])
    # The file is append-only. Native-grid rounding is not a monotone map:
    # compiling only the last scene can omit earlier qualified positive copper.
    # Recompile every source-bound stage contribution, never the output ledger.
    _,current,_=p.operands(store,source)
    for stage in ORDER[:-1]:
        result=p.load(run/(stage+'.json'));scene=store.get_json(result['output_scene_ref'],kind='scene');rows,after,_=p.operands(store,scene)
        for sid,shape in sorted(after.items()):
            if sid not in current or p.to_wkb(shape)!=p.to_wkb(current[sid]):prepare(shape,sid,stage+'_finish'if rows[sid]['kind']=='component_remedy'else stage)
        current=after
    prepared=store.get_json(value['plan']['scene_ref'],kind='scene');policy=store.get_json(value['plan']['policy_ref'],kind='policy');adapter=p.CoverageAdapter(p.box(*prepared['viewport_mm']))
    for row in sorted(prepared['objects'],key=lambda row:row['source_id']):
        sid=row['source_id']
        if row['kind']!='component_remedy':continue
        shape=p.geometry(store,row['geometry_ref'])
        if sid not in current or p.to_wkb(shape)!=p.to_wkb(current[sid]):prepare(shape,sid,'t05_floor')
    try:
        for d in value['candidate']['decisions']:
            if d['status']!='GROWN':continue
            owner,radius,domain,foreign=adapter._operands(store,prepared,policy,value['plan']['details'],d);region,_=prepare_export_region(store,value,adapter,owner,domain,d,foreign);prepare(region,d['source_id'],'t05')
    finally:adapter.close()
    final_rows={row['source_id']:row for row in final['objects']}
    for fill in value['intra']['fills']:
        sid=fill['source_id'];prepare(p.geometry(store,final_rows[sid]['geometry_ref']),sid,'t05_finish')
    expected=assemble_native_material(before,references,grid_mm=GRID_MM)
    if expected.is_empty or not expected.is_valid or expected.area<=0:raise ValueError('NATIVE_AGGREGATE_REFERENCE_INVALID')
    proof=dict(basis='Immutable original source plus every qualified intermediate/final source-stage native contribution on the existing file grid; independently compiled, no generated ledger/file used',source_objects=len(source_rows),nonmaterial_route_views=aliases,reference_parts=len(references),grid_mm=GRID_MM,inventory=inventory,raw_decision_image_ref=value['intra']['after_native_ref'])
    if include_parents:return expected,proof,[((row['stage'],row['source_id'],row['native_reference_sha256']),shape)for row,shape in zip(inventory,references)]
    return expected,proof


from .native_assembly import assemble as assemble_native_material,weld as weld_native_material

def canonical_source_image(raw):
    base,_=canonical_base(raw);parsed=parse((base+'M02*\n').encode('ascii'))
    return p.affine_scale(p.source_profile.ordered((p.source_profile.object_geometry(o)[0],o.polarity_dark)for o in parsed.objects),1,-1,origin=(0,0))

def encoding_support_parents(store,records,value):
    """Retain the existing bounded one-grid support as explicit extra material.

    These supports still face the full scope, foreign-clearance and aggregate
    2 nm checks. Fresh export reconstruction binds their source derivation.
    """
    grown={d['source_id']for d in value['candidate']['decisions']if d['status']=='GROWN'};parents={}
    for row in records:
        support=row.get('encoding_support')
        if support is None:continue
        if row['stage']!='t05'or row['source_id']not in grown or support['cap_radius_mm']!=GRID_MM or not 0<support['component_area_mm2']<=GRID_MM**2 or not 0<=support['gap_to_encoded_owner_mm']<=GRID_MM:raise ValueError('NATIVE_ENCODING_SUPPORT_UNQUALIFIED')
        shape=p.geometry(store,row['raw_qualified_ref']);native,proof=export_reference(shape)
        from .native_material import normal_form
        shell,holes=normal_form(native,grid_mm=GRID_MM)
        if holes or len(shell)!=4:raise ValueError('NATIVE_ENCODING_SUPPORT_SHAPE_CHANGED')
        xs=[a[0]for a in shell];ys=[a[1]for a in shell];x,y=(min(xs)+max(xs))//2,(min(ys)+max(ys))//2
        if set(shell)!={(x-1,y),(x,y-1),(x+1,y),(x,y+1)}:raise ValueError('NATIVE_ENCODING_SUPPORT_SIZE_CHANGED')
        identity=(row['stage'],row['source_id'],p.digest(p.to_wkb(native)))
        if identity[2]!=row['component_reference_proof']['partition_parent_reference_proof']['export_reference_sha256']:raise ValueError('NATIVE_ENCODING_SUPPORT_PARENT_CHANGED')
        parents[identity]=native
    return list(parents.items())

def check(run,body,ledger):
    verify_sources(run);store,binding=context(run);raw=store.get(binding['source_ref'],kind='gerber-source');original,_,_=p.source_profile.parse_source(raw);actual=parse(body);n=len(original.objects)
    expected_base,_=canonical_base(raw)
    if not body.startswith((expected_base+'\n').encode('ascii')):raise ValueError('ORIGINAL_CANONICAL_COMMAND_PREFIX_CHANGED')
    if p.digest(body)!=ledger['generated_sha256']or len(actual.objects)!=n+len(ledger['records']):raise ValueError('GENERATED_GERBER_COUNT_OR_HASH_CHANGED')
    source_shapes=[];reference_source_shapes=[];proofs=[]
    for i,(a,b)in enumerate(zip(original.objects,actual.objects[:n])):
        ga,_=p.source_profile.object_geometry(a);gb,_=p.source_profile.object_geometry(b)
        if type(a)!=type(b)or a.polarity_dark!=b.polarity_dark or ga.hausdorff_distance(gb)>1e-8 or ga.symmetric_difference(gb).area>2*ga.length*1e-8:raise ValueError('ORIGINAL_PLOTTING_ATOM_CHANGED:'+str(i))
        source_shapes.append((gb,b.polarity_dark));reference_source_shapes.append((ga,a.polarity_dark))
    before=p.affine_scale(p.source_profile.ordered(source_shapes),1,-1,origin=(0,0));by_stage=collections.defaultdict(dict);observed=[]
    reference_before=canonical_source_image(raw)
    if p.to_wkb(before)!=p.to_wkb(reference_before):raise ValueError('CANONICAL_SOURCE_PREFIX_GEOMETRY_CHANGED')
    expected,reference_proof,native_parents=native_model_reference(run,store,reference_before,include_parents=True)
    for i,(obj,row)in enumerate(zip(actual.objects[n:],ledger['records'])):
        if not obj.polarity_dark or not isinstance(obj,p.go.Region):raise ValueError('APPENDED_REGION_ROLE_OR_POLARITY_CHANGED')
        g,_=p.source_profile.object_geometry(obj);g=p.affine_scale(g,1,-1,origin=(0,0));reference=p.geometry(store,row['geometry_ref']);proofs.append(dict(ordinal=n+i,stage=row['stage'],source_id=row['source_id'],**fidelity(reference,g)));observed.append(g);d=by_stage[row['stage']];d.setdefault(row['source_id'],[]).append(g)
    raw_observed=observed
    support_parents=encoding_support_parents(store,ledger['records'],p.load(run/'t05.json'))
    welded,material_proof=weld_native_material(ledger['records'],raw_observed,[*native_parents,*support_parents],grid_mm=GRID_MM)
    observed=[];by_stage=collections.defaultdict(dict);material_parents=[]
    for (stage,sid,sha),shape in welded:
        observed.append(shape);by_stage[stage].setdefault(sid,[]).append(shape)
        material_parents.append(dict(stage=stage,source_id=sid,native_parent_sha256=sha,geometry_ref=p.geomref(store,shape)))
    material_proof['material_parents']=material_parents
    material_proof['bounded_encoding_support_parents']=len(support_parents)
    # Actual Gerber is an exact append-only constructive set: the original
    # source prefix is independently verified above, all additions are parsed
    # positive regions, and every later stage adds to its exact predecessor.
    # A floating overlay can invent tiny missing slivers even for A union B.
    # Prove core preservation by the actual positive operand inventory instead
    # of treating those overlay artifacts as physical removal. Geometry and
    # every finite-copper predicate below still use the actual parsed union.
    certificates={};core_evidence={}
    def certified_union(core,parts):
        parts=tuple(parts)
        if any(g.is_empty or not g.is_valid for g in parts):raise ValueError('APPEND_ONLY_OPERAND_INVALID')
        result=core if not parts else p.unary_union([core,*parts])
        key=(p.digest(p.to_wkb(core)),p.digest(p.to_wkb(result)))
        certificates[key]=dict(proof='EXACT_ORIGINAL_PREFIX_AND_PARSED_POSITIVE_APPEND_OPERANDS',generated_sha256=p.digest(body),core_sha256=key[0],candidate_sha256=key[1],positive_operand_sha256=[p.digest(p.to_wkb(g))for g in parts])
        return result
    class ActualCoreProof:
        def required_new_copper_gap(self):
            # Finished-file acceptance is the unchanged production hard floor.
            # Construction guard remains in all inherited geometry proofs.
            return self.contract.hard_gap_mm
        def source_core_preserved(self,sid,core,candidate):
            key=(p.digest(p.to_wkb(core)),p.digest(p.to_wkb(candidate)))
            proof=certificates.get(key)
            if proof is None:raise ValueError('ACTUAL_CORE_CONSTRUCTIVE_PROOF_MISSING:'+sid)
            core_evidence[sid]=dict(proof,overlay_covers_diagnostic=bool(candidate.covers(core)),overlay_removed_area_diagnostic_mm2=core.difference(candidate).area)
            return True
    class ActualLandScene(ActualCoreProof,p.PreparedLandScene):pass
    class ActualWidthScene(ActualCoreProof,p.PreparedWidthScene):pass
    source=store.get_json(binding['scene_ref'],kind='scene');rows,current,original_shapes=p.operands(store,source);checks={}
    for stage in ORDER[:-1]:
        previous=dict(current);result=p.load(run/(stage+'.json'));scene=store.get_json(result['output_scene_ref'],kind='scene');newrows,wanted,_=p.operands(store,scene)
        for sid,pieces in by_stage[stage].items():current[sid]=certified_union(current[sid],pieces)
        if stage in('t01','t02'):
            changed=set(by_stage[stage]);lands=[dict(id=s,original=previous[s]if s in previous else p.geometry(store,newrows[s]['original_ref']),candidate=current[s],native_source_kind='gr_circle'if newrows[s]['kind']=='circle'else'gr_poly',native_stroke_width_mm=0.)for s in sorted(changed)]
            if lands:
                fixed=[dict(id=s,geometry=g,trace_width_mm=newrows[s]['metadata'].get('original_width_mm',0.))for s,g in previous.items()if s not in changed];checker=ActualLandScene(lands,fixed);native_port_proofs=[]
                if stage=='t02':
                    # Match source-bound T02 port permissions, not contacts
                    # introduced by earlier stages' larger predecessor copper.
                    for land in lands:
                        sid=land['id']
                        for oid in checker.ids:
                            if oid==sid:continue
                            a,b=original_shapes[sid],original_shapes[oid];overlap=a.intersection(b);contact=not overlap.is_empty;w=max(checker.widths[sid],checker.widths[oid])+checker.contract.original_port_buffer_gap_mm
                            port,port_proof=original_contact_port(overlap,w,contact);checker.ports[(sid,oid)]=(port,contact,a.distance(b))
                            if port_proof is not None:native_port_proofs.append(dict(source_id=sid,neighbor_id=oid,**port_proof))
                q=checker.check(lands,materialize_scene=True)
                q['actual_file_required_gap_mm']=p.HARD_GAP_MM;q['original_source_native_port_proofs']=native_port_proofs
                p.save(run/'export'/('actual_'+sys.argv[2]+'_'+stage+'.json'),q) if __name__=='__main__' else None
                if not q['passed']:raise ValueError('ACTUAL_GERBER_LAND_CLEARANCE_FAILED:'+stage+':'+str(q['failures'][:3]))
                checks[stage]=q
        elif stage=='t04':
            paths=result['admission']['admitted'];used={m for path in paths for m in path['source_ids']};trials=[dict(id=path['path_id'],original=p.unary_union([previous[m]for m in path['source_ids']]),candidate=certified_union(p.unary_union([previous[m]for m in path['source_ids']]),[g for m in path['source_ids']for g in by_stage[stage].get(m,[])]),verified_original_width_mm=max(newrows[m]['metadata']['source_port_width_mm']for m in path['source_ids']))for path in paths];fixed=[dict(id=s,geometry=g,trace_width_mm=rows[s]['metadata'].get('original_width_mm',0.))for s,g in previous.items()if s not in used];q=ActualWidthScene(trials,fixed).check(trials,materialize_scene=True);q['actual_file_required_gap_mm']=p.HARD_GAP_MM
            p.save(run/'export'/('actual_'+sys.argv[2]+'_'+stage+'.json'),q) if __name__=='__main__' else None
            if not q['passed']:raise ValueError('ACTUAL_GERBER_WIDTH_CLEARANCE_FAILED:'+str(q['failures'][:3]))
            checks[stage]=q
        if stage=='t04':
            finish_parts=by_stage['t04_finish'];groups_before=cc.ACTIVE.project(current)
            for sid,pieces in finish_parts.items():current[sid]=p.unary_union(pieces)
            groups_after=cc.ACTIVE.project(current);checks['t04_finish']=native_completion(store,result,finish_parts,groups_before,groups_after)
        if set(current)!=set(wanted):raise ValueError('ACTUAL_STAGE_SOURCE_ID_COVERAGE_CHANGED:'+stage)
        rows=newrows
        for sid,row in rows.items():
            if sid not in original_shapes:original_shapes[sid]=p.geometry(store,row['original_ref'])
    value=p.load(run/'t05.json');prepared=copy.deepcopy(store.get_json(value['plan']['scene_ref'],kind='scene'));policy=store.get_json(value['plan']['policy_ref'],kind='policy')
    floor_parts=by_stage['t05_floor'];floor= value.get('prior_positive_floor');declared_floor={row['source_id']:row for row in floor['records']}if floor else{}
    if set(floor_parts)!=set(declared_floor):raise ValueError('ACTUAL_PRIOR_FLOOR_INVENTORY_CHANGED')
    groups_before_floor=cc.ACTIVE.project(current)
    for sid,pieces in floor_parts.items():current[sid]=certified_union(current[sid],pieces)if sid in current else p.unary_union(pieces)
    groups_with_floor=cc.ACTIVE.project(current);checks['t05_prior_floor_clearance']=native_clearance(groups_before_floor,groups_with_floor)
    floor_missing=sum(prior.difference(groups_with_floor[own].buffer(POLYGON_TOLERANCE_MM)).area for own,prior in cc.ACTIVE.reserved.items())
    checks['t05_prior_positive_retention']=dict(passed=floor_missing<=1e-12,missing_area_mm2=floor_missing,prior_sha256=cc.ACTIVE.reservation_sha256,contour_uncertainty_mm=POLYGON_TOLERANCE_MM)
    if floor_missing>1e-12:raise ValueError('ACTUAL_T05_ENTRY_PRIOR_COPPER_MISSING:'+str(floor_missing))
    for row in prepared['objects']:
        sid=row['source_id'];g=p.unary_union([current[s]for s in row['metadata']['reference_source_ids']])if row['kind']=='trace'else current[sid];row['geometry_ref']=p.geomref(store,g)
    declared=store.get_json(value['plan']['scene_ref'],kind='scene')
    nominal_adapter=p.CoverageAdapter(p.box(*declared['viewport_mm']));declared_domains={}
    try:
        for decision in value['candidate']['decisions']:
            if decision['status']=='GROWN':declared_domains[decision['source_id']]=nominal_adapter._operands(store,declared,policy,value['plan']['details'],decision)[2]
    finally:nominal_adapter.close()
    adapter=p.CoverageAdapter(p.box(*prepared['viewport_mm']));preimage=p.unary_union(list(current.values()));patches=[]
    for d in value['candidate']['decisions']:
        if d['status']!='GROWN':continue
        owner,radius,domain,foreign=adapter._operands(store,prepared,policy,value['plan']['details'],d);declared_domain=declared_domains[d['source_id']];parts=by_stage['t05'][d['source_id']];addition=native_spindle_operand(parts);net_addition=addition.difference(preimage);patches.append(dict(id=d['source_id'],original_owner_id=adapter.owner_for_route(d['source_id']),owner=owner,regions=parts,addition=addition,net_addition=net_addition,window=declared_domain.buffer(POLYGON_TOLERANCE_MM),foreign=foreign))
    adapter.close();checks['t05']=[]
    for patch in patches:
        q=actual_spindle_check(patch['owner'],patch['regions'],patch['addition'],patch['window'],patch['foreign']+[(other['id'],other['addition'])for other in patches if other['id']!=patch['id']and other['original_owner_id']!=patch['original_owner_id']])
        p.save(run/'export'/('junction_'+sys.argv[2]+'_'+str(len(checks['t05']))+'.json'),dict(source_id=patch['id'],check=q)) if __name__=='__main__' else None
        q['additive_operand_basis']=dict(policy='ACTUAL_PARSED_POSITIVE_APPEND_REGIONS_INCLUDING_OWNER_ENCODING_SUPPORT',net_added_area_mm2=patch['net_addition'].area,positive_operand_area_mm2=patch['addition'].area,clearance_scope='Complete positive operand; conservative relative to net-only testing',delta_reassembly_tolerance_unchanged=True)
        if not q['passed']:raise ValueError('ACTUAL_GERBER_JUNCTION_CHECK_FAILED:'+patch['id']+':'+str(q['failures']))
        checks['t05'].append(dict(source_id=patch['id'],check=q))
    # Dynamic source-contact obligations; no C03 historical counts are imported.
    model=store.get_json(value['plan']['scene_ref'],kind='scene');adapter=p.CoverageAdapter(p.box(*model['viewport_mm']));_,model_current,_=p.operands(store,model);model_before=p.geometry(store,value['candidate']['before_ref']);attachments=[]
    for d in value['candidate']['decisions']:
        if not d['land_ids']:continue
        owner,radius,domain,foreign=adapter._operands(store,model,policy,value['plan']['details'],d);desired=adapter._blend(owner,radius,domain)[1];needs=adapter.needs(model_current,d,radius,desired.difference(model_before));selected=p.geometry(store,d['patch_ref']).difference(model_before)if d['status']=='GROWN'else p.Polygon();parts=by_stage['t05'].get(d['source_id'],[])
        if len(needs)!=len(d['attachment_outcomes']):raise ValueError('ACTUAL_ATTACHMENT_INVENTORY_CHANGED')
        for need,outcome in zip(needs,d['attachment_outcomes']):
            if any(outcome[k]!=need[k]for k in('id','land_id','reference_land_id','required_reference')):raise ValueError('ACTUAL_ATTACHMENT_MEMBERSHIP_CHANGED')
            if outcome['status']=='TREATED_VERIFIED':q=obligation_check(selected.intersection(need['window']),preimage,parts)
            elif outcome['status']=='ALREADY_SATISFIED_VERIFIED':q=obligation_check(desired.intersection(need['window']),preimage,[],already=True)
            elif outcome['status']=='BLOCKED_CLEARANCE_OR_BOUNDARY'and not outcome['required_reference']:q=dict(passed=False,status='BLOCKED_NOT_COUNTED_AS_COVERED')
            else:raise ValueError('ACTUAL_ATTACHMENT_OUTCOME_NOT_QUALIFIED')
            attachments.append(dict(id=outcome['id'],status=outcome['status'],check=q))
    adapter.close();checks['attachment_obligations']=attachments
    groups_before=cc.ACTIVE.project(current);t05_observed={}
    for stage_name in ('t05',):
        for sid,pieces in by_stage[stage_name].items():t05_observed.setdefault(sid,[]).extend(pieces)
    for sid,pieces in t05_observed.items():current[sid]=p.unary_union(pieces)
    groups_t05=cc.ACTIVE.project(current);checks['t05_component_clearance']=native_clearance(groups_before,groups_t05)
    for sid,pieces in by_stage['t05_finish'].items():current[sid]=p.unary_union(pieces)
    groups_after=cc.ACTIVE.project(current);checks['t05_finish']=native_completion(store,value,by_stage['t05_finish'],groups_t05,groups_after)
    source_groups=decoded_groups(before,{});all_observed={}
    for stage_map in by_stage.values():
        for sid,pieces in stage_map.items():all_observed.setdefault(sid,[]).extend(pieces)
    actual_owner_groups=decoded_groups(before,all_observed);checks['whole_board_owner_clearance']=native_clearance(source_groups,actual_owner_groups);checks['whole_board_void_inventory']=final_inventory(before,actual_owner_groups)
    after=before.union(p.unary_union(observed));actual_grid=assemble_native_material(before,observed,grid_mm=GRID_MM);distance,metric=image_hausdorff(actual_grid,expected,tolerance=POLYGON_TOLERANCE_MM);area=actual_grid.symmetric_difference(expected).area;bound=2*expected.length*POLYGON_TOLERANCE_MM
    raw_grid=union_all([before,*raw_observed],grid_size=GRID_MM);raw_distance,raw_metric=image_hausdorff(raw_grid,expected,tolerance=POLYGON_TOLERANCE_MM);raw_overlay_diagnostic=dict(status='DIAGNOSTIC_ONLY_NOT_PHYSICAL_MATERIAL',hausdorff_mm=raw_distance,symmetric_difference_mm2=raw_grid.symmetric_difference(expected).area,metric=raw_metric,basis='Unwelded triangle overlays can create numerical seams; physical qualification uses exact parsed integer-material proofs before assembly')
    raw_decision_image=p.from_wkb(store.get(value['intra']['after_native_ref'],kind='geometry'));raw_area=after.symmetric_difference(raw_decision_image).area;raw_area_bound=2*raw_decision_image.length*POLYGON_TOLERANCE_MM
    if not raw_decision_image.is_valid or raw_area>raw_area_bound:raise ValueError('RAW_MODEL_IMAGE_AREA_FIDELITY_FAILED')
    if not all(math.isfinite(v) for v in (distance,area,bound)) or distance>POLYGON_TOLERANCE_MM or area>bound or before.difference(after).area>1e-12:raise ValueError('ACTUAL_FINAL_COPPER_FIDELITY_OR_PRESERVATION_FAILED')
    prior=cc.ACTIVE.reserved;coverage=after.buffer(POLYGON_TOLERANCE_MM);prior_missing=sum(g.difference(coverage).area for g in prior.values());checks['prior_positive_retention']=dict(passed=prior_missing<=1e-12,missing_area_mm2=prior_missing,prior_sha256=cc.ACTIVE.reservation_sha256,contour_uncertainty_mm=POLYGON_TOLERANCE_MM)
    if prior_missing>1e-12:raise ValueError('PRIOR_QUALIFIED_POSITIVE_COPPER_MISSING:'+str(prior_missing))
    store.verify_reads();verify_sources(run)
    return dict(status='PASS',geometry_producer_binding_sha256=p.digest((run/'PRODUCER_BINDING.json').read_bytes()),remedy_policy_snapshot_sha256=p.digest((run/'REMEDY_POLICY_SNAPSHOT.json').read_bytes()),original_ownership_sha256=cc.ACTIVE.index.fingerprint,source_objects_preserved=n,source_clear_operations_preserved=sum(not o.polarity_dark for o in original.objects),appended_positive_regions=len(raw_observed),native_material_assembly=material_proof,actual_material_image_ref=p.geomref(store,after),raw_region_overlay_diagnostic=raw_overlay_diagnostic,actual_hard_gap_mm=p.HARD_GAP_MM,contour_proofs=proofs,actual_scene_checks=checks,exact_append_only_core_proofs=core_evidence,native_model_reference=reference_proof,aggregate_metric=metric,raw_model_image_comparison=dict(reference_type=raw_decision_image.geom_type,symmetric_difference_mm2=raw_area,area_bound_mm2=raw_area_bound,role="Decision image; native boundary fidelity uses the declared file-grid reference"),final_copper=dict(hausdorff_mm=distance,symmetric_difference_mm2=area,area_bound_mm2=bound,original_area_mm2=before.area,final_area_mm2=after.area,added_area_mm2=after.difference(before).area),generated_sha256=p.digest(body),producer_sha256=p.digest(Path(__file__).read_bytes()))

if __name__=='__main__':
    p.configure();run=Path(sys.argv[1]);mode=sys.argv[2]
    if mode=='construct':
        body,ledger=construct(run);folder=run/'export';folder.mkdir();(folder/'top.art.gbr').write_bytes(body);p.save(folder/'ledger.json',ledger)
    else:
        folder=run/'export';body=(folder/'top.art.gbr').read_bytes();ledger=p.load(folder/'ledger.json');expected_body,expected_ledger=construct(run)
        if body!=expected_body or p.canonical(ledger)!=p.canonical(expected_ledger):raise ValueError('FRESH_EXPORT_RECONSTRUCTION_CHANGED')
        proof=check(run,body,ledger);p.save(folder/('proof_'+mode+'.json'),proof);print(json.dumps(dict(status='PASS',pid=os.getpid(),proof_sha256=p.digest(p.canonical(proof)),regions=proof['appended_positive_regions'],final_copper=proof['final_copper'])))
