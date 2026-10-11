// Riconoscimento del testo (OCR) con il framework Vision di macOS.
// Uso: ocr <file immagine o PDF> [--langs it-IT,en-US]
// Scrive il testo su stdout: una pagina dopo l'altra, separate dal carattere \f.
// Su stderr scrive l'avanzamento come righe "PROGRESS <fatto> <totale>".

import AppKit
import Foundation
import ImageIO
import PDFKit
import Vision

func fail(_ message: String) -> Never {
    FileHandle.standardError.write((message + "\n").data(using: .utf8)!)
    exit(1)
}

func progress(_ done: Int, _ total: Int) {
    FileHandle.standardError.write("PROGRESS \(done) \(total)\n".data(using: .utf8)!)
}

var arguments = Array(CommandLine.arguments.dropFirst())
var languages = ["it-IT", "en-US"]
if let i = arguments.firstIndex(of: "--langs"), i + 1 < arguments.count {
    languages = arguments[i + 1].split(separator: ",").map(String.init)
    arguments.removeSubrange(i...(i + 1))
}
guard let inputPath = arguments.first else { fail("Uso: ocr <file> [--langs it-IT,en-US]") }
let url = URL(fileURLWithPath: inputPath)

// Ricompone le righe riconosciute in paragrafi in base alla distanza verticale.
func recognize(_ image: CGImage) throws -> String {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    if #available(macOS 13.0, *) {
        request.automaticallyDetectsLanguage = true
    }
    let supported = (try? request.supportedRecognitionLanguages()) ?? []
    let wanted = languages.filter { supported.contains($0) }
    if !wanted.isEmpty { request.recognitionLanguages = wanted }

    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])
    let observations = (request.results ?? []).sorted { a, b in
        // dall'alto verso il basso (in Vision l'origine è in basso a sinistra), poi da sinistra a destra
        if abs(a.boundingBox.midY - b.boundingBox.midY) > min(a.boundingBox.height, b.boundingBox.height) * 0.5 {
            return a.boundingBox.midY > b.boundingBox.midY
        }
        return a.boundingBox.minX < b.boundingBox.minX
    }

    var paragraphs: [String] = []
    var current = ""
    var previous: CGRect? = nil
    for observation in observations {
        guard let text = observation.topCandidates(1).first?.string else { continue }
        let box = observation.boundingBox
        if let prev = previous {
            let gap = prev.minY - box.maxY
            let sameLine = abs(prev.midY - box.midY) < box.height * 0.5
            if sameLine {
                current += "  " + text
            } else if gap > box.height * 0.9 || abs(prev.minX - box.minX) > 0.08 {
                paragraphs.append(current)
                current = text
            } else {
                // parola spezzata a fine riga: si ricongiunge
                if current.hasSuffix("-") {
                    current = String(current.dropLast()) + text
                } else {
                    current += " " + text
                }
            }
        } else {
            current = text
        }
        previous = box
    }
    if !current.isEmpty { paragraphs.append(current) }
    return paragraphs.joined(separator: "\n\n")
}

func render(_ page: PDFPage, scale: CGFloat) -> CGImage? {
    let bounds = page.bounds(for: .mediaBox)
    let width = Int(bounds.width * scale)
    let height = Int(bounds.height * scale)
    guard width > 0, height > 0,
          let context = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return nil }
    context.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    context.scaleBy(x: scale, y: scale)
    context.translateBy(x: -bounds.minX, y: -bounds.minY)
    page.draw(with: .mediaBox, to: context)
    return context.makeImage()
}

var pages: [String] = []
do {
    if url.pathExtension.lowercased() == "pdf" {
        guard let document = PDFDocument(url: url) else { fail("Impossibile aprire il PDF") }
        let count = document.pageCount
        for index in 0..<count {
            guard let page = document.page(at: index), let image = render(page, scale: 2.5) else {
                pages.append("")
                continue
            }
            pages.append(try recognize(image))
            progress(index + 1, count)
        }
    } else {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { fail("Impossibile leggere l'immagine") }
        pages.append(try recognize(image))
        progress(1, 1)
    }
} catch {
    fail("Riconoscimento del testo non riuscito: \(error.localizedDescription)")
}

FileHandle.standardOutput.write(pages.joined(separator: "\n\u{0C}\n").data(using: .utf8)!)
