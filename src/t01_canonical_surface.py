"""Uniform source-wide construction guard; the retained verifiers stay unchanged.

The legacy interaction kernel proposes contours. Only optional copper is limited
here by the full original-copper visibility and symmetric original-contact ports.
The extra 0.00002 mm is construction reserve, never a verification tolerance.
"""
import hashlib
from shapely import STRtree, to_wkb
from shapely.ops import unary_union
from src.crop_square_neighbor_experiment import retain_attached
from src.trace_width_clearance import TraceWidthContract


class SurfaceGuard:
    def __init__(self, rows, shapes, sites):
        self.contract=TraceWidthContract();self.reserve=.00002
        aliases={a:s['source_id'] for s in sites for a in s['aliases']}
        self.original={};self.widths={};self.index={};self.hidden={};self.ports={}
        for i,(r,g) in enumerate(zip(rows,shapes)):
            sid=aliases.get(r['id'],r['id'])
            if sid in self.original:continue
            self.original[sid]=g;self.index[sid]=i;self.widths[sid]=r.get('trace_width_mm') or 0.
        self.ids=sorted(self.original);self.tree=STRtree([self.original[s] for s in self.ids])
        self.predecessor=unary_union([self.original[s] for s in self.ids])
        self.aliases=aliases;self.rows=rows;self.records=[];self.surfaces={}

    def hidden_by_original(self,sid,g):
        key=(sid,tuple(g.bounds))
        if key not in self.hidden:
            self.hidden[key]=unary_union([self.original[self.ids[int(i)]] for i in self.tree.query(g.envelope) if self.ids[int(i)]!=sid])
        return self.hidden[key]

    def port(self,sid,other):
        key=tuple(sorted((sid,other)))
        if key not in self.ports:
            overlap=self.original[sid].intersection(self.original[other])
            self.ports[key]=None if overlap.is_empty else overlap.buffer(max(self.widths[sid],self.widths[other])+self.contract.original_port_buffer_gap_mm,quad_segs=self.contract.port_quad_segs)
        return self.ports[key]

    def limit(self,site,proposal,scene,*,priority=False,record=True,overrides=None):
        sid=site['source_id'];core=site['core']
        if to_wkb(proposal)==to_wkb(core):return core
        radius=self.contract.construction_gap_mm+self.reserve
        neighbors={self.aliases.get(self.rows[int(i)]['id'],self.rows[int(i)]['id']) for i in scene.tree.query(proposal.buffer(radius).envelope)}-{sid}
        constraints=[];checks=[]
        for other in sorted(neighbors):
            g=(overrides or {}).get(other,scene.shapes[self.index[other]])
            key=(other,hashlib.sha256(to_wkb(g)).digest())
            if key not in self.surfaces:self.surfaces[key]=(g.difference(self.hidden_by_original(other,g)),g.difference(self.predecessor))
            exposed,earlier=self.surfaces[key];port=self.port(sid,other)
            forward=exposed.buffer(radius,quad_segs=128)
            if port is not None:forward=forward.difference(port)
            # Earlier additions must also remain clear of this new surface.
            if port is not None:earlier=earlier.difference(port)
            constraints.extend([forward,earlier.buffer(radius,quad_segs=128)])
            checks.append((other,exposed,port))
        forbidden=unary_union(constraints)
        optional=proposal.difference(core).difference(forbidden)
        candidate,_=retain_attached(optional,core,scene.settings.kernel())
        # Overlay arithmetic can make covers() false with zero difference area.
        # A sub-nanometre interior reserve makes exact containment constructive.
        candidate=unary_union([candidate,core.buffer(1e-10,quad_segs=128)])
        held=[]
        if priority and candidate.symmetric_difference(proposal).area>scene.settings.area_epsilon:
            held.append('COMPLETE_ROUND_REQUIRED')
        if not candidate.covers(core):held.append('EXACT_CORE_CONTAINMENT')
        added=candidate.difference(self.predecessor)
        for other,exposed,port in checks:
            checked=added if port is None else added.difference(port)
            if not checked.is_empty and not exposed.is_empty and checked.distance(exposed)+self.contract.comparison_epsilon_mm<self.contract.construction_gap_mm:
                held.append('FULL_SURFACE_CONSTRUCTION_GUARD');break
        if held:candidate=core
        if candidate.difference(core).area<=scene.settings.area_epsilon:candidate=core
        if record:self.records.append(dict(source_id=sid,proposal_sha256=hashlib.sha256(to_wkb(proposal)).hexdigest(),candidate_sha256=hashlib.sha256(to_wkb(candidate)).hexdigest(),removed_optional_area_mm2=proposal.difference(candidate).area,held_reasons=held,construction_reserve_mm=self.reserve))
        return candidate
