import Foundation

public struct RouteIndexEntry: Codable, Sendable {
    public let routeID: String
    public let objectIndices: [Int]
}
public struct RouteCatalogueIndex: Codable, Sendable {
    public let schema: Int
    public let job: String, revision: String, catalogueSHA256: String, objectsSHA256: String
    public let entries: [RouteIndexEntry]

    public func validate(scene: Snapshot) throws {
        var identity = Data()
        for object in scene.objects {
            let bytes = Data(object.id.utf8)
            var length = UInt64(bytes.count).bigEndian
            withUnsafeBytes(of: &length) { identity.append(contentsOf: $0) }
            identity.append(bytes)
        }
        guard schema == 1, job == scene.job, revision == scene.revision,
              Snapshot.isDigest(catalogueSHA256), objectsSHA256 == SnapshotReader.digest(identity),
              entries.count <= scene.objects.count,
              Set(entries.map(\.routeID)).count == entries.count else { throw ABIError.invalid("Route catalogue index binding mismatch") }
        var seen = Set<Int>()
        for entry in entries {
            guard !entry.routeID.isEmpty, entry.routeID.count <= 256, !entry.objectIndices.isEmpty else { throw ABIError.invalid("Invalid route index entry") }
            for index in entry.objectIndices {
                guard scene.objects.indices.contains(index), seen.insert(index).inserted else { throw ABIError.invalid("Ambiguous route index membership") }
            }
        }
    }
}

public struct RouteGroupReference: Codable, Sendable {
    public let kind: String, id: String
}
public struct RouteMember: Codable, Sendable {
    public let objectID: String, sourceID: String
    public let currentPathSHA256: String, currentWkbSHA256: String, originalWkbSHA256: String
    public let points: [[Double]]
    public let groups: [RouteGroupReference]
}
public struct RoutePresentation: Codable, Sendable {
    public let schema: Int
    public let job: String, revision: String, routeID: String, catalogueSHA256: String, bindingSHA256: String, currentWkbSHA256: String
    public let displayHausdorffMM: Double
    public let assembled: ComparisonArtwork
    public let comparison: GrowthComparison?
    public let comparisonUnavailable: String?
    public let bounds: Bounds
    public let members: [RouteMember]
    public let groups: [RouteGroupReference]

    public func validate(scene: Snapshot, selected: SceneObject) throws {
        guard schema == 1, job == scene.job, revision == scene.revision, !routeID.isEmpty, routeID.count <= 256,
              [catalogueSHA256, bindingSHA256, currentWkbSHA256].allSatisfy(Snapshot.isDigest),
              displayHausdorffMM.isFinite, displayHausdorffMM >= 0, displayHausdorffMM <= 0.000500001,
              bounds.valid, !members.isEmpty, members.count <= 2048,
              Set(members.map(\.objectID)).count == members.count,
              Set(members.map(\.sourceID)).count == members.count,
              members.contains(where: { $0.objectID == selected.id && $0.sourceID == selected.sourceID }),
              members.reduce(0, { $0 + $1.points.count }) <= 100000,
              assembled.path.count <= 1024 * 1024 else { throw ABIError.invalid("Invalid route presentation") }
        let objects = Dictionary(uniqueKeysWithValues: scene.objects.map { ($0.id, $0) })
        func within(_ x: Double, _ y: Double) -> Bool {
            x >= bounds.x - 1e-6 && x <= bounds.x + bounds.width + 1e-6 &&
            y >= bounds.y - 1e-6 && y <= bounds.y + bounds.height + 1e-6
        }
        func validGroup(_ group: RouteGroupReference) -> Bool {
            ["straight", "arc"].contains(group.kind) && !group.id.isEmpty && group.id.count <= 512
        }
        for member in members {
            guard let object = objects[member.objectID], object.sourceID == member.sourceID,
                  object.layer == selected.layer,
                  member.currentPathSHA256 == SnapshotReader.digest(Data(object.path.utf8)),
                  Snapshot.isDigest(member.currentWkbSHA256), Snapshot.isDigest(member.originalWkbSHA256),
                  member.points.count >= 2, member.groups.allSatisfy(validGroup),
                  member.points.allSatisfy({ p in p.count == 2 && p.allSatisfy({ $0.isFinite && abs($0) < 1e7 }) && within(p[0],p[1]) }) else {
                throw ABIError.invalid("Route member/centerline binding mismatch")
            }
        }
        guard groups.allSatisfy(validGroup),
              Set(groups.map { $0.kind + ":" + $0.id }) == Set(members.flatMap(\.groups).map { $0.kind + ":" + $0.id }) else {
            throw ABIError.invalid("Route group references mismatch")
        }
        let b = assembled.bounds
        guard within(b.x,b.y), within(b.x+b.width,b.y+b.height) else { throw ABIError.invalid("Route bounds mismatch") }
        let object = SceneObject(id: selected.id, sourceID: selected.sourceID, layer: selected.layer,
                                 kind: "Maintained route", path: assembled.path, bounds: b, attributes: [:])
        try Snapshot(schema: 1, job: scene.job, revision: scene.revision, slice: "Route presentation", status: "Preview",
                     parentRevision: nil, bounds: b, affected: b, objects: [object], sources: scene.sources,
                     evidence: [], limitations: []).validate()
        if let comparison {
            guard comparison.currentWkbSHA256 == currentWkbSHA256 else {
                throw ABIError.invalid("Route growth comparison body mismatch")
            }
            try comparison.validate(scene: scene, selected: object)
        }
    }
}
