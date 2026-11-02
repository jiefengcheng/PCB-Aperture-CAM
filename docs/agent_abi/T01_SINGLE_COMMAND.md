# One Terminal command: raw directory → T01 → audited native exports

From any Terminal working directory:

```sh
"/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/tools/Run_T01_Board.command" --input-dir "/Users/geoffcheng/Projects/client/PCB/szu_comm/manual-test-3020301113B/ORG"
```

The directory is the only input operand. It is never fixed to a project default,
previous crop, prepared job or previous result. Another raw directory uses the
same command with a different path. The entry selects the pinned project Python,
starts native directory intake and owns an in-process macOS file adapter for the
entire fresh run. It needs no pre-opened launcher, Local Code, model, MCP, service,
installation, network or global configuration. Native OS access is attempted
automatically; real denials retain exact errno/path in the native intake evidence.

The same eighteen native source/T01/export operations execute in the original
order, including full source coverage, every inspection/comparison/port page,
fresh construction, separate fresh reconstruction, protected-object checks,
native KiCad writing/rereading and actual nine-layer Gerber export/reparse with
corruption controls. Unmatched raw Gerbers are explicitly excluded/unqualified
companions, snapshotted and delivered byte-for-byte unchanged. No rendering or
later stage is exposed.

After every successful native attempt, a deterministic auditor checks its receipt,
ABI correlation, real process exit, raw response and gate-specific source/artifact
predicates. Each proof records actual operands, expected values, hashes and
PASS/FAIL. The native route recalculates that proof before advancing. These
proofs live under `native/audits/machine-NNN/proof.json` and are included in the
original native checkpoints. The legacy wire decision token
`PASS_SLICE_OBSERVATION_AUDIT` remains for checkpoint compatibility; its note
links the explicit machine proof. No `review-N.json` or agent observation is made.

The final report states **18 machine audits, zero human/agent observations**.
This is automatic technical qualification, with owner PENDING_USER, independent
NOT_RUN: CHANNEL_UNAVAILABLE and electrical/manufacturing NOT_ESTABLISHED.
Machine predicates do not synthesize the qualitative judgment of a human/agent.
The ordinary-English stepped route remains available with its original mode.

A failure halts before another slice, retains all receipts and proof failures,
prints an evidence path, marks subsequent operations NOT_RUN and exits nonzero.
No retries, resume, changed tolerance, shortened source, alternate input or
acceptance promotion are performed. Ctrl-C stops only owned native process
groups and retains the interrupted attempt. Keep the Terminal command running;
progress is printed during native work and after each accepted machine audit.
Source qualification can take around two minutes; full native construction and
independent reconstruction are additional work. No agent thinking is involved.

The command uses the shared project managed job slot and lock. It cannot replace
an incomplete/active job or silently retry identical failed bytes/code. A
completed predecessor remains untouched. For isolated engineering qualification
only, `--state-dir /absolute/project/out/path/managed` selects separate state;
it never changes the source-directory operand or acceptance rules.

Exit 0 returns candidate KiCad, native Gerbers, excluded companions, export HTML
and `MACHINE_RECEIPT.json` links. The nine-layer export comes from the supplied
KiCad board; companion layer identity/geometry remain unqualified. Original
shared clearance and file-grid limitations are unchanged. No manufacturing or
strict universal-distance claim follows from a successful machine run.

Adapter supervision: the unattended Terminal client checks adapter liveness on
every reply poll. An adapter exception or unexpected thread exit halts the wait
immediately. The Terminal journal retains `adapter_failure.json` with exception
type, errno and traceback, and `processes/process-<pid>.json` records actual native
exit codes and captured output. Failure-record write errors emit the original
record and storage error to stderr. Freeing disk space does not resume an exited
adapter; preserve the failed attempt and use a fresh job after fixing the cause.
These machine records do not constitute human observation or owner acceptance.


LaCie storage policy (2026-11-02): the same Terminal command now prepares a
project-specific APFS sparse image stored on LaCie and uses `out/lacie_work/`
for new managed jobs, journals, exports and temporary files. No internal fallback
is permitted. The image has a 200 GiB ceiling and grows only as used; LaCie is
not reformatted. Both image and backing volume must retain a 5 GiB reserve.
Use `tools/Run_PCB_Tests.command` for tests and
`tools/Prepare_LaCie_Workspace.command` before other engineering writes.
The Local Code native launcher must be reopened once to use the new defaults.
No old evidence is relocated or deleted. These project controls cannot prevent
unrelated applications from consuming the internal system disk.
