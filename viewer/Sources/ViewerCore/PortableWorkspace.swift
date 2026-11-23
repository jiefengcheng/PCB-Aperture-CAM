import Foundation

/// diskutil and Foundation expose different UUIDs for an APFS boot-volume group.
/// Authenticate the Python marker with its diskutil authority, then retain the
/// native identity for cheap, fail-closed checks during this viewer lifetime.
public struct PortableWorkspaceGuard {
    private let root: URL
    private let marker: Data
    private let nativeUUID: String
    private let mount: URL
    private let device: UInt64

    public static func volumeIdentity(at root: URL) throws -> String {
        let values = try root.resourceValues(forKeys: [.volumeURLKey])
        guard let mount = values.volume else { throw ABIError.invalid("Workspace volume missing") }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/sbin/diskutil")
        process.arguments = ["info", "-plist", mount.path]
        let output = Pipe(); process.standardOutput = output; process.standardError = FileHandle.nullDevice
        try process.run()
        let data = output.fileHandleForReading.readDataToEndOfFile(); process.waitUntilExit()
        guard process.terminationStatus == 0,
              let info = try PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any],
              let uuid = info["VolumeUUID"] as? String,
              let format = info["FilesystemType"] as? String,
              format.uppercased() == "APFS", info["ReadOnlyVolume"] as? Bool != true else {
            throw ABIError.invalid("Writable APFS workspace volume identity required")
        }
        return uuid
    }

    public init(root: URL) throws {
        self.root = root.resolvingSymlinksInPath()
        let path = self.root.appendingPathComponent("CLEANUP_WORKSPACE.json")
        marker = try Data(contentsOf: path)
        let value = try JSONSerialization.jsonObject(with: marker) as? [String: Any]
        let values = try self.root.resourceValues(forKeys: [.volumeUUIDStringKey, .volumeURLKey, .volumeIsReadOnlyKey])
        guard value?["schema"] as? String == "portable-copper-workspace/1",
              let expected = value?["volume_uuid"] as? String,
              let workspaceID = value?["workspace_id"] as? String, !workspaceID.isEmpty,
              try Self.volumeIdentity(at: self.root).lowercased() == expected.lowercased(),
              let uuid = values.volumeUUIDString, let mounted = values.volume,
              values.volumeIsReadOnly == false,
              let number = try FileManager.default.attributesOfFileSystem(forPath: self.root.path)[.systemNumber] as? NSNumber else {
            throw ABIError.invalid("Selected workspace volume unavailable; no fallback folder is used")
        }
        nativeUUID = uuid; mount = mounted; device = number.uint64Value
        try verify()
    }

    public func verify() throws {
        let path = root.appendingPathComponent("CLEANUP_WORKSPACE.json")
        let values = try root.resourceValues(forKeys: [.volumeUUIDStringKey, .volumeURLKey, .volumeIsReadOnlyKey])
        let link = try path.resourceValues(forKeys: [.isSymbolicLinkKey])
        let number = try FileManager.default.attributesOfFileSystem(forPath: root.path)[.systemNumber] as? NSNumber
        guard try Data(contentsOf: path) == marker, link.isSymbolicLink == false,
              values.volumeUUIDString == nativeUUID, values.volume == mount,
              values.volumeIsReadOnly == false, number?.uint64Value == device else {
            throw ABIError.invalid("Selected workspace volume unavailable; no fallback folder is used")
        }
    }
}
