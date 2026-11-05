import random
import pytest
from shapely.geometry import Polygon,Point,box,MultiPolygon
from shapely import get_num_coordinates
from src.gerber_u05 import gerber_source_profile as p
from src.gerber_u05.exporter import canonical_base,parse
from src.native_boundary_metric import distance
from test_gerber_source import source_circle

def l46():return b'%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.2*%\n%LPD*%\nD10*\nX1Y-2D03*\nM02*\n'
def test_l46_reimport_retains_exact_coordinates_and_source_prefix():
 raw=l46();g,parser,proof=p.parse_source(raw)
 assert len(g.objects)==1 and g.objects[0].x==.000001 and g.objects[0].y==-.000002
 assert proof['source_format']=='MM_L46_ABSOLUTE'
 base,oracle=canonical_base(raw);assert (base+'M02*\n').encode()==raw
 assert oracle['source_grid_mm']==oracle['output_grid_mm']==.000001
@pytest.mark.parametrize('mutate',[lambda b:b.replace(b'X1Y-2',b'XY-2'),lambda b:b.replace(b'MOMM',b'MOIN'),lambda b:b.replace(b'%LPD*%',b'%IPNEG*%\n%LPD*%'),lambda b:b.replace(b'M02*',b''),lambda b:b.replace(b'FSLAX46Y46',b'FSLAX46Y45')])
def test_corrupt_generated_source_cannot_get_legacy_empty_word_admission(mutate):
 with pytest.raises(Exception):p.parse_source(mutate(l46()))
def test_raw_legacy_profile_keeps_its_existing_zero_semantics():
 _,_,proof=p.parse_source(source_circle());assert proof['zero_semantics'].startswith('EXPLICIT_SEPARATE_LEGACY_T35')
@pytest.mark.parametrize('seed',range(5))
def test_large_indexed_hausdorff_agrees_with_native_all_vertex_metric(seed):
 r=random.Random(seed);a=Point(0,0).buffer(1,quad_segs=270).difference(box(-.1,-.2,.2,.3));b=Point(r.uniform(-.01,.01),r.uniform(-.01,.01)).buffer(1.002,quad_segs=271).difference(box(-.1,-.2,.2,.3))
 assert get_num_coordinates(a)+get_num_coordinates(b)>2048
 assert distance(a,b)==pytest.approx(a.hausdorff_distance(b),abs=1e-15,rel=1e-13)
def test_holes_and_minimum_grid_triangle_are_retained_by_metric():
 a=Point(0,0).buffer(1,quad_segs=270).difference(box(-.1,-.2,.2,.3));b=MultiPolygon([a,Polygon([(3,0),(3.000001,0),(3,.000001)])])
 assert distance(a,b)==pytest.approx(a.hausdorff_distance(b),abs=1e-15,rel=1e-13)

def test_history_read_fence_rejects_retained_result_before_open(tmp_path):
 import subprocess,sys
 from pathlib import Path
 from src.gerber_u05.pipeline import ROOT
 code="""from pathlib import Path
from src.gerber_u05.guard import install_read_fence
from src.gerber_u05.workspace import configure
import sys
install_read_fence(Path(sys.argv[1]))
try:(configure()/'evidence/not-this-job/top.art.gbr').read_bytes()
except PermissionError as error:
 assert 'HISTORICAL_EVIDENCE_READ_FORBIDDEN' in str(error)
else:raise AssertionError('historical read admitted')
"""
 result=subprocess.run([sys.executable,'-B','-c',code,str(tmp_path)],cwd=ROOT,capture_output=True,text=True)
 assert result.returncode==0,result.stderr

def test_job_reference_and_policy_snapshots_are_hash_bound(tmp_path,monkeypatch):
 from src.gerber_u05 import guard
 from src.gerber_u05.pipeline import save
 monkeypatch.setattr(guard,'producer_files',lambda:[])
 save(tmp_path/'source.json',{'fixture':'source'})
 save(tmp_path/'REFERENCE_BINDING.json',{'generated_sha256':'a'*64})
 guard.seal(tmp_path,'fixture');guard.verify_sources(tmp_path)
 (tmp_path/'REFERENCE_BINDING.json').write_text('{"generated_sha256":"forged"}')
 with pytest.raises(ValueError,match='GERBER_JOB_INPUT_CHANGED'):guard.verify_sources(tmp_path)
