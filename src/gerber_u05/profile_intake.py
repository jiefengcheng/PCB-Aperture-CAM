"""Read-only accepted-T03 custody and a content-addressed read-through store."""
import json
from pathlib import Path
import shutil
from . import pipeline as p
from .profile_schedule import SCHEDULE
from src.t04_settings import read_snapshot, SNAPSHOT_NAME

POLICIES = ('LEGACY_REFERENCE_JOB.json', 'SOURCE_ASSEMBLY_BINDING.json',
            'PIN_SEPARATION_POLICY.json', 'T04_SETTINGS_SNAPSHOT.json', 'T04_PASS_SCHEDULE.json',
            'HOLE_ACCEPTANCE_SNAPSHOT.json', 'STORAGE_ENCODING.json')


def source_inventory():
    return {str(q.relative_to(p.ROOT)): p.digest(q.read_bytes()) for q in sorted((p.ROOT/'src').rglob('*.py'))}


class EvidenceStore:
    def __init__(self, run):
        self.artifacts = Path(run)/'runtime/artifacts'

    def get(self, ref, *, kind=None):
        kind = kind or ref['artifact_id'].split(':', 1)[0]
        sha = ref['sha256']
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha) or ref['artifact_id'] != kind+':'+sha:
            raise ValueError('T04_INPUT_ARTIFACT_REFERENCE_INVALID')
        path = self.artifacts/ref['artifact_id']
        if path.is_symlink():
            raise ValueError('T04_INPUT_ARTIFACT_LINK_FORBIDDEN')
        raw = path.read_bytes()
        if p.digest(raw) != sha:
            raise ValueError('T04_INPUT_ARTIFACT_CHANGED')
        return raw

    def get_json(self, ref, *, kind=None):
        return json.loads(self.get(ref, kind=kind))


class BoundStore(p.Store):
    def __init__(self, root, reader):
        super().__init__(root)
        self.reader = reader

    def get(self, ref, *, kind=None):
        return (super().get(ref, kind=kind) if (self.root/'artifacts'/ref['artifact_id']).exists()
                else self.reader.get(ref, kind=kind))


def read(run, expected=None):
    run = Path(run)
    reader = EvidenceStore(run)
    raw = (run/'t03.json').read_bytes()
    t03 = json.loads(raw)
    binding = p.load(run/'source.json')
    source_sha = binding['source_ref']['sha256']
    expected = expected or dict(source_sha256=source_sha, t03_sha256=p.digest(raw), scene_ref=t03['output_scene_ref'])
    if (p.digest(raw) != expected['t03_sha256'] or source_sha != expected['source_sha256']
            or t03['output_scene_ref'] != expected['scene_ref']):
        raise ValueError('T04_ACCEPTED_T03_BINDING_CHANGED')
    audits = {}
    for name in ('construct', '1', '2', 'proof'):
        data = (run/'audits/t03'/(name+'.json')).read_bytes()
        audit = json.loads(data)
        if (audit['status'], audit['candidate_sha256'], audit['source_sha256']) != ('PASS', p.digest(raw), source_sha):
            raise ValueError('T04_ACCEPTED_T03_AUDIT_CHANGED:'+name)
        audits[name] = p.digest(data)
    scene = reader.get_json(t03['output_scene_ref'], kind='scene')
    if scene['source_sha256'] != source_sha:
        raise ValueError('T04_INPUT_SCENE_SOURCE_CHANGED')
    reader.get(binding['source_ref'], kind='gerber-source')
    settings = read_snapshot(run/SNAPSHOT_NAME)
    schedule = p.load(run/'T04_PASS_SCHEDULE.json')
    if schedule['schema'] != 'pcb-t04-pass-schedule/1' or tuple(schedule['pass_increments']) != SCHEDULE:
        raise ValueError('T04_PROFILE_SCHEDULE_CHANGED')
    policies = {name:p.digest((run/name).read_bytes()) for name in POLICIES if (run/name).exists()}
    evidence = dict(source_sha256=source_sha, t03_sha256=p.digest(raw), scene_ref=t03['output_scene_ref'],
                    settings_sha256=settings.source_sha256, schedule=list(SCHEDULE),
                    policy_sha256=policies, audits_sha256=audits, completed_t04_dependency=False)
    return reader, binding, scene, settings, evidence


def prepare(out, run):
    for name in POLICIES:
        if (Path(run)/name).exists():
            shutil.copyfile(Path(run)/name, Path(out)/name)
