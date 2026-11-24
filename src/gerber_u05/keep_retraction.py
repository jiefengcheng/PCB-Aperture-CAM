"""Retract selected optional T04 growth to exact predecessor bodies.

Only a source-bound KEEP decision may call this. Original copper and every
unselected operand remain byte-identical. No widths are guessed or clipped.
"""
from shapely import from_wkb
from src.stage_abi.store import digest
from .limiting_math import GUARD
import math


def preserved_copper_conflict(gap_mm):
    """Use the existing functional guard; constructor reserve is not a verdict."""
    if type(gap_mm)not in(int,float)or not math.isfinite(gap_mm)or gap_mm<0:
        raise ValueError('FINITE_NONNEGATIVE_CLEARANCE_REQUIRED')
    return gap_mm+1e-12<GUARD


def retract(current, predecessor, decisions):
    if not decisions or not set(decisions) <= set(current).intersection(predecessor):
        raise ValueError('RETRACTION_REQUIRES_KNOWN_KEPT_SOURCES')
    result = dict(current); records = []
    for source, reason in sorted(decisions.items()):
        if not reason:raise ValueError('SOURCE_KEEP_REASON_REQUIRED')
        old, kept = from_wkb(current[source]), from_wkb(predecessor[source])
        if (old.is_empty or kept.is_empty or not old.is_valid or not kept.is_valid or
                not old.covers(kept)):
            raise ValueError('RETRACTION_CANNOT_ADD_OR_REMOVE_PREDECESSOR_COPPER:' + source)
        result[source] = predecessor[source]
        records.append(dict(source_id=source, reason=reason, before_sha256=digest(current[source]),
                            kept_sha256=digest(predecessor[source]),
                            removed_optional_area_mm2=old.difference(kept).area,
                            kept_predecessor_bytes_identical=True, added_copper=False))
    if any(result[s] != body for s,body in current.items() if s not in decisions):
        raise ValueError('UNSELECTED_RETRACTION_OPERAND_CHANGED')
    return result, records
