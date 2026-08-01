<!--
Bloques opcionales que se inyectan en {{VARIANTES}} de la plantilla.
Activálos en libro.toml:  variantes = ["examen", "tecnico"]

Cada variante es un `## nombre` seguido del texto que se pega en el prompt.
Podés agregar las tuyas: el nombre del encabezado es la clave.
-->

## examen

Al final del documento, genera 20 flashcards en formato `Pregunta | Respuesta`
listas para importar a Anki. Una por línea, sin numerar, cubriendo definiciones,
distinciones y aplicaciones (no solo memorización literal).

## investigacion

En la sección 7 (Conexiones), incluye 3-5 preguntas de investigación abiertas
que podrían derivarse de esta sección. En la sección 8, marca explícitamente
las afirmaciones que necesitarían fuente secundaria para poder citarse.

## tecnico

En la sección 5, para cada idea difícil incluye además una representación
formal: fórmula, diagrama en pseudocódigo, o esquema causal en texto.

## narrativo

En la sección 3, en vez de mapa argumental usa un mapa de tensiones: qué se
opone a qué, qué evoluciona, qué se resuelve y qué queda abierto.

## aplicacion-practica

Agrega una sección final "12. Cómo lo uso" con 3-5 acciones concretas y
verificables que se desprendan de esta sección, cada una con la condición en
la que aplica y con la referencia al pasaje que la respalda.
