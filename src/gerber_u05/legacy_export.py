"""Gerber-only serialization: retain original atoms, append qualified positive copper."""
import collections,copy,json,os,re,sys,math
from pathlib import Path
from . import pipeline as p
from shapely import set_precision,union_all
from shapely.ops import nearest_points
from .guard import verify_sources
from gerbonara.rs274x import GerberFile
from gerbonara.utils import MM
from src.gerber_image import CompletionParser
from src.pcb_data_abi.board_geometry import export_reference,bridge_contour,fidelity
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM,GRID_MM
from src.indexed_hausdorff import distance as image_hausdorff
from src.native_boundary_metric import distance as boundary_distance
from src.u05_board.export import export_region,actual_spindle_check
from .export_absorption import supported_region
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

def connected_native_normalization(shape):
    """Keep a connected contribution connected within the existing file budget.

    Nearest-grid reduction can sever a sub-grid neck and strand a long, thin
    fragment. Retain every positive surface by rounding a one-grid outward
    envelope only for that case. This is accepted only when it still covers
    the complete original contribution and passes the unchanged 2 nm contour
    and area bounds. Actual stage and foreign-owner checks remain mandatory.
    """
    normalized=set_precision(shape,GRID_MM,mode='valid_output')
    proof=dict(encoding_guard_mm=0.,connectivity_support=None)
    if shape.geom_type=='Polygon' and normalized.geom_type=='MultiPolygon':
        from src.native_boundary_metric import distance as boundary_distance
        supported=set_precision(shape.buffer(GRID_MM,quad_segs=16),GRID_MM,mode='valid_output')
        gap=boundary_distance(shape,supported)
        area=shape.symmetric_difference(supported).area
        bound=2*shape.length*POLYGON_TOLERANCE_MM+math.pi*POLYGON_TOLERANCE_MM**2
        if supported.geom_type!='Polygon' or not supported.is_valid or not supported.covers(shape) or not math.isfinite(gap) or gap>POLYGON_TOLERANCE_MM or not math.isfinite(area) or area>bound:
            raise ValueError('EXPORT_CONNECTED_CONTRIBUTION_NOT_FILE_GRID_REPRESENTABLE')
        proof=dict(encoding_guard_mm=GRID_MM,connectivity_support=dict(reason='Preserve a connected qualified contribution during native-grid conversion',nearest_grid_components=len(normalized.geoms),all_qualified_copper_covered=True,hausdorff_mm=gap,tolerance_mm=POLYGON_TOLERANCE_MM,area_mm2=area,area_bound_mm2=bound))
        normalized=supported
    return normalized,proof

def owned_grid_holes(shape,owner):
    """Omit microscopic holes in redundant support already covered by its owner.

    This adds no physical copper: the entire closed hole must be covered by
    qualified predecessor copper. Other holes and all exterior vertices stay
    exact. No size, clearance, source-void or pin-separation waiver is granted.
    """
    if owner is None or not shape.interiors:return shape,[]
    kept=[];absorbed=[]
    for ring in shape.interiors:
        hole=p.Polygon(ring);x,y,x1,y1=hole.bounds
        allowance=8*max(math.ulp(v)for v in hole.bounds)
        if x1-x<=GRID_MM+allowance and y1-y<=GRID_MM+allowance and owner.covers(hole):
            absorbed.append(dict(hole_sha256=p.digest(p.to_wkb(hole)),area_mm2=hole.area,
                                 bounds_mm=list(hole.bounds),owner_sha256=p.digest(p.to_wkb(owner)),
                                 owner_covers_complete_hole=True,added_physical_copper_mm2=0.))
        else:kept.append(ring)
    if not absorbed:return shape,[]
    result=p.Polygon(shape.exterior,kept)
    if not result.is_valid or not result.covers(shape)or not owner.covers(result.difference(shape)):
        raise ValueError('OWNED_GRID_HOLE_CHANGES_PHYSICAL_COPPER')
    return result,absorbed


def append_regions(shape,stage,sid,records,blocks,store,*,owner=None):
    qualified=shape
    # Nominal nearest-grid contours: inward padding changes overlap topology.
    # Construction margins remain in the source-stage proofs; actual native
    # clearance is checked separately against the production hard floor.
    normalized,connectivity=connected_native_normalization(shape);encoding_guard=connectivity['encoding_guard_mm'];area=shape.symmetric_difference(normalized).area;bound=2*shape.length*.000001+3.141592653589793e-12
    if normalized.is_empty or not normalized.is_valid or normalized.geom_type not in('Polygon','MultiPolygon')or area>bound:raise ValueError('EXPORT_FILE_GRID_NORMALIZATION_FAILED')
    raw_ref=p.geomref(store,qualified);normalization=dict(encoding_guard_mm=encoding_guard,qualified_reference_unchanged=True,grid_mm=.000001,mode='valid_output',area_change_mm2=area,area_bound_mm2=bound,raw_type=shape.geom_type,normalized_type=normalized.geom_type,raw_components=1 if shape.geom_type=='Polygon'else len(shape.geoms),normalized_components=1 if normalized.geom_type=='Polygon'else len(normalized.geoms))
    if connectivity['connectivity_support'] is not None:normalization['connectivity_support']=connectivity['connectivity_support']
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
        q,proof=export_reference(piece);q,absorbed=owned_grid_holes(q,owner)
        material=piece
        if absorbed:
            material=q;proof=dict(proof or {},redundant_owned_grid_holes=absorbed,
                                 encoded_reference_sha256=p.digest(p.to_wkb(q)))
        points=bridge_contour(q);points=points+[points[0]]
        # Kernel y-down -> original Gerber y-up. Every word is explicit, 1 nm.
        xy=[(round(x*1e6),round(-y*1e6))for x,y in points]
        if any(a==b for a,b in zip(xy,xy[1:])):raise ValueError('EXPORT_ZERO_LENGTH_GRID_EDGE')
        block=['G04 qualified '+stage+' '+str(len(records))+'*','%LPD*%','G01*','G75*','D10*','G36*']
        block+=['X'+str(x)+'Y'+str(y)+('D02*'if i==0 else'D01*')for i,(x,y)in enumerate(xy)];block+=['G37*']
        blocks.append('\n'.join(block)+'\n');records.append(dict(stage=stage,source_id=sid,geometry_ref=p.geomref(store,material),reference_ref=p.geomref(store,q),raw_qualified_ref=raw_ref,normalization=normalization,component_reference_proof=proof))

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
    after=owner.union(p.unary_union([*pieces,*caps]));distance=boundary_distance(before,after);area=before.symmetric_difference(after).area;bound=2*before.length*POLYGON_TOLERANCE_MM+math.pi*POLYGON_TOLERANCE_MM**2
    if after.geom_type!='Polygon' or not after.is_valid or not math.isfinite(distance)or distance>POLYGON_TOLERANCE_MM or area>bound:raise ValueError('EXPORT_POINT_CONTACT_SUPPORT_NOT_QUALIFIED')
    return caps


def encoded_route_owner(encoded_current,members,land_ids,route_id):
    from src import source_channel_scope
    scope=source_channel_scope.ACTIVE
    if scope is not None:return scope.project(encoded_current)[scope.owner(route_id)]
    return p.unary_union([encoded_current[s]for s in [*members,*land_ids]])

def construct(run):
    verify_sources(run)
    if p.canonical(p.load(run/'audits/t01/supplement_1.json'))!=p.canonical(p.load(run/'audits/t01/supplement_2.json')):raise ValueError('T01_SUPPLEMENT_PROOFS_DIFFER')
    for stage in ORDER:
        if p.load(run/'audits'/stage/'proof.json')['status']!='PASS':raise ValueError('UNVERIFIED_GEOMETRY_STAGE')
    store=p.Store(run/'runtime');binding=p.load(run/'source.json')
    if(run/'LEGACY_REFERENCE_JOB.json').exists():p.initialize(store,binding)
    raw=store.get(binding['source_ref'],kind='gerber-source');base,oracle=canonical_base(raw);scene=store.get_json(binding['scene_ref'],kind='scene');_,current,_=p.operands(store,scene);encoded_current=dict(current);records=[];blocks=[]
    for stage in ORDER[:-1]:
        value=p.load(run/(stage+'.json'));scene=store.get_json(value['output_scene_ref'],kind='scene');rows,after,_=p.operands(store,scene)
        for sid,g in sorted(after.items()):
            if sid not in current or p.to_wkb(g)!=p.to_wkb(current[sid]):
                first=len(records);append_regions(g,stage,sid,records,blocks,store);parts=[p.geometry(store,row['geometry_ref'])for row in records[first:]];encoded_current[sid]=p.unary_union([*([encoded_current[sid]]if sid in encoded_current else[]),*parts])
        current=after
    value=p.load(run/'t05.json');prepared=store.get_json(value['plan']['scene_ref'],kind='scene');policy=store.get_json(value['plan']['policy_ref'],kind='policy');adapter=p.CoverageAdapter(p.box(*prepared['viewport_mm']))
    objects={row['source_id']:row for row in prepared['objects']}
    for d in value['candidate']['decisions']:
        if d['status']!='GROWN':continue
        owner,radius,domain,foreign=adapter._operands(store,prepared,policy,value['plan']['details'],d);addition=p.geometry(store,d['patch_ref']);region,support,_support_mode=supported_region(addition,owner,domain);first=len(records);append_regions(region,'t05',d['source_id'],records,blocks,store,owner=owner)
        members=objects[d['source_id']]['metadata']['reference_source_ids'];encoded_owner=encoded_route_owner(encoded_current,members,d['land_ids'],d['source_id']);pieces=[p.geometry(store,row['geometry_ref'])for row in records[first:]];preserve_point_contacts(encoded_owner,pieces,d['source_id'],records,blocks,store)
    adapter.close();body=(base+'\n'+''.join(blocks)+'M02*\n').encode('ascii');store.verify_reads();verify_sources(run)
    return body,dict(source_sha256=binding['source_ref']['sha256'],coordinate_oracle=oracle,records=records,generated_sha256=p.digest(body),producer_sha256=p.digest(Path(__file__).read_bytes()),profile='GERBER_SOURCE_ONLY; KiCad source/write/plot N/A; positive appended contours, original ordered clear operations retained')

def original_contact_port(overlap,width,contact):
    if not contact:return None,None
    raw=overlap.buffer(width,quad_segs=128)
    # Model-bound source permission, represented in a file whose existing
    # contour uncertainty is 2 nm. Never grant a new contact to a source pair.
    port=raw.buffer(POLYGON_TOLERANCE_MM,quad_segs=128)
    return port,dict(original_contact=True,raw_source_port_sha256=p.digest(p.to_wkb(raw)),native_port_sha256=p.digest(p.to_wkb(port)),file_uncertainty_mm=POLYGON_TOLERANCE_MM)


def native_model_reference(run,store,before):
    binding=p.load(run/'source.json');source=store.get_json(binding['scene_ref'],kind='scene');source_rows={r['source_id']:r for r in source['objects']};value=p.load(run/'t05.json');final=store.get_json(value['output_scene_ref'],kind='scene');references=[];inventory=[]
    def prepare(shape,sid,owner=None):
        normalized,_connectivity=connected_native_normalization(shape);area=shape.symmetric_difference(normalized).area;bound=2*shape.length*GRID_MM+math.pi*GRID_MM**2
        if normalized.is_empty or not normalized.is_valid or normalized.geom_type not in('Polygon','MultiPolygon')or area>bound:raise ValueError('NATIVE_MODEL_REFERENCE_NORMALIZATION_FAILED:'+sid)
        parts=[normalized]if normalized.geom_type=='Polygon'else list(normalized.geoms)
        for part in parts:
            reference,proof=export_reference(part);reference,absorbed=owned_grid_holes(reference,owner);references.append(reference);inventory.append(dict(source_id=sid,qualified_sha256=p.digest(p.to_wkb(shape)),native_reference_sha256=p.digest(p.to_wkb(reference)),normalization_area_mm2=area,normalization_area_bound_mm2=bound,redundant_owned_grid_holes=absorbed))
    if not set(source_rows)<={r['source_id']for r in final['objects']}:raise ValueError('NATIVE_REFERENCE_SOURCE_OCCURRENCE_MISSING')
    aliases=0
    for row in final['objects']:
        # Trace rows are immutable reference views; CoverageAdapter's material
        # ledger excludes them. Original material strokes remain included.
        if row['kind']=='trace':aliases+=1;continue
        if row['kind']=='junction_addition':continue
        sid=row['source_id']
        if sid not in source_rows or row['geometry_ref']!=source_rows[sid]['geometry_ref']:prepare(p.geometry(store,row['geometry_ref']),sid)
    prepared=store.get_json(value['plan']['scene_ref'],kind='scene');policy=store.get_json(value['plan']['policy_ref'],kind='policy');adapter=p.CoverageAdapter(p.box(*prepared['viewport_mm']))
    try:
        for d in value['candidate']['decisions']:
            if d['status']!='GROWN':continue
            owner,radius,domain,foreign=adapter._operands(store,prepared,policy,value['plan']['details'],d);region,_,_support_mode=supported_region(p.geometry(store,d['patch_ref']),owner,domain);prepare(region,d['source_id'],owner)
    finally:adapter.close()
    expected=union_all([before,*references],grid_size=GRID_MM)
    if expected.is_empty or not expected.is_valid or expected.area<=0:raise ValueError('NATIVE_AGGREGATE_REFERENCE_INVALID')
    return expected,dict(basis='Immutable original source plus independently prepared source/model native contours on the existing file grid; no generated ledger used',source_objects=len(source_rows),nonmaterial_route_views=aliases,reference_parts=len(references),grid_mm=GRID_MM,inventory=inventory,raw_decision_image_ref=value['candidate']['after_ref'])


def check(run,body,ledger):
    verify_sources(run);store=p.Store(run/'runtime');binding=p.load(run/'source.json');raw=store.get(binding['source_ref'],kind='gerber-source');original,_,_=p.source_profile.parse_source(raw);actual=parse(body);n=len(original.objects)
    expected_base,_=canonical_base(raw)
    if not body.startswith((expected_base+'\n').encode('ascii')):raise ValueError('ORIGINAL_CANONICAL_COMMAND_PREFIX_CHANGED')
    if p.digest(body)!=ledger['generated_sha256']or len(actual.objects)!=n+len(ledger['records']):raise ValueError('GENERATED_GERBER_COUNT_OR_HASH_CHANGED')
    source_shapes=[];reference_source_shapes=[];proofs=[]
    for i,(a,b)in enumerate(zip(original.objects,actual.objects[:n])):
        ga,_=p.source_profile.object_geometry(a);gb,_=p.source_profile.object_geometry(b)
        if type(a)!=type(b)or a.polarity_dark!=b.polarity_dark or boundary_distance(ga,gb)>1e-8 or ga.symmetric_difference(gb).area>2*ga.length*1e-8:raise ValueError('ORIGINAL_PLOTTING_ATOM_CHANGED:'+str(i))
        source_shapes.append((gb,b.polarity_dark));reference_source_shapes.append((ga,a.polarity_dark))
    before=p.affine_scale(p.source_profile.ordered(source_shapes),1,-1,origin=(0,0));by_stage=collections.defaultdict(dict);observed=[]
    for i,(obj,row)in enumerate(zip(actual.objects[n:],ledger['records'])):
        if not obj.polarity_dark or not isinstance(obj,p.go.Region):raise ValueError('APPENDED_REGION_ROLE_OR_POLARITY_CHANGED')
        g,_=p.source_profile.object_geometry(obj);g=p.affine_scale(g,1,-1,origin=(0,0));reference=p.geometry(store,row['geometry_ref']);proofs.append(dict(ordinal=n+i,stage=row['stage'],source_id=row['source_id'],**fidelity(reference,g)));observed.append(g);d=by_stage[row['stage']];d.setdefault(row['source_id'],[]).append(g)
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
        def check(self,rows,**kwargs):
            from src import component_clearance as ownership
            previous_context=ownership.ACTIVE;ownership.ACTIVE=original_owner_context
            try:return super().check(rows,**kwargs)
            finally:ownership.ACTIVE=previous_context
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
    from src.component_clearance import Context as OriginalOwnerContext
    original_material=p.affine_scale(p.source_profile.ordered(reference_source_shapes),1,-1,origin=(0,0))
    original_owner_context=OriginalOwnerContext(original_material,binding['source_ref']['sha256'],original_shapes)
    for stage in ORDER[:-1]:
        previous=dict(current);result=p.load(run/(stage+'.json'));scene=store.get_json(result['output_scene_ref'],kind='scene');newrows,wanted,_=p.operands(store,scene)
        original_owner_context.register_scene(store,scene)
        for sid,parts in by_stage[stage].items():
            if sid not in current:
                row=newrows[sid];members=row['metadata'].get('members',[])
                if row['kind']!='inclusive_rectangle'or not members or any(m not in previous or m not in original_shapes for m in members):raise ValueError('UNBOUND_NEW_LEGACY_MATERIAL')
                base=p.unary_union([previous[m]for m in members]);previous[sid]=base;current[sid]=base;original_shapes[sid]=p.unary_union([original_shapes[m]for m in members])
            current[sid]=certified_union(current[sid],parts)
        if set(current)!=set(wanted):raise ValueError('ACTUAL_STAGE_SOURCE_ID_COVERAGE_CHANGED:'+stage)
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
        rows=newrows
    value=p.load(run/'t05.json');prepared=copy.deepcopy(store.get_json(value['plan']['scene_ref'],kind='scene'));policy=store.get_json(value['plan']['policy_ref'],kind='policy')
    for row in prepared['objects']:
        sid=row['source_id'];g=p.unary_union([current[s]for s in row['metadata']['reference_source_ids']])if row['kind']=='trace'else current[sid];row['geometry_ref']=p.geomref(store,g)
    declared=store.get_json(value['plan']['scene_ref'],kind='scene')
    original_owner_context.register_scene(store,declared)
    def original_foreign(route,pairs):
        from src import source_channel_scope
        selected=source_channel_scope.ACTIVE or original_owner_context;owner=selected.owner(route)
        return [(sid,g)for sid,g in pairs if tuple(selected.ids.get(sid,()))!=(owner,)]
    nominal_adapter=p.CoverageAdapter(p.box(*declared['viewport_mm']));declared_domains={}
    try:
        for decision in value['candidate']['decisions']:
            if decision['status']=='GROWN':declared_domains[decision['source_id']]=nominal_adapter._operands(store,declared,policy,value['plan']['details'],decision)[2]
    finally:nominal_adapter.close()
    adapter=p.CoverageAdapter(p.box(*prepared['viewport_mm']));preimage=p.unary_union(list(current.values()));patches=[]
    for d in value['candidate']['decisions']:
        if d['status']!='GROWN':continue
        owner,radius,domain,foreign=adapter._operands(store,prepared,policy,value['plan']['details'],d);declared_domain=declared_domains[d['source_id']];parts=by_stage['t05'][d['source_id']];addition=p.unary_union(parts).difference(preimage);patches.append(dict(id=d['source_id'],owner=owner,regions=parts,addition=addition,window=declared_domain.buffer(POLYGON_TOLERANCE_MM),foreign=foreign))
    adapter.close();checks['t05']=[]
    for patch in patches:
        q=actual_spindle_check(patch['owner'],patch['regions'],patch['addition'],patch['window'],original_foreign(patch['id'],patch['foreign']+[(other['id'],other['addition'])for other in patches if other['id']!=patch['id']]))
        p.save(run/'export'/('junction_'+sys.argv[2]+'_'+str(len(checks['t05']))+'.json'),dict(source_id=patch['id'],check=q)) if __name__=='__main__' else None
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
    after=before.union(p.unary_union(observed));reference_before=p.affine_scale(p.source_profile.ordered(reference_source_shapes),1,-1,origin=(0,0));expected,reference_proof=native_model_reference(run,store,reference_before);actual_grid=union_all([before,*observed],grid_size=GRID_MM);distance,metric=image_hausdorff(actual_grid,expected,tolerance=POLYGON_TOLERANCE_MM);area=actual_grid.symmetric_difference(expected).area;bound=2*expected.length*POLYGON_TOLERANCE_MM
    raw_decision_image=p.from_wkb(store.get(value['candidate']['after_ref'],kind='geometry'));raw_area=after.symmetric_difference(raw_decision_image).area;raw_area_bound=2*raw_decision_image.length*POLYGON_TOLERANCE_MM
    if not raw_decision_image.is_valid or raw_area>raw_area_bound:raise ValueError('RAW_MODEL_IMAGE_AREA_FIDELITY_FAILED')
    if not all(math.isfinite(v) for v in (distance,area,bound)) or distance>POLYGON_TOLERANCE_MM or area>bound or before.difference(after).area>1e-12:raise ValueError('ACTUAL_FINAL_COPPER_FIDELITY_OR_PRESERVATION_FAILED')
    store.verify_reads();verify_sources(run)
    result=dict(status='PASS',source_objects_preserved=n,source_clear_operations_preserved=sum(not o.polarity_dark for o in original.objects),appended_positive_regions=len(observed),actual_hard_gap_mm=p.HARD_GAP_MM,contour_proofs=proofs,actual_scene_checks=checks,exact_append_only_core_proofs=core_evidence,native_model_reference=reference_proof,aggregate_metric=metric,raw_model_image_comparison=dict(reference_type=raw_decision_image.geom_type,symmetric_difference_mm2=raw_area,area_bound_mm2=raw_area_bound,role="Decision image; native boundary fidelity uses the declared file-grid reference"),final_copper=dict(hausdorff_mm=distance,symmetric_difference_mm2=area,area_bound_mm2=bound,original_area_mm2=before.area,final_area_mm2=after.area,added_area_mm2=after.difference(before).area),generated_sha256=p.digest(body),producer_sha256=p.digest(Path(__file__).read_bytes()))

    from src import source_channel_scope
    functional=source_channel_scope.ACTIVE
    if functional is not None:
        from .channel_material import current_legacy_channels
        owned,proof=current_legacy_channels(functional,store,binding,[p.load(run/(stage+'.json'))for stage in ORDER],body,ledger,result)
        if proof['status']!='PASS':raise ValueError('NATIVE_LEGACY_FUNCTIONAL_CHANNEL_CHECK_FAILED:'+str(proof['physical_clearance']['failures'][:3]))
        result['functional_channels']=dict(proof,owned_geometry_refs={o:p.geomref(store,g)for o,g in owned.items()},channel_certificate_sha256=p.digest(p.canonical(functional.certificate)))
    if (run/'LEGACY_REFERENCE_JOB.json').exists():
        from .checking_envelopes import install,check_native
        if functional is not None:checking_context=functional
        else:
            from src.component_clearance import Context
            source_scene=store.get_json(binding['scene_ref'],kind='scene');_,source_material,_=p.operands(store,source_scene)
            checking_context=Context(before,binding['source_ref']['sha256'],source_material)
            from src.component_voids import parts
            owned={checking_context.index.membership(g)[0]:g for g in parts(after)}
        install(checking_context,store,binding,run)
        result['checking_envelope_clearance']=check_native(checking_context,owned,p.CONSTRUCTION_GAP_MM)
    return result

if __name__=='__main__':
    p.configure();run=Path(sys.argv[1]);mode=sys.argv[2]
    if mode=='construct':
        body,ledger=construct(run);folder=run/'export';folder.mkdir();(folder/'top.art.gbr').write_bytes(body);p.save(folder/'ledger.json',ledger)
    else:
        folder=run/'export';body=(folder/'top.art.gbr').read_bytes();ledger=p.load(folder/'ledger.json');expected_body,expected_ledger=construct(run)
        if body!=expected_body or p.canonical(ledger)!=p.canonical(expected_ledger):raise ValueError('FRESH_EXPORT_RECONSTRUCTION_CHANGED')
        proof=check(run,body,ledger);p.save(folder/('proof_'+mode+'.json'),proof);print(json.dumps(dict(status='PASS',pid=os.getpid(),proof_sha256=p.digest(p.canonical(proof)),regions=proof['appended_positive_regions'],final_copper=proof['final_copper'])))
