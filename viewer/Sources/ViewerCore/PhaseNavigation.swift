import Foundation

public struct SavedPhaseDestination: Codable, Sendable {
    public let path: String
    public let snapshotSHA256: String
    public let presentationSHA256: String
}

public struct PhaseNavigation: Codable, Sendable {
    public let schema: Int
    public let sourceSHA256: String
    public let pipelineResultSHA256: String
    public let workspaces: [String: SavedPhaseDestination]

    public func phase(at workspace: URL) throws -> String {
        let path = workspace.resolvingSymlinksInPath().standardizedFileURL.path
        guard let name = workspaces.first(where: { $0.value.path == path })?.key else {
            throw ABIError.invalid("Workspace is not in the saved phase pair")
        }
        return name
    }

    public func destination(from workspace: URL) throws -> (String, SavedPhaseDestination) {
        let name = try phase(at: workspace) == "large_copper" ? "t04" : "large_copper"
        guard let entry = workspaces[name] else { throw ABIError.invalid("Linked phase missing") }
        return (name, entry)
    }
}

public enum PhaseNavigationReader {
    public static func read(workspace: URL, workRoot: URL, digest: String,
                            sourceSHA256: String) throws -> PhaseNavigation? {
        let file = workspace.appendingPathComponent("phase-navigation.json")
        guard FileManager.default.fileExists(atPath: file.path) else { return nil }
        guard try file.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink != true else {
            throw ABIError.invalid("Linked phase metadata must not be a symlink")
        }
        let value = try JSONDecoder().decode(PhaseNavigation.self,
            from: SnapshotReader.limitedData(file, limit: 16_384))
        let root = workRoot.resolvingSymlinksInPath().standardizedFileURL.path + "/"
        guard value.schema == 1, value.sourceSHA256 == sourceSHA256,
              Snapshot.isDigest(value.sourceSHA256), Snapshot.isDigest(value.pipelineResultSHA256),
              Set(value.workspaces.keys) == Set(["large_copper", "t04"]),
              Set(value.workspaces.values.map(\.path)).count == 2 else {
            throw ABIError.invalid("Linked phase binding changed")
        }
        for entry in value.workspaces.values {
            let url = URL(fileURLWithPath: entry.path)
            guard entry.path.hasPrefix(root),
                  url.resolvingSymlinksInPath().standardizedFileURL.path == entry.path,
                  Snapshot.isDigest(entry.snapshotSHA256), Snapshot.isDigest(entry.presentationSHA256) else {
                throw ABIError.invalid("Linked phase escapes workspace or has invalid pins")
            }
        }
        let current = try value.phase(at: workspace)
        guard value.workspaces[current]?.snapshotSHA256 == digest else {
            throw ABIError.invalid("Linked phase revision changed")
        }
        return value
    }
}
