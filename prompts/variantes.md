<!--
Bloques opcionales que se inyectan en {{VARIANTES}} de la plantilla.
Activálos en libro.toml:  variantes = ["examen", "tecnico"]

Cada variante es un `## nombre` seguido del texto que se pega en el prompt.
Podés agregar las tuyas: el nombre del encabezado es la clave.

Las referencias son a los siete bloques de prompts/estudio.md:
  1 Idea principal · 2 Explicación paso a paso · 3 Mapa ·
  4 Vocabulario clave · 5 Distinciones que se confunden ·
  6 Qué releer del original · 7 Autoevaluación · Flashcards

Ninguna variante puede agregar nada DESPUÉS de `## Flashcards`, y si agrega un
bloque nuevo tiene que ir entre las respuestas del 7 y las flashcards: el sitio
pliega todo lo que sigue a la marca de respuestas hasta el próximo `##`.
-->

## examen

En el bloque Flashcards, generá exactamente 20 tarjetas en vez de 12 a 18.
Reparto: unas 8 del vocabulario del bloque 4, unas 5 de las distinciones del
bloque 5 (preguntadas como "¿cómo distingo A de B?"), unas 5 de las afirmaciones
y consecuencias del bloque 2, y 2 de aplicación (un caso corto y qué
corresponde). Nada de memorización literal de frases del autor.

En el bloque 5, subí a 5 distinciones si el material las da, y en cada una cerrá
el "dónde se cae" con la respuesta equivocada concreta que se suele dar.

## investigacion

Al final del bloque 6, agregá una lista "Preguntas abiertas" con 3 a 5 preguntas
de investigación que se desprendan de este capítulo y que el texto no contesta.

En el bloque 2, marcá explícitamente, dentro del paso donde caiga, cada
afirmación que necesitaría una fuente secundaria para poder citarse en un
trabajo: "esto lo afirma sin sustento en esta sección". No abras un bloque nuevo
para eso.

## tecnico

En el bloque 2, agregale a cada paso que lo admita una representación formal
además de la prosa: una fórmula, un esquema causal en texto o un pseudocódigo en
un bloque de código cercado. No uses ```mermaid para eso: el único diagrama del
documento es el del bloque 3.

## narrativo

En el bloque 3, en vez del esqueleto del argumento, dibujá un mapa de tensiones:
qué se opone a qué, qué evoluciona, qué se resuelve y qué queda abierto. Sigue
siendo un solo diagrama Mermaid, con las mismas reglas de sintaxis y el mismo
tope de 9 nodos.

## aplicacion-practica

Agregá un bloque `## 8. Cómo lo uso` con 3 a 5 acciones concretas y verificables
que se desprendan de este capítulo, cada una con la condición en la que aplica y
con la referencia al pasaje que la respalda.

Ubicación obligatoria: **después** de las respuestas de referencia del bloque 7 y
**antes** de `## Flashcards`. En otro lugar, el sitio lo mete dentro del pliegue
de las respuestas o lo parsea como tarjetas.
