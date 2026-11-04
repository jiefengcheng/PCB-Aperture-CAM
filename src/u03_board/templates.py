"""Operation-local prepared source offsets; shared constructor/verifier unchanged."""
import json,copy,math,hashlib,functools
from collections import OrderedDict
from shapely import to_wkb
from shapely.ops import unary_union
from src.native_inventory import steps,ERROR_MM
from src.source_offset_width import FAMILY


class GeometryHashes:
    """Operation-local identity memo, bounded by byte weight and entry count."""
    def __init__(self,budget=8*1024**2):
        self.budget=budget;self.entries=OrderedDict();self.weight=0;self.hits=0
    def sha(self,g):
        key=id(g);entry=self.entries.get(key)
        if entry is not None and entry[0] is g:
            self.hits+=1;self.entries.move_to_end(key);return entry[1]
        blob=to_wkb(g);value=hashlib.sha256(blob).hexdigest();weight=2*len(blob)+256
        if weight<=self.budget:
            while self.entries and (self.weight+weight>self.budget or len(self.entries)>=4096):
                _,old=self.entries.popitem(last=False);self.weight-=old[2]
            self.entries[key]=(g,value,weight);self.weight+=weight
        return value


class RouteTemplate:
    def __init__(self,sid,model,raw,meta,blobs,baseline):
        self.sid=sid;self.model=model;self.raw=raw;self.meta=meta;self.blobs=blobs
        self.source=raw[sid]
        if type(self.source) is not bytes or any(type(blobs[s]) is not bytes for s in model.chains[sid]['source_ids']):raise ValueError('IMMUTABLE_TEMPLATE_BYTES_REQUIRED')
        self.chain=copy.deepcopy(model.chains[sid]);self.ids=tuple(self.chain['source_ids'])
        self.rows={s:copy.deepcopy(meta[s]) for s in self.ids};self.bytes={s:blobs[s] for s in self.ids}
        record,parts,_,self.original,_,_=baseline
        self.record=json.dumps(record,allow_nan=False,separators=(',',':')).encode()
        self.cores={s:parts[s] for s in self.ids};self.hashes=None
    def validate(self):
        if self.raw[self.sid]!=self.source or self.model.chains[self.sid]!=self.chain or any(self.meta[s]!=self.rows[s] or self.blobs[s]!=self.bytes[s] for s in self.ids):
            raise ValueError('U03_ROUTE_TEMPLATE_OPERANDS_CHANGED')
    def sha(self,g):return self.hashes.sha(g)
    def build(self,factor):
        if type(factor) not in (float,int) or not math.isfinite(factor) or not 1<=factor<=1.5:raise ValueError('ONE_FINITE_COMMON_SCALE_REQUIRED_WITHIN_1_TO_1P5')
        record=json.loads(self.record);original=self.original
        nominal_parts={};envelope_parts={}
        for p in record['primitives']:
            sid=p['source_id'];core=self.cores[sid];width=p['original_width_mm']
            delta=width*(factor-1)/2;q=2*steps(width*.5/2)
            nominal=core if factor==1 else core.buffer(delta,quad_segs=q)
            envelope=core if factor==1 else core.buffer(delta+ERROR_MM,quad_segs=q)
            if not nominal.is_valid or not envelope.is_valid:raise ValueError('INVALID_OFFSET_COPPER')
            if not nominal.covers(core):raise ValueError('OFFSET_SOURCE_CORE_NOT_RETAINED')
            if not envelope.covers(nominal):raise ValueError('OFFSET_NOMINAL_OUTSIDE_ENVELOPE')
            nominal_parts[sid]=nominal;envelope_parts[sid]=envelope
            p.update(factor=factor,nominal_candidate_width_mm=width*factor,uniform_radial_increase_mm=delta,
                nominal_candidate_wkb_sha256=self.sha(nominal),
                verification_envelope_wkb_sha256=self.sha(envelope),
                fixed_offset_quadrant_segments=q,nominal_outward_margin_mm=0.,
                verification_outward_margin_mm=0. if factor==1 else ERROR_MM)
        nominal=unary_union(list(nominal_parts.values()));envelope=unary_union(list(envelope_parts.values()))
        if not nominal.covers(original):raise ValueError('OFFSET_COMPLETE_SOURCE_CORE_NOT_RETAINED')
        if not envelope.covers(nominal):raise ValueError('OFFSET_COMPLETE_NOMINAL_OUTSIDE_ENVELOPE')
        record.update(factor=factor,uniform_nominal_width_mm=record['verified_original_width_mm']*factor,
            geometry_family=FAMILY,geometry_role='NOMINAL_SOURCE_OFFSET_WITH_SEPARATE_CHECKING_ENVELOPE',
            added_area_mm2=nominal.difference(original).area,core_removed_mm2=original.difference(nominal).area,
            nominal_copper_wkb_sha256=self.sha(nominal),
            verification_envelope_wkb_sha256=self.sha(envelope),
            nominal_width_ceiling_factor=1.5,route_change='NONE',
            approximation='Fixed polygonal source offset; checking margin excluded from nominal copper')
        return record,nominal_parts,envelope_parts,original,nominal,envelope


def install_route_templates(model,raw,meta,blobs):
    original=model.construct
    templates={sid:RouteTemplate(sid,model,raw,meta,blobs,original(sid,1.)) for sid in sorted(model.chains)}
    hashes=GeometryHashes()
    for template in templates.values():template.hashes=hashes
    model._construct=functools.lru_cache(maxsize=2*len(model.chains)+128)(lambda sid,factor:templates[sid].build(factor))
    def construct(sid,factor):
        if sid not in templates:raise ValueError('INVALID_COMPLETE_TRACE_SCALE')
        templates[sid].validate()
        return original(sid,factor)
    model.construct=construct;model.route_templates=templates
    return model
