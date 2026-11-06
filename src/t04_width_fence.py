"""Separate source-bound no-bypass guard for completed T04 route decisions."""
from shapely import from_wkb,to_wkb
from shapely.geometry import Polygon
from src.stage_abi.store import canonical,digest
ACTIVE=None


class Rule:
    @classmethod
    def from_accepted(cls,corridors,accepted,baseline,binding):
        from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM
        forbidden=corridors.difference(accepted.buffer(POLYGON_TOLERANCE_MM,quad_segs=128))
        rule=cls(forbidden,baseline,binding)
        if not rule.remedy(accepted,baseline)['passed']:raise ValueError('T04_ACCEPTED_SCENE_MUST_NOT_FORBID_ITSELF')
        return rule

    def __init__(self,forbidden,baseline,binding):
        self.forbidden=forbidden;self.baseline=baseline;self.binding=binding
    def remedy(self,logical,predecessor):
        from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM
        added=logical.difference(predecessor).difference(self.baseline)
        raw=added.intersection(self.forbidden)
        # A retained logical surface and its proved native-grid predecessor
        # may differ within the existing 2 nm export fidelity budget. That is
        # redundant representation of current material, not another widening
        # decision. Pin topology is checked independently without this skin.
        forbidden=raw.difference(predecessor.buffer(POLYGON_TOLERANCE_MM,quad_segs=128))if not raw.is_empty else raw
        return dict(passed=forbidden.is_empty or forbidden.area==0,
                    reason='T04_FROZEN_WIDENING_DECISION',
                    forbidden_added_area_mm2=forbidden.area,raw_difference_area_mm2=raw.area,
                    current_native_fidelity_mm=POLYGON_TOLERANCE_MM,binding=self.binding,
                    unit='COMPLETE_LOGICAL_PROPOSAL; no clipping or splitting')
    def state(self,store):
        return dict(schema='frozen-t04-route-widening-decisions/1',binding=self.binding,
                    forbidden_ref=store.put('geometry',to_wkb(self.forbidden)),
                    baseline_ref=store.put('geometry',to_wkb(self.baseline)))


def remedy(logical,predecessor):
    return None if ACTIVE is None else ACTIVE.remedy(logical,predecessor)


def require(material,*,scope):
    if ACTIVE is None:return None
    proof=ACTIVE.remedy(material,ACTIVE.baseline)
    if not proof['passed']:raise ValueError('T04_REMEDY_BYPASSES_FROZEN_WIDTH:'+scope)
    return proof


def restore(store,scene):
    global ACTIVE
    ACTIVE=None
    if scene is None:return
    for entry in reversed(scene['lineage']):
        if 't04_width_fence'not in entry:continue
        value=entry['t04_width_fence']
        if value['schema']!='frozen-t04-route-widening-decisions/1':raise ValueError('T04_WIDTH_FENCE_SCHEMA_CHANGED')
        ACTIVE=Rule(from_wkb(store.get(value['forbidden_ref'],kind='geometry')),
                    from_wkb(store.get(value['baseline_ref'],kind='geometry')),value['binding'])
        return
