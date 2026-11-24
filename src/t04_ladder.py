"""Deterministic independent-route widening, with no continuous search."""
from src.stage_abi.store import canonical, digest

SCHEMA = 'source-route-ten-step-width-ladder/1'


def solve(widths, settings, evaluate, accept=lambda route, factor: None, *, keep_routes=None):
    """evaluate sees the current accepted scene; accept publishes one change.

    A rejected next rung may be reconsidered on the next complete pass. There
    are at most ten passes and ten attempts per route, including cap failures.
    Neither callback may start a combination or continuous-factor search.
    """
    order = sorted(widths)
    keep_routes={}if keep_routes is None else keep_routes
    if not set(keep_routes)<=set(order):raise ValueError('T04_KEEP_ROUTE_OUTSIDE_INVENTORY')
    if not order or any(type(s) is not str for s in order):
        raise ValueError('T04_COMPLETE_ROUTE_WIDTHS_REQUIRED')
    for width in widths.values():
        settings.rung(width, 0)
    rungs = dict.fromkeys(order, 0)
    attempts = dict.fromkeys(order, 0)
    last = {}; ledger = []; passes = []
    for number in range(1, settings.step_count + 1):
        advanced = []
        for sid in order:
            if rungs[sid] == settings.step_count:
                continue
            candidate = settings.rung(widths[sid], rungs[sid] + 1)
            if sid in keep_routes:
                candidate=dict(candidate,within_growth_limits=False,blocking_reason='GLOBAL_TRACE_ELIGIBILITY_KEEP')
            attempts[sid] += 1
            if not candidate['within_growth_limits']:
                check = dict(passed=False, failures=[dict(reason=candidate['blocking_reason'])],
                             scope='PARAMETER_LIMIT; geometry not constructed')
            else:
                check = evaluate(sid, candidate['factor'])
                if type(check) is not dict or type(check.get('passed')) is not bool or type(check.get('failures')) is not list:
                    raise ValueError('T04_COMPLETE_CANDIDATE_CHECK_REQUIRED')
                if check['passed'] and check['failures']:
                    raise ValueError('T04_INCONSISTENT_PASS_WITH_FAILURES')
            row = dict(index=len(ledger), pass_number=number, route_id=sid,
                       preceding_rung=rungs[sid], candidate=candidate,
                       passed=check['passed'], failures=check['failures'],
                       check_sha256=digest(canonical(check)))
            ledger.append(row)
            if check['passed']:
                accept(sid, candidate['factor'])
                rungs[sid] += 1; advanced.append(sid)
            last[sid] = row
        passes.append(dict(number=number, advanced_routes=advanced))
        if not advanced:
            break
    decisions = []
    for sid in order:
        result = settings.rung(widths[sid], rungs[sid])
        terminal = ('MAXIMUM_FACTOR_RUNG' if rungs[sid] == settings.step_count else
                    'TEN_PASS_LIMIT' if last[sid]['passed'] else
                    last[sid]['failures'][0].get('reason', 'SCENE_CHECK_REJECTED') if last[sid]['failures'] else
                    'SCENE_CHECK_REJECTED')
        decisions.append(dict(route_id=sid, final_rung=rungs[sid], attempts=attempts[sid],
                              selected_factor=result['factor'],
                              original_width_mm=result['original_width_mm'],
                              resulting_width_mm=result['resulting_width_mm'],
                              total_width_increase_mm=result['total_width_increase_mm'],
                              percentage_growth=result['percentage_growth'],
                              blocking_reason=terminal,
                              last_check_index=last[sid]['index']))
    return dict(schema=SCHEMA, passed=True, process_completed=True,
                geometry_family='original-source-uniform-outward-offset',
                parameters=settings.resolved(), settings_sha256=settings.source_sha256,
                stable_route_order=order, selected_rungs=rungs,
                selected_scales={d['route_id']:d['selected_factor'] for d in decisions},
                evaluation_count=len(ledger), geometry_evaluation_count=sum(r['candidate']['within_growth_limits'] for r in ledger),
                passes=passes, evaluations=ledger, decisions=decisions,
                stop_reason='NO_ROUTE_ADVANCED' if not passes[-1]['advanced_routes'] else 'TEN_COMPLETE_PASSES',
                maximum_claim='NONE; safe prescribed discrete process only')


def replay(widths, settings, solution, evaluate, accept=lambda route, factor: None, *, keep_routes=None):
    """Freshly execute every prescribed attempt and compare the complete ledger."""
    actual = solve(widths, settings, evaluate, accept,keep_routes=keep_routes)
    if canonical(actual) != canonical(solution):
        raise ValueError('T04_FRESH_LADDER_REPLAY_CHANGED')
    return dict(passed=True, complete_ladder_replayed=True,
                attempts=actual['evaluation_count'], passes=len(actual['passes']),
                settings_sha256=settings.source_sha256,
                solution_sha256=digest(canonical(solution)))
