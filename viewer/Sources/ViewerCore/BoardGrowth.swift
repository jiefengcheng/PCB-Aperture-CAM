import Foundation

public struct BoardGrowth: Codable, Sendable {
    public let cleanup: CopperCleanup?
    public let t04: T04Workspace?
    public let schema: Int
    public let job: String, revision: String, sceneSHA256: String, sourceSHA256: String
    public let predecessorSHA256: String, constructionSHA256: String, beforeWkbSHA256: String, afterWkbSHA256: String
    public let parts: [SceneObject]
    public let bounds: Bounds
    public let addedAreaMM2: Double, removedAreaMM2: Double, displayHausdorffMM: Double
    public let summary: String, note: String
}
public struct T04Workspace: Codable, Sendable {
    public let schema: Int
    public let fullBoard: Bool?
    public let largeFillCoverageFraction: Double?
    public let inputSceneSHA256: String, beforeWkbSHA256: String, afterWkbSHA256: String
    public let parts: [SceneObject], bounds: Bounds
    public let addedAreaMM2: Double, removedAreaMM2: Double, displayHausdorffMM: Double
    public let findings: [T04Finding]
    public let grownRoutes: Int, keptRoutes: Int, connectionChecks: Int
    public let nominalCutoffMM: Double, maximumFactor: Double, maximumWidthIncreaseMM: Double
    public let summary: String, note: String
}
public struct T04Finding: Codable, Sendable {
    public let id: String, kind: String, routeID: String, description: String
    public let sourceIDs: [String], reasons: [String], bounds: Bounds
    public let missingSectionMM: Double?
}
public struct CopperCleanup: Codable, Sendable {
    public let schema: Int
    public let operation: String?
    public let cases: [CopperCleanupCase]
    public let objects: [CopperCleanupObject]?
    public let parts: [SceneObject]?
    public let areaLimitFraction: Double, depthLimitMM: Double
    public let areaComparison: String, areaBasis: String, note: String
}
public struct CopperCleanupObject: Codable, Sendable {
    public let id: String
    public let bounds: Bounds
    public let areaMM2: Double
}
public struct CopperCleanupCase: Codable, Sendable {
    public let reviewNumber: Int?
    public let boundaryKind: String?
    public let id: String, kind: String, status: String, path: String, rule: String
    public let referencePath: String, disposition: String
    public let bounds: Bounds
    public let areaMM2: Double, depthLimitMM: Double
    public let sources: [CopperCleanupSource]
    public let objectIDs: [String]?
}
public struct CopperCleanupSource: Codable, Sendable {
    public let sourceID: String, ordinal: Int?
    public let originalAreaMM2: Double
    public let protrudingAreaMM2: Double?, areaFraction: Double?
    public let rule: String, contacts: String
}
private struct BoardGrowthEnvelope: Decodable {
    let schema: Int, sha256: String, payloadBase64: String
}
public enum BoardGrowthReader {
    public static func decode(_ data: Data, scene: Snapshot, digest: String) throws -> BoardGrowth {
        guard data.count <= 90 * 1024 * 1024 else { throw ABIError.invalid("Board growth resource limit") }
        let envelope = try JSONDecoder().decode(BoardGrowthEnvelope.self, from: data)
        guard envelope.schema == 1, let payload = Data(base64Encoded: envelope.payloadBase64),
              payload.count <= 64 * 1024 * 1024, SnapshotReader.digest(payload) == envelope.sha256 else {
            throw ABIError.invalid("Board growth checksum mismatch")
        }
        let value = try JSONDecoder().decode(BoardGrowth.self, from: payload)
        guard value.schema == 1, value.job == scene.job, value.revision == scene.revision,
              value.sceneSHA256 == digest, scene.sources.count == 1,
              value.sourceSHA256 == scene.sources[0].sha256,
              [value.predecessorSHA256, value.constructionSHA256, value.beforeWkbSHA256, value.afterWkbSHA256].allSatisfy(Snapshot.isDigest),
              [value.addedAreaMM2, value.removedAreaMM2].allSatisfy({ $0.isFinite && $0 >= 0 }),
              value.displayHausdorffMM.isFinite, value.displayHausdorffMM >= 0, value.displayHausdorffMM <= 0.000500001,
              !value.summary.isEmpty, value.summary.count <= 1000, value.note.count <= 2000,
              value.parts.allSatisfy({ ["source", "added", "removed"].contains($0.kind) && $0.id.hasPrefix("growth:") && $0.sourceID.hasPrefix(value.sourceSHA256 + ":display-growth:") }) else {
            throw ABIError.invalid("Board growth revision/source binding mismatch")
        }
        try Snapshot(schema: 1, job: scene.job, revision: scene.revision, slice: "Board growth display", status: "Preview",
                     parentRevision: nil, bounds: value.bounds, affected: value.bounds, objects: value.parts,
                     sources: scene.sources, evidence: [], limitations: []).validate()
        if let t04 = value.t04 {
            guard t04.schema == 1, [t04.inputSceneSHA256,t04.beforeWkbSHA256,t04.afterWkbSHA256].allSatisfy(Snapshot.isDigest),
                  t04.afterWkbSHA256 == value.afterWkbSHA256,
                  [t04.addedAreaMM2,t04.removedAreaMM2,t04.displayHausdorffMM].allSatisfy({$0.isFinite && $0 >= 0}),
                  t04.displayHausdorffMM <= 0.000500001, t04.bounds.valid,
                  t04.grownRoutes >= 0, t04.keptRoutes >= 0, t04.connectionChecks >= 0,
                  [t04.nominalCutoffMM,t04.maximumFactor,t04.maximumWidthIncreaseMM].allSatisfy({$0.isFinite && $0 > 0}),
                  (t04.largeFillCoverageFraction == nil || (t04.largeFillCoverageFraction!.isFinite && t04.largeFillCoverageFraction! > 0 && t04.largeFillCoverageFraction! <= 1)),
                  t04.summary.count <= 1000, t04.note.count <= 2000,
                  t04.findings.count <= 20000, Set(t04.findings.map(\.id)).count == t04.findings.count,
                  t04.findings.allSatisfy({["corner","endpoint","eligibility","continuity"].contains($0.kind) && $0.bounds.valid &&
                      $0.description.count <= 2000 && $0.reasons.count <= 50 &&
                      $0.sourceIDs.allSatisfy({$0.hasPrefix(value.sourceSHA256+":")}) &&
                      ($0.missingSectionMM == nil || ($0.missingSectionMM!.isFinite && $0.missingSectionMM! >= 0))}),
                  t04.parts.allSatisfy({["source","added","removed"].contains($0.kind) && $0.id.hasPrefix("growth:t04:") &&
                      $0.sourceID.hasPrefix(value.sourceSHA256+":display-growth:t04:")}) else {
                throw ABIError.invalid("T04 workspace binding invalid")
            }
            try Snapshot(schema:1,job:scene.job,revision:scene.revision,slice:"Saved T04 workspace",status:"Preview",
                parentRevision:nil,bounds:t04.bounds,affected:t04.bounds,objects:t04.parts,
                sources:scene.sources,evidence:[],limitations:[]).validate()
        }
        if let cleanup = value.cleanup {
            guard cleanup.schema == 1, cleanup.areaLimitFraction == 0.1, cleanup.depthLimitMM == 0.1,
                  cleanup.areaComparison == "STRICTLY_LESS_THAN", cleanup.areaBasis == "ORIGINAL_CAUSING_PAD_OR_TRACE",
                  cleanup.cases.count <= 20000, Set(cleanup.cases.map(\.id)).count == cleanup.cases.count else {
                throw ABIError.invalid("Copper cleanup binding invalid")
            }
            for item in cleanup.cases {
                guard ["bump", "recess"].contains(item.kind), ["corrected", "unresolved", "ignored"].contains(item.status),
                      item.areaMM2.isFinite, item.areaMM2 >= 0, item.depthLimitMM == 0.1,
                      item.sources.allSatisfy({ $0.sourceID.hasPrefix(value.sourceSHA256 + ":") && $0.originalAreaMM2.isFinite && $0.originalAreaMM2 > 0 && ($0.areaFraction == nil || ($0.areaFraction!.isFinite && $0.areaFraction! >= 0)) }) else {
                    throw ABIError.invalid("Copper cleanup case invalid")
                }
                if let number=item.reviewNumber, !(1...8).contains(number) { throw ABIError.invalid("Cleanup review number invalid") }
                if let kind=item.boundaryKind, !["circular","other"].contains(kind) { throw ABIError.invalid("Cleanup boundary kind invalid") }
                guard item.bounds.valid, item.path.count <= 8_000_000, item.referencePath.count <= 8_000_000,
                      item.rule.count <= 200, item.disposition.count <= 2000 else {
                    throw ABIError.invalid("Copper cleanup geometry invalid")
                }
                if !item.path.isEmpty { _ = try Snapshot.polygonCoordinates(item.path) }
                let allowed = CharacterSet(charactersIn: "MLZmlz0123456789+-.eE ,\n\t")
                guard item.referencePath.unicodeScalars.allSatisfy({ allowed.contains($0) }) else {
                    throw ABIError.invalid("Copper cleanup reference path invalid")
                }
                let numbers=item.referencePath.components(separatedBy:CharacterSet(charactersIn:"MLZmlz, \n\t")).filter{!$0.isEmpty}
                guard numbers.count % 2 == 0,numbers.allSatisfy({ if let v=Double($0) { return v.isFinite && abs(v)<1e7 };return false }),
                      item.sources.allSatisfy({$0.protrudingAreaMM2 == nil || ($0.protrudingAreaMM2!.isFinite && $0.protrudingAreaMM2!>=0)}) else {
                    throw ABIError.invalid("Copper cleanup measurement invalid")
                }
            }
            let reviewNumbers=cleanup.cases.compactMap(\.reviewNumber)
            guard Set(reviewNumbers).count==reviewNumbers.count else { throw ABIError.invalid("Duplicate cleanup review number") }
            if let objects=cleanup.objects,let parts=cleanup.parts {
                guard Set(objects.map(\.id)).count==objects.count,objects.allSatisfy({$0.bounds.valid && $0.areaMM2.isFinite && $0.areaMM2>=1}),
                      parts.allSatisfy({["source","removed","added"].contains($0.kind) && $0.sourceID.hasPrefix(value.sourceSHA256+":display-growth:") && $0.bounds.valid}) else {
                    throw ABIError.invalid("Isolated copper objects invalid")
                }
                for part in parts { _ = try Snapshot.polygonCoordinates(part.path) }
            }
            if cleanup.operation == "TRIM_ONLY" {
                guard value.addedAreaMM2<=1e-12,cleanup.cases.allSatisfy({$0.kind=="bump"}),
                      (cleanup.parts ?? []).allSatisfy({$0.kind != "added"}) else {
                    throw ABIError.invalid("Trim-only display contains added copper")
                }
            }
        }
        return value
    }
    public static func read(_ url: URL, scene: Snapshot, digest: String) throws -> BoardGrowth {
        try decode(SnapshotReader.limitedData(url, limit: 90 * 1024 * 1024), scene: scene, digest: digest)
    }
}
