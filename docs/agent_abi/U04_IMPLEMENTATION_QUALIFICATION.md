# U04 C03 reconciliation and runtime correction — 2026-11-03

**PASS for fresh C03 U04 native qualification; owner PENDING_USER.**
T01 → T03 → T04 → T02 completed all 43 native gates and deterministic machine
audits with zero human/agent observations. No rendering; independent NOT_RUN:
CHANNEL_UNAVAILABLE; electrical/manufacturing NOT_ESTABLISHED.

[Reconciliation, runtime, limitations and custody report](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/evidence/u04_c03_reconcile_20261103T114634Z/REPORT.md)
· [Final audit](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/evidence/u04_c03_reconcile_20261103T114634Z/FINAL_AUDIT.json)
· [Native report](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/operator_routes/u04_board/managed/jobs/20261103T121121Z-1068388351fb4a01b7b855bcd930c489/native/U04_REPORT.md)

T02 native construction took 73.445 seconds;
47 rectangles grew and 6 inclusive fills qualified.
Every bounded attempt and final surface check was reconstructed. The failed
1,800-second run remains unchanged, as do all accepted C03 files. The complete
source-role and policy differences from the historical final C03 geometry are
listed in the report; this is not owner acceptance or a T05 execution.

Final source fingerprint: `67abc1f2543ea3ce54c78bd05c7b3db209d76d8d92f7a4162c6adb113c125616`. Final frozen source
passed 128 focused regressions, then the fresh 43-gate C03 run. Earlier 38-check
synthetic native qualification preceded the last operation-local preparation
cache change; its scope is preserved separately. Shared kernels are unchanged.

---

# Earlier synthetic qualification — retained 2026-11-03

**PASS for bounded synthetic implementation qualification.** U04 is **T01 → T03 → T04 → T02**. U05 is reserved for U04 + T05 and was not implemented or executed.

158 distinct tests passed: 132 predecessor/stage regressions, nine rectangle/surface regressions, one fresh native U03 command regression, and 16 U04 tests. The final U04 test suite took 408.52 seconds for both native cases and its unit checks; this is synthetic qualification timing, not real-board runtime.

| Fresh native case | Gates / machine audits | Machine predicates | Final bound files | Actual T02 outcome |
|---|---:|---:|---:|---|
| Whole board | 41 | 761 | 1265 | 2 grown rectangles, 1 inclusive fills |
| Absolute crop image | 43 | 944 | 1298 | NO_APPLICABLE_FEATURE; full predecessor retained |

Both commands produced and reparsed actual fresh before/candidate nine-layer native Gerbers. All written rectangle/inclusive contours, T01 lands and T04 trace contours were accounted for; remaining F.Cu atoms and eight other layers were protected. Native crop qualification retained the exact supplied synthetic image bytes and unchanged outside-crop source copper. Positive rectangle/inclusive construction is demonstrated by the whole-board case; the native crop case qualifies the empty T02 branch.

All runs record deterministic machine audits and **zero human/agent observations**. Owner **PENDING_USER**; independent **NOT_RUN: CHANNEL_UNAVAILABLE**; electrical/manufacturing **NOT_ESTABLISHED**. Rendering **NOT_REQUESTED**. At that earlier checkpoint no real raw directory had been supplied for U04, and no real-board run or runtime was established. No owner app trial, acceptance promotion, commit or push occurred.

## Retained evidence

[Final custody audit](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/evidence/u04_scope_correction_20261103T095350Z/FINAL_AUDIT.json) — SHA-256 `53a963a52cbce8ef810f9134712f6ce189e070e8f87a843f58496c145f642d59`.

Earlier implementation fingerprint: `7f100e059321ac05f5df9aad2fbf8c72b9d648d82cb914b795f72e0e6f6c2c89`. Base HEAD: `b1a75aa523c44568a3aba54aa741edd7d590f0f8` with uncommitted U04 changes. The audit checked every final artifact hash, native attempt receipt, machine-proof evidence hash and producer snapshot for both current jobs. All 70 immutable assets passed their manifest; U03/U02 kernels, stage ABI and their contracts match HEAD.

- Whole-board [native report](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/operator_routes/u04_board/managed/jobs/20261103T100727Z-dfeab6c12a5f43e8826f812729acbb7c/native/U04_REPORT.md) · [retained job](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/operator_routes/u04_board/managed/jobs/20261103T100727Z-dfeab6c12a5f43e8826f812729acbb7c) · [terminal result](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/operator_routes/u04_board/terminal_runs/20261103T100727Z-2f9dfba6e359474093dbe109523ace51/result.json)
- Crop-image [native report](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/operator_routes/u04_board/managed/jobs/20261103T101058Z-c0acd957f4434ee2a092908692e45dac/native/U04_REPORT.md) · [retained job](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/operator_routes/u04_board/managed/jobs/20261103T101058Z-c0acd957f4434ee2a092908692e45dac) · [terminal result](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/operator_routes/u04_board/terminal_runs/20261103T101058Z-61a157df88174841b4cb2cd76f5b84b2/result.json)

- [u04_corrected_native_v2.log](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/u04_corrected_native_v2.log) — `d97fb614f4f4e50d652775aa6fe406b9837b533422213749b3073973debedffd`
- [u04_predecessor_regressions_v1.log](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/u04_predecessor_regressions_v1.log) — `f0602c0df3ea5789ec623a7dbe0e879c17f8224647fff895c5ebe0db1c8fde6c`
- [u04_rectangle_surface_regressions.log](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/u04_rectangle_surface_regressions.log) — `45abebc3866c7aaabc61d13e6cb2a483a865d3aaa6de60480622f0f782e9cac2`
- [u04_legacy_u03_native_v1.log](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/u04_legacy_u03_native_v1.log) — `d51fdf3e0377307bd6fe7c8c2bf591b8f6ca0bdb00fd0ce699df7da691512f52`

## Preserved failures and scope correction

The earlier owner-stopped mistaken U04/T05 job remains stopped at [its original location](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/operator_routes/u04_board/managed/jobs/20261103T095047Z-fe06fb047f2e4a0aa8bf2014231949b7). The superseded 20-file implementation snapshot verifies byte-for-byte against [its manifest](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/evidence/u04_scope_correction_20261103T095350Z/STOPPED_IMPLEMENTATION.json). It is not U04 or U05 qualification.

The first corrected positive run [halted at its final route gate](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/out/lacie_work/operator_routes/u04_board/managed/jobs/20261103T095855Z-a3f04018754d4970bce000dbe11d0481). Its five actual negative controls rejected correctly, while the inherited route expected exactly three. U04 now requires the exact applicable inherited and rectangle/inclusive fault names and rejection prefixes. A dedicated regression rejects missing, duplicated or falsely labelled controls. Fresh independent jobs on the corrected implementation passed; the failed job was not resumed, retried or resealed.

## Running a new case

Use [the U04 recipe](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/docs/agent_abi/U04_SINGLE_COMMAND.md) and [contract](/Users/geoffcheng/Projects/client/PCB/aperture_align_demo/PCB_Aperture_CAM_V1_Codex_Handoff/contracts/operator/u04_board.json). From this checkout:

```sh
./tools/Run_U04_Board.command --input-dir "/explicit/absolute/raw/directory" --whole-board
# Or provide an actual absolute crop-image path:
./tools/Run_U04_Board.command --input-dir "/explicit/absolute/raw/directory" --crop "/explicit/absolute/crop/image.png"
```

Ordinary-English Local Code request: “Run fresh U04 (T01 → T03 → T04 → T02), without rendering, from <explicit absolute raw directory>, optionally using <explicit absolute crop-image path>. Review every native gate and return audited candidate KiCad/Gerber exports and evidence. Stop on failure; keep owner review pending.” Reopen the existing native launcher once for U04 support; the owner operates the app.

The qualified T02 family covers original axis-aligned zero-stroke filled source rectangles, original 1.25× axis caps and separately qualified connected inclusive fills. Rotated rectangles in scope halt as unsupported. Other native forms and crop-crossing complete envelopes remain protected. T02 does not alter trace paths/widths, reclassify T01 polygons, infer electrical intent, establish manufacturing approval or claim a global optimum.
