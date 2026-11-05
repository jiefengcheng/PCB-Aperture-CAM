"""Exact-source land recovery using ordinary T02; no route or T04 execution.

The inherited native writer, plot verification and negative controls are reused.
This is a separate engineering qualification, never a U04 completion receipt.
"""
from pathlib import Path
from shapely import from_wkb, to_wkb
from shapely.geometry import box
from src.stage_abi.store import ArtifactStore, canonical, digest
from src.stage_abi.lands import LandAdapter, land_parameters
from src.stage_abi.scene import validate_scene
from src.prepared_land_scene import PreparedLandScene
from src.t01_canonical import specification
from src.pcb_data_abi.board_export import BoardDataService
from src.pcb_data_abi.board_custody import validate_host
from src.u04_board.export import U04DataService, validate_export_controls
from src.pcb_data_abi.service import read


def permission(source):
    spec=specification();revision=spec['permission_revision']
    authority=(Path(__file__).resolve().parents[1]/revision['authority_path']).read_bytes()
    if digest(authority)!=revision['authority_sha256']:
        raise ValueError('SCOPED_LAND_AUTHORITY_CHANGED')
    import json
    decision=json.loads(authority)
    if decision['source_sha256']!=source or decision['full_circle_obligation']!='C028_BLOCKED':
        raise ValueError('SCOPED_LAND_SOURCE_AUTHORITY_REQUIRED')
    p=spec['permissions'][source]
    if (len(p['ordinary_t02_recovery_source_ids'])!=2 or
            len(set(p['ordinary_t02_recovery_source_ids']))!=2 or
            p['companion_evaluation_source_ids']!=p['blocked_full_circle_obligation_source_ids']):
        raise ValueError('SCOPED_LAND_PERMISSION_INVALID')
    return p


def validate_machine_prefix(root):
    """Read and hash each retained proof; never write into the predecessor."""
    root=Path(root);m=read(root/'MACHINE_RECEIPT.json')
    expected=read(Path(__file__).resolve().parents[1]/'contracts/operator/t01_board_auto.json')['sequence']
    if m['operations']!=expected or len(m['proofs'])!=18:
        raise ValueError('SCOPED_LAND_COMPLETE_T01_MACHINE_PREFIX_REQUIRED')
    predicates=0
    for path,h in m['proofs'].items():
        p=root/path
        if not p.resolve().is_relative_to(root.resolve()) or digest(p.read_bytes())!=h:
            raise ValueError('SCOPED_LAND_PREFIX_PROOF_CHANGED')
        proof=read(p)
        if proof['status']!='PASS' or not proof['checks'] or not all(c['passed']for c in proof['checks']):
            raise ValueError('SCOPED_LAND_PREFIX_PREDICATE_FAILED')
        predicates+=len(proof['checks'])
    return dict(status='RETAINED_VERIFIED',machine_audits=18,machine_predicates=predicates,
                receipt_sha256=digest((root/'MACHINE_RECEIPT.json').read_bytes()))


def rectangle_scene(prefix_store,receipt,manifest,store):
    """Preserve the complete native source map and original contact authority."""
    original=prefix_store.get_json(receipt['scene_ref'],kind='scene')
    candidate=prefix_store.get_json(receipt['candidate_ref'],kind='candidate')
    current=prefix_store.get_json(candidate['output_scene_ref'],kind='scene')
    meta={r['id']:r for r in manifest['objects']}
    binding=prefix_store.get_json(receipt['binding_ref'],kind='t01-binding')
    raw=prefix_store.get(binding['source_ref'],kind='native-source')
    if digest(raw)!=receipt['source_sha256']:
        raise ValueError('SCOPED_LAND_NATIVE_SOURCE_CHANGED')
    if (manifest['source_sha256']!=receipt['source_sha256'] or
            len(meta)!=len(manifest['objects']) or
            set(meta)!={r['source_id']for r in original['objects']} or
            set(meta)!={r['source_id']for r in current['objects']}):
        raise ValueError('SCOPED_LAND_COMPLETE_SOURCE_REQUIRED')
    objects=[]
    originals={r['source_id']:r for r in original['objects']}
    selected=permission(receipt['source_sha256'])['ordinary_t02_recovery_source_ids']
    import sexpdata
    from src.native_reference import one
    for sid in selected:
        if sid not in meta:raise ValueError('SCOPED_LAND_RECTANGLE_MISSING')
        m=meta[sid];start,end=m['source_span'];node=sexpdata.loads(raw[start:end].decode())
        if (sid!=f'{digest(raw)}:bytes:{start}:{end}'or m['kind']!='gr_poly'or
                str(node[0])!='gr_poly'or list(map(str,one(node,'layer')))!=['F.Cu']or
                str(one(node,'fill',[''])[0])not in('yes','solid')or
                float(one(one(node,'stroke'),'width')[0])!=0):
            raise ValueError('SCOPED_LAND_FILLED_ZERO_STROKE_RECTANGLE_REQUIRED')
    for row in current['objects']:
        sid=row['source_id'];m=meta[sid];old=originals[sid]
        blob=prefix_store.get(old['original_ref'],kind='geometry')
        if digest(blob)!=m['geometry_sha256'] or old['original_ref']!=row['original_ref']:
            raise ValueError('SCOPED_LAND_ORIGINAL_SOURCE_CHANGED')
        core=from_wkb(blob)
        oldref=store.put('geometry',blob)
        nowref=store.put('geometry',prefix_store.get(row['geometry_ref'],kind='geometry'))
        if sid in selected and (not core.equals(box(*core.bounds))or nowref!=oldref):
            raise ValueError('SCOPED_LAND_ORIGINAL_RECTANGLE_REQUIRED')
        kind=('trace'if m['kind']in('segment','arc')else'circle'if m['kind']=='gr_circle'
              else'rectangle'if m['kind']=='gr_poly'and core.equals(box(*core.bounds))else'fixed_source')
        objects.append(dict(source_id=sid,kind=kind,original_ref=oldref,geometry_ref=nowref,
                            metadata=dict(native_source_ids=[sid],native_source_kind=m['kind'],
                                          nominal_width_mm=m.get('trace_width_mm')or 0.)))
    scene=dict(current,objects=objects)
    ref=store.put_json('scene',scene);validate_scene(store,ref)
    return ref,scene


def construct_rectangles(store,scene_ref,scene):
    ids=permission(scene['source_sha256'])['ordinary_t02_recovery_source_ids']
    adapter=LandAdapter('t02');policy=dict(stage='t02',parameters=land_parameters('t02'))
    pref=store.put_json('policy',policy)
    n=len(ids);bounds=dict(max_source_objects=len(scene['objects']),max_targets=n,
        max_evaluations=400*n+2*n*n*n,max_output_bytes=1_000_000_000,max_seconds=1800)
    selection=dict(stage='t02',scene_ref=scene_ref,source_ids=ids)
    details=adapter.plan(store,scene,policy,selection,bounds)
    plan=dict(stage='t02',scene_ref=scene_ref,policy_ref=pref,profile_id='scoped-ordinary-t02-recovery/1',
              implementation=adapter.describe()['implementation'],details=details)
    candidate=adapter.run(store,scene,policy,plan,lambda _:None)
    candidate.update(plan_ref=store.put_json('plan',plan),scene_ref=scene_ref,policy_ref=pref,profile_id=plan['profile_id'])
    output=store.get_json(candidate['output_scene_ref'],kind='scene')
    if len(output['objects'])!=len(scene['objects']):
        raise ValueError('SCOPED_LAND_UNAUTHORIZED_INCLUSIVE_ADDITION')
    verification=adapter.verify(store,scene,policy,plan,candidate,
        {'scope':'complete-source-land-and-inclusive'},lambda _:None)
    if not verification['passed']:raise ValueError('SCOPED_LAND_RECONSTRUCTION_FAILED')
    return dict(plan=plan,candidate=candidate,verification=verification,
                qualification='SCOPED_T02_ON_T01_ONLY; not U04; T04 NOT_RUN')


def verify_recovery(store,recovery):
    plan=recovery['plan'];candidate=recovery['candidate']
    scene=validate_scene(store,plan['scene_ref'])
    ids=permission(scene['source_sha256'])['ordinary_t02_recovery_source_ids']
    adapter=LandAdapter('t02');policy=store.get_json(plan['policy_ref'],kind='policy')
    if (plan['implementation']!=adapter.describe()['implementation'] or
            plan['details']!=adapter.plan(store,scene,policy,
                dict(stage='t02',scene_ref=plan['scene_ref'],source_ids=ids),plan['details']['bounds'])):
        raise ValueError('SCOPED_LAND_PLAN_CHANGED')
    actual=adapter.verify(store,scene,policy,plan,candidate,
        {'scope':'complete-source-land-and-inclusive'},lambda _:None)
    if actual!=recovery['verification']or not actual['passed']or actual['inclusive_fills']:
        raise ValueError('SCOPED_LAND_RECONSTRUCTION_CHANGED')
    return actual


def check_export_surfaces(circles,rectangles,fixed):
    """Keep model-core and actual-export obligations on their own operands.

    T01 is immutable here: every actual contour must equal its qualified export.
    Exact original-core checks still apply to the nominal T01 scene. Actual new
    rectangle copper is checked both in that scene and against actual retained
    T01 contours, with ports derived exclusively from immutable source contacts.
    Existing native fidelity must separately pass for every exported target.
    """
    identities=[];model=[]
    for row in circles:
        if to_wkb(row['actual'])!=row['predecessor_export_wkb']:
            raise ValueError('SCOPED_T01_EXPORTED_CONTOUR_CHANGED:'+row['id'])
        identities.append(dict(source_id=row['id'],sha256=digest(row['predecessor_export_wkb'])))
        model.append(dict(id=row['id'],original=row['original'],candidate=row['nominal'],
                          native_source_kind='gr_circle',native_stroke_width_mm=0.))
    parts=[dict(id=r['id'],original=r['original'],candidate=r['actual'],
                native_source_kind='gr_poly',native_stroke_width_mm=0.)for r in rectangles]
    model.extend(parts)
    full=PreparedLandScene(model,fixed).check(model,materialize_scene=True,fail_fast=False)
    if not full['passed']:raise ValueError('SCOPED_EXACT_MODEL_SURFACE_FAILED:'+str(full['failures'][:10]))
    actual_fixed=[*fixed,*[dict(id=r['id'],geometry=r['actual'],trace_width_mm=0.)for r in circles]]
    checker=PreparedLandScene(parts,actual_fixed)
    original={r['id']:r['original']for r in [*circles,*rectangles]}
    original.update({r['id']:r['geometry']for r in fixed})
    for part in parts:
        sid=part['id']
        for oid in checker.ids:
            if oid==sid:continue
            overlap=original[sid].intersection(original[oid])
            port=None if overlap.is_empty else overlap.buffer(
                max(checker.widths[sid],checker.widths[oid])+checker.contract.original_port_buffer_gap_mm,
                quad_segs=checker.contract.port_quad_segs)
            checker.ports[(sid,oid)]=(port,not overlap.is_empty,original[sid].distance(original[oid]))
    actual=checker.check(parts,materialize_scene=True,fail_fast=False)
    if not actual['passed']:raise ValueError('SCOPED_ACTUAL_RECTANGLE_SURFACE_FAILED:'+str(actual['failures'][:10]))
    return dict(passed=True,exact_model_surface=full,actual_rectangle_surface=actual,
                exported_T01_identity=identities,file_grid_policy='UNCHANGED; separately verified native fidelity',
                port_authority='IMMUTABLE_ORIGINAL_SOURCE_CONTACTS_ONLY')


class ScopedRectangleExport(U04DataService):
    """Reuse U04's writer/checks with zero width changes and exact two targets."""
    def predecessor_root(self,host):return validate_host(host,'data')

    def __init__(self,host,output,recovery_store,recovery):
        BoardDataService.__init__(self,host)
        self.prefix_proof=validate_machine_prefix(self.previous)
        ids=permission(self.receipt['source_sha256'])['ordinary_t02_recovery_source_ids']
        candidate=recovery['candidate']
        verify_recovery(recovery_store,recovery)
        if {d['source_id']for d in candidate['decisions']}!=set(ids):
            raise ValueError('SCOPED_LAND_VERIFIED_TWO_RECTANGLES_REQUIRED')
        self.rectangle_sources={r['source_id']:r for r in recovery_store.get_json(candidate['output_scene_ref'],kind='scene')['objects']}
        self.rectangle_targets={d['source_id']:from_wkb(recovery_store.get(d['candidate_ref'],kind='geometry'))
                                for d in candidate['decisions']if d['status']=='GROWN'}
        if set(self.rectangle_targets)!=set(ids):raise ValueError('SCOPED_LAND_TWO_POSITIVE_RECOVERIES_REQUIRED')
        self.width_targets={};self.width_primitives={};self.width={};self.inclusive_targets={}
        self.out=Path(output);self.before=self.out/'before/board.kicad_pcb';self.board=self.out/'candidate/board.kicad_pcb'

    def finish(self,name,value):
        if name=='pcb_export_controls':
            measured,_,_=self.plot_check();validate_export_controls(value,measured)
        return super().finish(name,value)

    def plot_check(self,candidate_fcu=None):
        from src.pcb_data_abi import gerber
        paths=read(self.out/'pcb_gerber_export.json')['exports']
        plots=[gerber.parse(paths['before']['F.Cu']),gerber.parse(candidate_fcu or paths['candidate']['F.Cu'])]
        if any(not obj.polarity_dark for plot in plots for obj in plot.objects):
            raise ValueError('SCOPED_LAND_CLEAR_POLARITY_UNSUPPORTED')
        return super().plot_check(candidate_fcu)


def native_positions(raw):
    from src.source_locators import locate
    spans=locate(raw)
    top=[s for s in spans if s.parent_start==spans[0].start]
    return {s.identity:i+1 for i,s in enumerate(top)}


def verify_native_scope(service,prefix,source,actual_targets,receipt):
    from src.native_preparation import native_view,mutable_copy
    from src.pcb_data_abi import board_native
    from src.source_locators import locate
    original_board=native_view(service.raw.decode());candidate_board=native_view(service.board.read_text())
    previous_board=native_view((prefix/'data_output/candidate/board.kicad_pcb').read_text())
    positions=native_positions(service.raw)
    p=permission(receipt['source_sha256']);ids=p['ordinary_t02_recovery_source_ids'];allowed={positions[sid]for sid in ids}
    if len(previous_board)!=len(candidate_board):raise ValueError('SCOPED_NATIVE_OBJECT_COUNT_CHANGED')
    for i,(a,b)in enumerate(zip(previous_board,candidate_board)):
        if i not in allowed and a!=b:raise ValueError('SCOPED_PREDECESSOR_NATIVE_NODE_CHANGED:'+str(i))
    records=[]
    from shapely.affinity import scale
    from src.pcb_data_abi.board_geometry import fidelity
    for sid in ids:
        core=from_wkb(source.get(service.rectangle_sources[sid]['original_ref'],kind='geometry'))
        target=service.rectangle_targets[sid];actual=actual_targets[sid]
        cap=scale(core,1.25,1.25,origin=core.centroid)
        if not target.equals(cap):raise ValueError('SCOPED_RECTANGLE_FULL_CAP_NOT_RECOVERED')
        proof=fidelity(cap,actual)
        records.append(dict(source_id=sid,factors=[1.25,1.25],model_missing_area_mm2=cap.difference(target).area,
            added_area_mm2=target.difference(core).area,actual_missing_area_mm2=cap.difference(actual).area,
            native_node_sha256=digest(board_native.encode(mutable_copy(candidate_board[positions[sid]])).encode()),file_fidelity=proof))
    c028=p['blocked_full_circle_obligation_source_ids'][0];index=positions[c028]
    if original_board[index]!=candidate_board[index]:raise ValueError('SCOPED_C028_UNEVALUATED_WRITE')
    return dict(passed=True,rectangles=records,other_predecessor_nodes_unchanged=True,
        C028_full_circle_obligation='BLOCKED',C028_native_node='UNCHANGED_ORIGINAL',T04='NOT_RUN',
        source_sha256=receipt['source_sha256'],candidate_board_sha256=digest(service.board.read_bytes()))
