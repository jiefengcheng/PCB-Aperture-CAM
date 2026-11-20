from types import SimpleNamespace
import pytest
from shapely.geometry import box
from src.gerber_u05 import performance
from src.stage_abi.store import canonical,digest
from src.u05_board.coverage import CoverageAdapter
from src.t05_certified_execution import MEMO_BYTES


def bind(run):
    path=run/performance.T05_SNAPSHOT
    (run/'PRODUCER_BINDING.json').write_bytes(canonical(dict(job_inputs={str(path):digest(path.read_bytes())})))


def test_explicit_profile_is_sealed_and_independent_of_reference_parse_cache(tmp_path):
    assert performance.t05_profile(tmp_path)is None
    performance.capture_t05(tmp_path)
    with pytest.raises(FileNotFoundError):performance.t05_profile(tmp_path)
    bind(tmp_path)
    assert performance.t05_profile(tmp_path)==performance.T05_PROFILE
    a=performance.configure_t05_adapter(tmp_path,CoverageAdapter(box(0,0,1,1)))
    assert a.certificate_consumption and a.geometry_budgets['memo_bytes']==MEMO_BYTES
    assert not(tmp_path/performance.SNAPSHOT).exists()
    assert performance.T05_PROFILE['reference_measurement_bank']is False
    with pytest.raises(FileExistsError):performance.capture_t05(tmp_path)


def test_mutated_and_resealed_unsupported_profile_fail_closed(tmp_path):
    performance.capture_t05(tmp_path);bind(tmp_path)
    path=tmp_path/performance.T05_SNAPSHOT
    bad=dict(performance.T05_PROFILE,memo_bytes=1024**3)
    path.write_bytes(canonical(bad))
    with pytest.raises(ValueError,match='UNBOUND'):performance.t05_profile(tmp_path)
    bind(tmp_path)
    with pytest.raises(ValueError,match='UNSUPPORTED'):performance.t05_profile(tmp_path)


def test_symlink_profile_is_never_authority(tmp_path):
    external=tmp_path/'external';external.write_bytes(canonical(performance.T05_PROFILE))
    (tmp_path/performance.T05_SNAPSHOT).symlink_to(external);bind(tmp_path)
    with pytest.raises(ValueError,match='UNBOUND'):performance.t05_profile(tmp_path)


def test_certificate_optin_requires_fresh_t02_t05_boundary_before_reading_prefix(tmp_path):
    from src.gerber_u05.incremental import prepare
    with pytest.raises(ValueError,match='REQUIRE_T04_PREFIX'):
        prepare(tmp_path/'missing',tmp_path/'job',through='t02',t05_certificates=True)


def test_actual_gerber_t04_t02_t05_pipeline_uses_integrated_profile_without_changing_copper(tmp_path):
    from tests.gerber_u05.test_gerber_source import source_circle
    from src.gerber_u05 import pipeline as p
    from src.t04_settings import capture_job
    outcomes=[]
    for enabled in (False,True):
        run=tmp_path/str(enabled);store=p.Store(run/'runtime')
        capture_job(run)
        source=p.build_source(store,source_circle());scene=store.get_json(source['scene_ref'],kind='scene')
        t04=p.run_t04(store,scene)
        t02=p.run_t02(store,store.get_json(t04['output_scene_ref'],kind='scene'))
        if enabled:performance.capture_t05(run);bind(run)
        t05=p.run_t05(store,store.get_json(t02['output_scene_ref'],kind='scene'),t04)
        assert t02['verification']['passed']and t05['verification']['passed']
        assert t05['candidate']['coverage']['grown']>0
        outcomes.append((store.get(t05['candidate']['after_ref'],kind='geometry'),t05['candidate']['decisions']))
    assert outcomes[0]==outcomes[1]
