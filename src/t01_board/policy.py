"""Board-wide selection of the existing source-derived T01 interaction policy."""
from src.t01_crop.policy import RULES as CROP_RULES
from src.t01_abi.contract import SETTINGS,PALETTE
from src.t01_abi import FAMILY
from src.stage_abi.store import canonical,digest
from src.stage_abi.contracts import fail,ref,finite_json

HEADER='T01 whole-board controlled English version 1.'
RULES=list(CROP_RULES)
RULES[0]=('R01','Use the verified PCB data ABI KiCad/Gerber pair and complete original F.Cu source geometry. Select every supported filled zero-stroke native graphic circle across the entire source, including covered circles and all exact aliases; keep every other source contribution fixed.','source','data-abi-qualified-entire-original-fcu')
RULES[-1]=('R16','Use every original F.Cu source surface as context and every eligible source circle as the priority pool. Derive a complete selection window from all source bounds plus the maximum T01 growth envelope; use no screenshot, image location, user coordinates or crop boundary keeps. Source-specific directives follow source identity.','roi_scope','complete-source-pool-no-image-selection')

def english():return HEADER+'\n'+'\n'.join(k+': '+t for k,t,_,_ in RULES)+'\n'
def compile_policy(text,binding_ref):
    ref(binding_ref,'binding_ref')
    if type(text)is not str or text.replace('\r\n','\n').strip()!=english().strip():fail('T01_ENGLISH_UNSUPPORTED','Complete whole-board normative wording required')
    return dict(stage='t01',family=FAMILY,dialect=HEADER,english=english(),english_sha256=digest(english().encode()),binding_ref=binding_ref,rules={f:v for _,_,f,v in RULES},settings=dict(SETTINGS),diameter_classes_mm=list(PALETTE),clause_trace=[dict(clause=k,english=t,contract_field=f,value=v) for k,t,f,v in RULES])
def validate_policy(p):
    if canonical(compile_policy(p['english'],p['binding_ref']))!=canonical(p):fail('T01_CONTRACT_DERIVATION_MISMATCH','Whole-board T01 policy')

def validate_binding(b):
    keys={'schema','source_ref','manifest_ref','source_sha256','manifest_sha256','source_objects','source_inventory_ref','viewport_mm','scope_ref','scope_sha256','reviewed_pairs','recess_source_ids'}
    if type(b)is not dict or set(b)!=keys or b['schema']!='t01-board-binding/1':fail('T01_BOARD_BINDING_INVALID','Closed complete-source binding required')
    finite_json(b)
    for k in ('source_ref','manifest_ref','source_inventory_ref','scope_ref'):ref(b[k],k)
    for k in ('source_sha256','manifest_sha256','scope_sha256'):
        if type(b[k])is not str or len(b[k])!=64 or any(c not in '0123456789abcdef' for c in b[k]):fail('T01_BOARD_BINDING_INVALID',k)
    v=b['viewport_mm']
    if type(b['source_objects'])is not int or b['source_objects']<=0 or type(v)is not list or len(v)!=4 or any(type(x)not in(int,float)for x in v) or v[0]>=v[2] or v[1]>=v[3]:fail('T01_BOARD_BINDING_INVALID','Counts or bounds')
    if type(b['reviewed_pairs'])is not list or type(b['recess_source_ids'])is not list:fail('T01_BOARD_BINDING_INVALID','Source directives')
    seen=set()
    for pair in b['reviewed_pairs']:
        if type(pair)is not list or len(pair)!=2 or any(type(s)is not str for s in pair) or len(set(pair))!=2 or seen.intersection(pair):fail('T01_BOARD_BINDING_INVALID','Disjoint source pairs')
        seen.update(pair)
    if any(type(s)is not str for s in b['recess_source_ids']) or len(set(b['recess_source_ids']))!=len(b['recess_source_ids']):fail('T01_BOARD_BINDING_INVALID','Recess identities')
    return b
