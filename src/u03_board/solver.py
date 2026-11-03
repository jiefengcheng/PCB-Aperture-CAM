"""Bounded-width scalar algorithm with a sparse whole-board evidence ledger.

Same ceiling-first, stable-order brackets and final-neighbor proofs as
bounded_width_solver; complete vectors are hashed rather than duplicated in
every ledger row. No numeric or clearance policy changes.
"""
import json,math
from src.stage_abi.store import canonical, digest
from src.stage_abi.contracts import StageABIError,fail
from src.source_offset_width import FAMILY


class ScaleVectorEncoding:
    """Exact canonical JSON bytes for a fixed-key vector with sparse updates."""
    def __init__(self,vector):
        canonical(vector)  # Preserve the shared strict plain-JSON contract.
        self.keys=sorted(vector);self.positions={k:i for i,k in enumerate(self.keys)}
        self.prefixes=[canonical(k)+b':' for k in self.keys]
        self.parts=[prefix+canonical(vector[k]) for k,prefix in zip(self.keys,self.prefixes)]

    def update(self,changes):
        for key,value in changes.items():
            i=self.positions[key];self.parts[i]=self.prefixes[i]+canonical(value)

    def sha256(self):return digest(b'{'+b','.join(self.parts)+b'}')


def read_width_check(store,reference):
    """Validate JSON while decoding rather than walking every decoded node.

    The standard decoder creates only plain JSON types and string object keys.
    Its two numeric hooks enforce the same finite-number rule, including
    overflowing exponent literals. Artifact bytes/kind/hash still use store.get.
    The shared Python-value validator and general artifact reader are unchanged.
    """
    def finite_float(token):
        value=float(token)
        if not math.isfinite(value):fail('NONFINITE_NUMBER','JSON numbers must be finite')
        return value
    def nonfinite(token):fail('NONFINITE_NUMBER','JSON numbers must be finite')
    try:return json.loads(store.get(reference,kind='width-check'),parse_float=finite_float,parse_constant=nonfinite)
    except (UnicodeError,json.JSONDecodeError) as error:raise StageABIError('ARTIFACT_JSON_INVALID',str(error)) from error


def validate_ledger(store,candidate):
    solution=candidate['solution'];groups=solution['stable_group_order'];vector=dict.fromkeys(groups,1.)
    encoded=ScaleVectorEncoding(vector)
    if solution['ledger_initial_scales']!=vector or len(candidate['check_refs'])!=len(solution['evaluations']) or solution['evaluation_count']!=len(candidate['check_refs']):
        raise ValueError('U03_WIDTH_LEDGER_COVERAGE_CHANGED')
    for i,(record,ref) in enumerate(zip(solution['evaluations'],candidate['check_refs'],strict=True)):
        if not set(record['changes'])<=set(vector):raise ValueError('U03_WIDTH_LEDGER_GROUP_CHANGED')
        vector.update(record['changes']);report=read_width_check(store,ref)
        if record['index']!=i:raise ValueError('U03_WIDTH_LEDGER_BINDING_CHANGED')
        encoded.update(record['changes'])
        if record['scales_sha256']!=encoded.sha256() or record['report_sha256']!=ref['sha256'] or record['passed']!=report['passed']:
            raise ValueError('U03_WIDTH_LEDGER_BINDING_CHANGED')
        if i==solution['final_check_index'] and (vector!=solution['selected_scales'] or not record['passed']):
            raise ValueError('U03_WIDTH_FINAL_VECTOR_CHANGED')
    return len(candidate['check_refs'])


def solve(group_ids, evaluate):
    ids = sorted(group_ids)
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('INVALID_GROUP_IDENTITIES')
    scales = dict.fromkeys(ids, 1.); checks = []; previous = dict(scales);encoded=None
    def check(proposal):
        nonlocal previous,encoded
        report = evaluate(proposal)
        if type(report.get('passed')) is not bool:
            raise ValueError('EXPLICIT_GEOMETRY_VERDICT_REQUIRED')
        changes={k:v for k,v in proposal.items() if v != previous[k]}
        if encoded is None:encoded=ScaleVectorEncoding(proposal)
        else:encoded.update(changes)
        record = dict(index=len(checks), scales_sha256=encoded.sha256(),
                      changes=changes,
                      passed=report['passed'], report_sha256=digest(canonical(report)),
                      failures=report.get('failures', []))
        previous = dict(proposal); checks.append(record); return record
    baseline = check(scales)
    if not baseline['passed']:
        raise ValueError('U03_WIDTH_BASELINE_REJECTED')
    decisions = []
    for gid in ids:
        cap = dict(scales); cap[gid] = 1.5; ceiling = check(cap)
        if ceiling['passed']:
            scales = cap
            decisions.append(dict(group_id=gid, selected_factor=1.5, upper_rejected_factor=None,
                                  status='HARD_CEILING_REACHED', safe_check_index=ceiling['index']))
            continue
        lo, hi = 1., 1.5; steps = 0
        while hi-lo > 1e-6 and steps < 36:
            mid = (lo+hi)/2; trial = dict(scales); trial[gid] = mid; result = check(trial); steps += 1
            if result['passed']: lo = mid
            else: hi = mid
        scales[gid] = lo
        decisions.append(dict(group_id=gid, selected_factor=lo, upper_rejected_factor=hi,
                              factor_bracket_width=hi-lo, search_steps=steps,
                              status='MODEL_BOUND_ESTABLISHED'))
    final = check(scales); proofs = []
    for d in decisions:
        upper = d['upper_rejected_factor']; gid = d['group_id']
        if upper is None:
            proofs.append(dict(group_id=gid, status='AT_HARD_CEILING', proved=True))
        else:
            trial = dict(scales); trial[gid] = upper; result = check(trial)
            proofs.append(dict(group_id=gid, status='FINAL_NEIGHBORS_REJECT_UPPER_BRACKET',
                               proved=not result['passed'] and upper-scales[gid] <= 1e-6,
                               upper_factor=upper, rejection_check_index=result['index']))
    proved = final['passed'] and all(p['proved'] for p in proofs)
    return dict(schema='u03-sparse-bounded-width-solver/1', status='PASS_COORDINATEWISE_MODEL_MAXIMUM' if proved else 'MAXIMUM_NOT_ESTABLISHED',
                passed=final['passed'], maximum_established=proved, selected_scales=scales,
                stable_group_order=ids, decisions=decisions, maximum_proofs=proofs,
                evaluations=checks, evaluation_count=len(checks), final_check_index=final['index'],
                scale_tolerance=1e-6, max_steps_per_group=36, geometry_family=FAMILY,
                hard_ceiling=1.5, applied='NONE', ledger_initial_scales=dict.fromkeys(ids, 1.),
                scope='Coordinate-wise model maximum; no global optimum or electrical/manufacturing claim')
