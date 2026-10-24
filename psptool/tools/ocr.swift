// OCR for glyph tiles with macOS Vision.
// usage: swift ocr.swift DIR > out.json   (DIR holds NNNN.png)
import Foundation
import Vision
import AppKit

let dir = CommandLine.arguments[1]
let files = try FileManager.default.contentsOfDirectory(atPath: dir).filter { $0.hasSuffix(".png") }.sorted()
var result: [String: [String]] = [:]
for f in files {
    guard let img = NSImage(contentsOfFile: dir + "/" + f),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["ja-JP"]
    req.usesLanguageCorrection = false
    req.minimumTextHeight = 0
    try? VNImageRequestHandler(cgImage: cg).perform([req])
    var cands: [String] = []
    for obs in req.results ?? [] {
        for c in obs.topCandidates(3) { cands.append(c.string) }
    }
    result[String(f.dropLast(4))] = cands
}
let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
