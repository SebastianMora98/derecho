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
import tomllib
from pathlib import Path

from markdown_it import MarkdownIt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import idea_principal, normalizar_titulo, sin_acentos, slugify  # noqa: E402

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
            # El parseo va acá y no en el render porque acá está el nombre del
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

    Así la hoja muestra el libro completo y no solo lo ya procesado: se ve la
    obra entera y qué falta. La lista sale de `capitulos.toml`, que escribe
    `ema.py dividir` justamente porque `secciones/` no va a git.
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
    return idea_principal(texto)


# --------------------------------------------------------------------------- #
# render de un documento
# --------------------------------------------------------------------------- #


# Qué bloques del documento se sacan del capítulo y a qué consolidado del libro
# van. La clave es UNA PALABRA del título normalizado, no el título entero ni el
# número: renumerar la plantilla ya rompió el sitio en silencio una vez, y
# renombrar «Vocabulario clave» a «Vocabulario del capítulo» tampoco debe romper.
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

    Una línea que no calza NO se descarta en silencio: se devuelve aparte, se
    renderiza en crudo y se avisa. Perder contenido callado es el modo de falla
    que este proyecto ya pagó dos veces.
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

    El capítulo queda con la idea principal, la explicación, el mapa y qué
    releer. El vocabulario, las distinciones, la autoevaluación y las flashcards
    se muestran una sola vez por libro: repetir ese aparato en cada capítulo era
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
    # Lo anterior al primer `##` se conserva: `bloques_h2` lo descartaría, y
    # hasta ahora se renderizaba porque se renderizaba el documento entero.
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


def emparejar_autoevaluacion(preguntas_md: str, respuestas_md: str, origen: str = "") -> str:
    """Devuelve cada pregunta con SU respuesta escondida debajo.

    Antes las diez respuestas vivían en un solo desplegable: para verificar una
    había que abrirlo entero y leerlas todas, que es justo lo que arruina la
    autoevaluación.

    Se emparejan por posición, que es lo que el documento garantiza: pregunta N y
    respuesta N son listas numeradas paralelas. Si las cantidades no coinciden no
    se empareja nada y se devuelve "" — mejor el formato viejo que respuestas
    cruzadas.
    """
    preguntas = items_numerados(preguntas_md)
    contestadas = items_numerados(respuestas_md)
    if not preguntas:
        return ""
    if len(preguntas) != len(contestadas):
        print(f"aviso: {origen}: {len(preguntas)} preguntas y {len(contestadas)} respuestas; no las emparejo")
        return ""

    filas = [
        f'<details class="pregunta">'
        f'<summary><span class="numero">{i}</span>'
        f'<span class="texto">{md.renderInline(p)}</span></summary>'
        f'<div class="respuesta">{md.render(r)}</div>'
        f"</details>"
        for i, (p, r) in enumerate(zip(preguntas, contestadas), 1)
    ]
    return f'<div class="autoevaluacion">{"".join(filas)}</div>'


def anclar(html_render: str, prefijo: str = "") -> str:
    """Pone un `id` en cada `<h2>` y le saca el número al título.

    markdown-it no trae plugin de anclas y el documento no puede escribir HTML
    crudo, así que los `id` se agregan acá, sobre el HTML ya renderizado.

    El `prefijo` es obligatorio en la hoja del libro: los 39 capítulos de una
    página generarían 39 veces `mapa`. El deduplicado se hace sobre el slug SIN
    prefijo, así que la lógica de choque dentro de un capítulo no cambia.

    El número se quita del encabezado visible además del `id`: con cuatro
    bloques no orienta, y hace que un documento con la numeración vieja y uno con
    la nueva se vean igual mientras se regeneran.
    """
    usadas: set[str] = set()

    def reemplazo(m: re.Match) -> str:
        interno = re.sub(r"^(\s*)\d+(\.\d+)*\.?\s*", r"\1", m.group(1))
        crudo = html.unescape(re.sub(r"<[^>]+>", "", interno)).strip()
        base = slugify(crudo, 40)
        identificador, n = base, 2
        while identificador in usadas:
            identificador, n = f"{base}-{n}", n + 1
        usadas.add(identificador)
        return f'<h2 id="{prefijo}{identificador}">{interno}</h2>'

    return re.sub(r"<h2>(.*?)</h2>", reemplazo, html_render, flags=re.DOTALL)


def render_chips(enlaces: list[tuple[str, str]], etiqueta: str) -> str:
    """Fila de enlaces cortos. La usan los consolidados para saltar por capítulo."""
    if len(enlaces) < 2:
        return ""
    items = "".join(f'<a href="#{i}">{html.escape(t)}</a>' for i, t in enlaces)
    return f'<nav class="indice-doc" aria-label="{html.escape(etiqueta)}">{items}</nav>'


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
    divergente es un defecto del documento, no contenido para el lector, y
    mostrar las dos reproduce la redundancia que este rediseño vino a sacar.
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


def chips_de_capitulos(secciones: list[dict], prefijo: str) -> str:
    return render_chips([(f"{prefijo}-{s['ancla']}", s["numero"]) for s in secciones], "Capítulos")


def render_glosario(secciones: list[dict]) -> str:
    entradas = consolidar_vocabulario(secciones)
    sueltos = [(s, x) for s in secciones for x in s.get("extraido", {}).get("sueltos", [])]
    if not entradas and not sueltos:
        return ""
    filas = []
    for e in entradas:
        caps = "".join(
            f'<a class="cap" href="#{c["ancla"]}">{c["numero"]}</a>' for c in e["caps"]
        )
        filas.append(
            f'<dt><span class="termino">{html.escape(e["termino"])}</span>{caps}</dt>'
            f'<dd>{md.renderInline(e["definicion"])}</dd>'
        )
    # Las líneas que no calzaron con el formato se muestran igual: perderlas en
    # silencio sería peor que mostrarlas sin estructura.
    for s, crudo in sueltos:
        filas.append(f'<dt><span class="termino">{s["numero"]}</span></dt><dd>{md.renderInline(crudo)}</dd>')
    return f'<dl class="glosario">{"".join(filas)}</dl>'


def render_distinciones(secciones: list[dict]) -> str:
    """Las distinciones, agrupadas por capítulo de origen.

    No se mezclan: «Tridimensionalismo vs. eclecticismo» solo se entiende dentro
    de su parágrafo.
    """
    conteo = 0
    partes = [chips_de_capitulos([s for s in secciones if s["extraido"]["distinciones"].strip()], "distinciones")]
    for s in secciones:
        bloque = s["extraido"]["distinciones"].strip()
        if not bloque:
            continue
        conteo += 1
        partes.append(
            f'<h3 id="distinciones-{s["ancla"]}">'
            f'<a href="#{s["ancla"]}">{s["numero"]}</a> {html.escape(s["titulo"])}</h3>'
            + transformar(md.render(bloque))
        )
    return "".join(partes) if conteo else ""


def render_autoevaluacion(secciones: list[dict]) -> str:
    """El test del libro, agrupado por capítulo. La numeración reinicia en cada uno."""
    cuerpos = []
    con_preguntas = []
    for s in secciones:
        e = s["extraido"]
        if not e["preguntas"].strip():
            continue
        emparejadas = emparejar_autoevaluacion(e["preguntas"], e["respuestas"], s.get("archivo", s["numero"]))
        if emparejadas:
            cuerpo = emparejadas
        else:
            # Respaldo: preguntas sueltas y las respuestas juntas en un pliegue,
            # antes que perderlas.
            cuerpo = transformar(md.render(e["preguntas"]))
            if e["respuestas"].strip():
                cuerpo += (
                    '<details class="respuestas"><summary>Respuestas de referencia — '
                    "no mires hasta responder</summary>"
                    + transformar(md.render(e["respuestas"]))
                    + "</details>"
                )
        con_preguntas.append(s)
        cuerpos.append(
            f'<h3 id="autoevaluacion-{s["ancla"]}">'
            f'<a href="#{s["ancla"]}">{s["numero"]}</a> {html.escape(s["titulo"])}</h3>{cuerpo}'
        )
    if not cuerpos:
        return ""
    ayuda = (
        '<p class="ayuda">Contestá primero. Al hacer clic en una pregunta '
        "aparece su respuesta debajo.</p>"
    )
    return ayuda + chips_de_capitulos(con_preguntas, "autoevaluacion") + "".join(cuerpos)


def render_mazo(secciones: list[dict]) -> str:
    """Un solo mazo por libro. Un mazo es para machacar, no un índice.

    La procedencia va en la tarjeta como `<span>` y NO como `<a>`: contenido
    interactivo dentro de un `<button>` es HTML inválido.
    """
    vistas: set[str] = set()
    items = []
    for s in secciones:
        for pregunta, respuesta in s["extraido"]["flashcards"]:
            clave = " ".join(re.sub(r"[^\w ]", " ", sin_acentos(pregunta).lower()).split())
            if clave in vistas:
                print(f"aviso: flashcard repetida, la salteo: {pregunta[:50]}")
                continue
            vistas.add(clave)
            items.append(
                f'<button class="tarjeta" type="button">'
                f'<span class="pregunta">{html.escape(pregunta)}</span>'
                f'<span class="respuesta">{html.escape(respuesta)}</span>'
                f'<span class="origen">{html.escape(s["numero"])}</span></button>'
            )
    if not items:
        return ""
    return (
        f'<p class="ayuda">{len(items)} tarjetas. Hacé clic para revelar la respuesta, '
        f"o la tecla R para esconderlas todas.</p>"
        f'<div class="tarjetas">{"".join(items)}</div>'
    )


def bloques_consolidados(secciones: list[dict]) -> tuple[str, list[tuple[str, str]]]:
    """Los cuatro plegables del final de la hoja, y sus entradas para el riel.

    Un consolidado sin contenido no se renderiza ni aparece en el riel: un
    plegable vacío promete algo que no está.
    """
    hechos = [s for s in secciones if not s.get("pendiente")]
    if not hechos:
        return "", []
    de_cuantos = f"De los {len(hechos)} capítulos con documento, de {len(secciones)}."

    definiciones = [
        ("glosario", "Glosario del libro", render_glosario(hechos)),
        ("distinciones", "Distinciones que se confunden", render_distinciones(hechos)),
        ("autoevaluacion", "Autoevaluación", render_autoevaluacion(hechos)),
        ("flashcards", "Flashcards", render_mazo(hechos)),
    ]
    plegables, riel = [], []
    for ancla, titulo, cuerpo in definiciones:
        if not cuerpo:
            continue
        riel.append((ancla, titulo))
        plegables.append(
            f'<details class="consolidado" id="{ancla}">'
            f'<summary><span class="cuerpo"><strong>{titulo}</strong>'
            f'<span class="tesis">{de_cuantos}</span></span></summary>'
            f'<div class="contenido">{cuerpo}</div></details>'
        )
    if not plegables:
        return "", []
    return (
        '<h2 class="parte">Del libro entero</h2>'
        f'<div class="consolidados">{"".join(plegables)}</div>'
    ), riel


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
            f'<p class="meta">{sum(1 for s in libro["secciones"] if not s.get("pendiente"))}'
            f' de {len(libro["secciones"])} capítulos con documento</p>'
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
    desplegar, y es lo que convierte la hoja en un mapa del libro. Adentro va
    solo lo esencial del capítulo —idea, explicación, mapa y qué releer—: el
    vocabulario, las distinciones, el test y las flashcards se muestran una vez
    por libro, al final de la hoja.

    Los `id` van con el prefijo `sNN-` porque en una sola hoja conviven todos los
    capítulos, y sin prefijo habría tantas anclas `mapa` como capítulos.
    """
    # Un capítulo sin documento todavía se muestra igual, para que la hoja sea
    # el libro entero y no solo lo ya procesado. Va como <div> y no como
    # <details>: no hay nada que desplegar, y un desplegable vacío promete algo
    # que no está.
    if s.get("pendiente"):
        return (
            f'<div class="capitulo pendiente" id="{s["ancla"]}">'
            f'<span class="numero">{s["numero"]}</span>'
            f'<span class="cuerpo"><strong>{html.escape(s["titulo"])}</strong>'
            f'<span class="tesis">Todavía sin documento de estudio.</span></span>'
            f"</div>"
        )

    # Sin fila de chips: estaba dimensionada para siete bloques largos y con
    # cuatro cortos es ruido justo debajo del summary que acabás de abrir.
    documento = anclar(transformar(md.render(s["visible"])), f'{s["ancla"]}-')
    return (
        f'<details class="capitulo" id="{s["ancla"]}">'
        f"<summary>"
        f'<span class="numero">{s["numero"]}</span>'
        f'<span class="cuerpo"><strong>{html.escape(s["titulo"])}</strong>'
        f'<span class="tesis">{html.escape(s["tesis"])}</span></span>'
        f"</summary>"
        f'<div class="documento">{documento}</div>'
        f"</details>"
    )


def render_indice_libro(
    grupos: list[tuple[str | None, list[dict]]],
    consolidados: list[tuple[str, str]],
) -> str:
    """El índice del libro para la columna fija de desktop.

    Debajo de 68rem se oculta por CSS: ahí el cuerpo de la hoja ya es el índice,
    y un segundo listado de treinta y nueve enlaces es scroll de más.
    """
    partes = []
    for titulo, secciones in grupos:
        if titulo:
            partes.append(f'<span class="parte" title="{html.escape(titulo)}">{html.escape(titulo)}</span>')
        partes += [
            f'<a href="#{s["ancla"]}"{" class=pendiente" if s.get("pendiente") else ""}>'
            f'<span class="numero">{s["numero"]}</span>'
            f'{html.escape(s["titulo"])}</a>'
            for s in secciones
        ]
    # Van DESPUÉS de los capítulos: el marcador de posición recorre los destinos
    # en el orden del riel y corta en el primero que queda por debajo del límite,
    # así que ese orden tiene que coincidir con el de la hoja.
    if consolidados:
        partes.append('<span class="parte">Del libro entero</span>')
        partes += [f'<a href="#{ancla}">{html.escape(titulo)}</a>' for ancla, titulo in consolidados]
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

    consolidado, riel = bloques_consolidados(libro["secciones"])
    bloques.append(consolidado)

    ficha = " · ".join(
        html.escape(str(x))
        for x in [cfg.get("autor"), cfg.get("anio"), cfg.get("edicion")]
        if x
    )
    # El cuerpo va envuelto en `div.hoja` porque en desktop `main` es una grilla
    # de dos columnas: con los hijos sueltos, la grilla los colocaría uno por
    # celda y se desarmaría.
    cuerpo = (
        f'{render_indice_libro(grupos, riel)}'
        f'<div class="hoja">'
        f'<h1>{html.escape(cfg.get("titulo", libro["slug"]))}</h1>'
        f'<p class="ficha">{ficha}</p>'
        '<p class="intro">La idea principal de cada capítulo, para repasar de una pasada. '
        'Desplegá un capítulo para leer lo esencial; el vocabulario, el test y las '
        'flashcards del libro entero están al final.</p>'
        '<div class="controles">'
        '<button type="button" class="alternar-todo" aria-expanded="false">'
        "Abrir todo el libro</button></div>"
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
