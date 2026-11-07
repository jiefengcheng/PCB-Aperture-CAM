# Source rectangle terminals in T02

Gerber plotting syntax does not by itself distinguish a terminal from a trace.
The 3020212826 marked small rectangular terminals are short draws made with
rectangular apertures. Treating all draws as T04 routes limited these terminals
to the trace-width ladder, so they missed the existing T02 rectangle treatment.

`source-short-rectangular-aperture-terminal/1` admits a native positive Line as
a T02 rectangle only when all these source facts hold:

- Its aperture is rectangular, with finite positive dimensions.
- Its centreline is horizontal or vertical, has positive length, and is no
  longer than the smaller aperture dimension.
- Its complete resolved copper is exactly its axis-aligned bounding rectangle.
- No later clear operation clips that source occurrence.

This is a bounded compact-terminal family. Long fingers, longer rectangular
traces, diagonal sweeps, arcs and degenerate source contexts remain in their
existing families. Unsupported clipped traces retain their explicit rejection.
Existing Flash and rectangular Region admission is unchanged.

Recognition happens at source intake, before T04 admission or its frozen-width
guard. The source ID, byte span, prefix hash, original geometry and aliases are
preserved. The native draw and attachment-width ledger remains unchanged for
T01. Both T03 variants continue to check the original native draw. The filled
land row has zero trace width for T02's land checker; its separate native port
width and centreline metadata are retained.

`src/gerber_u05/source_catalogue.py` records one exclusive source growth owner
and the roles consumed by T03, T04, T02 and T05. Every fresh source binding has
a hash-bound `source_catalogue_ref`, covering all effective source occurrences.
New short-draw terminals carry `growth_owner: T02`; their T04 role is explicitly
excluded. T03 verifies their original native draws and T05 recognizes them as
source lands. Consumers check the catalogue's source ID, original geometry hash,
family and assignment binding. Missing or changed authority on a newly
recognized terminal fails; ordinary older scenes retain their original family
contract. The catalogue grants no new geometric, clearance or remedy authority.

Inclusive-fill reconstruction independently replays the original ordered
proposals from their entry pin-rejection state, and checks the resulting full
rejection history. Construction's sticky history remains installed for later
fills and stages; verification cannot clear it or turn rejected fragments into
accepted copper.

T02 then applies its existing fixed-centre, independent per-axis 1.25 ceiling,
containment KEEP, integral source joints, foreign-copper and functional-channel
clearance, protected pin separation, budgets, reconstruction and 20% inclusive
fill checks. Reclassification grants no authority to import an old widened
trace, bypass a frozen T04 decision, fill a protected slot, or change source
polarity. T05 sees the newly qualified source land and its original trace
attachments through the existing land admission.

The larger boxed 0.650 mm Flash pad already belongs to T02. Its retained
horizontal/vertical difference was constrained by neighboring copper. This
slice does not change that growth algorithm, its centre, or its spacing rules.

`tools/qualify_t02_rectangle_terminals.py` records a separate bounded study:
fresh classification and eleven marked rectangles over exact retained T03 copper,
with full current-scene physical/pin checks and actual export/reparse. Its
retained prefix is explicitly identified. It is not a fresh current-T01,
T04, T05, full-U05 or manufacturing qualification. All previous jobs and failed
evidence remain immutable; historical `.DS_Store` custody failures remain
**EXPLICIT_UNWAIVED_UNATTRIBUTED**. Integration requires separate review of the
findings and highlighted result.
