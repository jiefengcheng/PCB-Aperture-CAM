---
type: "Playbook"
title: "Review an existing workbench"
description: "Verify and browse recorded visual evidence without creating a new operation."
generated: {"by": "codex/pcb-cam-runbooks-v1", "at": "2026-10-16T14:43:36.762882+00:00"}
status: "stable"
tags: ["pcb", "cam", "runbook", "project-local"]
sources: [{"id": "implementation", "resource": "/references/sources.json", "title": "Version-bound implementation and source register"}, {"id": "source-1", "resource": "/references/source_text/docs--CLIENT_DATA_DEMO.txt", "title": "docs/CLIENT_DATA_DEMO.md"}, {"id": "source-2", "resource": "/references/source_text/docs--VISUAL_WORKBENCH.txt", "title": "docs/VISUAL_WORKBENCH.md"}, {"id": "source-3", "resource": "/references/source_text/docs--consolidation--RUN_CONSOLIDATED_DEMO.txt", "title": "docs/consolidation/RUN_CONSOLIDATED_DEMO.md"}]
---

# Select and verify

Use `out/client_demo/current.txt` for the client tour, or `out/consolidation/current_visual.txt` for Processing/Storage and the synthetic/public cases. Pointers are convenience references, not immutable evidence identities. Resolve the pointer, verify that directory, and record its build receipt before presenting it.

```sh
.venv/bin/python - <<'PYCODE'
from pathlib import Path
import subprocess, sys
bundle = Path(Path('out/client_demo/current.txt').read_text().strip())
subprocess.run([sys.executable, 'tools/verify_visual_bundle.py', str(bundle)], check=True)
print('Open: http://127.0.0.1:8766/' + bundle.name + '/index.html')
PYCODE
python3 -m http.server 8766 --bind 127.0.0.1 --directory out/visual
```

The server runs in the foreground; Ctrl-C stops that instance. If the port is occupied, reuse an already verified loopback server or choose another loopback port and adjust the URL. Keep the complete bundle directory so finding pages and evidence links resolve. The tested browser route is localhost; don't bypass a browser policy that rejects local-file URLs.

# Client nine-step narrative

1. Coupon: learn the same contract/validate pattern on fully specified synthetic geometry.
2. Client B.Cu: supplied back copper and bottom mask openings. The two panes show the same copper; the right adds opening boundaries.
3. Client F.Cu: front copper and openings; top's 304 zero-width warnings keep strict acceptance unestablished.
4. Bounded operation: define R140.1, its dependent trace, fixed opening, protected R140.2 and permitted region. The current display uses accepted geometry here to illustrate roles; it is not the immediate chronological input to step 5.
5. Challenge: a separate deliberate +0.35 mm offset creates the alignment failure. The original client source was already aligned.
6. Candidate: recorded execution restores alignment and passes nine declared local checks; output equals original source bytes.
7. Open control: a missing trace segment breaks continuity. Pink/red highlights copper present in the accepted reference but absent from this control; read it as missing copper, not a forbidden region.
8. Bridge control: extra copper toward protected geometry fails separation and protected-object preservation. The highlight marks the added offending copper.
9. Boundary: restore the accepted result and state the local, same-layer limits.

# Overlay meanings

Operation roles: yellow target, blue dependent trace, purple protected copper. The blue trace endpoint may adjust with the pad; its far anchor is fixed. A separately toggled dashed expected-link edge expresses a required relationship, not a routed copper track. Mask outlines show coating openings. Green B.Cu/yellow F.Cu are display colors. A selection ring is not proof of a drilled hole.

Processing and Storage views describe their recorded native datasets, not a new VME-WREN native import. Browser controls change presentation only. REPLAY means recorded execution; the included narrated montage is not live editing. A snapshot verifier PASS confirms stored-file consistency, not current live sources or manufacturing approval.
