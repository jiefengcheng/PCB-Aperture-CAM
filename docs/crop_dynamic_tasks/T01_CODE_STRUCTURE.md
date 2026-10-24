# T01 code map

The accepted T01 crop is a pipeline with frozen source facts, a policy decision,
geometry construction, independent saved-output checks, and a browser review.
Keep those boundaries visible when extending the trial:

```text
ORG source + pinned policy
        │
        ├── crop_circle_sources.py       source identities and immutable cores
        ├── crop_balanced_t01.py         scene revisions, reservations and construction
        ├── crop_diameter_selection.py   discrete diameter target decisions
        ├── crop_square_recess.py        optional square-guided recess construction
        └── crop_owner_review.py         hash-bound, named owner target edits
                 │
                 ▼
        run_crop_balanced_t01.py          orchestration and evidence capture
                 │
           ┌─────┴──────┐
           ▼            ▼
 audit_crop_...       render_crop_...
 fresh saved-output   local replay page
 checks               and receipt
```

`tools/run_crop_diameter_classes_t01.py` is the narrow command-line entry point
for the shared-class, promotion, and owner-review policies. Its flags select a
pinned contract; it does not contain geometry logic. The saved run bundle records
the exact hashes of each implementation module that participated.

## Responsibilities and invariants

- Source discovery and identity stay in `crop_circle_sources.py`; source bytes
  and frozen historical evidence are not edited by this pipeline.
- `crop_balanced_t01.py` owns mutable accepted-scene revisions and execution
  order. It receives frozen target radii; it does not choose a size class.
- `crop_diameter_selection.py` chooses discrete targets and evaluates round
  reservations before construction.
- `crop_square_recess.py` removes optional growth in response to an actual
  selected copper neighbor; it retains the original core and lets actual copper
  determine the hard gap.
- `crop_owner_review.py` reads hash-bound prior run reports and applies only
  named owner edits. It freezes all other target radii.
- `tools/audit_crop_balanced_t01.py` reconstructs checks from saved geometry in
  a fresh process. It shares the native parser and geometry kernel with the
  constructor, so this is evidence auditing, not independent engineering
  qualification.
- `tools/render_crop_balanced_t01.py` presents saved, audited output. The browser
  does not execute board edits.

`src/crop_diameter_classes.py` is retained as a compatibility facade for existing
imports. New implementation code should import the narrow module that owns the
operation. Preserve this facade until downstream scripts and tests migrate.

## Current boundary

The owner accepted the reviewed crop in run
`out/crop_dynamic_tasks/t01_owner_review_20261024_v2/`. This refactor changes
module ownership and import paths only; it does not regenerate or replace that
frozen accepted run. T01's separate dynamic-adaptation criterion remains
`PARTIAL`; owner acceptance of the visual crop does not change that measured
criterion. The next task can build on these boundaries without coupling review
policy to geometry construction.
