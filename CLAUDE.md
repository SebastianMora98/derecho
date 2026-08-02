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
  comun.py            slugify e idea_principal, compartidos por ema y contenido
  limpieza.py         reparación del texto extraído de PDF
  ocr.py              OCR para PDF escaneados (sin capa de texto)
  ocr_vision.swift    helper de OCR con el framework Vision de macOS
  contenido.py        lee estudio/*.md y separa capítulo de consolidados — sin HTML
  datos.py            arma el JSON estructurado a partir de contenido.py
estaticos/            estilo.css y tarjetas.js — los copia el build de Astro
web/                  sitio Astro: lee el JSON, arma el HTML (`npm run build`)
  src/data/           <slug>.json por libro — lo escribe `datos.py`, en git
  src/pages/          index.astro (lista de libros) y [slug]/index.astro (la hoja)
  src/components/     Capitulo, Consolidados, IndiceLibro
  src/lib/            md.ts (markdown-it, único renderizador) y consolidados.ts
sitio/                HTML que arma Astro — fuera de git, lo reconstruye Vercel
libros/<slug>/
  libro.toml          ficha editable: autor, nivel, propósito, variantes, resumen
  libro.md            conversión completa a Markdown (fuera de git)
  libro.json          el mismo JSON de web/src/data/, al lado del contenido que describe — en git
  original/           copia del archivo fuente (fuera de git)
  secciones/          NN-titulo.md + indice.md (fuera de git)
  prompts/            prompts ya rellenados (fuera de git)
  capitulos.toml      lista de capítulos que escribe `dividir` — en git, la
                      usa el JSON para mostrar también los pendientes
  estudio/            NN-titulo.md — los documentos de estudio, en git
  artefactos/         páginas HTML sueltas
```

### De HTML directo a JSON + Astro

Hasta acá `scripts/sitio.py` leía `estudio/*.md` y armaba el HTML en las mismas
funciones: el texto y las etiquetas quedaban soldados, y tocar el render de un
bloque significaba tocar también su parseo. Se partió en tres capas:

1. **`contenido.py`** (antes `sitio.py`) lee `estudio/*.md` y separa lo que se ve
   dentro de un capítulo de lo que se consolida por libro. No sabe que existe un
   HTML.
2. **`datos.py`** toma esas estructuras, las afina (separa el bloque 2 en
   párrafos, extrae el código Mermaid crudo, parte las distinciones en sus tres
   campos) y escribe `libros/<slug>/libro.json` + `web/src/data/<slug>.json`.
   **Los dos JSON son el mismo archivo por partida doble**: uno vive junto al
   contenido que describe, el otro es lo que Astro importa en build time.
3. **`web/`** (Astro, sin componentes de UI: HTML + CSS + `tarjetas.js`, igual
   que antes) lee esos JSON y arma el HTML. `estilo.css` y `tarjetas.js` se
   copiaron sin tocar a `web/public/`; el único renderizador de markdown que
   queda es `web/src/lib/md.ts` (markdown-it, la versión JS de la misma
   librería que usaba Python).

`ema.py web` sigue siendo el único comando: corre `datos.py` y después
`npm run build` dentro de `web/`. La primera vez instala `node_modules`.
**Vercel no necesita Python**: su build es `npm install --prefix web && npm run
build --prefix web`, y lee directo los JSON ya commiteados — por eso `sitio/`
dejó de commitearse (lo reconstruye cada deploy) y `web/src/data/*.json` pasó a
ser lo que antes era `sitio/`: el artefacto versionado que Vercel consume.

**Un bug real salió a la luz al mover el render de las distinciones.** El bloque
6 separa cada par con una línea en blanco para que sea legible al escribirlo,
pero eso hace que CommonMark trate la lista como "loose" y envuelva cada ítem en
un `<p>` (`<li><p><strong>…`). El CSS pinta el acento del par con el selector
`li > strong`, así que con esa envoltura el color nunca se aplicaba —**en el
sitio que estuvo en producción hasta este cambio, no solo en la versión
nueva**. La corrección no fue tocar los 58 documentos: `datos.py` ya parsea cada
distinción en sus campos (`par`, `texto`, `se_confunden`, `criterio`, `error`),
así que el renderizador arma el `<ul><li>` a mano desde esos campos en vez de
pasarle el markdown crudo a `md.render()`. No depende de si el original tiene
líneas en blanco o no.

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
- Esa detección mide la página **1**, y `pdfinfo` sin `-f`/`-l` solo informa el
  tamaño de esa página. Si el libro tiene una portada escaneada como el pliego
  entero (apaisada) pero el cuerpo es retrato normal —pasó con *La inteligencia
  fracasada*, 852x611 vs. 460x599 en las páginas interiores—, la sola página 1
  hace pensar que el libro entero es doble-página-por-hoja y partiría cada
  página del cuerpo al medio, mezclando su texto igual que el problema que la
  regla anterior evita. Por eso `a_markdown` confirma con una página interior
  (la del medio del libro) antes de aplicar el corte a todo, y `rasterizar` con
  `mitades=1` ya no fuerza un recorte `-W/-H` medido de una sola página: cada
  página se rasteriza a su tamaño nativo, para no toparse con la misma mezcla
  de tamaños de otra forma.
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
  pasaje quedó ilegible, marcalo en media cláusula dentro del bloque 2, con la
  referencia para leerlo en el original, en vez de reconstruirlo.
- Los diagramas Mermaid tienen que compilar: etiquetas entre comillas dobles y
  sin paréntesis. Las etiquetas **sí llevan acentos**; lo que va sin acentos son
  los identificadores. Verificá el render con `ema.py web` y el navegador antes
  de dar la sección por hecha: un error deja un recuadro vacío, sin mensaje.
- Una sección por corrida. Procesar el libro entero de un tirón produce
  resúmenes superficiales, que es justo lo que este taller evita.

## Estructura del documento de estudio

Los 6 bloques de `prompts/estudio.md`, **y donde se publica cada uno**:

| bloque | dónde se ve |
|---|---|
| 1 Idea principal | dentro del capítulo |
| 2 Lo esencial del capítulo | dentro del capítulo |
| 3 Mapa (un solo diagrama) | dentro del capítulo |
| 4 Vocabulario clave | glosario del libro |
| 5 Distinciones que se confunden | sección del libro |
| 6 Autoevaluación | test del libro |
| Flashcards | mazo del libro |

Los cuatro últimos **no se muestran dentro del capítulo**: el sitio los extrae y
los publica una sola vez por libro, al final de la hoja. Repetir ese aparato en
cada capítulo era lo que hacía los documentos largos y redundantes.

**Se eliminó el bloque «Qué releer del original»**, que era el 4 y se veía dentro
del capítulo. Repetía lo que el bloque 2 ya señalaba: el 2 tiene prohibido
reproducir los ejemplos y enumeraciones del autor y debe mandar al original donde
caen, así que juntarlos otra vez en una lista al final era decir dos veces lo
mismo con distinto formato. Ahora el bloque 2 es **el único lugar que manda al
original**, en media cláusula y con la referencia. La renumeración —5→4, 6→5,
7→6— no rompió nada porque la extracción y el índice buscan **por título**, no por
número, y los `id` de las anclas se derivan del título sin el número.

Tres topes, y el que manda es el segundo: 1.100 palabras el documento entero,
**500 los bloques 1 a 3 juntos** —lo único que se lee al abrir un capítulo, y el 3
es un diagrama— y 400 el bloque 2. Se miden **excluyendo el código Mermaid y los
encabezados**.

**El tope del bloque 2 no se cumple contándolo al final, y está medido:** en la
tanda de los 39 de Beccaria se violó las 39 veces, siempre entre 460 y 500, y hubo
que recortar documento por documento en una segunda pasada. Escribir 500 palabras
de prosa continua sale solo. Por eso el prompt ahora da además un **presupuesto
por párrafo**, que sí se controla mientras se escribe: **2 párrafos de unas 130
palabras, y 3 como máximo** cuando la sección es larga o junta dos capítulos del
autor. Nunca 4. Es un promedio, no un máximo por párrafo.

Ojo con la calibración de esa clase de regla: la primera versión que escribí pedía
«3 párrafos de 5 o 6 oraciones» y solo la cumplían 3 de 58 documentos. Un
presupuesto en oraciones no describe estos textos; en párrafos y palabras, sí.
Medir contra los documentos aprobados **antes** de dejar la regla en el prompt.

**El bloque 2 no lleva pasos numerados.** La versión con pasos forzaba la
cobertura, pero partía la lectura en fichas y obligaba a un andamiaje meta ("el
movimiento es", "importa porque") que se comía un tercio del espacio. La cobertura
se pide ahora directo: el primer párrafo arranca donde arranca el capítulo, el
último llega a su cierre, y cada párrafo lleva una referencia.

Su regla central sigue siendo el **reparto del material**: cada tipo de contenido
tiene un bloque asignado y está prohibido en los otros. Lo más importante del
reparto: **el test dejó de cubrir recall**, que pasó a ser trabajo exclusivo de las
flashcards. Antes eran el mismo material en dos formatos y el 32% del mazo repetía
una pregunta del test.

### El test y el mazo se calibraron contra el examen real

El usuario mostró el examen que prepara: **seis preguntas amplias y de
exposición** —«¿cómo define usted el Derecho?», «¿qué entender por el formalismo
jurídico y cuáles son sus implicaciones?», «ubique el Derecho Civil», «identifique
dos derechos subjetivos y explique hasta dónde puede ejercerlos»—. Cruzan varios
capítulos y piden desarrollar, no reconocer.

Contra eso, 4 preguntas y 8 flashcards por capítulo daban **155 preguntas y 312
tarjetas** en Beccaria: material que se genera fácil y no se repasa nunca. Ahora
son **2 preguntas y hasta 4 flashcards por capítulo**, con el foco cambiado:

- De las 2 preguntas, **una es de exposición** y se formula con el verbo del
  examen («¿qué se entiende por…?», «explique… y sus implicaciones», «ubique…»);
  la otra es de aplicación o crítica. Su respuesta de referencia es el molde de la
  respuesta del examen —3 a 5 oraciones que abren con la definición o la tesis—,
  no una pista.
- **Las flashcards son entre 1 y 4, nunca una cifra fija.** La primera versión
  de esta regla decía «exactamente 4», y fue el mismo error que ya se había
  corregido una vez con «exactamente 8»: una cantidad obligatoria fuerza a
  completar con relleno cuando el capítulo no da para tanto. El criterio real es
  doble, y los dos tienen que dar que sí: *¿la necesitaría para escribir el
  párrafo de una respuesta?* y **¿esto se le preguntaría a un estudiante de
  primer semestre en un examen?** Un matiz correcto pero de especialista, un
  nombre propio secundario o una precisión histórica no pasa el segundo filtro
  aunque pase el primero, y sale.
- El prompt pide usar `{{CONTEXTO_PREVIO}}` para que la pregunta de exposición
  obligue a traer capítulos anteriores, porque las preguntas reales cruzan
  capítulos y ninguna pregunta por capítulo las imita sola.

**La variante `examen` dejó de subir las cantidades.** Subía a 5 y 12, que es la
dirección contraria; ahora mantiene 2 y hasta 4 y lo que hace es apretar el foco
(las dos preguntas de exposición, respuestas de 5 a 7 oraciones).

### Los 58 documentos ya están alineados a esta regla

Se hizo en dos tandas. La primera (8 corridas en paralelo) recortó el bloque 2
a 2-3 párrafos, bajó el test a 2 preguntas y el mazo a 4 flashcards fijas por
capítulo — y esa cifra fija resultó ser el mismo error que el «8» original.
La segunda tanda (6 corridas en paralelo, una revisión y no una reescritura)
releyó cada capítulo entero y aplicó el filtro real a sus 4 flashcards:
cuántas pasan las dos pruebas —hace falta para exponer, y se lo preguntarían a
un estudiante de primer semestre—, sin tocar ningún otro bloque. El resultado
varía capítulo por capítulo, de 1 a 4 tarjetas; **Beccaria cierra en 136
flashcards (antes 156) y FS en 60 (antes 76)**, con las preguntas del test sin
tocar: 78 y 38. El build no emite ningún aviso —ni término de glosario
duplicado, ni par pregunta/respuesta descalzado, ni bloque faltante— en los 58.

Contratos con el código que no hay que romper:

- **Los cuatro títulos son claves de extracción.** Un `##` cuyo título contenga
  «vocabulario», «distinciones», «autoevaluacion» o «flashcards» sale del capítulo
  y va al consolidado (`contenido.py: destino_del_bloque`). Es lista blanca de
  extracción, no de visibilidad: lo que no clasifica queda visible, así que
  renombrar un bloque lo hace reaparecer feo en el capítulo en vez de
  desaparecer callado.
- **1. Idea principal** — su primer párrafo, en una sola línea y sin notas al
  redactor, es el resumen que se publica en el índice del libro y el contexto que
  hereda la corrida siguiente. Se busca por el título del bloque, no por su número
  (`comun.py: idea_principal`), así que renumerar no rompe el sitio.
- **7. Autoevaluación** — lo que sigue a `--- No mires esto hasta responder ---`
  son las respuestas, y el sitio **las empareja por posición con las preguntas**
  para mostrar cada una debajo de la suya. Tiene que haber exactamente una
  respuesta por pregunta y en el mismo orden: si las cantidades no coinciden no se
  empareja nada y caen todas juntas al final, con aviso en consola.
- **Flashcards** — al final del archivo, una por línea, `Pregunta | Respuesta`,
  sin markdown adentro (el sitio escapa el texto).
- **6. Distinciones** — se escribe en forma de lista, un ítem por par con sus
  tres subítems (`Se confunden porque` / `Criterio para decidir` / `Dónde se
  cae`), pegada o con líneas en blanco entre pares: `datos.py: parsear_distinciones`
  la separa en campos (`par`, `texto`, `se_confunden`, `criterio`, `error`) por
  regex, y el sitio arma el `<ul><li>` a mano desde esos campos — no le pasa el
  markdown crudo a un renderizador. Esto **corrigió un bug real**: con líneas en
  blanco entre pares, CommonMark trataba la lista como "loose" y envolvía cada
  ítem en un `<p>`, con lo que el selector CSS `li > strong` —el que pinta el
  acento del par— nunca coincidía. Pasó inadvertido en el sitio HTML directo
  porque nadie miró el color con la lupa puesta ahí. El vocabulario tiene el
  mismo tratamiento: no se renderiza desde markdown crudo, se parsea y se
  re-arma como `<dl>`.

`ema.py preparar` le pasa al prompt, además de las ideas principales anteriores,
**la lista de términos que el glosario ya tiene**, con la instrucción de no
redefinirlos. Eso evita la duplicación en el origen; el deduplicado del sitio es
solo la red. Con los 58 documentos actuales el build no emite ningún aviso.

El documento no puede escribir HTML crudo ni anclas propias: dentro de un
capítulo las únicas tres anclas posibles (`#sNN-idea-principal`,
`#sNN-lo-esencial-del-capitulo`, `#sNN-mapa`) son fijas, porque los tres títulos
visibles nunca cambian (`web/src/lib/anclas.ts`). Tampoco casillas `- [ ]`,
notas al pie, callouts ni atributos `{.clase}`: no hay plugins de markdown
instalados en `web/src/lib/md.ts` y se ven como caracteres sueltos.

## Sitio y despliegue

`ema.py web` regenera todo desde `libros/*/estudio/*.md`: corre `datos.py`
(escribe `libros/<slug>/libro.json` y `web/src/data/<slug>.json`) y después
`npm run build` dentro de `web/` (Astro), que arma `sitio/`. Sigue sin haber
framework de UI: el HTML final tiene la misma estructura que antes —capítulos
en `<details>`, Mermaid diferido, flashcards con `<button>`— y usa el mismo
`estilo.css` y `tarjetas.js`, sin tocar. Lo que cambió es de dónde sale el
contenido: antes `sitio.py` leía el markdown y armaba el HTML en las mismas
funciones; ahora `contenido.py` + `datos.py` lo dejan en JSON, y `web/` es lo
único que sabe de HTML.

`vercel.json` corre `npm install --prefix web && npm run build --prefix web` y
sirve `sitio/`. **`sitio/` ya no se commitea** — Vercel lo reconstruye en cada
deploy a partir de `web/src/data/*.json`, que sí está en git. Si se edita un
documento de estudio hay que correr `ema.py web` igual que antes para que el
JSON quede al día; lo que cambia es que ya no hay que revisar un diff de HTML
gigante en cada push, porque el HTML no viaja por git.

**Cada libro es UNA página**: `sitio/<libro>/index.html` trae la jerarquía
completa del original con la idea principal de cada capítulo, y cada capítulo
plegado en un `<details>` que se abre ahí mismo. No hay una página por capítulo:
el enlace profundo a un capítulo es `index.html#sNN`, y a un bloque suyo
`index.html#sNN-vocabulario-clave`.

Arriba de todo, antes de la lista de capítulos, puede ir un **resumen general
del texto entero** («De qué trata el texto»): de qué va el libro completo, para
ubicarse antes de entrar a cualquier capítulo. Sale de la clave `resumen` de
`libro.toml` —prosa escrita a mano, **no se genera con el prompt**—, con los
párrafos separados por una línea en blanco y markdown inline permitido
(negrita, cursiva). `datos.py` lo guarda ya partido en párrafos, igual que el
bloque 2 de un capítulo, así que el JSON sigue sin llevar HTML. Un libro sin
esa clave simplemente no muestra el bloque.

La hoja muestra **todos** los capítulos del libro, no solo los procesados: los
que todavía no tienen documento salen atenuados y con borde punteado. La lista
sale de `libros/<slug>/capitulos.toml`, que escribe `dividir` y que **sí va a
git** — `secciones/` no, porque ahí está el texto del original. Si se re-divide
un libro hay que volver a correr `web`, o la hoja queda con capítulos que ya no
existen (el sitio avisa cuando un documento no está en el manifiesto).

Al final de la hoja van los **cuatro consolidados del libro** —glosario,
distinciones, autoevaluación y mazo de flashcards—, cada uno en su plegable y
armados juntando los bloques de todos los capítulos. Sus anclas (`#glosario`,
`#distinciones`, `#autoevaluacion`, `#flashcards`) van **en el `<details>` mismo
y no en un encabezado interno**: el marcador del riel saltea los destinos sin
`offsetParent`, y un `h2` dentro de un plegable cerrado tiene rect en ceros. Un
consolidado sin contenido no se renderiza ni aparece en el riel.

El glosario deduplica por término, gana la definición del primer capítulo y avisa
en consola cuando dos capítulos lo definen distinto. **No unifica sinónimos**
(`Tridimensionalismo` y `Teoría tridimensional del derecho` quedan como dos
entradas): cualquier regla que los junte junta también términos distintos, y eso
se arregla escribiendo mejor los documentos, no en el sitio.

Detalles del diseño que no son obvios y ya costaron una vuelta:

- Los `id` van namespaceados con `sNN-`. En una sola hoja hay tantos
  `vocabulario-clave` y `flashcards` como capítulos, y sin prefijo las anclas
  colisionan. Por eso `recolectar` avisa si dos documentos repiten el número.
- **Mermaid vive en `estaticos/tarjetas.js`**, copiado sin tocar a
  `web/public/tarjetas.js`, y se carga con `import()` dinámico cuando un
  diagrama se acerca a la pantalla (`IntersectionObserver`). Arrancar treinta y
  nueve diagramas al cargar es inaceptable, y uno dentro de un `<details>`
  cerrado mide cero de ancho, así que Mermaid lo calcularía mal. El observador
  resuelve las dos cosas: un elemento en `display:none` nunca intersecta, y
  avisa recién cuando el capítulo se abre, con el ancho real.
- El botón "Abrir todos los capítulos" existe porque el navegador **no busca
  dentro de un `<details>` cerrado**: con todo abierto, Cmd-F recorre el libro
  entero.
- `details.capitulo` necesita `min-width: 0`. Es un ítem de grilla y hereda
  `min-width: auto`, o sea su tamaño mínimo de contenido, que con la grilla de
  flashcards adentro pasa de 800px y desborda la columna de lectura.
- Un `<summary>` con `display: flex` **pierde el triángulo nativo**, así que el
  chevron se dibuja con `::after`.
- El marcador de posición del riel saltea los destinos sin `offsetParent`: los
  que están dentro de un capítulo cerrado tienen rect en ceros y se leerían como
  "estoy justo acá".
- Todo lo que puede ser destino de un ancla necesita `scroll-margin-top`, no solo
  los encabezados: la sección de flashcards también, o la barra fija la tapa.

`web/src/data/*.json` se commitea; `sitio/` no. Si cambia un documento de
estudio y no se corre `web`, el JSON queda desactualizado y el próximo deploy
publica lo viejo. Ojo con el diff del JSON: cada corrida reescribe el archivo
del libro entero, así que agregar un capítulo cambia un archivo grande.

Está publicado en https://derecho-five.vercel.app (proyecto `derecho` del team
`sebastianmora98s-projects`, importado desde GitHub: cada push a `main`
redespliega).

Los enlaces a `estilo.css`, `tarjetas.js` y entre libros son **absolutos**
(`/estilo.css`, `/beccaria-delitos-y-penas/index.html`), no relativos: es lo que
usa `web/src/layouts/Base.astro`. Con eso, activar `cleanUrls` no debería romper
nada por el motivo viejo (rutas relativas resolviéndose contra la raíz cuando
`/<slug>` se sirve sin barra final), pero no hay necesidad de activarlo — no
está probado y no resuelve nada que haga falta.

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
por el autor, sin apartados ni capítulo contenedor, así que el sitio muestra la
lista corrida. Dividido con `--nivel 2` → **39 secciones** («Al lector»,
«Introducción» y los 47 capítulos, con 9 secciones que juntan capítulos cortos).
`formato_citas = "capitulos"`: el autor numera sus capítulos y esta edición no
preservó la paginación.

**Está completo: las 39 secciones tienen documento de estudio, alineado a la
plantilla condensada.** El libro entero queda en 154 términos de glosario, 78
preguntas (2 por capítulo) y 136 flashcards (entre 1 y 4 por capítulo, según lo
que cada uno sostiene de verdad), y la hoja pesa 340 KB crudos / 94 KB gzip.
Los 39 diagramas Mermaid compilan, verificado en el navegador abriendo la hoja
entera. Todos los documentos entran en los tres topes (1.100 palabras totales,
500 la parte visible, 400 el bloque 2), igual que los 19 de FS.

**Sin la variante `examen`**, por el mismo motivo que en el otro libro: mantiene
2 preguntas y 4 flashcards, y solo aprieta el foco de la variante base.

La conversión está verificada byte a byte contra el PDF: 47/47 capítulos, y el
delta de palabras por capítulo es exactamente la cantidad de números de página
que cruza. Cero prosa perdida. Lo que sí quedaba mal era el formato, ya
arreglado: 70 párrafos partidos en los saltos de página y 18 palabras con el
guion colgado. Queda pendiente, a propósito, la reubicación de las 3 notas al pie
que cortan una frase al medio (líneas con marcador numérico o `*`). Las tres
están anotadas en el documento del capítulo donde caen, como pide el prompt: la
del cap. 3, la del cap. 13 —que parte la frase sobre la atrocidad del delito— y
la del cap. 34, que aparece a mitad del cap. 35 y contiene la retractación de
Beccaria («me avergüenzo de haber escrito así»).

**fs-diferentes-concepciones-de-lo-juridico-1** — *Derecho y persona*, Carlos
Fernández Sessarego (5ª ed., Astrea, 2015). Es el capítulo "Diferentes
concepciones de lo jurídico", **escaneado**: se procesó con `ocr.py`, no con
`convertir`. Tiene tres pisos —capítulo > apartado A/B > parágrafo §—. El
capítulo se declara en la clave `contenedor` de su `libro.toml` y los apartados
en `[[partes]]`; de ahí saca el sitio la jerarquía. Dividido con `--nivel 2` →
**10 secciones** (§ 53 a § 63, con 1 que junta dos parágrafos cortos).
`formato_citas = "paginas"` porque el escaneo conservó los folios.

**Se sacó el apartado C entero** —«Personalismo, tridimensionalismo y otros
aportes del código civil peruano de 1984 a la codificación civil comparada»,
que eran los parágrafos § 64 a § 74 y las secciones 11 a 19—: es material
sobre el código civil peruano que no entra en la materia. Se sacó con
`omitir` en `libro.toml` (`'^§\s*(6[4-9]|7[0-4])\.'`) en vez de a mano, para
que volver a dividir no los traiga de nuevo, y se borraron sus 9 documentos de
estudio. El apartado C también salió de `[[partes]]`. Las secciones 1 a 10 no
cambiaron de número ni de slug, así que ningún enlace profundo se rompió.

**Está completo: los 10 capítulos tienen documento de estudio, alineado a la
plantilla condensada.** El libro entero queda en 43 términos de glosario, 20
preguntas (2 por capítulo) y 31 flashcards (entre 1 y 4 por capítulo, según lo
que cada uno sostiene de verdad), y la hoja pesa 92 KB crudos / 23 KB gzip.

**Sin la variante `examen`, a propósito**: mantiene 2 preguntas y 4 flashcards
por capítulo, igual que la variante base.

Dos cosas que aprendió esta tanda y conviene repetir:

- **Procesar en orden estricto.** `contexto_previo` le pasa al prompt los términos
  que el glosario ya tiene, y esa lista se arma leyendo `estudio/*.md` en el
  momento de `preparar`. Procesar salteado hace que un término se defina en el
  capítulo equivocado: pasó con `nasciturus` y `situaciones jurídicas subjetivas`,
  que son de § 70 y quedaron primero en § 71 por haber hecho las secciones largas
  como lote. (Esos dos parágrafos ya no están en el libro —eran del apartado C—,
  pero la lección vale igual para cualquier tanda.)
- **Medir excluyendo el diagrama.** Contar el código Mermaid como palabras del
  documento infla unas 80 por archivo y hace perseguir un tope que ya se cumplía.

`ema.py estado` da el detalle y avisa si quedó algún documento de `estudio/`
cuya sección ya no existe.

**Auditoría de la conversión** (hecha a pedido, porque el sitio parecía
incompleto): el texto está completo. Cubre pp. 119-189 sin huecos, 72 mitades
con texto de las 76 del PDF —las otras 4 están realmente en blanco— y el volumen
cierra al 0,3% contra lo esperable para el formato. Lo que hacía parecer
incompleto al libro era que faltaban los documentos de estudio, no el texto.

Defectos que quedan, todos cosméticos y ya medidos:

- El título de § 63 dice `concrero` por `concreto`: es una mala lectura del OCR
  sobre el escaneo, y no hay regla que la arregle sin un diccionario.
- En la p. 158 la palabra `fugaz` quedó partida (`tan fu-` + `gaz`) porque el
  párrafo arrancaba con el número de folio, así que el rearmado de guiones no
  disparó. Va con un resto de cabecera cortada, `EL DERECH`.
- Las notas al pie que siguen de una página a la otra se sueldan a mitad de una
  frase del autor. Es el problema de orden de las notas; queda sin resolver a
  propósito.

Ojo con este libro: es material **con derechos vigentes** (Astrea 2015), a
diferencia de Beccaria, que es CC. El `libro.md` y las `secciones/` quedan
fuera de git, como corresponde, y los documentos de estudio no deben
reconstruir el texto: citas cortas y con referencia, nada más.

**el-ojo-del-poder** — *El ojo del poder*, entrevista a Michel Foucault sobre
el Panóptico de Bentham (Jean-Pierre Barou y Michelle Perrot, en Bentham,
Jeremías: *El Panóptico*, Ed. La Piqueta, Barcelona, 1980). No es un texto de
Derecho, pero se usa en la misma materia que Beccaria y FS. Es una entrevista
corrida sin capítulos del autor: **1 sola sección**, dividida con
`--max-chars 60000` para que no se partiera a la mitad de un intercambio.
`formato_citas = "parrafos"`.

`markitdown` **arma mal el orden de las palabras** en este PDF concreto —un
defecto distinto y peor que el de página/pie interrumpiendo una palabra: acá
párrafos enteros salen con las palabras reordenadas, aunque el resultado se lea
como prosa plausible—. `pdftotext -layout` extrae el mismo texto en el orden
correcto, así que `libro.md` se reconstruyó desde ahí en vez de desde
`markitdown`. Además había una cabecera corrida
(`www.philosophia.cl / Escuela de Filosofía Universidad ARCIS.`) que
`limpieza.py: detectar_cabeceras()` no detecta porque su heurística descarta
líneas que terminan en `.,;:` —para no confundirlas con prosa normal—, y esta
cabecera termina en punto. Se sacó a mano con una regex específica de esta
conversión (no es un caso general, no se tocó `limpieza.py` por esto).

**Está completo: la única sección tiene su documento de estudio.** 3 términos
de glosario, 2 preguntas, 3 flashcards, y la hoja pesa 12 KB crudos / 3,7 KB
gzip. El diagrama Mermaid compila, verificado en el navegador.

**la-inteligencia-fracasada** — *La inteligencia fracasada*, José Antonio
Marina (Anagrama, 6ª ed., 2005). **Escaneado**, procesado con `ocr.py`, no con
`convertir` (sin capa de texto). Jerarquía plana: Introducción + capítulos I a
VII + Epílogo, **9 secciones**, una por capítulo real.

Dos problemas de conversión que no había hecho falta resolver antes:

- **La detección de doble-página-por-hoja se dejaba engañar por la portada.**
  Esta detección mide el tamaño de la página 1 (`pdfinfo` sin `-f`/`-l` informa
  solo esa), y la portada de este escaneo quedó apaisada (852x611, el pliego
  entero) mientras el cuerpo es retrato normal (460x599). Con la regla vieja,
  `ocr.py` habría partido las 173 páginas del cuerpo al medio, mezclando texto
  de renglones vecinos igual que el problema que esa regla existe para evitar
  — la vio corriendo esta misma conversión y se frenó a tiempo. Corregido en
  `ocr.py`: `a_markdown` ahora confirma con una página interior (la del medio
  del libro) antes de aplicar el corte a todo, y `rasterizar` con `mitades=1`
  ya no fuerza un recorte `-W/-H` medido de una sola página. Ver el detalle en
  "PDF escaneados" arriba.
- **Los encabezados de capítulo no los detectó el heurístico de `ocr.py`**,
  que da por sentado el patrón `§ NN. TÍTULO` de FS. Los títulos de este libro
  son romanos ("I. LA INTELIGENCIA MALOGRADA") y Vision los reconoció bien,
  pero no como encabezado propio: quedaron como texto corrido pegado al
  párrafo anterior. Se insertaron los 9 `##` a mano, ubicados cruzando el
  índice del propio libro (al final del escaneo) contra el folio más cercano
  a cada uno — los 9 se confirmaron con el texto real de la página, no a
  ciegas. También se recortó a mano la bibliografía por capítulos y el índice
  del libro, pegados sin encabezado propio al final del Epílogo.
- **Los folios en general no se preservaron**: Vision solo reconoció 6 de 173
  como marca aparte del cuerpo; el resto de los números de página quedaron
  sueltos dentro del texto corrido. Por eso `formato_citas = "capitulos"` y no
  `"paginas"`, pese a ser un escaneo — se cita por el número romano del
  capítulo, no por folio.

**Está completo: los 9 capítulos tienen documento de estudio.** El libro
entero queda en 38 términos de glosario, 18 preguntas (2 por capítulo) y 36
flashcards (todas los 9 capítulos dieron para las 4), y la hoja pesa 80 KB
crudos / 21 KB gzip. Los 9 diagramas Mermaid compilan, verificado en el
navegador (los nueve, no solo una muestra).

**Sin la variante `examen`, mismo motivo que los otros tres libros.**

Un bug real de la plantilla salió a la luz procesando este libro: en el bloque
6, `prompts/estudio.md` tenía escrito literalmente `{{CONTEXTO_PREVIO}}` en
medio de una oración ("Si `{{CONTEXTO_PREVIO}}` trae capítulos ya
procesados..."), en vez de nombrar la sección "CONTEXTO DE CORRIDAS
ANTERIORES". Como la sustitución de placeholders es un reemplazo literal, el
prompt generado para cada sección quedaba con el bloque entero de contexto
pegado en medio de esa frase, en vez de una referencia por nombre. Corregido:
ahora dice "Si el CONTEXTO DE CORRIDAS ANTERIORES de arriba trae capítulos ya
procesados...". De paso, el bloque 1 pedía "qué pregunta **del derecho** viene
a contestar este capítulo" — específico de Derecho y ya no genérico ahora que
el taller suma textos de otra disciplina usados en la misma materia. Se sacó
"del derecho".

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
