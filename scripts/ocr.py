#!/usr/bin/env python3
"""OCR de PDF escaneados (sin capa de texto) usando el framework Vision de macOS.

`markitdown` solo extrae texto ya presente en el PDF. Un escaneo no tiene
ninguno, así que devuelve un `libro.md` vacío. Este módulo cubre ese caso:

    1. `pdftoppm` rasteriza cada página (poppler, ya instalado con brew).
    2. `ocr_vision.swift` reconoce el texto con Vision — viene con el sistema,
       no hay que instalar tesseract ni pagar una API.
    3. Se reconstruyen los párrafos a partir de la sangría de cada renglón,
       se rearman las palabras cortadas con guión y se conservan los números
       de página del original en marcas `<!-- p. N -->`.

Esas marcas son lo que permite citar por página real. La conversión de un PDF
con capa de texto suele perderlas; un escaneo bien procesado no.

Los libros escaneados a doble página (un pliego por hoja, típico de fotocopia)
se detectan por la proporción de la hoja y se parten al medio antes del OCR:
si no, el OCR mezcla las dos columnas de texto de páginas distintas.

Uso directo:
    uv run scripts/ocr.py entrada/libro.pdf            # imprime el markdown
    uv run scripts/ocr.py entrada/libro.pdf -o libro.md
"""

from __future__ import annotations

import argparse
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
FUENTE_SWIFT = AQUI / "ocr_vision.swift"
BINARIO = AQUI / ".ocr_vision"  # compilado al vuelo, fuera de git

DPI = 300
# Una hoja más ancha que alta contiene, casi siempre, dos páginas de libro.
PROPORCION_PLIEGO = 1.15
# Cuánto más a la derecha tiene que empezar un renglón (en fracción del ancho
# de la página) para considerarlo primera línea de un párrafo nuevo.
SANGRIA = 0.022
# Renglones cuyo centro vertical difiere menos que esto son la misma fila.
TOLERANCIA_FILA = 0.008
# El encabezado se separa del cuerpo por un blanco mayor que el interlineado
# normal; este es el múltiplo a partir del cual se considera separación.
SALTO_ENCABEZADO = 1.6
# Cuántas filas puede ocupar el encabezado. Son dos y no una porque en un
# escaneo torcido el folio y el título corriente caen a alturas distintas.
MAX_FILAS_ENCABEZADO = 2
# Un encabezado más largo que esto es texto del cuerpo, no una cabecera.
MAX_LARGO_ENCABEZADO = 70
# Cuántas veces tiene que repetirse un texto de cabecera para darlo por título
# corriente y borrarlo del cuerpo. Una frase del autor no se repite tanto.
MIN_REPETICIONES_CABECERA = 5


# --------------------------------------------------------------------------- #
# herramientas externas
# --------------------------------------------------------------------------- #


def exigir(programa: str, ayuda: str) -> str:
    ruta = shutil.which(programa)
    if not ruta:
        raise SystemExit(f"error: falta '{programa}'. {ayuda}")
    return ruta


def compilar_ocr() -> Path:
    """Compila el helper de Vision si hace falta. Tarda ~2s la primera vez."""
    if BINARIO.exists() and BINARIO.stat().st_mtime >= FUENTE_SWIFT.stat().st_mtime:
        return BINARIO
    exigir("swiftc", "Instalá las herramientas de línea de comandos de Xcode: xcode-select --install")
    print("→ compilando el OCR de Vision ...", file=sys.stderr, flush=True)
    subprocess.run(["swiftc", "-O", "-o", str(BINARIO), str(FUENTE_SWIFT)], check=True)
    return BINARIO


def medir_pagina(pdf: Path, numero: int | None = None) -> tuple[float, float, int]:
    """Devuelve (ancho, alto, cantidad de páginas) en puntos.

    Sin `numero`, `pdfinfo` informa el tamaño de la página 1 nada más. Eso
    alcanza para casi todos los PDF, pero no para un escaneo cuya portada
    quedó apaisada (todo el pliego) mientras el cuerpo es retrato normal: ahí
    hay que poder pedir el tamaño de una página interior específica.
    """
    exigir("pdfinfo", "Instalá poppler: brew install poppler")
    orden = ["pdfinfo", str(pdf)]
    if numero is not None:
        orden += ["-f", str(numero), "-l", str(numero)]
    salida = subprocess.run(orden, capture_output=True, text=True, check=True).stdout
    ancho = alto = 0.0
    paginas = 0
    for linea in salida.splitlines():
        if linea.startswith("Page size:") or re.match(r"Page\s+\d+ size:", linea):
            m = re.search(r"([\d.]+) x ([\d.]+)", linea)
            if m:
                ancho, alto = float(m.group(1)), float(m.group(2))
        elif linea.startswith("Pages:"):
            paginas = int(linea.split(":", 1)[1])
    if not paginas:
        raise SystemExit(f"error: no pude leer el PDF {pdf}")
    return ancho, alto, paginas


def rasterizar(pdf: Path, carpeta: Path, mitades: int, dpi: int, desde: int, hasta: int) -> list[Path]:
    """Rasteriza el PDF a PNG. Con mitades=2 corta cada hoja en dos páginas."""
    exigir("pdftoppm", "Instalá poppler: brew install poppler")

    if mitades == 1:
        # Sin recorte: cada página se rasteriza a su propio tamaño nativo. Si
        # se forzara igual un -W/-H fijo (medido de una sola página), un PDF
        # con tamaños mezclados —una portada apaisada y el cuerpo en retrato,
        # el caso real que hizo falta esto— recortaría o dejaría margen de
        # más en las páginas que no midan lo mismo que la que se usó de
        # referencia.
        orden = ["pdftoppm", "-png", "-r", str(dpi), "-f", str(desde), "-l", str(hasta), str(pdf), str(carpeta / "m0")]
        subprocess.run(orden, check=True, capture_output=True)
        return sorted(carpeta.glob("m0*.png"))

    ancho_pt, alto_pt, _ = medir_pagina(pdf)
    ancho_px = round(ancho_pt * dpi / 72)
    alto_px = round(alto_pt * dpi / 72)

    imagenes: list[Path] = []
    for indice in range(mitades):
        prefijo = carpeta / f"m{indice}"
        orden = [
            "pdftoppm", "-png", "-r", str(dpi),
            "-f", str(desde), "-l", str(hasta),
            "-W", str(ancho_px // mitades), "-H", str(alto_px),
            "-x", str(indice * (ancho_px // mitades)), "-y", "0",
            str(pdf), str(prefijo),
        ]
        subprocess.run(orden, check=True, capture_output=True)

    # Intercalar: hoja 1 izquierda, hoja 1 derecha, hoja 2 izquierda, ...
    por_hoja: dict[str, list[Path]] = {}
    for img in sorted(carpeta.glob("m*.png")):
        por_hoja.setdefault(img.stem.split("-", 1)[1], []).append(img)
    for hoja in sorted(por_hoja):
        imagenes += sorted(por_hoja[hoja], key=lambda p: p.stem)
    return imagenes


def reconocer(imagenes: list[Path], lote: int = 20) -> list[list[tuple[float, float, float, str]]]:
    """Corre el OCR y devuelve, por imagen, la lista de renglones con geometría."""
    binario = compilar_ocr()
    paginas: list[list[tuple[float, float, float, str]]] = []
    for inicio in range(0, len(imagenes), lote):
        grupo = imagenes[inicio : inicio + lote]
        print(f"  OCR {inicio + 1}-{inicio + len(grupo)} de {len(imagenes)} ...", file=sys.stderr, flush=True)
        proceso = subprocess.run(
            [str(binario), *map(str, grupo)], capture_output=True, text=True, check=True
        )
        for bruto in proceso.stdout.split("\f"):
            renglones = []
            for linea in bruto.splitlines():
                partes = linea.split("\t", 3)
                if len(partes) == 4:
                    renglones.append((float(partes[0]), float(partes[1]), float(partes[2]), partes[3]))
            paginas.append(renglones)
    return paginas[: len(imagenes)]


# --------------------------------------------------------------------------- #
# reconstrucción del texto
# --------------------------------------------------------------------------- #


def agrupar_filas(renglones: list) -> list[list]:
    """Agrupa en una sola fila los renglones que están a la misma altura.

    El título corriente y el folio comparten fila, y hay que tratarlos juntos
    para medir bien el blanco que los separa del cuerpo.
    """
    filas: list[list] = []
    for r in renglones:
        if filas and abs(filas[-1][0][2] - r[2]) <= TOLERANCIA_FILA:
            filas[-1].append(r)
        else:
            filas.append([r])
    return filas


def separar_encabezado(renglones: list) -> tuple[str | None, list, str]:
    """Quita el título corriente y el folio; devuelve (folio, cuerpo, encabezado).

    No usa una franja fija: identifica el encabezado por el blanco que lo
    separa del cuerpo, comparado con el interlineado de la propia página. Así
    funciona igual a cualquier dpi y con márgenes distintos.

    El encabezado puede ocupar DOS filas y no una: si el escaneo está torcido,
    el folio y el título corriente quedan a alturas distintas aunque en el papel
    estén en el mismo renglón. Sin admitir ese caso, el folio se filtra al
    cuerpo y el título corriente queda pegado al primer párrafo de la página.
    """
    filas = agrupar_filas(renglones)
    if len(filas) < 3:
        return None, renglones, ""

    alturas = [f[0][2] for f in filas]
    saltos = [alturas[i] - alturas[i + 1] for i in range(len(alturas) - 1)]
    interlineado = sorted(saltos)[len(saltos) // 2]
    if interlineado <= 0:
        return None, renglones, ""

    corte = None
    for k in range(min(MAX_FILAS_ENCABEZADO, len(filas) - 1)):
        texto_junto = " ".join(r[3] for f in filas[: k + 1] for r in f).strip()
        if len(texto_junto) > MAX_LARGO_ENCABEZADO:
            break
        if saltos[k] > interlineado * SALTO_ENCABEZADO:
            corte = k + 1
            break
    if corte is None:
        return None, renglones, ""  # no hay encabezado separado

    encabezado = [r for f in filas[:corte] for r in f]
    cuerpo = [r for f in filas[corte:] for r in f]
    pagina = None
    for _, _, _, texto in encabezado:
        limpio = texto.strip()
        # El folio puede venir solo o pegado al título corriente.
        m = (
            re.fullmatch(r"(\d{1,4})", limpio)
            or re.match(r"^(\d{1,4})\b", limpio)
            or re.search(r"\b(\d{1,4})$", limpio)
        )
        if m:
            pagina = m.group(1)
            break

    junto = " ".join(r[3] for r in encabezado)
    # Una cabecera siempre lleva folio. Si no hay ningún dígito, esto no era
    # cabecera: era la primera línea de una página de apertura, que arranca
    # mucho más abajo y por eso deja un blanco parecido. Sin esta guarda se
    # perdían el «CAPÍTULO V» del libro y el autor de la portadilla.
    if pagina is None and not re.search(r"\b\d{1,4}\b", junto):
        return None, renglones, ""

    # El texto del encabezado sin el folio: es el título corriente, que sirve
    # como red de seguridad para las páginas donde la geometría no alcance.
    titulo = re.sub(r"\b\d{1,4}\b", " ", junto)
    return pagina, cuerpo, " ".join(titulo.split())


def versalita(texto: str) -> bool:
    letras = [c for c in texto if c.isalpha()]
    return bool(letras) and sum(c.isupper() for c in letras) / len(letras) > 0.7


def continua_palabra(izquierda: str, derecha: str) -> bool:
    """¿El guión al final de `izquierda` es un corte de renglón?

    Si la continuación empieza en minúscula, sí. Si empieza en mayúscula suele
    ser un compuesto legítimo («sociológico-existencial»)... salvo en los
    títulos en versalitas del original, donde todo va en mayúscula y el corte
    es igual de real («JURÍ-» + «DICA»).
    """
    if not izquierda.endswith("-") or not derecha[:1].isalpha():
        return False
    if derecha[:1].islower():
        return True
    # En un título cortado, el renglón siguiente arrastra el final del título
    # y el comienzo del cuerpo («DICA. - No es extraño...»): hay que mirar sólo
    # la primera palabra, no el renglón entero.
    primera = re.match(r"[^\W\d_]+", derecha)
    return bool(primera) and versalita(izquierda) and versalita(primera.group(0))


def unir(lineas: list[str]) -> str:
    """Une renglones rearmando las palabras cortadas con guión al final."""
    salida = ""
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        if not salida:
            salida = linea
        elif continua_palabra(salida, linea):
            salida = salida[:-1] + linea
        else:
            salida += " " + linea
    return salida


def parrafos_de_pagina(renglones: list) -> list[tuple[bool, str]]:
    """Agrupa los renglones en párrafos. Devuelve (empieza_parrafo, texto).

    `empieza_parrafo` es False cuando el primer párrafo de la página continúa
    el último de la página anterior: eso pasa siempre que el renglón de arriba
    no viene sangrado.
    """
    if not renglones:
        return []
    # Vision parte a veces un mismo renglón físico en dos cajas. Tratarlas por
    # separado desordena el texto y, como la segunda empieza muy a la derecha,
    # la hace pasar por sangrada. Se agrupan por altura y se leen de izquierda
    # a derecha.
    lineas = []
    for fila in agrupar_filas(renglones):
        fila = sorted(fila, key=lambda r: r[0])
        lineas.append((min(r[0] for r in fila), unir([r[3] for r in fila])))

    # Mediana y no mínimo: un solo renglón torcido del escaneo (o una nota al
    # pie que entra más a la izquierda) corre el margen y hace que las líneas
    # normales pasen por sangradas, partiendo párrafos en mitades.
    margen = statistics.median(minx for minx, _ in lineas)
    grupos: list[tuple[bool, list[str]]] = []
    for minx, texto in lineas:
        nuevo = minx > margen + SANGRIA or texto.lstrip().startswith("§")
        if not grupos or nuevo:
            grupos.append((nuevo, [texto]))
        else:
            grupos[-1][1].append(texto)
    parrafos = []
    for nuevo, lineas in grupos:
        texto = unir(lineas)
        # El escaneo deja manchas que el OCR lee como puntuación suelta al
        # principio del renglón. No es texto del original: se descarta.
        texto = re.sub(r'^[.,;:·•*"\']+\s*', "", texto).strip()
        if texto:
            parrafos.append((nuevo, texto))
    return parrafos


def ensamblar(paginas: list[list], folios: list[str | None]) -> str:
    """Pega las páginas en un solo texto, con marcas de folio y párrafos unidos."""
    bloques: list[str] = []
    for renglones, folio in zip(paginas, folios):
        parrafos = parrafos_de_pagina(renglones)
        marca = f"<!-- p. {folio} -->" if folio else "<!-- p. ? -->"
        if not parrafos:
            continue
        primero_nuevo, primer_texto = parrafos[0]
        if bloques and not primero_nuevo:
            # La página arranca a media frase: la marca de folio va en el
            # punto exacto del corte, dentro del párrafo.
            anterior = bloques[-1]
            if anterior.endswith("-") and primer_texto[:1].islower():
                bloques[-1] = f"{anterior[:-1]}{primer_texto} {marca}"
            else:
                bloques[-1] = f"{anterior} {marca} {primer_texto}"
        else:
            bloques.append(marca)
            bloques.append(primer_texto)
        bloques += [t for _, t in parrafos[1:]]
    return "\n\n".join(bloques)


def titular(texto: str) -> str:
    """Pasa un título en versalitas a algo legible como encabezado."""
    letras = [c for c in texto if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) / len(letras) > 0.7:
        texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto)
    # El título puede venir de dos renglones y quedar con el guion de corte
    # adentro («sujeto de de- recho»). Acá sí se puede unir sin riesgo: un
    # compuesto legítimo no lleva espacio después del guion.
    texto = re.sub(r"(\w)-\s+(\w)", r"\1\2", texto)
    # Si el título abre comillas y no las cierra —pasa cuando el OCR se come la
    # de cierre— se quitan las dos: mejor sin comillas que a medias.
    if texto.count('"') % 2:
        texto = texto.replace('"', "")
    texto = texto.strip(" .,;:-–—")
    return texto[:1].upper() + texto[1:]


RE_APARTADO = re.compile(r"^([A-Z])\)\s+(.+)$")


def marcar_apartados(texto: str) -> str:
    """Convierte los apartados del libro en encabezados `#` de nivel 1.

    Un libro puede tener tres pisos: capítulo > apartado > parágrafo. Los
    apartados vienen como párrafos enteros en mayúsculas que arrancan con
    «A)», «B)»… y, cuando en la maqueta ocupaban dos o tres renglones, quedan
    partidos en párrafos separados. Marcarlos permite que `dividir` sepa a qué
    bloque pertenece cada parágrafo, y que el índice del sitio los agrupe.

    Los parágrafos siguen en `##`, así que `dividir --nivel 2` no cambia.
    """
    parrafos = texto.split("\n\n")
    salida, i = [], 0
    while i < len(parrafos):
        actual = " ".join(parrafos[i].split())
        m = RE_APARTADO.match(actual)
        if not (m and versalita(actual)):
            salida.append(parrafos[i])
            i += 1
            continue
        # El título puede seguir en los párrafos siguientes, también en
        # mayúsculas. Se corta al toparse con otro apartado o con algo largo.
        piezas, i = [m.group(2)], i + 1
        while i < len(parrafos):
            sig = " ".join(parrafos[i].split())
            if not (versalita(sig) and 3 < len(sig) <= MAX_LARGO_ENCABEZADO and not RE_APARTADO.match(sig)):
                break
            piezas.append(sig)
            i += 1
        salida.append(f"# {m.group(1)}) {titular(' '.join(piezas))}")
    return "\n\n".join(salida)


def rescatar_folios(texto: str) -> str:
    """Recupera los folios que quedaron al principio del cuerpo de la página.

    Cuando el folio y el título corriente caen en filas distintas —pasa en las
    páginas pares, que son la mitad más torcida del pliego—, la geometría no
    los reconoce como cabecera y el número termina como primer párrafo de la
    página. El número está ahí: se promueve a folio y se borra del texto.

    Se exige que el número sea el párrafo COMPLETO y que valga exactamente el
    folio siguiente al último conocido. Aceptar un simple prefijo alcanzaría
    igual en este libro, pero se comería marcadores de nota al pie, artículos
    («80° del Cód. Civil») o años en cualquier libro cuya paginación se solape
    con esos números; acá no se solapa por casualidad.

    Las marcas legítimas sin folio (portadilla, apertura de capítulo) quedan
    intactas por construcción: son las primeras, todavía no hay folio conocido
    y la regla no puede inventar un esperado.
    """
    # El número puede haber quedado inline detrás de la marca o como párrafo
    # suelto debajo: son la misma cosa, según cómo cayó la sangría.
    patron = re.compile(r"<!-- p\. \? -->[ \t]*\n{0,2}[ \t]*(\d{1,4})[ \t]*(?=\n\n|\n?$)")
    ultimo: int | None = None
    salida, pos = [], 0
    for m in re.finditer(r"<!-- p\. ([\d?]+) -->", texto):
        if m.group(1) != "?":
            ultimo = int(m.group(1))
            continue
        if ultimo is None:
            continue  # portadilla o apertura: no hay folio del cual deducir
        candidato = patron.match(texto, m.start())
        if not candidato or int(candidato.group(1)) != ultimo + 1:
            continue
        ultimo += 1
        salida.append(texto[pos : m.start()])
        salida.append(f"<!-- p. {ultimo} -->")
        pos = candidato.end()
    salida.append(texto[pos:])
    return "".join(salida)


RE_CAPITULO = re.compile(r"^CAP[IÍ]TULO\s+([IVXLCDM]+|\d{1,3})\W*$", re.IGNORECASE)


def juntar_titulo_capitulo(texto: str) -> str:
    """Junta el número y el título del capítulo en una sola línea.

    En la página de apertura, el número (`CAPÍTULO V`) y el título van en
    renglones separados y con sangrías distintas, así que salen como párrafos
    sueltos. Se pegan en uno para que sea legible y se pueda copiar a la clave
    `contenedor` de `libro.toml`.

    A propósito NO se convierte en encabezado: el capítulo se declara a mano en
    la ficha del libro. Agregar un tercer nivel de encabezado obligaría a que
    `dividir` llevara dos ancestros por sección, y el único libro con este
    nivel tiene un solo capítulo.
    """
    parrafos = texto.split("\n\n")
    salida, i = [], 0
    while i < len(parrafos):
        actual = " ".join(parrafos[i].split())
        if not RE_CAPITULO.match(actual):
            salida.append(parrafos[i])
            i += 1
            continue
        piezas, i = [actual.rstrip(". ")], i + 1
        while i < len(parrafos):
            sig = " ".join(parrafos[i].split())
            # Corta en el apartado, en un parágrafo o en cualquier cosa que ya
            # no parezca parte del título.
            if not (
                versalita(sig)
                and 3 < len(sig) <= MAX_LARGO_ENCABEZADO
                and not RE_APARTADO.match(sig)
                and not sig.startswith("§")
            ):
                break
            piezas.append(sig)
            i += 1
        salida.append(f"{piezas[0]}. {' '.join(piezas[1:])}".strip(". ") if len(piezas) > 1 else piezas[0])
    return "\n\n".join(salida)


def quitar_titulo_corriente(texto: str, encabezados: list[str]) -> str:
    """Borra el título corriente que se le haya escapado a la geometría.

    Red de seguridad: en las páginas donde `separar_encabezado` no reconoce la
    cabecera, el título corriente queda pegado al arranque del párrafo. Se
    borran solo los que aparecen repetidos en varias páginas, que es lo que
    distingue una cabecera de una frase del autor.
    """
    frecuencia = Counter(e for e in encabezados if e)
    repetidos = [e for e, n in frecuencia.items() if n >= MIN_REPETICIONES_CABECERA]
    if not repetidos:
        return texto
    for cabecera in sorted(repetidos, key=len, reverse=True):
        escapada = re.escape(cabecera)
        # Como párrafo suelto, al principio de un párrafo, o detrás de una
        # marca de folio.
        texto = re.sub(rf"^{escapada}\s*$", "", texto, flags=re.MULTILINE)
        texto = re.sub(rf"(?m)^{escapada}\s+(?=\S)", "", texto)
        texto = re.sub(rf"(<!-- p\. [^>]*-->)\s*{escapada}\s+", r"\1 ", texto)
    return texto


def marcar_paragrafos(texto: str) -> str:
    """Convierte los parágrafos numerados del original en encabezados `##`.

    El libro numera sus divisiones como «§ 54. TÍTULO EN VERSALITAS. - Texto».
    Ese es el corte natural para `ema.py dividir --nivel 2`, y el que permite
    citar «§ 54» en lugar de inventar una referencia.
    """
    # El punto antes del guion a veces se pierde en el OCR, sobre todo cuando
    # el título cierra con comillas («CONCRETO" - El...» en vez de
    # «CONCRETO". - El...»): el punto se hace opcional. El espacio a los dos
    # lados del guion, en cambio, es obligatorio: sin eso, un guion de corte
    # de sílaba a mitad de palabra («DE-» + «RECHO») se confunde con el
    # separador y trunca el título ahí.
    patron = re.compile(
        r'§\W{0,3}\s*(\d{1,3})\s*\.\s*(.{3,200}?)\s*"?\s*\.?\s+[-–—]\s+',
        re.DOTALL,
    )

    def reemplazo(m: re.Match) -> str:
        return f"\n\n## § {m.group(1)}. {titular(m.group(2))}\n\n"

    texto = patron.sub(reemplazo, texto)

    # Segunda pasada, para los parágrafos que no usan el guion separador y
    # arrancan el cuerpo justo después del título: «§ 72. VISIÓN
    # TRIDIMENSIONAL DE LA PERSONA JURÍDICA. En los arts...».
    #
    # Va DESPUÉS de la primera y no antes: hay títulos a los que el OCR les
    # comió el punto y cerró con comilla (§ 63), y a esos solo los levanta la
    # primera.
    #
    # Lo que evita los falsos positivos NO es el ancla de principio de línea:
    # el autor usa «§ 25» como referencia cruzada y también queda en columna 0,
    # porque el armado de párrafos corta al ver un «§». Lo que lo salva es
    # exigir que el título esté en versalitas. No borrar esa guarda.
    directo = re.compile(r"^§\W{0,3}\s*(\d{1,3})\s*\.\s*([^.\s][^.]{2,199}?)\s*\.\s+(?=\S)", re.MULTILINE)

    def reemplazo_directo(m: re.Match) -> str:
        if not versalita(m.group(2)):
            return m.group(0)
        return f"\n\n## § {m.group(1)}. {titular(m.group(2))}\n\n"

    return directo.sub(reemplazo_directo, texto)


def a_markdown(pdf: Path, mitades: int | None, dpi: int, desde: int, hasta: int | None) -> str:
    ancho, alto, total = medir_pagina(pdf)
    hasta = hasta or total
    if mitades is None:
        apaisada_p1 = ancho / max(alto, 1) > PROPORCION_PLIEGO
        mitades = 1
        if apaisada_p1:
            # La página 1 sola puede engañar: una portada escaneada como el
            # pliego entero mientras el cuerpo es retrato normal también da
            # esta proporción, y ahí partir todo el libro al medio mezclaría
            # el texto de páginas vecinas. Se confirma con una interior antes
            # de aplicar el corte a las 173 páginas.
            interior = min(max(total // 2, 1), total)
            ancho_i, alto_i, _ = medir_pagina(pdf, numero=interior)
            if ancho_i / max(alto_i, 1) > PROPORCION_PLIEGO:
                mitades = 2
                print(f"→ hoja apaisada ({ancho:.0f}x{alto:.0f}): la parto en dos páginas", file=sys.stderr)
            else:
                print(
                    f"→ la página 1 es apaisada ({ancho:.0f}x{alto:.0f}) pero la página "
                    f"{interior} no ({ancho_i:.0f}x{alto_i:.0f}): no es doble página por "
                    "hoja, no parto nada",
                    file=sys.stderr,
                )

    with tempfile.TemporaryDirectory() as tmp:
        imagenes = rasterizar(pdf, Path(tmp), mitades, dpi, desde, hasta)
        print(f"→ {len(imagenes)} páginas rasterizadas a {dpi} dpi", file=sys.stderr)
        paginas = reconocer(imagenes)

    cuerpos, folios, encabezados = [], [], []
    for renglones in paginas:
        folio, cuerpo, encabezado = separar_encabezado(renglones)
        cuerpos.append(cuerpo)
        folios.append(folio)
        encabezados.append(encabezado)

    texto = ensamblar(cuerpos, folios)
    # Antes de tocar la estructura: rescatar folios opera sobre las marcas y el
    # texto crudo, y juntar el título del capítulo tiene que pasar antes de que
    # `marcar_apartados` se coma los párrafos en versalitas que lo siguen.
    texto = rescatar_folios(texto)
    texto = quitar_titulo_corriente(texto, encabezados)
    texto = juntar_titulo_capitulo(texto)
    texto = marcar_apartados(texto)
    texto = marcar_paragrafos(texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    reconocidos = len(re.findall(r"<!-- p\. \d+ -->", texto))
    print(f"→ folios reconocidos: {reconocidos}/{len(folios)}", file=sys.stderr)
    return texto.strip() + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pdf", type=Path)
    p.add_argument("-o", "--salida", type=Path, help="archivo destino (por defecto: stdout)")
    p.add_argument("--dpi", type=int, default=DPI)
    p.add_argument("--mitades", type=int, choices=[1, 2], help="páginas de libro por hoja (por defecto: automático)")
    p.add_argument("--desde", type=int, default=1)
    p.add_argument("--hasta", type=int)
    args = p.parse_args()

    texto = a_markdown(args.pdf, args.mitades, args.dpi, args.desde, args.hasta)
    if args.salida:
        args.salida.write_text(texto, encoding="utf-8")
        print(f"✓ {len(texto):,} caracteres → {args.salida}", file=sys.stderr)
    else:
        sys.stdout.write(texto)


if __name__ == "__main__":
    main()
