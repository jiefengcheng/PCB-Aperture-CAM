"""File-only embedded client launch checks; native process boundary stays explicit."""
from pathlib import Path
import os,time
import pytest
from tools import t01_crop_jobs as jobs
from tools.t01_route_client import encode,publish


def test_missing_stale_and_stopped_launcher_halt_without_process_ops(tmp_path,monkeypatch):
    monkeypatch.setattr(jobs,'ROOT',tmp_path);monkeypatch.setattr(jobs,'LAUNCHER',tmp_path/'out/launcher')
    jobs.LAUNCHER.mkdir(parents=True)
    for row in [None,dict(status='STOPPED',updated_at=time.time()),dict(status='READY',updated_at=time.time()-100)]:
        if row is not None:
            jobs.replace(jobs.LAUNCHER/'current.json',dict(schema='pcb-native-launcher/1',launcher_id='host',**row))
        with pytest.raises(ValueError,match='NATIVE_LAUNCHER_REQUIRED'):jobs.launcher_ready()


def test_embedded_launch_uses_only_mailbox_not_os_process_operations(tmp_path,monkeypatch):
    import subprocess
    monkeypatch.setattr(jobs,'ROOT',tmp_path);host=tmp_path/'out/launcher';host.mkdir(parents=True)
    monkeypatch.setattr(jobs,'LAUNCHER',host);(host/'inbox').mkdir();(host/'replies').mkdir()
    job=tmp_path/'out/job';job.mkdir();publish(job/'job.json',b'{}')
    (job/'native').mkdir();publish(job/'native/operator_binding.json',b'{}')
    publish(job/'ready.json',encode(dict(session=str(job/'native'),binding_sha256=jobs.digest(b'{}'))))
    publish(job/'launch.json',encode(dict(launcher_id='host')))
    publish(job/'worker_status.json',encode(dict(launcher_id='host',status='RUNNING',updated_at=time.time())))
    def forbidden(*a,**k):raise OSError(45,'OS process operations are unavailable in embedded Python')
    monkeypatch.setattr(subprocess,'Popen',forbidden);monkeypatch.setattr(os,'kill',forbidden)
    def heartbeat():
        pending=list((host/'inbox').glob('*.json'))
        for p in pending:
            reply=host/'replies'/p.name
            if not reply.exists():publish(reply,encode(dict(status='LAUNCHED',launcher_id='host',job=str(job))))
        return dict(launcher_id='host')
    monkeypatch.setattr(jobs,'launcher_ready',heartbeat)
    assert jobs.launch(job)==job/'native/operator_binding.json'
    assert len(list((host/'inbox').glob('*.json')))==1


def test_launcher_does_not_accept_stale_generation_or_replay_requests(tmp_path,monkeypatch):
    from tools.t01_crop_launcher import Launcher
    monkeypatch.setattr(jobs,'ROOT',tmp_path);registry=tmp_path/'out/launcher'
    launcher=Launcher(registry)
    try:
        request=registry/'inbox/request-one.json'
        publish(request,encode(dict(launcher_id='old-host',job=str(tmp_path/'out/job'),job_sha256='bad')))
        launcher.tick()
        reply=registry/'replies/request-one.json';before=reply.read_bytes()
        assert b'HALTED' in before
        launcher.tick();assert reply.read_bytes()==before and not launcher.children
        with pytest.raises(ValueError,match='ALREADY_RUNNING'):Launcher(registry)
    finally:launcher.close()
    assert b'STOPPED' in (registry/'current.json').read_bytes()
