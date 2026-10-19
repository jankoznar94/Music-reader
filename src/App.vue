<template>
  <router-view />
  <!-- Aktualizace jen na tlačítko (Jan) — objeví se, až když je na serveru
       jiná verze; appka se sama nikdy nenačítá. -->
  <button v-if="updateAvailable" class="update-pill" @click="applyUpdate">
    Aktualizovat
  </button>
</template>

<script setup>
import { updateAvailable, applyUpdate } from './update';
</script>

<style scoped>
.update-pill {
  position: fixed;
  right: calc(14px + env(safe-area-inset-right, 0px));
  bottom: calc(14px + var(--sab));
  z-index: 60;
  padding: 10px 16px;
  font: 600 13px/1.2 system-ui, -apple-system, sans-serif;
  letter-spacing: 0.02em;
  color: var(--bg);
  background: var(--accent);
  border: 1px solid var(--accent);
  border-radius: 12px;
  /* Žádné hover/focus efekty (mobilní PWA); stav jen při stisku. */
  -webkit-tap-highlight-color: transparent;
}
.update-pill:active { background: var(--accent-dim); border-color: var(--accent-dim); }
</style>
