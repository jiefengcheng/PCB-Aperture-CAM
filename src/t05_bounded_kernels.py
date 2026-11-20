"""Select the retained junction kernels for a bounded comparison."""
from contextlib import contextmanager
from contextvars import ContextVar

ACTIVE = ContextVar('t05_bounded_junction_kernels', default=False)


@contextmanager
def bounded_junction_kernels():
    """Allow geometry-changing kernels in a proposal-level replay.

    Compare actual output geometry and complete checks against the reference
    with the authorized bounded-resemblance contract. Stage run/verify reject
    this scope, so the caller must explicitly provide a bounded sample.
    """
    token = ACTIVE.set(True)
    try:
        yield
    finally:
        ACTIVE.reset(token)
