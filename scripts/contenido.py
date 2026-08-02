"""Lee `libros/<slug>/estudio/*.md` y separa cada documento en sus partes.

Hasta hace poco este archivo se llamaba `sitio.py` y hacía dos cosas a la vez:
parsear el markdown de cada documento de estudio Y armar el HTML del sitio en
las mismas funciones — el texto y las etiquetas quedaban soldados. Ahora solo
hace la primera mitad: leer `estudio/*.md`, separar lo que se ve dentro de un
capítulo de lo que se consolida por libro (vocabulario, distinciones,
autoevaluación, flashcards), y devolver estructuras de datos planas. Quien
consume esas estructuras es `scripts/datos.py`, que las escribe a JSON, y de
ahí en más el HTML lo arma `web/` (Astro) — sin que este archivo sepa que el
HTML existe.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import normalizar_titulo, sin_acentos  # noqa: E402

MARCA_RESPUESTAS = "--- No mires esto hasta responder ---"


# --------------------------------------------------------------------------- #
# lectura
# --------------------------------------------------------------------------- #


def recolectar(libros_dir: Path, leer_config) -> list[dict]:
    libros = []
    for carpeta in sorted(p for p in libros_dir.iterdir() if p.is_dir()):
        estudios = sorted((carpeta / "estudio").glob("*.md")) if (carpeta / "estudio").exists() else []
        cfg = leer_config(carpeta)
        # Una entrada puede ser solo el resumen general, sin ningún documento de
        # estudio: es el caso de una charla o un video, donde lo único que se
        # publica es de qué trata. Sin `resumen` y sin documentos no hay nada
        # que mostrar, y la carpeta se saltea.
        if not estudios:
            if str(cfg.get("resumen", "")).strip():
                libros.append({"slug": carpeta.name, "cfg": cfg, "secciones": []})
            continue
        secciones = []
        vistos: set[str] = set()
        for ruta in estudios:
            numero = ruta.name.split("-")[0]
            if not numero.isdigit():
                print(f"aviso: {ruta.name} no empieza con el número de sección; lo salteo")
                continue
            # Todos los `id` de la hoja se derivan del número, así que un número
            # repetido genera anclas duplicadas y enlaces que van al capítulo
            # equivocado. Antes esto pasaba callado.
            if numero in vistos:
                print(f"aviso: {ruta.name} repite el número {numero}; lo salteo para no duplicar anclas")
                continue
            vistos.add(numero)
            texto = ruta.read_text(encoding="utf-8")
            tesis = tesis_de(texto)
            if not tesis:
                print(f"aviso: {ruta.name} no tiene bloque de idea principal; va sin resumen en el índice")
            # El parseo va acá y no más adelante porque acá está el nombre del
            # archivo: un aviso que no dice de qué documento habla no sirve.
            visible, extraido = partir_documento(texto, ruta.name)
            secciones.append(
                {
                    "numero": numero,
                    "ancla": f"s{numero}",
                    "archivo": ruta.name,
                    "titulo": titulo_de(texto, ruta.stem),
                    "tesis": tesis,
                    "visible": visible,
                    "extraido": extraido,
                }
            )
        if not secciones:
            continue
        secciones = completar_con_pendientes(carpeta, secciones)
        libros.append({"slug": carpeta.name, "cfg": cfg, "secciones": secciones})
    return libros


def completar_con_pendientes(carpeta: Path, secciones: list[dict]) -> list[dict]:
    """Agrega los capítulos del libro que todavía no tienen documento.

    Así se sabe que el libro está completo o no, y qué falta: la lista sale de
    `capitulos.toml`, que escribe `ema.py dividir` justamente porque
    `secciones/` no va a git.
    """
    manifiesto = carpeta / "capitulos.toml"
    if not manifiesto.exists():
        return secciones
    with manifiesto.open("rb") as fh:
        capitulos = tomllib.load(fh).get("capitulos", [])
    if not capitulos:
        return secciones

    hechos = {s["numero"]: s for s in secciones}
    completas = []
    for cap in capitulos:
        numero = str(cap.get("numero", "")).strip()
        if numero in hechos:
            completas.append(hechos.pop(numero))
        else:
            completas.append(
                {
                    "numero": numero,
                    "ancla": f"s{numero}",
                    "titulo": cap.get("titulo", numero),
                    "tesis": "",
                    "texto": "",
                    "pendiente": True,
                }
            )
    # Un documento cuyo número no está en el manifiesto quedó huérfano: el libro
    # se volvió a dividir con otro criterio y nadie borró el documento viejo.
    for numero, s in sorted(hechos.items()):
        print(f"aviso: la sección {numero} tiene documento pero ya no existe en capitulos.toml")
        completas.append(s)
    return completas


def titulo_de(texto: str, respaldo: str) -> str:
    m = re.search(r"^# +(.+)$", texto, re.MULTILINE)
    return m.group(1).strip() if m else respaldo


def tesis_de(texto: str) -> str:
    """La idea principal del documento: es el resumen que va en los índices."""
    from comun import idea_principal

    return idea_principal(texto)


# --------------------------------------------------------------------------- #
# separar lo visible de lo que se consolida por libro
# --------------------------------------------------------------------------- #


# Qué bloques del documento se sacan del capítulo y a qué consolidado del libro
# van. La clave es UNA PALABRA del título normalizado, no el título entero ni el
# número: renumerar la plantilla ya rompió esto en silencio una vez, y renombrar
# «Vocabulario clave» a «Vocabulario del capítulo» tampoco debe romperlo.
CLAVES_EXTRAIBLES = (
    ("vocabulario", "vocabulario"),
    ("distinciones", "distinciones"),
    ("autoevaluacion", "autoevaluacion"),
    ("flashcards", "flashcards"),
)

# `- **Término** — definición`. Acepta raya, semirraya y guion pelado, porque una
# corrección a mano se escapa. El término no goloso, para que una negrita dentro
# de la definición no se lo trague.
LINEA_TERMINO = re.compile(
    r"^\s*[-*]\s+\*\*(?P<termino>.+?)\*\*\s*[—–-]+\s*(?P<definicion>\S.*?)\s*$"
)


def destino_del_bloque(titulo: str) -> str | None:
    """A qué consolidado va un bloque, o None si se muestra en el capítulo.

    Es una lista blanca de EXTRACCIÓN, no de visibilidad: lo que no clasifica
    queda visible. Así, si alguien renombra un bloque, reaparece feo dentro del
    capítulo en vez de desaparecer sin que nadie se entere. Es la dirección
    segura del fallo.
    """
    normalizado = normalizar_titulo(titulo)
    return next((destino for clave, destino in CLAVES_EXTRAIBLES if clave in normalizado), None)


def parsear_vocabulario(cuerpo: str, origen: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Parte el bloque de vocabulario en (término, definición).

    Una línea que no calza NO se descarta en silencio: se devuelve aparte y se
    avisa. Perder contenido callado es el modo de falla que este proyecto ya
    pagó dos veces.
    """
    terminos, sueltos = [], []
    for linea in cuerpo.splitlines():
        if not linea.strip().startswith(("-", "*")):
            continue
        m = LINEA_TERMINO.match(linea.rstrip())
        if m:
            terminos.append((m.group("termino").strip(), m.group("definicion").strip()))
        else:
            sueltos.append(linea.strip().lstrip("-* ").strip())
            print(f"aviso: {origen}: línea de vocabulario fuera de formato: {linea.strip()[:60]}")
    return terminos, sueltos


def parsear_flashcards(cuerpo: str) -> list[tuple[str, str]]:
    """Cada línea `Pregunta | Respuesta`. Una línea sin `|` se ignora."""
    tarjetas = []
    for linea in cuerpo.splitlines():
        if "|" in linea and linea.strip():
            pregunta, _, respuesta = linea.partition("|")
            tarjetas.append((pregunta.strip(" -*"), respuesta.strip()))
    return tarjetas


def partir_documento(texto: str, origen: str = "") -> tuple[str, dict]:
    """Separa lo que se lee en el capítulo de lo que se consolida por libro.

    El capítulo queda con la idea principal, la explicación y el mapa. El
    vocabulario, las distinciones, la autoevaluación y las flashcards se
    muestran una sola vez por libro: repetir ese aparato en cada capítulo era
    lo que hacía los documentos largos y redundantes.
    """
    texto = re.sub(r"^# +.+\n", "", texto, count=1)  # el título va en el summary
    extraido = {
        "vocabulario": [],
        "sueltos": [],
        "distinciones": "",
        "preguntas": "",
        "respuestas": "",
        "flashcards": [],
    }

    marcas = list(re.finditer(r"^## +(.+?)[ \t]*$", texto, re.MULTILINE))
    # Lo anterior al primer `##` se conserva: descartarlo perdería contenido
    # que hasta ahora siempre se mostró.
    visibles = [texto[: marcas[0].start()].strip()] if marcas else [texto.strip()]

    for i, m in enumerate(marcas):
        titulo = m.group(1).strip()
        cuerpo = texto[m.end() : marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)]
        destino = destino_del_bloque(titulo)
        if destino is None:
            visibles.append(f"## {titulo}\n{cuerpo}")
            continue
        if destino == "vocabulario":
            terminos, sueltos = parsear_vocabulario(cuerpo, origen)
            extraido["vocabulario"] += terminos
            extraido["sueltos"] += sueltos
        elif destino == "flashcards":
            extraido["flashcards"] += parsear_flashcards(cuerpo)
        elif destino == "autoevaluacion":
            preguntas, _, respuestas = cuerpo.partition(MARCA_RESPUESTAS)
            extraido["preguntas"] += preguntas
            extraido["respuestas"] += respuestas
        else:
            extraido["distinciones"] += cuerpo

    faltan = [d for d in ("vocabulario", "autoevaluacion", "flashcards") if not extraido[d if d != "autoevaluacion" else "preguntas"]]
    if faltan and origen:
        print(f"aviso: {origen}: no encontré el bloque de {', '.join(faltan)}")
    return "\n\n".join(p for p in visibles if p.strip()), extraido


def items_numerados(texto: str) -> list[str]:
    """Parte una lista numerada de markdown en sus ítems, sin el número."""
    marcas = list(re.finditer(r"^\s*(\d{1,2})\.[ \t]+", texto, re.MULTILINE))
    items = []
    for i, m in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        items.append(texto[m.end() : fin].strip())
    return items


# --------------------------------------------------------------------------- #
# consolidado del libro
# --------------------------------------------------------------------------- #


def clave_termino(termino: str) -> str:
    """Clave para deduplicar el glosario.

    Normaliza solo lo seguro: mayúsculas, acentos, puntuación, paréntesis y el
    plural regular. NO intenta unificar sinónimos: «Tridimensionalismo» y
    «Teoría tridimensional del derecho» son el mismo concepto y quedan como dos
    entradas, porque cualquier regla que los junte junta también cosas
    distintas. Eso se arregla escribiendo mejor los documentos.
    """
    base = re.sub(r"\(.*?\)", " ", sin_acentos(termino).lower())
    base = re.sub(r"[^a-z0-9 ]", " ", base)
    # El corte en 5 caracteres evita destrozar «tres» o «pais»; deja pasar
    # «leyes → ley» y «penas → pena», que es lo que se quiere atrapar.
    return " ".join(
        re.sub(r"(?:es|s)$", "", palabra) if len(palabra) >= 5 else palabra
        for palabra in base.split()
    )


def equivalentes(a: str, b: str) -> bool:
    """¿Dos definiciones dicen lo mismo? Se ignora la cita con referencia."""
    limpiar = lambda d: " ".join(re.sub(r"\(.*?\)", " ", sin_acentos(d).lower()).split()).strip(" .")
    return limpiar(a) == limpiar(b)


def consolidar_vocabulario(secciones: list[dict]) -> list[dict]:
    """Un glosario por libro: una entrada por término, con sus capítulos.

    Gana la definición del capítulo donde el término aparece primero, que es la
    que el lector va a encontrar leyendo en orden. Cuando dos capítulos lo
    definen distinto se avisa por consola y se usa la primera: una definición
    divergente es un defecto del documento, no contenido para el lector.
    """
    entradas: dict[str, dict] = {}
    for s in secciones:
        for termino, definicion in s.get("extraido", {}).get("vocabulario", []):
            clave = clave_termino(termino)
            if clave not in entradas:
                entradas[clave] = {"termino": termino, "definicion": definicion, "caps": [s]}
                continue
            # ya definido antes
            entrada = entradas[clave]
            if s not in entrada["caps"]:
                entrada["caps"].append(s)
            if not equivalentes(entrada["definicion"], definicion):
                previos = ", ".join(c["numero"] for c in entrada["caps"])
                print(f"aviso: «{termino}» está definido distinto en los capítulos {previos}; "
                      f"el glosario usa el primero")
    return sorted(entradas.values(), key=lambda e: sin_acentos(e["termino"]).lower())
