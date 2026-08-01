"""Genera el sitio estático a partir de los documentos de estudio.

Sale HTML plano en `sitio/`, sin build ni framework: Vercel lo sirve tal cual.

    sitio/index.html                      lista de libros
    sitio/<libro>/index.html              secciones del libro
    sitio/<libro>/<NN>.html               documento de estudio

Los bloques ```mermaid se convierten en diagramas, el test de comprensión
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

MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
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
        for ruta in estudios:
            numero = ruta.name.split("-")[0]
            if not numero.isdigit():
                print(f"aviso: {ruta.name} no empieza con el número de sección; lo salteo")
                continue
            texto = ruta.read_text(encoding="utf-8")
            tesis = tesis_de(texto)
            if not tesis:
                print(f"aviso: {ruta.name} no tiene bloque de idea principal; va sin resumen en el índice")
            secciones.append(
                {
                    "numero": numero,
                    "archivo": f"{numero}.html",
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


def render_documento(texto: str) -> tuple[str, list[tuple[str, str]]]:
    """Devuelve el HTML del documento y las anclas para su índice interno."""
    cuerpo, flashcards = separar_flashcards(texto)
    cuerpo = re.sub(r"^# +.+\n", "", cuerpo, count=1)  # el título va en la cabecera
    cuerpo, respuestas = separar_respuestas(cuerpo)

    # Solo se anclan los encabezados del cuerpo: los del bloque de respuestas
    # viven dentro de un <details> cerrado y no deben entrar al índice.
    cuerpo_html, anclas = anclar(transformar(md.render(cuerpo)))
    partes = [cuerpo_html]
    if respuestas:
        partes.append(
            '<details class="respuestas"><summary>Respuestas de referencia — no mires hasta responder</summary>'
            + transformar(md.render(respuestas))
            + "</details>"
        )
    if flashcards:
        partes.append(render_flashcards(flashcards))
        anclas.append(("flashcards", "Flashcards"))
    return "\n".join(partes), anclas


def anclar(html_render: str) -> tuple[str, list[tuple[str, str]]]:
    """Pone un `id` en cada `<h2>` y devuelve las anclas del índice interno.

    markdown-it no trae plugin de anclas y el documento no puede escribir HTML
    crudo, así que los `id` se agregan acá, sobre el HTML ya renderizado. Solo
    `h2`: los `h3` de los pasos harían un índice de doce enlaces que en un
    teléfono ocupa media pantalla.
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
        anclas.append((identificador, etiqueta))
        return f'<h2 id="{identificador}">{m.group(1)}</h2>'

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


def render_flashcards(tarjetas: list[tuple[str, str]]) -> str:
    items = "\n".join(
        f'<button class="tarjeta" type="button">'
        f'<span class="pregunta">{html.escape(p)}</span>'
        f'<span class="respuesta">{html.escape(r)}</span></button>'
        for p, r in tarjetas
    )
    return (
        f'<section id="flashcards"><h2>Flashcards</h2>'
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
    con_mermaid: bool = False,
    clase_main: str = "",
) -> str:
    base = "../" * profundidad
    script = (
        f'<script type="module">'
        f'import mermaid from "{MERMAID_CDN}";'
        f'const oscuro = matchMedia("(prefers-color-scheme: dark)").matches;'
        f'mermaid.initialize({{startOnLoad:true, theme: oscuro ? "dark" : "neutral", '
        f'themeVariables:{{fontSize:"15px", fontFamily:"ui-sans-serif, system-ui, sans-serif"}}, '
        f'flowchart:{{curve:"basis", useMaxWidth:true, nodeSpacing:45, rankSpacing:55}}}});'
        f"</script>"
        if con_mermaid
        else ""
    )
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
{script}
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
        print(f"aviso: {len(sueltas)} sección(es) fuera de todo [[partes]]: "
              f"{', '.join(s['numero'] for s in sueltas)}")
        grupos.append((None, sueltas))
    return grupos


def render_libro(libro: dict) -> str:
    cfg = libro["cfg"]
    bloques = []
    for titulo, secciones in agrupar_en_partes(libro["secciones"], cfg):
        if titulo:
            bloques.append(f'<h2 class="parte">{html.escape(titulo)}</h2>')
        filas = "".join(
            f'<a class="seccion" href="{s["archivo"]}">'
            f'<span class="numero">{s["numero"]}</span>'
            f'<span class="cuerpo"><strong>{html.escape(s["titulo"])}</strong>'
            f'<span class="tesis">{html.escape(s["tesis"])}</span></span></a>'
            for s in secciones
        )
        bloques.append(f'<div class="secciones">{filas}</div>')

    ficha = " · ".join(
        html.escape(str(x))
        for x in [cfg.get("autor"), cfg.get("anio"), cfg.get("edicion")]
        if x
    )
    cuerpo = (
        f'<h1>{html.escape(cfg.get("titulo", libro["slug"]))}</h1>'
        f'<p class="ficha">{ficha}</p>'
        '<p class="intro">La idea principal de cada capítulo, para repasar de una pasada. '
        'Hacé clic en un capítulo para abrir su documento de estudio.</p>'
        f'{"".join(bloques)}'
    )
    migas = f'<span>{html.escape(cfg.get("titulo", libro["slug"]))}</span>'
    return pagina(cfg.get("titulo", libro["slug"]), migas, cuerpo, 1)


def render_seccion(libro: dict, i: int) -> str:
    s = libro["secciones"][i]
    cfg = libro["cfg"]
    anterior = libro["secciones"][i - 1] if i > 0 else None
    siguiente = libro["secciones"][i + 1] if i + 1 < len(libro["secciones"]) else None

    nav = ['<nav class="paso">']
    nav.append(f'<a href="{anterior["archivo"]}">← {html.escape(anterior["titulo"])}</a>' if anterior else "<span></span>")
    nav.append(f'<a href="{siguiente["archivo"]}">{html.escape(siguiente["titulo"])} →</a>' if siguiente else "<span></span>")
    nav.append("</nav>")

    documento, anclas = render_documento(s["texto"])
    indice = render_indice_interno(anclas)
    # El índice va como hermano del artículo, no adentro: así en desktop se
    # puede llevar a una columna propia a la izquierda, fija al scrollear.
    cuerpo = (
        f'{indice}'
        f'<article class="documento">'
        f'<h1>{html.escape(s["titulo"])}</h1>'
        f'{documento}'
        f"</article>" + "".join(nav)
    )
    migas = (
        f'<a href="index.html">{html.escape(cfg.get("titulo", libro["slug"]))}</a>'
        f'<span>{html.escape(s["titulo"])}</span>'
    )
    return pagina(
        f'{s["titulo"]} — {cfg.get("titulo", "")}',
        migas,
        cuerpo,
        1,
        con_mermaid=True,
        clase_main="con-indice" if indice else "",
    )


# --------------------------------------------------------------------------- #


def construir(libros_dir: Path, destino: Path, estaticos: Path, leer_config) -> tuple[int, int]:
    libros = recolectar(libros_dir, leer_config)
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)

    for archivo in estaticos.iterdir():
        shutil.copy(archivo, destino / archivo.name)

    (destino / "index.html").write_text(render_indice(libros), encoding="utf-8")
    paginas = 1
    for libro in libros:
        carpeta = destino / libro["slug"]
        carpeta.mkdir()
        (carpeta / "index.html").write_text(render_libro(libro), encoding="utf-8")
        paginas += 1
        for i, s in enumerate(libro["secciones"]):
            (carpeta / s["archivo"]).write_text(render_seccion(libro, i), encoding="utf-8")
            paginas += 1
    return len(libros), paginas
