<template>
  <div class="app-root">
    <!-- Banner: dostupná aktualizace (ruční převzetí nové verze) -->
    <div v-if="needRefresh" class="update-banner">
      <span class="ub-text">Nová verze aplikace je dostupná.</span>
      <button class="ub-btn" @click="applyUpdate">Aktualizovat</button>
    </div>
    <router-view />
  </div>
</template>

<script setup>
import { registerSW } from 'virtual:pwa-register';

// Ruční aktualizace Service Workeru (registerType: 'prompt'):
// - nová verze se stáhne na pozadí, ale NEaktivuje se sama
// - zobrazí se banner "Nová verze je dostupná" → uživatel klikne Aktualizovat
// - po kliknutí se pošle SKIP_WAITING, SW převezme kontrolu a stránka se obnoví
const { needRefresh, updateSW } = registerSW({
  immediate: true,
  onNeedRefresh() {
    needRefresh.value = true;
  },
  onOfflineReady() {
    console.log('Noty App připravena pro offline použití.');
  },
  onRegisteredSW(_swUrl, registration) {
    if (!registration) return;
    // Periodická kontrola nové verze na pozadí (každých 30 min)
    setInterval(() => {
      registration.update().catch((err) => console.warn('Kontrola aktualizace SW selhala', err));
    }, 30 * 60 * 1000);
  },
});

function applyUpdate() {
  if (updateSW) updateSW(true); // true = skipWaiting → okamžité převzetí + reload
}
</script>

<style scoped>
.app-root { flex: 1; display: flex; flex-direction: column; min-height: 0; }

/* Banner aktualizace — plochý, teplé tmavé barvy, bez glow (Janův astigmatismus) */
.update-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg-elev);
  border-bottom: 1px solid var(--border);
}
.ub-text { color: var(--text); font-size: 0.95rem; }
.ub-btn {
  background: var(--accent);
  color: #17130f;
  border: none;
  font-weight: 600;
  padding: 10px 16px;
  border-radius: 10px;
  white-space: nowrap;
}
.ub-btn:active { background: var(--accent-dim); }
</style>
