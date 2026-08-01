// Los tres encabezados que quedan visibles dentro de un capítulo son siempre
// los mismos tres textos ("Idea principal", "Lo esencial del capítulo",
// "Mapa"), así que sus anclas son estáticas y no hace falta reimplementar
// `sitio.py: anclar()` para calcularlas dinámicamente. Si algún día alguno de
// estos títulos cambia, hay que actualizar esta lista — quedaría con un
// desacople silencioso si no.
export const ANCLA_IDEA = "idea-principal";
export const ANCLA_ESENCIAL = "lo-esencial-del-capitulo";
export const ANCLA_MAPA = "mapa";
