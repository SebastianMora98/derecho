# derecho — taller de documentos de estudio

Convierte libros a Markdown con [MarkItDown](https://github.com/microsoft/markitdown),
los parte en secciones del tamaño de una sesión de estudio, los pasa por una
plantilla de prompt editable y publica el resultado como sitio estático.

Los documentos generados **acompañan** la lectura del original: mapa del
argumento, diagramas, conceptos, preguntas socráticas, autoevaluación. El
documento es andamio; el libro es el edificio.

## Instalación

```bash
uv sync
```

## Flujo completo

```bash
# 1. dejar el archivo en entrada/ y convertirlo
uv run scripts/ema.py convertir

# 2. partirlo en secciones (revisar secciones/indice.md antes de seguir)
uv run scripts/ema.py dividir mi-libro --objetivo 9000 --max-chars 16000

# 3. completar libros/mi-libro/libro.toml (autor, nivel, propósito)

# 4. generar el prompt de una sección
uv run scripts/ema.py preparar mi-libro 3

# 5. ejecutar ese prompt en Claude y guardar la salida en
#    libros/mi-libro/estudio/03-<mismo-slug>.md

# 6. regenerar el sitio
uv run scripts/ema.py web
python3 -m http.server -d sitio 8000
```

`uv run scripts/ema.py estado` muestra qué secciones faltan.

## Qué se edita para mejorar los resultados

`prompts/estudio.md`. Está pensado para afinarse corrida a corrida: cambiás una
sección, volvés a `preparar`, comparás. `prompts/variantes.md` guarda bloques
opcionales (examen, investigación, texto técnico, texto narrativo) que se
activan desde `libro.toml`.

| Marcador | Sale de |
|---|---|
| `{{OBRA}}` | `titulo`, `autor`, `edicion` de `libro.toml` |
| `{{SECCION}}` | número y título de la sección |
| `{{NIVEL}}` `{{PROPOSITO}}` `{{TIEMPO}}` `{{FORMATO_CITAS}}` | `libro.toml` |
| `{{CONTEXTO_PREVIO}}` | tesis centrales de las secciones ya estudiadas |
| `{{VARIANTES}}` | bloques activados de `prompts/variantes.md` |
| `{{TEXTO}}` | el fragmento del libro |

## Conversión de PDF

`scripts/limpieza.py` repara lo que la extracción de un PDF rompe: cabeceras
corridas repetidas en cada página, números de página sueltos, palabras
partidas con guion, párrafos cortados renglón por renglón. Cuando el PDF no
trae encabezados, reconstruye los títulos de capítulo como Markdown para que
`dividir` tenga por dónde cortar. Con `--crudo` se desactiva.

## El sitio

`ema.py web` genera `sitio/`: una página por libro y una por sección, con los
diagramas Mermaid renderizados, el test de comprensión con las respuestas
plegadas y las flashcards revelables al clic. Es HTML plano, sin build.

Para desplegar en Vercel: importar el repositorio y dejar la configuración por
defecto — `vercel.json` ya indica que no hay build y que la salida es `sitio/`.

## Qué hay en el repositorio

Los documentos de estudio, las plantillas y el sitio generado. **No** los
libros: `libros/*/original/`, `libro.md`, `secciones/` y los prompts rellenados
quedan fuera de git y se regeneran con `ema.py convertir`.
