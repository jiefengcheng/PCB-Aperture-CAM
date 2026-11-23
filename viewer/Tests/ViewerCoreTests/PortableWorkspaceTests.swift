import Foundation
import XCTest
@testable import ViewerCore

final class PortableWorkspaceTests: XCTestCase {
    func fixture() throws -> URL {
        let base = try XCTUnwrap(ProcessInfo.processInfo.environment["VIEWER_TEST_ROOT"])
        let root = URL(fileURLWithPath: base).appendingPathComponent("portable-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let data = try JSONSerialization.data(withJSONObject: ["schema":"portable-copper-workspace/1",
            "volume_uuid":try PortableWorkspaceGuard.volumeIdentity(at: root),"workspace_id":UUID().uuidString])
        try data.write(to: root.appendingPathComponent("CLEANUP_WORKSPACE.json"))
        return root
    }

    func testBootHomeUsesTheSameIdentityAsPythonDiskutilMount() throws {
        let root = URL(fileURLWithPath: NSHomeDirectory())
        // On a boot-volume group Foundation's UUID may identify Data while
        // diskutil / identifies the system volume. Neither is corrupt.
        let process = Process(); process.executableURL = URL(fileURLWithPath: "/usr/sbin/diskutil")
        process.arguments = ["info", "-plist", "/"]
        let output = Pipe(); process.standardOutput = output
        try process.run(); let data = output.fileHandleForReading.readDataToEndOfFile(); process.waitUntilExit()
        let info = try XCTUnwrap(PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any])
        XCTAssertEqual(try PortableWorkspaceGuard.volumeIdentity(at: root), info["VolumeUUID"] as? String)
    }

    func testAuthenticatedWorkspaceReopenAndMarkerMutation() throws {
        let root = try fixture(), marker = root.appendingPathComponent("CLEANUP_WORKSPACE.json")
        let guardValue = try PortableWorkspaceGuard(root: root)
        XCTAssertNoThrow(try guardValue.verify())
        XCTAssertNoThrow(try PortableWorkspaceGuard(root: root).verify())
        try Data("{}".utf8).write(to: marker)
        XCTAssertThrowsError(try guardValue.verify())
        XCTAssertThrowsError(try PortableWorkspaceGuard(root: root))
    }

    func testForeignVolumeMarkerRejected() throws {
        let root = try fixture(), marker = root.appendingPathComponent("CLEANUP_WORKSPACE.json")
        let data = try JSONSerialization.data(withJSONObject: ["schema":"portable-copper-workspace/1",
            "volume_uuid":UUID().uuidString,"workspace_id":UUID().uuidString])
        try data.write(to: marker)
        XCTAssertThrowsError(try PortableWorkspaceGuard(root: root))
    }

    func testSameByteSymlinkAndMissingWorkspaceRejected() throws {
        let root = try fixture(), marker = root.appendingPathComponent("CLEANUP_WORKSPACE.json")
        let guardValue = try PortableWorkspaceGuard(root: root)
        let retained = root.appendingPathComponent("retained-marker.json")
        try FileManager.default.moveItem(at: marker, to: retained)
        try FileManager.default.createSymbolicLink(at: marker, withDestinationURL: retained)
        XCTAssertThrowsError(try guardValue.verify())
        XCTAssertThrowsError(try PortableWorkspaceGuard(root: root))
        XCTAssertThrowsError(try PortableWorkspaceGuard(root: root.appendingPathComponent("missing")))
        XCTAssertFalse(FileManager.default.fileExists(atPath: root.appendingPathComponent("missing").path))
    }
}
