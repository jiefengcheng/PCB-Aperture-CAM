# T02 repeated predecessor-buffer preparation

Status: isolated performance candidate, not integrated. This is separate from
the provisional 1% shared-gap matching policy. The active full-board U05 job
continues from its unchanged captured source.

A cProfile of the complete 78-rectangle policy replay measured 269.835 seconds.
The two inclusive-fill passes took 192.308 seconds. T04 width-fence checks took
195.021 cumulative seconds and buffer construction took 177.096 seconds. The
same predecessor skin was rebuilt for repeated rejected fill proposals.

The candidate reuses that exact immutable predecessor's existing native-fidelity
buffer. Every logical proposal still computes its additions, forbidden overlap
and no-bypass result. The key includes geometry identity, tolerance and buffer
segments. Equal coordinates with different geometry or precision metadata are
not treated as the same object. A changed predecessor replaces the one cached
entry; oversized entries are not retained. The estimate is capped at 32 MiB per
Rule. This is a bounded cache estimate, not a process RSS limit.

The serialized rule and all returned predicate fields remain unchanged. No
search, shape, numerical tolerance, spacing, pin, source, growth-cap, budget,
export/reparse or corruption check is removed. Cache-disabled parity and the
existing gate regressions remain required. No measured speedup is claimed until
the same retained-proposal replay and actual native checks finish.
