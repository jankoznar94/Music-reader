<template>
  <div>
    <router-view />

    <!-- Banner: je dostupná nová verze appky -->
    <div v-if="needRefresh" class="update-banner">
      <span>Je dostupná nová verze. Obnovit pro použití?</span>
      <div class="ub-actions">
        <button class="ub-btn" @click="doUpdate">Obnovit</button>
        <button class="ub-btn ghost" @click="dismissUpdate">Později</button>
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
});

function doUpdate() {
  if (updateSW) updateSW(true);
  else location.reload();
}

function dismissUpdate() {
  needRefresh.value = false;
}
</script>

<style scoped>
.update-banner {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 100;
  padding: 20px;
  box-sizing: border-box;
}
.update-banner > span {
  display: block;
  background: var(--bg-elev, #17130f);
  border: 1px solid var(--border, #333);
  border-radius: 14px;
  padding: 14px 24px;
  text-align: center;
  font-weight: 600;
  max-width: 420px;
  width: 100%;
}
.ub-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}
.ub-btn {
  background: var(--accent, #e5d7a6);
  color: #17130f;
  border: none;
  border-radius: 10px;
  padding: 10px 20px;
  font-weight: 600;
}
.ub-btn.ghost {
  background: transparent;
  color: var(--text), #eee;
  border: 1px solid var(--border, #333);
}
</style>
