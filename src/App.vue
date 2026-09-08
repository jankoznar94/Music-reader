<template>
  <div class="app-root">
    <router-view />
    <!-- Trvalé tlačítko aktualizace — na kliknutí zkontroluje nový SW a případně nasadí -->
    <button class="update-fab" @click="checkAndApply" title="Zkontrolovat novou verzi aplikace">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/></svg>
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { registerSW } from 'virtual:pwa-register';

// Trvalé tlačítko aktualizace (registerType: 'prompt'):
// - tlačítko je vidět pořád (pravý dolní roh)
// - na kliknutí zavolá registration.update() → prohlížeč zkontroluje nový SW
// - pokud je nová verze, pošle SKIP_WAITING a stránka se obnoví
const checking = ref(false);
let registration = null;
let updateSW = null;

const { updateSW: us } = registerSW({
  immediate: true,
  onOfflineReady() {
    console.log('Noty App připravena pro offline použití.');
  },
  onRegisteredSW(_swUrl, reg) {
    registration = reg;
  },
});
updateSW = us;

async function checkAndApply() {
  if (checking.value) return;
  checking.value = true;
  try {
    // 1. Vynutit kontrolu nové verze
    if (registration) await registration.update();
    // 2. Pokud je nová verze připravená (waiting), aplikovat ji
    if (registration && registration.waiting) {
      updateSW(true); // skipWaiting → okamžité převzetí + reload
      return;
    }
    // 3. Pokud se právě instaluje, počkat na dokončení a pak aplikovat
    if (registration && registration.installing) {
      const w = registration.installing;
      w.addEventListener('statechange', () => {
        if (w.state === 'installed' && navigator.serviceWorker.controller) {
          updateSW(true);
        }
      });
      return;
    }
    // 4. Žádná nová verze
    console.log('Aplikace je aktuální.');
  } catch (err) {
    console.warn('Kontrola aktualizace selhala', err);
  } finally {
    checking.value = false;
  }
}
</script>

<style scoped>
.app-root { flex: 1; display: flex; flex-direction: column; min-height: 0; }

/* Trvalé tlačítko aktualizace — ploché, teplé tmavé barvy, bez glow (Janův astigmatismus) */
.update-fab {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 100;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-elev2);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 0;
}
.update-fab:active { background: var(--bg-elev); }
</style>
