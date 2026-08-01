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
  capitulos.toml      lista de capítulos que escribe `dividir` — en git, la
                      usa el sitio para mostrar también los pendientes
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
son **2 preguntas y 4 flashcards por capítulo**, con el foco cambiado:

- De las 2 preguntas, **una es de exposición** y se formula con el verbo del
  examen («¿qué se entiende por…?», «explique… y sus implicaciones», «ubique…»);
  la otra es de aplicación o crítica. Su respuesta de referencia es el molde de la
  respuesta del examen —3 a 5 oraciones que abren con la definición o la tesis—,
  no una pista.
- Las 4 flashcards se eligen por prioridad —definición del término central,
  enumeración que hay que recitar, tesis con su autor, criterio de una
  distinción— y la prueba para dejar una es *¿la necesitaría para escribir el
  párrafo de una respuesta?*
- El prompt pide usar `{{CONTEXTO_PREVIO}}` para que la pregunta de exposición
  obligue a traer capítulos anteriores, porque las preguntas reales cruzan
  capítulos y ninguna pregunta por capítulo las imita sola.

**La variante `examen` dejó de subir las cantidades.** Subía a 5 y 12, que es la
dirección contraria; ahora mantiene 2 y 4 y lo que hace es apretar el foco (las
dos preguntas de exposición, respuestas de 5 a 7 oraciones).

### Qué falta alinear en los 58 documentos ya escritos

Se les quitó «Qué releer del original» y se renumeraron —eso era mecánico y ya
está hecho—, pero **siguen con la forma vieja en dos puntos**, y las dos
diferencias son reescritura de contenido, no un `sed`:

1. **El bloque 2 tiene 4 párrafos y unas 400-450 palabras**; la regla nueva pide 2
   o 3 y hasta 400.
2. **El test y el mazo van con 4 preguntas y 8 flashcards** por capítulo; la regla
   nueva pide 2 y 4.

Conviene hacer las dos en **una sola pasada por documento**, y completa por libro:
un mazo mitad de 4 y mitad de 8, o un libro con capítulos de 2 y de 4 párrafos, se
nota enseguida. Son 58 documentos —39 de Beccaria y 19 de FS—.

Contratos con el código que no hay que romper:

- **Los cuatro títulos son claves de extracción.** Un `##` cuyo título contenga
  «vocabulario», «distinciones», «autoevaluacion» o «flashcards» sale del capítulo
  y va al consolidado (`sitio.py: destino_del_bloque`). Es lista blanca de
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
- **6. Distinciones** — la lista va **pegada**, sin líneas en blanco entre ítems, o
  se pierde el color de acento del par (`estilo.css`: el selector es
  `li > strong`, y con líneas en blanco el markdown mete un `<p>` en medio). Este
  contrato **era del vocabulario y se mudó acá**: el vocabulario ya no se
  renderiza desde markdown crudo, el sitio lo parsea y lo re-arma como `<dl>`.

`ema.py preparar` le pasa al prompt, además de las ideas principales anteriores,
**la lista de términos que el glosario ya tiene**, con la instrucción de no
redefinirlos. Eso evita la duplicación en el origen; el deduplicado del sitio es
solo la red. Con los seis documentos actuales el build no emite ningún aviso.

El documento no puede escribir HTML crudo ni anclas propias: los `id` los pone
`sitio.py: anclar`, que además le saca el número al encabezado visible. Tampoco
casillas `- [ ]`, notas al pie, callouts ni atributos `{.clase}`: no hay plugins
de markdown instalados y se ven como caracteres sueltos.

## Sitio y despliegue

`ema.py web` regenera `sitio/` completo desde `libros/*/estudio/*.md`. Es HTML
plano: sin build y sin framework. `vercel.json` apunta a `sitio/` sin comando de
build, así que Vercel solo sirve los archivos.

**Cada libro es UNA página**: `sitio/<libro>/index.html` trae la jerarquía
completa del original con la idea principal de cada capítulo, y cada capítulo
plegado en un `<details>` que se abre ahí mismo. No hay una página por capítulo:
el enlace profundo a un capítulo es `index.html#sNN`, y a un bloque suyo
`index.html#sNN-vocabulario-clave`.

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
- **Mermaid vive en `estaticos/tarjetas.js`, no en `sitio.py`**, y se carga con
  `import()` dinámico cuando un diagrama se acerca a la pantalla
  (`IntersectionObserver`). Arrancar treinta y nueve diagramas al cargar es
  inaceptable, y uno dentro de un `<details>` cerrado mide cero de ancho, así que
  Mermaid lo calcularía mal. El observador resuelve las dos cosas: un elemento en
  `display:none` nunca intersecta, y avisa recién cuando el capítulo se abre, con
  el ancho real.
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

El sitio se commitea. Si cambia un documento de estudio y no se corre `web`,
lo publicado queda desactualizado. Ojo con el diff: cada corrida reescribe la
hoja entera de cada libro, así que agregar un capítulo cambia un archivo grande.

Está publicado en https://derecho-five.vercel.app (proyecto `derecho` del team
`sebastianmora98s-projects`, importado desde GitHub: cada push a `main`
redespliega).

**No volver a activar `cleanUrls` en `vercel.json`.** El motivo original —que
rompía los enlaces relativos `02.html` del índice— ya no aplica, porque esos
enlaces son anclas dentro de la misma hoja. Pero sigue siendo mala idea: los
enlaces a `estilo.css` y `tarjetas.js` siguen siendo relativos, y `cleanUrls`
sirve el índice del libro en `/<slug>` sin barra final, así que cualquier ruta
relativa se resuelve contra la raíz.

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

**Está completo: las 39 secciones tienen documento de estudio.** El libro entero
queda en 154 términos de glosario, 155 preguntas y 312 flashcards, y la hoja pesa
420 KB crudos / 111 KB gzip —el doble que el otro libro, porque tiene el doble de
capítulos—. Los 39 diagramas Mermaid compilan, verificado en el navegador
abriendo la hoja entera. Todos los documentos entran en los tres topes (1.400
palabras totales, 700 la parte visible, 450 el bloque 2), igual que los 19 de FS.

**Sin la variante `examen`**, por el mismo motivo que en el otro libro: pedía 12
flashcards y 5 preguntas, y los documentos ya escritos iban con 8 y 4. La
cantidad quedó pareja para los 39.

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
`convertir`. Tiene tres pisos —capítulo > apartado A/B/C > parágrafo §—. El
capítulo se declara en la clave `contenedor` de su `libro.toml` y los apartados
en `[[partes]]`; de ahí saca el sitio la jerarquía. Dividido con `--nivel 2` →
**19 secciones** (§ 53 a § 74, con 3 que juntan parágrafos cortos).
`formato_citas = "paginas"` porque el escaneo conservó los folios.

**Está completo: los 19 capítulos tienen documento de estudio.** El libro entero
queda en 81 términos de glosario, 76 preguntas y 152 flashcards, y la hoja pesa
212 KB crudos / 52 KB gzip.

**Sin la variante `examen`, a propósito.** Pedía 12 flashcards y 5 preguntas por
capítulo; con el mazo y el test consolidados por libro eso daba 228 tarjetas y 95
preguntas, y los primeros documentos ya iban con 8 y 4. Un mazo mezclado se nota,
así que la cantidad quedó pareja en 8 y 4 para los 19.

Dos cosas que aprendió esta tanda y conviene repetir:

- **Procesar en orden estricto.** `contexto_previo` le pasa al prompt los términos
  que el glosario ya tiene, y esa lista se arma leyendo `estudio/*.md` en el
  momento de `preparar`. Procesar salteado hace que un término se defina en el
  capítulo equivocado: pasó con `nasciturus` y `situaciones jurídicas subjetivas`,
  que son de § 70 y quedaron primero en § 71 por haber hecho las secciones largas
  como lote.
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
