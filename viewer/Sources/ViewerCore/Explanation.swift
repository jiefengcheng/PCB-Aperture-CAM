import Foundation

public struct ViewerExplanation: Codable, Sendable {
    public let schema: Int
    public let job: String, revision: String, objectID: String, sourceID: String
    public let author: String, text: String
    public let evidence: [String]
}
private struct ExplanationEnvelope: Decodable {
    let schema: Int
    let sha256: String
    let payloadBase64: String
}
public enum ExplanationReader {
    public static func decode(_ data: Data, scene: Snapshot, selectedID: String) throws -> ViewerExplanation {
        guard data.count <= 128 * 1024 else { throw ABIError.invalid("Explanation resource limit") }
        let envelope = try JSONDecoder().decode(ExplanationEnvelope.self, from: data)
        guard envelope.schema == 1, let payload = Data(base64Encoded: envelope.payloadBase64),
              payload.count <= 64 * 1024, SnapshotReader.digest(payload) == envelope.sha256 else { throw ABIError.invalid("Explanation checksum mismatch") }
        let explanation = try JSONDecoder().decode(ViewerExplanation.self, from: payload)
        guard explanation.schema == 1, explanation.job == scene.job, explanation.revision == scene.revision,
              explanation.objectID == selectedID,
              scene.objects.contains(where: { $0.id == selectedID && $0.sourceID == explanation.sourceID }),
              !explanation.author.isEmpty, !explanation.text.isEmpty, explanation.text.count <= 48_000,
              !explanation.evidence.isEmpty else { throw ABIError.invalid("Explanation selection/revision mismatch") }
        return explanation
    }
    public static func read(_ url: URL, scene: Snapshot, selectedID: String) throws -> ViewerExplanation {
        try decode(SnapshotReader.limitedData(url, limit: 128 * 1024), scene: scene, selectedID: selectedID)
    }
}
