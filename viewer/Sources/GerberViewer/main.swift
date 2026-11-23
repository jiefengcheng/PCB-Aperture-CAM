import AppKit
import WebKit
import SwiftUI
import ViewerCore

@MainActor
final class ViewerHost: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var timer: Timer?
    var workspace: URL!
    var repository: URL!
    var workRoot: URL!
    var portable = false
    var portableStorage: PortableWorkspaceGuard?
    var workerEnvironment: [String: String] = [:]
    var loaded: LoadedRevision?
    var pageReady = false
    var loading = false
    var lastManifestDigest: String?
    var displayReadStarted: ContinuousClock.Instant?
    var lastExplanationKey: String?
    var lastPresentationKey: String?
    var loadingPresentation = false
    var importing = false
    var cleanupBusy = false
    var cleanupJob: URL?
    var smokeStarted = false
    var modelTask: Task<Void, Never>?
    var traceBusy = false
    var pendingTrace: (Snapshot, SceneObject)?
    var routePresentations: [String: RoutePresentation] = [:]
    var initialSelection: [String: String]?
    func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            portable = Bundle.main.object(forInfoDictionaryKey: "CleanupPortable") as? Bool == true
            func argument(_ name: String) throws -> String {
                let args = CommandLine.arguments
                if let index = args.lastIndex(of: name), index + 1 < args.count { return args[index + 1] }
                let key = name == "--workspace" ? "ViewerWorkspace" : "ViewerRepository"
                guard let value = Bundle.main.object(forInfoDictionaryKey: key) as? String else { throw ABIError.invalid("Launch through tools/Start_Gerber_Viewer.command") }
                return value
            }
            if portable {
                guard try initializePortable() else { return }
            } else {
                workspace = URL(fileURLWithPath: try argument("--workspace")).resolvingSymlinksInPath()
                repository = URL(fileURLWithPath: try argument("--repository")).resolvingSymlinksInPath()
                workRoot = repository.appendingPathComponent("out/lacie_work").resolvingSymlinksInPath()
            }
            guard FileManager.default.fileExists(atPath: workspace.path),
                  workspace.path.hasPrefix(workRoot.path + "/") else { throw ABIError.invalid("Viewer requires its explicitly prepared workspace") }
            try verifyStorage()
            if let data = try? Data(contentsOf: workspace.appendingPathComponent("outbox/selection.json")),
               let saved = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let revision = saved["revision"] as? String,
               let object = saved["object"] as? [String: Any], let id = object["id"] as? String {
                initialSelection = ["id": id, "revision": revision]
            }
            try FileManager.default.createDirectory(at: workspace.appendingPathComponent("tmp"), withIntermediateDirectories: true)
            let controller = WKUserContentController()
            controller.add(self, name: "viewer")
            let config = WKWebViewConfiguration(); config.userContentController = controller
            web = WKWebView(frame: .zero, configuration: config)
            web.navigationDelegate = self
            window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 820), styleMask: [.titled,.closable,.miniaturizable,.resizable], backing: .buffered, defer: false)
            window.title = "Gerber Viewer"; window.minSize = NSSize(width: 760, height: 520)
            window.contentView = NSHostingView(rootView: CanvasHost(web: web))
            window.center(); window.makeKeyAndOrderFront(nil)
            let menu = NSMenu(); let item = NSMenuItem(); menu.addItem(item)
            let appMenu = NSMenu(); appMenu.addItem(withTitle: "Quit Gerber Viewer", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"); item.submenu = appMenu
            NSApplication.shared.mainMenu = menu
            guard let url = Bundle.module.url(forResource: "canvas", withExtension: "html") else { throw ABIError.invalid("Missing canvas resource") }
            web.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
            timer = Timer.scheduledTimer(withTimeInterval: 0.7, repeats: true) { [weak self] _ in Task { @MainActor in self?.poll() } }
            NSApp.activate(ignoringOtherApps: true)
        } catch { fatalDialog(error.localizedDescription) }
    }
    func initializePortable() throws -> Bool {
        guard let resources = Bundle.main.resourceURL, let frameworks = Bundle.main.privateFrameworksURL else {
            throw ABIError.invalid("Portable runtime missing")
        }
        repository = resources.appendingPathComponent("payload").resolvingSymlinksInPath()
        let args = CommandLine.arguments
        let chosen: URL
        if let index = args.firstIndex(of: "--work-root"), index + 1 < args.count {
            chosen = URL(fileURLWithPath: args[index+1])
        } else {
            let picker = NSOpenPanel(); picker.canChooseFiles = false; picker.canChooseDirectories = true
            picker.canCreateDirectories = true; picker.allowsMultipleSelection = false
            picker.message = "Choose an APFS work folder with at least 5 GiB free. Jobs, caches and saved results stay here."
            picker.prompt = "Use work folder"
            NSApp.activate(ignoringOtherApps: true)
            guard picker.runModal() == .OK, let url = picker.url else { NSApp.terminate(nil); return false }
            chosen = url
        }
        let home = frameworks.appendingPathComponent("Python.framework/Versions/3.14")
        workerEnvironment = ProcessInfo.processInfo.environment
        workerEnvironment.removeValue(forKey: "__PYVENV_LAUNCHER__")
        workerEnvironment["PYTHONHOME"] = home.path
        workerEnvironment["PYTHONPATH"] = repository.path
        workerEnvironment["PYTHONNOUSERSITE"] = "1"
        workerEnvironment["PYTHONDONTWRITEBYTECODE"] = "1"
        let process = Process(); process.executableURL = repository.appendingPathComponent(".venv/bin/python")
        process.currentDirectoryURL = repository
        process.arguments = ["-B", "tools/portable_cleanup.py", "--workspace", chosen.path, "init"]
        process.environment = workerEnvironment
        let output = Pipe(), errors = Pipe(); process.standardOutput = output; process.standardError = errors
        try process.run()
        let data = output.fileHandleForReading.readDataToEndOfFile(); process.waitUntilExit()
        guard process.terminationStatus == 0,
              let value = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let path = value["workspace"] as? String else {
            throw ABIError.invalid("Workspace setup stopped: " + String(decoding: errors.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self))
        }
        workRoot = URL(fileURLWithPath: path).resolvingSymlinksInPath()
        workerEnvironment["PCB_CLEANUP_WORKSPACE"] = path
        workerEnvironment["TMPDIR"] = workRoot.appendingPathComponent("tmp").path
        if let index = args.firstIndex(of: "--workspace"), index + 1 < args.count {
            workspace = URL(fileURLWithPath: args[index+1]).resolvingSymlinksInPath()
        } else {
            workspace = workRoot.appendingPathComponent("native_sessions/" + UUID().uuidString)
            try FileManager.default.createDirectory(at: workspace, withIntermediateDirectories: true)
        }
        return true
    }
    func verifyStorage() throws {
        let root = workRoot!
        if portable {
            if portableStorage == nil { portableStorage = try PortableWorkspaceGuard(root: root) }
            try portableStorage!.verify()
            return
        }
        let data = try Data(contentsOf: root.appendingPathComponent("STORAGE_IDENTITY.json"))
        let identity = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        guard identity?["lacie_volume_uuid"] as? String == "6D461CE3-1544-4670-BA1D-BE4DA490D97E" else { throw ABIError.invalid("LaCie storage identity mismatch") }
        // An unmounted directory must never become an internal fallback.
        let values = try root.resourceValues(forKeys: [.volumeURLKey])
        guard values.volume?.standardizedFileURL.path == root.standardizedFileURL.path else { throw ABIError.invalid("LaCie workspace is not mounted") }
    }
    func fatalDialog(_ message: String) { let alert = NSAlert(); alert.messageText = "Gerber Viewer"; alert.informativeText = message; alert.runModal(); NSApp.terminate(nil) }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { pageReady = true; if portable { send("configurePortableCleanup", "") }; if CommandLine.arguments.contains("--live") { send("configureLive", "") }; poll() }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction) async -> WKNavigationActionPolicy {
        navigationAction.navigationType == .other && navigationAction.request.url?.isFileURL == true ? .allow : .cancel
    }
    func send(_ function: String, _ value: Any) {
        guard pageReady else { return }
        Task {
            do { _ = try await web.callAsyncJavaScript("window[fn](value)", arguments: ["fn": function, "value": value], in: nil, contentWorld: .page) }
            catch { NSLog("Canvas error: %@", error.localizedDescription) }
        }
    }
    func poll() {
        guard pageReady, !loading else { return }
        do { try verifyStorage() } catch { send("viewerError", error.localizedDescription); return }
        if cleanupBusy, let job = cleanupJob,
           let data = try? Data(contentsOf: job.appendingPathComponent("PROGRESS.json")),
           let progress = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            let state = progress["status"] as? String ?? "Working"
            let phase = progress["phase"] as? String ?? (state.hasPrefix("COMPLETED") ? "preparing saved display" : state)
            let count = (progress["completed"] as? Int).map { " · \($0)/\(progress["candidates"] as? Int ?? 0)" } ?? ""
            send("receiveCleanupStatus", ["busy": true, "text": "Large copper: " + phase + count])
        }
        pollExplanation()
        guard FileManager.default.fileExists(atPath: workspace.appendingPathComponent("current.json").path) else { return }
        if let data = try? Data(contentsOf: workspace.appendingPathComponent("current.json")), SnapshotReader.digest(data) == lastManifestDigest, loaded != nil {
            pollBoardGrowth()
            return
        }
        loading = true
        displayReadStarted = ContinuousClock().now
        let root = workspace!
        Task {
            do {
                let next = try await Task.detached { try SnapshotReader.read(workspace: root) }.value
                lastManifestDigest = next.manifestDigest
                if next.digest != loaded?.digest {
                    let encoder = JSONEncoder()
                    let current = try JSONSerialization.jsonObject(with: encoder.encode(next.current))
                    let previous: Any = try next.previous.map { try JSONSerialization.jsonObject(with: encoder.encode($0)) } ?? NSNull()
                    var value: [String: Any] = ["current": current, "previous": previous]
                    var presentationKey: String?
                    let presentation = root.appendingPathComponent("presentations/" + next.digest + ".json")
                    if FileManager.default.fileExists(atPath: presentation.path) {
                        let stamp = try presentation.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey])
                        if let date = stamp.contentModificationDate, let size = stamp.fileSize {
                            presentationKey = next.digest + ":" + String(date.timeIntervalSince1970) + ":" + String(size)
                        }
                        let growth = try await Task.detached {
                            try BoardGrowthReader.read(presentation, scene: next.current, digest: next.digest)
                        }.value
                        value["boardGrowth"] = try JSONSerialization.jsonObject(with: encoder.encode(growth))
                    }
                    loaded = next
                    lastPresentationKey = presentationKey
                    if let restore = initialSelection, restore["revision"] == next.current.revision {
                        value["restoreSelection"] = restore
                    }
                    initialSelection = nil
                    send("receiveRevision", value)
                    runSmokeIfRequested()
                } else { send("clearABIError", "") }
            } catch { send("viewerError", "Update rejected; retaining displayed revision. " + error.localizedDescription) }
            loading = false
        }
    }
    func pollBoardGrowth() {
        guard !loadingPresentation, let current = loaded else { return }
        let url = workspace.appendingPathComponent("presentations/" + current.digest + ".json")
        guard let values = try? url.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey]),
              let date = values.contentModificationDate, let size = values.fileSize else { return }
        let key = current.digest + ":" + String(date.timeIntervalSince1970) + ":" + String(size)
        guard key != lastPresentationKey else { return }
        loadingPresentation = true
        Task {
            defer { loadingPresentation = false }
            do {
                let growth = try await Task.detached {
                    try BoardGrowthReader.read(url, scene: current.current, digest: current.digest)
                }.value
                guard loaded?.digest == current.digest else { return }
                let value = try JSONSerialization.jsonObject(with: JSONEncoder().encode(growth))
                lastPresentationKey = key
                send("receiveBoardGrowth", value)
            } catch {
                lastPresentationKey = key
                send("viewerError", "Comparison update rejected; retaining displayed artwork. " + error.localizedDescription)
            }
        }
    }
    func pollExplanation() {
        guard let loaded else { return }
        let response = workspace.appendingPathComponent("inbox/explanation.json")
        let selectionURL = workspace.appendingPathComponent("outbox/selection.json")
        guard let size = try? response.resourceValues(forKeys: [.fileSizeKey]).fileSize, size <= 2 * 1024 * 1024,
              let body = try? Data(contentsOf: response), let selectedData = try? Data(contentsOf: selectionURL),
              let selection = try? JSONSerialization.jsonObject(with: selectedData) as? [String: Any],
              let revision = selection["revision"] as? String,
              let object = selection["object"] as? [String: Any], let id = object["id"] as? String else { return }
        let key = SnapshotReader.digest(body + selectedData)
        guard key != lastExplanationKey else { return }
        lastExplanationKey = key
        let scene = revision == loaded.current.revision ? loaded.current : loaded.previous
        guard let scene, scene.revision == revision else { return }
        do {
            let explanation = try ExplanationReader.decode(body, scene: scene, selectedID: id)
            rememberRoute(explanation)
            let value = try JSONSerialization.jsonObject(with: JSONEncoder().encode(explanation))
            send("receiveExplanation", value)
        } catch { NSLog("Explanation rejected: %@", error.localizedDescription) }
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: String], let action = body["action"] else { return }
        if action == "open" { if !portable { openGerbers() }; return }
        if action == "runLargeCopper" { runLargeCopper(); return }
        if action == "modelStatus" {
            Task { send("modelResult", await AppleViewerProvider().availability()) }; return
        }
        if action == "displayed", let revision = body["revision"], let loaded, revision == loaded.current.revision {
            do {
                try verifyStorage()
                let folder = workspace.appendingPathComponent("outbox")
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                var ack: [String: Any] = ["schema": 1, "status": "DISPLAY_DOM_UPDATED", "job": loaded.current.job, "revision": revision, "payloadSHA256": loaded.digest, "presentation": body["presentation"] ?? "OBJECT_ARTWORK", "growthParts": body["growthParts"] ?? "0", "timestamp": ISO8601DateFormatter().string(from: Date())]
                if let started = displayReadStarted {
                    let duration = started.duration(to: ContinuousClock().now).components
                    ack["native_snapshot_read_to_dom_seconds"] = Double(duration.seconds) + Double(duration.attoseconds) / 1e18
                }
                try JSONSerialization.data(withJSONObject: ack, options: [.sortedKeys]).write(to: folder.appendingPathComponent("display.json"), options: .atomic)
            } catch { send("viewerError", error.localizedDescription) }
            return
        }
        if action == "clearSelection", let revision = body["revision"], let loaded {
            pendingTrace = nil
            let scene = revision == loaded.current.revision ? loaded.current : loaded.previous
            guard let scene, scene.revision == revision else { return }
            do { try writeSelection(scene: scene, object: nil) }
            catch { send("viewerError", error.localizedDescription) }
            return
        }
        guard let id = body["id"], let revision = body["revision"], let loaded else { return }
        let scene = revision == loaded.current.revision ? loaded.current : loaded.previous
        guard let scene, scene.revision == revision, let object = scene.objects.first(where: { $0.id == id }) else { return }
        do {
            let objectData = try JSONEncoder().encode(object)
            if action == "select" {
                try writeSelection(scene: scene, object: object, mode: body["mode"] ?? "route")
                queueTraceComparison(scene: scene, object: object)
            } else if action == "routeResolved" || action == "selectionMode" {
                try writeSelection(scene: scene, object: object, mode: body["mode"] ?? "route")
            } else if action == "explain" {
                guard modelTask == nil else { return }
                send("modelResult", "Explaining selected record…")
                modelTask = Task {
                    defer { modelTask = nil }
                    do { send("modelResult", try await AppleViewerProvider().explain(selectionJSON: String(decoding: objectData, as: UTF8.self))) }
                    catch { send("modelResult", "Model unavailable or request failed: " + error.localizedDescription) }
                }
            }
        } catch { send("viewerError", error.localizedDescription) }
    }
    func rememberRoute(_ answer: ViewerExplanation) {
        guard let route = answer.route else { return }
        routePresentations[answer.revision + ":" + route.routeID] = route
        if routePresentations.count > 8 {
            for key in routePresentations.keys.sorted() where key != answer.revision + ":" + route.routeID {
                routePresentations.removeValue(forKey: key)
                if routePresentations.count <= 8 { break }
            }
        }
    }
    func writeSelection(scene: Snapshot, object: SceneObject?, mode: String = "route") throws {
        try verifyStorage()
        let value: Any = try object.map { try JSONSerialization.jsonObject(with: JSONEncoder().encode($0)) } ?? NSNull()
        var selection: [String: Any] = ["schema": 1, "job": scene.job, "revision": scene.revision, "object": value,
                                      "selectionMode": mode == "segment" ? "segment" : "route",
                                      "timestamp": ISO8601DateFormatter().string(from: Date())]
        if let object, let route = routePresentations.values.first(where: {
            $0.job == scene.job && $0.revision == scene.revision && $0.members.contains(where: { $0.objectID == object.id })
        }) {
            selection["route"] = ["routeID": route.routeID, "bindingSHA256": route.bindingSHA256,
                                  "catalogueSHA256": route.catalogueSHA256,
                                  "memberSourceIDs": route.members.map(\.sourceID)]
        }
        let folder = workspace.appendingPathComponent("outbox")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        try JSONSerialization.data(withJSONObject: selection, options: [.sortedKeys]).write(to: folder.appendingPathComponent("selection.json"), options: .atomic)
    }
    func queueTraceComparison(scene: Snapshot, object: SceneObject) {
        if portable { return }
        guard FileManager.default.fileExists(atPath: workspace.deletingLastPathComponent().appendingPathComponent("connection.json").path) else { return }
        pendingTrace = (scene, object)
        send("receiveTraceStatus", ["revision": scene.revision, "objectID": object.id, "text": "Reading retained source and T04 geometry…"])
        runNextTraceComparison()
    }
    func runNextTraceComparison() {
        guard !traceBusy, let (scene, object) = pendingTrace else { return }
        pendingTrace = nil; traceBusy = true
        let repo = repository!, root = workspace!
        Task {
            let result = await Task.detached { () -> (Data?, String?) in
                do {
                    let folder = root.appendingPathComponent("trace-requests")
                    try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                    let stem = UUID().uuidString
                    let request = folder.appendingPathComponent(stem + ".request.json")
                    let response = folder.appendingPathComponent(stem + ".response.json")
                    let log = folder.appendingPathComponent(stem + ".log")
                    let value: [String: Any] = ["job": scene.job, "revision": scene.revision,
                                               "object": try JSONSerialization.jsonObject(with: JSONEncoder().encode(object))]
                    try JSONSerialization.data(withJSONObject: value).write(to: request, options: .atomic)
                    let process = Process(); process.executableURL = repo.appendingPathComponent(".venv/bin/python")
                    process.currentDirectoryURL = repo
                    process.arguments = ["-B", "tools/viewer_trace.py", "--workspace", root.path,
                                         "--request", request.path, "--response", response.path]
                    var env = ProcessInfo.processInfo.environment
                    env["PYTHONDONTWRITEBYTECODE"] = "1"; env["TMPDIR"] = root.appendingPathComponent("tmp").path
                    process.environment = env
                    FileManager.default.createFile(atPath: log.path, contents: nil)
                    let output = try FileHandle(forWritingTo: log); defer { try? output.close() }
                    process.standardOutput = output; process.standardError = output
                    try process.run(); process.waitUntilExit()
                    guard process.terminationStatus == 0 else { return (nil, "Comparison unavailable; retained evidence: " + log.path) }
                    // Size and identity validation uses the same reader as chat responses.
                    let answer = try ExplanationReader.read(response, scene: scene, selectedID: object.id)
                    return (try JSONEncoder().encode(answer), nil)
                } catch { return (nil, "Comparison unavailable: " + error.localizedDescription) }
            }.value
            if let data = result.0, let value = try? JSONSerialization.jsonObject(with: data) {
                if let answer = try? JSONDecoder().decode(ViewerExplanation.self, from: data) { rememberRoute(answer) }
                send("receiveTraceComparison", value)
            } else {
                send("receiveTraceStatus", ["revision": scene.revision, "objectID": object.id, "text": result.1 ?? "Comparison unavailable"])
            }
            traceBusy = false; runNextTraceComparison()
        }
    }
    func runSmokeIfRequested() {
        let args = CommandLine.arguments
        guard !smokeStarted, let i = args.firstIndex(of: "--smoke-report"), i + 1 < args.count else { return }
        smokeStarted = true
        let folder = URL(fileURLWithPath: args[i + 1]).resolvingSymlinksInPath()
        guard folder.path.hasPrefix(workRoot.path + "/") else { return }
        if args.contains("--cleanup-smoke") { runCleanupSmoke(folder: folder); return }
        if let ri = args.firstIndex(of: "--route-smoke-response"), ri + 1 < args.count,
           let si = args.firstIndex(of: "--route-smoke-source"), si + 1 < args.count {
            runRouteSmoke(folder: folder, response: URL(fileURLWithPath: args[ri+1]), source: args[si+1])
            return
        }
        Task {
            do {
                try await Task.sleep(for: .milliseconds(400))
                let result = try await web.callAsyncJavaScript("""
                const checks=[];const check=(name,ok)=>{checks.push({name,pass:!!ok});if(!ok)throw Error(name)};
                check('revision received',!!bundle && !!scene());
                check('all current objects drawn',document.querySelectorAll('.shape').length===scene().objects.length);
                const cameraBefore=JSON.stringify(camera);
                const copy=JSON.parse(JSON.stringify(bundle));copy.current.revision+='-smoke';
                window.receiveRevision(copy);check('viewport preserved',JSON.stringify(camera)===cameraBefore);
                window.receiveRevision(value);check('snapshot restored',scene().revision===value.current.revision);
                const layer=scene().objects[0].layer, checkbox=document.querySelector('#layers input');
                checkbox.click();check('layer visibility toggles',!visible.has(layer));checkbox.click();
                document.getElementById('changes').checked=true;draw();check('change overlay enabled',document.getElementById('changes').checked);
                if(bundle.previous&&bundle.previous.objects.some((o,i)=>o.path!==scene().objects[i]?.path)){check('actual changed paths drawn',!!document.querySelector('#board path[stroke=\"#49dfba\"]'));}
                if(bundle.previous){document.getElementById('previous').click();check('previous revision',which==='previous');document.getElementById('current').click();}
                document.getElementById('fit-change').click();check('fit change',JSON.stringify(camera)===JSON.stringify(padded(scene().affected)));
                const rect=svg.getBoundingClientRect(),scale=Math.min(rect.width/camera.width,rect.height/camera.height),vw=rect.width/scale,vh=rect.height/scale,left=camera.x-(vw-camera.width)/2,top=camera.y-(vh-camera.height)/2;
                const outside=scene().objects.find(o=>o.bounds.x>left+vw||o.bounds.x+o.bounds.width<left||o.bounds.y>top+vh||o.bounds.y+o.bounds.height<top);
                if(outside)check('offscreen geometry culled',!drawnPaths.has(outside.id));
                const object=scene().objects[0], path=[...document.querySelectorAll('.shape')].find(p=>p.dataset.object===object.id);
                const box=path.getBBox();let inside=null;
                for(let x=1;x<20&&!inside;x++)for(let y=1;y<20&&!inside;y++){const p=new DOMPoint(box.x+box.width*x/20,box.y+box.height*y/20);if(path.isPointInFill(p))inside=p;}
                check('filled artwork pick point',!!inside);
                const screen=inside.matrixTransform(svg.getScreenCTM());
                drag={moved:false};svg.dispatchEvent(new PointerEvent('pointerup',{clientX:screen.x,clientY:screen.y,bubbles:true}));
                check('shape click selects object',!!selected);
                const screen2=inside.matrixTransform(svg.getScreenCTM());
                const hits=hitObjects({clientX:screen2.x,clientY:screen2.y});
                if(hits.length>1){const first=selected;drag={moved:false};svg.dispatchEvent(new PointerEvent('pointerup',{clientX:screen2.x,clientY:screen2.y,bubbles:true}));check('overlap cycling',selected!==first);}
                check('inspector populated',document.querySelector('#properties').children.length===4);
                if((object.path.match(/M /g)||[]).length>1){const center=new DOMPoint(box.x+box.width/2,box.y+box.height/2).matrixTransform(svg.getScreenCTM());check('aperture hole not selectable',hitObjects({clientX:center.x,clientY:center.y}).length===0);}
                const selectedObject=scene().objects.find(o=>o.id===selected);
                const answer={revision:scene().revision,objectID:selected,author:'UI fixture',text:'Source comparison fixture',comparison:{original:{path:selectedObject.path,bounds:selectedObject.bounds},added:{path:selectedObject.path,bounds:selectedObject.bounds},summary:'Width fixture',snapshotNote:'Pinned snapshot'}};
                window.receiveExplanation(answer);check('source and growth paths rendered',document.querySelectorAll('[data-comparison]').length===2);
                check('comparison legend visible',!document.getElementById('growth-legend').hidden);
                window.receiveTraceComparison({...answer,author:'Retained T04 geometry',text:'automatic'});
                check('automatic comparison preserves chat answer',document.getElementById('model-output').textContent.includes('Source comparison fixture'));
                clearExplanation();window.receiveTraceComparison({...answer,author:'Retained T04 geometry',text:'automatic'});
                check('selection receives automatic comparison',!!comparison());
                window.receiveExplanation({revision:answer.revision,objectID:answer.objectID,author:'UI fixture',text:'Source comparison fixture'});
                check('chat text retains automatic growth',!!comparison());
                window.receiveTraceComparison({...answer,objectID:'another-object',text:'wrong selection'});
                check('late selection response ignored',!document.getElementById('model-output').textContent.includes('wrong selection'));
                const pickBefore=hitObjects({clientX:screen2.x,clientY:screen2.y});check('overlay preserves picking',JSON.stringify(pickBefore)===JSON.stringify(hits));
                document.getElementById('growth-overlay').click();check('growth toggle removes overlay',document.querySelectorAll('[data-comparison]').length===0);
                document.getElementById('growth-overlay').click();document.getElementById('fit-selection').click();
                check('fit selected source',JSON.stringify(camera)===JSON.stringify(padded(selectedObject.bounds)));
                window.receiveExplanation({...answer,revision:'stale',text:'wrong'});check('stale answer ignored',!document.getElementById('model-output').textContent.includes('wrong'));
                document.getElementById('current').click();check('selection change clears explanation',!explanation&&document.querySelectorAll('[data-comparison]').length===0);
                selected=selectedObject.id;inspect();window.receiveExplanation(answer);
                document.getElementById('inspector').hidden=false;draw();
                return {checks,revision:scene().revision,selected,objects:scene().objects.length,viewBox:svg.getAttribute('viewBox')};
                """, arguments: ["value": ["current": try JSONSerialization.jsonObject(with: JSONEncoder().encode(loaded!.current)), "previous": try loaded!.previous.map { try JSONSerialization.jsonObject(with: JSONEncoder().encode($0)) } ?? NSNull()]], in: nil, contentWorld: .page)
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                try JSONSerialization.data(withJSONObject: result as Any, options: [.prettyPrinted, .sortedKeys]).write(to: folder.appendingPathComponent("ui-smoke.json"))
                let image = try await web.takeSnapshot(configuration: nil)
                if let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff), let png = bitmap.representation(using: .png, properties: [:]) {
                    try png.write(to: folder.appendingPathComponent("viewer.png"))
                }
            } catch {
                try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                try? Data(error.localizedDescription.utf8).write(to: folder.appendingPathComponent("ui-smoke-failed.txt"))
            }
        }
    }
    func runCleanupSmoke(folder: URL) {
        Task {
            do {
                try await Task.sleep(for: .milliseconds(500))
                let result = try await web.callAsyncJavaScript("""
                const checks=[],check=(name,ok)=>{checks.push({name,pass:!!ok});if(!ok)throw Error(name)};
                window.cleanupSmokeChecks=checks;
                check('revision-bound saved cleanup present',!!cleanupData());
                const sourcePaths=scene().objects.map(o=>o.path).join('|'),revision=scene().revision;
                const actualPost=post,messages=[];post=v=>messages.push(v);
                try {
                  $('workspace-mode').value='cleanup';$('workspace-mode').onchange();
                  check('dedicated controls',!$('cleanup-controls').hidden&&$('trace-controls').hidden&&!$('cleanup-panel').hidden&&$('inspector').hidden);
                  check('only treated copper artwork',boardGrowth().parts.length>0&&boardGrowth().parts.every(p=>p.attributes.copper_object?.length===1));
                  const boardAdditions=bundle.boardGrowth.parts.filter(p=>p.kind==='added').map(p=>p.path);
                  check('trace growth excluded',boardGrowth().parts.filter(p=>p.kind==='added').every(p=>!boardAdditions.includes(p.path)||cleanupData().cases.some(c=>c.kind==='recess'&&c.path===p.path)));
                  for(const object of cleanupData().objects){$('cleanup-object').value=object.id;$('cleanup-object').onchange();check('copper object '+object.id,boardGrowth().parts.every(p=>p.attributes.copper_object[0]===object.id));}
                  $('cleanup-object').value='all';$('cleanup-object').onchange();
                  const all=cleanupData().cases;
                  for(const c of all){cleanupSelection=c.id;$('cleanup-places').value=c.id;cleanupInfo();focusCleanup();check('place '+c.id,cleanupSelected()?.id===c.id&&$('cleanup-info').textContent.includes(c.disposition));}
                  const first=cleanupSelection;$('cleanup-next').click();$('cleanup-prev').click();check('next and previous',cleanupSelection===first);
                  for(const mode of ['original','corrected','comparison']){
                    $('cleanup-view').value=mode;draw();
                    const paths=[...document.querySelectorAll('[data-board-growth]')];
                    check(mode+' grey copper',paths.filter(p=>p.dataset.boardGrowth!=='removed'||mode!=='comparison').every(p=>p.getAttribute('fill')==='#bac8ce'));
                    check(mode+' correct partition',mode==='original'?!paths.some(p=>p.dataset.boardGrowth==='added'):mode==='corrected'?!paths.some(p=>p.dataset.boardGrowth==='removed'):true);
                  }
                  $('cleanup-ghosts').checked=false;draw();check('removal ghosts optional',!document.querySelector('[data-board-growth="removed"]'));
                  $('cleanup-ghosts').checked=true;
                  for(const filter of ['bump','recess','corrected','unresolved','ignored','circular']){$('cleanup-filter').value=filter;$('cleanup-filter').onchange();check(filter+' filter',cleanupCases().every(c=>c.kind===filter||c.status===filter||filter==='circular'&&c.boundaryKind==='circular'));}
                  $('cleanup-filter').value='all';updateCleanup();
                  $('cleanup-area').checked=false;updateCleanup();check('area rule independent',cleanupCases().every(c=>!c.rule.includes('AREA_NOISE')));$('cleanup-area').checked=true;
                  $('cleanup-shallow').checked=false;updateCleanup();check('shallow rule independent',cleanupCases().every(c=>!c.rule.includes('SHALLOW_SOURCE_EDGE')));$('cleanup-shallow').checked=true;updateCleanup();
                  const playbackCases=cleanupCases(),playbackStart=cleanupSelection;
                  if(playbackCases.length>1){
                  $('cleanup-play').click();check('play starts',cleanupTimer!==null&&$('cleanup-play').getAttribute('aria-pressed')==='true');
                  const playbackDeadline=performance.now()+10000;
                  while(cleanupSelection===playbackStart&&performance.now()<playbackDeadline)await new Promise(resolve=>setTimeout(resolve,100));
                  check('play advances saved detail',cleanupSelection===playbackCases[(playbackCases.findIndex(c=>c.id===playbackStart)+1)%playbackCases.length].id);
                  const detail=cleanupSelected().bounds;check('play fits detail',camera.x<detail.x&&camera.y<detail.y&&camera.width>detail.width);
                  $('cleanup-play').click();const pausedPlace=cleanupSelection;check('pause clears timer',cleanupTimer===null&&$('cleanup-play').getAttribute('aria-pressed')==='false');
                  await new Promise(resolve=>setTimeout(resolve,100));check('pause retains place',cleanupSelection===pausedPlace);
                  $('cleanup-play').click();$('cleanup-next').click();check('manual navigation pauses',cleanupTimer===null);
                  cleanupSelection=cleanupCases().at(-1).id;advanceCleanup();check('playback wraps filtered places',cleanupSelection===cleanupCases()[0].id);
                  $('cleanup-play').click();$('cleanup-filter').value='unresolved';$('cleanup-filter').onchange();check('filter change pauses',cleanupTimer===null);
                  }else{check('zero or one place disables playback',$('cleanup-play').disabled&&cleanupTimer===null)}
                  $('cleanup-filter').value='recess';$('cleanup-filter').onchange();if(trimOnly())check('empty list disables play',$('cleanup-play').disabled);
                  $('cleanup-filter').value='all';$('cleanup-filter').onchange();
                  if(trimOnly())check('trim only without added copper',bundle.boardGrowth.addedAreaMM2<=1e-12&&!boardGrowth().parts.some(p=>p.kind==='added'));
                  if(cleanupData().cases.some(c=>c.reviewNumber!=null)){
                    $('cleanup-filter').value='reviewed';$('cleanup-filter').onchange();
                    check('original eight review places retained',cleanupCases().length===8&&cleanupCases().every((c,i)=>c.reviewNumber===i+1));
                    for(const c of cleanupCases()){cleanupSelection=c.id;$('cleanup-places').value=c.id;cleanupInfo();focusCleanup();check('review '+c.reviewNumber+' explanation',$('cleanup-info').textContent.includes('Place '+c.reviewNumber+'/8:')&&c.sources.length>0&&c.areaMM2>0)}
                    $('cleanup-filter').value='all';$('cleanup-filter').onchange();
                  }
                  check('source geometry unchanged',revision===scene().revision&&sourcePaths===scene().objects.map(o=>o.path).join('|'));
                  check('zero treatment or selection requests',messages.length===0);
                  $('cleanup-all').click();
                } finally {post=actualPost}
                return {checks,revision,constructionSHA256:bundle.boardGrowth.constructionSHA256,sourceSHA256:bundle.boardGrowth.sourceSHA256,cases:cleanupData().cases.length,trimmed:cleanupData().cases.filter(c=>c.kind==='bump'&&c.status==='corrected').length,recesses:cleanupData().cases.filter(c=>c.kind==='recess').length,unresolved:cleanupData().cases.filter(c=>c.status==='unresolved').length,ignored:cleanupData().cases.filter(c=>c.status==='ignored').length};
                """, arguments: [:], in: nil, contentWorld: .page)
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                try JSONSerialization.data(withJSONObject: result as Any, options: [.prettyPrinted,.sortedKeys]).write(to: folder.appendingPathComponent("cleanup-ui.json"))
                for mode in ["original","corrected","comparison"] {
                    _ = try await web.callAsyncJavaScript("$('cleanup-view').value=mode;draw()", arguments: ["mode":mode], in: nil, contentWorld: .page)
                    let image = try await web.takeSnapshot(configuration: nil)
                    if let tiff=image.tiffRepresentation,let bitmap=NSBitmapImageRep(data:tiff),let png=bitmap.representation(using:.png,properties:[:]) {
                        try png.write(to:folder.appendingPathComponent("cleanup-"+mode+".png"))
                    }
                }
                for example in ["area", "recess", "shallow", "marked"] {
                    let shown = try await web.callAsyncJavaScript("""
                    $('cleanup-object').value='all';$('cleanup-filter').value='all';updateCleanup();
                    if(example==='recess'&&trimOnly())return false;
                    const chosen=cleanupCases().find(c=>c.status==='corrected'&&(example==='marked'?c.sources.some(s=>s.ordinal===2688):example==='shallow'?c.rule.includes('SHALLOW_SOURCE_EDGE'):example==='recess'?c.kind==='recess':c.rule==='AREA_NOISE'));
                    if(!chosen)return false;
                    cleanupSelection=chosen.id;$('cleanup-places').value=chosen.id;cleanupInfo();focusCleanup();
                    $('cleanup-view').value='comparison';draw();return true;
                    """, arguments:["example":example],in:nil,contentWorld:.page)
                    guard shown as? Bool == true else { continue }
                    let image=try await web.takeSnapshot(configuration:nil)
                    if let tiff=image.tiffRepresentation,let bitmap=NSBitmapImageRep(data:tiff),let png=bitmap.representation(using:.png,properties:[:]) {
                        try png.write(to:folder.appendingPathComponent("cleanup-detail-"+example+".png"))
                    }
                }
                for number in 1...8 {
                    let shown = try await web.callAsyncJavaScript("""
                    if(!cleanupData().cases.some(c=>c.reviewNumber===number))return false;
                    $('cleanup-object').value='all';$('cleanup-filter').value='reviewed';updateCleanup();
                    const chosen=cleanupCases().find(c=>c.reviewNumber===number);
                    cleanupSelection=chosen.id;$('cleanup-places').value=chosen.id;cleanupInfo();focusCleanup();
                    $('cleanup-view').value='comparison';$('cleanup-panel').scrollTop=0;draw();return true;
                    """, arguments:["number":number],in:nil,contentWorld:.page)
                    if shown as? Bool == true {
                        let image=try await web.takeSnapshot(configuration:nil)
                        if let tiff=image.tiffRepresentation,let bitmap=NSBitmapImageRep(data:tiff),let png=bitmap.representation(using:.png,properties:[:]) {
                            try png.write(to:folder.appendingPathComponent("review-place-\(number).png"))
                        }
                    }
                }
                let circularShown = try await web.callAsyncJavaScript("""
                const latest=cleanupData().cases.find(c=>c.boundaryKind==='circular'&&c.sources.some(s=>s.ordinal===14440));
                if(!latest)return false;
                $('cleanup-object').value='all';$('cleanup-filter').value='circular';updateCleanup();
                cleanupSelection=latest.id;$('cleanup-places').value=latest.id;cleanupInfo();focusCleanup();
                $('cleanup-panel').scrollTop=0;return true;
                """,arguments:[:],in:nil,contentWorld:.page)
                if circularShown as? Bool == true {
                    for mode in ["original","corrected","comparison"] {
                        _ = try await web.callAsyncJavaScript("$('cleanup-view').value=mode;draw()",arguments:["mode":mode],in:nil,contentWorld:.page)
                        let image=try await web.takeSnapshot(configuration:nil)
                        if let tiff=image.tiffRepresentation,let bitmap=NSBitmapImageRep(data:tiff),let png=bitmap.representation(using:.png,properties:[:]) {
                            try png.write(to:folder.appendingPathComponent("circular-endpoint-"+mode+".png"))
                        }
                    }
                }
            } catch {
                try? FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
                try? Data(error.localizedDescription.utf8).write(to:folder.appendingPathComponent("cleanup-ui-failed.txt"))
                if let checks=try? await web.callAsyncJavaScript("return window.cleanupSmokeChecks || []",arguments:[:],in:nil,contentWorld:.page),let data=try? JSONSerialization.data(withJSONObject:checks){try? data.write(to:folder.appendingPathComponent("cleanup-ui-partial.json"))}
            }
        }
    }
    func runRouteSmoke(folder: URL, response: URL, source: String) {
        Task {
            do {
                guard response.resolvingSymlinksInPath().path.hasPrefix(repository.appendingPathComponent("out/lacie_work").resolvingSymlinksInPath().path + "/"),
                      let loaded else { throw ABIError.invalid("Route smoke requires a retained local response") }
                // Qualify the revision actually selected by the user, including Previous.
                let candidates = [loaded.current, loaded.previous].compactMap { $0 }
                guard let answer = candidates.compactMap({ try? ExplanationReader.read(response, scene: $0, selectedID: source) }).first,
                      let scene = candidates.first(where: { $0.revision == answer.revision }) else {
                    throw ABIError.invalid("Route smoke response does not match Current or Previous")
                }
                guard answer.route != nil else { throw ABIError.invalid("Route smoke response has no maintained route") }
                rememberRoute(answer)
                try await Task.sleep(for: .milliseconds(400))
                let value = try JSONSerialization.jsonObject(with: JSONEncoder().encode(answer))
                let result = try await web.callAsyncJavaScript("""
                const checks=[],check=(name,ok)=>{checks.push({name,pass:!!ok});if(!ok)throw Error(name)};window.routeSmokeChecks=checks;
                if(scene().revision!==answer.revision)$(bundle.current.revision===answer.revision?'current':'previous').click();
                check('response matches displayed revision',answer.revision===scene().revision);
                $('selection-mode').value='route';selectObject(answer.objectID);window.receiveTraceComparison(answer);
                const r=routeView();check('maintained route selected',!!r&&r.routeID===answer.route.routeID);
                check('catalogue picking index retained',routeMembership.size===answer.routeIndex.entries.reduce((n,e)=>n+e.objectIndices.length,0));
                $('fit-selection').click();check('fit complete route',JSON.stringify(camera)===JSON.stringify(padded(r.bounds)));
                check('assembled copper filled',document.querySelector('[data-route-copper]')?.getAttribute('fill')==='#49dfba');
                check('all original members drawn',document.querySelectorAll('[data-source-centerline]').length===r.members.length);
                check('original centerlines dotted',Array.from(document.querySelectorAll('[data-source-centerline]')).every(p=>p.getAttribute('fill')==='none'&&p.getAttribute('stroke-dasharray')==='1 4'&&p.getAttribute('vector-effect')==='non-scaling-stroke'));
                check('route avoids clicked-segment overlay',document.querySelectorAll('[data-comparison]').length===0);
                check('route growth controls and legend visible',!!r.comparison&&!$('comparison-controls').hidden&&!$('growth-legend').hidden&&$('growth-title').textContent.startsWith('Selected route'));
                check('original route copper is grey',document.querySelector('[data-route-comparison=original]')?.getAttribute('fill')==='#bac8ce');
                check('added route copper has a green edge',!!document.querySelector('[data-route-comparison=added]')===!!r.comparison.added&&(!r.comparison.added||(document.querySelector('[data-route-comparison=added]').getAttribute('fill')==='#bac8ce'&&document.querySelector('[data-route-comparison=added]').getAttribute('stroke')==='#42f599')));
                check('removed route copper is distinct',!!document.querySelector('[data-route-comparison=removed]')===!!r.comparison.removed&&(!r.comparison.removed||document.querySelector('[data-route-comparison=removed]').getAttribute('fill')==='#ff87a8'));
                $('growth-overlay').click();check('growth toggle retains filled route and dotted centerlines',document.querySelectorAll('[data-route-comparison]').length===0&&!!document.querySelector('[data-route-copper]')&&document.querySelectorAll('[data-source-centerline]').length===r.members.length);$('growth-overlay').click();
                check('growth toggle restores route comparison',!!document.querySelector('[data-route-comparison=original]'));

                check('catalogue group references shown',document.querySelectorAll('[data-group-reference]').length===r.groups.length);
                check('segment picker retains complete membership',$('segment-picker').options.length===r.members.length);
                $('centerlines').click();check('centerlines toggle off',document.querySelectorAll('[data-source-centerline]').length===0);$('centerlines').click();
                $('group-references').click();check('group reference toggle off',document.querySelectorAll('[data-group-reference]').length===0);$('group-references').click();
                if(r.members.length>1){
                    const sibling=r.members.find(m=>m.objectID!==selected);$('segment-picker').value=sibling.objectID;$('segment-picker').dispatchEvent(new Event('change'));
                    check('segment drilldown keeps whole route',selected===sibling.objectID&&routeView().routeID===r.routeID);
                    check('segment drilldown retains whole-route growth',$('growth-summary').textContent===r.comparison.summary&&!!document.querySelector('[data-route-comparison=original]'));
                    const path=drawnPaths.get(sibling.objectID),box=path.getBBox();let inside=null;
                    for(let x=1;x<45&&!inside;x++)for(let y=1;y<45&&!inside;y++){const p=new DOMPoint(box.x+box.width*x/45,box.y+box.height*y/45);if(path.isPointInFill(p))inside=p;}
                    check('member copper has a pick point',!!inside);const screen=inside.matrixTransform(svg.getScreenCTM());drag={moved:false};svg.dispatchEvent(new PointerEvent('pointerup',{clientX:screen.x,clientY:screen.y,bubbles:true}));
                    check('member click selects catalogue route',routeView()?.routeID===r.routeID);
                }
                selectObject(answer.objectID);window.receiveTraceComparison(answer);
                $('selection-mode').value='segment';$('selection-mode').dispatchEvent(new Event('change'));
                check('segment mode preserves source inspection',!routeView()&&$('properties').children.length===4&&document.querySelectorAll('[data-route-copper]').length===0);
                $('fit-selection').click();check('segment fit uses clicked source',JSON.stringify(camera)===JSON.stringify(padded(scene().objects.find(o=>o.id===selected).bounds)));
                $('selection-mode').value='route';$('selection-mode').dispatchEvent(new Event('change'));$('fit-selection').click();
                const width=document.querySelector('[data-source-centerline]').getAttribute('stroke-width');camera={...camera,width:camera.width*.75,height:camera.height*.75};draw();check('dotted stroke stable while zooming',document.querySelector('[data-source-centerline]').getAttribute('stroke-width')===width);$('fit-selection').click();
                const old=routeView().bindingSHA256;window.receiveTraceComparison({...answer,revision:'stale'});check('stale route response ignored',routeView().bindingSHA256===old);
                const layer=scene().objects.find(o=>o.id===selected).layer;visible.delete(layer);draw();check('hidden layer hides route',document.querySelectorAll('[data-route-copper]').length===0);visible.add(layer);draw();
                if(bundle.previous){const saved=which;$(which==='current'?'previous':'current').click();check('revision switch clears route selection',selected===null&&!routeView());$(saved).click();selectObject(answer.objectID);window.receiveTraceComparison(answer);$('fit-selection').click();}
                $('inspector').hidden=false;draw();selectionMessage('routeResolved');
                return {checks,revision:scene().revision,selected,routeID:r.routeID,members:r.members.length,groups:r.groups,viewBox:svg.getAttribute('viewBox')};
                """, arguments: ["answer": value], in: nil, contentWorld: .page)
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                try JSONSerialization.data(withJSONObject: result as Any, options: [.prettyPrinted,.sortedKeys]).write(to: folder.appendingPathComponent("ui-route-smoke.json"))
                let args=CommandLine.arguments
                if let oi=args.firstIndex(of:"--route-smoke-other"),oi+1<args.count,
                   let other=scene.objects.first(where:{$0.id==args[oi+1]}),let index=answer.routeIndex,
                   let objectIndex=scene.objects.firstIndex(where:{$0.id==other.id}),
                   let entry=index.entries.first(where:{$0.objectIndices.contains(objectIndex)}) {
                    let started=Date()
                    _ = try await web.callAsyncJavaScript("""
                    const o=scene().objects.find(o=>o.id===id);fit(o.bounds);const path=drawnPaths.get(id),b=path.getBBox();let p=null;
                    for(let x=1;x<60&&!p;x++)for(let y=1;y<60&&!p;y++){const q=new DOMPoint(b.x+b.width*x/60,b.y+b.height*y/60);if(path.isPointInFill(q))p=q;}
                    if(!p)throw Error('Other route has no copper pick point');const s=p.matrixTransform(svg.getScreenCTM());
                    drag={moved:false};svg.dispatchEvent(new PointerEvent('pointerup',{clientX:s.x,clientY:s.y,bubbles:true}));
                    """,arguments:["id":other.id],in:nil,contentWorld:.page)
                    var arrived=false
                    for _ in 0..<60 {
                        try await Task.sleep(for:.milliseconds(200))
                        let ready=try await web.callAsyncJavaScript("return routeView()?.routeID===expected",arguments:["expected":entry.routeID],in:nil,contentWorld:.page)
                        if (ready as? Bool)==true {arrived=true;break}
                    }
                    guard arrived else {throw ABIError.invalid("Different catalogue route did not arrive through the native selection worker")}
                    let roundtrip=try await web.callAsyncJavaScript("$('fit-selection').click();return {routeID:routeView().routeID,members:routeView().members.length,selected,filled:!!document.querySelector('[data-route-copper]'),dotted:document.querySelectorAll('[data-source-centerline]').length}",arguments:[:],in:nil,contentWorld:.page)
                    try JSONSerialization.data(withJSONObject:["result":roundtrip,"elapsed_s":Date().timeIntervalSince(started),"expected":entry.routeID,"injected_route_response":false],options:[.prettyPrinted,.sortedKeys]).write(to:folder.appendingPathComponent("different-route-roundtrip.json"))
                    try await Task.sleep(for:.milliseconds(200))
                    let second=try await web.takeSnapshot(configuration:nil)
                    if let tiff=second.tiffRepresentation,let bitmap=NSBitmapImageRep(data:tiff),let png=bitmap.representation(using:.png,properties:[:]){try png.write(to:folder.appendingPathComponent("viewer-second-route.png"))}
                    _ = try await web.callAsyncJavaScript("selectObject(answer.objectID);window.receiveTraceComparison(answer);$('fit-selection').click();selectionMessage('routeResolved');",arguments:["answer":value],in:nil,contentWorld:.page)
                }
                try await Task.sleep(for: .milliseconds(250))
                let image = try await web.takeSnapshot(configuration: nil)
                if let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data:tiff), let png = bitmap.representation(using:.png,properties:[:]) {
                    try png.write(to:folder.appendingPathComponent("viewer-route.png"))
                }
            } catch {
                try? FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
                let detail = error.localizedDescription + "\n" + String(describing: (error as NSError).userInfo)
                try? Data(detail.utf8).write(to:folder.appendingPathComponent("ui-route-smoke-failed.txt"))
                if let checks = try? await web.callAsyncJavaScript("return window.routeSmokeChecks || []", arguments: [:], in: nil, contentWorld: .page),
                   let data = try? JSONSerialization.data(withJSONObject: checks, options: [.prettyPrinted,.sortedKeys]) {
                    try? data.write(to:folder.appendingPathComponent("failed-checks.json"))
                }
                if let image = try? await web.takeSnapshot(configuration: nil), let tiff = image.tiffRepresentation,
                   let bitmap = NSBitmapImageRep(data:tiff), let png = bitmap.representation(using:.png,properties:[:]) {
                    try? png.write(to:folder.appendingPathComponent("failed-viewer.png"))
                }
            }
        }
    }
    func runLargeCopper() {
        guard !cleanupBusy, !importing else { return }
        let panel = NSOpenPanel(); panel.allowsMultipleSelection = false; panel.canChooseDirectories = false
        panel.message = "Choose one Gerber source. One fixed trimming policy is applied; viewing filters do not select treatment families. Unresolved findings remain unchanged in the saved Preview."
        panel.beginSheetModal(for: window) { [weak self] response in
            guard response == .OK, let self, let source = panel.url else { return }
            self.cleanupBusy = true
            let repo = self.repository!
            let work = self.workRoot!, portable = self.portable, portableEnvironment = self.workerEnvironment
            let job = work.appendingPathComponent("large_copper_jobs/viewer-" + UUID().uuidString)
            self.cleanupJob = job
            self.send("receiveCleanupStatus", ["busy": true, "text": "Reading source and preparing copper…"])
            Task {
                let result = await Task.detached { () -> (URL?, String) in
                    do {
                        let process = Process(); process.executableURL = repo.appendingPathComponent(".venv/bin/python")
                        process.currentDirectoryURL = repo
                        process.arguments = (portable ? ["-B", "tools/portable_cleanup.py", "--workspace", work.path, "run"] : ["-B", "tools/run_large_copper.py", "run"]) + ["--source", source.path,
                                             "--output", job.path, "--prepare-display"]
                        var env = portable ? portableEnvironment : ProcessInfo.processInfo.environment
                        env["PYTHONDONTWRITEBYTECODE"] = "1"
                        env["TMPDIR"] = work.appendingPathComponent("tmp").path
                        process.environment = env
                        let log = work.appendingPathComponent("large-copper-" + UUID().uuidString + ".log")
                        FileManager.default.createFile(atPath: log.path, contents: nil)
                        let errors = try FileHandle(forWritingTo: log); defer { try? errors.close() }
                        let output = Pipe(); process.standardOutput = output; process.standardError = errors
                        try process.run()
                        let data = output.fileHandleForReading.readDataToEndOfFile(); process.waitUntilExit()
                        guard process.terminationStatus == 0,
                              let value = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                              let display = value["display"] as? [String: Any], let path = display["workspace"] as? String else {
                            return (nil, "Trimming stopped. Retained evidence: " + log.path)
                        }
                        let target = URL(fileURLWithPath: path).resolvingSymlinksInPath()
                        let fence = work.path + "/"
                        guard target.path.hasPrefix(fence) else { return (nil, "Cleanup display path rejected") }
                        return (target, "Saved trimming result · one fixed policy · review unresolved findings")
                    } catch { return (nil, error.localizedDescription) }
                }.value
                self.cleanupBusy = false; self.cleanupJob = nil
                if let target = result.0 {
                    self.workspace = target; self.loaded = nil; self.lastManifestDigest = nil
                    self.lastExplanationKey = nil; self.lastPresentationKey = nil; self.initialSelection = nil
                    self.pendingTrace = nil; self.routePresentations.removeAll()
                    self.poll()
                }
                self.send("receiveCleanupStatus", ["busy": false, "text": result.1])
            }
        }
    }
    func openGerbers() {
        guard !importing else { return }
        let panel = NSOpenPanel(); panel.allowsMultipleSelection = true; panel.canChooseDirectories = false
        panel.message = "Choose Gerber layers. Import is read-only and creates a Preview snapshot."
        panel.beginSheetModal(for: window) { [weak self] response in
            guard response == .OK, let self else { return }
            self.importing = true
            self.send("importStatus", "Parsing selected Gerbers…")
            let files = panel.urls.map(\.path)
            let repo = self.repository!, root = self.workspace!
            Task {
                let result = await Task.detached { () -> String? in
                    do {
                        let process = Process()
                        process.executableURL = repo.appendingPathComponent(".venv/bin/python")
                        process.currentDirectoryURL = repo
                        process.arguments = ["-B", "tools/viewer_publish.py", "--workspace", root.path, "--slice", "Manual Gerber import"] + files.flatMap { ["--gerber", $0] }
                        var env = ProcessInfo.processInfo.environment
                        env["PYTHONDONTWRITEBYTECODE"] = "1"; env["TMPDIR"] = root.appendingPathComponent("tmp").path
                        process.environment = env
                        let log = root.appendingPathComponent("import-" + UUID().uuidString + ".log")
                        FileManager.default.createFile(atPath: log.path, contents: nil)
                        let output = try FileHandle(forWritingTo: log); defer { try? output.close() }
                        process.standardOutput = output; process.standardError = output
                        try process.run(); process.waitUntilExit()
                        return process.terminationStatus == 0 ? nil : "Import rejected. Evidence: " + log.path
                    } catch { return error.localizedDescription }
                }.value
                self.importing = false
                self.send("importStatus", "")
                if let result { self.send("viewerError", result) } else { self.poll() }
            }
        }
    }
}
struct CanvasHost: NSViewRepresentable {
    let web: WKWebView
    func makeNSView(context: Context) -> WKWebView { web }
    func updateNSView(_ nsView: WKWebView, context: Context) {}
}
let app = NSApplication.shared
let delegate = ViewerHost()
app.setActivationPolicy(.regular)
app.delegate = delegate
app.run()
