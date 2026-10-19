# Preliminary Storage & indexes visualization

This presentation extends the completed bounded R140 catalogue. It uses the existing dataset revision and recorded retrieval/export; no new board extraction, repair or engineering qualification is performed.

Open `http://127.0.0.1:8769/index.html`, choose **Storage & indexes**, then use the four theme cards:

1. **Discovery** joins native and Gerber occurrences for the four returned roles. Select a row to inspect the actual Gerber geometry and bound source record. The R140 footprint remains a parent dependency.
2. **Grouping** diagrams footprint ownership, copper contact, proximity and the mask association separately. The graph is a relationship schematic; the pane beside it shows actual board coordinates. R140.1 and its trace form one copper group; R140.2 is a separate nearby group.
3. **Storage & indexes** shows actual SQLite table/index inventories and content-addressed files. This store contains eight object rows and eight artifact revisions. The same-artifact SQL relations table has zero rows; cross-source matches, contact witnesses and qualifications are pinned JSON sidecars. The R-tree is rebuilt in memory on reopen from three stored native copper shapes. It is not advertised as a durable R-tree file.
4. **Selective export** lets the reviewer include/exclude roles. Shared native objects deduplicate and required parent records follow automatically. All four roles include eight source occurrences; the trace alone includes two; the mask role includes its native pad, its Gerber opening and the footprint dependency.

**Preview selection** composes a diagnostic manifest from the verified replay. On the local server, **Download selection manifest** resolves those roles through read-only catalogue selections and returns a normal JSON attachment. It includes source/revision identities, records, dependencies, matches, qualifications and selection receipts, and references the saved payloads. It does not produce a standalone KiCad board. The linked recorded full-context export contains the original byte-complete store and retains the earlier fresh-process reopen proof. Offline pages retain a data-link preview manifest; the local-server download is the tested route for the in-app browser.

The new producer profile is `common_context_presentation: storage-themes-v1`. Historical publications without it retain their existing projection and continue to verify. For a rebuild retaining the current registry:

```sh
.venv/bin/python tools/ingestion.py --output out/ingestion/directory_intake/workbench --storage-themes
```

Counts, file sizes, source links, SQLite index definitions and spatial-state descriptions are derived from the copied catalogue during publication and recomputed during verification. Altered or omitted theme facts reject. Cases and earlier source inspectors remain available.

Verification artifacts and the additive review are recorded under `out/common_catalogue/themes_20261018/`. The preceding Step 2 completion/audit remains historical and does not stand in for verification of this presentation change.
