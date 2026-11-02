"""One-command lifecycle, owned native processes and explicit machine reporting."""
from pathlib import Path
import sys,time,threading,subprocess
import pytest
from tools.pcb_t01_board_run import OwnedRunner


def test_owned_native_runner_preserves_real_exit_and_output(tmp_path):
    runner=OwnedRunner();result=runner([sys.executable,'-c','import sys; print("actual output"); sys.exit(7)'],cwd=tmp_path,timeout=5)
    assert result.returncode==7 and result.stdout==b'actual output\n'


def test_native_timeout_keeps_partial_output_and_stops_only_owned_process(tmp_path):
    runner=OwnedRunner()
    with pytest.raises(subprocess.TimeoutExpired)as error:runner([sys.executable,'-u','-c','import time; print("partial"); time.sleep(10)'],cwd=tmp_path,timeout=.15)
    assert b'partial'in error.value.stdout and runner.current is None


def test_interrupt_cancels_owned_work_and_prevents_a_later_launch(tmp_path):
    runner=OwnedRunner();out=[]
    thread=threading.Thread(target=lambda:out.append(runner([sys.executable,'-c','import time; time.sleep(10)'],cwd=tmp_path,timeout=20)));thread.start()
    until=time.monotonic()+5
    while runner.current is None and time.monotonic()<until:time.sleep(.01)
    runner.cancel();thread.join(timeout=5)
    assert not thread.is_alive()and out[0].returncode!=0
    with pytest.raises(OSError,match='CANCELLED'):runner([sys.executable,'-c','print(1)'],cwd=tmp_path)


def test_terminal_entry_has_one_explicit_directory_and_no_launcher_requirement():
    root=Path(__file__).resolve().parents[1];wrapper=(root/'tools/Run_T01_Board.command').read_text();script=(root/'tools/pcb_t01_board_run.py').read_text()
    assert 'pcb_t01_board_run.py'in wrapper and '.venv/bin/python'in wrapper
    assert "add_argument('--input-dir',required=True"in script
    assert 'jobs.launcher_ready('not in script and 'native_intake('not in script


def test_machine_delivery_reports_machine_checks_and_zero_observations(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    from tools import t01_board_auto_operator as module
    from tools.t01_route_client import encode
    from tools.pcb_c01_operator import sha
    root=tmp_path/'native';root.mkdir();page=root/'export_review.html';page.write_text('18 separate observation audits');(root/'EXPORT_CHECKPOINT.json').write_text('{}')
    proofs=root/'audits/machine-001';proofs.mkdir(parents=True);(proofs/'proof.json').write_bytes(encode(dict(status='PASS')))
    original=dict(files=[dict(path=str(page),sha256=sha(page.read_bytes()),bytes=page.stat().st_size)],html=str(page),ready_markdown='18 separate observation audits',observation_audits=18)
    monkeypatch.setattr(module.ExportOperator,'delivery',lambda self:original)
    operator=module.MachineOperator.__new__(module.MachineOperator);operator.client=SimpleNamespace(root=root);operator.verify_observations=lambda:None
    result=operator.delivery()
    assert result['machine_audits']==18 and result['observation_audits']==0
    assert result['human_or_agent_observations']=='NOT_RUN'and 'machine audits'in result['ready_markdown']
    assert not list(root.rglob('review-*.json'))
    record=next(f for f in result['files']if f['path']==str(page));assert record['sha256']==sha(page.read_bytes())
    assert json.loads((root/'MACHINE_RECEIPT.json').read_bytes())['owner']=='PENDING_USER'


def test_wait_detects_dead_adapter_before_native_timeout(tmp_path):
    from tools.pcb_t01_board_operator import BoardClient
    from tools.pcb_t01_board_run import adapter_health
    from types import SimpleNamespace
    client=BoardClient.__new__(BoardClient)
    client.submit=lambda *args:'pending'
    client.replies=tmp_path
    client.health_check=lambda:adapter_health(SimpleNamespace(is_alive=lambda:False),[])
    started=time.monotonic()
    with pytest.raises(RuntimeError,match='ADAPTER_EXITED_WITHOUT_REPLY'):
        client.call('t01_run',{})
    assert time.monotonic()-started<1


def test_adapter_error_keeps_errno_and_recording_failure_is_visible(tmp_path,monkeypatch,capsys):
    from tools import pcb_t01_board_run as module
    from types import SimpleNamespace
    record=dict(error_type='OSError',errno=28,error='No space left on device',traceback='original failure')
    with pytest.raises(RuntimeError,match='No space left'):
        module.adapter_health(SimpleNamespace(is_alive=lambda:False),[record])
    def full(*args):raise OSError(28,'No space left on device')
    monkeypatch.setattr(module,'publish',full)
    module.retain_error(tmp_path/'failure.json',record)
    output=capsys.readouterr().err
    assert 'evidence_write_failed'in output and 'original failure'in output and '28'in output


def test_native_exit_evidence_survives_later_adapter_failure(tmp_path):
    import json
    runner=OwnedRunner(tmp_path/'evidence')
    runner([sys.executable,'-c','import sys; print("retained"); sys.exit(7)'],cwd=tmp_path)
    record=json.loads(next((tmp_path/'evidence').glob('process-*.json')).read_text())
    assert record['returncode']==7 and record['stdout']=='retained\n'
