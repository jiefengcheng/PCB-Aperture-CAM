import AppKit
import ViewerCore

extension ViewerHost {
    func runCopperPipeline() {
        guard !cleanupBusy, !importing, !loading, !loadingPresentation, !traceBusy, modelTask == nil else { return }
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false; panel.canChooseDirectories = false
        panel.prompt = "Trim → T04"
        panel.message = "Choose one Gerber source. Run large-copper trimming, then T04 trace growth. Both saved results keep separate grey views; unresolved features remain recorded."
        panel.beginSheetModal(for: window) { [weak self] response in
            guard response == .OK, let self, let source = panel.url else { return }
            self.startCopperPipeline(source: source)
        }
    }

    func startCopperPipeline(source: URL) {
        do { try verifyStorage() } catch { send("viewerError", error.localizedDescription); return }
        cleanupBusy = true
        let repo = repository!, work = workRoot!, portable = portable
        let environment = portable ? workerEnvironment : ProcessInfo.processInfo.environment
        let job = work.appendingPathComponent("copper_pipeline_jobs/viewer-" + UUID().uuidString)
        cleanupJob = job
        send("receiveCleanupStatus", ["busy": true, "text": "Trimming → T04: reading source…"])
        send("phaseNavigationBusy", true)
        Task {
            let answer = await Task.detached { () -> (URL?, String) in
                let log = work.appendingPathComponent("copper-pipeline-" + UUID().uuidString + ".log")
                do {
                    let process = Process(); process.executableURL = repo.appendingPathComponent(".venv/bin/python")
                    process.currentDirectoryURL = repo
                    process.arguments = (portable ? ["-B", "tools/portable_cleanup.py", "--workspace", work.path, "run-pipeline"] : ["-B", "tools/run_copper_pipeline.py", "run"]) + ["--source", source.path, "--output", job.path, "--prepare-display"]
                    var env = environment
                    env["PYTHONDONTWRITEBYTECODE"] = "1"; env["TMPDIR"] = work.appendingPathComponent("tmp").path
                    process.environment = env
                    FileManager.default.createFile(atPath: log.path, contents: nil)
                    let errors = try FileHandle(forWritingTo: log); defer { try? errors.close() }
                    let output = Pipe(); process.standardOutput = output; process.standardError = errors
                    try process.run()
                    let data = output.fileHandleForReading.readDataToEndOfFile(); process.waitUntilExit()
                    guard process.terminationStatus == 0,
                          let value = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                          let display = value["display"] as? [String: Any],
                          let paths = display["workspaces"] as? [String: String], let path = paths["large_copper"] else {
                        return (nil, "Trimming → T04 stopped; current view retained. Evidence: " + log.path + " · requested job: " + job.path)
                    }
                    let target = URL(fileURLWithPath: path).resolvingSymlinksInPath()
                    guard target.path.hasPrefix(work.path + "/") else { throw ABIError.invalid("Pipeline display path rejected") }
                    let next = try SnapshotReader.read(workspace: target)
                    guard let link = try PhaseNavigationReader.read(workspace: target, workRoot: work,
                        digest: next.digest, sourceSHA256: next.current.sources.first?.sha256 ?? ""),
                        try link.phase(at: target) == "large_copper" else {
                        throw ABIError.invalid("Completed linked cleanup/T04 views required")
                    }
                    return (target, "Trimming and T04 complete · review trimming, then Open T04 result →")
                } catch { return (nil, "Trimming → T04 stopped; current view retained. " + error.localizedDescription + " · Evidence: " + log.path) }
            }.value
            cleanupBusy = false; cleanupJob = nil
            if let target = answer.0 {
                workspace = target; loaded = nil; lastManifestDigest = nil
                lastExplanationKey = nil; lastPresentationKey = nil; initialSelection = nil
                pendingTrace = nil; routePresentations.removeAll()
                window.title = "Large Copper Cleanup"
                poll()
            }
            send("receiveCleanupStatus", ["busy": false, "text": answer.1])
            send("phaseNavigationBusy", false)
        }
    }

    func pollCopperPipeline() {
        guard cleanupBusy, let job = cleanupJob else { return }
        let file = job.appendingPathComponent("STATE.json")
        guard let data = try? Data(contentsOf: file),
              let state = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
        let phase = state["phase"] as? String ?? "working"
        let labels = ["intake": "Reading source", "large_copper": "Trimming large copper", "seal_cleanup_output": "Sealing trimmed input",
                      "t04": "T04 trace growth", "seal_t04_output": "Sealing T04 result", "complete": "Preparing separate saved views"]
        var text = labels[phase] ?? phase
        if phase == "large_copper",
           let raw = try? Data(contentsOf: job.appendingPathComponent("large_copper/PROGRESS.json")),
           let detail = try? JSONSerialization.jsonObject(with: raw) as? [String: Any] {
            text += " · " + (detail["phase"] as? String ?? "working")
            if let count = detail["completed"] as? Int { text += " · \(count)/\(detail["candidates"] as? Int ?? 0)" }
        }
        send("receiveCleanupStatus", ["busy": true, "text": text])
    }
}
