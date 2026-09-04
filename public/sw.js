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

// Veškerá data aplikace (PDF soubory + anotace) žijí v IndexedDB — žádná síť.
