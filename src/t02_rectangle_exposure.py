"""Original exposed rectangle perimeter, independent of T01's circle rule.

Edges internal to the original copper composite are buried. Coincident outer
outlines remain exposed. Growth, pixels and covered-area fractions are never
measurement operands. Source identity and T02 ownership remain unchanged.
"""
from dataclasses import dataclass
from decimal import Decimal
import hashlib,json,math
from pathlib import Path
from shapely import to_wkb
from shapely.geometry import box
from shapely.ops import unary_union
from src.shape_containment import ContainmentIndex
from src.trace_width_clearance import TraceWidthContract

REGISTRY=Path(__file__).resolve().parents[1]/'contracts/t02_rectangle_exposure/settings.json'
SCHEMA='t02-rectangle-exposure-settings/1'
KEY='minimum_exposed_perimeter_fraction_for_growth'
TOLERANCE_KEY='relative_exposure_tolerance'
FIXED=dict(schema=SCHEMA,revision=2,status='PROVISIONAL',
 tolerance_convention='RELATIVE_TO_NOMINAL_THRESHOLD',
 comparison='GROWTH_ELIGIBLE_WHEN_GREATER_OR_EQUAL_TO_TOLERATED_THRESHOLD',
 context='COMPLETE_ORIGINAL_RESOLVED_SOURCE_COPPER',
 exclude='SELF_AND_EXACT_GEOMETRIC_ALIASES',
 measurement='ORIGINAL_RECTANGLE_PERIMETER_EXPOSED_TO_EMPTY_SPACE',
 action_below_limit='KEEP_EXACT_STAGE_ENTRY_AND_RETAIN_T02_OWNERSHIP',
 scope='ALL_T02_RECTANGLES; no T04 reassignment or inclusive-fill membership')

def pairs(values):
 result={}
 for key,value in values:
  if key in result:raise ValueError('DUPLICATE_T02_EXPOSURE_SETTING:'+key)
  result[key]=value
 return result

@dataclass(frozen=True)
class Settings:
 minimum_exposed_perimeter_fraction_for_growth:float
 relative_exposure_tolerance:float
 source_sha256:str
 raw_json:str
 @property
 def effective_floor_fraction(self):
  return float(Decimal(str(self.minimum_exposed_perimeter_fraction_for_growth))*(Decimal(1)-Decimal(str(self.relative_exposure_tolerance))))
 def snapshot(self):return dict(json.loads(self.raw_json),registry_sha256=self.source_sha256,registry_json=self.raw_json)

def from_bytes(raw):
 def invalid(value):raise ValueError('NONFINITE_T02_EXPOSURE_SETTING:'+value)
 value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
 if type(value)is not dict or set(value)!={*FIXED,KEY,TOLERANCE_KEY}or type(value['revision'])is not int or any(value[k]!=v for k,v in FIXED.items()):raise ValueError('T02_EXPOSURE_SETTINGS_SCHEMA_CHANGED')
 f=value[KEY]
 if type(f)not in(int,float)or not math.isfinite(f)or not 0<=f<=1:raise ValueError('T02_EXPOSURE_FRACTION_OUT_OF_RANGE')
 tolerance=value[TOLERANCE_KEY]
 if type(tolerance)not in(int,float)or not math.isfinite(tolerance)or not 0<=tolerance<1:raise ValueError('T02_EXPOSURE_TOLERANCE_OUT_OF_RANGE')
 return Settings(float(f),float(tolerance),hashlib.sha256(raw).hexdigest(),raw.decode())

def capture(path=REGISTRY):return from_bytes(Path(path).read_bytes())

def original_index(scene,original):
 from src import component_clearance as cc
 if cc.ACTIVE is not None and cc.ACTIVE.source_hash==scene['source_sha256']:return ContainmentIndex(cc.ACTIVE.originals)
 rows=scene['objects'];catalogued=[r for r in rows if 'growth_authority'in r['metadata']]
 if catalogued:
  from src.gerber_u05.source_catalogue import authority
  for r in catalogued:authority(r)
  return ContainmentIndex({r['source_id']:original[r['source_id']]for r in catalogued})
 if any('original_owner_id'in r['metadata']or'original_component_owner_id'in r['metadata']for r in rows):raise ValueError('T02_EXPOSURE_ORIGINAL_OCCURRENCE_CONTEXT_REQUIRED')
 return ContainmentIndex(original)

def assess(sid,index,settings,aliases=()):
 if sid not in index.geometries:raise ValueError('T02_EXPOSURE_ORIGINAL_TARGET_MISSING')
 core=index.geometries[sid]
 if core.is_empty or not core.is_valid or not core.equals(box(*core.bounds)):raise ValueError('T02_EXPOSURE_ORIGINAL_RECTANGLE_REQUIRED')
 near=sorted(index.ids[int(i)]for i in index.tree.query(core.envelope))
 excluded={sid,*aliases}|{s for s in near if index.geometries[s].equals(core)}
 contributors=[s for s in near if s not in excluded];other=unary_union([index.geometries[s]for s in contributors])
 exposed=core.boundary.intersection(unary_union([core,other]).boundary)
 length=exposed.length;fraction=length/core.length
 if not math.isfinite(fraction)or not 0<=fraction<=1:raise ValueError('T02_EXPOSURE_MEASUREMENT_INVALID')
 contained=index.assess(sid,sorted(excluded))['contained']
 # Compare lengths with the existing surface predicate's arithmetic epsilon.
 # A nominal half-perimeter must not flip to KEEP through a few binary ulps.
 # The separately registered relative exposure allowance is applied first.
 # This arithmetic epsilon changes no clearance or protected-pin predicate.
 epsilon=TraceWidthContract().comparison_epsilon_mm
 eligible=not contained and length+epsilon>=settings.effective_floor_fraction*core.length
 return dict(source_id=sid,source_geometry_sha256=hashlib.sha256(to_wkb(core)).hexdigest(),
             excluded_aliases=sorted(excluded),context_source_ids=contributors,
             other_copper_union_sha256=hashlib.sha256(to_wkb(other)).hexdigest(),
             perimeter_mm=core.length,exposed_perimeter_mm=length,exposed_perimeter_fraction=fraction,
             exposed_segments_wkb_hex=to_wkb(exposed).hex(),fully_contained=contained,
             minimum_exposed_perimeter_fraction_for_growth=settings.minimum_exposed_perimeter_fraction_for_growth,
             relative_exposure_tolerance=settings.relative_exposure_tolerance,effective_floor_fraction=settings.effective_floor_fraction,
             tolerance_consumed=eligible and length+epsilon<settings.minimum_exposed_perimeter_fraction_for_growth*core.length,
             growth_eligible=eligible,disposition='KEEP_CONTAINED'if contained else'ELIGIBLE_FOR_ORDINARY_T02_CHECKS'if eligible else'KEEP_EXPOSED_PERIMETER_BELOW_LIMIT',
             settings_sha256=settings.source_sha256,length_comparison_epsilon_mm=epsilon,
             comparison='GREATER_OR_EQUAL_TO_RELATIVE_TOLERATED_FLOOR; existing length arithmetic epsilon')

def records(scene,original,targets,settings):
 index=original_index(scene,original);rows={r['source_id']:r for r in scene['objects']}
 return {s:assess(s,index,settings,rows[s]['metadata'].get('alias_source_ids',()))for s in sorted(targets)}

def eligible(details,sid):
 # Legacy merge-only fixtures have no land plan. Public T02 plans always
 # require and reconstruct the complete exposure record in _context.
 values=details.get('rectangle_exposure')
 return values is None or values[sid]['growth_eligible']
