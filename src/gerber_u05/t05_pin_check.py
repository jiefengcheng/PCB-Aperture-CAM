"""Complete T05 pin predicates from unchanged source-bound material parts.

Union distributes over restriction to each complete protected domain. Reuse
the existing streaming checker so unrelated overlapping copper outside those
domains cannot break a pin predicate's preliminary whole-board overlay.
No coordinates, materials, domains, spacing rules or rejection state change.
"""


def require_parts(rule, material, *, scope='t05_complete'):
    proof = rule.check_parts(material, finished=True)
    if not proof['passed']:
        raise ValueError('PIN_SEPARATION_' + scope.upper() + '_FAILED:' +
                         str([r for r in proof['checks'] if not r['passed']][:3]))
    return proof
