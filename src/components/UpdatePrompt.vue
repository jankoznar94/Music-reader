<!-- UpdatePrompt.vue — hlášení „je k dispozici nová verze".

Proč: appka má v knihovně tlačítko „Aktualizovat“, ale uživatel nemá jak
poznat, že je vůbec co stahovat (Jan, listopad 2026: „teď je tam tlačítko na
ruční stažení, ale uživatel neví, že je něco nového k dispozici“).

Zdroj pravdy je `updateAvailable` z `src/update.js` — ten porovnává běžící
bundle s `index.html` na serveru (kontrola běží po startu, při návratu do
appky a každých 5 minut). Tady se z toho stavu jen ukáže okno; samo se nic
nenačítá ani neobnovuje — přepnutí dělá až tlačítko (`applyUpdate`).

Vzhled (Jan, listopad 2026): okno je UPROSTŘED obrazovky, s výraznou teplou
plochou, a zbytek appky je ZATMAVENÝ a neklikatelný, dokud ho uživatel
neodklikne („Aktualizovat hned“ / „Později“).

Chování: „Později“ okno zavře a pro TUTÉŽ verzi už se neukáže (sessionStorage);
po restartu appky se připomene znovu. Nová verze = nové okno.
-->
<template>
  <div v-if="visible" class="up-root">
    <!-- Zatmavení a uzamčení zbytku appky: dokud uživatel neodpoví, nic pod
         oknem nejde zmáčknout (jinak by šlo omylem kreslit do not). -->
    <div class="up-scrim" />
    <div class="up-box">
      <div class="up-title">Nová verze aplikace</div>
      <div class="up-text">Je k dispozici aktualizace s opravami a novinkami. Appka se obnoví až po tvém klepnutí.</div>
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
  inset: 0;
  display: flex;
  align-items: center;         /* PŘESNÝ STŘED obrazovky */
  justify-content: center;
  padding: 16px;
  box-sizing: border-box;
  z-index: 9800;               /* nad obsahem i plovoucími panely nástrojů */
}
.up-scrim {
  position: absolute;
  inset: 0;
  background: rgba(10, 8, 7, 0.72);   /* zbytek appky ztmavený a neklikatelný */
}
.up-box {
  position: relative;
  width: min(92vw, 460px);
  box-sizing: border-box;
  background: var(--accent);          /* výrazná teplá plocha, ne šedá karta */
  color: #1c1410;
  border: 2px solid #e2c69c;
  border-radius: 18px;
  padding: 22px 20px 20px;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.55);
  text-align: center;
}
.up-title {
  font-size: 22px;
  line-height: 1.2;
  font-weight: 800;
  color: #1c1410;
  margin-bottom: 8px;
}
.up-text {
  font-size: 15px;
  line-height: 1.4;
  color: #3a2c1e;
  margin-bottom: 18px;
}
.up-actions { display: flex; flex-direction: column; gap: 10px; }
.up-btn {
  width: 100%;
  padding: 16px 14px;
  font-size: 17px;
  font-weight: 700;
  border-radius: 12px;
  border: 2px solid #1c1410;
  background: transparent;
  color: #1c1410;
  font-family: inherit;
}
.up-btn.primary {
  background: #1c1410;
  border-color: #1c1410;
  color: var(--accent);
}
/* Žádné hover/focus efekty — mobilní PWA (Jan). */
.up-btn:focus { outline: none; }
</style>
