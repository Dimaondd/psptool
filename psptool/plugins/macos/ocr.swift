// Text recognition with macOS Vision: ocr <lang> <image>... -> one JSON line per image
// {"file": ..., "lines": [{"text": ..., "x": ..., "y": ..., "w": ..., "h": ..., "conf": ...}]}
// Coordinates are fractions of the image, origin top-left.
import Foundation
import Vision

let args = CommandLine.arguments
if args.count < 3 {
    FileHandle.standardError.write("usage: ocr <lang> <image>...\n".data(using: .utf8)!)
    exit(2)
}
let lang = args[1]
for path in args.dropFirst(2) {
    var lines: [[String: Any]] = []
    let url = URL(fileURLWithPath: path)
    let req = VNRecognizeTextRequest { req, _ in
        for case let obs as VNRecognizedTextObservation in req.results ?? [] {
            guard let best = obs.topCandidates(1).first else { continue }
            let b = obs.boundingBox
            lines.append(["text": best.string, "conf": best.confidence,
                          "x": b.minX, "y": 1 - b.maxY, "w": b.width, "h": b.height])
        }
    }
    req.recognitionLevel = .accurate
    req.recognitionLanguages = [lang]
    req.usesLanguageCorrection = true
    do {
        try VNImageRequestHandler(url: url).perform([req])
    } catch {
        FileHandle.standardError.write("\(path): \(error)\n".data(using: .utf8)!)
    }
    let out: [String: Any] = ["file": path, "lines": lines]
    let data = try! JSONSerialization.data(withJSONObject: out)
    print(String(data: data, encoding: .utf8)!)
}
