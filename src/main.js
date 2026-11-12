import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import './style.css';
import { resetLibraryState } from './libraryState';
import { checkForUpdate } from './update';
import { runPresentationMigrations } from './presentation';

// Při každém (re)startu appky vynulovat stav přehledu not.
// SPA přechod do PDF prohlížeče a zpět stav NEMAŽE (module žije po dobu běhu).
resetLibraryState();

// --- Service worker ---------------------------------------------------------
// Jen offline cache. ŽÁDNÉ automatické přebírání kontroly a ŽÁDNÝ reload:
// nová verze se nasadí výhradně tlačítkem „Aktualizovat“ (Jan: „appka se sama
// obnoví přímo pod rukami a to se nesmí dít“). Proto se tu ani nevolá
// reg.update() — nový SW by se instaloval pod běžící stránkou.
if ('serviceWorker' in navigator) {
  if (import.meta.env.DEV) {
    // Ve vývoji SW NEREGISTROVAT a starý rovnou odhlásit — jinak dev server
    // servíruje starý bundle ze sw-v2.js a testy měří jinou verzi, než jakou
    // má uživatel (naměřeno: str. 9 vracela 5 taktů místo 4).
    navigator.serviceWorker.getRegistrations()
      .then((rs) => rs.forEach((r) => r.unregister()))
      .catch(() => {});
  } else {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw-v2.js').catch(() => {});
    });
  }
}

// --- ZJIŠTĚNÍ nové verze (nic nenačítá) -------------------------------------
// Porovná běžící bundle s index.html na serveru; když se liší, rozsvítí se
// tlačítko. Kontrola je jen čtení, takže může běžet i periodicky.
window.__checkUpdate = checkForUpdate;
window.addEventListener('load', () => {
  setTimeout(checkForUpdate, 1500);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) checkForUpdate();
  });
});
setInterval(checkForUpdate, 5 * 60 * 1000);

// --- Vzhled: jednorázové migrace PŘED mountem -------------------------------
// Musí doběhnout dřív, než se vykreslí knihovna i prohlížeč — jinak by se
// skladba mohla otevřít ve vzhledu, který uživatel nikdy neviděl.
(async () => {
  try { await runPresentationMigrations(); }
  catch (e) { console.warn('[vzhled] migrace přeskočena', e); }
  createApp(App).use(router).mount('#app');
})();
