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

// Índice del documento: marca en qué bloque estoy. Un índice fijo que no dice
// dónde estás sirve la mitad, sobre todo en la explicación paso a paso, que es
// larga y ocupa varias pantallas.
(() => {
  const enlaces = new Map();
  document.querySelectorAll(".indice-doc a[href^='#']").forEach((a) => {
    const destino = document.getElementById(decodeURIComponent(a.hash.slice(1)));
    if (destino) enlaces.set(destino, a);
  });
  if (!enlaces.size) return;

  // Se calcula por posición y no con IntersectionObserver: el observador solo
  // reacciona a lo que cruza una franja, así que ante un salto instantáneo
  // —que es justo lo que hace un clic en este índice— ningún encabezado la
  // atraviesa y la marca queda vieja.
  const destinos = [...enlaces.keys()];
  const LIMITE = 96; // un poco por debajo de la barra fija

  const marcar = () => {
    let actual = destinos[0];
    for (const destino of destinos) {
      if (destino.getBoundingClientRect().top > LIMITE) break;
      actual = destino;
    }
    enlaces.forEach((a, destino) => {
      if (destino === actual) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    });
  };

  let pendiente = false;
  const alScrollear = () => {
    if (pendiente) return;
    pendiente = true;
    requestAnimationFrame(() => {
      pendiente = false;
      marcar();
    });
  };

  addEventListener("scroll", alScrollear, { passive: true });
  addEventListener("resize", alScrollear);
  addEventListener("hashchange", alScrollear);
  marcar();
})();
