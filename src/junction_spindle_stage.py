"""Shared internal T05 stage mechanics; no agent ABI or source admission.

Crop adapters must qualify exact original contacts, immutable source operands
and foreign copper first. These pure functions never read/write accepted scenes.
"""
from src.clearance_policy import HARD_GAP_MM, CONSTRUCTION_GAP_MM, CONTACT_BUFFER_MM, LEGACY_CONSTRUCTION_MM, BARRIER_GAP_MM
from dataclasses import dataclass
from shapely.ops import unary_union
from src.junction_spindle_blend import spindle_blend, check_spindle
from src.stage_abi.preparation import prepared_buffer


@dataclass(frozen=True)
class SpindleStageContract:
    family: str = 'land-sized-additive-spindle/1'
    barrier_gap_mm: float = BARRIER_GAP_MM
    construction_gap_mm: float = CONSTRUCTION_GAP_MM
    hard_gap_mm: float = HARD_GAP_MM
    area_epsilon_mm2: float = 1e-12
    minimum_visible_addition_mm2: float = 1e-8
    buffer_quad_segs: int = 64
    window_land_radii: float = 2.
    radius_scales: tuple = (1., .75, .5, .25)


CONTRACT = SpindleStageContract()


def _fixed_contract(contract):
    if contract != CONTRACT:
        raise ValueError('SPINDLE_STAGE_CONTRACT_CHANGED')


def prepare_spindle_context(trace, qualified_lands, crop, *, contract=CONTRACT):
    """Build the owner/window after the caller proves each source contact."""
    _fixed_contract(contract)
    lands = list(qualified_lands)
    if not lands:
        raise ValueError('QUALIFIED_LANDS_REQUIRED')
    radius = min(min(g.bounds[2]-g.bounds[0], g.bounds[3]-g.bounds[1])/2
                 for g in lands)
    if radius <= 0:
        raise ValueError('INVALID_LAND_SIZE')
    owner = unary_union([trace] + lands)
    window = unary_union([prepared_buffer(g,contract.window_land_radii*radius,
                                   quad_segs=contract.buffer_quad_segs)
                          for g in lands]).intersection(crop)
    return owner, radius, window


def fit_spindle_blend(owner, radius, window, foreign, *, contract=CONTRACT):
    """Try the four established scales; never edit predecessor contributions.

    Foreign entries are (source_id, actual finite copper). A complete exact
    owner-coverage witness is the sole primitive-internal exemption. No label
    or electrical intent is inferred. Return None plus reasons when blocked.
    """
    _fixed_contract(contract)
    foreign = list(foreign)
    barriers = unary_union([
        prepared_buffer(g,contract.barrier_gap_mm, quad_segs=contract.buffer_quad_segs)
        for _, g in foreign if not g.difference(owner).is_empty
    ])
    attempts = []
    for scale in contract.radius_scales:
        try:
            _, addition = spindle_blend(owner, radius*scale, window)
            addition = addition.difference(barriers)
            candidate = owner.union(addition)
            check = check_spindle(owner, candidate, addition, window, foreign,
                                  gap=contract.construction_gap_mm)
        except ValueError as error:
            attempts.append(dict(scale=scale, error=str(error)))
            continue
        attempts.append(dict(scale=scale, passed=check['passed'],
                             failures=check['failures'],
                             added_area_mm2=addition.area))
        if check['passed'] and addition.area > contract.minimum_visible_addition_mm2:
            return dict(candidate=candidate, addition=addition,
                        check=check, scale=scale), attempts
    return None, attempts


def verify_spindle_batch(accepted, *, contract=CONTRACT):
    """Repeat checks including every other final addition, in saved order."""
    _fixed_contract(contract)
    checks = []
    for item in accepted:
        foreign = item['foreign'] + [
            (other['id'], other['addition']) for other in accepted
            if other['id'] != item['id']
        ]
        check = check_spindle(item['owner'],
                              item['owner'].union(item['addition']),
                              item['addition'], item['window'], foreign,
                              gap=contract.construction_gap_mm)
        if not check['passed']:
            raise ValueError('FINAL_SPINDLE_CHECK_FAILED:' + item['id'] + ':' +
                             ','.join(check['failures']))
        checks.append(dict(id=item['id'], check=check))
    return checks


def assemble_spindle_scene(predecessor, accepted, *, contract=CONTRACT):
    """Add patches in established order; preserve immutable input geometry."""
    _fixed_contract(contract)
    additions = unary_union([r['addition'] for r in accepted])
    after = predecessor.union(additions)
    if predecessor.difference(after).area > contract.area_epsilon_mm2:
        raise ValueError('PREDECESSOR_COPPER_REMOVED')
    return after
