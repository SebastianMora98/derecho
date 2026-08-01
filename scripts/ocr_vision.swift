// OCR con el framework Vision de macOS. No requiere instalar nada:
// Vision viene con el sistema y reconoce español mejor que tesseract sin
// entrenar. Lo usa scripts/ocr.py, que compila este archivo la primera vez.
//
// Uso:  ocr_vision <imagen> [imagen ...]
//
// Salida: una línea por renglón detectado, en TSV
//     minX <TAB> maxX <TAB> midY <TAB> texto
// con las coordenadas normalizadas (0-1, origen abajo-izquierda). Las
// imágenes se separan con \f. La geometría es necesaria para reconstruir
// los párrafos: la sangría de la primera línea es lo único que distingue
// un párrafo nuevo de la continuación del anterior.

import Foundation
import Vision
import AppKit

struct Renglon {
    let minX: Double, maxX: Double, midY: Double, texto: String
}

func reconocer(_ ruta: String) -> [Renglon] {
    guard let imagen = NSImage(contentsOfFile: ruta),
          let datos = imagen.tiffRepresentation,
          let mapa = NSBitmapImageRep(data: datos),
          let cg = mapa.cgImage
    else {
        FileHandle.standardError.write("ocr_vision: no pude leer \(ruta)\n".data(using: .utf8)!)
        return []
    }

    let peticion = VNRecognizeTextRequest()
    peticion.recognitionLevel = .accurate
    peticion.recognitionLanguages = ["es-ES"]
    peticion.usesLanguageCorrection = true

    do {
        try VNImageRequestHandler(cgImage: cg, options: [:]).perform([peticion])
    } catch {
        FileHandle.standardError.write("ocr_vision: falló \(ruta): \(error)\n".data(using: .utf8)!)
        return []
    }

    let observaciones = peticion.results ?? []
    // Vision no garantiza orden de lectura: ordenar de arriba hacia abajo y,
    // dentro de un mismo renglón, de izquierda a derecha.
    let ordenadas = observaciones.sorted { a, b in
        let dy = a.boundingBox.midY - b.boundingBox.midY
        if abs(dy) > 0.008 { return dy > 0 }
        return a.boundingBox.minX < b.boundingBox.minX
    }

    return ordenadas.compactMap { obs in
        guard let texto = obs.topCandidates(1).first?.string else { return nil }
        let caja = obs.boundingBox
        return Renglon(minX: caja.minX, maxX: caja.maxX, midY: caja.midY, texto: texto)
    }
}

let rutas = Array(CommandLine.arguments.dropFirst())
var salida: [String] = []
for ruta in rutas {
    let lineas = reconocer(ruta).map { r in
        let t = r.texto.replacingOccurrences(of: "\t", with: " ")
        return String(format: "%.4f\t%.4f\t%.4f\t", r.minX, r.maxX, r.midY) + t
    }
    salida.append(lineas.joined(separator: "\n"))
}
print(salida.joined(separator: "\u{0C}"))
