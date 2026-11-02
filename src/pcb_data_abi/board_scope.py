"""Complete native board scope belongs to the PCB data ABI, not T01/UI."""
import copy
from pathlib import Path
from shapely.geometry import box
from src.stage_abi.store import digest
from src.t01_crop.source import sites_from_cache
from src.t01_abi.contract import SETTINGS
from .roi import ROIService,local,bound,read,fresh,CLI,CLI_SHA

OPERATIONS=('pcb_inputs_verify','pcb_board_scope','pcb_board_verify')

def derive_scope(raw,manifest,shapes):
    bounds=[min(g.bounds[0]for g in shapes),min(g.bounds[1]for g in shapes),max(g.bounds[2]for g in shapes),max(g.bounds[3]for g in shapes)]
    _,_,sites=sites_from_cache(raw,manifest,shapes,bounds)
    pad=max(s['radius']for s in sites)*(SETTINGS['hard_factor']-1)+SETTINGS['construction_gap']
    viewport=[bounds[0]-pad,bounds[1]-pad,bounds[2]+pad,bounds[3]+pad]
    if not all(box(*viewport).covers(g)for g in shapes):raise ValueError('PCB_BOARD_SOURCE_WINDOW_INCOMPLETE')
    return dict(schema='pcb-board-scope/1',source_sha256=digest(raw),manifest_sha256=None,
        all_source_ids=sorted(r['id']for r in manifest['objects']),eligible_occurrence_ids=sorted(a for s in sites for a in s['aliases']),
        source_objects=len(manifest['objects']),canonical_sites=len(sites),source_occurrences=sum(len(s['aliases'])for s in sites),
        source_bounds_mm=bounds,bounds_mm=viewport,growth_padding_mm=pad,selection='Entire F.Cu native source; all filled zero-stroke graphic circles and aliases; other geometry fixed',image_used=False)

def assess_scope(value,expected):
    if value!=expected:raise ValueError('PCB_BOARD_SCOPE_COVERAGE_MISMATCH')
    return True

class BoardScopeService(ROIService):
    def __init__(self,host):
        if type(host)is not dict or set(host)!={'schema','inputs','output'} or host['schema']!='pcb-board-source-host/1' or set(host['inputs'])!={'kicad','gerber'}:raise ValueError('PCB_BOARD_HOST_INVALID')
        self.host=host;self.inputs={k:bound(v)for k,v in host['inputs'].items()};self.out=local(host['output'],True)
        if digest(CLI.read_bytes())!=CLI_SHA:raise ValueError('PINNED_KICAD_CLI_CHANGED')
    def verify_inputs(self):
        result=super().verify_inputs()
        manifest,_=self.load_source();allowed={'segment','arc','gr_line','gr_arc','gr_circle','gr_rect','gr_poly'}
        unsupported=[r['id']for r in manifest['objects']if r['kind']not in allowed or r['parent_id']is not None or r['unresolved_layers']]
        if unsupported:raise ValueError('PCB_BOARD_NATIVE_PROFILE_UNSUPPORTED:'+str(unsupported[:10]))
        return result
    def scope(self):
        manifest,shapes=self.load_source();result=derive_scope(self.inputs['kicad'].read_bytes(),manifest,shapes)
        result['manifest_sha256']=digest((self.out/'source_manifest.json').read_bytes())
        result['facts']=dict(passed=True,source_objects=result['source_objects'],canonical_sites=result['canonical_sites'],source_occurrences=result['source_occurrences'],complete_source_window=True,image_used=False,construction_status='NOT_RUN')
        fresh(self.out/'scope.json',result);return result
    def verify(self):
        manifest,shapes=self.load_source();saved=read(self.out/'scope.json');expected=derive_scope(self.inputs['kicad'].read_bytes(),manifest,shapes)
        expected['manifest_sha256']=digest((self.out/'source_manifest.json').read_bytes());expected['facts']=dict(passed=True,source_objects=expected['source_objects'],canonical_sites=expected['canonical_sites'],source_occurrences=expected['source_occurrences'],complete_source_window=True,image_used=False,construction_status='NOT_RUN')
        assess_scope(saved,expected)
        controls=[]
        for name,key in [('missing_source_object','all_source_ids'),('missing_circle_occurrence','eligible_occurrence_ids'),('shortened_board_window','bounds_mm')]:
            mutation=copy.deepcopy(saved)
            if key=='bounds_mm':mutation[key][2]-=.1
            else:mutation[key]=mutation[key][:-1]
            try:assess_scope(mutation,expected)
            except ValueError as error:controls.append(dict(name=name,error=str(error),status='PASS_EXPECTED_REJECTION'))
            else:raise ValueError('PCB_BOARD_CONTROL_NOT_REJECTED:'+name)
        result=dict(saved,schema='pcb-board-scope-verified/1',scope_sha256=digest((self.out/'scope.json').read_bytes()),
            facts=dict(passed=True,complete_source_coverage=True,source_objects=len(manifest['objects']),canonical_sites=saved['canonical_sites'],source_occurrences=saved['source_occurrences'],kicad_gerber_correspondence=True,deliberate_controls=3,image_used=False,construction_status='NOT_RUN'),controls=controls)
        fresh(self.out/'verified.json',result);return result
    def dispatch(self,operation):return dict(pcb_inputs_verify=self.verify_inputs,pcb_board_scope=self.scope,pcb_board_verify=self.verify)[operation]()
