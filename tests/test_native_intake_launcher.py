"""Launcher custody and concurrency around native-only intake workers."""
from pathlib import Path
import json
import pytest
from tools import t01_crop_jobs as jobs
from tools.t01_route_client import encode,publish
from tools.t01_crop_launcher import Launcher


def test_intake_worker_is_native_async_retained_and_not_replayed(tmp_path,monkeypatch):
    import tools.t01_crop_launcher as module
    monkeypatch.setattr(jobs,'ROOT',tmp_path);monkeypatch.setattr(jobs,'MANAGED',tmp_path/'out/managed');registry=tmp_path/'out/launcher'
    class Process:
        pid=123
        def poll(self):return 0
    calls=[]
    def spawn(argv,**kwargs):calls.append(argv);return Process()
    monkeypatch.setattr(module.subprocess,'Popen',spawn)
    launcher=Launcher(registry)
    try:
        request=dict(action='directory_intake',launcher_id=launcher.id,input_directory='/explicit/raw inputs',companion_policy='PRESERVE_EXCLUDED')
        path=registry/'inbox/unique.json';publish(path,encode(request));launcher.tick()
        assert len(calls)==1 and 't01_directory_intake_worker.py'in calls[0][2]
        reply=json.loads((registry/'replies/unique.json').read_bytes());assert reply['error']=='NATIVE_INTAKE_WORKER_EXITED_WITHOUT_RESULT'
        assert(registry/'calls/unique/request.json').exists()and(registry/'calls/unique/launch.json').exists()
        assert json.loads((registry/'current.json').read_bytes())['directory_intake']=='native-directory/1'
        launcher.tick();assert len(calls)==1
    finally:launcher.close()


def test_cancelled_native_intake_stops_before_source_scan(tmp_path,monkeypatch):
    from tools import t01_directory_intake_worker as module
    monkeypatch.setattr(jobs,'ROOT',tmp_path);registry=tmp_path/'out/launcher';call=registry/'calls/cancelled';call.mkdir(parents=True);(registry/'replies').mkdir()
    publish(call/'request.json',encode(dict(action='directory_intake',launcher_id='native',input_directory='/not-read',companion_policy='PRESERVE_EXCLUDED')));publish(call/'cancel_requested.json',b'{}')
    monkeypatch.setattr(module,'collect_raw',lambda *a:pytest.fail('Cancelled intake must not read the source'))
    assert module.process(call,registry,tmp_path/'out/managed')==2
    reply=json.loads((call/'response.json').read_bytes());assert reply['error'].startswith('NATIVE_INTAKE_CANCELLED')and not(tmp_path/'out/managed/jobs').exists()
