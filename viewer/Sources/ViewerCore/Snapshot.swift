import Foundation
import CryptoKit

public struct Bounds: Codable, Equatable, Sendable {
    public let x: Double, y: Double, width: Double, height: Double
    public var valid: Bool { [x,y,width,height].allSatisfy { $0.isFinite && abs($0) < 1e7 } && width > 0 && height > 0 }
}
public struct SceneObject: Codable, Sendable {
    public let id: String, sourceID: String, layer: String, kind: String, path: String
    public let bounds: Bounds
    public let attributes: [String: [String]]
}
public struct SourceRecord: Codable, Sendable {
    public let name: String, sha256: String, layer: String
}
public struct Snapshot: Codable, Sendable {
    public let schema: Int
    public let job: String, revision: String, slice: String, status: String
    public let parentRevision: String?
    public let bounds: Bounds, affected: Bounds
    public let objects: [SceneObject]
    public let sources: [SourceRecord]
    public let evidence: [String]
    public let limitations: [String]
    public func validate() throws {
        guard schema == 1, !job.isEmpty, !revision.isEmpty, !slice.isEmpty,
              ["Preview", "Verified", "Failed"].contains(status),
              bounds.valid, affected.valid, !objects.isEmpty, objects.count <= 200_000,
              Set(objects.map(\.id)).count == objects.count,
              !sources.isEmpty, Set(sources.map(\.layer)).count == sources.count, sources.allSatisfy({ Self.isDigest($0.sha256) }) else { throw ABIError.invalid("Invalid snapshot header or identities") }
        // Data paths only: forbid arbitrary SVG, links, scripts and non-finite coordinates.
        for object in objects {
            guard !object.id.isEmpty, !object.sourceID.isEmpty, !object.layer.isEmpty,
                  object.bounds.valid, object.path.count <= 8_000_000,
                  sources.contains(where: { $0.layer == object.layer && object.sourceID.hasPrefix($0.sha256 + ":") }) else { throw ABIError.invalid("Invalid object geometry") }
            let values = try Self.polygonCoordinates(object.path)
            let xs = stride(from: 0, to: values.count, by: 2).map { values[$0] }
            let ys = stride(from: 1, to: values.count, by: 2).map { values[$0] }
            let b = object.bounds, tolerance = 1e-6
            guard let minX = xs.min(), let maxX = xs.max(), let minY = ys.min(), let maxY = ys.max(),
                  abs(b.x-minX) <= tolerance, abs(b.y-minY) <= tolerance,
                  abs(b.width-(maxX-minX)) <= tolerance, abs(b.height-(maxY-minY)) <= tolerance,
                  b.x >= bounds.x-tolerance, b.y >= bounds.y-tolerance,
                  b.x+b.width <= bounds.x+bounds.width+tolerance,
                  b.y+b.height <= bounds.y+bounds.height+tolerance else { throw ABIError.invalid("Geometry bounds mismatch") }

        }
        if status == "Verified" && evidence.isEmpty { throw ABIError.invalid("Verified requires scoped evidence references") }
    }
    static func polygonCoordinates(_ path: String) throws -> [Double] {
        // A linear scanner avoids ICU backtracking limits on detailed joint contours.
        let allowed = CharacterSet(charactersIn: "MLZ0123456789., +-eE\n\r\t")
        guard path.unicodeScalars.allSatisfy({ allowed.contains($0) }) else { throw ABIError.invalid("Invalid polygon characters") }
        let tokens = path.replacingOccurrences(of: ",", with: " ").split(whereSeparator: { $0.isWhitespace })
        var values: [Double] = [], i = 0, vertices = 0, open = false
        while i < tokens.count {
            let command = tokens[i]; i += 1
            if command == "Z" {
                guard open, vertices >= 3 else { throw ABIError.invalid("Incomplete polygon contour") }
                open = false; continue
            }
            guard (command == "M" && !open) || (command == "L" && open), i + 1 < tokens.count,
                  let x = Double(tokens[i]), let y = Double(tokens[i+1]),
                  x.isFinite, y.isFinite, abs(x) < 1e7, abs(y) < 1e7 else { throw ABIError.invalid("Invalid polygon coordinates") }
            if command == "M" { open = true; vertices = 0 }
            vertices += 1; values.append(contentsOf: [x,y]); i += 2
        }
        guard !open, !values.isEmpty else { throw ABIError.invalid("Unclosed polygon contour") }
        return values
    }
    public static func isDigest(_ value: String) -> Bool { value.count == 64 && value.allSatisfy { "0123456789abcdef".contains($0) } }
}
public enum ABIError: Error, LocalizedError {
    case invalid(String)
    public var errorDescription: String? { if case .invalid(let s) = self { return s }; return nil }
}
public struct Manifest: Codable, Sendable {
    public let schema: Int
    public let payload: String, sha256: String
    public let previousPayload: String?, previousSHA256: String?
}
public struct LoadedRevision: Sendable {
    public let current: Snapshot, previous: Snapshot?
    public let digest: String
    public let manifestDigest: String
}
public enum SnapshotReader {
    public static func digest(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
    public static func read(workspace: URL) throws -> LoadedRevision {
        let root = workspace.resolvingSymlinksInPath().standardizedFileURL
        let manifestData = try limitedData(root.appendingPathComponent("current.json"), limit: 16_384)
        let manifest = try JSONDecoder().decode(Manifest.self, from: manifestData)
        guard manifest.schema == 1 else { throw ABIError.invalid("Unsupported manifest") }
        func scene(_ file: String, _ hash: String) throws -> Snapshot {
            guard file == hash + ".json", Snapshot.isDigest(hash) else { throw ABIError.invalid("Invalid content-addressed payload") }
            let url = root.appendingPathComponent("snapshots").appendingPathComponent(file).resolvingSymlinksInPath()
            guard url.deletingLastPathComponent().path == root.appendingPathComponent("snapshots").path else { throw ABIError.invalid("Payload escapes workspace") }
            let data = try limitedData(url, limit: 128 * 1024 * 1024)
            guard digest(data) == hash else { throw ABIError.invalid("Snapshot checksum mismatch") }
            let snapshot = try JSONDecoder().decode(Snapshot.self, from: data)
            try snapshot.validate()
            return snapshot
        }
        let current = try scene(manifest.payload, manifest.sha256)
        var previous: Snapshot?
        if let file = manifest.previousPayload, let hash = manifest.previousSHA256 {
            previous = try scene(file, hash)
            guard previous?.revision == current.parentRevision, previous?.job == current.job,
                  previous?.revision != current.revision else { throw ABIError.invalid("Broken revision chain") }
        } else if manifest.previousPayload != nil || manifest.previousSHA256 != nil || current.parentRevision != nil {
            throw ABIError.invalid("Missing parent snapshot")
        }
        return LoadedRevision(current: current, previous: previous, digest: manifest.sha256, manifestDigest: digest(manifestData))
    }
    static func limitedData(_ url: URL, limit: Int) throws -> Data {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        let data = try handle.read(upToCount: limit + 1) ?? Data()
        guard data.count <= limit else { throw ABIError.invalid("Payload resource limit") }
        return data
    }
}
