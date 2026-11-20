"""Fresh, scheduled profile ladder, separate from the legacy default policy.

Profiles use progress factors; their geometric width caps are independently
checked by the constructor. No retained pass state or replay enters this path.
"""
from src.stage_abi.store import canonical, digest

SCHEDULE = (1, 1, 1, 1, 2, 2, 2)


def solve(widths, settings, evaluate, accept, *, pass_increments=None,
          prefix=None, checkpoint=None, describe_rung=None):
    if prefix is not None or checkpoint is not None:
        raise ValueError('T04_PROFILE_FRESH_ONLY')
    increments = list(pass_increments or SCHEDULE)
    if tuple(increments) != SCHEDULE or sum(increments) != settings.step_count:
        raise ValueError('T04_PROFILE_SCHEDULE_CHANGED')
    order = sorted(widths)
    if not order:
        raise ValueError('T04_COMPLETE_ROUTE_WIDTHS_REQUIRED')
    rungs = dict.fromkeys(order, 0)
    attempts = dict.fromkeys(order, 0)
    ledger, passes, last = [], [], {}
    for number, step in enumerate(increments, 1):
        advanced = []
        for sid in order:
            if rungs[sid] == settings.step_count:
                continue
            rung = min(settings.step_count, rungs[sid] + step)
            candidate = (settings.rung(widths[sid], rung) if describe_rung is None else
                         describe_rung(sid, rung))
            attempts[sid] += 1
            check = (evaluate(sid, candidate['factor']) if candidate['within_growth_limits'] else
                     dict(passed=False, failures=[dict(reason=candidate['blocking_reason'])],
                          scope='PARAMETER_LIMIT; geometry not constructed'))
            if type(check.get('passed')) is not bool or type(check.get('failures')) is not list or (check['passed'] and check['failures']):
                raise ValueError('T04_COMPLETE_CANDIDATE_CHECK_REQUIRED')
            row = dict(index=len(ledger), pass_number=number, route_id=sid,
                       preceding_rung=rungs[sid], candidate=candidate,
                       passed=check['passed'], failures=check['failures'],
                       check_sha256=digest(canonical(check)))
            ledger.append(row)
            last[sid] = row
            if check['passed']:
                accept(sid, candidate['factor'])
                rungs[sid] = candidate['rung']
                advanced.append(sid)
        passes.append(dict(number=number, advanced_routes=advanced))
        if not advanced:
            break
    decisions = []
    for sid in order:
        result = (settings.rung(widths[sid], rungs[sid]) if describe_rung is None else
                  describe_rung(sid, rungs[sid]))
        terminal = ('MAXIMUM_FACTOR_RUNG' if rungs[sid] == settings.step_count else
                    'PRESCRIBED_PASS_LIMIT' if last[sid]['passed'] else
                    last[sid]['failures'][0].get('reason', 'SCENE_CHECK_REJECTED') if last[sid]['failures'] else
                    'SCENE_CHECK_REJECTED')
        decisions.append(dict(route_id=sid, final_rung=rungs[sid], attempts=attempts[sid],
                              selected_factor=result['factor'], original_width_mm=result['original_width_mm'],
                              resulting_width_mm=result['resulting_width_mm'],
                              total_width_increase_mm=result['total_width_increase_mm'],
                              percentage_growth=result['percentage_growth'], blocking_reason=terminal,
                              last_check_index=last[sid]['index']))
    return dict(schema='source-route-ten-step-width-ladder/1', passed=True, process_completed=True,
                geometry_family='original-source-uniform-outward-offset', parameters=settings.resolved(),
                settings_sha256=settings.source_sha256, stable_route_order=order, selected_rungs=rungs,
                selected_scales={d['route_id']: d['selected_factor'] for d in decisions},
                evaluation_count=len(ledger), geometry_evaluation_count=sum(r['candidate']['within_growth_limits'] for r in ledger),
                passes=passes, evaluations=ledger, decisions=decisions,
                stop_reason='NO_ROUTE_ADVANCED' if not passes[-1]['advanced_routes'] else 'PRESCRIBED_PASSES_COMPLETED',
                maximum_claim='NONE; safe prescribed discrete process only', pass_increments=increments)
