# Production default 0.040 mm

Owner instruction: “The production 0.020 mm policy should be adjust to 0.040mm by default.”

Normal app and Terminal T01/T03/T04/T02/T05 now share the pinned production clearance authority in contracts/clearance/production.json and src/clearance_policy.py. Hard floor 0.04000 mm; construction 0.04010 mm; contact buffer and T01 construction 0.04002 mm; T05 barrier 0.04011 mm. Existing numerical safety margins, scalar caps, original-contact authority, exact predecessor/coverage/pagination, nominal/envelope/upper proofs, two U05 evaluations, native write/reopen/export/reparse and corruption controls remain. Recognition tolerances and source widths are not clearance defaults.

Canonical T01 /4 archives /3 contract 650f43a1a58ba477513af32742d05a33a6dd4c20e70e58859e3d82daf26ba17d byte-identically. Permissions, contained-shape KEEP and C028 BLOCKED obligation remain. Old 0.020 mm qualification is historical; it is not relabelled as 0.040 mm qualification.

Validation: 200 focused and 317 broader tests pass (overlap). Fresh synthetic whole-board U04+U05 passed 41+14 native gates; another whole-board U04 passed 41. All 28 U05 evaluator workers were distinct in their pairs and succeeded. The additional crop trial had already passed 43 native gates before the owner waived further crop testing. Its final test lookup failed after native completion; corrected read-only postcondition verification is retained. No native job was resumed or retried. Tests-only correction did not change native runtime; every native result stays bound to its captured producer cut.

The U04 crop host/auditor carryover was aligned with U03 canonical whole-source T01. Crop location and T04 write-scope checks remain. No T04 recovery family or crop boundary was expanded.

Evidence: out/lacie_work/evidence/production_clearance_040_20261104T182448Z. NATIVE_VALIDATION.json records exact jobs, checks, failed receipts and source limits. SOURCE_GUARDS.json and PRODUCTION_DEFAULT.patch describe only the clearance integration; the snapshot storage guard was excluded. The original production storage guard is unchanged. Four early stopped test jobs and all 2,896 files remain exact. Original failed C03 evidence and coverage recovery are separate.

The .DS_Store custody failures remain explicit, unwaived and unattributed. No historical acceptance promotion. The performance 10% target remains waived by owner; geometry/check criteria remain. Owner PENDING_USER; independent NOT_RUN: CHANNEL_UNAVAILABLE; electrical/manufacturing NOT_ESTABLISHED.

Next requested operation is fresh whole-board U04 then U05 over the explicit HFlex input directory, no rendering or C03 reference. The remaining literal sweep follows this rung.
