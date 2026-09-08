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
// - pokud je nová verze, pošle SKIP_WAITING přímo novému workeru a stránka se
//   obnoví SAMA (controllerchange listener → reload), bez vypínání/zapínání appky
const checking = ref(false);
let registration = null;
let refreshing = false; // prevence vícenásobného reloadu

const { updateSW } = registerSW({
  immediate: true,
  onOfflineReady() {
    console.log('Noty App připravena pro offline použití.');
  },
  onRegisteredSW(_swUrl, reg) {
    registration = reg;
  },
});

// Robustní obnova po aktivaci nového SW — funguje i v standalone PWA režimu.
// Registrujeme listener PŘED odesláním SKIP_WAITING (jako v CFSB).
function setupReloadOnActivate() {
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (refreshing) return;
    refreshing = true;
    window.location.reload();
  });
}

// Počká, dokud se nový worker nedostane do stavu 'installed' (připraven k aktivaci)
function waitForInstalled(worker) {
  return new Promise((resolve) => {
    if (worker.state === 'installed') return resolve();
    worker.addEventListener('statechange', () => {
      if (worker.state === 'installed') resolve();
    });
  });
}

async function checkAndApply() {
  if (checking.value) return;
  checking.value = true;
  try {
    if (!registration) return;
    // 1. Vynutit kontrolu nové verze
    await registration.update();
    // 2. Najít nový worker (waiting = už stažený, installing = právě se stahuje)
    let newWorker = registration.waiting || registration.installing;
    if (!newWorker) {
      console.log('Aplikace je aktuální.');
      return;
    }
    // 3. Pokud se právě instaluje, počkat na dokončení
    if (newWorker.state === 'installing') {
      await waitForInstalled(newWorker);
    }
    // 4. Aktivovat: poslat SKIP_WAITING přímo novému workeru
    setupReloadOnActivate();
    newWorker.postMessage({ type: 'SKIP_WAITING' });
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
