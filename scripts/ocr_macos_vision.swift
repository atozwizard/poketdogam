import AppKit
import Foundation
import Vision

guard CommandLine.arguments.count >= 2 else {
    fputs("usage: ocr_macos_vision.swift <image-path>\n", stderr)
    exit(64)
}

let imageURL = URL(fileURLWithPath: CommandLine.arguments[1])
guard
    let image = NSImage(contentsOf: imageURL),
    let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let cgImage = bitmap.cgImage
else {
    fputs("unable to decode image\n", stderr)
    exit(65)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true

let preferredLanguages = ["ko-KR", "en-US", "ja-JP"]
if let supportedLanguages = try? request.supportedRecognitionLanguages() {
    let selected = preferredLanguages.filter { supportedLanguages.contains($0) }
    if !selected.isEmpty {
        request.recognitionLanguages = selected
    }
}

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
} catch {
    fputs("Vision OCR failed: \(error.localizedDescription)\n", stderr)
    exit(70)
}

let observations = (request.results ?? []).sorted { left, right in
    let verticalDistance = abs(left.boundingBox.midY - right.boundingBox.midY)
    if verticalDistance > 0.025 {
        return left.boundingBox.midY > right.boundingBox.midY
    }
    return left.boundingBox.minX < right.boundingBox.minX
}

for observation in observations {
    if let candidate = observation.topCandidates(1).first {
        print(candidate.string)
    }
}
