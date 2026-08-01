"""Genera el sitio estático a partir de los documentos de estudio.

Sale HTML plano en `sitio/`, sin build ni framework: Vercel lo sirve tal cual.

    sitio/index.html                      lista de libros
    sitio/<libro>/index.html              el libro entero, en una sola hoja

Cada libro es UNA página: la jerarquía del original con la idea principal de
cada capítulo, y cada capítulo plegado en un `<details>` que se abre ahí mismo.
Así se ve el mapa completo de una pasada y, abriendo todo, se puede buscar en el
libro entero con Cmd-F.

Los bloques ```mermaid se convierten en diagramas —que dibuja `tarjetas.js` a
medida que se abren los capítulos, no todos al cargar—, el test de comprensión
esconde las respuestas, y las flashcards se revelan al hacer clic.
"""

from __future__ import annotations

import html
import re
import shutil
import sys
from pathlib import Path

from markdown_it import MarkdownIt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import idea_principal, slugify  # noqa: E402

MARCA_RESPUESTAS = "--- No mires esto hasta responder ---"

md = MarkdownIt("commonmark", {"html": False, "linkify": True}).enable("table").enable("strikethrough")


# --------------------------------------------------------------------------- #
# lectura
# --------------------------------------------------------------------------- #


def recolectar(libros_dir: Path, leer_config) -> list[dict]:
    libros = []
    for carpeta in sorted(p for p in libros_dir.iterdir() if p.is_dir()):
        estudios = sorted((carpeta / "estudio").glob("*.md")) if (carpeta / "estudio").exists() else []
        if not estudios:
            continue
        cfg = leer_config(carpeta)
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
            secciones.append(
                {
                    "numero": numero,
                    "ancla": f"s{numero}",
                    "titulo": titulo_de(texto, ruta.stem),
                    "tesis": tesis,
                    "texto": texto,
                }
            )
        if not secciones:
            continue
        libros.append({"slug": carpeta.name, "cfg": cfg, "secciones": secciones})
    return libros


def titulo_de(texto: str, respaldo: str) -> str:
    m = re.search(r"^# +(.+)$", texto, re.MULTILINE)
    return m.group(1).strip() if m else respaldo


def tesis_de(texto: str) -> str:
    """La idea principal del documento: es el resumen que va en los índices."""
    return idea_principal(texto)


# --------------------------------------------------------------------------- #
# render de un documento
# --------------------------------------------------------------------------- #


def render_documento(texto: str, prefijo: str = "") -> tuple[str, list[tuple[str, str]]]:
    """Devuelve el HTML del documento y las anclas para su índice interno."""
    cuerpo, flashcards = separar_flashcards(texto)
    cuerpo = re.sub(r"^# +.+\n", "", cuerpo, count=1)  # el título va en la cabecera
    cuerpo, respuestas = separar_respuestas(cuerpo)

    # Solo se anclan los encabezados del cuerpo: los del bloque de respuestas
    # viven dentro de un <details> cerrado y no deben entrar al índice.
    cuerpo_html, anclas = anclar(transformar(md.render(cuerpo)), prefijo)
    partes = [cuerpo_html]
    if respuestas:
        partes.append(
            '<details class="respuestas"><summary>Respuestas de referencia — no mires hasta responder</summary>'
            + transformar(md.render(respuestas))
            + "</details>"
        )
    if flashcards:
        partes.append(render_flashcards(flashcards, prefijo))
        anclas.append((f"{prefijo}flashcards", "Flashcards"))
    return "\n".join(partes), anclas


def anclar(html_render: str, prefijo: str = "") -> tuple[str, list[tuple[str, str]]]:
    """Pone un `id` en cada `<h2>` y devuelve las anclas del índice interno.

    markdown-it no trae plugin de anclas y el documento no puede escribir HTML
    crudo, así que los `id` se agregan acá, sobre el HTML ya renderizado. Solo
    `h2`: los `h3` de los pasos harían un índice de doce enlaces que en un
    teléfono ocupa media pantalla.

    El `prefijo` es obligatorio en la hoja del libro: los 39 documentos de una
    página generarían 39 veces `vocabulario-clave`. El deduplicado se hace sobre
    el slug SIN prefijo, así que la lógica de choque dentro de un documento no
    cambia y el prefijo solo desambigua entre capítulos.
    """
    anclas: list[tuple[str, str]] = []
    usadas = {"flashcards"}  # ya lo usa render_flashcards

    def reemplazo(m: re.Match) -> str:
        crudo = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        # El número queda en el encabezado pero no en la etiqueta del enlace:
        # «Vocabulario clave» se lee mejor que «4. Vocabulario clave».
        etiqueta = re.sub(r"^\d+(\.\d+)*\.?\s*", "", crudo) or crudo
        base = slugify(etiqueta, 40)
        identificador, n = base, 2
        while identificador in usadas:
            identificador, n = f"{base}-{n}", n + 1
        usadas.add(identificador)
        anclas.append((f"{prefijo}{identificador}", etiqueta))
        return f'<h2 id="{prefijo}{identificador}">{m.group(1)}</h2>'

    return re.sub(r"<h2>(.*?)</h2>", reemplazo, html_render, flags=re.DOTALL), anclas


def render_indice_interno(anclas: list[tuple[str, str]]) -> str:
    """Los enlaces a los bloques del documento, para saltar sin scrollear."""
    if len(anclas) < 3:
        return ""
    enlaces = "".join(f'<a href="#{i}">{html.escape(t)}</a>' for i, t in anclas)
    return f'<nav class="indice-doc" aria-label="Bloques de este documento">{enlaces}</nav>'


def separar_flashcards(texto: str) -> tuple[str, list[tuple[str, str]]]:
    m = re.search(r"\n## *Flashcards *\n(.*)$", texto, re.DOTALL | re.IGNORECASE)
    if not m:
        return texto, []
    tarjetas = []
    for linea in m.group(1).splitlines():
        if "|" in linea and linea.strip():
            pregunta, _, respuesta = linea.partition("|")
            tarjetas.append((pregunta.strip(" -*"), respuesta.strip()))
    return texto[: m.start()], tarjetas


def separar_respuestas(texto: str) -> tuple[str, str]:
    if MARCA_RESPUESTAS not in texto:
        return texto, ""
    cuerpo, _, resto = texto.partition(MARCA_RESPUESTAS)
    # Lo que venga después de la siguiente sección vuelve al cuerpo principal.
    corte = re.search(r"\n## ", resto)
    if corte:
        return cuerpo + resto[corte.start():], resto[: corte.start()]
    return cuerpo, resto


def transformar(html_render: str) -> str:
    """Convierte los bloques ```mermaid en contenedores que Mermaid dibuja."""
    def reemplazo(m: re.Match) -> str:
        return f'<pre class="mermaid">{m.group(1)}</pre>'

    return re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        reemplazo,
        html_render,
        flags=re.DOTALL,
    )


def render_flashcards(tarjetas: list[tuple[str, str]], prefijo: str = "") -> str:
    items = "\n".join(
        f'<button class="tarjeta" type="button">'
        f'<span class="pregunta">{html.escape(p)}</span>'
        f'<span class="respuesta">{html.escape(r)}</span></button>'
        for p, r in tarjetas
    )
    return (
        f'<section id="{prefijo}flashcards"><h2>Flashcards</h2>'
        f'<p class="ayuda">{len(tarjetas)} tarjetas. Hacé clic para revelar la respuesta.</p>'
        f'<div class="tarjetas">{items}</div></section>'
    )


# --------------------------------------------------------------------------- #
# plantillas
# --------------------------------------------------------------------------- #


def pagina(
    titulo: str,
    migas: str,
    contenido: str,
    profundidad: int,
    clase_main: str = "",
) -> str:
    base = "../" * profundidad
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)}</title>
<link rel="stylesheet" href="{base}estilo.css">
</head>
<body>
<header class="barra">
  <a class="marca" href="{base}index.html">Documentos de estudio</a>
  <nav class="migas">{migas}</nav>
</header>
<main{f' class="{clase_main}"' if clase_main else ""}>
{contenido}
</main>
<footer>
  <p>Documentos de estudio generados para acompañar la lectura del original, no para reemplazarla.</p>
</footer>
<script src="{base}tarjetas.js"></script>
</body>
</html>
"""


def render_indice(libros: list[dict]) -> str:
    tarjetas = []
    for libro in libros:
        cfg = libro["cfg"]
        tarjetas.append(
            f'<a class="libro" href="{libro["slug"]}/index.html">'
            f'<h2>{html.escape(cfg.get("titulo", libro["slug"]))}</h2>'
            f'<p class="autor">{html.escape(cfg.get("autor", ""))}</p>'
            f'<p class="meta">{len(libro["secciones"])} secciones estudiadas</p>'
            f"</a>"
        )
    cuerpo = (
        "<h1>Documentos de estudio</h1>"
        "<p class=\"intro\">Cada documento acompaña la lectura de una sección del original: "
        "mapa del argumento, conceptos, preguntas y autoevaluación.</p>"
        f'<div class="libros">{"".join(tarjetas)}</div>'
    )
    return pagina("Documentos de estudio", "", cuerpo, 0)


def agrupar_en_partes(secciones: list[dict], cfg: dict) -> list[tuple[str | None, list[dict]]]:
    """Agrupa las secciones por apartado del libro, según `[[partes]]`.

    Un libro de jerarquía plana no declara `partes`: devuelve un solo grupo sin
    título y el índice sale como lista corrida, igual que antes.
    """
    partes = cfg.get("partes") or []
    if not partes:
        return [(None, secciones)]

    grupos: list[tuple[str | None, list[dict]]] = []
    sueltas = list(secciones)
    for p in partes:
        desde, hasta = int(p.get("desde", 1)), int(p.get("hasta", 10**6))
        elegidas = [s for s in secciones if desde <= int(s["numero"]) <= hasta]
        if not elegidas:
            continue
        for s in elegidas:
            sueltas.remove(s)
        grupos.append((p.get("titulo", ""), elegidas))
    if sueltas:
        # En una hoja única estas secciones quedan al final, fuera del orden del
        # libro, y se leerían como si ese fuera su lugar. Mejor decirlo en la
        # página además de en la consola.
        print(f"aviso: {len(sueltas)} sección(es) fuera de todo [[partes]]: "
              f"{', '.join(s['numero'] for s in sueltas)}. Revisá los rangos en libro.toml")
        grupos.append(("Sin apartado declarado en libro.toml", sueltas))
    return grupos


def render_capitulo(s: dict) -> str:
    """Un capítulo, plegado en un `<details>`.

    El `<summary>` lleva número, título e idea principal: eso es lo que se ve sin
    desplegar, y es lo que convierte la hoja en un mapa del libro. Adentro va el
    documento de estudio completo.

    Los `id` del documento van con el prefijo `sNN-` porque en una sola hoja
    conviven todos los capítulos, y sin prefijo habría tantas anclas
    `vocabulario-clave` como capítulos.
    """
    prefijo = f'{s["ancla"]}-'
    documento, anclas = render_documento(s["texto"], prefijo)
    return (
        f'<details class="capitulo" id="{s["ancla"]}">'
        f"<summary>"
        f'<span class="numero">{s["numero"]}</span>'
        f'<span class="cuerpo"><strong>{html.escape(s["titulo"])}</strong>'
        f'<span class="tesis">{html.escape(s["tesis"])}</span></span>'
        f"</summary>"
        f'<div class="documento">{render_indice_interno(anclas)}{documento}</div>'
        f"</details>"
    )


def render_indice_libro(grupos: list[tuple[str | None, list[dict]]]) -> str:
    """El índice del libro para la columna fija de desktop.

    Debajo de 68rem se oculta por CSS: ahí el cuerpo de la hoja ya es el índice,
    y un segundo listado de treinta y nueve enlaces es scroll de más.
    """
    partes = []
    for titulo, secciones in grupos:
        if titulo:
            partes.append(f'<span class="parte" title="{html.escape(titulo)}">{html.escape(titulo)}</span>')
        partes += [
            f'<a href="#{s["ancla"]}"><span class="numero">{s["numero"]}</span>'
            f'{html.escape(s["titulo"])}</a>'
            for s in secciones
        ]
    return f'<nav class="indice-libro" aria-label="Capítulos del libro">{"".join(partes)}</nav>'


def render_libro(libro: dict) -> str:
    """El libro entero en una sola hoja."""
    cfg = libro["cfg"]
    grupos = agrupar_en_partes(libro["secciones"], cfg)

    bloques = []
    if contenedor := cfg.get("contenedor"):
        bloques.append(f'<h2 class="contenedor">{html.escape(contenedor)}</h2>')
    # Si el libro declara un contenedor, los apartados bajan un nivel para no
    # competir con él. El CSS los toma por clase, no por etiqueta, justamente
    # para que el nivel pueda variar.
    nivel_parte = 3 if cfg.get("contenedor") else 2
    for titulo, secciones in grupos:
        if titulo:
            bloques.append(f'<h{nivel_parte} class="parte">{html.escape(titulo)}</h{nivel_parte}>')
        capitulos = "".join(render_capitulo(s) for s in secciones)
        bloques.append(f'<div class="capitulos">{capitulos}</div>')

    ficha = " · ".join(
        html.escape(str(x))
        for x in [cfg.get("autor"), cfg.get("anio"), cfg.get("edicion")]
        if x
    )
    # El cuerpo va envuelto en `div.hoja` porque en desktop `main` es una grilla
    # de dos columnas: con los hijos sueltos, la grilla los colocaría uno por
    # celda y se desarmaría.
    cuerpo = (
        f'{render_indice_libro(grupos)}'
        f'<div class="hoja">'
        f'<h1>{html.escape(cfg.get("titulo", libro["slug"]))}</h1>'
        f'<p class="ficha">{ficha}</p>'
        '<p class="intro">La idea principal de cada capítulo, para repasar de una pasada. '
        'Desplegá un capítulo para leer su documento de estudio completo.</p>'
        '<div class="controles">'
        '<button type="button" class="alternar-todo" aria-expanded="false">'
        "Abrir todos los capítulos</button></div>"
        f'{"".join(bloques)}'
        f"</div>"
    )
    migas = f'<span>{html.escape(cfg.get("titulo", libro["slug"]))}</span>'
    return pagina(cfg.get("titulo", libro["slug"]), migas, cuerpo, 1, clase_main="con-indice")


# --------------------------------------------------------------------------- #


def construir(libros_dir: Path, destino: Path, estaticos: Path, leer_config) -> tuple[int, int]:
    libros = recolectar(libros_dir, leer_config)
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)

    for archivo in estaticos.iterdir():
        shutil.copy(archivo, destino / archivo.name)

    (destino / "index.html").write_text(render_indice(libros), encoding="utf-8")
    for libro in libros:
        carpeta = destino / libro["slug"]
        carpeta.mkdir()
        (carpeta / "index.html").write_text(render_libro(libro), encoding="utf-8")
    # Una hoja por libro, más el índice general: ya no hay una página por
    # capítulo. El enlace profundo a un capítulo es `index.html#sNN`.
    return len(libros), len(libros) + 1
