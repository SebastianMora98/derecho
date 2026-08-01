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

### Pendientes de la plantilla

Detectados al ejecutar el prompt en las primeras dos secciones; conviene
resolverlos antes de seguir en serie:

- Las secciones 3 (mapa argumental en texto) y 4 (mapa visual) se solapan. Si
  el diagrama cumple, la 3 debería reducirse a las referencias al original.
- `formato_citas = "subtitulos"` no aplica a un texto sin subtítulos ni
  paginación preservada; se terminó citando por capítulo. Falta admitir
  `capitulos` como valor en `libro.toml`.
- La sección 8 pide conectar con secciones anteriores aunque sea la primera
  corrida. Debería condicionarse a `{{CONTEXTO_PREVIO}}`.

## Convenciones

- Todo en español neutro.
- No editar `libro.md`, `secciones/` ni `sitio/` a mano: se regeneran. Lo que
  se edita es `prompts/`, `libro.toml`, `estaticos/` y los documentos de
  `estudio/`.
- Fuera de git: `original/`, `libro.md`, `secciones/`, `prompts/` de cada libro.
  El repo publica los documentos de estudio, no los libros.
