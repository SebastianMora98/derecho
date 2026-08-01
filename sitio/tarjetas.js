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
