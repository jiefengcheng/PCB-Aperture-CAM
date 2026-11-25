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
        var t04Part=part;t04Part["id"]="growth:t04:0";t04Part["sourceID"]=scene.sources[0].sha256+":display-growth:t04:0"
        var finding:[String:Any] = ["id":"t04-finding:0","kind":"endpoint","routeID":"r","description":"Saved endpoint finding",
            "sourceIDs":[scene.sources[0].sha256+":source"],"reasons":["FROZEN_END_SECTION_NOT_REALIZED_BY_EMITTED_ROUTE"],
            "bounds":["x":0,"y":0,"width":1,"height":1],"missingSectionMM":0.001]
        var t04:[String:Any] = ["schema":1,"inputSceneSHA256":sha,"beforeWkbSHA256":sha,"afterWkbSHA256":sha,
            "parts":[t04Part],"bounds":["x":0,"y":0,"width":4,"height":2],"addedAreaMM2":0,"removedAreaMM2":0,
            "displayHausdorffMM":0,"findings":[finding],"grownRoutes":1,"keptRoutes":0,"connectionChecks":1,
            "nominalCutoffMM":0.25,"maximumFactor":1.5,"maximumWidthIncreaseMM":0.03,"summary":"T04 only","note":"Saved data only"]
        value["t04"]=t04;XCTAssertNoThrow(try validate(value))
        var shoulder:[String:Any] = ["beforeWkbSHA256":sha,"afterWkbSHA256":sha,
            "parts":[t04Part],"bounds":["x":0,"y":0,"width":4,"height":2],
            "addedAreaMM2":0,"removedAreaMM2":0,"displayHausdorffMM":0,
            "summary":"Previous widening","note":"Saved geometry only"]
        t04["shoulderReview"]=shoulder;value["t04"]=t04;XCTAssertNoThrow(try validate(value))
        shoulder["afterWkbSHA256"]=String(repeating:"d",count:64)
        t04["shoulderReview"]=shoulder;value["t04"]=t04;XCTAssertThrowsError(try validate(value))
        shoulder["afterWkbSHA256"]=sha;shoulder["displayHausdorffMM"]=0.001
        t04["shoulderReview"]=shoulder;value["t04"]=t04;XCTAssertThrowsError(try validate(value))
        t04.removeValue(forKey:"shoulderReview")
        t04["fullBoard"]=false;t04["largeFillCoverageFraction"]=0.8;value["t04"]=t04;XCTAssertNoThrow(try validate(value))
        t04["largeFillCoverageFraction"]=1.1;value["t04"]=t04;XCTAssertThrowsError(try validate(value));t04["largeFillCoverageFraction"]=0.8
        t04["inputSceneSHA256"]="stale";value["t04"]=t04;XCTAssertThrowsError(try validate(value));t04["inputSceneSHA256"]=sha
        t04["afterWkbSHA256"]=String(repeating:"c",count:64);value["t04"]=t04;XCTAssertThrowsError(try validate(value));t04["afterWkbSHA256"]=sha
        finding["kind"]="bump";t04["findings"]=[finding];value["t04"]=t04;XCTAssertThrowsError(try validate(value))
        finding["kind"]="endpoint";finding["missingSectionMM"] = -1;t04["findings"]=[finding];value["t04"]=t04;XCTAssertThrowsError(try validate(value))
        value.removeValue(forKey:"t04")
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
