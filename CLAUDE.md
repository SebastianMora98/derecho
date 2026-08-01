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
uv run scripts/ema.py dividir mi-libro         # --nivel 1|2|3 --objetivo N --max-chars N
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
`##` (para poder `dividir --nivel 2`) y conserva los folios reales del
original en marcas `<!-- p. N -->`. Esas marcas son lo que habilita
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
  franja fija de la página.

## Flujo cuando el usuario pide procesar un libro

1. `convertir` y `dividir`. Revisá `secciones/indice.md`: si el corte quedó mal
   (una sección de 200k caracteres, o 80 secciones de dos líneas), volvé a
   dividir con otro `--nivel` u `--objetivo` en vez de seguir con un corte malo.
   Para PDF sin encabezados, `limpieza.py` reconstruye los títulos de capítulo;
   si falla, mirá `libro.md` antes de dividir a ciegas.
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
  pasaje quedó ilegible, reportalo en la sección 9 en vez de reconstruirlo.
- Los diagramas Mermaid tienen que compilar: etiquetas entre comillas dobles,
  sin acentos ni paréntesis en los identificadores. Si dudás, verificá el
  render con `ema.py web` y el navegador antes de dar la sección por hecha.
- Una sección por corrida. Procesar el libro entero de un tirón produce
  resúmenes superficiales, que es justo lo que este taller evita.

## Estructura del documento de estudio

Las 12 secciones de `prompts/estudio.md`, en orden. Tres tienen efecto en el
sitio y no hay que cambiarles el formato:

- **2. Tesis central** — su primer párrafo es el resumen que aparece en el
  índice del libro.
- **10. Test de comprensión** — todo lo que va después de la línea
  `--- No mires esto hasta responder ---` se pliega en un `<details>`.
- **Flashcards** (variante `examen`) — una por línea, `Pregunta | Respuesta`;
  el sitio las convierte en tarjetas que se revelan al clic.

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
Beccaria (ed. UC3M 2015, CC BY-NC-ND). Dividido con
`--nivel 2 --objetivo 9000 --max-chars 16000` → 17 secciones. Procesadas la 1
y la 2; faltan de la 3 a la 17. `ema.py estado` da el detalle.

**fs-diferentes-concepciones-de-lo-juridico-1** — *Derecho y persona*, Carlos
Fernández Sessarego (5ª ed., Astrea, 2015). Es el capítulo "Diferentes
concepciones de lo jurídico", **escaneado**: se procesó con `ocr.py`, no con
`convertir`. Dividido con `--nivel 2` → 20 secciones (§ 53 a § 74).
`formato_citas = "paginas"` porque el escaneo conservó los folios; variante
`examen` activa. Procesada la 1; faltan de la 2 a la 20.

Dos detalles conocidos de este libro, ambos cosméticos: el título de § 70
quedó con el guión de corte adentro (`"sujeto de de- recho"`) y § 72 no se
detectó como encabezado porque el original no usa el guión separador después
del título — su texto está dentro de la sección 18, sin pérdida.

Ojo con este libro: es material **con derechos vigentes** (Astrea 2015), a
diferencia de Beccaria, que es CC. El `libro.md` y las `secciones/` quedan
fuera de git, como corresponde, y los documentos de estudio no deben
reconstruir el texto: citas cortas y con referencia, nada más.

### Pendientes de la plantilla

Detectados al ejecutar el prompt; conviene resolverlos antes de seguir en
serie:

- Las secciones 3 (mapa argumental en texto) y 4 (mapa visual) se solapan. Si
  el diagrama cumple, la 3 debería reducirse a las referencias al original.
- La sección 8 pide conectar con secciones anteriores aunque sea la primera
  corrida. Debería condicionarse a `{{CONTEXTO_PREVIO}}`.
- La sección 12 pide "en qué páginas detenerme" incluso cuando el texto no
  preservó paginación. Debería seguir a `{{FORMATO_CITAS}}`.
- La sección 11 (prueba Feynman) genera un espacio en blanco que en el sitio
  se ve como un hueco sin explicación. Convendría que el HTML muestre ahí un
  recuadro o una nota, o que la plantilla lo marque de otro modo.

Ya resueltos: `formato_citas` ahora admite `capitulos` y explica los cuatro
valores; la sección 2 aclara que lo que se escribe es la tesis misma, porque
su primer párrafo se publica como resumen en el índice (se colaba la frase de
instrucción en el resultado).

## Convenciones

- Todo en español neutro.
- No editar `libro.md`, `secciones/` ni `sitio/` a mano: se regeneran. Lo que
  se edita es `prompts/`, `libro.toml`, `estaticos/` y los documentos de
  `estudio/`.
- Fuera de git: `original/`, `libro.md`, `secciones/`, `prompts/` de cada libro.
  El repo publica los documentos de estudio, no los libros.
