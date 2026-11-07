"""Replaceable matching tolerance, captured separately from copper fidelity."""
from dataclasses import dataclass
import hashlib,json,math
from pathlib import Path

REGISTRY=Path(__file__).resolve().parents[1]/'contracts/t02_shared_gaps/settings.json'
FIXED=dict(schema='t02-shared-gap-settings/1',revision=1,status='PROVISIONAL',
 comparison='MAXIMUM_MINUS_MINIMUM_DIVIDED_BY_MINIMUM',
 scope='Complete source-qualified shared-neighbor gap spans; no clearance, pin, growth-cap or frozen-slot exemption')
KEY='maximum_relative_gap_difference'

@dataclass(frozen=True)
class Settings:
 maximum_relative_gap_difference:float
 raw_json:str
 source_sha256:str
 def snapshot(self):return dict(json.loads(self.raw_json),registry_json=self.raw_json,registry_sha256=self.source_sha256)

def from_bytes(raw):
 def pairs(values):
  result={}
  for key,value in values:
   if key in result:raise ValueError('DUPLICATE_T02_GAP_SETTING:'+key)
   result[key]=value
  return result
 def invalid(value):raise ValueError('NONFINITE_T02_GAP_SETTING:'+value)
 value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
 if type(value)is not dict or set(value)!={*FIXED,KEY}or type(value['revision'])is not int or any(value[k]!=v for k,v in FIXED.items()):raise ValueError('T02_GAP_SETTINGS_SCHEMA_CHANGED')
 fraction=value[KEY]
 if type(fraction)not in(int,float)or not math.isfinite(fraction)or not 0<=fraction<1:raise ValueError('T02_GAP_TOLERANCE_OUT_OF_RANGE')
 return Settings(float(fraction),raw.decode(),hashlib.sha256(raw).hexdigest())

def capture(path=REGISTRY):return from_bytes(Path(path).read_bytes())
