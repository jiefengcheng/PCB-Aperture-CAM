# T01 owner corrections — 2026-10-24

S38 and S22 are restored to their exact pre-promotion saved contours (diameter
0.29998 mm). S08 uses a 0.3749 mm envelope and a square-guided recess explicitly
toward S12. This is an owner-specific exception to full roundness; S31 retains
its earlier exception. The other 49 target radii equal the previous reviewed run;
related optional companion contours may readapt.

Review http://127.0.0.1:8783/ . Start at **Your 3 marked locations**: compare
marks 1 and 2 with the earlier sizes, then inspect expanded mark 3. Use
**Previous result** on the whole crop for context. Existing annotations remain
attached to the earlier report; fresh annotations bind this result.

## Evidence and reproduction

- Output: `out/crop_dynamic_tasks/t01_owner_review_20261024_v2/`
- Report SHA-256: `c65f91a33cf6b6770da818bbe517da3c4b21eb4e2614fcd77af5935c4316fdb9`
- Policy: `contracts/crop_owner_review_t01_policy.json`
- Reproduce: `.venv/bin/python tools/run_crop_diameter_classes_t01.py --apply-owner-review --output out/crop_dynamic_tasks/t01_owner_review_replay_01`
- `fresh_audit.json` checks exact undo contours, fixed other radii, S08's selected
  neighbor, square-disabled controls, source preservation and the 1.5× ceiling.
- 35 focused tests passed. Same-policy replay saved equal geometry.

40/51 sites grow; 24 remain round reservations and two have explicit recess
exceptions. Total added copper decreases from 1.378447 to 1.371317 mm² because
undo is intentional. This is not a maximal-growth claim.

The owner accepted this saved crop visually after review. T01 remains
**PARTIAL**: 18 reservation-response sites are separate from zero true
evolving-companion response sites (target at least three). Fresh-process checks
share the author, parser and geometry kernel; they are not independent
electrical, manufacturing or EDIT-rule qualification. Frozen rejected T01-R1
records and native boards remain unchanged. Cursor review:
`NOT_RUN: CHANNEL_UNAVAILABLE`.

The owner decision is captured separately in
`contracts/agent_abi/v0_1/owner_decisions.json` and bound to this run's source,
scene, policy, report and audit hashes. The historical report and publication
receipt retain their original pre-review status fields.
