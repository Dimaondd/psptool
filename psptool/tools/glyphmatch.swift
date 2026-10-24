// Match 16x16 glyph tiles against characters rendered with system fonts.
// usage: glyphmatch TILES.raw CHARS.txt FONT[,FONT..] > out.tsv
//   TILES.raw: N*256 bytes of alpha; CHARS.txt: candidate chars (UTF-8)
// out: index \t best \t score \t second \t score
import Foundation
import CoreText
import CoreGraphics

let args = CommandLine.arguments
let tiles = [UInt8](try Data(contentsOf: URL(fileURLWithPath: args[1])))
let chars = Array(try String(contentsOfFile: args[2], encoding: .utf8)).filter { $0 != "\n" }
let fonts = args[3].split(separator: ",").map(String.init)
let N = tiles.count / 256
let R = 16, PAD = 2, W = R + 2 * PAD   // render with margin, match with shifts

func render(_ ch: Character, _ font: CTFont) -> [Float] {
    var buf = [UInt8](repeating: 0, count: W * W)
    let cs = CGColorSpaceCreateDeviceGray()
    buf.withUnsafeMutableBytes { p in
        let ctx = CGContext(data: p.baseAddress, width: W, height: W, bitsPerComponent: 8, bytesPerRow: W,
                            space: cs, bitmapInfo: CGImageAlphaInfo.none.rawValue)!
        ctx.setFillColor(gray: 1, alpha: 1)
        let s = NSAttributedString(string: String(ch), attributes: [kCTFontAttributeName as NSAttributedString.Key: font,
                                   kCTForegroundColorFromContextAttributeName as NSAttributedString.Key: true])
        let line = CTLineCreateWithAttributedString(s)
        let b = CTLineGetBoundsWithOptions(line, .useGlyphPathBounds)
        // centre ink box in the tile
        ctx.textPosition = CGPoint(x: CGFloat(W) / 2 - b.midX, y: CGFloat(W) / 2 - b.midY)
        CTLineDraw(line, ctx)
    }
    // CG origin is bottom-left; flip rows
    var out = [Float](repeating: 0, count: W * W)
    for y in 0..<W { for x in 0..<W { out[y * W + x] = Float(buf[(W - 1 - y) * W + x]) / 255 } }
    return out
}

// tiles as float, centred on ink box too
func tile(_ i: Int) -> [Float] {
    var minx = 16, maxx = -1, miny = 16, maxy = -1
    for y in 0..<16 { for x in 0..<16 where tiles[i * 256 + y * 16 + x] > 64 {
        minx = min(minx, x); maxx = max(maxx, x); miny = min(miny, y); maxy = max(maxy, y) } }
    var out = [Float](repeating: 0, count: W * W)
    if maxx < 0 { return out }
    let ox = W / 2 - (minx + maxx + 1) / 2, oy = W / 2 - (miny + maxy + 1) / 2
    for y in 0..<16 { for x in 0..<16 {
        let X = x + ox, Y = y + oy
        if X >= 0 && X < W && Y >= 0 && Y < W { out[Y * W + X] = Float(tiles[i * 256 + y * 16 + x]) / 255 } } }
    return out
}

func score(_ a: [Float], _ b: [Float]) -> Float {
    var best: Float = -1
    for dy in -1...1 { for dx in -1...1 {
        var ab: Float = 0, aa: Float = 0, bb: Float = 0
        for y in 1..<(W - 1) { for x in 1..<(W - 1) {
            let u = a[y * W + x], v = b[(y + dy) * W + x + dx]
            ab += u * v; aa += u * u; bb += v * v } }
        if aa > 0 && bb > 0 { best = max(best, ab / (aa * bb).squareRoot()) }
    } }
    return best
}

var cands: [(Character, [Float])] = []
for name in fonts {
    for size in [14.0, 15.0, 16.0] {
        let f = CTFontCreateWithName(name as CFString, CGFloat(size), nil)
        for c in chars { cands.append((c, render(c, f))) }
    }
}
let T = (0..<N).map(tile)
var lines = [String](repeating: "", count: N)
DispatchQueue.concurrentPerform(iterations: N) { i in
    var best: [Character: Float] = [:]
    let t = T[i]
    if t.allSatisfy({ $0 == 0 }) { lines[i] = "\(i)\t \t1\t \t0"; return }
    for (c, r) in cands { let s = score(t, r); if s > (best[c] ?? -2) { best[c] = s } }
    let top = best.sorted { $0.value > $1.value }.prefix(3)
    lines[i] = "\(i)\t" + top.map { "\($0.key)\t\(String(format: "%.3f", $0.value))" }.joined(separator: "\t")
}
print(lines.joined(separator: "\n"))
