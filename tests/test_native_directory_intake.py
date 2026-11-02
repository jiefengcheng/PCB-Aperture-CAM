"""Native ingestion is reproducible and file-only for restricted clients."""
import errno,json,os,subprocess
from pathlib import Path
import pytest
from tools import t01_crop_jobs as jobs,t01_board_export_jobs as exports
from tools.t01_route_client import encode,publish
from src.pcb_data_abi import input_directory as intake
from src.pcb_data_abi.raw_directory import parse_raw,image,compare_images,match_candidates
from shapely import affinity
from shapely.geometry import Point

RAW=b'%FSLAX33Y33*%\n%MOMM*%\n%ADD10C,0.2*%\n%IPPOS*%\n%LNarbitrary-name*%\nD10*\nX1000Y1000D03*\nM02*\n'

def test_legacy_metadata_and_units_are_explicit_and_bytes_unchanged():
    blob=RAW;g,objects,profile=parse_raw(blob,'misleading-bottom.gbr')
    assert len(g.objects)==1 and profile['coordinate_format']==[3,3]
    assert profile['explicit_legacy_metadata']==['%IPPOS*%','%LNarbitrary-name*%']
    assert profile['registration_fit_used']is False and blob==RAW
    a=image(objects);assert compare_images(a,a,profile['correspondence_tolerance_mm'])['passed']
    assert not compare_images(a,affinity.translate(a,xoff=.02),profile['correspondence_tolerance_mm'])['passed']
    assert not compare_images(a,a.union(Point(2,2).buffer(.05)),profile['correspondence_tolerance_mm'])['passed']

@pytest.mark.parametrize('blob',[RAW.replace(b'IPPOS',b'IPNEG'),RAW.replace(b'MOMM',b'MOIN'),RAW.replace(b'M02*',b''),RAW.replace(b'M02*',b'%SRX2Y2I1J1*%\nM02*'),RAW.replace(b'X1000Y1000D03*',b'X1000Y1000D03*\n%IPPOS*%')])
def test_legacy_profile_failures_do_not_become_passes(blob):
    with pytest.raises(Exception):parse_raw(blob,'source')

def test_missing_or_duplicate_geometry_assignment_rejects():
    assert match_candidates({'wrong-name':['F.Cu'],'unmatched':[]})=={'wrong-name':'F.Cu'}
    for candidates in[{'a':[]},{'a':['F.Cu','F.Mask']},{'a':['F.Cu'],'renamed':['F.Cu']}]:
        with pytest.raises(ValueError):match_candidates(candidates)

@pytest.mark.parametrize('number',[errno.EPERM,errno.EACCES])
def test_denied_walk_retains_errno_and_exact_path(tmp_path,monkeypatch,number):
    def denied(root,**kw):
        kw['onerror'](PermissionError(number,os.strerror(number),str(root)));return iter(())
    monkeypatch.setattr(intake.os,'walk',denied)
    with pytest.raises(intake.IntakeAccessError)as exc:intake.collect_raw(tmp_path)
    assert exc.value.details['errno']==number and exc.value.details['path']==str(tmp_path)
    assert 'EXACTLY_ONE_KICAD'not in str(exc.value)and 'TCC'not in str(exc.value)


def test_client_native_intake_has_no_source_io_or_process_launch(tmp_path,monkeypatch):
    monkeypatch.setattr(jobs,'ROOT',tmp_path);registry=tmp_path/'out/launcher';registry.mkdir(parents=True)
    for name in['inbox','replies','calls']:(registry/name).mkdir()
    monkeypatch.setattr(jobs,'LAUNCHER',registry)
    job=tmp_path/'out/managed/jobs/unique';job.mkdir(parents=True);row=dict(task_scope=exports.SCOPE);publish(job/'job.json',encode(row))
    supplied=Path('/unreadable/source/ordinary English')
    def forbidden(*a,**kw):pytest.fail('Embedded client attempted source IO or process launch')
    monkeypatch.setattr(exports,'collect',forbidden);monkeypatch.setattr(exports,'allocate',forbidden);monkeypatch.setattr(subprocess,'Popen',forbidden)
    original_stat=Path.stat
    def guarded_stat(self,*a,**k):
        if self==supplied or supplied in self.parents:forbidden()
        return original_stat(self,*a,**k)
    monkeypatch.setattr(Path,'stat',guarded_stat)
    def heartbeat():
        for request in(registry/'inbox').glob('*.json'):
            req=json.loads(request.read_bytes());assert req['input_directory']==str(supplied)
            reply=registry/'replies'/request.name
            if not reply.exists():publish(reply,encode(dict(status='INTAKE_READY',launcher_id='native',job=str(job),job_sha256=jobs.digest((job/'job.json').read_bytes()))))
        return dict(launcher_id='native',directory_intake='native-directory/1')
    monkeypatch.setattr(jobs,'launcher_ready',heartbeat)
    assert exports.native_intake(supplied,timeout=1)==(job,row)


def test_client_access_failure_has_retained_native_evidence(tmp_path,monkeypatch):
    monkeypatch.setattr(jobs,'ROOT',tmp_path);registry=tmp_path/'out/launcher';registry.mkdir(parents=True)
    for name in['inbox','replies','calls']:(registry/name).mkdir()
    monkeypatch.setattr(jobs,'LAUNCHER',registry)
    details=dict(code='INPUT_DIRECTORY_ACCESS_FAILED',errno=1,path='/denied',os_message='Operation not permitted')
    def heartbeat():
        for request in(registry/'inbox').glob('*.json'):
            reply=registry/'replies'/request.name
            if not reply.exists():publish(reply,encode(dict(status='HALTED',launcher_id='native',error='INPUT_DIRECTORY_ACCESS_FAILED',error_details=details)))
        return dict(launcher_id='native',directory_intake='native-directory/1')
    monkeypatch.setattr(jobs,'launcher_ready',heartbeat)
    with pytest.raises(exports.NativeIntakeError)as exc:exports.native_intake('/denied',timeout=1)
    assert exc.value.details==details and '/calls/intake-'in exc.value.evidence


def test_old_launcher_fails_actionably_without_reading_sources(monkeypatch):
    monkeypatch.setattr(jobs,'launcher_ready',lambda:dict(launcher_id='old'))
    with pytest.raises(ValueError,match='NATIVE_LAUNCHER_UPDATE_REQUIRED'):exports.native_intake('/not-accessed')


def test_full_image_containment_checks_holes_and_islands():
    from shapely.geometry import box
    a=box(0,0,10,10).difference(box(2,2,3,3));b=a.union(box(20,20,21,21))
    assert not compare_images(a,b,.001)['passed']
    assert not compare_images(a,box(0,0,10,10),.001)['passed']
    assert compare_images(a,a,.000024)['passed']


def test_real_identification_ignores_names_and_preserves_unmatched_bytes(tmp_path,monkeypatch):
    from src.pcb_data_abi import raw_directory as module
    from src.pcb_data_abi.service import plot_name
    cli=tmp_path/'cli';cli.write_bytes(b'native CLI test double');monkeypatch.setattr(module,'CLI',cli);monkeypatch.setattr(module,'CLI_SHA',intake.digest(cli.read_bytes()))
    monkeypatch.setattr(module,'inventory',lambda b:dict(objects=[dict(layers=['F.Cu']),dict(layers=['F.Mask'])]))
    raw=tmp_path/'raw';raw.mkdir();out=tmp_path/'proof';out.mkdir()
    blobs={'raw.kicad_pcb':b'(kicad_pcb)', 'bottom misleading.gbr':RAW,'unrepresented.gbr':RAW.replace(b'X1000',b'X50000')}
    originals=dict(blobs)
    def native(argv,stem):
        if stem=='version':return '10.99.0'
        for layer,x in[('F.Cu',1000000),('F.Mask',2000000)]:
            body=RAW.replace(b'%IPPOS*%\n',b'').replace(b'%LNarbitrary-name*%\n',b'').replace(b'33Y33',b'46Y46').replace(b'X1000Y1000',f'X{x}Y1000000'.encode())
            (out/'source_plots'/plot_name(layer)).write_bytes(body)
    manifest=module.identify(raw,blobs,[],out,native)
    assert blobs==originals
    assert {r['relative_path']:r['layer']for r in manifest['files']if r['kind']=='gerber'}=={'bottom misleading.gbr':'F.Cu'}
    assert manifest['identification']['excluded_companions']==['unrepresented.gbr']
    snapshot=tmp_path/'snapshot';snapshot.mkdir()
    for name,blob in blobs.items():(snapshot/name).write_bytes(blob)
    assert intake.verify_snapshot(manifest,snapshot)['F.Cu'].name=='bottom misleading.gbr'
    (snapshot/'unrepresented.gbr').write_bytes(b'changed')
    with pytest.raises(ValueError,match='SNAPSHOT_CHANGED'):intake.verify_snapshot(manifest,snapshot)


def test_fifo_cannot_hang_native_intake(tmp_path):
    fifo=tmp_path/'not-a-regular-gerber';os.mkfifo(fifo)
    with pytest.raises(ValueError,match='SIZE_OR_TYPE'):intake.regular_bytes(fifo)


@pytest.mark.parametrize('end',[(1,0),(0,1),(1,1)])
def test_rectangular_stroke_is_exact_sweep_not_circular_equivalent_width(end):
    from gerbonara import graphic_objects as go
    from gerbonara.apertures import RectangleAperture
    from gerbonara.utils import MM
    from shapely.geometry import box
    from src.pcb_data_abi.raw_directory import raw_object_geometry
    x,y=end;obj=go.Line(x1=0,y1=0,x2=x,y2=y,aperture=RectangleAperture(w=.2,h=.4,unit=MM),unit=MM)
    expected=box(-.1,-.2,.1,.2).union(box(x-.1,y-.2,x+.1,y+.2)).convex_hull
    assert raw_object_geometry(obj).symmetric_difference(expected).area<1e-15
    # The old generic helper's circular equivalent width is detectably different.
    from src.gerber_image import object_geometry
    assert object_geometry(obj).symmetric_difference(expected).area>.001


def test_buffer_dilation_preserves_all_pieces_and_holes_despite_nested_shell_aggregate(monkeypatch):
    from shapely.geometry import box,MultiPolygon,Polygon
    from shapely.geometry.base import BaseGeometry
    from src.pcb_data_abi.raw_directory import buffer_image
    # Models the GEOS nested-shell result seen with the actual board. The
    # mathematical result is the union of all valid buffer pieces, not a hole.
    source=box(0,0,1,1);outer=box(-1,-1,2,2);nested=box(0,0,.5,.5)
    aggregate=MultiPolygon([outer,nested]);assert not aggregate.is_valid
    monkeypatch.setattr(BaseGeometry,'buffer',lambda *a,**k:aggregate)
    actual=buffer_image(source,.1);assert actual.is_valid and actual.equals(outer)
    with_hole=Polygon(outer.exterior.coords,[box(0,0,1,1).exterior.coords])
    monkeypatch.setattr(BaseGeometry,'buffer',lambda *a,**k:with_hole)
    assert buffer_image(source,.1).equals(with_hole)
