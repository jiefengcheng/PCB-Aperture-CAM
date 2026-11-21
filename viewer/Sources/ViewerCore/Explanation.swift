import Foundation

public struct ViewerExplanation: Codable, Sendable {
    public let schema: Int
    public let job: String, revision: String, objectID: String, sourceID: String
    public let author: String, text: String
    public let evidence: [String]
    public let comparison: GrowthComparison?
    public let route: RoutePresentation?
    public let routeUnavailable: String?
    public let routeIndex: RouteCatalogueIndex?
}
public struct ComparisonArtwork: Codable, Sendable {
    public let path: String
    public let bounds: Bounds
}
public struct GrowthComparison: Codable, Sendable {
    public let schema: Int
    public let selectedPathSHA256: String, originalWkbSHA256: String, currentWkbSHA256: String
    public let original: ComparisonArtwork
    public let added: ComparisonArtwork?, removed: ComparisonArtwork?
    public let addedAreaMM2: Double, removedAreaMM2: Double, displayHausdorffMM: Double
    public let summary: String, snapshotNote: String

    func validate(scene: Snapshot, selected: SceneObject) throws {
        guard schema == 1, selectedPathSHA256 == SnapshotReader.digest(Data(selected.path.utf8)),
              Snapshot.isDigest(originalWkbSHA256), Snapshot.isDigest(currentWkbSHA256),
              [addedAreaMM2, removedAreaMM2, displayHausdorffMM].allSatisfy({ $0.isFinite && $0 >= 0 }),
              displayHausdorffMM <= 0.000500001, !summary.isEmpty, summary.count <= 1000,
              snapshotNote.count <= 2000 else { throw ABIError.invalid("Growth comparison binding mismatch") }
        for artwork in [original, added, removed].compactMap({ $0 }) {
            guard artwork.path.count <= 1024 * 1024 else { throw ABIError.invalid("Growth comparison resource limit") }
            let object = SceneObject(id: selected.id, sourceID: selected.sourceID, layer: selected.layer,
                                     kind: selected.kind, path: artwork.path, bounds: artwork.bounds, attributes: [:])
            // Use the same data-only polygon grammar, finite-coordinate and bounds checks.
            try Snapshot(schema: 1, job: scene.job, revision: scene.revision, slice: "Source comparison", status: "Preview",
                         parentRevision: nil, bounds: artwork.bounds, affected: artwork.bounds, objects: [object],
                         sources: scene.sources, evidence: [], limitations: []).validate()
        }
    }
}
private struct ExplanationEnvelope: Decodable {
    let schema: Int
    let sha256: String
    let payloadBase64: String
}
public enum ExplanationReader {
    public static func decode(_ data: Data, scene: Snapshot, selectedID: String) throws -> ViewerExplanation {
        guard data.count <= 2 * 1024 * 1024 else { throw ABIError.invalid("Explanation resource limit") }
        let envelope = try JSONDecoder().decode(ExplanationEnvelope.self, from: data)
        guard envelope.schema == 1, let payload = Data(base64Encoded: envelope.payloadBase64),
              payload.count <= 1024 * 1024, SnapshotReader.digest(payload) == envelope.sha256 else { throw ABIError.invalid("Explanation checksum mismatch") }
        let explanation = try JSONDecoder().decode(ViewerExplanation.self, from: payload)
        guard explanation.schema == 1, explanation.job == scene.job, explanation.revision == scene.revision,
              explanation.objectID == selectedID,
              scene.objects.contains(where: { $0.id == selectedID && $0.sourceID == explanation.sourceID }),
              !explanation.author.isEmpty, !explanation.text.isEmpty, explanation.text.count <= 48_000,
              !explanation.evidence.isEmpty else { throw ABIError.invalid("Explanation selection/revision mismatch") }
        if let comparison = explanation.comparison,
           let selected = scene.objects.first(where: { $0.id == selectedID }) {
            try comparison.validate(scene: scene, selected: selected)
        }
        if let route = explanation.route,
           let selected = scene.objects.first(where: { $0.id == selectedID }) {
            try route.validate(scene: scene, selected: selected)
        }
        try explanation.routeIndex?.validate(scene: scene)
        if let route = explanation.route, let index = explanation.routeIndex {
            guard let entry = index.entries.first(where: { $0.routeID == route.routeID }),
                  Set(entry.objectIndices.map { scene.objects[$0].id }) == Set(route.members.map(\.objectID)) else {
                throw ABIError.invalid("Route presentation differs from maintained membership")
            }
        }
        return explanation
    }
    public static func read(_ url: URL, scene: Snapshot, selectedID: String) throws -> ViewerExplanation {
        try decode(SnapshotReader.limitedData(url, limit: 2 * 1024 * 1024), scene: scene, selectedID: selectedID)
    }
}
