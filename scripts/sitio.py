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
from pathlib import Path

from markdown_it import MarkdownIt

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
            texto = ruta.read_text(encoding="utf-8")
            secciones.append(
                {
                    "numero": ruta.name.split("-")[0],
                    "archivo": f"{ruta.name.split('-')[0]}.html",
                    "titulo": titulo_de(texto, ruta.stem),
                    "tesis": tesis_de(texto),
                    "texto": texto,
                }
            )
        libros.append({"slug": carpeta.name, "cfg": cfg, "secciones": secciones})
    return libros


def titulo_de(texto: str, respaldo: str) -> str:
    m = re.search(r"^# +(.+)$", texto, re.MULTILINE)
    return m.group(1).strip() if m else respaldo


def tesis_de(texto: str) -> str:
    """La primera frase de la sección 2 sirve de resumen en los índices."""
    m = re.search(r"^## *2\..*?\n+(.+?)(?=\n\n|\n##)", texto, re.MULTILINE | re.DOTALL)
    return " ".join(m.group(1).split()) if m else ""


# --------------------------------------------------------------------------- #
# render de un documento
# --------------------------------------------------------------------------- #


def render_documento(texto: str) -> str:
    cuerpo, flashcards = separar_flashcards(texto)
    cuerpo = re.sub(r"^# +.+\n", "", cuerpo, count=1)  # el título va en la cabecera
    cuerpo, respuestas = separar_respuestas(cuerpo)

    partes = [transformar(md.render(cuerpo))]
    if respuestas:
        partes.append(
            '<details class="respuestas"><summary>Respuestas de referencia — no mires hasta responder</summary>'
            + transformar(md.render(respuestas))
            + "</details>"
        )
    if flashcards:
        partes.append(render_flashcards(flashcards))
    return "\n".join(partes)


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


def pagina(titulo: str, migas: str, contenido: str, profundidad: int, con_mermaid: bool = False) -> str:
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
<main>
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


def render_libro(libro: dict) -> str:
    cfg = libro["cfg"]
    filas = []
    for s in libro["secciones"]:
        filas.append(
            f'<a class="seccion" href="{s["archivo"]}">'
            f'<span class="numero">{s["numero"]}</span>'
            f'<span class="cuerpo"><strong>{html.escape(s["titulo"])}</strong>'
            f'<span class="tesis">{html.escape(s["tesis"])}</span></span></a>'
        )
    ficha = " · ".join(
        html.escape(str(x))
        for x in [cfg.get("autor"), cfg.get("anio"), cfg.get("edicion")]
        if x
    )
    cuerpo = (
        f'<h1>{html.escape(cfg.get("titulo", libro["slug"]))}</h1>'
        f'<p class="ficha">{ficha}</p>'
        f'<div class="secciones">{"".join(filas)}</div>'
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

    cuerpo = (
        f'<article class="documento">'
        f'<h1>{html.escape(s["titulo"])}</h1>'
        f'{render_documento(s["texto"])}'
        f"</article>" + "".join(nav)
    )
    migas = (
        f'<a href="index.html">{html.escape(cfg.get("titulo", libro["slug"]))}</a>'
        f'<span>{html.escape(s["titulo"])}</span>'
    )
    return pagina(f'{s["titulo"]} — {cfg.get("titulo", "")}', migas, cuerpo, 1, con_mermaid=True)


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
