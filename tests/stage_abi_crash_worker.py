"""Fault injection after a real executed journal event has committed."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.stage_abi.store import ArtifactStore
from src.stage_abi.registry import TrustedRegistry
from src.stage_abi.service import StageService
from src.stage_abi.lands import LandAdapter
from src.stage_abi.width import WidthAdapter
from src.stage_abi.routes import RouteAdapter
from src.stage_abi.spindle import SpindleAdapter
from src.stage_abi.journal import ExecutionJournal
config=json.loads(Path(sys.argv[1]).read_text());doc=config['registry'];store=ArtifactStore(config['store']);adapters={p['adapter']:{'t01':LandAdapter('t01'),'t02':LandAdapter('t02'),'t03':RouteAdapter(),'t04':WidthAdapter(),'t05':SpindleAdapter()}[p['stage']] for p in doc['profiles'].values()};original=ExecutionJournal.call

def interrupted(self,name,inputs,producer):
 result=original(self,name,inputs,producer)
 if self.cursor>=config['crash_after']:
  Path(config['marker']).write_text(str(self.cursor));os._exit(73)
 return result
ExecutionJournal.call=interrupted
response=StageService(store,TrustedRegistry(store,doc),adapters).dispatch(config['request']);print(json.dumps(response));sys.exit(0)
