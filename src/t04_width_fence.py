"""Separate source-bound no-bypass guard for completed T04 route decisions."""
from shapely import equals_identical,from_wkb,get_precision,prepare,to_wkb,STRtree,get_num_coordinates,get_srid,set_srid
from shapely.geometry import Polygon,MultiPolygon
from src.pcb_data_abi.geometry import POLYGON_TOLERANCE_MM
from src.stage_abi.loaded_geometry import GeometryMemo
from src.t04_predecessor_buffer import ACTIVE as LOCAL_PREDECESSOR
from src.stage_abi.store import canonical,digest
ACTIVE=None


class Rule:
    @classmethod
    def from_accepted(cls,corridors,accepted,baseline,binding):
        forbidden=corridors.difference(accepted.buffer(POLYGON_TOLERANCE_MM,quad_segs=128))
        rule=cls(forbidden,baseline,binding)
        if not rule.remedy(accepted,baseline)['passed']:raise ValueError('T04_ACCEPTED_SCENE_MUST_NOT_FORBID_ITSELF')
        return rule

    def __init__(self,forbidden,baseline,binding):
        self.forbidden=forbidden;self.baseline=baseline;self.binding=binding
        self._predecessor_buffer = None
        self._overlays = GeometryMemo('t04-width-guard')

    def _buffer_predecessor(self, predecessor):
        # The predecessor is the composed copper before this proposal. Rejecting
        # a proposal preserves it; accepting copper can replace it. The one-slot
        # cache holds that exact surface and its buffer for both fill passes.
        cached = self._predecessor_buffer
        if cached is not None:
            previous, buffered = cached
            if predecessor is previous:
                return buffered
            # A replay can reconstruct the same immutable geometry. GEOS also
            # uses the input precision model when buffering.
            if get_precision(predecessor) == get_precision(previous) and equals_identical(predecessor, previous):
                self._predecessor_buffer = predecessor, buffered
                return buffered
        buffered = predecessor.buffer(POLYGON_TOLERANCE_MM, quad_segs=128)
        self._predecessor_buffer = predecessor, buffered
        return buffered

    def proposal_delta(self, logical, predecessor):
        """Exact ordered subtraction shared by the pin and width witnesses."""
        return self._overlays.difference(logical, predecessor)

    def _local_forbidden(self, remainder, forbidden):
        """Select complete original polygons, retaining their original order.

        Only valid floating-precision polygons reach this helper. A component
        whose bounding box cannot meet the proposal cannot contribute to the
        intersection. Keep entire polygons and all their holes: no clipping,
        snapping, union, simplification or clearance tolerance is introduced.
        One immutable source index lives with this rule; changed forbidden
        copper rebuilds it. Generic size bounds avoid costly preparation for
        small inputs and cap the indexed source at one million coordinates.
        """
        cached = getattr(self, '_forbidden_index', None)
        if cached is None or cached[0] is not forbidden:
            eligible = (forbidden.geom_type == 'MultiPolygon'
                        and len(forbidden.geoms) >= 16
                        and 32768 <= get_num_coordinates(forbidden) <= 1000000)
            components = tuple(forbidden.geoms) if eligible else ()
            tree = STRtree(components) if eligible else None
            cached = self._forbidden_index = (forbidden, components, tree)
        _, components, tree = cached
        if tree is None:return forbidden
        indices = tuple(sorted(map(int, tree.query(remainder))))
        if not indices or len(indices) == len(components):return forbidden
        # Equal component selections recur across neighbouring proposals. Bind
        # this construction to the full original surface and ordered indices;
        # the existing memo checks bytes/SRID/precision and result integrity.
        return self._overlays.construct(
            'width-forbidden-components', [forbidden], indices,
            lambda: set_srid(MultiPolygon([components[i] for i in indices]),
                             get_srid(forbidden)),
        )

    def _intersect_forbidden(self, remainder):
        forbidden = self.forbidden
        # A disjoint valid floating-precision pair has zero raw overlap.
        # Preserve the exact overlay for contacts and fixed-grid operands.
        eligibility = getattr(self, '_prepared_forbidden', None)
        if eligibility is None or eligibility[0] is not forbidden:
            eligible = (get_precision(forbidden) == 0 and forbidden.is_valid
                        and forbidden.geom_type in ('Polygon', 'MultiPolygon'))
            if eligible:
                prepare(forbidden)
            self._prepared_forbidden = (forbidden, eligible)
        else:
            eligible = eligibility[1]
        if (eligible and get_precision(remainder) == 0 and remainder.is_valid
                and remainder.geom_type in ('Polygon', 'MultiPolygon')
                and not forbidden.intersects(remainder)):
            return Polygon()
        if (eligible and get_precision(remainder) == 0 and remainder.is_valid
                and remainder.geom_type in ('Polygon', 'MultiPolygon')):
            forbidden = self._local_forbidden(remainder, forbidden)
        return remainder.intersection(forbidden)

    def remedy(self,logical,predecessor):
        # Preserve GEOS operand order and raw area. The exact overlay key
        # includes the proposal, predecessor, baseline and forbidden surface.
        # Each call still evaluates the proof from the resulting geometry.
        raw = self._overlays.construct(
            'width-guard-overlap', [logical, predecessor, self.baseline, self.forbidden], (),
            lambda: self._intersect_forbidden(self.proposal_delta(logical, predecessor).difference(self.baseline)),
        )
        # A retained logical surface and its proved native-grid predecessor
        # may differ within the existing 2 nm export fidelity budget. That is
        # redundant representation of current material, not another widening
        # decision. Pin topology is checked independently without this skin.
        forbidden = raw
        if not raw.is_empty:
            local = LOCAL_PREDECESSOR.get()
            buffered = None if local is None else local.reusable(
                self._predecessor_buffer, predecessor, logical, POLYGON_TOLERANCE_MM)
            if buffered is None:
                buffered = self._buffer_predecessor(predecessor)
            # A local hit leaves the cached full buffer bound to its actual
            # parent. Its new use is limited to this exact proposal window.
            forbidden = self._overlays.difference(raw, buffered)
        return self._proof(forbidden.is_empty or forbidden.area==0, forbidden.area, raw.area)

    def exact_predecessor(self, logical, predecessor):
        """Return the empty-difference proof for identical valid copper."""
        if (get_precision(logical) == get_precision(predecessor)
                and equals_identical(logical, predecessor) and logical.is_valid):
            return self._proof(True, 0.0, 0.0)
        return None

    def _proof(self, passed, forbidden_area, raw_area):
        return dict(passed=passed,
                    reason='T04_FROZEN_WIDENING_DECISION',
                    forbidden_added_area_mm2=forbidden_area,raw_difference_area_mm2=raw_area,
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
