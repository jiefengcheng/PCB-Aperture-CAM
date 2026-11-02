"""Location ownership, raster uncertainty, coverage and authority boundaries."""
import copy,json
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from shapely.geometry import Point,box
from shapely.ops import unary_union
from src.pcb_data_abi import roi
from src.stage_abi.store import canonical,digest
from src.stage_abi.contracts import StageABIError
from src.t01_crop.policy import english,compile_policy,validate_policy,validate_binding
from src.t01_crop.adapter import groups_for

ROOT=Path(__file__).resolve().parents[1]

def sample():
    g=unary_union([Point(x,y).buffer(r,quad_segs=64) for x,y,r in ((.4,.5,.13),(1.1,.4,.18),(1.6,1.0,.15),(.7,1.5,.16))])
    b=[0,0,2,2];a=roi.contains_xy(g,(np.arange(400)[None,:]+.5)/200,(np.arange(400)[:,None]+.5)/200)
    return g,b,a

def row(a,g,b):
    m=roi.pixel_metrics(a,g,b);return dict(iou=m['iou'],boundary_metrics=m,bounds_mm=b)

def test_data_abi_owns_location_without_t01_dependency():
    text=(ROOT/'src/pcb_data_abi/roi.py').read_text()
    assert 'src.t01' not in text
    contract=json.loads((ROOT/'contracts/operator/t01_crop.json').read_bytes())
    assert contract['operations'][:3]==list(roi.OPERATIONS)

def test_edge_uncertainty_accepts_only_bounded_edges():
    g,b,a=sample();assert roi.assess([row(a,g,b)])
    shifted=np.roll(a,1,axis=1);assert roi.assess([row(shifted,g,b)])
    with pytest.raises(ValueError,match='NOT_LOCATED|BOUNDARY_MODEL_EXCEEDED'):roi.assess([row(np.roll(a,12,axis=1),g,b)])

def test_missing_copper_interior_is_not_raster_edge_uncertainty():
    g,b,a=sample();a[90:110,70:90]=False
    with pytest.raises(ValueError,match='BOUNDARY_MODEL_EXCEEDED'):roi.assess([row(a,g,b)])

def test_ambiguous_locations_rejected_even_with_perfect_pixels():
    g,b,a=sample();r=row(a,g,b)
    with pytest.raises(ValueError,match='AMBIGUOUS'):roi.assess([r,dict(r,bounds_mm=[4,4,6,6])])

@pytest.mark.parametrize('count',[0,5])
def test_insufficient_landmarks_do_not_authorize_t01(count):
    g,b,a=sample()
    with pytest.raises(ValueError,match='LANDMARKS_NOT_ESTABLISHED'):roi.assess([row(a,g,b)],[dict(matched=True) for _ in range(count)])

def test_unsupported_color_image_rejects():
    with pytest.raises(ValueError,match='IMAGE_PROFILE_UNSUPPORTED'):roi.image_panels(Image.new('RGB',(200,200),'blue'))

def test_panel_detection_uses_pixels_not_registered_c01_bounds():
    im=Image.new('RGB',(300,500),'white')
    a=np.asarray(im).copy();a[20:180,30:270]=[255,0,0];a[300:460,40:280]=[255,0,0]
    assert [p['pixel_bounds'] for p in roi.image_panels(Image.fromarray(a))]==[[30,20,270,180],[40,300,280,460]]

def test_source_binding_is_byte_bound_and_project_local(tmp_path):
    p=tmp_path/'source';p.write_bytes(b'actual')
    with pytest.raises(ValueError,match='INPUT_CHANGED'):roi.bound(dict(path=str(p),sha256='0'*64))
    with pytest.raises(ValueError,match='PROJECT_PATH_REQUIRED'):roi.local(ROOT/'..'/'another')
    q=tmp_path/'link';q.symlink_to(p)
    with pytest.raises(ValueError,match='PROJECT_PATH_REQUIRED'):roi.local(q)

def test_english_one_policy_has_no_crop_name_and_no_clearance_waiver():
    ref=dict(artifact_id='t01-binding-'+'a'*64,sha256='a'*64)
    p=compile_policy(english(),ref);validate_policy(p)
    assert len(p['clause_trace'])==16 and p['settings']['hard_gap']==.020
    with pytest.raises(StageABIError):compile_policy(english().replace('0.020 mm','0.001 mm'),ref)
    p['settings']['hard_gap']=.001
    with pytest.raises(StageABIError):validate_policy(p)

def test_reviewed_identity_pair_outside_roi_and_boundary_stay_singletons():
    s=[dict(source_id='a',center=[0,0],radius=.1),dict(source_id='b',center=[.22,0],radius=.1),dict(source_id='c',center=[1,0],radius=.1)]
    groups=groups_for(s,[['a','b']],{'a','b'},.020)
    assert sorted(x for g in groups for x in g['site_ids'])==['a','b','c']
    assert all(len(g['site_ids'])==1 for g in groups)

def test_native_route_exposes_no_later_stages():
    from src.pcb_data_abi.crop_custody import STEPS
    assert not any(op.startswith(('t02','t03','t04','t05')) for op in STEPS)
    assert len(STEPS)==21

def test_generic_render_preserves_numerical_display_limits():
    a=json.loads((ROOT/'contracts/render/c01.json').read_bytes());b=json.loads((ROOT/'contracts/render/crop.json').read_bytes())
    for k in ('raster_boundary_error_mm','dependencies','cli_sha256','negative_controls'):assert a[k]==b[k]

@pytest.mark.parametrize('k,mirror',[(k,m) for k in range(4) for m in (False,True)])
def test_whole_board_constellation_recovers_rotation_and_reflection(k,mirror):
    pts=[(.32,.28),(.76,.31),(1.34,.27),(.44,.72),(1.2,.81),(.28,1.18),(.84,1.12),(1.48,1.17)]
    features=[dict(source_id=str(i),aliases=[str(i)],center=[x+10,y+20],radius=.065) for i,(x,y) in enumerate(pts)]
    geometry=unary_union([Point(*q['center']).buffer(q['radius'],quad_segs=64) for q in features])
    xs=10+(np.arange(540)+.5)/300;ys=20+(np.arange(450)+.5)/300
    mask=roi.contains_xy(geometry,xs[None,:],ys[:,None]);attached=roi.orient(mask,k,mirror)
    poses=roi.seed_poses(attached,features)
    assert poses and poses[0]['seed_landmarks']==8
    b=poses[0]['bounds_mm'];assert abs((b[0]+b[2])/2-10.9)<.02 and abs((b[1]+b[3])/2-20.75)<.02
