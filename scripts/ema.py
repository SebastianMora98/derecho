#!/usr/bin/env python3
"""CLI del taller de documentos.

Flujo:
    convertir  entrada/*.pdf        -> libros/<slug>/libro.md
    dividir    libros/<slug>        -> libros/<slug>/secciones/NN-*.md
    preparar   libros/<slug> NN     -> libros/<slug>/prompts/NN-*.md
    web                             -> sitio/ (HTML estático para Vercel)
    estado                          -> resumen de avance

Uso:
    uv run scripts/ema.py <comando> [args]
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import idea_principal, slugify  # noqa: E402
from limpieza import limpiar_pdf  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
LIBROS = RAIZ / "libros"
ENTRADA = RAIZ / "entrada"
PROMPTS = RAIZ / "prompts"
SITIO = RAIZ / "sitio"
ESTATICOS = RAIZ / "estaticos"

# Tope duro de una sección, en caracteres. ~30k ≈ 10-15 páginas: más que eso
# en una sola corrida produce un documento superficial.
MAX_CHARS = 30_000
# Un capítulo más corto que esto no da para una sesión de estudio propia: se
# pega a su vecino. Los de tamaño normal NUNCA se agrupan — cada documento de
# estudio corresponde a un capítulo del autor, que es lo que se puede citar.
CORTO = 2_000
# Ningún pegote de capítulos cortos pasa de acá.
TOPE_FUSION = 6_000
# Largo mínimo para que el texto anterior al primer encabezado (portadilla,
# créditos) valga como sección propia.
MIN_PRELUDIO = 1_500


# --------------------------------------------------------------------------- #
# utilidades
# --------------------------------------------------------------------------- #


def error(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def resolver_libro(nombre: str) -> Path:
    """Acepta el slug, o una ruta a la carpeta del libro."""
    candidatos = [Path(nombre), LIBROS / nombre, LIBROS / slugify(nombre)]
    for c in candidatos:
        if c.is_dir() and (c / "libro.md").exists():
            return c.resolve()
    error(f"no encuentro el libro '{nombre}'. Libros disponibles: {', '.join(listar_libros()) or '(ninguno)'}")


def listar_libros() -> list[str]:
    if not LIBROS.exists():
        return []
    return sorted(p.name for p in LIBROS.iterdir() if (p / "libro.md").exists())


def leer_config(libro: Path) -> dict:
    ruta = libro / "libro.toml"
    if not ruta.exists():
        return {}
    with ruta.open("rb") as fh:
        return tomllib.load(fh)


def escribir_config_inicial(libro: Path, titulo: str, fuente: str) -> None:
    ruta = libro / "libro.toml"
    if ruta.exists():
        return
    ruta.write_text(
        f'''# Ficha del libro. Editá estos valores: alimentan la sección
# CONFIGURACIÓN de los prompts generados por `ema.py preparar`.

titulo = "{titulo}"
autor = ""
edicion = ""
fuente = "{fuente}"

# principiante / intermedio / avanzado
nivel = "intermedio"
# examen / investigacion / cultura-general / aplicacion-practica
proposito = "cultura-general"
tiempo = "90 minutos"
# paginas / capitulos / subtitulos / parrafos — ver la nota en
# prompts/estudio.md para cuál corresponde según cómo esté marcado el texto
formato_citas = "subtitulos"

# Encabezados que la conversión dejó como `##` pero no son capítulos del autor
# (portadilla, índice, catálogo de la editorial). `dividir` los descarta.
# Son expresiones regulares, sin distinguir mayúsculas.
omitir = []

# Variantes de la plantilla a activar. Ver prompts/variantes.md
# Opciones: examen, investigacion, tecnico, narrativo
variantes = []

# Plantilla base a usar en `preparar` (archivo dentro de prompts/)
plantilla = "estudio.md"
''',
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# convertir
# --------------------------------------------------------------------------- #


def cmd_convertir(args: argparse.Namespace) -> None:
    try:
        from markitdown import MarkItDown
    except ImportError:
        error("falta markitdown. Instalá con: uv sync")

    rutas: list[Path] = []
    for objetivo in args.archivos or [ENTRADA]:
        p = Path(objetivo)
        if p.is_dir():
            rutas += sorted(f for f in p.iterdir() if f.is_file() and not f.name.startswith("."))
        elif p.is_file():
            rutas.append(p)
        else:
            error(f"no existe: {p}")

    if not rutas:
        error(f"no hay archivos para convertir. Dejá los documentos en {ENTRADA.relative_to(RAIZ)}/")

    md = MarkItDown(enable_plugins=False)

    for ruta in rutas:
        slug = args.slug or slugify(ruta.stem)
        libro = LIBROS / slug
        destino = libro / "libro.md"

        if destino.exists() and not args.forzar:
            print(f"~ {slug}: ya convertido (usá --forzar para rehacerlo)")
            continue

        print(f"→ convirtiendo {ruta.name} ...", flush=True)
        try:
            resultado = md.convert(str(ruta))
        except Exception as exc:  # noqa: BLE001 - queremos seguir con los demás
            print(f"✗ {ruta.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue

        for sub in ("original", "secciones", "prompts", "estudio", "artefactos"):
            (libro / sub).mkdir(parents=True, exist_ok=True)

        copia = libro / "original" / ruta.name
        if not copia.exists():
            copia.write_bytes(ruta.read_bytes())

        texto = resultado.text_content
        if ruta.suffix.lower() == ".pdf" and not args.crudo:
            texto = limpiar_pdf(texto)
        texto = limpiar(texto)
        destino.write_text(texto, encoding="utf-8")
        titulo = (resultado.title or ruta.stem).strip()
        escribir_config_inicial(libro, titulo.replace('"', "'"), ruta.name)

        print(f"✓ {slug}: {len(texto):,} caracteres → {destino.relative_to(RAIZ)}")
        print(f"  siguiente: uv run scripts/ema.py dividir {slug}")


def limpiar(texto: str) -> str:
    """Normaliza saltos de línea y quita ruido típico de la extracción de PDF."""
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = re.sub(r"[ \t]+\n", "\n", texto)
    texto = re.sub(r"\n{4,}", "\n\n\n", texto)
    return texto.strip() + "\n"


# --------------------------------------------------------------------------- #
# dividir
# --------------------------------------------------------------------------- #


def cmd_dividir(args: argparse.Namespace) -> None:
    libro = resolver_libro(args.libro)
    cfg = leer_config(libro)
    texto = (libro / "libro.md").read_text(encoding="utf-8")
    destino = libro / "secciones"
    destino.mkdir(exist_ok=True)

    if any(destino.glob("*.md")) and not args.forzar:
        error(f"{libro.name}/secciones ya tiene contenido. Usá --forzar para rehacerlo.")
    for viejo in destino.glob("*.md"):
        viejo.unlink()

    bloques = partir_por_encabezado(texto, args.nivel)
    if not bloques:
        bloques = [{"titulo": "Documento completo", "cuerpo": texto, "apartado": None}]

    bloques = descartar_paratexto(bloques, (args.omitir or []) + list(cfg.get("omitir", [])))

    secciones: list[dict] = []
    for b in bloques:
        trozos = partir_por_tamano(b["cuerpo"], args.max_chars)
        if len(trozos) == 1:
            secciones.append(dict(b, capitulos=[b["titulo"]]))
        else:
            # Un capítulo enorme no se puede procesar de una sola corrida.
            for i, trozo in enumerate(trozos, 1):
                secciones.append(
                    dict(
                        b,
                        titulo=f"{b['titulo']} (parte {i}/{len(trozos)})",
                        cuerpo=trozo,
                        capitulos=[b["titulo"]],
                    )
                )

    secciones = fusionar_cortas(secciones, args.corto, args.tope_fusion)

    indice = ["# Índice de secciones", "", f"Fuente: `libro.md` · {len(secciones)} secciones", ""]
    apartado_actual = object()
    for i, s in enumerate(secciones, 1):
        nombre = f"{i:02d}-{slugify(s['titulo'], 40)}.md"
        meta = [f"seccion: {i:02d}", f"titulo: {s['titulo']}"]
        if len(s["capitulos"]) > 1:
            meta.append(f"capitulos: {', '.join(s['capitulos'])}")
        if s.get("apartado"):
            meta.append(f"apartado: {s['apartado']}")
        meta.append(f"caracteres: {len(s['cuerpo'])}")
        (destino / nombre).write_text(
            f"<!-- {' | '.join(meta)} -->\n\n{s['cuerpo'].strip()}\n", encoding="utf-8"
        )
        if s.get("apartado") != apartado_actual:
            apartado_actual = s.get("apartado")
            if apartado_actual:
                indice += ["", f"## {apartado_actual}", ""]
        indice.append(f"- `{nombre}` — {s['titulo']} ({len(s['cuerpo']):,} car.)")

    (destino / "indice.md").write_text("\n".join(indice) + "\n", encoding="utf-8")
    escribir_manifiesto(libro, secciones)

    fusionadas = [s for s in secciones if len(s["capitulos"]) > 1]
    if fusionadas:
        print(f"  {len(fusionadas)} sección(es) juntan capítulos cortos:")
        for s in fusionadas:
            print(f"    {' + '.join(s['capitulos'])}  ({len(s['cuerpo']):,} car.)")

    partes = bloque_partes(secciones)
    if partes:
        (destino / "indice.md").write_text(
            "\n".join(indice) + "\n\n<!--\nPegá esto en libro.toml para que el índice del "
            f"sitio agrupe por apartado:\n\n{partes}\n-->\n",
            encoding="utf-8",
        )
        print("\n  Los apartados del libro dan este bloque para libro.toml:\n")
        print("\n".join(f"  {l}" for l in partes.splitlines()))

    print(f"\n✓ {libro.name}: {len(secciones)} secciones → {destino.relative_to(RAIZ)}")
    print(f"  siguiente: uv run scripts/ema.py preparar {libro.name} 1")


def partir_por_encabezado(texto: str, nivel: int | None) -> list[dict]:
    """Corta por encabezados markdown, conservando el apartado que los contiene.

    Un libro puede tener tres pisos: capítulo > apartado > parágrafo. Los
    apartados vienen marcados con `#` (los pone `ocr.py`) y los capítulos con
    `##`. Se corta por capítulo, pero cada bloque recuerda a qué apartado
    pertenece: eso es lo que después permite agrupar el índice del sitio.
    Un libro de jerarquía plana no tiene ningún `#` y cae en el camino de
    siempre, con `apartado = None`.
    """
    niveles = [nivel] if nivel else [1, 2, 3]
    for n in niveles:
        patron = re.compile(rf"^{'#' * n} +(.+)$", re.MULTILINE)
        marcas = list(patron.finditer(texto))
        if len(marcas) < (1 if nivel else 3):
            continue

        bloques: list[dict] = []
        preludio = texto[: marcas[0].start()].strip()
        if len(preludio) > MIN_PRELUDIO:
            bloques.append({"titulo": "Preliminares", "cuerpo": preludio, "apartado": None})
        for i, m in enumerate(marcas):
            fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
            bloques.append(
                {
                    "titulo": m.group(1).strip(),
                    "cuerpo": texto[m.start() : fin].strip(),
                    "apartado": apartado_de(texto, m.start(), n),
                }
            )
        return bloques
    return []


def apartado_de(texto: str, posicion: int, nivel: int) -> str | None:
    """El último encabezado de nivel superior antes de `posicion`."""
    if nivel < 2:
        return None
    previos = list(re.finditer(r"^# +(.+)$", texto[:posicion], re.MULTILINE))
    return previos[-1].group(1).strip() if previos else None


def descartar_paratexto(bloques: list[dict], patrones: list[str]) -> list[dict]:
    """Saca los encabezados que no son capítulos del autor.

    La conversión de un PDF deja como encabezado cosas que no lo son:
    portadilla, ISBN, el índice, el catálogo de la editorial. No se pueden
    filtrar por tamaño ni por el patrón del título — «Publicaciones» tiene
    5.500 caracteres y «8. Nota sobre la presente edición» sí es contenido
    útil —, así que se listan a mano en `libro.toml`.
    """
    if not patrones:
        return bloques
    compilados = [re.compile(p, re.IGNORECASE) for p in patrones]
    salida, descartados = [], []
    for b in bloques:
        if any(c.search(b["titulo"]) for c in compilados):
            descartados.append(b["titulo"])
        else:
            salida.append(b)
    if descartados:
        print(f"  descartados por `omitir` ({len(descartados)}): {', '.join(descartados)}")
    return salida


def escribir_manifiesto(libro: Path, secciones: list[dict]) -> None:
    """Deja la lista de capítulos del libro en un archivo que sí va a git.

    El sitio necesita conocer TODOS los capítulos para mostrar el libro
    completo, incluidos los que todavía no tienen documento de estudio. Pero
    `secciones/` está fuera de git —ahí está el texto del original— y el sitio
    solo puede leer lo que está versionado. Este manifiesto es el puente: lo
    escribe `dividir` y lo lee `sitio.py`. No editarlo a mano.
    """
    lineas = [
        "# Generado por `ema.py dividir`. No editar a mano: se reescribe.",
        "# El sitio lo usa para mostrar todos los capítulos del libro, tengan o",
        "# no documento de estudio todavía.",
        "",
    ]
    for i, s in enumerate(secciones, 1):
        lineas += [
            "[[capitulos]]",
            f'numero = "{i:02d}"',
            f"titulo = {cadena_toml(s['titulo'])}",
            f"caracteres = {len(s['cuerpo'])}",
            "",
        ]
    (libro / "capitulos.toml").write_text("\n".join(lineas), encoding="utf-8")


def cadena_toml(texto: str) -> str:
    """Cita un valor para TOML. Los títulos del OCR traen comillas dobles."""
    escapado = texto.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escapado}"'


def bloque_partes(secciones: list[dict]) -> str:
    """Arma el TOML `[[partes]]` con el rango de secciones de cada apartado."""
    rangos: list[tuple[str, int, int]] = []
    for i, s in enumerate(secciones, 1):
        apartado = s.get("apartado")
        if not apartado:
            continue
        if rangos and rangos[-1][0] == apartado:
            rangos[-1] = (apartado, rangos[-1][1], i)
        else:
            rangos.append((apartado, i, i))
    lineas = []
    for titulo, desde, hasta in rangos:
        lineas += ["[[partes]]", f'titulo = "{titulo}"', f"desde = {desde}", f"hasta = {hasta}", ""]
    return "\n".join(lineas).strip()


def partir_por_tamano(texto: str, maximo: int) -> list[str]:
    if len(texto) <= maximo:
        return [texto]
    parrafos = texto.split("\n\n")
    trozos, actual = [], ""
    for p in parrafos:
        if actual and len(actual) + len(p) + 2 > maximo:
            trozos.append(actual.strip())
            actual = p
        else:
            actual = f"{actual}\n\n{p}" if actual else p
    if actual.strip():
        trozos.append(actual.strip())
    return trozos


def fusionar_cortas(secciones: list[dict], corto: int, tope: int) -> list[dict]:
    """Cada documento de estudio es un capítulo del autor.

    Solo se agrupa el capítulo demasiado corto para sostener una sesión propia,
    y se lo pega a su vecino MÁS CHICO: si se tomara siempre el siguiente, un
    capítulo de dos párrafos podría caer sobre uno de veinte mil caracteres.
    Nunca se cruza un apartado, y el resultado se vuelve a examinar para que
    tres capítulos muy breves y seguidos entren en un solo documento.
    """
    s = [dict(x) for x in secciones]
    i = 0
    while i < len(s):
        if len(s[i]["cuerpo"]) >= corto:
            i += 1
            continue
        vecinos = [
            j
            for j in (i - 1, i + 1)
            if 0 <= j < len(s)
            and s[j].get("apartado") == s[i].get("apartado")
            and len(s[j]["cuerpo"]) + len(s[i]["cuerpo"]) <= tope
        ]
        if not vecinos:
            i += 1
            continue
        j = min(vecinos, key=lambda k: len(s[k]["cuerpo"]))
        a, b = sorted((i, j))
        s[a] = dict(
            s[a],
            titulo=f"{s[a]['titulo']} + {s[b]['titulo']}",
            cuerpo=f"{s[a]['cuerpo']}\n\n{s[b]['cuerpo']}",
            capitulos=s[a]["capitulos"] + s[b]["capitulos"],
        )
        del s[b]
        i = a  # el pegote puede seguir siendo corto: se revisa de nuevo
    return s


# --------------------------------------------------------------------------- #
# preparar
# --------------------------------------------------------------------------- #


def cmd_preparar(args: argparse.Namespace) -> None:
    libro = resolver_libro(args.libro)
    cfg = leer_config(libro)
    secciones = sorted(p for p in (libro / "secciones").glob("*.md") if p.name != "indice.md")
    if not secciones:
        error(f"{libro.name} no tiene secciones. Corré primero: ema.py dividir {libro.name}")

    plantilla_nombre = args.plantilla or cfg.get("plantilla", "estudio.md")
    plantilla_ruta = PROMPTS / plantilla_nombre
    if not plantilla_ruta.exists():
        error(f"no existe la plantilla {plantilla_ruta.relative_to(RAIZ)}")
    # El comentario HTML inicial es documentación para quien edita la plantilla
    # (y menciona los propios marcadores): no debe llegar al prompt.
    plantilla = re.sub(r"\A\s*<!--.*?-->\s*", "", plantilla_ruta.read_text(encoding="utf-8"), flags=re.DOTALL)

    objetivos = seleccionar(secciones, args.seccion)
    (libro / "prompts").mkdir(exist_ok=True)

    for ruta in objetivos:
        numero = ruta.name.split("-")[0]
        cuerpo = ruta.read_text(encoding="utf-8")
        titulo = extraer_titulo(cuerpo) or ruta.stem
        cuerpo = re.sub(r"^<!--.*?-->\n+", "", cuerpo, flags=re.DOTALL)

        obra = ", ".join(x for x in [cfg.get("titulo", libro.name), cfg.get("autor"), cfg.get("edicion")] if x)
        reemplazos = {
            "OBRA": obra,
            "SECCION": f"sección {numero} — {titulo}",
            "NIVEL": cfg.get("nivel", "intermedio"),
            "PROPOSITO": cfg.get("proposito", "cultura general"),
            "TIEMPO": cfg.get("tiempo", "90 minutos"),
            "FORMATO_CITAS": cfg.get("formato_citas", "subtítulos"),
            "CONTEXTO_PREVIO": contexto_previo(libro, numero),
            "VARIANTES": variantes_texto(cfg.get("variantes", [])),
            "TEXTO": cuerpo.strip(),
        }
        render = plantilla
        for clave, valor in reemplazos.items():
            render = render.replace("{{" + clave + "}}", valor)

        salida = libro / "prompts" / f"{numero}-{slugify(plantilla_ruta.stem, 20)}.md"
        salida.write_text(render, encoding="utf-8")
        print(f"✓ {salida.relative_to(RAIZ)} ({len(render):,} car.)")

    print("\n  siguiente: pedile a Claude que procese ese prompt y guarde la salida en")
    print(f"  {(libro / 'estudio').relative_to(RAIZ)}/")


def seleccionar(secciones: list[Path], spec: str | None) -> list[Path]:
    if not spec or spec == "todas":
        return secciones
    numeros: set[int] = set()
    for parte in spec.split(","):
        parte = parte.strip()
        if "-" in parte:
            a, b = parte.split("-", 1)
            numeros.update(range(int(a), int(b) + 1))
        else:
            numeros.add(int(parte))
    elegidas = [p for p in secciones if int(p.name.split("-")[0]) in numeros]
    if not elegidas:
        error(f"ninguna sección coincide con '{spec}'")
    return elegidas


def extraer_titulo(cuerpo: str) -> str | None:
    m = re.search(r"titulo: (.+?) \|", cuerpo)
    return m.group(1) if m else None


def contexto_previo(libro: Path, numero: str) -> str:
    """Junta las ideas principales ya generadas, para encadenar capítulos."""
    ideas = []
    for previo in sorted((libro / "estudio").glob("*.md")):
        if previo.name.split("-")[0] >= numero:
            continue
        if idea := idea_principal(previo.read_text(encoding="utf-8")):
            ideas.append(f"- {previo.name.split('-')[0]}: {idea}")
    if not ideas:
        return "(esta es la primera sección procesada)"
    return "Ya procesamos estas secciones y sus ideas principales:\n" + "\n".join(ideas)


def variantes_texto(variantes: list[str]) -> str:
    archivo = PROMPTS / "variantes.md"
    if not variantes or not archivo.exists():
        return "(ninguna variante activa)"
    texto = archivo.read_text(encoding="utf-8")
    bloques = []
    for v in variantes:
        m = re.search(rf"^## {re.escape(v)}\b.*?\n(.*?)(?=\n## |\Z)", texto, re.MULTILINE | re.DOTALL)
        if m:
            bloques.append(m.group(1).strip())
        else:
            print(f"aviso: variante '{v}' no está en prompts/variantes.md", file=sys.stderr)
    return "\n\n".join(bloques) or "(ninguna variante activa)"


# --------------------------------------------------------------------------- #
# web
# --------------------------------------------------------------------------- #


def cmd_web(args: argparse.Namespace) -> None:
    from sitio import construir

    # Comprobar ANTES de construir: `construir` empieza borrando sitio/ entero,
    # así que fallar después dejaría el sitio publicado vacío — y cada push
    # redespliega solo.
    if not any((p / "estudio").glob("*.md") for p in LIBROS.iterdir() if p.is_dir()):
        error("todavía no hay documentos de estudio. Generá al menos uno en libros/<slug>/estudio/")

    libros, paginas = construir(LIBROS, SITIO, ESTATICOS, leer_config)
    print(f"✓ {libros} libro(s), {paginas} páginas → {SITIO.relative_to(RAIZ)}/")
    print("  ver en local: python3 -m http.server -d sitio 8000")


# --------------------------------------------------------------------------- #
# estado
# --------------------------------------------------------------------------- #


def cmd_estado(args: argparse.Namespace) -> None:
    libros = listar_libros()
    if not libros:
        print("No hay libros todavía. Dejá archivos en entrada/ y corré: uv run scripts/ema.py convertir")
        return
    for nombre in libros:
        libro = LIBROS / nombre
        cfg = leer_config(libro)
        secciones = [p for p in (libro / "secciones").glob("*.md") if p.name != "indice.md"]
        prompts = list((libro / "prompts").glob("*.md"))
        estudios = list((libro / "estudio").glob("*.md"))
        artefactos = list((libro / "artefactos").glob("*"))
        print(f"\n{nombre}  —  {cfg.get('titulo', '?')} · {cfg.get('autor') or 'autor sin definir'}")
        print(f"  secciones: {len(secciones):>3}   prompts: {len(prompts):>3}   estudio: {len(estudios):>3}   artefactos: {len(artefactos):>3}")
        numeros = {p.name.split("-")[0] for p in secciones}
        pendientes = sorted(n for n in numeros if not any(e.name.startswith(n) for e in estudios))
        if pendientes:
            print(f"  pendientes de estudio: {', '.join(pendientes)}")
        # El caso inverso: un documento cuya sección ya no existe. Pasa al
        # re-dividir con otro criterio, y si no se borra reaparece en el sitio
        # con un número que ya no corresponde.
        huerfanos = sorted(e.name for e in estudios if e.name.split("-")[0] not in numeros)
        if huerfanos:
            print(f"  ⚠ documentos sin sección correspondiente: {', '.join(huerfanos)}")


# --------------------------------------------------------------------------- #


def main() -> None:
    parser = argparse.ArgumentParser(prog="ema.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("convertir", help="documentos → libros/<slug>/libro.md")
    p.add_argument("archivos", nargs="*", help="archivos o carpetas (por defecto: entrada/)")
    p.add_argument("--slug", help="nombre de carpeta a usar (solo con un archivo)")
    p.add_argument("--forzar", action="store_true")
    p.add_argument("--crudo", action="store_true", help="no aplicar la limpieza de PDF")
    p.set_defaults(func=cmd_convertir)

    p = sub.add_parser("dividir", help="libro.md → secciones/ (una por capítulo)")
    p.add_argument("libro")
    p.add_argument("--nivel", type=int, choices=[1, 2, 3], help="nivel de encabezado del capítulo")
    p.add_argument("--max-chars", type=int, default=MAX_CHARS, help="tope duro de una sección")
    p.add_argument("--corto", type=int, default=CORTO, help="por debajo de esto, el capítulo se junta con su vecino")
    p.add_argument("--tope-fusion", type=int, default=TOPE_FUSION, help="tope de un grupo de capítulos cortos")
    p.add_argument("--omitir", action="append", metavar="PATRON", help="encabezados que no son capítulos (repetible)")
    p.add_argument("--forzar", action="store_true")
    p.set_defaults(func=cmd_dividir)

    p = sub.add_parser("preparar", help="sección + plantilla → prompt listo")
    p.add_argument("libro")
    p.add_argument("seccion", nargs="?", help="'3', '1-4', '2,5' o 'todas'")
    p.add_argument("--plantilla", help="archivo de prompts/ (por defecto el de libro.toml)")
    p.set_defaults(func=cmd_preparar)

    p = sub.add_parser("web", help="documentos de estudio → sitio/ (HTML estático)")
    p.set_defaults(func=cmd_web)

    p = sub.add_parser("estado", help="resumen de avance")
    p.set_defaults(func=cmd_estado)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
