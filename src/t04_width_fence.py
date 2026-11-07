"""Separate source-bound no-bypass guard for completed T04 route decisions."""
from shapely import from_wkb,to_wkb
from shapely.geometry import Polygon
from src.stage_abi.store import canonical,digest
ACTIVE=None
PREDECESSOR_CACHE_BYTES=32*1024**2


class Rule:
    @classmethod
    def from_accepted(cls,corridors,accepted,baseline,binding):
        from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM
        forbidden=corridors.difference(accepted.buffer(POLYGON_TOLERANCE_MM,quad_segs=128))
        rule=cls(forbidden,baseline,binding)
        if not rule.remedy(accepted,baseline)['passed']:raise ValueError('T04_ACCEPTED_SCENE_MUST_NOT_FORBID_ITSELF')
        return rule

    def __init__(self,forbidden,baseline,binding,*,cache_bytes=PREDECESSOR_CACHE_BYTES):
        if type(cache_bytes)is not int or cache_bytes<0:raise ValueError('T04_PREDECESSOR_CACHE_BUDGET_INVALID')
        self.forbidden=forbidden;self.baseline=baseline;self.binding=binding
        self._skin_limit=cache_bytes;self._skin_key=None;self._skin_predecessor=None;self._skin=None;self._skin_bytes=0
        self._skin_hits=0;self._skin_misses=0
    def _predecessor_skin(self,predecessor,tolerance):
        # Shapely geometries are immutable. Identity deliberately avoids reusing
        # a coordinate-equal object's potentially different precision metadata.
        key=(id(predecessor),tolerance,128)
        if self._skin_predecessor is predecessor and self._skin_key==key:
            self._skin_hits+=1;return self._skin
        self._skin_misses+=1
        self._skin_key=None;self._skin_predecessor=None;self._skin=None;self._skin_bytes=0
        skin=predecessor.buffer(tolerance,quad_segs=128)
        if self._skin_limit:
            size=2*(len(to_wkb(predecessor))+len(to_wkb(skin)))+512
            if size<=self._skin_limit:
                self._skin_key=key;self._skin_predecessor=predecessor;self._skin=skin;self._skin_bytes=size
        return skin
    def cache_statistics(self):
        return dict(entries=int(self._skin is not None),estimated_bytes=self._skin_bytes,
                    limit_bytes=self._skin_limit,hits=self._skin_hits,misses=self._skin_misses)
    def remedy(self,logical,predecessor):
        from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM
        added=logical.difference(predecessor).difference(self.baseline)
        raw=added.intersection(self.forbidden)
        # A retained logical surface and its proved native-grid predecessor
        # may differ within the existing 2 nm export fidelity budget. That is
        # redundant representation of current material, not another widening
        # decision. Pin topology is checked independently without this skin.
        forbidden=raw.difference(self._predecessor_skin(predecessor,POLYGON_TOLERANCE_MM))if not raw.is_empty else raw
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
