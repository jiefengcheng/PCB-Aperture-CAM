"""Apply independent pin and T04 decision constraints to complete fills."""
from src import pin_separation as pin,t04_width_fence as width

def remedy(logical,predecessor,*,pin_rule=None):
    pin_check=pin.remedy(logical,predecessor)if pin_rule is None else pin_rule.remedy(logical,predecessor)
    width_check=width.remedy(logical,predecessor)
    if width_check is None:return pin_check
    checks=[q for q in (pin_check,width_check)if q is not None]
    if not checks:return None
    return dict(passed=all(q['passed']for q in checks),checks=checks,
                pin_separation=pin_check,t04_width_decision=width_check)

def require_remedy(logical,predecessor,*,scope='encoded_remedy'):
    proof=pin.require_remedy(logical,predecessor,scope=scope)
    width_check=width.remedy(logical,predecessor)
    if width_check is None:return proof
    if not width_check['passed']:raise ValueError('T04_REMEDY_BYPASSES_FROZEN_WIDTH:'+scope)
    return dict(passed=True,pin=proof,width=width_check)

def encoded_remedy(logical,encoded,predecessor):
    first=pin.encoded_remedy(logical,encoded,predecessor)
    if first is not None and not first['passed']:return first
    logical_check=width.remedy(logical,predecessor)
    if logical_check is None:return first
    native_check=width.remedy(encoded,predecessor)
    return dict(passed=logical_check['passed']and native_check['passed'],pin=first,
                logical_width=logical_check,encoded_width=native_check)
