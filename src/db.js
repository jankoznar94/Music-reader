// src/db.js — IndexedDB persistence (lokální, žádný backend)
// Obejktové úložiště:
//   'songs'  -> id, name, composer, fileName, data (Blob PDF), pages, createdAt
//   'meta'   -> klíč-hodnota (vybraná skladba, pozice atd.)

const DB_NAME = 'noty-app';
const DB_VERSION = 1;

let _dbPromise = null;

function openDb() {
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('songs')) {
        db.createObjectStore('songs', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('meta')) {
        db.createObjectStore('meta');
      }
      if (!db.objectStoreNames.contains('annotations')) {
        // Anotace na skladbu, keyPath = songId
        db.createObjectStore('annotations', { keyPath: 'songId' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return _dbPromise;
}

function tx(store, mode, fn) {
  return openDb().then((db) => {
    return new Promise((resolve, reject) => {
      const t = db.transaction(store, mode);
      const s = t.objectStore(store);
      const request = fn(s);
      t.oncomplete = () => resolve(request ? request.result : undefined);
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
  });
}

export async function dbGetAllSongs() {
  const res = await openDb().then((db) =>
    new Promise((resolve, reject) => {
      const t = db.transaction('songs', 'readonly');
      const req = t.objectStore('songs').getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    })
  );
  // Seřadit podle jména
  return res.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'cs'));
}

export function dbSaveSong(song) {
  return tx('songs', 'readwrite', (s) => s.put(song));
}

export function dbDeleteSong(id) {
  return tx('songs', 'readwrite', (s) => s.delete(id));
}

export function dbGetSong(id) {
  return tx('songs', 'readonly', (s) => s.get(id));
}

export async function dbSetMeta(key, value) {
  return tx('meta', 'readwrite', (s) => s.put(value, key));
}

export async function dbGetMeta(key) {
  const val = await tx('meta', 'readonly', (s) => s.get(key));
  return val === undefined ? null : val;
}

// --- Anotace (dostupné jen ve fullscreen režimu) ---
export function dbSaveAnnotations(annotations) {
  return tx('annotations', 'readwrite', (s) => s.put(annotations));
}

export function dbGetAnnotations(songId) {
  return tx('annotations', 'readonly', (s) => s.get(songId));
}
