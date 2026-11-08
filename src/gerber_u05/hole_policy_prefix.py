"""Exact owner-authorized strict-to-relaxed transition before fresh connected T01 or T04."""
import hashlib,json
from pathlib import Path
from src import hole_acceptance as holes
ROOT=Path(__file__).resolve().parents[2]
PAIRS={'contracts/component_remedy/settings.json': ('93f72a95f01677380d34d916efab3d755fa8ad9187df6eb16d5dc354c43c4e23',
                                              'd296f436a16f93469e4ac5ed0a179eb1fed0fa85f03ffa7ab16c7b3060bab140'),
 'src/component_absorption.py': ('ad4ec3c20158c3d83c2b707697e7568653c614f370f0877219480e1e89dbfea9',
                                 'f1e841cb83ab07ce19da3da91ee22660b5153550e9493ab048aa17e3f633174b'),
 'src/component_hole_lineage.py': ('e4820afc452f81c958bd8baa197510eb68a1ef25481e1434933bf00dafd0847c',
                                   '7372d3793e9a1f260f3a5d3b906ee8d0eae0b0f303c0b5bcfc070208d669b956'),
 'src/component_voids.py': ('9eb6134838be22414bcee7de54c8b78bcaf51ed6504102e6ea4fc19e99c24725',
                            'cdbed5b8bd497878ec277b5c0d251f98dd7091018f6113d093664ab6cf20aa8a'),
 'src/gerber_u05/component_policy.py': ('68600f8aaabc4783800b081d8b1b7b11d66ff1e7057a37c12fae2104460c2ec3',
                                        '6fa24f46ee75b98b140e46d6cd94ab1aa94303990de976ca879b6831180b917e'),
 'src/gerber_u05/component_rectangles.py': ('7bcaeb074bbe3c91fef66cedf404e06d4f9fc926ed982cfe7ede73843579170f',
                                            '043acbad6515e297452d712df7c0db7647a78807ae168926e6ace66d6c6dc55f'),
 'src/gerber_u05/native_component_checks_final.py': ('b985a0b53f1f177e739f2a36462529d9815d0963278ab774214c41dbadce1b83',
                                                     '8cfc48ce3aa0574c972aa46b13ac4112c08a6a1dd09ed1799cf9476bee844a0c'),
 'src/gerber_u05/reference_recipe.py': ('364b91ab3926a57fb05580c45ef8fdab4d1411f65969ef7b5e7cbf4c478067db',
                                        '33f53f69b3028737cb2368bf7e6d72891d513e619d07c079c8e550280b37a8bc'),
 'src/growth_void_remedy_v09.py': ('a8d330a2172f7823780caa83b3fd6e8399a9a092270c52e313da05e9dbf11ffc',
                                   'e029c41b6905d429c4454f7d6a448795aa871e4b054910e9775b7a20021ed610'),
 'src/t04_topology.py': ('82f73006c10d9e2f31e140b3a6b889d56f9666f704c7b4aa7714984a3489a10c',
                         'af86ddebd42021d859b8f63227bcd926dfc9b2a67af7231b04832bfa168da506'),
 'src/t05_trapped_voids.py': ('f4f2bcc76dea92cb40ad806c6d343fcee17cf47ea3eb4ff331c6228c57380083',
                              '85138265ade0d36dacdddfcf3f7039293b40cea9d16a534dabb4675aacb023ec')}
EXTRA={'contracts/hole_acceptance/settings.json': 'bcff0e3e0db43ecfde439e9bdc03ec40ff482afe20ab66471da6038eee35aedd',
 'src/hole_acceptance.py': '4c91e4fd9f4562a8395c50a8a57c3b186b5e87da6bf083015dc3ba02761638bb'}


def enabled(root=ROOT):
 root=Path(root)
 return all(hashlib.sha256((root/n).read_bytes()).hexdigest()==h for n,h in EXTRA.items()) and holes.decode((root/'contracts/hole_acceptance/settings.json').read_bytes())['ordinary_holes']==holes.RELAXED


def allowed_delta(relative,before,after,stages,root=ROOT):
 return tuple(stages)in((),('t01','t03')) and PAIRS.get(relative)==(before,after) and enabled(root)


def transition_remedy_snapshot(run,*,retained=('t01','t03')):
 """Only this policy label changes; all numerical and growth settings must match."""
 from . import pipeline as p
 if tuple(retained)not in((),('t01','t03')):raise ValueError('HOLE_POLICY_TRANSITION_RETAINED_SCOPE_CHANGED')
 if not enabled():raise ValueError('QUALIFIED_HOLE_POLICY_TRANSITION_REQUIRED')
 path=Path(run)/'REMEDY_POLICY_SNAPSHOT.json';value=p.load(path)
 raw=(ROOT/'contracts/component_remedy/settings.json').read_bytes();new=json.loads(raw)
 old=dict(value['settings']);old['source_voids']=new['source_voids']
 if old!=new:raise ValueError('HOLE_POLICY_TRANSITION_CHANGED_NONHOLE_SETTINGS')
 if hashlib.sha256(value['registry_json'].encode()).hexdigest()!=value['registry_sha256']or json.loads(value['registry_json'])!=value['settings']:raise ValueError('HOLE_POLICY_OLD_REMEDY_SNAPSHOT_CHANGED')
 value.update(settings=new,registry_json=raw.decode(),registry_sha256=hashlib.sha256(raw).hexdigest())
 archive=Path(run)/'prefix_evidence/PRETRANSITION_REMEDY_POLICY_SNAPSHOT.json'
 archive.parent.mkdir(parents=True,exist_ok=True)
 if archive.exists():raise ValueError('HOLE_POLICY_TRANSITION_ARCHIVE_EXISTS')
 path.rename(archive)
 p.save(path,value)
 return dict(schema='owner-hole-policy-prefix-transition/1',ordinary_holes=holes.RELAXED,retained_stages=list(retained),fresh_from='t01'if not retained else't04',source_ancestry_requirement='NOT_REQUIRED',nonhole_settings='IDENTICAL',retained_geometry='UNCHANGED; qualified under stricter earlier policy',original_failures='PRESERVED_UNCHANGED')
