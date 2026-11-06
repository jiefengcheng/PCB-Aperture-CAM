from shapely.geometry import box
from src.gerber_u05.width_prior import check_parts


def test_retained_same_owner_width_cannot_override_a_lower_ladder_choice():
 old=box(0,-.06,1,.06);accepted=box(0,-.05,1,.05)
 proof=check_parts({'trace':old},accepted)
 assert not proof['passed']
 assert proof['parts'][0]['missing_area_mm2']>.019


def test_accepted_neighbour_or_existing_joint_material_is_valid_coverage():
 old=box(0,-.06,1,.06)
 accepted=box(0,-.06,.5,.06).union(box(.5,-.06,1,.06))
 proof=check_parts({'trace':old},accepted)
 assert proof['passed']
 assert proof['parts'][0]['missing_area_mm2']==0
