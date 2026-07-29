import AppKit
import Foundation

guard CommandLine.arguments.count >= 3 else {
    fputs("usage: render_ocr_fixture.swift <text-file> <png-output>\n", stderr)
    exit(64)
}

let textURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
let text = try String(contentsOf: textURL, encoding: .utf8)
let size = NSSize(width: 1200, height: 760)
let image = NSImage(size: size)

image.lockFocus()
NSColor(calibratedWhite: 0.97, alpha: 1).setFill()
NSBezierPath(rect: NSRect(origin: .zero, size: size)).fill()

let paragraph = NSMutableParagraphStyle()
paragraph.lineSpacing = 14
let attributes: [NSAttributedString.Key: Any] = [
    .font: NSFont(name: "Apple SD Gothic Neo", size: 64) ?? NSFont.systemFont(ofSize: 64),
    .foregroundColor: NSColor(calibratedWhite: 0.08, alpha: 1),
    .paragraphStyle: paragraph,
]
text.draw(
    in: NSRect(x: 90, y: 90, width: size.width - 180, height: size.height - 180),
    withAttributes: attributes
)
image.unlockFocus()

guard
    let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let png = bitmap.representation(using: .png, properties: [:])
else {
    fputs("unable to render fixture image\n", stderr)
    exit(65)
}
try png.write(to: outputURL)
