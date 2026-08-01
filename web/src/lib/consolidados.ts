// Construye los cuatro consolidados de un libro (glosario, distinciones,
// autoevaluación, mazo) como HTML ya renderizado. Vive separado de
// `Consolidados.astro` porque el índice fijo de la izquierda (`IndiceLibro`)
// necesita la MISMA lista de qué consolidados tienen contenido —si los
// calculara por su cuenta, un descuadre entre los dos generaría un enlace del
// índice a un consolidado que no se dibujó, que es exactamente el tipo de
// bug silencioso que este taller ya sufrió una vez con las anclas.
import { inline, bloque } from "./md";

function chips(anclas: { ancla: string; numero: string }[], etiqueta: string): string {
  if (anclas.length < 2) return "";
  const items = anclas.map((a) => `<a href="#${a.ancla}">${a.numero}</a>`).join("");
  return `<nav class="indice-doc" aria-label="${etiqueta}">${items}</nav>`;
}

function glosarioHTML(libro: any): string {
  if (!libro.glosario.length) return "";
  const filas = libro.glosario.map((e: any) => {
    const caps = e.caps.map((n: string) => `<a class="cap" href="#s${n}">${n}</a>`).join("");
    return `<dt><span class="termino">${e.termino}</span>${caps}</dt><dd>${inline(e.definicion)}</dd>`;
  });
  return `<dl class="glosario">${filas.join("")}</dl>`;
}

// Se arma HTML a mano desde los `items` estructurados, en vez de pasar el
// markdown crudo por `bloque()`. El motivo es un bug real que también afecta
// al sitio en producción: el prompt separa cada par con una línea en blanco
// para que se pueda leer al escribirlo, y esa línea en blanco hace que
// CommonMark trate la lista como "loose" y envuelva cada ítem en un `<p>`
// (`<li><p><strong>…`). El CSS espera `li > strong` para pintar el acento del
// par, así que con esa envoltura el color nunca se aplicaba. Construir el HTML
// directo desde los campos ya parseados no depende de cómo haya quedado el
// espaciado del original.
function itemDistincion(it: any): string {
  return (
    `<li><strong>${inline(it.par)}</strong> — ${inline(it.texto)}` +
    `<ul>` +
    `<li>Se confunden porque: ${inline(it.se_confunden)}</li>` +
    `<li>Criterio para decidir: ${inline(it.criterio)}</li>` +
    `<li>Dónde se cae: ${inline(it.error)}</li>` +
    `</ul></li>`
  );
}

function distincionesHTML(libro: any): string {
  if (!libro.distinciones.length) return "";
  const anclas = libro.distinciones.map((d: any) => ({ ancla: `s${d.cap}`, numero: d.cap }));
  const partes = [chips(anclas, "Capítulos")];
  for (const d of libro.distinciones) {
    partes.push(
      `<h3 id="distinciones-s${d.cap}"><a href="#s${d.cap}">${d.cap}</a> ${d.titulo_cap}</h3>` +
        `<ul>${d.items.map(itemDistincion).join("")}</ul>`
    );
  }
  return partes.join("");
}

function autoevaluacionHTML(libro: any): string {
  if (!libro.autoevaluacion.length) return "";
  const anclas = libro.autoevaluacion.map((a: any) => ({ ancla: `s${a.cap}`, numero: a.cap }));
  const ayuda =
    '<p class="ayuda">Contestá primero. Al hacer clic en una pregunta aparece su respuesta debajo.</p>';
  const cuerpos = libro.autoevaluacion.map((a: any) => {
    const filas = a.preguntas
      .map(
        (p: any, i: number) =>
          `<details class="pregunta"><summary><span class="numero">${i + 1}</span>` +
          `<span class="texto">${inline(p.pregunta)}</span></summary>` +
          `<div class="respuesta">${bloque(p.respuesta)}</div></details>`
      )
      .join("");
    return (
      `<h3 id="autoevaluacion-s${a.cap}"><a href="#s${a.cap}">${a.cap}</a> ${a.titulo_cap}</h3>` +
      filas
    );
  });
  return ayuda + chips(anclas, "Capítulos") + cuerpos.join("");
}

function mazoHTML(libro: any): string {
  if (!libro.mazo.length) return "";
  const items = libro.mazo
    .map(
      (t: any) =>
        `<button class="tarjeta" type="button"><span class="pregunta">${inline(
          t.pregunta
        )}</span><span class="respuesta">${inline(t.respuesta)}</span>` +
        `<span class="origen">${t.cap}</span></button>`
    )
    .join("");
  return (
    `<p class="ayuda">${libro.mazo.length} tarjetas. Hacé clic para revelar la respuesta, ` +
    `o la tecla R para esconderlas todas.</p><div class="tarjetas">${items}</div>`
  );
}

export interface Consolidado {
  ancla: string;
  titulo: string;
  cuerpo: string;
}

export function construirConsolidados(libro: any): Consolidado[] {
  const definiciones: [string, string, string][] = [
    ["glosario", "Glosario del libro", glosarioHTML(libro)],
    ["distinciones", "Distinciones que se confunden", distincionesHTML(libro)],
    ["autoevaluacion", "Autoevaluación", autoevaluacionHTML(libro)],
    ["flashcards", "Flashcards", mazoHTML(libro)],
  ];
  return definiciones
    .filter(([, , cuerpo]) => cuerpo)
    .map(([ancla, titulo, cuerpo]) => ({ ancla, titulo, cuerpo }));
}
