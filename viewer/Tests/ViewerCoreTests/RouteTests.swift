import Foundation
import XCTest
@testable import ViewerCore

final class RouteTests: XCTestCase {
    func fixture() throws -> (Snapshot, [String: Any]) {
        let source = String(repeating: "a", count: 64)
        func artwork(_ x: Int) -> [String: Any] {
            ["id": "s\(x)", "sourceID": source + ":\(x)", "kind": "Line", "layer": "F.Cu",
             "path": "M \(x) 0 L \(x+2) 0 L \(x+2) 2 L \(x) 2 Z",
             "bounds": ["x":x,"y":0,"width":2,"height":2], "attributes": [:]]
        }
        let snapshot: [String: Any] = ["schema":1,"job":"route-test","revision":"r1","slice":"test","status":"Preview",
            "bounds":["x":0,"y":0,"width":4,"height":2],"affected":["x":0,"y":0,"width":4,"height":2],
            "objects":[artwork(0),artwork(2)],"sources":[["name":"source","sha256":source,"layer":"F.Cu"]],"evidence":[],"limitations":[]]
        let scene = try JSONDecoder().decode(Snapshot.self, from: JSONSerialization.data(withJSONObject: snapshot))
        let groups: [[String: Any]] = [["kind":"straight","id":"PGS-saved"]]
        let members: [[String: Any]] = scene.objects.enumerated().map { i,o in
            ["objectID":o.id,"sourceID":o.sourceID,"currentPathSHA256":SnapshotReader.digest(Data(o.path.utf8)),
             "currentWkbSHA256":source,"originalWkbSHA256":source,
             "points":[[Double(i*2),1.0],[Double(i*2+2),1.0]],"groups":groups]
        }
        return (scene, ["schema":1,"job":scene.job,"revision":scene.revision,"routeID":"JR-saved",
            "catalogueSHA256":source,"bindingSHA256":source,"currentWkbSHA256":source,"displayHausdorffMM":0,
            "assembled":["path":"M 0 0 L 4 0 L 4 2 L 0 2 Z","bounds":["x":0,"y":0,"width":4,"height":2]],
            "bounds":["x":0,"y":0,"width":4,"height":2],"members":members,"groups":groups])
    }
    func decode(_ route: [String: Any], scene: Snapshot, selected: String = "s0") throws -> ViewerExplanation {
        let object = try XCTUnwrap(scene.objects.first { $0.id == selected })
        let value: [String: Any] = ["schema":1,"job":scene.job,"revision":scene.revision,"objectID":selected,
            "sourceID":object.sourceID,"author":"Retained geometry","text":"Route","evidence":["saved"],"route":route]
        let payload = try JSONSerialization.data(withJSONObject:value)
        let envelope = try JSONSerialization.data(withJSONObject:["schema":1,"sha256":SnapshotReader.digest(payload),"payloadBase64":payload.base64EncodedString()])
        return try ExplanationReader.decode(envelope,scene:scene,selectedID:selected)
    }
    func testWholeRouteIsBoundToEveryMemberAndSupportsEitherSegment() throws {
        let (scene,route) = try fixture()
        XCTAssertEqual(try decode(route,scene:scene).route?.members.count,2)
        XCTAssertEqual(try decode(route,scene:scene,selected:"s2").route?.routeID,"JR-saved")
    }
    func testStaleMemberPartialMembershipAndUnsafePathReject() throws {
        let (scene,route) = try fixture()
        var wrong = route
        wrong["revision"] = "older"
        XCTAssertThrowsError(try decode(wrong,scene:scene))
        var members = try XCTUnwrap(route["members"] as? [[String: Any]])
        members[1]["currentPathSHA256"] = String(repeating:"b",count:64)
        wrong = route; wrong["members"] = members
        XCTAssertThrowsError(try decode(wrong,scene:scene))
        wrong = route; wrong["members"] = Array(members.dropFirst())
        XCTAssertThrowsError(try decode(wrong,scene:scene))
        wrong = route; wrong["members"] = [members[0],members[0]]
        XCTAssertThrowsError(try decode(wrong,scene:scene))
        wrong = route; wrong["assembled"] = ["path":"M 0 0 <script>","bounds":["x":0,"y":0,"width":4,"height":2]]
        XCTAssertThrowsError(try decode(wrong,scene:scene))
    }
    func testOriginalCenterlinesAndGroupsCannotEscapeTheirDataBoundary() throws {
        let (scene,route) = try fixture()
        var members = try XCTUnwrap(route["members"] as? [[String: Any]])
        members[0]["points"] = [[0.0,1.0],[400.0,1.0]]
        var wrong = route; wrong["members"] = members
        XCTAssertThrowsError(try decode(wrong,scene:scene))
        wrong = route; wrong["groups"] = [["kind":"arc","id":"invented"]]
        XCTAssertThrowsError(try decode(wrong,scene:scene))
    }

    func testCataloguePickingIndexRejectsWrongObjectOrderAndDuplicateOwnership() throws {
        let (scene,_) = try fixture()
        var data=Data()
        for object in scene.objects {
            let bytes=Data(object.id.utf8);var length=UInt64(bytes.count).bigEndian
            withUnsafeBytes(of:&length){data.append(contentsOf:$0)};data.append(bytes)
        }
        var value: [String:Any]=["schema":1,"job":scene.job,"revision":scene.revision,
            "catalogueSHA256":String(repeating:"a",count:64),"objectsSHA256":SnapshotReader.digest(data),
            "entries":[["routeID":"JR-one","objectIndices":[0,1]]]]
        func validate(_ value:[String:Any]) throws {
            try JSONDecoder().decode(RouteCatalogueIndex.self,from:JSONSerialization.data(withJSONObject:value)).validate(scene:scene)
        }
        XCTAssertNoThrow(try validate(value))
        value["entries"]=[["routeID":"JR-one","objectIndices":[0]],["routeID":"JR-other","objectIndices":[0]]]
        XCTAssertThrowsError(try validate(value))
        value["entries"]=[["routeID":"JR-one","objectIndices":[999]]]
        XCTAssertThrowsError(try validate(value))
        value["entries"]=[["routeID":"JR-one","objectIndices":[0,1]]]
        value["objectsSHA256"]=String(repeating:"b",count:64)
        XCTAssertThrowsError(try validate(value))
    }

    func testRouteGrowthBindsToAssembledCopperNotClickedSegment() throws {
        let (scene, route) = try fixture()
        let artwork = try XCTUnwrap(route["assembled"] as? [String: Any])
        let path = try XCTUnwrap(artwork["path"] as? String)
        var comparison: [String: Any] = ["schema":1,
            "selectedPathSHA256":SnapshotReader.digest(Data(path.utf8)),
            "originalWkbSHA256":String(repeating:"b",count:64),
            "currentWkbSHA256":route["currentWkbSHA256"]!,
            "original":artwork,"addedAreaMM2":0,"removedAreaMM2":0,
            "displayHausdorffMM":0,"summary":"Complete route unchanged","snapshotNote":"Saved revision"]
        var value = route; value["comparison"] = comparison
        XCTAssertNoThrow(try decode(value,scene:scene,selected:"s0"))
        XCTAssertNoThrow(try decode(value,scene:scene,selected:"s2"))
        comparison["selectedPathSHA256"] = SnapshotReader.digest(Data(scene.objects[0].path.utf8))
        value["comparison"] = comparison
        XCTAssertThrowsError(try decode(value,scene:scene))
        comparison["selectedPathSHA256"] = SnapshotReader.digest(Data(path.utf8))
        comparison["currentWkbSHA256"] = String(repeating:"c",count:64)
        value["comparison"] = comparison
        XCTAssertThrowsError(try decode(value,scene:scene))
    }
}
