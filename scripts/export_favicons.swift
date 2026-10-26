#!/usr/bin/env swift
// macOS: swift scripts/export_favicons.swift
// Export the generated portrait with nearest-neighbor sampling to keep pixels crisp.
import AppKit
import Foundation

let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
let images = root.appendingPathComponent("images")
let source = images.appendingPathComponent("pixel-avatar.png")
guard let portrait = NSImage(contentsOf: source) else {
    fatalError("Cannot read \(source.path)")
}

func png(_ size: Int) throws -> Data {
    guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: size * 4, bitsPerPixel: 32),
        let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        fatalError("Cannot allocate icon bitmap")
    }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    context.imageInterpolation = .none
    context.shouldAntialias = false
    portrait.draw(in: NSRect(x: 0, y: 0, width: size, height: size),
                  from: .zero, operation: .copy, fraction: 1)
    NSGraphicsContext.restoreGraphicsState()
    guard let result = bitmap.representation(using: .png, properties: [:]) else {
        fatalError("Cannot encode icon PNG")
    }
    return result
}

for (name, size) in [("favicon-16x16.png", 16), ("favicon-32x32.png", 32),
                     ("apple-touch-icon.png", 180), ("android-chrome-192x192.png", 192),
                     ("android-chrome-512x512.png", 512)] {
    try png(size).write(to: images.appendingPathComponent(name), options: .atomic)
    print("Exported \(name)")
}

// ICO directory containing correctly sized PNG payloads.
func littleEndian<T: FixedWidthInteger>(_ value: T) -> Data {
    var bytes = value.littleEndian
    return withUnsafeBytes(of: &bytes) { Data($0) }
}
let sizes = [16, 32, 48]
let payloads = try sizes.map { try png($0) }
var ico = littleEndian(UInt16(0)) + littleEndian(UInt16(1)) + littleEndian(UInt16(sizes.count))
var offset = 6 + 16 * sizes.count
for (size, payload) in zip(sizes, payloads) {
    ico.append(contentsOf: [UInt8(size), UInt8(size), 0, 0])
    ico.append(littleEndian(UInt16(1)))
    ico.append(littleEndian(UInt16(32)))
    ico.append(littleEndian(UInt32(payload.count)))
    ico.append(littleEndian(UInt32(offset)))
    offset += payload.count
}
for payload in payloads { ico.append(payload) }
try ico.write(to: images.appendingPathComponent("favicon.ico"), options: .atomic)
print("Exported favicon.ico (16, 32, 48 px)")
