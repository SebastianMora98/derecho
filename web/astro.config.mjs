import { defineConfig } from 'astro/config';

// Sin framework de UI: el sitio es HTML + CSS + un script vanilla, igual que
// la versión que generaba sitio.py. Astro aporta solo el ruteo de páginas y
// la lectura de datos en build time; no hay hidratación ni JS de cliente
// más allá de estaticos/tarjetas.js.
export default defineConfig({
  outDir: '../sitio',
  build: { format: 'directory' },
});
