import AppKit
import WebKit

extension ViewerHost {
    func runPhaseNavigationSmoke(folder: URL) {
        Task {
            let originalWindow = window
            let originalWeb = web
            do {
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                @MainActor func js(_ source: String) async throws -> Any? {
                    try await web.callAsyncJavaScript(source, arguments: [:], in: nil, contentWorld: .page)
                }
                @MainActor func waitFor(_ phase: String) async throws {
                    for _ in 0..<240 {
                        if try await js("return linkedPhase?.phase==='\(phase)' && !$('phase-navigation').disabled && !!bundle?.boardGrowth") as? Bool == true { return }
                        try await Task.sleep(for: .milliseconds(250))
                    }
                    throw NSError(domain: "PhaseNavigationSmoke", code: 1,
                        userInfo: [NSLocalizedDescriptionKey: "Saved phase did not open: " + phase])
                }
                @MainActor func capture(_ name: String) async throws {
                    let image = try await web.takeSnapshot(configuration: nil)
                    if let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff),
                       let png = bitmap.representation(using: .png, properties: [:]) {
                        try png.write(to: folder.appendingPathComponent(name + ".png"))
                    }
                }
                try await waitFor("large_copper")
                _ = try await js("""
                window.phaseSmokeChecks=[];window.phaseSmokeMessages=[];
                window.phaseCheck=(name,ok)=>{phaseSmokeChecks.push({name,pass:!!ok});if(!ok)throw Error(name)};
                phaseCheck('cleanup opens without automatic transition',isCleanup()&&!isT04()&&!t04Data());
                phaseCheck('central button opens saved T04',$('phase-navigation').textContent==='Open T04 result →'&&!$('cleanup-run').hidden);
                const originalPost=post;post=value=>{phaseSmokeMessages.push(value.action);originalPost(value)};
                $('cleanup-filter').value='unresolved';$('cleanup-view').value='original';updateCleanup();focusCleanup();
                window.cleanupViewBefore=JSON.stringify({camera,place:cleanupSelection,filter:$('cleanup-filter').value,view:$('cleanup-view').value});
                """)
                try await capture("cleanup-before-switch")
                _ = try await js("$('phase-navigation').click()")
                try await waitFor("t04")
                _ = try await js("""
                phaseCheck('T04 uses its own workspace and controls',isT04()&&!!t04Data()&&!cleanupData()&&$('cleanup-controls').hidden&&!$('t04-controls').hidden);
                phaseCheck('back button available',$('phase-navigation').textContent==='← Back to trimming');
                phaseCheck('T04 stays grey',[...document.querySelectorAll('[data-board-growth]')].filter(p=>p.dataset.boardGrowth!=='removed').every(p=>p.getAttribute('fill')==='#bac8ce'));
                for(const mode of ['comparison','corrected']){
                  $('t04-view').value=mode;$('t04-additions').checked=true;draw();focusT04();
                  const edges=[...document.querySelectorAll('[data-board-growth=added]')];
                  phaseCheck(mode+' shows green added edges',edges.length>0&&edges.every(p=>p.getAttribute('stroke')==='#42f599'));
                  phaseCheck(mode+' shows addition legend',!$('growth-legend').querySelectorAll('.legend-colors span')[1].hidden);
                  $('t04-additions').checked=false;draw();
                  phaseCheck(mode+' can hide added edges',[...document.querySelectorAll('[data-board-growth=added]')].every(p=>p.getAttribute('stroke')==='none'));
                }
                $('t04-view').value='comparison';$('t04-additions').checked=true;draw();focusT04();
                window.t04ViewBefore=JSON.stringify({camera,place:t04Selection,filter:$('t04-filter').value,view:$('t04-view').value});
                """)
                try await capture("t04-after-switch")
                _ = try await js("$('phase-navigation').click()")
                try await waitFor("large_copper")
                _ = try await js("""
                phaseCheck('cleanup camera selection and controls restored',cleanupViewBefore===JSON.stringify({camera,place:cleanupSelection,filter:$('cleanup-filter').value,view:$('cleanup-view').value}));
                phaseCheck('cleanup excludes T04 traces',!t04Data()&&boardGrowth().parts.every(p=>p.attributes.copper_object?.length===1));
                phaseCheck('cleanup stays grey',[...document.querySelectorAll('[data-board-growth]')].every(p=>p.getAttribute('fill')==='#bac8ce'));
                """)
                try await capture("cleanup-returned")
                _ = try await js("$('phase-navigation').click()")
                try await waitFor("t04")
                let result = try await js("""
                phaseCheck('T04 camera selection and controls restored',t04ViewBefore===JSON.stringify({camera,place:t04Selection,filter:$('t04-filter').value,view:$('t04-view').value}));
                phaseCheck('green highlights survive phase round trip',[...document.querySelectorAll('[data-board-growth=added]')].some(p=>p.getAttribute('stroke')==='#42f599'));
                phaseCheck('three explicit phase clicks',phaseSmokeMessages.filter(a=>a==='openSavedPhase').length===3);
                phaseCheck('zero treatment execution requests',!phaseSmokeMessages.some(a=>['runCopperPipeline','runLargeCopper','runT04','open'].includes(a)));
                return {checks:phaseSmokeChecks,actions:phaseSmokeMessages,revision:scene().revision,phase:linkedPhase.phase,treatmentRequests:0};
                """)
                guard window === originalWindow, web === originalWeb else {
                    throw NSError(domain: "PhaseNavigationSmoke", code: 2,
                        userInfo: [NSLocalizedDescriptionKey: "Native window or web view was replaced"])
                }
                var receipt = result as? [String: Any] ?? [:]
                receipt["sameNativeWindow"] = true; receipt["sameWebView"] = true
                try JSONSerialization.data(withJSONObject: receipt, options: [.prettyPrinted, .sortedKeys])
                    .write(to: folder.appendingPathComponent("phase-navigation-ui.json"))
                try await capture("t04-returned")
            } catch {
                try? Data(String(describing: error).utf8).write(to: folder.appendingPathComponent("PHASE_NAVIGATION_FAILED.txt"))
            }
        }
    }
}
