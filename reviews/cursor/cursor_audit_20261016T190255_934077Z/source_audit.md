## Independent Read-Only Audit Report

### Findings (ordered by severity)

- **P1 — Independent execution evidence is missing in this session (blocking for a clean acceptance verdict).**  
  - **File/line:** N/A (execution environment constraint).  
  - **Trigger/reproduction:** Attempted to run read-only shell verification (`git rev-parse` + packet hash recompute + `tools/ingestion.py --verify`), but shell calls are blocked in this Ask-mode session with: *“You are in ask mode and cannot run non read-only tools.”*  
  - **Expected:** Independently run the packet-specified verify command and local checks.  
  - **Actual:** Could only perform static file/code/artifact inspection; no independent command execution, no live browser validation, no test re-run.

- **P3 — Published metadata still hardcodes “channel unavailable” for Cursor review.**  
  - **File/line:** `src/ingestion_registry.py` line 98, `web/ingestion_views.js` line 56, `out/ingestion/workbench/run-05888c57424f4db48bd9821fc8324b36/receipt.json` line 440.  
  - **Trigger/reproduction:** Source and run receipt inspection.  
  - **Expected:** Neutral or updatable review status after authenticated review availability.  
  - **Actual:** `cursor_review` / UI text remains `NOT_RUN: CHANNEL_UNAVAILABLE`.  
  - **Impact:** Not a geometry/registration blocker, but status text is stale relative to the now-authenticated review channel.

---

### R1–R4 correction status (independent assessment)

- **R1 (false-positive publication verification):** **Code-level corrected; runtime re-execution NOT_ESTABLISHED in this session.**  
  Evidence in `src/ingestion_verification.py` line 73 (schema), 74 (PASS status), 76–77 (non-empty outputs + required files), 82–83 (exact inventory/hash verification), 93–95 (embedded scene + registry binding), 126 (render input binding).

- **R2 (actual Gerber render inputs unbound/drift):** **Code-level corrected; runtime re-execution NOT_ESTABLISHED.**  
  Evidence in `src/ingestion_visuals.py` line 57 onward: verified bindings before/after composition (lines 68 and 80), receipt-bound input resolution (lines 29–53), explicit source/native inputs in run receipt `render_inputs`.

- **R3 (cross-pane geometry leakage):** **Code-level corrected; live browser re-check NOT_RUN here.**  
  Evidence in `web/ingestion_views.js` lines 39–44: separate source pane, native pane, delta-only pane; JS contract assertions in `tests/js/ingestion_views.test.cjs` line 30.

- **R4 (hardcoded/cross-dataset measurement leakage):** **Code-level corrected; runtime re-execution NOT_ESTABLISHED.**  
  Evidence in `web/ingestion_views.js` lines 20–33 using `qualification.records`; dataset switching and leakage checks in `tests/js/ingestion_views.test.cjs` lines 33–34; receipt-projection logic in `src/ingestion_visuals.py` lines 10–27.

---

### Requirement 6 / 7 / 9 status

- **Requirement 6 (stable ingestion entry + publication verification):**  
  - Entry exists at `out/ingestion/workbench/index.html` redirecting to run `run-05888c57424f4db48bd9821fc8324b36`.  
  - Verifier logic is materially stronger in code.  
  - **Independent status in this session:** **NOT_ESTABLISHED** (no command execution permitted).

- **Requirement 7 (visual review and evidence link integrity):**  
  - Scene/receipt structure appears complete and bound; pane separation implemented.  
  - **Independent status in this session:** **NOT_ESTABLISHED** (no live browser inspection performed here).

- **Requirement 9 (durable reproduction + exercised checks):**  
  - Test suite expansion is present (`tests/test_ingestion_registry.py` now 11 ingestion-focused tests; JS DOM contract test file present).  
  - Existing logs show pass, but those are inspected artifacts, not my independent rerun.  
  - **Independent status in this session:** **NOT_ESTABLISHED**.

---

### Independent commands/results vs unrun checks

- **Independent command execution:**  
  - `NOT_RUN` (shell execution blocked in this Ask-mode channel).

- **Specifically unrun due mode constraints:**  
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/ingestion.py --verify out/ingestion/workbench/run-05888c57424f4db48bd9821fc8324b36`  
  - `python -m unittest tests.test_ingestion_registry -v`  
  - JS test execution and live browser inspection

- **What was independently inspected instead:**  
  - Packet, policy/handoff docs, triggering assessment, source files, tests, published run files, and remediation evidence JSON/log artifacts.

---

### Reviewed HEAD and source hashes

- **Reviewed HEAD (from `.git/refs/heads/main`):** `19ff47204d429b93fdac21d3b1a94ed3462b3629`  
- **Packet-declared source hashes (from `packet.json`):**
  - `src/ingestion_registry.py`: `5d9e98ecba2a7686563f839d9fb5b487394e9e9db20b2de18d07bbb510826ed8`
  - `src/ingestion_verification.py`: `306760bf3448614883adf691bb655ca99e92fd3c65c2055b933e70bad94826f9`
  - `src/ingestion_visuals.py`: `1add49520e0facdb2bc0ae90e03c8ca0a970e9b19107dea50ec6de7195fac8cd`
  - `web/ingestion_views.js`: `8a82ade1b5a26abe909f81b76e6c49c5685b5b2669c92dc128a43381d60cb590`
  - `tools/ingestion.py`: `8a8bee68442b92bc18664ea5a7b3d2514190d6f82676e4604cb9acc356366b7b`
  - `tests/test_ingestion_registry.py`: `dd6d871659d054620a3d2719553cdd17020fb954d34e82e54dcaf6d3cda77a2e`
  - `tests/js/ingestion_views.test.cjs`: `b8ff4c075541251b24412ed671db78063d91a3ae181cd57f7de1f4bc167af93a`
  - `contracts/ingestion_registry_v1.json`: `f2777e0f7b3cecdbce024e5daf55b44c8a66e81e1d8617a8e052052cfc5558c5`
- **Hash recomputation against disk:** `NOT_RUN` (tooling restriction in this session).

---

### Scope limits observed

- Read-only inspection only; no edits, no external services, no adjacent checkout reads, no installs, no agent launches.
- Original rejected run and prior review artifacts are preserved in place (as referenced by `completion_audit_v2.json`).

---

## Verdict

**COMPLETION_NOT_ESTABLISHED**

**Reason:** I found no new code-level blocker in the R1–R4 remediation path from static inspection, but I could not independently execute the required verification command/tests or perform live visual validation in this session due execution restrictions. A clean `QUALIFIED_IN_DECLARED_SCOPE` verdict requires at least one independent, successful runtime verification pass in this authenticated channel.
