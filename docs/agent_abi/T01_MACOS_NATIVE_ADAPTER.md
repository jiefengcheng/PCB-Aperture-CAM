# Local macOS native runner and adapter

User direction: no MCP. Keep the native runner and contracts, with an extendible,
system-specific adapter above them. The first supported target is local macOS.

```text
Local Code / another local file-capable agent
                  |
       macOS adapter: JSON mailbox
                  |
    native runner: bounded call/result + custody
                  |
             unchanged T01 ABI
```

This is a project-local interface, not an industry standard. It makes setup
repeatable through one versioned descriptor and contract, without requiring each
agent to load Shapely or execute the project interpreter in its own tool host.
No MCP, web server, network listener, installed service or global agent settings
are involved. A foreground native process consumes local files while the agent
uses its existing authorized file tools. The process must remain running.

## Start and acquire

From this checkout, start once with a fresh output directory:

```sh
.venv/bin/python -B tools/t01_macos_adapter.py --session out/<fresh-session>
```

The runner verifies assets, protected results, source bindings and runtime, then
prints the path to `agent_setup.json`. Give that same descriptor to each local
agent. The standard-library convenience client runs in the agent's existing
Python host:

```sh
python3 tools/t01_route_client.py --setup <absolute-agent_setup.json> --agent LocalCode --attempt <fresh-attempt-id>
```

An agent with file tools can instead follow
`contracts/t01/macos_adapter.json`: read the descriptor, atomically publish a
request in `inbox`, and read its correlated reply. No arbitrary executable, shell
command, output path, geometry authority or other-stage operation is accepted.
The descriptor lists the exact exposed operations and input schemas.

The native runner remains independently usable, without the adapter:

```sh
.venv/bin/python -B tools/t01_native_route.py --session out/<another-fresh-session>
```

The default routes perform setup conformance only: positive controlled-English
compilation, the R14 semantic-negative rejection, and actual native describe.
The separately authorized C01 extension requires `--profile c01` and uses the
checked operation/audit sequence described below. A setup pass alone grants no
geometry execution authority.

## Custody and progress

The native runner preserves actual command, request, stdout, stderr, exit status,
identity and hashes under `attempts`. Failed attempts remain intact; reusing an
attempt ID is rejected. The adapter separately retains the exact submitted
request, start event, reply and hashes under `calls`. Completed native operations
publish timestamped completion records. These provide real progress without
coordinator prompts or a reasoning watchdog.

Replies include the native receipt path and digest. Clients check correlation,
runtime identity and file hashes; the running native process independently checks
its retained receipt digest. This is integrity within one local user account,
not authentication of an agent or protection against a process that can rewrite
the entire checkout. It requires the same authorized project-file access already
used by the agent. Do not add permissions or escape a sandbox to make it work.

A timeout means incomplete evidence, not a cancelled native operation. Claimed
calls are never automatically replayed. If the process stops mid-call, retain
that session and inspect its evidence; start a fresh session for a new attempt.
Stop the foreground adapter with Ctrl-C after use. No daemon is installed.

## Extension boundary and qualification

System adapters customize invocation and presentation. They share
`NativeRoute.call(operation, arguments, caller)` and its result/receipt contract.
They do not implement T01 geometry, reinterpret policy, grant themselves execution
authority, or alter T02/shared clearance behavior. Only macOS file transport is
implemented in this slice. Apple Intelligence, App Intents and other platforms
are future adapters, not established compatibility.

Qualification is recorded separately for native runner controls, macOS transport,
and actual Local Code use. A coordinator client pass cannot stand in for the
Local Code proof or the later one-instruction autonomous C01 experiment.

The superseded, untested MCP draft is retained only as historical design material
under `out/crop_dynamic_tasks/t01_macos_native_adapter_20261031_304/superseded_draft/`.
It is not an available route or setup requirement.

## Scoped validation — 2026-10-31

Session 304 passed 23 focused tests and three actual native setup conformance
attempts through the same descriptor. One was invoked by Local Code through its
existing supported Python tool, without per-step coordinator transport. It read
back the actual stdout/stderr and reported exit 0, the expected negative exit 2,
and receipt integrity PASS. The other two client labels were coordinator-hosted
repeatability probes, not independent reviewers.

The runner used Python 3.14.5, Shapely 2.1.2 and GEOS 3.13.1; T01 implementation
91213e88cef84814017620b81592750f68953682c3919412e3c791146e33cfcc
and shared runtime remained unchanged. The adapter was stopped after testing.
See the evidence index and final custody receipt in
`out/crop_dynamic_tasks/t01_macos_native_adapter_20261031_304/`.
Full autonomous C01 execution, wider custody qualification and Apple adapters
remain unqualified by this setup slice.

## Authorized C01 extension

Setup remains the default profile. The explicitly selected `--profile c01` now
exposes the C01 recovery sequence one operation at a time, with native technical
checks and operator observation audits before continuation. See
`T01_C01_MACOS_RECOVERY.md` and `contracts/t01/c01_route.json`. Session305
passed the observed bounded route and exact post-construction C01 comparison;
this does not upgrade session304 or general qualification retroactively.

## Authorized PCB-data file extension

`--profile c01-files` exposes five PCB-data operations to materialize/reopen
KiCad, export/reparse native Gerbers and falsify corrupt copies. It uses the same
macOS adapter and stdlib client, with source-bound native custody and observation
audits. The observed session306 case passes with EDIT-style polygon representation
and geometry/role preservation, rather than byte identity. See
`T01_C01_FILE_WRITEBACK.md`; this is not general PCB editing qualification.
