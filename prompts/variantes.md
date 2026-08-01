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

**No cambia las cantidades: siguen siendo 2 preguntas y 4 flashcards.** Antes esta
variante las subía a 5 y 12, y era el error que la hacía inservible: un examen se
prepara con menos material y mejor elegido, no con más. Lo que hace es apretar el
foco.

En Autoevaluación, **las 2 preguntas son de exposición** —se pierde la de
aplicación—, y las dos se formulan con el verbo del examen: «¿qué se entiende
por…?», «explique… y sus implicaciones», «ubique… dentro de…», «identifique dos… y
explique hasta dónde…». Al menos una tiene que obligar a traer un capítulo
anterior de {{CONTEXTO_PREVIO}}, porque las preguntas reales cruzan capítulos.

Las respuestas de referencia pasan a ser **el molde completo de la respuesta**: de
5 a 7 oraciones, abriendo con la definición o la tesis, siguiendo con lo que la
sostiene y cerrando con la implicación que el examen suele pedir aparte.

En Flashcards, las 4 se eligen todas por el mismo criterio: **lo que habría que
tener en la punta de la lengua para abrir una respuesta**. Definición del término
central, la enumeración que hay que recitar, la tesis con su autor, el criterio de
la distinción. Nada de frases célebres ni datos de color.

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
