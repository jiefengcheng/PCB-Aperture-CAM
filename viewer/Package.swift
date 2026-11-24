// swift-tools-version: 6.0
import PackageDescription
let package = Package(name: "GerberViewer", platforms: [.macOS(.v15)], products: [.executable(name: "GerberViewer", targets: ["GerberViewer"])], targets: [
    .target(name: "ViewerCore"),
    .executableTarget(name: "GerberViewer", dependencies: ["ViewerCore"], resources: [.copy("Resources/canvas.html"), .copy("Resources/t04.js")]),
    .testTarget(name: "ViewerCoreTests", dependencies: ["ViewerCore"])
])
