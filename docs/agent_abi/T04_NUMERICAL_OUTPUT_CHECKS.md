# T04 numerical output checks — 2026-11-27

This correction belongs to T04 itself, in
`src/gerber_u05/group_components.py` and
`src/gerber_u05/retained_boundary.py`. The portable 0.3.7 package contains
byte-identical copies of these repository modules. It is not a package-only
patch. The widening constructor, thresholds and established phase order remain
unchanged.

Independent clipping and unioning can manufacture tiny polygon faces on
unchanged source edges. Such a face alone does not demonstrate lost copper or
new physical growth. Source preservation now measures each exact original
contribution against its emitted contribution once, before combining affected
dependencies. Overlapping emitted support can retain that contribution.

Positive additions use immutable stage-entry contributions belonging to the
frozen physical owner. A numerical face may be excluded only by exact
containment or an exact rational proof that its complete exterior lies in one
finite original edge's convex capsule, bounded by eight coordinate ULP of that
support operand. Area is only a prefilter, never an exemption. A proved face
intersecting foreign copper still undergoes the actual contact/spacing checks.
Holes, original edges, ordered operands and original precision are preserved.

Production boundary sections come from the existing shared T02/T05 copper
context. Frozen owner membership supplies borrowed source references once;
this correction adds no private full-board index, owner reconstruction or
per-defect board union. Exact source subtractions are cached across overlapping
dependency groups. Real source loss, disconnection and clearance violations
remain fatal. Minor finishing findings remain review findings under the
existing output-disposition policy.

## Verification and retained evidence

The repository regression set passed 123 tests, including deliberate real
source loss, small physical additions, holes, foreign contact and
threshold-adjacent failures. The complete saved-board spacing batch passed
1,553 pairs in both operand orders, locally and on Neo, using the resident
shared boundary preparation. The fresh joined full-board run on Neo completed
with valid output and two review findings. All 1,005 emitted T04 source bodies
match the earlier retained construction byte for byte; no widening was changed
to make the checker pass.

Evidence is under
`out/lacie_work/copper_pipeline_viewer_037_20261127_01/`, especially
`REPOSITORY_SOURCE_PARITY.json`, `SOURCE_DELTA.json`, `qualification/` and
`neo-normal-run/`. Consult its `REPORT.md` for the final native viewer outcome;
geometry completion alone does not establish successful display.

Neo's fresh run took 3,629.441 seconds through the pipeline completion receipt,
including 918.466 seconds for assembly and 438.999 seconds for construction
serialization. A live process sample recorded a 32.5 GB peak physical
footprint on its 8 GB host. These are test accounting facts, not a memory
optimization claim. Neo is a test machine; no separate memory work lane is
authorized by this correction.

Both previous failed jobs remain unchanged. Do not resume, reseal or promote
them. No T05 treatment, export qualification or manufacturing acceptance is
created here.
