// sw.js — Service Worker pro Noty App (lokální, bez backendu/FCM)
importScripts('https://storage.googleapis.com/workbox-cdn/releases/7.1.0/workbox-sw.js');

if (workbox) {
  console.log('Noty App SW: registered.');
  // Precache app shellu (html/js/css/assets) pro offline. Právě zde Workbox
  // vloží vygenerovaný seznam souborů (self.__WB_MANIFEST).
  workbox.precaching.precacheAndRoute(self.__WB_MANIFEST || []);
} else {
  console.error('Workbox nebylo načteno.');
}

// Reakce na zprávu "SKIP_WAITING" od registerSW() — umožní nové verzi
// převzít kontrolu okamžitě (skipWaiting + clients.claim), takže reload
// z banneru provede okamžitý přechod na novou verzi.
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// Jakmile nový SW převezme kontrolu (po skipWaiting), okamžitě ovládá stránky.
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// Veškerá data aplikace (PDF soubory + anotace) žijí v IndexedDB — žádná síť.
