// Draws the app icon (1024x1024 PNG) for the Vivaldi Profile Launcher.
// Run: swift make_icon.swift <out.png>
// No third-party dependencies – uses AppKit/CoreGraphics.

import AppKit

let outPath = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "icon.png"
let S: CGFloat = 1024

let rep = NSBitmapImageRep(
    bitmapDataPlanes: nil, pixelsWide: Int(S), pixelsHigh: Int(S),
    bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
    colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let ctx = NSGraphicsContext.current!.cgContext

// --- Rounded tile with a Vivaldi-red gradient -----------------------------
let pad: CGFloat = 80
let tile = CGRect(x: pad, y: pad, width: S - 2 * pad, height: S - 2 * pad)
let radius: CGFloat = (S - 2 * pad) * 0.2237   // macOS squircle-ish radius
let tilePath = NSBezierPath(roundedRect: tile, xRadius: radius, yRadius: radius)
tilePath.addClip()

let topColor = NSColor(calibratedRed: 0.937, green: 0.243, blue: 0.259, alpha: 1) // #EF3E42
let botColor = NSColor(calibratedRed: 0.733, green: 0.122, blue: 0.149, alpha: 1) // #BB1F26
let gradient = NSGradient(starting: topColor, ending: botColor)!
gradient.draw(in: tile, angle: -90)

// Subtle gloss along the top.
let glossTop = NSColor(white: 1, alpha: 0.16)
let glossBot = NSColor(white: 1, alpha: 0.0)
let gloss = NSGradient(starting: glossTop, ending: glossBot)!
gloss.draw(in: CGRect(x: tile.minX, y: tile.midY, width: tile.width, height: tile.height / 2), angle: -90)

// --- White "V" ------------------------------------------------------------
let vText = "V"
let font = NSFont.systemFont(ofSize: 620, weight: .bold)
let attrs: [NSAttributedString.Key: Any] = [
    .font: font,
    .foregroundColor: NSColor.white,
]
let str = NSAttributedString(string: vText, attributes: attrs)
let textSize = str.size()
// Nudged up/left to leave room for the magnifying glass.
let tx = (S - textSize.width) / 2 - 40
let ty = (S - textSize.height) / 2 + 40
str.draw(at: CGPoint(x: tx, y: ty))

// --- Magnifying glass (search) at the bottom right ------------------------
ctx.setShouldAntialias(true)
let glassCenter = CGPoint(x: S * 0.66, y: S * 0.40)
let glassR: CGFloat = 110
let ring = NSBezierPath(ovalIn: CGRect(
    x: glassCenter.x - glassR, y: glassCenter.y - glassR,
    width: glassR * 2, height: glassR * 2))
ring.lineWidth = 46
NSColor.white.setStroke()
// Dark "glass" fill for contrast against the V.
NSColor(white: 0.0, alpha: 0.16).setFill()
ring.fill()
ring.stroke()

// Handle.
let handle = NSBezierPath()
let a = CGPoint(x: glassCenter.x + glassR * 0.72, y: glassCenter.y - glassR * 0.72)
let b = CGPoint(x: a.x + 92, y: a.y - 92)
handle.move(to: a)
handle.line(to: b)
handle.lineWidth = 56
handle.lineCapStyle = .round
NSColor.white.setStroke()
handle.stroke()

NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else {
    FileHandle.standardError.write("Could not create PNG\n".data(using: .utf8)!)
    exit(1)
}
try! png.write(to: URL(fileURLWithPath: outPath))
print("Wrote \(outPath)")
