#!/usr/bin/env python3
"""Utilidades compartidas por `ema.py` y `sitio.py`.

Existe por un motivo concreto: la extracción de la idea principal de un
documento de estudio estaba escrita dos veces, con dos expresiones regulares
distintas y ambas atadas al número del bloque. Cambiar la numeración de la
plantilla rompía el resumen del índice del sitio y el encadenado de contexto
entre corridas, en silencio y en dos lugares a la vez. Acá vive una sola vez y
busca por título, no por número.
"""

from __future__ import annotations

import re
import unicodedata

# Títulos que identifican el bloque de la idea principal, en orden de
# preferencia. El segundo es el de la plantilla vieja de 12 bloques: se
# mantiene para que los documentos ya generados sigan apareciendo bien en el
# índice mientras se los va regenerando.
CLAVES_IDEA = ("idea principal", "tesis central")


def sin_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def slugify(texto: str, largo: int = 60) -> str:
    texto = sin_acentos(texto)
    texto = re.sub(r"[^\w\s-]", "", texto.lower())
    texto = re.sub(r"[\s_-]+", "-", texto).strip("-")
    return texto[:largo] or "sin-titulo"


def normalizar_titulo(titulo: str) -> str:
    """Baja a minúsculas sin acentos y quita la numeración inicial."""
    return re.sub(r"^\s*\d+(\.\d+)*\.?\s*", "", sin_acentos(titulo).lower()).strip()


def bloques_h2(texto: str):
    """Itera (título, cuerpo) por cada encabezado `##` del documento."""
    marcas = list(re.finditer(r"^## +(.+?)[ \t]*$", texto, re.MULTILINE))
    for i, m in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        yield m.group(1).strip(), texto[m.end() : fin]


def primer_parrafo(cuerpo: str) -> str:
    """El primer párrafo real de un bloque, con los espacios normalizados.

    Saltea lo que no es prosa: comentarios HTML, subencabezados, notas entre
    corchetes, viñetas y bloques de código. Si el bloque arranca con algo de
    eso, el resumen del índice saldría con basura.
    """
    cuerpo = re.sub(r"<!--.*?-->", "", cuerpo, flags=re.DOTALL)
    cuerpo = re.sub(r"^```.*?^```", "", cuerpo, flags=re.DOTALL | re.MULTILINE)
    for bruto in re.split(r"\n\s*\n", cuerpo):
        parrafo = " ".join(bruto.split())
        if not parrafo or parrafo.startswith(("#", "[", "-", "*", ">", "|", "!")):
            continue
        return parrafo
    return ""


def idea_principal(texto: str) -> str:
    """El primer párrafo del bloque de idea principal de un documento.

    Busca por título y no por número, así la plantilla puede renumerar sus
    bloques sin romper ni el índice del sitio ni el contexto entre corridas.
    """
    candidatos = list(bloques_h2(texto))
    for clave in CLAVES_IDEA:
        for titulo, cuerpo in candidatos:
            if clave in normalizar_titulo(titulo):
                if parrafo := primer_parrafo(cuerpo):
                    return parrafo
    # Respaldo por posición, para un documento con títulos inesperados.
    for titulo, cuerpo in candidatos:
        if re.match(r"^\s*[12]\.", titulo):
            if parrafo := primer_parrafo(cuerpo):
                return parrafo
    return ""
