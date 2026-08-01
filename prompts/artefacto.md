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

1. **Cabecera** con obra, autor y secciones cubiertas.
2. **Mapa de la obra**: las tesis centrales de cada sección en una línea,
   navegables.
3. **Tarjetas de conceptos**: una por concepto clave, que muestran el término
   y revelan la definición reformulada al hacer clic. Marcá la "confusión
   frecuente" con un color distinto.
4. **Modo test**: las preguntas de la sección 9 de cada documento, una a la
   vez, con botón para revelar la respuesta de referencia y un contador de
   autoevaluación (acerté / fallé) que persiste en `localStorage`.
5. **Preguntas socráticas** en una lista aparte, para leer antes de volver al
   libro.
6. **Qué releer**: los pasajes señalados, agrupados por sección.

# REGLAS

- Todo el contenido sale de los documentos de estudio. Si algo falta, dejá el
  bloque vacío con una nota, no lo rellenes.
- Debe funcionar en tema claro y oscuro, y en pantalla de teléfono.
- Español neutro. Sin animaciones decorativas ni relleno.
- Guardá el archivo en `libros/<slug>/artefactos/` antes de publicarlo.
