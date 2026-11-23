import Foundation
import XCTest
@testable import ViewerCore

final class BoardGrowthTests: XCTestCase {
    func testChecksummedRevisionBoundDataOnlyArtwork() throws {
        let (scene, _) = try RouteTests().fixture()
        let sha = String(repeating: "b", count: 64)
        var part: [String: Any] = ["id":"growth:source:0", "sourceID":scene.sources[0].sha256 + ":display-growth:0",
            "layer":"F.Cu", "kind":"source", "path":scene.objects[0].path,
            "bounds":["x":0,"y":0,"width":2,"height":2], "attributes":[:]]
        var value: [String: Any] = ["schema":1,"job":scene.job,"revision":scene.revision,"sceneSHA256":sha,
            "sourceSHA256":scene.sources[0].sha256,"predecessorSHA256":sha,"constructionSHA256":sha,
            "beforeWkbSHA256":sha,"afterWkbSHA256":sha,"parts":[part],"bounds":["x":0,"y":0,"width":4,"height":2],
            "addedAreaMM2":0,"removedAreaMM2":0,"displayHausdorffMM":0,"summary":"Saved T04 over T03", "note":"Display only"]
        func envelope(_ v: [String: Any], corrupt: Bool = false) throws -> Data {
            let data = try JSONSerialization.data(withJSONObject:v)
            return try JSONSerialization.data(withJSONObject:["schema":1,"sha256":corrupt ? sha : SnapshotReader.digest(data),"payloadBase64":data.base64EncodedString()])
        }
        func validate(_ v: [String: Any]) throws {
            _ = try BoardGrowthReader.decode(envelope(v),scene:scene,digest:sha)
        }
        XCTAssertNoThrow(try validate(value))
        let source: [String:Any] = ["sourceID":scene.sources[0].sha256+":source", "ordinal":1,
            "originalAreaMM2":1.0,"protrudingAreaMM2":0.2,"areaFraction":0.2,
            "rule":"SHALLOW_SOURCE_EDGE","contacts":"Saved bounded contact checks"]
        var cleanupCase: [String:Any] = ["id":"cleanup:0","kind":"bump","status":"corrected",
            "path":scene.objects[0].path,"bounds":["x":0,"y":0,"width":2,"height":2],
            "areaMM2":0.2,"depthLimitMM":0.1,"sources":[source],"rule":"SHALLOW_SOURCE_EDGE",
            "referencePath":"M 0 0 L 1 0","disposition":"Saved bounded correction"]
        var cleanup: [String:Any] = ["schema":1,"cases":[cleanupCase],"areaLimitFraction":0.1,
            "depthLimitMM":0.1,"areaComparison":"STRICTLY_LESS_THAN","areaBasis":"ORIGINAL_CAUSING_PAD_OR_TRACE","note":"Saved results only"]
        value["cleanup"]=cleanup;XCTAssertNoThrow(try validate(value))
        cleanup["operation"]="TRIM_ONLY";value["cleanup"]=cleanup
        XCTAssertNoThrow(try validate(value))
        value["addedAreaMM2"]=0.001;XCTAssertThrowsError(try validate(value));value["addedAreaMM2"]=0
        cleanupCase["kind"]="recess";cleanup["cases"]=[cleanupCase];value["cleanup"]=cleanup
        XCTAssertThrowsError(try validate(value))
        cleanupCase["kind"]="bump";cleanup["cases"]=[cleanupCase]
        cleanupCase["reviewNumber"]=1;cleanup["cases"]=[cleanupCase];value["cleanup"]=cleanup
        XCTAssertNoThrow(try validate(value))
        cleanupCase["status"]="ignored";cleanup["cases"]=[cleanupCase];value["cleanup"]=cleanup
        XCTAssertNoThrow(try validate(value));cleanupCase["status"]="corrected"
        cleanupCase["boundaryKind"]="circular";cleanup["cases"]=[cleanupCase];value["cleanup"]=cleanup
        XCTAssertNoThrow(try validate(value));cleanupCase["boundaryKind"]="invented"
        cleanup["cases"]=[cleanupCase];value["cleanup"]=cleanup;XCTAssertThrowsError(try validate(value));cleanupCase["boundaryKind"]="circular"
        cleanupCase["reviewNumber"]=9;cleanup["cases"]=[cleanupCase];value["cleanup"]=cleanup
        XCTAssertThrowsError(try validate(value))
        cleanupCase["reviewNumber"]=1;var duplicateReview=cleanupCase;duplicateReview["id"]="cleanup:1"
        cleanup["cases"]=[cleanupCase,duplicateReview];value["cleanup"]=cleanup;XCTAssertThrowsError(try validate(value))
        cleanupCase["referencePath"]="<script>";cleanup["cases"]=[cleanupCase];value["cleanup"]=cleanup
        XCTAssertThrowsError(try validate(value))
        cleanupCase["referencePath"]="M 0 0 L 1 0";cleanup["cases"]=[cleanupCase];cleanup["areaComparison"]="LESS_OR_EQUAL";value["cleanup"]=cleanup
        XCTAssertThrowsError(try validate(value))
        value.removeValue(forKey:"cleanup")
        XCTAssertThrowsError(try BoardGrowthReader.decode(envelope(value,corrupt:true),scene:scene,digest:sha))
        for key in ["job","revision","sceneSHA256","sourceSHA256"] {
            var wrong=value;wrong[key]="stale";XCTAssertThrowsError(try validate(wrong))
        }
        var wrong=value;wrong["addedAreaMM2"] = -1;XCTAssertThrowsError(try validate(wrong))
        wrong=value;wrong["bounds"]=["x":20,"y":20,"width":1,"height":1];XCTAssertThrowsError(try validate(wrong))
        part["path"]="<script>";wrong=value;wrong["parts"]=[part];XCTAssertThrowsError(try validate(wrong))
        part["path"]=scene.objects[0].path;part["kind"]="invented";value["parts"]=[part]
        XCTAssertThrowsError(try validate(value))
    }
}
