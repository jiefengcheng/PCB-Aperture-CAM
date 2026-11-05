"""Shared clearance settings, captured immutably at a job boundary.

Changing the registry affects the next capture. Existing job snapshots never
reread defaults. No environment override or global OS setting is involved.
"""
from dataclasses import dataclass,field
from decimal import Decimal
import hashlib,json,math
from pathlib import Path
DEFAULT_REGISTRY=Path(__file__).resolve().parents[1]/'contracts/clearance/settings.json'


def _number(value,name,*,positive=False):
    if type(value)not in(int,float)or not math.isfinite(value)or value<0 or(positive and value==0):
        raise ValueError('INVALID_CLEARANCE_SETTING:'+name)
    return float(value)


def _pairs(rows):
    out={}
    for k,v in rows:
        if k in out:raise ValueError('DUPLICATE_CLEARANCE_SETTING:'+k)
        out[k]=v
    return out


def _decode(raw):
    return json.loads(raw,object_pairs_hook=_pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('NONFINITE_CLEARANCE_SETTING:'+x)))


def _json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


@dataclass(frozen=True)
class ClearanceSettings:
    nominal_mm:float
    relative_tolerance:float
    trace_land_margin_mm:float
    source_contact_margin_mm:float
    t01_margin_mm:float
    spindle_barrier_margin_mm:float
    source_sha256:str
    _raw:bytes=field(repr=False)

    @property
    def absolute_tolerance_mm(self):return float(Decimal(str(self.nominal_mm))*Decimal(str(self.relative_tolerance)))
    @property
    def effective_floor_mm(self):return float(Decimal(str(self.nominal_mm))-Decimal(str(self.absolute_tolerance_mm)))
    @property
    def construction_gap_mm(self):return float(Decimal(str(self.nominal_mm))+Decimal(str(self.trace_land_margin_mm)))
    @property
    def contact_buffer_mm(self):return float(Decimal(str(self.nominal_mm))+Decimal(str(self.source_contact_margin_mm)))
    @property
    def t01_construction_gap_mm(self):return float(Decimal(str(self.nominal_mm))+Decimal(str(self.t01_margin_mm)))
    @property
    def barrier_gap_mm(self):return float(Decimal(str(self.nominal_mm))+Decimal(str(self.spindle_barrier_margin_mm)))

    def compare_gap(self,measured_mm):
        gap=_number(measured_mm,'measured_gap_mm')
        return dict(status='PASS_NOMINAL'if gap>=self.nominal_mm else 'PASS_OWNER_TOLERANCE'if gap>=self.effective_floor_mm else 'FAIL_CLEARANCE',passed=gap>=self.effective_floor_mm,nominal_passed=gap>=self.nominal_mm,
            tolerance_consumed=gap<self.nominal_mm and gap>=self.effective_floor_mm,
            measured_mm=gap,nominal_mm=self.nominal_mm,relative_tolerance=self.relative_tolerance,
            absolute_tolerance_mm=self.absolute_tolerance_mm,effective_floor_mm=self.effective_floor_mm,
            policy_sha256=self.source_sha256)

    def resolved(self):
        return dict(nominal_mm=self.nominal_mm,relative_tolerance=self.relative_tolerance,
            absolute_tolerance_mm=self.absolute_tolerance_mm,effective_floor_mm=self.effective_floor_mm,
            construction_gap_mm=self.construction_gap_mm,contact_buffer_mm=self.contact_buffer_mm,
            t01_construction_gap_mm=self.t01_construction_gap_mm,barrier_gap_mm=self.barrier_gap_mm)

    def write_snapshot(self,path):
        payload=dict(schema='pcb-clearance-job-snapshot/1',source_sha256=self.source_sha256,
            source_json=self._raw.decode('utf-8'),resolved=self.resolved())
        with Path(path).open('xb')as stream:stream.write(_json(payload))
        return hashlib.sha256(_json(payload)).hexdigest()


def from_bytes(raw):
    d=_decode(raw)
    if set(d)!={'schema','revision','nominal_clearance_mm','relative_clearance_tolerance','construction_margins_mm','scope'}or d['schema']!='pcb-clearance-settings/1' or type(d['revision'])is not int or d['revision']<1 or not isinstance(d['scope'],str):
        raise ValueError('CLEARANCE_REGISTRY_SCHEMA_CHANGED')
    nominal=_number(d['nominal_clearance_mm'],'nominal_clearance_mm',positive=True)
    tolerance=_number(d['relative_clearance_tolerance'],'relative_clearance_tolerance')
    if tolerance>=1:raise ValueError('CLEARANCE_TOLERANCE_MUST_BE_BELOW_ONE')
    margins=d['construction_margins_mm'];keys=('trace_land','source_contact','t01','spindle_barrier')
    if type(margins)is not dict or set(margins)!=set(keys):raise ValueError('CLEARANCE_MARGIN_SCHEMA_CHANGED')
    values=[_number(margins[k],k)for k in keys]
    policy=ClearanceSettings(nominal,tolerance,*values,hashlib.sha256(raw).hexdigest(),raw)
    if not all(math.isfinite(v)for v in policy.resolved().values()):raise ValueError('CLEARANCE_DERIVATION_NONFINITE')
    return policy


def capture(path=DEFAULT_REGISTRY):return from_bytes(Path(path).read_bytes())


def read_snapshot(path):
    payload=_decode(Path(path).read_bytes())
    if set(payload)!={'schema','source_sha256','source_json','resolved'}or payload['schema']!='pcb-clearance-job-snapshot/1':raise ValueError('CLEARANCE_SNAPSHOT_SCHEMA_CHANGED')
    policy=from_bytes(payload['source_json'].encode('utf-8'))
    if policy.source_sha256!=payload['source_sha256']or policy.resolved()!=payload['resolved']:raise ValueError('CLEARANCE_JOB_SNAPSHOT_CHANGED')
    return policy
