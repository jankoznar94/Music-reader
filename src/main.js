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
      check();                       // hned při startu, ne až za 5 minut
      setInterval(check, 5 * 60 * 1000);
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden) check();
      });
    }).catch(() => {});
  });
}

// --- TVRDÁ KONTROLA VERZE (nezávislá na service workeru i HTTP cache) -------
// Service worker umí držet starý index.html ve precache, takže se nová verze
// někdy vůbec nestáhne (Jan: „žádná aktualizace se nestahuje“). Proto se
// index.html stáhne s unikátním parametrem a `no-store` (parametr precache
// nezná → jde to opravdu ze sítě), porovná se hash JS bundlu s tím, který
// právě běží, a při rozdílu se zahodí cache i SW a stránka se načte znovu.
const BOOT_JS = (document.querySelector('script[type="module"]') || {}).src || '';
async function checkForUpdate() {
  try {
    if (!BOOT_JS) return;
    const res = await fetch('/index.html?ts=' + Date.now(), { cache: 'no-store' });
    if (!res.ok) return;
    const html = await res.text();
    const m = html.match(/assets\/index-[A-Za-z0-9_-]+\.js/);
    if (!m || BOOT_JS.includes(m[0])) { window.__updateState = 'same'; return; }
    const hash = m[0];
    // Pojistka proti smyčce: každou verzi zkusit vynutit jen jednou.
    if (sessionStorage.getItem('forcedUpdate') === hash) {
      window.__updateState = 'blocked:' + hash;
      return;
    }
    sessionStorage.setItem('forcedUpdate', hash);
    window.__updateState = 'updating:' + hash;
    if ('caches' in window) {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    }
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map((r) => r.unregister()));
    }
    window.location.reload();
  } catch (e) {
    window.__updateState = 'error';
  }
}
window.__checkUpdate = checkForUpdate;   // ruční/ diagnostická kontrola verze
window.addEventListener('load', () => {
  setTimeout(checkForUpdate, 1200);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) checkForUpdate();
  });
});
setInterval(checkForUpdate, 5 * 60 * 1000);


createApp(App).use(router).mount('#app');
