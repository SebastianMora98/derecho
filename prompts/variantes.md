<!--
Bloques opcionales que se inyectan en {{VARIANTES}} de la plantilla.
Activálos en libro.toml:  variantes = ["examen", "tecnico"]

Cada variante es un `## nombre` seguido del texto que se pega en el prompt.
Podés agregar las tuyas: el nombre del encabezado es la clave.

**Citá los bloques por TÍTULO y no por número.** Los números ya se corrieron dos
veces al reordenar la plantilla y las referencias quedaron apuntando al bloque
equivocado sin que nada avisara.

Ninguna variante puede agregar nada DESPUÉS de `## Flashcards`. Y si agrega un
bloque nuevo, ese bloque se va a ver DENTRO del capítulo, no consolidado por
libro: solo se consolidan los cuatro cuyo título contiene «vocabulario»,
«distinciones», «autoevaluacion» o «flashcards».
-->

## examen

En Flashcards, subí a 12 tarjetas en vez de 6 a 8, que es el mazo del libro y es
donde vive todo el recall. Reparto: la mitad de los términos del vocabulario, unas
3 de las distinciones (preguntadas como "¿cómo distingo A de B?") y el resto de
las afirmaciones y consecuencias del capítulo. Nada de memorizar frases literales
del autor, y ninguna que repita otra con otras palabras.

En Autoevaluación, subí a 5 preguntas si el capítulo las da, manteniendo la regla
de que ninguna se contesta con un dato o una definición: de las 5, al menos 3 de
aplicación a un caso nuevo.

## investigacion

Al final de «Qué releer del original», agregá una lista "Preguntas abiertas" con 3
preguntas de investigación que se desprendan de este capítulo y que el texto no
contesta.

En «Lo esencial del capítulo», marcá en media cláusula, donde caiga, cada
afirmación que necesitaría una fuente secundaria para poder citarse en un trabajo:
"esto lo afirma sin sustento en esta sección". No abras un bloque nuevo para eso.

## tecnico

En «Lo esencial del capítulo», agregá al final una representación formal de lo que
la prosa explicó: una fórmula, un esquema causal en texto o un pseudocódigo en un
bloque de código cercado. Una sola, y no uses ```mermaid para eso: el único
diagrama del documento es el del Mapa.

## narrativo

En «Mapa», en vez del esqueleto del argumento, dibujá un mapa de tensiones: qué se
opone a qué, qué evoluciona, qué se resuelve y qué queda abierto. Sigue siendo un
solo diagrama Mermaid, con las mismas reglas de sintaxis y el mismo tope de 7
nodos.

## aplicacion-practica

Agregá un bloque `## 8. Cómo lo uso` con 3 acciones concretas y verificables que se
desprendan de este capítulo, cada una con la condición en la que aplica y con la
referencia al pasaje que la respalda.

Ubicación obligatoria: **después** de las respuestas de referencia de
«Autoevaluación» y **antes** de `## Flashcards`. Ese bloque se va a ver dentro del
capítulo, al final, porque su título no es una de las cuatro claves de
consolidación.
