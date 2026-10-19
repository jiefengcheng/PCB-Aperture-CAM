# Preliminary infrastructure visualization — delivered

The four requested themes are available in **Storage & indexes** at `http://127.0.0.1:8769/index.html`: **Discovery → Grouping → Storage & indexes → Selective export**. See [the usage guide](STORAGE_THEMES.md).

| Theme | What can be reviewed | Current evidence |
| --- | --- | --- |
| Discovery | Four native/Gerber role mappings, original source identities and retained footprint parent | Source-bound table and actual Gerber geometry |
| Grouping | Footprint ownership, copper contact, proximity and mask association shown separately; selecting a node highlights its geometry | Actual browser selection of R140.2, with measured 0.360 mm proximity and a separate copper group |
| Storage & indexes | Eight SQLite object rows, eight artifact revisions, 19 content-addressed files; SQL indexes versus the in-memory R-tree rebuilt on reopen | Inventories recomputed from the copied store; altered or omitted theme facts reject |
| Selective export | Include/exclude roles, deduplicate shared objects, retain required parents, preview and download a diagnostic manifest | Actual mask-only browser attachment: three objects, no write IDs, incomplete membership in the original contact group explicitly retained |

The download uses the existing read-only revision catalogue and selection machinery. It retains filtered recorded relationship witnesses, matches, qualifications and source references. It references saved payloads; the earlier full-context diagnostic store remains the byte-complete export/reopen evidence. No new connectivity or standalone KiCad/manufacturing output is claimed.

Published run: `out/ingestion/directory_intake/workbench/run-89e0672dff474f33bb58fe5d26bb8a0c/`. Dataset revision remains `687c863c124fd6b3f00c8a1db95b680c84bd03dd2d14481b759da63ed12a0ab5`. Cases, earlier native pipeline projections and the core reopened result compare identical to the preceding qualified delivery. Old publication profiles continue to verify.

Verification: **161 Python tests**, **five JavaScript suites**, actual browser selection/download, and publication verification of **378 outputs / five datasets / three comparisons**. The [independent Cursor audit](../../reviews/cursor/storage_themes_20261018/audit.md) returns **QUALIFIED_IN_DECLARED_SCOPE**, with no actionable findings; it checked 54 source/test/document hashes unchanged before and after, independently confirmed store inventories and subset counts 8/3/2/4, and exercised the local download endpoint.

Artifacts: `out/common_catalogue/themes_20261018/completion.json`, `verification/browser_download_mask.json`, `verification/grouping.png`, test logs and publication/preservation checks. The review is an additive presentation/selection assessment; original inputs, older receipts and engineering acceptance boundaries remain preserved.
