<!--
Plantilla para convertir uno o varios documentos de estudio en un artefacto
de Claude (página HTML autocontenida, publicable con la herramienta Artifact).

No se usa con `ema.py preparar`. Se lo pasás a Claude directamente:
  "Seguí prompts/artefacto.md para libros/<slug>, secciones 1-4"
-->

# ROL

Construí un artefacto de estudio interactivo a partir de los documentos de
estudio ya generados. El artefacto no reemplaza al documento: es la herramienta
de repaso activo que uso cuando ya leí el original.

# ENTRADA

Los archivos de `libros/<slug>/estudio/` indicados, más `libro.toml` para el
título y el autor. No inventes contenido que no esté en esos documentos.

# LO QUE DEBES PRODUCIR

Una página HTML autocontenida (sin recursos externos: CSS y JS en línea) con:

Los bloques se citan por TÍTULO y no por número: los números de
`prompts/estudio.md` ya se corrieron dos veces al reordenarla.

1. **Cabecera** con obra, autor y capítulos cubiertos.
2. **Mapa de la obra**: la «Idea principal» de cada capítulo en una línea,
   navegables, agrupadas por apartado si `libro.toml` declara `[[partes]]`.
3. **Tarjetas de vocabulario**: una por término de «Vocabulario clave», que
   muestran el término y revelan la definición al hacer clic. Deduplicá los
   términos repetidos entre capítulos, como hace el glosario del sitio.
4. **Modo test**: las preguntas de «Autoevaluación» de cada documento, una a la
   vez, con botón para revelar la respuesta de referencia y un contador de
   autoevaluación (acerté / fallé) que persiste en `localStorage`.
5. **Distinciones**: las de «Distinciones que se confunden», cada una con su
   criterio para decidir, en un panel aparte y con el "dónde se cae" en otro color.
6. **Qué releer**: los pasajes de «Qué releer del original», agrupados por capítulo.

# REGLAS

- Todo el contenido sale de los documentos de estudio. Si algo falta, dejá el
  bloque vacío con una nota, no lo rellenes.
- Debe funcionar en tema claro y oscuro, y en pantalla de teléfono.
- Español neutro. Sin animaciones decorativas ni relleno.
- Guardá el archivo en `libros/<slug>/artefactos/` antes de publicarlo.
