// src/update.js — ZJIŠTĚNÍ nové verze. Nic samo nenačítá.
// Jan: „Teď se appka sama obnoví přímo pod rukami a to se nesmí dít.
// Aktualizace budou jen na tlačítko.“ Proto se tu jen zjistí, že je na
// serveru jiný JS bundle, a rozsvítí se tlačítko; přepnutí dělá až `applyUpdate`.
import { ref } from 'vue';

const BOOT_JS = (document.querySelector('script[type="module"]') || {}).src || '';
export const updateAvailable = ref(false);
export let updateHash = '';
let checking = false;

/** Porovná běžící bundle s tím na serveru (obchází SW i HTTP cache). */
export async function checkForUpdate() {
  if (checking || !BOOT_JS) return false;
  checking = true;
  try {
    const res = await fetch('/index.html?ts=' + Date.now(), { cache: 'no-store' });
    if (!res.ok) { window.__updateState = 'error'; return false; }
    const html = await res.text();
    const m = html.match(/assets\/index-[A-Za-z0-9_-]+\.js/);
    if (!m || BOOT_JS.includes(m[0])) {
      updateAvailable.value = false;
      window.__updateState = 'same';
      return false;
    }
    updateHash = m[0];
    updateAvailable.value = true;
    window.__updateState = 'available:' + updateHash;
    return true;
  } catch (e) {
    window.__updateState = 'error';
    return false;
  } finally {
    checking = false;
  }
}

/** Tlačítko „Aktualizovat“: zahodí cache i SW a načte appku znovu. */
export async function applyUpdate() {
  updateAvailable.value = false;
  try {
    if ('caches' in window) {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    }
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map((r) => r.unregister()));
    }
  } catch (e) { /* i tak reload */ }
  window.location.reload();
}
