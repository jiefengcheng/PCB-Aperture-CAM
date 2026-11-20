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
    var loaded: LoadedRevision?
    var pageReady = false
    var loading = false
    var lastManifestDigest: String?
    var importing = false
    var smokeStarted = false
    var modelTask: Task<Void, Never>?
    func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            func argument(_ name: String) throws -> String {
                let args = CommandLine.arguments
                if let index = args.lastIndex(of: name), index + 1 < args.count { return args[index + 1] }
                let key = name == "--workspace" ? "ViewerWorkspace" : "ViewerRepository"
                guard let value = Bundle.main.object(forInfoDictionaryKey: key) as? String else { throw ABIError.invalid("Launch through tools/Start_Gerber_Viewer.command") }
                return value
            }
            workspace = URL(fileURLWithPath: try argument("--workspace")).resolvingSymlinksInPath()
            repository = URL(fileURLWithPath: try argument("--repository")).resolvingSymlinksInPath()
            guard FileManager.default.fileExists(atPath: workspace.path),
                  workspace.path.hasPrefix(repository.appendingPathComponent("out/lacie_work").resolvingSymlinksInPath().path + "/") else { throw ABIError.invalid("Viewer requires the prepared LaCie workspace") }
            try verifyStorage()
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
    func verifyStorage() throws {
        let root = repository.appendingPathComponent("out/lacie_work").resolvingSymlinksInPath()
        let data = try Data(contentsOf: root.appendingPathComponent("STORAGE_IDENTITY.json"))
        let identity = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        guard identity?["lacie_volume_uuid"] as? String == "5E178CE8-A7FF-37D9-B307-F0D08FBB4D14" else { throw ABIError.invalid("LaCie storage identity mismatch") }
        // An unmounted directory must never become an internal fallback.
        let values = try root.resourceValues(forKeys: [.volumeURLKey])
        guard values.volume?.standardizedFileURL.path == root.standardizedFileURL.path else { throw ABIError.invalid("LaCie workspace is not mounted") }
    }
    func fatalDialog(_ message: String) { let alert = NSAlert(); alert.messageText = "Gerber Viewer"; alert.informativeText = message; alert.runModal(); NSApp.terminate(nil) }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { pageReady = true; poll() }
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
        guard FileManager.default.fileExists(atPath: workspace.appendingPathComponent("current.json").path) else { return }
        if let data = try? Data(contentsOf: workspace.appendingPathComponent("current.json")), SnapshotReader.digest(data) == lastManifestDigest, loaded != nil { return }
        loading = true
        let root = workspace!
        Task {
            do {
                let next = try await Task.detached { try SnapshotReader.read(workspace: root) }.value
                lastManifestDigest = next.manifestDigest
                if next.digest != loaded?.digest {
                    let encoder = JSONEncoder()
                    let current = try JSONSerialization.jsonObject(with: encoder.encode(next.current))
                    let previous: Any = try next.previous.map { try JSONSerialization.jsonObject(with: encoder.encode($0)) } ?? NSNull()
                    loaded = next
                    send("receiveRevision", ["current": current, "previous": previous])
                    runSmokeIfRequested()
                } else { send("clearABIError", "") }
            } catch { send("viewerError", "Update rejected; retaining displayed revision. " + error.localizedDescription) }
            loading = false
        }
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: String], let action = body["action"] else { return }
        if action == "open" { openGerbers(); return }
        if action == "modelStatus" {
            Task { send("modelResult", await AppleViewerProvider().availability()) }; return
        }
        guard let id = body["id"], let revision = body["revision"], let loaded else { return }
        let scene = revision == loaded.current.revision ? loaded.current : loaded.previous
        guard let scene, scene.revision == revision, let object = scene.objects.first(where: { $0.id == id }) else { return }
        do {
            let objectData = try JSONEncoder().encode(object)
            let selection: [String: Any] = ["schema": 1, "job": scene.job, "revision": revision, "object": try JSONSerialization.jsonObject(with: objectData), "timestamp": ISO8601DateFormatter().string(from: Date())]
            if action == "select" {
                try verifyStorage()
                let folder = workspace.appendingPathComponent("outbox")
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                try JSONSerialization.data(withJSONObject: selection, options: [.sortedKeys]).write(to: folder.appendingPathComponent("selection.json"), options: .atomic)
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
    func runSmokeIfRequested() {
        let args = CommandLine.arguments
        guard !smokeStarted, let i = args.firstIndex(of: "--smoke-report"), i + 1 < args.count else { return }
        smokeStarted = true
        let folder = URL(fileURLWithPath: args[i + 1]).resolvingSymlinksInPath()
        guard folder.path.hasPrefix(repository.appendingPathComponent("out/lacie_work").resolvingSymlinksInPath().path + "/") else { return }
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
