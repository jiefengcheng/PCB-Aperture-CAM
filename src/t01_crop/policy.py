"""One controlled-English policy for every admitted ROI; source pins are separate."""
from src.t01_abi.contract import CLAUSES,SETTINGS as LEGACY_SETTINGS,PALETTE
from src.clearance_policy import HARD_GAP_MM, LEGACY_CONSTRUCTION_MM
SETTINGS=dict(LEGACY_SETTINGS,hard_gap=HARD_GAP_MM,construction_gap=LEGACY_CONSTRUCTION_MM)
from src.t01_abi import FAMILY
from src.stage_abi.store import canonical,digest
from src.stage_abi.contracts import fail,ref,finite_json
import re

HEADER='T01 canonical source analysis with read-only ROI version 4.'
CONCENTRIC_CENTER_EPS_MM=1e-12
RULES=[(k,t,f,v) for k,t,f,v in CLAUSES]
RULES[13]=('R14',CLAUSES[13][1].replace('construction gap 0.02002 mm','construction gap 0.04002 mm').replace('hard gap 0.020 mm','hard gap 0.040 mm'),'numeric_model','production-clearance-040-v1')
RULES[0]=('R01','Use the verified PCB data ABI input pair and complete original native geometry cache; the ROI selects whole source circle features and exact aliases, while every other source contribution stays fixed.','source','data-abi-qualified-original-with-roi-selection')
RULES[4]=('R05','Use source-identity reviewed pairs when both members are selected; otherwise greedily pair competing sites by normalized distance and stable source identities. Keep a selected member of a reviewed pair unchanged when its partner is outside the ROI.','grouping','identity-pinned-pairs-or-nearest-disjoint')
RULES[8]=('R09',"For each directional pair, use the priority anchor or first pair member as A; bound B's envelope by the facing side of A's enlarged-circle inscribed square at minus 45 degrees, with construction gap and safety. If distinct source circles are strictly nested and their computational centers differ by at most 0.000000000001 mm, retain both source identities and cores without choosing a facing side or applying this pair's directional square bound. Keep every ordinary size-class, priority, obstacle, source-port and final-assembly constraint.",'pair_interaction',dict(directional='final-A-square-support-bounds-B-envelope',concentric_nested='retain-both-sources-no-undefined-facing-side',center_epsilon_mm=CONCENTRIC_CENTER_EPS_MM,ordinary_constraints='unchanged'))
RULES[0]=('R01','Use complete original native F.Cu source for canonical T01 construction; a view does not select targets or priorities.','source','canonical-whole-source')
RULES[1]=('R02','Discover every supported filled zero-stroke original F.Cu circle across the entire source, including covered and nested circles; merge exact aliases and cross-check all original source spans.','eligibility','all-source-filled-circles-and-exact-aliases')
RULES[4]=('R05','Keep source-identity reviewed pairs first; greedily pair other competing source sites by normalized distance and stable source identities. Immutable permission keeps remain fixed singleton sources. Presentation bounds have no effect.','grouping','source-reviewed-pairs-or-nearest-disjoint-no-view-dependency')
RULES.append(('R16','Discover the complete native source circle pool, regardless of presentation bounds. Crops are read-only views; legacy crop-bound writes are retired. Immutable source permissions keep blocked objects unchanged.','roi_scope','read-only-view-no-construction-dependency'))
RULES[14]=('R15','Verify every saved contour by complete source-bound reconstruction and final assembled legacy finite-surface checks; retain rejected hypotheses, neighbor-restoration controls and the square-disabled control. Apply the unchanged complete visible-copper guard to every proposal: hard gap 0.04000 mm, construction gap 0.04010 mm, original contact buffer 0.04002 mm and comparison epsilon 0.000000000001 mm. Construct with an additional 0.00002 mm reserve and 0.0000000001 mm core containment reserve. Retain complete rounds or hold them unchanged; never clip them into companions. Reconstruct the full scene and retain every legacy check.','verification','complete-reconstruction-and-assembled-plus-uniform-full-surface-checks')


def english():return HEADER+'\n'+'\n'.join(k+': '+t for k,t,_,_ in RULES)+'\n'
def compile_policy(text,binding_ref):
    ref(binding_ref,'binding_ref')
    if type(text)is not str or text.replace('\r\n','\n').strip()!=english().strip():
        fail('T01_ENGLISH_UNSUPPORTED','Complete crop-driven normative wording required; no inferred policy')
    from src.t01_canonical import marker
    return dict(canonical_t01=marker(),stage='t01',family=FAMILY,dialect=HEADER,english=english(),english_sha256=digest(english().encode()),
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
