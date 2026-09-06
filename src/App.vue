<template>
  <router-view />
</template>

<script setup>
import { registerSW } from 'virtual:pwa-register';

// Automatická aktualizace Service Workeru (autoUpdate):
// - nová verze se stáhne a aktivuje SAMA, bez banneru a bez zásahu uživatele
// - aplikace se načte z nové verze při příštím otevření / obnovení
// - žádný loop s "obnovit" — nic se nedá zablokovat cache prohlížeče
registerSW({
  immediate: true,
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
</script>
