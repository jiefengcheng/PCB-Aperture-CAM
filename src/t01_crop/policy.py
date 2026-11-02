"""One controlled-English policy for every admitted ROI; source pins are separate."""
from src.t01_abi.contract import CLAUSES,SETTINGS,PALETTE
from src.t01_abi import FAMILY
from src.stage_abi.store import canonical,digest
from src.stage_abi.contracts import fail,ref,finite_json
import re

HEADER='T01 crop-driven controlled English version 2.'
CONCENTRIC_CENTER_EPS_MM=1e-12
RULES=[(k,t,f,v) for k,t,f,v in CLAUSES]
RULES[0]=('R01','Use the verified PCB data ABI input pair and complete original native geometry cache; the ROI selects whole source circle features and exact aliases, while every other source contribution stays fixed.','source','data-abi-qualified-original-with-roi-selection')
RULES[4]=('R05','Use source-identity reviewed pairs when both members are selected; otherwise greedily pair competing sites by normalized distance and stable source identities. Keep a selected member of a reviewed pair unchanged when its partner is outside the ROI.','grouping','identity-pinned-pairs-or-nearest-disjoint')
RULES[8]=('R09',"For each directional pair, use the priority anchor or first pair member as A; bound B's envelope by the facing side of A's enlarged-circle inscribed square at minus 45 degrees, with construction gap and safety. If distinct source circles are strictly nested and their computational centers differ by at most 0.000000000001 mm, retain both source identities and cores without choosing a facing side or applying this pair's directional square bound. Keep every ordinary size-class, priority, obstacle, source-port and final-assembly constraint.",'pair_interaction',dict(directional='final-A-square-support-bounds-B-envelope',concentric_nested='retain-both-sources-no-undefined-facing-side',center_epsilon_mm=CONCENTRIC_CENTER_EPS_MM,ordinary_constraints='unchanged'))
RULES.append(('R16','Use full original source surfaces for context. Choose priorities from the selected circle pool. Record the pool and boundary effects; keep location-uncertain boundary sites unchanged. Source-specific directives follow source identity, never crop names.','roi_scope','selected-pool-full-source-context-explicit-boundary-keep'))

def english():return HEADER+'\n'+'\n'.join(k+': '+t for k,t,_,_ in RULES)+'\n'
def compile_policy(text,binding_ref):
    ref(binding_ref,'binding_ref')
    if type(text)is not str or text.replace('\r\n','\n').strip()!=english().strip():
        fail('T01_ENGLISH_UNSUPPORTED','Complete crop-driven normative wording required; no inferred policy')
    return dict(stage='t01',family=FAMILY,dialect=HEADER,english=english(),english_sha256=digest(english().encode()),
        binding_ref=binding_ref,rules={f:v for _,_,f,v in RULES},settings=dict(SETTINGS),diameter_classes_mm=list(PALETTE),
        clause_trace=[dict(clause=k,english=t,contract_field=f,value=v) for k,t,f,v in RULES])
def validate_policy(policy):
    if canonical(compile_policy(policy['english'],policy['binding_ref']))!=canonical(policy):fail('T01_CONTRACT_DERIVATION_MISMATCH','Crop-driven policy')

def validate_binding(b):
    keys={'schema','source_ref','manifest_ref','source_sha256','manifest_sha256','source_objects','viewport_mm',
          'roi_ref','roi_sha256','location_uncertainty_mm','reviewed_pairs','recess_source_ids'}
    if type(b)is not dict:fail('T01_CROP_BINDING_INVALID','closed source/ROI binding')
    version=b.get('schema')
    if version=='t01-crop-binding/2':keys.add('source_inventory_ref')
    if set(b)!=keys or version not in ('t01-crop-binding/1','t01-crop-binding/2'):fail('T01_CROP_BINDING_INVALID','closed source/ROI binding')
    finite_json(b)
    for k in ('source_ref','manifest_ref','roi_ref'):ref(b[k],k)
    if version=='t01-crop-binding/2':ref(b['source_inventory_ref'],'source_inventory_ref')
    for k in ('source_sha256','manifest_sha256','roi_sha256'):
        if type(b[k])is not str or not re.fullmatch('[0-9a-f]{64}',b[k]):fail('T01_CROP_BINDING_INVALID',k)
    if type(b['source_objects'])is not int or b['source_objects']<=0:fail('T01_CROP_BINDING_INVALID','positive source object count')
    v=b['viewport_mm']
    if (type(v)is not list or len(v)!=4 or any(type(x) not in (int,float) for x in v)
        or v[0]>=v[2] or v[1]>=v[3] or type(b['location_uncertainty_mm']) not in (int,float)
        or not 0<=b['location_uncertainty_mm']<=.05):fail('T01_CROP_BINDING_INVALID','ROI or uncertainty')
    if type(b['reviewed_pairs'])is not list or type(b['recess_source_ids'])is not list:fail('T01_CROP_BINDING_INVALID','source directives')
    seen=set()
    for pair in b['reviewed_pairs']:
        if type(pair)is not list or len(pair)!=2 or any(type(s)is not str for s in pair) or len(set(pair))!=2 or seen.intersection(pair):fail('T01_CROP_BINDING_INVALID','disjoint reviewed feature pair')
        seen.update(pair)
    if any(type(s)is not str for s in b['recess_source_ids']) or len(set(b['recess_source_ids']))!=len(b['recess_source_ids']):fail('T01_CROP_BINDING_INVALID','unique recess identities')
    return b
