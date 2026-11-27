import AppKit
import WebKit
import ViewerCore

extension ViewerHost {
    func phaseConfiguration(_ link: PhaseNavigation, at root: URL) throws -> [String: String] {
        ["phase": try link.phase(at: root), "pipeline": link.pipelineResultSHA256]
    }

    func openSavedPhase() {
        guard !loading, !loadingPresentation, !importing, !cleanupBusy, !traceBusy,
              modelTask == nil, let displayed = loaded else {
            send("phaseNavigationBusy", false)
            return
        }
        do {
            try verifyStorage()
            guard let link = try PhaseNavigationReader.read(workspace: workspace, workRoot: workRoot,
                digest: displayed.digest, sourceSHA256: displayed.current.sources.first?.sha256 ?? "") else {
                throw ABIError.invalid("No completed linked phase is available")
            }
            let (phase, target) = try link.destination(from: workspace)
            let root = URL(fileURLWithPath: target.path)
            loading = true
            displayReadStarted = ContinuousClock().now
            send("phaseNavigationBusy", true)
            Task {
                defer { loading = false; send("phaseNavigationBusy", false) }
                do {
                    // Saved bytes only. No worker, geometry or treatment API.
                    let (next, growth) = try await Task.detached {
                        let next = try SnapshotReader.read(workspace: root)
                        guard next.digest == target.snapshotSHA256 else {
                            throw ABIError.invalid("Linked phase revision changed")
                        }
                        let presentation = root.appendingPathComponent("presentations/" + next.digest + ".json")
                        let growth = try BoardGrowthReader.read(presentation, scene: next.current,
                            digest: next.digest, expectedFileSHA256: target.presentationSHA256)
                        guard growth.sourceSHA256 == link.sourceSHA256,
                              (phase == "t04" ? growth.t04 != nil && growth.cleanup == nil : growth.cleanup != nil && growth.t04 == nil) else {
                            throw ABIError.invalid("Linked phase source or presentation kind changed")
                        }
                        return (next, growth)
                    }.value
                    try verifyStorage()
                    let encoder = JSONEncoder()
                    let current = try JSONSerialization.jsonObject(with: encoder.encode(next.current))
                    let previous: Any = try next.previous.map { try JSONSerialization.jsonObject(with: encoder.encode($0)) } ?? NSNull()
                    let value: [String: Any] = ["current": current, "previous": previous,
                        "boardGrowth": try JSONSerialization.jsonObject(with: encoder.encode(growth)),
                        "phaseNavigation": try phaseConfiguration(link, at: root)]
                    // Commit the workspace change only after the complete target validates.
                    let file = root.appendingPathComponent("presentations/" + next.digest + ".json")
                    let stamp = try file.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey])
                    workspace = root
                    loaded = next
                    lastManifestDigest = next.manifestDigest
                    lastPresentationKey = stamp.contentModificationDate.map {
                        next.digest + ":" + String($0.timeIntervalSince1970) + ":" + String(stamp.fileSize ?? 0)
                    }
                    pendingTrace = nil; initialSelection = nil; lastExplanationKey = nil
                    routePresentations.removeAll()
                    window.title = phase == "t04" ? "T04 Trace Growth" : "Large Copper Cleanup"
                    send("receiveRevision", value)
                } catch {
                    send("viewerError", "Saved phase not opened; retaining the current view. " + error.localizedDescription)
                }
            }
        } catch { send("viewerError", error.localizedDescription) }
    }
}
