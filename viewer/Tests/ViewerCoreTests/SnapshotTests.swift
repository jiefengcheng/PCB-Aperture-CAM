import Foundation
import XCTest
@testable import ViewerCore

final class SnapshotTests: XCTestCase {
    func scene(revision: String = "r1", parent: String? = nil, path: String = "M 0 0 L 2 0 L 2 2 L 0 2 Z M 0.5 0.5 L 1.5 0.5 L 1.5 1.5 Z") throws -> Data {
        var value: [String: Any] = ["schema":1,"job":"test","revision":revision,"slice":"test","status":"Preview", "bounds":["x":0,"y":0,"width":2,"height":2],"affected":["x":0,"y":0,"width":2,"height":2],"objects":[["id":"one","sourceID":String(repeating:"a",count:64)+":1","kind":"Flash","layer":"F.Cu","path":path,"bounds":["x":0,"y":0,"width":2,"height":2],"attributes":[:]]],"sources":[["name":"test.gbr","sha256":String(repeating:"a", count:64),"layer":"F.Cu"]],"evidence":[],"limitations":["test"]]
        if let parent { value["parentRevision"] = parent }
        return try JSONSerialization.data(withJSONObject:value, options:[.sortedKeys])
    }
    func workspace() throws -> URL {
        let root = try XCTUnwrap(ProcessInfo.processInfo.environment["VIEWER_TEST_ROOT"])
        let url = URL(fileURLWithPath:root).appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at:url.appendingPathComponent("snapshots"),withIntermediateDirectories:true)
        return url
    }
    func publish(_ data: Data, root: URL, previous: Data? = nil) throws {
        let hash = SnapshotReader.digest(data)
        try data.write(to:root.appendingPathComponent("snapshots/"+hash+".json"))
        var manifest: [String:Any] = ["schema":1,"payload":hash+".json","sha256":hash]
        if let previous {
            let old = SnapshotReader.digest(previous)
            try previous.write(to:root.appendingPathComponent("snapshots/"+old+".json"))
            manifest["previousPayload"] = old+".json"; manifest["previousSHA256"] = old
        }
        try JSONSerialization.data(withJSONObject:manifest).write(to:root.appendingPathComponent("current.json"))
    }
    func testHashBoundRevisionChain() throws {
        let root = try workspace(), old = try scene(), new = try scene(revision:"r2",parent:"r1")
        try publish(new,root:root,previous:old)
        let read = try SnapshotReader.read(workspace:root)
        XCTAssertEqual(read.current.revision,"r2"); XCTAssertEqual(read.previous?.revision,"r1")
        try Data("corrupt".utf8).write(to:root.appendingPathComponent("snapshots/"+read.digest+".json"))
        XCTAssertThrowsError(try SnapshotReader.read(workspace:root))
    }
    func testBrokenParentAndMissingParentRejected() throws {
        let root = try workspace()
        try publish(scene(revision:"r2",parent:"wrong"),root:root,previous:scene())
        XCTAssertThrowsError(try SnapshotReader.read(workspace:root))
        try publish(scene(revision:"r2",parent:"r1"),root:root)
        XCTAssertThrowsError(try SnapshotReader.read(workspace:root))
    }
    func testMarkupAndNonfiniteRejected() throws {
        for path in ["M 0 0 <script>","M NaN 0 Z","M 1e999 0 Z","M L Z","M 0 0 Z"] {
            let snapshot = try JSONDecoder().decode(Snapshot.self,from:scene(path:path))
            XCTAssertThrowsError(try snapshot.validate())
        }
    }
    func testHoleContoursAdmitted() throws {
        let snapshot = try JSONDecoder().decode(Snapshot.self,from:scene())
        XCTAssertNoThrow(try snapshot.validate())
    }
    func testSymlinkEscapeRejected() throws {
        let root = try workspace(), data = try scene(), hash = SnapshotReader.digest(data)
        let outside = root.appendingPathComponent("outside.json")
        try publish(data,root:root)
        let target = root.appendingPathComponent("snapshots/"+hash+".json")
        try FileManager.default.moveItem(at:target,to:outside)
        try FileManager.default.createSymbolicLink(at:target,withDestinationURL:outside)
        XCTAssertThrowsError(try SnapshotReader.read(workspace:root))
    }
    func testFalseDimensionsAndSourceBindingRejected() throws {
        for transform in [
            { (s: String) in s.replacingOccurrences(of: "\"width\":2", with: "\"width\":8") },
            { (s: String) in s.replacingOccurrences(of: String(repeating:"a",count:64)+":1", with: "unbound:1") }
        ] {
            let text = String(decoding: try scene(), as: UTF8.self)
            let snapshot = try JSONDecoder().decode(Snapshot.self, from: Data(transform(text).utf8))
            XCTAssertThrowsError(try snapshot.validate())
        }
    }
    func testVerifiedRequiresEvidence() throws {
        let text = String(decoding: try scene(), as: UTF8.self).replacingOccurrences(of:"Preview",with:"Verified")
        let snapshot = try JSONDecoder().decode(Snapshot.self, from:Data(text.utf8))
        XCTAssertThrowsError(try snapshot.validate())
    }

}
