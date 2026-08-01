# Taller de documentos de estudio

Convierte libros y documentos a Markdown, los parte en secciones manejables y
los procesa con una plantilla de prompt editable para producir documentos de
estudio que **acompañan** la lectura del original, no la reemplazan. El
resultado se publica como sitio estático en Vercel.

## Estructura

```
entrada/              documentos crudos que todavía no se procesaron
prompts/              plantillas editables (esto es lo que se afina)
  estudio.md          plantilla base con marcadores {{...}}
  variantes.md        bloques opcionales según el propósito
  artefacto.md        instrucciones para un artefacto HTML suelto
scripts/
  ema.py              CLI: convertir · dividir · preparar · web · estado
  comun.py            slugify e idea_principal, compartidos por ema y sitio
  limpieza.py         reparación del texto extraído de PDF
  ocr.py              OCR para PDF escaneados (sin capa de texto)
  ocr_vision.swift    helper de OCR con el framework Vision de macOS
  sitio.py            generador del sitio estático
estaticos/            estilo.css y tarjetas.js que copia el sitio
sitio/                HTML generado — se commitea, es lo que Vercel publica
libros/<slug>/
  libro.toml          ficha editable: autor, nivel, propósito, variantes
  libro.md            conversión completa a Markdown (fuera de git)
  original/           copia del archivo fuente (fuera de git)
  secciones/          NN-titulo.md + indice.md (fuera de git)
  prompts/            prompts ya rellenados (fuera de git)
  estudio/            NN-titulo.md — los documentos de estudio, en git
  artefactos/         páginas HTML sueltas
```

## Comandos

```bash
uv sync                                        # instalar dependencias
uv run scripts/ema.py convertir                # todo lo que haya en entrada/
uv run scripts/ema.py convertir ruta/al.pdf --slug mi-libro
uv run scripts/ema.py dividir mi-libro         # --nivel 1|2|3 --corto N --tope-fusion N
uv run scripts/ema.py preparar mi-libro 3      # '3', '1-4', '2,5' o 'todas'
uv run scripts/ema.py web                      # estudio/*.md → sitio/
uv run scripts/ema.py estado
```

## PDF escaneados

Si `convertir` deja un `libro.md` de unos pocos caracteres, el PDF es un
escaneo sin capa de texto y `markitdown` no tiene nada que extraer. Ahí va
`ocr.py`, que no necesita instalar nada: rasteriza con `pdftoppm` y reconoce
con el framework Vision de macOS.

```bash
uv run scripts/ocr.py entrada/libro.pdf -o libros/<slug>/libro.md
```

Reconstruye los párrafos por la sangría de cada renglón, rearma las palabras
cortadas con guión, convierte los `§ NN. TÍTULO` del original en encabezados
`##` y los apartados (`A) VISIONES...`) en `#`, y conserva los folios reales
del original en marcas `<!-- p. N -->`. Esas marcas son lo que habilita
`formato_citas = "paginas"`: un escaneo bien procesado preserva la paginación
que la conversión de un PDF con texto suele perder.

Detalles que ya costaron una vuelta, por si hay que tocarlo:

- Las fotocopias de libro vienen a doble página por hoja (hoja apaisada). Se
  detecta por la proporción y se parte al medio antes del OCR; sin eso el OCR
  entremezcla el texto de dos páginas distintas.
- El margen de sangría se mide con la **mediana**, no con el mínimo: un solo
  renglón torcido corre el margen y parte párrafos por la mitad.
- Vision parte a veces un renglón físico en dos cajas, así que hay que
  agrupar por altura antes de leer de izquierda a derecha.
- El encabezado se detecta por el blanco que lo separa del cuerpo, no por una
  franja fija, y puede ocupar **dos filas**: en un escaneo torcido el folio y
  el título corriente caen a alturas distintas aunque en el papel estén en el
  mismo renglón. Sin eso el folio se pierde y el título corriente queda pegado
  al primer párrafo de la página. `quitar_titulo_corriente` es la red de
  seguridad para las páginas donde la geometría igual falle.

## Flujo cuando el usuario pide procesar un libro

1. `convertir` y `dividir`. **Un documento de estudio = un capítulo del autor**:
   eso es lo que se puede citar y lo que el usuario espera ver. Solo se agrupan
   los capítulos de menos de `--corto` (2.000 car.) con su vecino. Revisá
   `secciones/indice.md`: si aparecen secciones que no son capítulos
   (portadilla, índice, catálogo de la editorial), agregá su patrón a `omitir`
   en `libro.toml` en vez de dejarlas — no se pueden filtrar por tamaño ni por
   la forma del título. Para PDF sin encabezados, `limpieza.py` reconstruye los
   títulos; si falla, mirá `libro.md` antes de dividir a ciegas.
2. Completá `libro.toml` (autor, nivel, propósito, variantes) preguntando al
   usuario lo que no puedas deducir del texto.
3. `preparar` la sección. Se genera `libros/<slug>/prompts/NN-estudio.md`.
4. **Ejecutá ese prompt vos mismo**: leélo completo y producí la respuesta
   siguiendo sus instrucciones al pie de la letra. Guardá el resultado en
   `libros/<slug>/estudio/NN-<mismo-slug>.md`. Nada más — sin preámbulo ni
   comentarios propios dentro del archivo.
5. Corré `ema.py web` y commiteá `sitio/` junto con el documento nuevo.
6. Al terminar cada sección, mencioná al usuario qué quedó flojo del prompt
   (secciones que salieron pobres, instrucciones ambiguas). Afinar
   `prompts/estudio.md` es parte del trabajo, no un extra.

## Reglas al generar documentos de estudio

- Las reglas de honestidad del prompt mandan sobre cualquier impulso de
  completar: si el fragmento no dice algo, se escribe "no aparece en esta
  sección".
- Citas del original: menos de 15 palabras, entre comillas, con referencia.
  Nunca inventar números de página que la conversión no preservó.
- El texto convertido puede traer ruido pese a la limpieza. Ignoralo; si un
  pasaje quedó ilegible, marcalo en el paso del bloque 2 donde cae y anotalo en
  el bloque 6, en vez de reconstruirlo.
- Los diagramas Mermaid tienen que compilar: etiquetas entre comillas dobles y
  sin paréntesis. Las etiquetas **sí llevan acentos**; lo que va sin acentos son
  los identificadores. Verificá el render con `ema.py web` y el navegador antes
  de dar la sección por hecha: un error deja un recuadro vacío, sin mensaje.
- Una sección por corrida. Procesar el libro entero de un tirón produce
  resúmenes superficiales, que es justo lo que este taller evita.

## Estructura del documento de estudio

Los 7 bloques de `prompts/estudio.md`, en orden: **1** Idea principal · **2**
Explicación paso a paso · **3** Mapa (un solo diagrama) · **4** Vocabulario
clave · **5** Distinciones que se confunden · **6** Qué releer del original ·
**7** Autoevaluación · **Flashcards**.

Está pensada para preparar un examen siendo principiante, y su regla central es
el **reparto del material**: cada tipo de contenido tiene un bloque asignado y
está prohibido en los otros. La plantilla vieja de 12 bloques hacía aparecer los
mismos 7 conceptos cuatro veces (tarjeta, nodo del diagrama, pregunta del test y
flashcard); si al ejecutar el prompt notás que estás repitiendo, es que el
reparto se está violando.

Cuatro contratos con el código que no hay que romper:

- **1. Idea principal** — su primer párrafo, en una sola línea y sin notas al
  redactor, es el resumen que se publica en el índice del libro y el contexto
  que hereda la corrida siguiente. Se busca por el título del bloque, no por su
  número (`comun.py: idea_principal`), así que renumerar no rompe el sitio, pero
  renombrar el bloque sí.
- **7. Autoevaluación** — todo lo que sigue a `--- No mires esto hasta responder
  ---` se pliega en un `<details>`. Tiene que ser lo último antes de las
  flashcards: lo que venga después del siguiente `##` se reinyecta en el cuerpo.
- **Flashcards** — al final del archivo, una por línea, `Pregunta | Respuesta`,
  sin markdown adentro (el sitio escapa el texto). Ya no dependen de la variante
  `examen`; esa variante solo fija la cantidad en 20.
- **4. Vocabulario clave** — la lista va **pegada**, sin líneas en blanco entre
  ítems, o se pierde el color de acento del término (`estilo.css`: el selector
  es `li > strong`, y con líneas en blanco el markdown mete un `<p>` en medio).

El sitio genera además un índice de bloques al principio de cada documento, con
un `id` por cada `##`. Eso sale de `sitio.py: anclar`, no del markdown: el
documento no puede escribir HTML crudo ni anclas propias. Tampoco casillas
`- [ ]`, notas al pie, callouts ni atributos `{.clase}`: no hay plugins de
markdown instalados y se ven como caracteres sueltos.

## Sitio y despliegue

`ema.py web` regenera `sitio/` completo desde `libros/*/estudio/*.md`. Es HTML
plano: sin build, sin framework, Mermaid por CDN. `vercel.json` apunta a
`sitio/` sin comando de build, así que Vercel solo sirve los archivos.

El sitio se commitea. Si cambia un documento de estudio y no se corre `web`,
lo publicado queda desactualizado.

Está publicado en https://derecho-five.vercel.app (proyecto `derecho` del team
`sebastianmora98s-projects`, importado desde GitHub: cada push a `main`
redespliega).

**No volver a activar `cleanUrls` en `vercel.json`.** `sitio.py` genera enlaces
relativos que calcan la estructura en disco (`02.html`, `../estilo.css`), y eso
funciona igual servido y abierto como archivo local. Con `cleanUrls` el índice
del libro se sirve en `/<slug>` sin barra final, así que `02.html` resuelve a
`/02` y da 404. `trailingSlash: true` tampoco sirve: haría que `/<slug>/02`
redirija a `/<slug>/02/` y rompería la navegación anterior/siguiente dentro de
las secciones.

El repositorio es `SebastianMora98/derecho` y el remoto va **por SSH**: el
`gh` CLI de esta máquina está autenticado con otra cuenta
(`jmoraautomatiza`), que no tiene permiso de escritura. Con HTTPS el push
falla con 403; la clave SSH sí es la de `SebastianMora98`.

Hay un servidor MCP de Vercel configurado (`https://mcp.vercel.com`, scope
local). Sirve para consultar proyectos, despliegues y logs sin salir de la
conversación — usalo para verificar que un build salió bien en vez de pedirle
al usuario que mire el panel. Si sus herramientas no aparecen, es que se
agregó después de arrancar la sesión: hay que reiniciar.

## Estado del trabajo

**beccaria-delitos-y-penas** — *Tratado de los delitos y de las penas*, Cesare
Beccaria (ed. UC3M 2015, CC BY-NC-ND). Jerarquía plana: 47 capítulos numerados
por el autor, sin apartados. Dividido con `--nivel 2` → **39 secciones**
(«Al lector», «Introducción» y los 47 capítulos, con 9 secciones que juntan
capítulos cortos). Procesada la 1. `formato_citas = "capitulos"`: el autor
numera sus capítulos y esta edición no preservó la paginación.

**fs-diferentes-concepciones-de-lo-juridico-1** — *Derecho y persona*, Carlos
Fernández Sessarego (5ª ed., Astrea, 2015). Es el capítulo "Diferentes
concepciones de lo jurídico", **escaneado**: se procesó con `ocr.py`, no con
`convertir`. Tiene tres pisos —capítulo > apartado A/B/C > parágrafo §— y los
apartados están declarados en `[[partes]]` de su `libro.toml`, que es de donde
el índice del sitio saca la agrupación. Dividido con `--nivel 2` → **18
secciones** (§ 53 a § 74, con 3 que juntan parágrafos cortos). Procesada la 1.
`formato_citas = "paginas"` porque el escaneo conservó los folios; variante
`examen` activa.

`ema.py estado` da el detalle y avisa si quedó algún documento de `estudio/`
cuya sección ya no existe.

Un detalle conocido de este libro, cosmético: § 72 no se detecta como
encabezado porque el original no usa el guión separador después del título; su
texto está dentro de la sección 15, sin pérdida.

Ojo con este libro: es material **con derechos vigentes** (Astrea 2015), a
diferencia de Beccaria, que es CC. El `libro.md` y las `secciones/` quedan
fuera de git, como corresponde, y los documentos de estudio no deben
reconstruir el texto: citas cortas y con referencia, nada más.

### Historia de la plantilla

La plantilla arrancó con 12 bloques pensados para acompañar una lectura
profunda. Al revisar los tres primeros documentos generados quedó claro que no
servía para preparar un examen: los mismos 7 conceptos aparecían cuatro veces
(tarjeta de concepto, nodo del diagrama, pregunta del test y flashcard), la
prueba Feynman salía idéntica byte a byte en dos documentos distintos porque el
modelo solo copiaba la plantilla, y bloques como «Ubicación» eran ceremoniales.

Se rehízo a los 7 bloques actuales, con foco en examen y nivel principiante. Los
cuatro pendientes que estaban anotados quedaron resueltos por el rediseño: el
mapa en texto y el visual se unificaron en un solo diagrama; las conexiones se
condicionaron a `{{CONTEXTO_PREVIO}}`; «qué releer» sigue a `{{FORMATO_CITAS}}`
y ya no pide páginas cuando no hay paginación; y la prueba Feynman se eliminó.
De paso se corrigió `variantes.md` y `artefacto.md`, que tenían todas sus
referencias a números de bloque corridas en uno desde que alguien insertó un
bloque sin renumerar.

Los tres documentos con la estructura vieja se regeneraron. `comun.py:
idea_principal` igual busca el bloque por título y no por número, así que un
documento viejo seguiría apareciendo bien en el índice.

## Convenciones

- Todo en español neutro.
- No editar `libro.md`, `secciones/` ni `sitio/` a mano: se regeneran. Lo que
  se edita es `prompts/`, `libro.toml`, `estaticos/` y los documentos de
  `estudio/`.
- Fuera de git: `original/`, `libro.md`, `secciones/`, `prompts/` de cada libro.
  El repo publica los documentos de estudio, no los libros.
