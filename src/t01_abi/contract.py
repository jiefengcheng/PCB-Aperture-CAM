"""A closed controlled-English dialect, compiled without an LLM or executable input.

Every normative clause has exactly one typed meaning. Case identities are supplied
separately by the trusted host. Arbitrary paraphrases are rejected, never guessed.
"""
from src.stage_abi.contracts import closed, fail, ref
from src.stage_abi.store import canonical, digest
from . import FAMILY

DIALECT = 'T01 controlled English version 1.'
CLAUSES = [
    ('R01', 'Use the bound original F.Cu source and complete exact geometry cache; change only the bound crop circle sites and their exact aliases.',
     'source', 'bound-original-full-cache'),
    ('R02', 'Discover all filled source circles intersecting the crop, including covered circles and complete edge circles; merge byte-identical aliases and cross-check raw source spans.',
     'eligibility', 'all-filled-intersecting-circles'),
    ('R03', 'Use each exact source polygon centroid as its computational center and the mean of its bounding-box width and height divided by four as its computational radius.',
     'circle_measurement', 'exact-polygon-centroid-and-mean-half-extents'),
    ('R04', 'Compute physical contact components from intersecting original F.Cu surfaces across the whole board; keep these distinct from growth competition pairs.',
     'components', 'whole-source-exact-intersects'),
    ('R05', 'Keep the bound reviewed pair first; greedily pair remaining competing sites by normalized center distance and stable source identities, leaving unpaired singletons.',
     'grouping', 'reviewed-pair-then-nearest-disjoint-pairs'),
    ('R06', 'Choose the largest source-qualified round priority per physical component, breaking ties by source identity; remove only the bound recess exceptions from round priority status.',
     'priorities', 'source-qualified-largest-per-component-with-bound-exceptions'),
    ('R07', 'Prefer each pair\'s largest common admissible diameter from the bound palette; otherwise use individual classes; preserve exact source geometry when no class is feasible.',
     'classes', 'largest-common-physical-diameter'),
    ('R08', 'Reduce constrained priorities by whole classes; jointly demote conflicting round priorities without scaling down their companions automatically.',
     'reservation', 'finite-class-joint-demotion'),
    ('R09', 'For each pair, use the priority anchor or first pair member as A; bound B\'s envelope by the facing side of A\'s enlarged-circle inscribed square at minus 45 degrees, with construction gap and safety.',
     'pair_interaction', 'final-A-square-support-bounds-B-envelope'),
    ('R10', 'Recover feasible next-class round promotions by greatest area gain and source-identity tie-break without shrinking other targets; recompute square bounds from final radii.',
     'promotion', 'maximal-discrete-greedy'),
    ('R11', 'Construct round priorities in source-identity order, then companions in centroid Y, X, identity order; each accepted enlarged contour replaces all its aliases in the current scene.',
     'schedule', 'priorities-first-live-alias-scene'),
    ('R12', 'Clip only optional companion copper against the current scene; retain source cores and attached additions; allow original trace contacts only inside fixed source-derived ports.',
     'companions', 'live-finite-surface-clipping-with-fixed-original-ports'),
    ('R13', 'For each bound recess exception, remove one optional lobe using its enlarged-circle square and the greatest actual obstacle conflict, breaking ties by source identity; apply all ordinary obstacle constraints afterward.',
     'recess', 'one-bound-exception-primary-conflict-square-lobe'),
    ('R14', 'Use a 1.5 growth cap, diameter palette 0.038 0.0761 0.2749 0.2999 0.3374 0.3749 0.4499 mm, construction gap 0.02002 mm, hard gap 0.020 mm, safety 0.00002 mm, 128 quadrant segments, area epsilon 0.0000000001 mm2 and event epsilon 0.00000001 mm2.',
     'numeric_model', 'frozen-C01-numerics'),
    ('R15', 'Verify every saved contour by source-bound reconstruction and final assembled finite-surface checks; retain rejected hypotheses and neighbor-restoration controls; never grant owner, independent or manufacturing acceptance.',
     'verification', 'complete-reconstruction-and-assembled-checks'),
]

SETTINGS = dict(hard_factor=1.5, construction_gap=.02002, hard_gap=.020,
                safety=.00002, orientation=-45, qsegs=128,
                area_epsilon=1e-10, event_epsilon=1e-8)
PALETTE = [.038, .0761, .2749, .2999, .3374, .3749, .4499]

def english_specification():
    return DIALECT + '\n' + '\n'.join(f'{key}: {text}' for key, text, _, _ in CLAUSES) + '\n'

def compile_english(text, binding_ref):
    if type(text) is not str or len(text.encode()) > 20000:
        fail('T01_ENGLISH_INVALID', 'Expected bounded controlled English')
    ref(binding_ref, 'binding_ref')
    # Only blank outer lines and CRLF versus LF are non-semantic formatting.
    lines = text.replace('\r\n', '\n').strip().split('\n')
    expected = english_specification().strip().split('\n')
    if len(lines) != len(expected) or lines[0] != DIALECT:
        fail('T01_ENGLISH_INCOMPLETE', 'The complete ordered version-1 clauses are required')
    trace = []
    for line, (key, wording, field, value) in zip(lines[1:], CLAUSES, strict=True):
        if line != f'{key}: {wording}':
            fail('T01_ENGLISH_UNSUPPORTED', key + ': unknown, reordered or changed normative wording')
        trace.append(dict(clause=key, english=wording, contract_field=field, value=value))
    return dict(stage='t01', family=FAMILY, dialect=DIALECT,
                english=english_specification(), english_sha256=digest(english_specification().encode()),
                binding_ref=binding_ref, rules={field:value for _,_,field,value in CLAUSES},
                settings=dict(SETTINGS), diameter_classes_mm=list(PALETTE), clause_trace=trace)

def validate_policy(policy):
    if type(policy) is not dict or 'binding_ref' not in policy or 'english' not in policy:
        fail('T01_CONTRACT_INVALID', 'Compiled English contract required')
    expected = compile_english(policy['english'], policy['binding_ref'])
    if canonical(expected) != canonical(policy):
        fail('T01_CONTRACT_DERIVATION_MISMATCH', 'Policy differs from its English derivation')
    return expected

def validate_binding(binding):
    closed(binding, {'schema','case_id','source_ref','manifest_ref','source_sha256',
                     'manifest_sha256','source_objects','viewport_mm','unique_sites',
                     'occurrences','reviewed_pair','recess_source_ids'}, 'T01 source binding')
    if binding['schema'] != 't01-source-binding/1':
        fail('T01_BINDING_UNSUPPORTED', 'schema')
    for k in ('source_ref','manifest_ref'):
        ref(binding[k], k)
    for k in ('source_objects','unique_sites','occurrences'):
        if type(binding[k]) is not int or not 0 < binding[k] <= 100000:
            fail('T01_BINDING_INVALID', k)
    v = binding['viewport_mm']
    if type(v) is not list or len(v)!=4 or any(type(x) not in (int,float) for x in v) or v[2]<=v[0] or v[3]<=v[1]:
        fail('T01_BINDING_INVALID','viewport')
    for k in ('reviewed_pair','recess_source_ids'):
        a=binding[k]
        if type(a) is not list or any(type(x) is not str for x in a) or len(set(a))!=len(a):
            fail('T01_BINDING_INVALID',k)
    if len(binding['reviewed_pair']) != 2:
        fail('T01_BINDING_INVALID','reviewed pair')
    return binding
