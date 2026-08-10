// --------------------------------------------------------------------------- //
// tema claro / oscuro
// --------------------------------------------------------------------------- //

// El `<head>` ya puso `data-tema` si había preferencia guardada, así que acá no
// hay que tocar nada al cargar: solo atender el botón. Sin atributo manda el
// sistema, que es el estado por defecto y también al que se vuelve.
function temaOscuroActivo() {
  const fijado = document.documentElement.dataset.tema;
  if (fijado === "oscuro") return true;
  if (fijado === "claro") return false;
  return matchMedia("(prefers-color-scheme: dark)").matches;
}

const botonTema = document.querySelector(".tema");
if (botonTema) {
  botonTema.addEventListener("click", () => {
    const oscuro = !temaOscuroActivo();
    document.documentElement.dataset.tema = oscuro ? "oscuro" : "claro";
    try {
      localStorage.setItem("tema", oscuro ? "oscuro" : "claro");
    } catch (e) {}
    redibujarMermaid();
  });
}

// Si el usuario nunca eligió, el sitio sigue al sistema en vivo: cambiar el
// tema del SO con la página abierta también tiene que redibujar los diagramas.
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (!document.documentElement.dataset.tema) redibujarMermaid();
});

// Flashcards: clic para revelar, y la tecla "r" para esconderlas todas de nuevo.
document.addEventListener("click", (evento) => {
  const tarjeta = evento.target.closest(".tarjeta");
  if (tarjeta) tarjeta.classList.toggle("abierta");
});

document.addEventListener("keydown", (evento) => {
  if (evento.key === "r" && !evento.metaKey && !evento.ctrlKey) {
    document.querySelectorAll(".tarjeta.abierta").forEach((t) => t.classList.remove("abierta"));
  }
});

// --------------------------------------------------------------------------- //
// capítulos plegables
// --------------------------------------------------------------------------- //

// Capítulos y consolidados: los dos se recuerdan y los dos los abre el botón.
const plegables = () => [...document.querySelectorAll("details.capitulo, details.consolidado")];
const CLAVE_ABIERTOS = "abiertos:" + location.pathname;

// Se recuerda qué capítulos quedaron abiertos: volver y encontrarse la pared de
// todos cerrados es justo la fricción que la hoja única viene a sacar.
// En file:// el origen es opaco y localStorage puede tirar, de ahí el try.
function guardarAbiertos() {
  try {
    const ids = plegables().filter((d) => d.open).map((d) => d.id);
    if (ids.length) localStorage.setItem(CLAVE_ABIERTOS, ids.join(" "));
    else localStorage.removeItem(CLAVE_ABIERTOS);
  } catch {}
}

function restaurarAbiertos() {
  let ids = [];
  try {
    ids = (localStorage.getItem(CLAVE_ABIERTOS) || "").split(" ").filter(Boolean);
  } catch {}
  // Abrir no dibuja los diagramas: eso lo decide la visibilidad, más abajo. Así
  // restaurar diez capítulos no dispara diez renders de Mermaid.
  ids.forEach((id) => {
    const d = document.getElementById(id);
    if (d) d.open = true;
  });
}

// Un enlace compartido tiene que abrir lo que apunta, y puede apuntar adentro de
// dos <details> anidados: #s04-flashcards vive dentro de details#s04.
function abrirCadena(nodo) {
  let d = nodo.closest("details");
  while (d) {
    d.open = true;
    d = d.parentElement && d.parentElement.closest("details");
  }
}

function irAlAncla() {
  const id = decodeURIComponent(location.hash.slice(1));
  if (!id) return;
  const destino = document.getElementById(id);
  if (!destino) return;
  abrirCadena(destino);
  // Abrir movió todo: el scroll que ya hizo el navegador quedó viejo.
  requestAnimationFrame(() => destino.scrollIntoView({ block: "start" }));
}

const alternarTodo = document.querySelector(".alternar-todo");
if (alternarTodo) {
  // Con todo abierto, Cmd-F recorre el libro entero: el navegador no busca
  // dentro de un <details> cerrado, así que este botón convierte el costo de
  // plegar en una capacidad que el sitio no tenía. Tiene que abrir también los
  // consolidados, o Cmd-F no encuentra un término que solo está en el glosario.
  alternarTodo.addEventListener("click", () => {
    const abrir = alternarTodo.getAttribute("aria-expanded") !== "true";
    plegables().forEach((d) => { d.open = abrir; });
    alternarTodo.setAttribute("aria-expanded", String(abrir));
    alternarTodo.textContent = abrir ? "Cerrar todo el libro" : "Abrir todo el libro";
  });
}

// --------------------------------------------------------------------------- //
// Mermaid, solo cuando el diagrama se ve
// --------------------------------------------------------------------------- //

const MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
let mermaidCargado = null;

function configurarMermaid(mermaid) {
  mermaid.initialize({
    startOnLoad: false,
    theme: temaOscuroActivo() ? "dark" : "neutral",
    themeVariables: { fontSize: "15px", fontFamily: "ui-sans-serif, system-ui, sans-serif" },
    flowchart: { curve: "basis", useMaxWidth: true, nodeSpacing: 45, rankSpacing: 55 },
  });
  return mermaid;
}

function cargarMermaid() {
  if (!mermaidCargado) {
    mermaidCargado = import(MERMAID_CDN).then(({ default: mermaid }) => configurarMermaid(mermaid));
  }
  return mermaidCargado;
}

// Arrancar los diagramas de todos los capítulos al cargar es inaceptable, y uno
// dentro de un <details> cerrado mide cero de ancho, así que Mermaid lo
// calcularía mal. El observador resuelve las dos cosas de una: un elemento en
// display:none nunca intersecta, y cuando el capítulo se abre avisa recién ahí,
// con el ancho real ya calculado.
const enEspera = new IntersectionObserver(
  (entradas) => {
    const nodos = [];
    for (const e of entradas) {
      if (!e.isIntersecting) continue;
      enEspera.unobserve(e.target);
      if (e.target.dataset.processed) continue;
      // Mermaid reemplaza el contenido del <pre> por el SVG, así que el código
      // fuente se pierde. Se guarda antes para poder volver a dibujar el
      // diagrama cuando cambia el tema.
      if (e.target.dataset.fuente === undefined) e.target.dataset.fuente = e.target.textContent;
      nodos.push(e.target);
    }
    if (!nodos.length) return;
    cargarMermaid()
      .then((mermaid) => mermaid.run({ nodes: nodos }))
      // No se suprimen los errores: un diagrama que no compila tiene que dejar
      // rastro en consola en vez de un recuadro vacío y mudo.
      .catch((err) => console.error("Mermaid:", err));
  },
  { rootMargin: "300px" },
);

document.querySelectorAll("pre.mermaid").forEach((n) => enEspera.observe(n));

// Al cambiar de tema, los diagramas ya dibujados quedan con los colores del
// tema anterior —texto claro sobre fondo claro, ilegible—, así que hay que
// rehacerlos desde el código que se guardó en `data-fuente`. Los que todavía
// no se dibujaron no se tocan: los va a tomar el observador con el tema nuevo.
function redibujarMermaid() {
  if (!mermaidCargado) return;
  const nodos = [...document.querySelectorAll("pre.mermaid[data-processed]")];
  if (!nodos.length) return;
  for (const n of nodos) {
    n.textContent = n.dataset.fuente;
    delete n.dataset.processed;
    n.removeAttribute("data-processed");
  }
  mermaidCargado
    .then((mermaid) => configurarMermaid(mermaid).run({ nodes: nodos }))
    .catch((err) => console.error("Mermaid:", err));
}

// --------------------------------------------------------------------------- //
// marcador de posición en el índice del libro
// --------------------------------------------------------------------------- //

// Se calcula por posición y no con IntersectionObserver: el observador solo
// reacciona a lo que cruza una franja, así que ante un salto instantáneo —que es
// justo lo que hace un clic en el índice— ningún destino la atraviesa y la marca
// queda vieja.
function marcador(nav) {
  const enlaces = new Map();
  nav.querySelectorAll("a[href^='#']").forEach((a) => {
    const destino = document.getElementById(decodeURIComponent(a.hash.slice(1)));
    if (destino) enlaces.set(destino, a);
  });
  if (!enlaces.size) return null;

  const destinos = [...enlaces.keys()];
  const LIMITE = 96; // un poco por debajo de la barra fija

  return () => {
    let actual = null;
    for (const destino of destinos) {
      // offsetParent nulo = está dentro de un <details> cerrado. Su rect es todo
      // ceros, y sin esta guarda `0 <= LIMITE` se leería como "estoy justo acá"
      // y la marca se pegaría al último capítulo oculto.
      if (!destino.offsetParent) continue;
      if (destino.getBoundingClientRect().top > LIMITE) break;
      actual = destino;
    }
    if (!actual) actual = destinos.find((d) => d.offsetParent) || null;
    enlaces.forEach((a, destino) => {
      if (destino === actual) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    });
  };
}

// Solo el índice del libro y el de un documento suelto llevan marca. Los chips
// de dentro de un capítulo no: leer el rect de sus encabezados en cada frame de
// scroll forzaría el layout de los subárboles que `content-visibility` acaba de
// saltear, justo en el caso peor (varios capítulos abiertos).
const marcas = [...document.querySelectorAll(".indice-libro, main > .indice-doc")]
  .map(marcador)
  .filter(Boolean);
const marcarTodos = () => marcas.forEach((f) => f());

let pendiente = false;
const alScrollear = () => {
  if (pendiente) return;
  pendiente = true;
  requestAnimationFrame(() => {
    pendiente = false;
    marcarTodos();
  });
};

addEventListener("scroll", alScrollear, { passive: true });
addEventListener("resize", alScrollear);
addEventListener("hashchange", irAlAncla);
addEventListener("hashchange", alScrollear);
// `toggle` no burbujea: hay que escucharlo en fase de captura.
document.addEventListener(
  "toggle",
  (e) => {
    const c = e.target.classList;
    if (c && (c.contains("capitulo") || c.contains("consolidado"))) guardarAbiertos();
    alScrollear(); // abrir un capítulo movió todas las posiciones
  },
  true,
);

restaurarAbiertos();
irAlAncla();
marcarTodos();

/* ---------- acceso por diez clics a una reseña oculta ----------

   Una sección del índice puede tener su documento publicado pero sin enlace
   (`resena_oculta = true` en grupos.toml). La hoja existe y se puede abrir por
   su URL; desde el sitio se llega haciendo diez clics sobre el título de la
   sección, que es lo único que la delata.

   El contador se reinicia si pasan más de dos segundos entre dos clics, para
   que un clic suelto al pasar no vaya sumando durante toda la visita. */
document.querySelectorAll("h2.grupo[data-resena-oculta]").forEach((titulo) => {
  const destino = `/resena/${titulo.dataset.resenaOculta}/index.html`;
  let clics = 0;
  let reloj = null;
  titulo.addEventListener("click", () => {
    clearTimeout(reloj);
    clics += 1;
    if (clics >= 10) {
      location.href = destino;
      return;
    }
    // A partir de la mitad se avisa con un parpadeo, para que quien ya sabe
    // del atajo note que va contando y no lo dé por roto.
    if (clics >= 5) {
      titulo.style.opacity = "0.45";
      setTimeout(() => (titulo.style.opacity = ""), 120);
    }
    reloj = setTimeout(() => (clics = 0), 2000);
  });
});
