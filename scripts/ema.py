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
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from limpieza import limpiar_pdf  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
LIBROS = RAIZ / "libros"
ENTRADA = RAIZ / "entrada"
PROMPTS = RAIZ / "prompts"
SITIO = RAIZ / "sitio"
ESTATICOS = RAIZ / "estaticos"

# Tamaño objetivo de una sección, en caracteres. ~30k ≈ 10-15 páginas,
# el rango que la plantilla recomienda por corrida.
MAX_CHARS = 30_000
MIN_CHARS = 1_500


# --------------------------------------------------------------------------- #
# utilidades
# --------------------------------------------------------------------------- #


def slugify(texto: str, largo: int = 60) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^\w\s-]", "", texto.lower())
    texto = re.sub(r"[\s_-]+", "-", texto).strip("-")
    return texto[:largo] or "sin-titulo"


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
    texto = (libro / "libro.md").read_text(encoding="utf-8")
    destino = libro / "secciones"
    destino.mkdir(exist_ok=True)

    if any(destino.glob("*.md")) and not args.forzar:
        error(f"{libro.name}/secciones ya tiene contenido. Usá --forzar para rehacerlo.")
    for viejo in destino.glob("*.md"):
        viejo.unlink()

    bloques = partir_por_encabezado(texto, args.nivel)
    if not bloques:
        bloques = [("Documento completo", texto)]

    secciones: list[tuple[str, str]] = []
    for titulo, cuerpo in bloques:
        trozos = partir_por_tamano(cuerpo, args.max_chars)
        if len(trozos) == 1:
            secciones.append((titulo, trozos[0]))
        else:
            for i, trozo in enumerate(trozos, 1):
                secciones.append((f"{titulo} (parte {i}/{len(trozos)})", trozo))

    secciones = fusionar_cortas(secciones, args.max_chars, args.objetivo)

    indice = ["# Índice de secciones", "", f"Fuente: `libro.md` · {len(secciones)} secciones", ""]
    for i, (titulo, cuerpo) in enumerate(secciones, 1):
        nombre = f"{i:02d}-{slugify(titulo, 40)}.md"
        (destino / nombre).write_text(
            f"<!-- seccion: {i:02d} | titulo: {titulo} | caracteres: {len(cuerpo)} -->\n\n{cuerpo.strip()}\n",
            encoding="utf-8",
        )
        indice.append(f"- `{nombre}` — {titulo} ({len(cuerpo):,} car.)")

    (destino / "indice.md").write_text("\n".join(indice) + "\n", encoding="utf-8")
    print(f"✓ {libro.name}: {len(secciones)} secciones → {destino.relative_to(RAIZ)}")
    print(f"  siguiente: uv run scripts/ema.py preparar {libro.name} 1")


def partir_por_encabezado(texto: str, nivel: int | None) -> list[tuple[str, str]]:
    """Corta por encabezados markdown. Si no se fija nivel, elige el más
    superficial que produzca al menos 3 bloques."""
    niveles = [nivel] if nivel else [1, 2, 3]
    for n in niveles:
        patron = re.compile(rf"^{'#' * n} +(.+)$", re.MULTILINE)
        marcas = list(patron.finditer(texto))
        if len(marcas) < (1 if nivel else 3):
            continue
        bloques = []
        preludio = texto[: marcas[0].start()].strip()
        if len(preludio) > MIN_CHARS:
            bloques.append(("Preliminares", preludio))
        for i, m in enumerate(marcas):
            fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
            bloques.append((m.group(1).strip(), texto[m.start() : fin].strip()))
        return bloques
    return []


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


def fusionar_cortas(secciones: list[tuple[str, str]], maximo: int, objetivo: int) -> list[tuple[str, str]]:
    """Une secciones consecutivas hasta llegar al tamaño objetivo.

    Sirve para dos cosas: descartar el ruido corto del principio (portadilla,
    índice) y agrupar capítulos breves en una sesión de estudio de tamaño
    razonable. El título resultante conserva el primero y el último.
    """
    salida: list[tuple[str, str]] = []
    for titulo, cuerpo in secciones:
        if salida and len(salida[-1][1]) < objetivo and len(salida[-1][1]) + len(cuerpo) <= maximo:
            t_ant, c_ant = salida[-1]
            base = t_ant.split(" — ")[0]
            salida[-1] = (base if titulo == base else f"{base} — {titulo}", f"{c_ant}\n\n{cuerpo}")
        else:
            salida.append((titulo, cuerpo))
    return salida


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
    """Junta las tesis centrales ya generadas, para encadenar capítulos."""
    tesis = []
    for previo in sorted((libro / "estudio").glob("*.md")):
        if previo.name.split("-")[0] >= numero:
            continue
        texto = previo.read_text(encoding="utf-8")
        m = re.search(r"##+ *2\..*?\n(.+?)(?=\n##)", texto, re.DOTALL)
        if m:
            tesis.append(f"- {previo.name.split('-')[0]}: {m.group(1).strip().splitlines()[0]}")
    if not tesis:
        return "(esta es la primera sección procesada)"
    return "Ya procesamos estas secciones y sus tesis centrales:\n" + "\n".join(tesis)


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

    libros, paginas = construir(LIBROS, SITIO, ESTATICOS, leer_config)
    if not libros:
        error("todavía no hay documentos de estudio. Generá al menos uno en libros/<slug>/estudio/")
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
        pendientes = sorted(
            p.name.split("-")[0] for p in secciones
            if not any(e.name.startswith(p.name.split("-")[0]) for e in estudios)
        )
        if pendientes:
            print(f"  pendientes de estudio: {', '.join(pendientes)}")


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

    p = sub.add_parser("dividir", help="libro.md → secciones/")
    p.add_argument("libro")
    p.add_argument("--nivel", type=int, choices=[1, 2, 3], help="nivel de encabezado para cortar")
    p.add_argument("--max-chars", type=int, default=MAX_CHARS, help="tope duro de una sección")
    p.add_argument("--objetivo", type=int, default=MIN_CHARS, help="tamaño al que agrupar capítulos cortos")
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
