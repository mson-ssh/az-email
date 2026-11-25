// Đọc chữ trong ảnh bằng Apple Vision (chạy trên máy, không gửi ảnh ra ngoài) – dùng cho trang gửi key (web.py).
//   swiftc -O app/ocr.swift -o data/.ocr-vision      (web.py tự biên dịch lần đầu, chỉ macOS)
//   data/.ocr-vision <ảnh>   → in từng dòng chữ, theo thứ tự trên → dưới
import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1,
      let img = NSImage(contentsOfFile: CommandLine.arguments[1]),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("Không đọc được ảnh\n".data(using: .utf8)!); exit(1)
}
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = false            // key / mã sản phẩm không phải từ điển
let langs = (try? req.supportedRecognitionLanguages()) ?? []
req.recognitionLanguages = ["vi-VT", "en-US"].filter { langs.contains($0) }
try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
let obs = (req.results ?? []).sorted { a, b in
    abs(a.boundingBox.midY - b.boundingBox.midY) > 0.01 ? a.boundingBox.midY > b.boundingBox.midY : a.boundingBox.minX < b.boundingBox.minX
}
for o in obs { if let t = o.topCandidates(1).first { print(t.string) } }
