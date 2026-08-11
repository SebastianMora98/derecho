// Un documento de sección se sirve desde dos rutas distintas según cuántos
// tenga su sección, y tres páginas —el índice, la hoja de la sección y la del
// documento— necesitan coincidir en cuál es. Esa regla vive acá y no copiada en
// cada `.astro`, porque si se separan las URLs dejan de cerrar entre sí.

export interface Documento {
  slug: string;
  archivo: string;
  titulo: string;
  bajada: string;
  enlace: string;
  oculto: boolean;
  palabras: number;
  texto: string;
}

export interface Grupo {
  nombre: string;
  slug: string;
  orden: number | null;
  documentos: Documento[];
}

/** Con un solo documento la sección no necesita hoja de elección: la URL de la
 *  sección es directamente la del documento. Es lo que mantiene
 *  `/resena/civil-personas/` donde estaba desde antes de que una sección
 *  pudiera tener varios. */
export function ruta(grupo: Grupo, doc: Documento): string {
  return grupo.documentos.length > 1
    ? `/resena/${grupo.slug}/${doc.slug}/index.html`
    : `/resena/${grupo.slug}/index.html`;
}

/** No siempre es una reseña —puede ser un taller resuelto o una guía para un
 *  debate—, así que el título sale de `grupos.toml` cuando está declarado. */
export function titulo(grupo: Grupo, doc: Documento): string {
  return doc.titulo || `Reseña de ${grupo.nombre}`;
}

export function bajada(grupo: Grupo, doc: Documento, lecturas: number): string {
  return (
    doc.bajada ||
    `Un solo texto sobre las ${lecturas} lecturas de esta clase, leídas juntas.`
  );
}

/** El texto del enlace del índice, debajo de las tarjetas de la sección. */
export function enlace(grupo: Grupo, doc: Documento, lecturas: number): string {
  return (
    doc.enlace ||
    `Reseña conjunta de ${
      lecturas === 2 ? "las dos lecturas" : `las ${lecturas} lecturas`
    } de ${grupo.nombre}`
  );
}

/** Los libros de una sección, en el mismo orden en que los muestra el índice. */
export function librosDe(libros: any[], grupo: { nombre: string }): any[] {
  return libros
    .filter((l) => (l.grupo || "").trim() === grupo.nombre)
    .sort((a, b) => a.slug.localeCompare(b.slug));
}

/** La sección lleva el atributo del atajo si tiene *algún* documento oculto: es
 *  lo único que delata que ahí hay algo, y con varios documentos la hoja de
 *  elección decide después cuál se abre. */
export function hayOcultos(grupo: Grupo | null | undefined): boolean {
  return !!grupo && (grupo.documentos ?? []).some((d) => d.oculto);
}

/** El índice enlaza cada documento anunciado por separado, no la hoja de la
 *  sección: si esa hoja es la de elección, listaría también los ocultos. */
export function anunciados(grupo: Grupo | null | undefined): Documento[] {
  return (grupo?.documentos ?? []).filter((d) => !d.oculto);
}
