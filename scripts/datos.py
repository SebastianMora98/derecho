#!/usr/bin/env python3
"""Extrae los documentos de estudio a JSON estructurado, sin HTML.

Existe para separar el contenido de su presentación. Antes, un solo archivo
(`sitio.py`) leía el markdown Y armaba el HTML en las mismas funciones, así que
el texto y las etiquetas quedaban soldados. Ahora `contenido.py` hace solo la
lectura: separa lo que se ve dentro de un capítulo de lo que se consolida por
libro (vocabulario, distinciones, autoevaluación, flashcards), sin saber que el
HTML existe. Este módulo (`datos.py`) toma esas estructuras y las afina un paso
más —separar el bloque 2 en párrafos, extraer el código Mermaid crudo, partir
las distinciones en sus tres campos— y las escribe en `libros/<slug>/libro.json`
y en `web/src/data/<slug>.json`. Cualquier front end (el sitio Astro actual, una
app, un export a Anki) puede consumir ese JSON sin tocar un regex de markdown.

Reutiliza la lectura de `contenido.py` en vez de duplicarla: `recolectar()` ya
separa lo visible de lo extraído por cada documento, y ese parseo es el que más
costó calibrar (avisos de vocabulario mal formado, deduplicado del glosario,
emparejado de preguntas y respuestas).
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from comun import bloques_h2, idea_principal, normalizar_titulo, primer_parrafo  # noqa: E402
import contenido  # noqa: E402


def parrafos_de(cuerpo: str) -> list[str]:
    """Los párrafos de prosa de un bloque, en orden, sin líneas vacías."""
    cuerpo = re.sub(r"<!--.*?-->", "", cuerpo, flags=re.DOTALL)
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", cuerpo) if p.strip()]


def mapa_de(cuerpo: str) -> str:
    """El código Mermaid crudo de un bloque `## 3. Mapa`, sin las cercas."""
    m = re.search(r"```mermaid\s*\n(.*?)```", cuerpo, re.DOTALL)
    return m.group(1).strip() if m else ""


def bloque_por_clave(visible: str, clave: str) -> str | None:
    for titulo, cuerpo in bloques_h2(visible):
        if clave in normalizar_titulo(titulo):
            return cuerpo
    return None


RE_DISTINCION_PAR = re.compile(r"^-\s+\*\*(.+?)\*\*\s*[—–-]+\s*(.+)$")
RE_DISTINCION_SUB = re.compile(
    r"^\s*-\s+(Se confunden porque|Criterio para decidir|D[oó]nde se cae):\s*(.+)$",
    re.IGNORECASE,
)


def parsear_distinciones(cuerpo: str) -> list[dict]:
    """Parte el bloque de distinciones en sus pares, cada uno con sus tres campos.

    Formato fijo (ver prompts/estudio.md): un ítem de primer nivel `- **A vs.
    B** — texto`, seguido de tres subítems `Se confunden porque / Criterio para
    decidir / Dónde se cae`. La lista va pegada, sin líneas en blanco, así que
    partir por línea alcanza.
    """
    items: list[dict] = []
    actual: dict | None = None
    for linea in cuerpo.splitlines():
        m = RE_DISTINCION_PAR.match(linea.strip())
        if m:
            if actual:
                items.append(actual)
            actual = {
                "par": m.group(1).strip(),
                "texto": m.group(2).strip(),
                "se_confunden": "",
                "criterio": "",
                "error": "",
            }
            continue
        m = RE_DISTINCION_SUB.match(linea)
        if m and actual:
            campo, valor = m.group(1).lower(), m.group(2).strip()
            if "confunden" in campo:
                actual["se_confunden"] = valor
            elif "criterio" in campo:
                actual["criterio"] = valor
            elif "cae" in campo:
                actual["error"] = valor
    if actual:
        items.append(actual)
    return items


def datos_de_seccion(s: dict) -> dict:
    """La forma estructurada de un capítulo, a partir de lo que ya parseó `contenido.py`."""
    if s.get("pendiente"):
        return {
            "numero": s["numero"],
            "ancla": s["ancla"],
            "titulo": s["titulo"],
            "pendiente": True,
        }

    visible = s["visible"]
    idea_cuerpo = bloque_por_clave(visible, "idea principal") or ""
    esencial_cuerpo = bloque_por_clave(visible, "esencial") or ""
    mapa_cuerpo = bloque_por_clave(visible, "mapa") or ""

    parrafos_idea = parrafos_de(idea_cuerpo)
    return {
        "numero": s["numero"],
        "ancla": s["ancla"],
        "titulo": s["titulo"],
        "pendiente": False,
        "idea": {
            "resumen": parrafos_idea[0] if parrafos_idea else s["tesis"],
            "contexto": parrafos_idea[1] if len(parrafos_idea) > 1 else "",
        },
        "esencial": parrafos_de(esencial_cuerpo),
        "mapa": mapa_de(mapa_cuerpo),
    }


def glosario_de(secciones: list[dict]) -> list[dict]:
    hechos = [s for s in secciones if not s.get("pendiente")]
    entradas = contenido.consolidar_vocabulario(hechos)
    return [
        {
            "termino": e["termino"],
            "definicion": e["definicion"],
            "caps": [c["numero"] for c in e["caps"]],
        }
        for e in entradas
    ]


def distinciones_de(secciones: list[dict]) -> list[dict]:
    salida = []
    for s in secciones:
        if s.get("pendiente"):
            continue
        bloque = s["extraido"]["distinciones"].strip()
        if not bloque:
            continue
        items = parsear_distinciones(bloque)
        if items:
            # `raw` es el markdown crudo del bloque, tal como lo escribió el
            # prompt. Los renderizadores lo usan tal cual para no arriesgar una
            # reconstrucción que no calce byte a byte con lo que el CSS espera
            # (la lista tiene que quedar pegada, sin párrafos intermedios). Los
            # `items` estructurados quedan para quien no vaya a renderizar
            # markdown — un export a Anki, una app nativa.
            salida.append(
                {"cap": s["numero"], "titulo_cap": s["titulo"], "items": items, "raw": bloque}
            )
    return salida


def autoevaluacion_de(secciones: list[dict]) -> list[dict]:
    salida = []
    for s in secciones:
        if s.get("pendiente"):
            continue
        e = s["extraido"]
        if not e["preguntas"].strip():
            continue
        preguntas = contenido.items_numerados(e["preguntas"])
        respuestas = contenido.items_numerados(e["respuestas"])
        if len(preguntas) != len(respuestas):
            print(
                f"aviso: {s['archivo']}: {len(preguntas)} preguntas y "
                f"{len(respuestas)} respuestas; no las empareja el JSON tampoco"
            )
            continue
        salida.append(
            {
                "cap": s["numero"],
                "titulo_cap": s["titulo"],
                "preguntas": [
                    {"pregunta": p, "respuesta": r} for p, r in zip(preguntas, respuestas)
                ],
            }
        )
    return salida


def mazo_de(secciones: list[dict]) -> list[dict]:
    from comun import sin_acentos

    vistas: set[str] = set()
    salida = []
    for s in secciones:
        if s.get("pendiente"):
            continue
        for pregunta, respuesta in s["extraido"]["flashcards"]:
            clave = " ".join(re.sub(r"[^\w ]", " ", sin_acentos(pregunta).lower()).split())
            if clave in vistas:
                continue
            vistas.add(clave)
            salida.append({"pregunta": pregunta, "respuesta": respuesta, "cap": s["numero"]})
    return salida


def datos_de_libro(libro: dict) -> dict:
    cfg = libro["cfg"]
    secciones = libro["secciones"]
    hechos = [s for s in secciones if not s.get("pendiente")]
    return {
        "slug": libro["slug"],
        "titulo": cfg.get("titulo", libro["slug"]),
        "autor": cfg.get("autor", ""),
        "anio": cfg.get("anio"),
        "edicion": cfg.get("edicion", ""),
        "nivel": cfg.get("nivel", ""),
        "formato_citas": cfg.get("formato_citas", ""),
        "contenedor": cfg.get("contenedor", ""),
        # Resumen general del texto entero, escrito a mano en `libro.toml`. Se
        # guarda partido en párrafos, igual que el bloque 2 de un capítulo: el
        # JSON no lleva HTML, y el sitio decide cómo mostrarlo.
        "resumen": parrafos_de(cfg.get("resumen", "")),
        # La entrada destacada que va arriba del resumen: lo que hay que saber
        # del texto para una prueba, no una descripción del libro.
        "resumen_corto": parrafos_de(cfg.get("resumen_corto", "")),
        # Enlace a la fuente cuando está en línea (un video, una charla). Los
        # libros no lo llevan: su fuente es el PDF, que no se publica.
        "fuente_url": cfg.get("fuente_url", ""),
        # Título de la sección bajo la que se agrupa esta entrada en el índice
        # de libros. Varias entradas con el mismo `grupo` salen juntas; sin
        # `grupo` la entrada va suelta.
        "grupo": cfg.get("grupo", ""),
        "partes": cfg.get("partes", []),
        "capitulos": [datos_de_seccion(s) for s in secciones],
        "glosario": glosario_de(secciones),
        "distinciones": distinciones_de(secciones),
        "autoevaluacion": autoevaluacion_de(secciones),
        "mazo": mazo_de(secciones),
        "estadisticas": {
            "capitulos_totales": len(secciones),
            "capitulos_con_documento": len(hechos),
        },
    }


def slug_de_grupo(nombre: str) -> str:
    """`Clase A` → `clase-a`. Es la ruta de la hoja de su reseña."""
    limpio = re.sub(r"[^\w\s-]", "", nombre, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s_]+", "-", limpio)


def grupos_de(libros_dir: Path) -> list[dict]:
    """Las secciones del índice declaradas en `libros/grupos.toml`.

    El markdown de la reseña se guarda crudo: igual que el resto del JSON, acá
    no se arma HTML — eso lo hace el sitio con `md.ts`.
    """
    ruta = libros_dir / "grupos.toml"
    if not ruta.exists():
        return []
    with ruta.open("rb") as fh:
        declarados = tomllib.load(fh).get("grupos", [])
    grupos = []
    for g in declarados:
        nombre = str(g.get("nombre", "")).strip()
        if not nombre:
            continue
        resena = ""
        archivo = str(g.get("resena", "")).strip()
        if archivo:
            md = libros_dir / "resenas" / archivo
            if md.exists():
                resena = md.read_text(encoding="utf-8").strip()
            else:
                print(f"aviso: el grupo {nombre} apunta a la reseña {archivo}, que no existe")
        grupos.append(
            {
                "nombre": nombre,
                "slug": slug_de_grupo(nombre),
                "orden": g.get("orden"),
                "resena": resena,
                # El documento de una sección no siempre es una reseña: puede
                # ser el taller resuelto, por ejemplo. Estas tres claves dejan
                # renombrar el título de la hoja, su bajada y el enlace del
                # índice; sin ellas se usan los textos por defecto de reseña.
                "resena_titulo": g.get("resena_titulo", ""),
                "resena_bajada": g.get("resena_bajada", ""),
                "resena_enlace": g.get("resena_enlace", ""),
            }
        )
    return grupos


def construir_datos(libros_dir: Path, leer_config, destino: Path | None = None) -> list[dict]:
    """Genera el JSON de cada libro y opcionalmente lo escribe en disco.

    `destino`, si se pasa, es un directorio donde se escribe `<slug>.json` por
    libro más un `indice.json` con la lista de libros y sus metadatos. Si no se
    pasa, cada libro además escribe su propio `libros/<slug>/libro.json`, al
    lado de `estudio/`, para que quede versionado junto con el contenido que
    describe.
    """
    libros = contenido.recolectar(libros_dir, leer_config)
    salida = []
    for libro in libros:
        datos = datos_de_libro(libro)
        salida.append(datos)
        (libros_dir / libro["slug"] / "libro.json").write_text(
            json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if destino is not None:
        destino.mkdir(parents=True, exist_ok=True)
        for datos in salida:
            (destino / f"{datos['slug']}.json").write_text(
                json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        indice = [
            {
                "slug": d["slug"],
                "titulo": d["titulo"],
                "autor": d["autor"],
                "grupo": d["grupo"],
                "capitulos_totales": d["estadisticas"]["capitulos_totales"],
                "capitulos_con_documento": d["estadisticas"]["capitulos_con_documento"],
            }
            for d in salida
        ]
        (destino / "indice.json").write_text(
            json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        grupos = grupos_de(libros_dir)
        usados = {d["grupo"] for d in salida if d["grupo"]}
        declarados = {g["nombre"] for g in grupos}
        for falta in sorted(usados - declarados):
            print(f"aviso: el grupo {falta!r} lo usa algún libro pero no está en grupos.toml")
        for sobra in sorted(declarados - usados):
            print(f"aviso: el grupo {sobra!r} está declarado en grupos.toml pero no lo usa ningún libro")
        (destino / "grupos.json").write_text(
            json.dumps(grupos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return salida


if __name__ == "__main__":
    raiz = Path(__file__).parent.parent
    sys.path.insert(0, str(raiz / "scripts"))
    from ema import leer_config  # noqa: E402

    libros_dir = raiz / "libros"
    destino = raiz / "web" / "src" / "data" if (raiz / "web").exists() else None
    libros = construir_datos(libros_dir, leer_config, destino)
    for d in libros:
        e = d["estadisticas"]
        print(
            f"✓ {d['slug']}: {e['capitulos_con_documento']}/{e['capitulos_totales']} capítulos, "
            f"{len(d['glosario'])} glosario, {len(d['mazo'])} flashcards, "
            f"{sum(len(a['preguntas']) for a in d['autoevaluacion'])} preguntas"
        )
