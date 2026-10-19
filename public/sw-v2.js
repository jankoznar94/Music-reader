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

// ŽÁDNÉ automatické přebírání kontroly: nová verze SW se nesmí ujmout pod
// běžící stránkou (appka by se pod rukama obnovila / rozbily by se lazy chunky).
// Aktualizaci provádí výhradně tlačítko „Aktualizovat“ (src/update.js):
// zruší registraci SW i cache a načte appku znovu ze sítě.

// Reakce na zprávu "SKIP_WAITING" — ponecháno pro případ ručního přepnutí.
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// Veškerá data aplikace (PDF soubory + anotace) žijí v IndexedDB — žádná síť.
