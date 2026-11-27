import Foundation
import XCTest
@testable import ViewerCore

final class PhaseNavigationTests: XCTestCase {
    func fixture() throws -> (URL, URL, [String: Any]) {
        let base = try XCTUnwrap(ProcessInfo.processInfo.environment["VIEWER_TEST_ROOT"])
        let root = URL(fileURLWithPath: base).appendingPathComponent(UUID().uuidString)
        let cleanup = root.appendingPathComponent("cleanup"), t04 = root.appendingPathComponent("t04")
        for directory in [cleanup, t04] {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        }
        return (root, cleanup, ["schema": 1, "sourceSHA256": String(repeating: "a", count: 64),
            "pipelineResultSHA256": String(repeating: "b", count: 64),
            "workspaces": ["large_copper": ["path": cleanup.path, "snapshotSHA256": String(repeating: "c", count: 64), "presentationSHA256": String(repeating: "d", count: 64)],
                           "t04": ["path": t04.path, "snapshotSHA256": String(repeating: "e", count: 64), "presentationSHA256": String(repeating: "f", count: 64)]]])
    }

    func read(_ value: [String: Any], root: URL, cleanup: URL) throws -> PhaseNavigation? {
        try JSONSerialization.data(withJSONObject: value).write(to: cleanup.appendingPathComponent("phase-navigation.json"))
        return try PhaseNavigationReader.read(workspace: cleanup, workRoot: root,
            digest: String(repeating: "c", count: 64), sourceSHA256: String(repeating: "a", count: 64))
    }

    func testSavedPairRequiresMatchingCurrentRevisionAndSource() throws {
        let (root, cleanup, value) = try fixture()
        let link = try XCTUnwrap(read(value, root: root, cleanup: cleanup))
        XCTAssertEqual(try link.destination(from: cleanup).0, "t04")
        XCTAssertEqual(try link.destination(from: root.appendingPathComponent("t04")).0, "large_copper")
        for key in ["sourceSHA256", "pipelineResultSHA256"] {
            var changed = value; changed[key] = "invalid"
            XCTAssertThrowsError(try read(changed, root: root, cleanup: cleanup))
        }
        XCTAssertThrowsError(try PhaseNavigationReader.read(workspace: cleanup, workRoot: root,
            digest: String(repeating: "e", count: 64), sourceSHA256: String(repeating: "a", count: 64)))
    }

    func testInvalidDestinationAndMetadataCannotOpenAnotherWorkspace() throws {
        let (root, cleanup, value) = try fixture()
        let original = try XCTUnwrap(value["workspaces"] as? [String: [String: String]])
        for path in [root.deletingLastPathComponent().path, cleanup.path, root.path + "/t04/../t04"] {
            var destinations = original; destinations["t04"]?["path"] = path
            var changed = value; changed["workspaces"] = destinations
            XCTAssertThrowsError(try read(changed, root: root, cleanup: cleanup))
        }
        var destinations = original; destinations["t04"]?["presentationSHA256"] = "not-a-digest"
        var changed = value; changed["workspaces"] = destinations
        XCTAssertThrowsError(try read(changed, root: root, cleanup: cleanup))
        let file = cleanup.appendingPathComponent("phase-navigation.json")
        try FileManager.default.removeItem(at: file)
        XCTAssertNil(try PhaseNavigationReader.read(workspace: cleanup, workRoot: root,
            digest: String(repeating: "c", count: 64), sourceSHA256: String(repeating: "a", count: 64)))
        let other = root.appendingPathComponent("other.json")
        try JSONSerialization.data(withJSONObject: value).write(to: other)
        try FileManager.default.createSymbolicLink(at: file, withDestinationURL: other)
        XCTAssertThrowsError(try PhaseNavigationReader.read(workspace: cleanup, workRoot: root,
            digest: String(repeating: "c", count: 64), sourceSHA256: String(repeating: "a", count: 64)))
    }
}
