"""Legacy C03 source-profile wrapper; frozen input defaults retained."""
from pathlib import Path
from src.trace_first_scene import sha,read,save,load_scene as _load_scene
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'out/crop_dynamic_tasks/c02_focused_growth_coverage_20261028_05/inputs'
def load_scene(run,through='T04'):
 if through not in ('T01','T04','T02'):raise ValueError('SUPPORTED_C03_STAGE_REQUIRED')
 return _load_scene(run,through,cache=CACHE)
