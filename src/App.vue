<template>
  <div>
    <router-view />

    <!-- Banner: je dostupná nová verze appky -->
    <div v-if="needRefresh" class="update-banner">
      <div class="update-card">
        <div class="ub-text">Je dostupná nová verze appky.</div>
        <div class="ub-actions">
          <button class="ub-btn primary" @click="doUpdate">Obnovit</button>
          <button class="ub-btn ghost" @click="dismissUpdate">Později</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { registerSW } from 'virtual:pwa-register';

const needRefresh = ref(false);

const { updateSW } = registerSW({
  immediate: true,
  onNeedRefresh() {
    needRefresh.value = true;
  },
  onOfflineReady() {
    console.log('Noty App připravena pro offline použití.');
  },
  onRegisteredSW(_swUrl, registration) {
    if (!registration) return;
    // Pozadová kontrola nové verze každých 30 min — banner se ukáže, jakmile vyjde nová verze
    setInterval(() => {
      registration.update().catch((err) => console.warn('Kontrola aktualizace SW selhala', err));
    }, 30 * 60 * 1000);
  },
});

function doUpdate() {
  try {
    if (typeof updateSW === 'function') {
      // updateSW(true) = skipWaiting + reload — SW má SKIP_WAITING handler, takže funguje
      updateSW(true);
    } else {
      location.reload();
    }
  } catch (err) {
    console.warn('SW update selhal, obnovuji ručně', err);
    location.reload();
  }
}

function dismissUpdate() {
  needRefresh.value = false;
}
</script>

<style scoped>
.update-banner {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 20px;
  box-sizing: border-box;
}
.update-card {
  background: var(--bg-elev, #17130f);
  border: 1px solid var(--border, #444);
  border-radius: 16px;
  padding: 18px 20px;
  max-width: 420px;
  width: 100%;
  box-sizing: border-box;
}
.ub-text {
  text-align: center;
  font-weight: 600;
  margin-bottom: 14px;
}
.ub-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}
.ub-btn {
  padding: 10px 0;
  width: 120px;
  border: none;
  border-radius: 10px;
  font-weight: 600;
  cursor: pointer;
  font-size: 1rem;
}
.ub-btn.primary {
  background: var(--accent, #e5d7a6);
  color: #17130f;
}
.ub-btn.ghost {
  background: transparent;
  color: var(--text, #eee);
  border: 1px solid var(--border, #444);
}
</style>
