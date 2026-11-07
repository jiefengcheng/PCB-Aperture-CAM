"""Apply independent pin and T04 decision constraints to complete fills."""
from src import pin_separation as pin,t04_width_fence as width,t02_shared_gaps as gaps

def remedy(logical,predecessor,*,pin_rule=None):
    pin_check=pin.remedy(logical,predecessor)if pin_rule is None else pin_rule.remedy(logical,predecessor)
    width_check=width.remedy(logical,predecessor)
    gap_check=gaps.remedy(logical,predecessor)
    if width_check is None and gap_check is None:return pin_check
    checks=[q for q in (pin_check,width_check,gap_check)if q is not None]
    if not checks:return None
    return dict(passed=all(q['passed']for q in checks),checks=checks,
                pin_separation=pin_check,t04_width_decision=width_check,shared_neighbor_gaps=gap_check)

def require_remedy(logical,predecessor,*,scope='encoded_remedy'):
    proof=pin.require_remedy(logical,predecessor,scope=scope)
    width_check=width.remedy(logical,predecessor)
    gap_check=gaps.remedy(logical,predecessor)
    if gap_check is not None and not gap_check['passed']:raise ValueError('T02_SHARED_GAP_REMEDY_INTRUSION:'+scope)
    if width_check is None:return proof if gap_check is None else dict(passed=True,pin=proof,shared_neighbor_gaps=gap_check)
    if not width_check['passed']:raise ValueError('T04_REMEDY_BYPASSES_FROZEN_WIDTH:'+scope)
    return dict(passed=True,pin=proof,width=width_check,shared_neighbor_gaps=gap_check)

def encoded_remedy(logical,encoded,predecessor):
    first=pin.encoded_remedy(logical,encoded,predecessor)
    if first is not None and not first['passed']:return first
    logical_check=width.remedy(logical,predecessor)
    native_check=width.remedy(encoded,predecessor)
    logical_gap=gaps.remedy(logical,predecessor);native_gap=gaps.remedy(encoded,predecessor)
    if logical_check is None and logical_gap is None:return first
    return dict(passed=all(q['passed']for q in (first,logical_check,native_check,logical_gap,native_gap)if q is not None),pin=first,
                logical_width=logical_check,encoded_width=native_check,logical_gap=logical_gap,encoded_gap=native_gap)
