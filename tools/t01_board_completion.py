"""Stdlib report-only completion of a retained board pixel-audit failure.

No process launch, rendering, native audit submission or source-job mutation.
Operational completion does not turn a failed qualification into a pass.
"""
import hashlib,html,json,math,os,re
from pathlib import Path
from tools.t01_route_client import child,decode,encode,publish

ROOT=Path(__file__).resolve().parents[1]
STEPS=('pcb_inputs_verify','pcb_board_scope','pcb_board_verify','t01_compile','t01_discover','t01_inspect','t01_plan','t01_run','t01_verify','t01_compare','t01_review','t01_negative_compile','board_candidate_check','pcb_kicad_write','pcb_kicad_verify','pcb_gerber_export','pcb_gerber_verify','pcb_export_controls','render_compare','render_verify','render_controls')
STATUS='COMPLETED_WITH_FAILED_FINDINGS'


def sha(blob):return hashlib.sha256(blob).hexdigest()


def scoped(path):
    path=Path(path).absolute()
    if '..'in path.parts or not path.is_relative_to(ROOT/'out'):raise ValueError('COMPLETION_PROJECT_OUT_REQUIRED')
    return child(ROOT,path)


class Evidence:
    def __init__(self):self.files={}
    def blob(self,path,expected=None):
        path=scoped(path);blob=path.read_bytes();h=sha(blob)
        if expected is not None and h!=expected:raise ValueError('COMPLETION_EVIDENCE_HASH_MISMATCH:'+str(path))
        self.files[str(path)]=h;return blob
    def read(self,path,expected=None):return decode(self.blob(path,expected))
    def inventory(self,folder,manifest):
        folder=scoped(folder)
        for name,h in manifest.items():
            path=scoped(folder/name)
            if not path.is_relative_to(folder):raise ValueError('COMPLETION_MANIFEST_ESCAPE')
            self.blob(path,h)


def retained(job):
    """Verify all 19 accepted observations, failed attempt and bound file outputs."""
    job=scoped(job);root=job/'native';e=Evidence();row=e.read(job/'job.json')
    if row.get('task_scope')!='full-board'or row.get('job')!=str(job):raise ValueError('COMPLETION_BOARD_JOB_REQUIRED')
    e.read(root/'adapter_stopped.json')
    if not(job/'halted.json').exists():raise ValueError('COMPLETION_RETAINED_HALT_REQUIRED')
    e.read(job/'halted.json');e.read(root/'START.json')
    for name,record in row['inputs'].items():
        if name not in('kicad','gerber'):raise ValueError('COMPLETION_INPUT_SCOPE')
        e.blob(Path(row['staged'][name]),record['sha256'])
    policy=e.read(root/'DECISION_POLICY.json')
    if policy['operations']!=list(STEPS):raise ValueError('COMPLETION_SEQUENCE_CHANGED')
    attempts=[]
    for p in(root/'attempts').glob('*/receipt.json'):
        receipt=e.read(p);actual={str(q.relative_to(p.parent))for q in p.parent.rglob('*')if q.is_file()and q!=p}
        if actual!=set(receipt['files']):raise ValueError('COMPLETION_ATTEMPT_FILE_SET_CHANGED')
        e.inventory(p.parent,receipt['files']);attempts.append((receipt,p.parent))
    attempts.sort(key=lambda r:r[0]['completed_at'])
    if len(attempts)!=20 or [r['tool']for r,p in attempts]!=list(STEPS[:20]):raise ValueError('COMPLETION_PIXEL_FAILURE_SEQUENCE_REQUIRED')
    if len({r['attempt_id']for r,p in attempts})!=20:raise ValueError('COMPLETION_DUPLICATE_ATTEMPT')
    audits={}
    for p in(root/'audits').glob('*/request.json'):
        req=e.read(p)['arguments'];decision=e.read(p.parent/'decision.json')
        if req['attempt_id']in audits or decision['status']!='PASS_SLICE_OBSERVATION_AUDIT':raise ValueError('COMPLETION_OBSERVATION_INVALID')
        audits[req['attempt_id']]=(req['audit'],decision['accepted_operation'])
    if set(audits)!={r['attempt_id']for r,p in attempts[:19]}:raise ValueError('COMPLETION_OBSERVATION_COVERAGE')
    responses={};observations=[]
    for i,(receipt,folder)in enumerate(attempts[:19],1):
        result=e.read(folder/'result.json');audit,operation=audits[receipt['attempt_id']];raw=e.read(folder/'abi/stdout.json')
        if (receipt['status']!='PASS_BOARD_OPERATION_CHECKS'or result['error']is not None or operation!=receipt['tool']or audit['verdict']!='PASS'or audit['response_sha256']!=sha((folder/'abi/stdout.json').read_bytes())or audit['observed']!=result['result']['facts']):raise ValueError('COMPLETION_OBSERVATION_MISMATCH')
        review=e.read(root/f'operator_ui/review-{i}.json');summary=e.read(root/f'operator_ui/summary-{i}.json',review['summary_sha256'])
        if (review['attempt_id']!=receipt['attempt_id']or review['audit']!=audit or summary['facts']!=audit['observed']or review['agent_observation_sha256']!=sha(review['agent_observation'].encode())or review['agent_observation_sha256']not in audit['note']):raise ValueError('COMPLETION_AGENT_OBSERVATION_CHANGED')
        observations.append(review['agent_observation']);responses[operation]=raw['result']
    if len(set(observations))!=19:raise ValueError('COMPLETION_DISTINCT_OBSERVATIONS_REQUIRED')
    failed,folder=attempts[-1];failure=e.read(folder/'result.json');native=e.read(folder/'abi/stdout.json');execution=e.read(folder/'abi/execution.json')
    error=native.get('error')or{};match=re.fullmatch(r'RASTER_FIDELITY_EXCEEDED:sample:([0-9.eE+-]+)',error.get('message',''))
    if (failed['status']!='FAIL'or failure['result']is not None or not failure['error']or native['status']!='REJECTED'or native['operation']!='render_verify'or error.get('code')!='RENDER_REJECTED'or not match):raise ValueError('COMPLETION_RENDER_TOLERANCE_FAILURE_REQUIRED')
    value=float(match[1])
    if not math.isfinite(value)or value<=0:raise ValueError('COMPLETION_FAILED_MEASUREMENT_INVALID')
    host=e.read(root/'pipeline_render_host.json',execution['registry_sha256'])
    if host['schema']!='pcb-board-render-host/1'or Path(host['output'])!=root/'render_output':raise ValueError('COMPLETION_HOST_SCOPE')
    contract=e.read(Path(host['contract_path']),host['contract_sha256']);checkpoint=e.read(Path(host['checkpoint']),host['checkpoint_sha256'])
    if Path(host['checkpoint'])!=root/'EXPORT_CHECKPOINT.json'or checkpoint['operations']!=list(STEPS[:18]):raise ValueError('COMPLETION_EXPORT_CHECKPOINT_REQUIRED')
    required={'RECEIPT.json','data_board/verified.json','T01_CHECKPOINT.json','data_output/pcb_gerber_export.json','data_output/pcb_gerber_verify.json','data_output/pcb_export_controls.json','data_output/candidate/board.kicad_pcb','data_output/candidate/gerbers/board-F_Cu.gbr'}
    if not required<=checkpoint['files'].keys():raise ValueError('COMPLETION_EXPORT_EVIDENCE_MISSING')
    e.inventory(root,checkpoint['files'])
    source=e.read(root/'RECEIPT.json');scope=e.read(root/'data_board/verified.json')
    if source.get('status')!='PASS_BOARD_T01_VERIFIED'or source.get('scope_sha256')!=e.files[str(root/'data_board/verified.json')]or scope.get('facts',{}).get('complete_source_coverage')is not True:raise ValueError('COMPLETION_VERIFIED_SOURCE_REQUIRED')
    bands=contract['raster_boundary_error_mm']
    if bands!={'kicad':.001,'gerber':.005}or value<=min(bands.values()):raise ValueError('COMPLETION_RETAINED_TOLERANCE_REQUIRED')
    # Below the Gerber band, only the KiCad check can emit this rejection.
    panel='kicad'if value<=bands['gerber']else'not_retained';limit=bands['kicad']if panel=='kicad'else None
    render=responses['render_compare'];saved=e.read(root/'render_output/render.json')
    if saved!=render:raise ValueError('COMPLETION_RENDER_RECEIPT_CHANGED')
    e.inventory(root/'render_output',render['files'])
    plan=e.read(root/'render_output/tile_plan.json')
    if plan!=contract['tiles']:raise ValueError('COMPLETION_TILE_PARTITION_CHANGED')
    for name,record in render['input_files'].items():e.blob(ROOT/record['path'],record['sha256'])
    if not render['facts']['complete_board_coverage']or render['facts']['geometry_edited']:raise ValueError('COMPLETION_COMPLETE_VIEWS_REQUIRED')
    tiles=plan['tiles'];audits=[];unrun_seen=False
    for tile in tiles:
        p=root/'render_output/tiles'/tile['id']/'audit.json'
        if not p.exists():unrun_seen=True;continue
        if unrun_seen:raise ValueError('COMPLETION_NONCONTIGUOUS_PIXEL_AUDITS')
        a=e.read(p)
        if a['tile']!=tile or set(a['audits'])!={'kicad','gerber'}or any(v['passed']is not True or v['mismatches_outside_band']!=0 or v['pixels_checked']!=math.prod(tile['pixels'])or v['allowed_boundary_error_mm']!=bands[name]for name,v in a['audits'].items()):raise ValueError('COMPLETION_PIXEL_AUDIT_CHANGED')
        audits.append(a)
    if len(audits)>=len(tiles)or(root/'render_output/verification.json').exists()or(root/'render_output/controls.json').exists():raise ValueError('COMPLETION_FAILED_AUDIT_DISPOSITION_INCONSISTENT')
    write=responses['pcb_kicad_write'];export=responses['pcb_gerber_export'];e.blob(Path(write['board']),write['board_sha256'])
    for name,h in export['output_sha256'].items():e.blob(Path(name),h)
    f=responses['board_candidate_check']['facts'];g=responses['pcb_gerber_verify']['facts']
    if not all(f.get(k)is True for k in('passed','complete_source_coverage','full_reconstruction_passed','protected_sources_unchanged'))or not g['protected_fcu_atoms_equal']or g['protected_other_layers']!=8:raise ValueError('COMPLETION_VERIFIED_EXPORTS_REQUIRED')
    finding=dict(id='RENDER_PIXEL_TOLERANCE',status='FAIL',operation='render_verify',panel=panel,panel_basis='Inferred from failed sample being below the Gerber failure threshold'if panel=='kicad'else'Failure record does not retain panel identity',tile=tiles[len(audits)]['id'],observed_sample_mm=value,allowed_boundary_error_mm=limit,message=error['message'],whole_tile_maximum='NOT_ESTABLISHED; auditor stopped on a failing sample batch',receipt_sha256=e.files[str(folder/'receipt.json')])
    ledger=[dict(operation=op,status='PASS'if i<19 else'FAIL'if i==19 else'NOT_RUN',reason='Retained native result and separate observation'if i<19 else'Failed pixel finding retained'if i==19 else'Blocked by failed pixel verification; no new rendering authorized')for i,op in enumerate(STEPS)]
    return dict(schema='pcb-board-completion/1',status=STATUS,task_outcome=STATUS,terminal=True,next_action='REPORT_AND_STOP',mode='REPORT_ONLY_RETAINED_EVIDENCE',pipeline_finished=True,native_pipeline_status='HALTED_RETAINED_UNCHANGED',render_qualification='FAIL',owner='PENDING_USER',independent='NOT_RUN: CHANNEL_UNAVAILABLE',electrical_manufacturing='NOT_ESTABLISHED',job=str(job),rerendered=False,new_native_operations=0,native_slices_passed=19,native_slices_failed=1,native_slices_not_run=1,distinct_observation_audits=19,canonical_sites=f['canonical_sites'],source_occurrences=f['aliases'],findings=[finding],operations=ledger,tiles=tiles,pixel_tiles_passed=len(audits),pixel_tiles_failed=1,pixel_tiles_not_run=len(tiles)-len(audits)-1,render_controls='NOT_RUN',kicad=write['board'],gerber=str(root/'data_output/candidate/gerbers/board-F_Cu.gbr'),display=str(root/'render_output/comparison.png'),source_files=e.files)


def finalize(job,output_base=None):
    result=retained(job);base=scoped(output_base or ROOT/'out/operator_routes/t01_board/completions')
    if base.is_relative_to(Path(result['job'])):raise ValueError('COMPLETION_MUST_BE_ADDITIVE')
    key=sha(encode(dict(job=result['job'],sources=result['source_files'],finalizer=sha(Path(__file__).read_bytes()))));folder=base/key
    if folder.exists():
        manifest=decode((folder/'MANIFEST.json').read_bytes())
        if {str(p.relative_to(folder))for p in folder.rglob('*')if p.is_file()and p.name!='MANIFEST.json'}!=set(manifest):raise ValueError('COMPLETION_REPORT_FILE_SET_CHANGED')
        Evidence().inventory(folder,manifest)
        cached=decode((folder/'COMPLETION.json').read_bytes())
        if any(cached.get(k)!=v for k,v in result.items()):raise ValueError('COMPLETION_REPORT_CHANGED')
        return cached
    folder.mkdir(parents=True);finding=result['findings'][0];views=[]
    for i,tile in enumerate(result['tiles']):
        status='PASS'if i<result['pixel_tiles_passed']else'FAIL'if i==result['pixel_tiles_passed']else'NOT_RUN'
        detail=folder/'tiles'/tile['id']/'index.html';detail.parent.mkdir(parents=True)
        originals=Path(result['job'])/'native/render_output/tiles'/tile['id']
        k=os.path.relpath(originals/'kicad.png',detail.parent);g=os.path.relpath(originals/'gerber.png',detail.parent)
        page=f'''<!doctype html><meta charset="utf-8"><title>{tile['id']}: {status}</title><style>body{{font:17px system-ui;background:#eef3f7;color:#152a40}}.finding{{background:#ffe6de;border:2px solid #b53718;padding:15px}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:15px}}img{{width:100%}}</style><h1>{tile['id']} — {status}</h1><p class="finding">Workflow completed with failed findings. Rendering qualification FAIL. This tile's retained pixel status: {status}. Owner PENDING_USER. No images regenerated.</p><p><a href="../../index.html">Completion report and all tile statuses</a>. Native bounds: {html.escape(str(tile['bounds_mm']))}. Click a PNG for full-resolution browser zoom.</p><div class="pair"><section><h2>Candidate KiCad</h2><a href="{k}"><img src="{k}"></a></section><section><h2>Candidate Gerber</h2><a href="{g}"><img src="{g}"></a></section></div>'''
        detail.write_text(page);views.append(dict(id=tile['id'],status=status,html=str(detail)))
    result['tile_views']=views;result['html']=str(folder/'index.html');result['evidence']=str(folder)
    png=os.path.relpath(result['display'],folder);kicad=os.path.relpath(result['kicad'],folder);gerber=os.path.relpath(result['gerber'],folder)
    value=finding['observed_sample_mm']*1000;limit=finding['allowed_boundary_error_mm'];band=f'{limit*1000:.6g} µm'if limit is not None else'original 1/5 µm KiCad/Gerber bands'
    links=''.join(f'<a class="{v["status"]}" href="tiles/{v["id"]}/index.html">{v["id"]}<small>{v["status"]}</small></a>'for v in views)
    page=f'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Whole-board pipeline completed with failed findings</title><style>body{{font:17px system-ui;line-height:1.55;background:#eef3f7;color:#152a40;max-width:1450px;margin:30px auto;padding:0 20px}}section{{background:white;padding:22px;margin:22px 0}}.finding{{border:3px solid #b53718;background:#fff0e9}}img{{width:100%}}.tiles{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}}.tiles a{{padding:9px;border:2px solid #8293a4;font-size:14px}}small{{display:block}}.tiles .FAIL{{border-color:#b53718;background:#ffe6de}}.tiles .PASS{{border-color:#21804b}}</style><h1>Whole-board pipeline completed with failed findings</h1><section class="finding"><h2>Rendering FAIL — original audit preserved</h2><p>{html.escape(finding['tile'])}: retained failing sample <strong>{value:.6f} µm</strong>; allowed {band}. This is a failed sample, not a measured maximum for the entire tile. Source, growth, KiCad/Gerber export and display production passed their recorded gates.</p><p>19 native slices/observations PASS; pixel verification FAIL; final controls NOT_RUN. Pixel tiles: {result['pixel_tiles_passed']} PASS, one FAIL/partially audited, {result['pixel_tiles_not_run']} NOT_RUN. Every one of the 21 planned slices has an explicit terminal disposition. Report completion is not qualification or acceptance.</p><p>No rendering, geometry construction, export, native audit submission or source-job edit occurred during finalization. The original native attempt stays HALTED. Owner PENDING_USER; independent NOT_RUN; electrical/manufacturing NOT_ESTABLISHED.</p></section><section><h2>Verified candidates and findings</h2><p>{result['canonical_sites']} canonical sites / {result['source_occurrences']} source occurrences. <a href="{kicad}">KiCad</a> · <a href="{gerber}">F.Cu Gerber</a> · <a href="COMPLETION.json">Machine-readable completion, findings and evidence hashes</a> · <a href="MANIFEST.json">Report manifest</a></p></section><section><h2>Candidate KiCad versus Gerber</h2><p>Retained overview for navigation only. Each linked tile shows its audit disposition.</p><img src="{png}"><div class="tiles">{links}</div></section>'''
    (folder/'index.html').write_text(page)
    result['ready_markdown']=f'''Whole-board pipeline **completed with failed findings** using retained outputs. No rendering was rerun.

T01 growth and KiCad/Gerber export passed for {result['canonical_sites']} canonical sites and {result['source_occurrences']} source occurrences. Rendering remains **FAIL**: {finding['tile']}, reported sample {value:.6f} µm versus {band}. {result['pixel_tiles_passed']}/{len(result['tiles'])} tiles passed pixel audit; the failed tile is partial and {result['pixel_tiles_not_run']} are NOT_RUN. Final render controls are NOT_RUN.

[Side-by-side review and failed findings]({result['html']}) · [KiCad]({result['kicad']}) · [F.Cu Gerber]({result['gerber']}) · [Completion record]({folder/'COMPLETION.json'})

All 21 planned slices are accounted for: 19 PASS, one FAIL, one NOT_RUN. Original native failure evidence is unchanged. This is operational completion, not a passed renderer qualification. Owner review remains pending; independent, electrical and manufacturing approval are not established.'''
    publish(folder/'COMPLETION.json',encode(result))
    outputs={str(p.relative_to(folder)):sha(p.read_bytes())for p in folder.rglob('*')if p.is_file()}
    publish(folder/'MANIFEST.json',encode(outputs));return result


def compact(result):
    """Keep the large source custody map in its verified additive completion."""
    return {k:v for k,v in result.items()if k not in('source_files','tiles','tile_views')}
