import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import './style.css';
import { resetLibraryState } from './libraryState';

// Při každém (re)startu appky vynulovat stav přehledu not.
// SPA přechod do PDF prohlížeče a zpět stav NEMAŽE (module žije po dobu běhu).
resetLibraryState();

// --- Aktualizace na novou verzi ---------------------------------------------
// Po nasazení se nový service worker hned ujme kontroly (skipWaiting) a
// stránka se jednou znovu načte. Bez toho appka běžela ze staré cache a
// uživatel viděl staré chování, i když byla na serveru nová verze.
if ('serviceWorker' in navigator) {
  let reloading = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloading) return;
    reloading = true;
    window.location.reload();
  });
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw-v2.js').then((reg) => {
      const check = () => reg.update().catch(() => {});
      // Pravidelná kontrola + hned po návratu do appky.
      setInterval(check, 5 * 60 * 1000);
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden) check();
      });
    }).catch(() => {});
  });
}

createApp(App).use(router).mount('#app');
