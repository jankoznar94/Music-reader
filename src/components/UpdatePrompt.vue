<!-- UpdatePrompt.vue — hlášení „je k dispozici nová verze".

Proč: appka má v knihovně tlačítko „Aktualizovat“, ale uživatel nemá jak
poznat, že je vůbec co stahovat (Jan, listopad 2026: „teď je tam tlačítko na
ruční stažení, ale uživatel neví, že je něco nového k dispozici“).

Zdroj pravdy je `updateAvailable` z `src/update.js` — ten porovnává běžící
bundle s `index.html` na serveru (kontrola běží po startu, při návratu do
appky a každých 5 minut). Tady se z toho stavu jen ukáže okno; samo se nic
nenačítá ani neobnovuje — přepnutí dělá až tlačítko (`applyUpdate`).

Chování: „Později“ okno zavře a pro TUTÉŽ verzi už se neukáže (sessionStorage);
po restartu appky se připomene znovu. Nová verze = nové okno.
-->
<template>
  <div v-if="visible" class="up-root">
    <div class="up-box">
      <div class="up-title">Nová verze aplikace je k dispozici</div>
      <div class="up-text">Aktualizace přinese opravy a novinky. Appka se obnoví až po tvém klepnutí.</div>
      <div class="up-actions">
        <button class="up-btn primary" @click="onUpdate">Aktualizovat hned</button>
        <button class="up-btn" @click="onLater">Později</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { updateAvailable, updateHash, applyUpdate } from '../update';

const DISMISS_KEY = 'noty-update-dismissed';
const dismissed = ref(readDismissed());

function readDismissed() {
  try { return sessionStorage.getItem(DISMISS_KEY) || ''; }
  catch (e) { return ''; }
}

const visible = computed(() => updateAvailable.value && dismissed.value !== (updateHash.value || 'unknown'));

function onLater() {
  dismissed.value = updateHash.value || 'unknown';
  try { sessionStorage.setItem(DISMISS_KEY, dismissed.value); } catch (e) { /* privátní režim */ }
}

async function onUpdate() {
  try { sessionStorage.setItem('noty-updated', '1'); } catch (e) { /* nevadí */ }
  await applyUpdate();     // zahodí cache + SW a načte appku znovu (viz update.js)
}
</script>

<style scoped>
.up-root {
  position: fixed;
  top: calc(env(safe-area-inset-top, 0px) + 64px);
  left: 0; right: 0;
  display: flex;
  justify-content: center;
  z-index: 9800;                 /* nad obsahem, pod plovoucími panely nástrojů */
  pointer-events: none;          /* okno nesmí blokovat kreslení pod sebou */
}
.up-box {
  pointer-events: auto;
  width: min(92vw, 440px);
  box-sizing: border-box;
  background: var(--bg-elev);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px 18px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
}
.up-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 6px;
}
.up-text {
  font-size: 14px;
  line-height: 1.35;
  color: var(--text-dim);
  margin-bottom: 14px;
}
.up-actions { display: flex; flex-direction: column; gap: 8px; }
.up-btn {
  width: 100%;
  padding: 13px 14px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-elev2);
  color: var(--text);
  font-family: inherit;
}
.up-btn.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #17130f;
  font-weight: 700;
}
/* Žádné hover/focus efekty — mobilní PWA (Jan). */
.up-btn:focus { outline: none; }
</style>
