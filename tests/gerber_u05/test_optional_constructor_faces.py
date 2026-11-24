"""Optional constructors must not emit detached sub-resolution faces."""
from shapely.geometry import Point, box
from shapely.ops import unary_union


def test_arc_rejects_only_unattached_optional_micro_disk():
    from src.gerber_u05.arc_group_plan import retain_attached_skin
    core = box(0, 0, 1, .1)
    grown = box(0, 0, 1, .12)
    disk = Point(.5, -.0000006).buffer(.00000005, quad_segs=128)
    body, proof = retain_attached_skin(unary_union([grown, disk]), core)
    assert body.equals(grown) and body.covers(core)
    assert proof['rejected_faces'] == 1 and proof['passed']
    assert proof['rejected'][0]['wkb_hex']


def test_arc_keeps_even_sub_resolution_original_source_faces():
    from src.gerber_u05.arc_group_plan import retain_attached_skin
    disk = Point(.5, -.0000006).buffer(.00000005, quad_segs=128)
    core = unary_union([box(0, 0, 1, .1), disk])
    grown = unary_union([box(0, 0, 1, .12), disk])
    body, proof = retain_attached_skin(grown, core)
    assert body.wkb == grown.wkb and body.covers(disk)
    assert proof['rejected_faces'] == 0


def test_arc_defers_a_substantive_unattached_skin_instead_of_hiding_it():
    from src.gerber_u05.arc_group_plan import retain_attached_skin
    core = box(0, 0, 1, .1)
    body, proof = retain_attached_skin(unary_union([core, box(0, .2, .1, .3)]), core)
    assert body is None and not proof['passed']
    assert proof['reason'] == 'UNATTACHED_ARC_SKIN_EXCEEDS_NATIVE_ERROR_BOUNDS'


def test_arc_retains_indirect_point_contact_to_its_source():
    from src.gerber_u05.arc_group_plan import retain_attached_skin
    core = box(0, 0, 1, .1)
    body = unary_union([core, box(1, .1, 1.1, .2), box(1.1, .2, 1.2, .3)])
    after, proof = retain_attached_skin(body, core)
    assert after.wkb == body.wkb and proof['rejected_faces'] == 0


def test_optional_cut_retains_parent_when_it_would_leave_a_micro_face():
    from src.gerber_u05.tangent_finish import subtract_optional_patch
    parent = unary_union([box(0, 0, .01, .01),
                          box(.009, .004, .0110001, .0040001)])
    cut = box(.01, .003, .011, .005)
    after, proof = subtract_optional_patch(parent, cut)
    assert after.wkb == parent.wkb
    assert proof['retained_original_parts'] == 1
    assert after.difference(parent).is_empty


def test_optional_cut_keeps_preexisting_tiny_positive_contribution():
    from src.gerber_u05.tangent_finish import subtract_optional_patch
    tiny = box(.02, 0, .0200001, .0000001)
    parent = unary_union([box(0, 0, .01, .01), tiny])
    after, proof = subtract_optional_patch(parent, box(0, 0, .005, .01))
    assert after.covers(tiny) and after.difference(parent).is_empty
    assert after.area < parent.area


def test_ordinary_optional_cut_is_byte_identical_to_existing_overlay():
    from src.gerber_u05.tangent_finish import subtract_optional_patch
    parent = box(0, 0, .01, .01)
    cut = box(0, 0, .005, .01)
    after, proof = subtract_optional_patch(parent, cut)
    assert after.wkb == parent.difference(cut).wkb
    assert proof['retained_original_parts'] == 0


def test_invalid_optional_tangent_difference_retains_its_exact_valid_operand(monkeypatch):
    from shapely.geometry import box,Polygon
    from src.gerber_u05 import tangent_finish as module
    source=box(0.,0.,1.,1.);before=source.wkb
    invalid=Polygon([(0.,0.),(1.,1.),(1.,0.),(0.,1.),(0.,0.)])
    assert not invalid.is_valid
    monkeypatch.setattr(module,'polygonal',lambda g:invalid)
    result,proof=module.subtract_optional_patch(source,box(0.,0.,.1,.1))
    assert result.wkb==before and proof['retained_original_parts']==1
    assert proof['retained'][0]['reason']=='KEEP_ORIGINAL_OPTIONAL_PART; INVALID_TANGENT_DIFFERENCE'
    assert proof['retained'][0]['rejected_candidate_wkb_hex']==invalid.wkb.hex()


def test_a_long_thin_new_tangent_face_defers_its_parent_cut():
    from shapely.geometry import box
    from src.gerber_u05.tangent_finish import subtract_optional_patch
    original=box(0.,0.,.01,.01)
    mask=box(-.01,.004,.02,.01-1e-12)
    raw=original.difference(mask)
    assert raw.geom_type=='MultiPolygon'and min(g.area for g in raw.geoms)<1e-12
    result,proof=subtract_optional_patch(original,mask)
    assert result.wkb==original.wkb and proof['retained_original_parts']==1
