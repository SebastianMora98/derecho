"""Limpieza de texto extraído de PDF.

La extracción de un PDF conserva la maquetación, no la estructura: cada línea
impresa es una línea del archivo, las palabras quedan partidas con guion, y en
cada página se repiten la cabecera corrida y el número de página.

Este módulo deshace eso y, cuando puede, reconstruye los encabezados de
capítulo como Markdown para que `dividir` tenga por dónde cortar.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

# Una cabecera corrida aparece al menos en tantas páginas:
MIN_REPETICIONES = 5
MAX_LARGO_CABECERA = 70
# Un título de capítulo no pasa de:
MAX_LARGO_TITULO = 90

RE_NUMERO_SOLO = re.compile(r"^\d{1,4}$")
RE_PUNTOS_GUIA = re.compile(r"[ .]*(?:\. ){3,}\.?[ .]*$")
RE_ROMANO = re.compile(r"^[IVXLC]{1,7}$")


def limpiar_pdf(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto.replace("\r\n", "\n").replace("\r", "\n"))
    # El salto de página (form feed) separa el pie de una página del encabezado
    # de la siguiente: sin esto, cabecera y texto quedan pegados en una línea.
    texto = texto.replace("\f", "\n")
    lineas = [linea.rstrip() for linea in texto.split("\n")]

    cabeceras = detectar_cabeceras(lineas)
    lineas = [quitar_cabecera(l, cabeceras) for l in lineas]
    lineas = marcar_capitulos(lineas)
    lineas = [l for l in lineas if not RE_NUMERO_SOLO.match(l.strip())]

    return reflujo("\n".join(lineas))


def detectar_cabeceras(lineas: list[str]) -> set[str]:
    """Líneas cortas que se repiten en muchas páginas: título corrido, autor."""
    conteo = Counter(
        l.strip() for l in lineas
        if 3 < len(l.strip()) <= MAX_LARGO_CABECERA and not l.strip()[-1] in ".,;:"
    )
    return {l for l, n in conteo.items() if n >= MIN_REPETICIONES}


def quitar_cabecera(linea: str, cabeceras: set[str]) -> str:
    """Quita la cabecera corrida, esté sola en su línea o pegada al texto que
    sigue (la extracción suele juntar el fin de página con el principio de la
    siguiente: 'CESARE BECCARIA1', 'TRATADO...PENASINTRODUCCIÓN')."""
    limpia = linea.strip()
    for cab in cabeceras:
        if limpia == cab:
            return ""
        if limpia.startswith(cab):
            return limpia[len(cab):].strip()
    return linea


def marcar_capitulos(lineas: list[str]) -> list[str]:
    """Convierte los inicios de capítulo en encabezados Markdown.

    Reconoce dos formas, ambas frecuentes en libros maquetados:
      - un número solo en su línea, y unas líneas después el título
      - un título en VERSALES aislado entre líneas en blanco
    """
    salida: list[str] = []
    i = 0
    while i < len(lineas):
        linea = lineas[i].strip()

        numero = linea if (RE_NUMERO_SOLO.match(linea) or RE_ROMANO.match(linea)) else None
        if numero:
            titulo, salto = buscar_titulo(lineas, i + 1)
            if titulo:
                # Un título en versales (INTRODUCCIÓN, CONCLUSIÓN) no lleva el
                # número: el que lo precedía era el de la página.
                encabezado = titulo.capitalize() if es_versales(titulo) else f"{numero}. {titulo}"
                salida.append(f"## {encabezado}")
                i = salto
                continue

        if es_versales(linea):
            salida.append(f"## {linea.capitalize() if linea.isupper() else linea}")
            i += 1
            continue

        salida.append(lineas[i])
        i += 1
    return salida


def buscar_titulo(lineas: list[str], desde: int) -> tuple[str | None, int]:
    """Tras un número de capítulo, el título es la primera línea con texto,
    corta y sin puntuación final de oración."""
    for j in range(desde, min(desde + 4, len(lineas))):
        candidato = lineas[j].strip()
        if not candidato:
            continue
        if len(candidato) > MAX_LARGO_TITULO or candidato[-1] in ".;:,":
            return None, desde
        if candidato[0].islower():
            return None, desde
        # Un título tiene letras: descarta los pares de números del índice.
        if len(re.findall(r"[^\W\d_]", candidato)) < 3:
            return None, desde
        # Y está aislado: si abajo sigue texto, era el primer renglón de un
        # párrafo que arrancaba después del número de página.
        if j + 1 < len(lineas) and lineas[j + 1].strip():
            return None, desde
        return candidato, j + 1
    return None, desde


def es_versales(linea: str) -> bool:
    return (
        3 < len(linea) <= MAX_LARGO_TITULO
        and linea.isupper()
        and bool(re.search(r"[A-ZÁÉÍÓÚÜÑ]{3}", linea))
        and not any(c.isdigit() for c in linea)
    )


def reflujo(texto: str) -> str:
    """Une las líneas de cada párrafo y repara las palabras cortadas con guion."""
    bloques = re.split(r"\n\s*\n", texto)
    salida = []
    for bloque in bloques:
        lineas = [l.strip() for l in bloque.split("\n") if l.strip()]
        if not lineas:
            continue
        if lineas[0].startswith("#"):
            salida.append("\n".join(lineas))
            continue

        parrafo = ""
        for linea in lineas:
            linea = RE_PUNTOS_GUIA.sub("", linea)
            linea = re.sub(r"[ \t]{2,}", " ", linea)
            if not parrafo:
                parrafo = linea
            elif parrafo.endswith("-") and linea[:1].islower():
                parrafo = parrafo[:-1] + linea
            else:
                parrafo = f"{parrafo} {linea}"
        if parrafo.strip():
            salida.append(parrafo.strip())

    return "\n\n".join(salida).strip() + "\n"
