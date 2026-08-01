// Único punto de renderizado de markdown inline en el sitio: negrita, cursiva,
// comillas tipográficas y links. El JSON de datos guarda el texto tal como lo
// escribió el prompt (con `**bold**` y comillas rectas); esto lo convierte a
// HTML recién al momento de mostrarlo, nunca al momento de leer los datos.
import MarkdownIt from "markdown-it";

const md = new MarkdownIt("commonmark", { html: false, linkify: true }).enable([
  "table",
  "strikethrough",
]);

/** Renderiza un fragmento corto (una oración, una definición) sin envolverlo en `<p>`. */
export function inline(texto: string): string {
  return texto ? md.renderInline(texto) : "";
}

/** Renderiza un bloque que puede tener varios párrafos. */
export function bloque(texto: string): string {
  return texto ? md.render(texto) : "";
}
