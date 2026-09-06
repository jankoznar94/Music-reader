// src/db.js — IndexedDB persistence (lokální, žádný backend)
// Objektové úložiště:
//   'songs'       -> id, name, composer, fileName, data (Blob PDF), pages, createdAt, groups: [], folderId
//   'meta'        -> klíč-hodnota (vybraná skladba, pozice atd.)
//   'annotations' -> songId -> { songId, items }
//   'groups'      -> id, name, songIds: [ordered], createdAt  (skupiny = setlisty)
//   'folders'     -> id, name, createdAt  (složky = kategorizace, skladba patří do právě jedné)
//   'jumps'       -> songId -> { songId, items: [{id, fromPage, toPage, label}] }  (Da Capo / VIDE skoky)

const DB_NAME = 'noty-app';
const DB_VERSION = 4;

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
      if (!db.objectStoreNames.contains('groups')) {
        // Skupiny (setlisty), keyPath = id
        db.createObjectStore('groups', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('folders')) {
        // Složky (kategorizace), keyPath = id
        db.createObjectStore('folders', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('jumps')) {
        // Skoky (Da Capo / VIDE), keyPath = songId
        db.createObjectStore('jumps', { keyPath: 'songId' });
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

// Hluboký klon, který zachová Blob a zbaví se Vue reaktivní proxy
// (IndexedDB put selže s DataCloneError na Proxy objektech)
function cloneForDb(obj) {
  if (obj instanceof Blob) return obj;
  if (Array.isArray(obj)) return obj.map(cloneForDb);
  if (obj && typeof obj === 'object') {
    const out = {};
    for (const k of Object.keys(obj)) out[k] = cloneForDb(obj[k]);
    return out;
  }
  return obj;
}

export function dbSaveSong(song) {
  return tx('songs', 'readwrite', (s) => s.put(cloneForDb(song)));
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
  return tx('annotations', 'readwrite', (s) => s.put(cloneForDb(annotations)));
}

export function dbGetAnnotations(songId) {
  return tx('annotations', 'readonly', (s) => s.get(songId));
}

// --- Skupiny (setlisty) ---
export function dbGetAllGroups() {
  return openDb().then((db) =>
    new Promise((resolve, reject) => {
      const t = db.transaction('groups', 'readonly');
      const req = t.objectStore('groups').getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    })
  );
}

export function dbGetGroup(id) {
  return tx('groups', 'readonly', (s) => s.get(id));
}

export function dbSaveGroup(group) {
  return tx('groups', 'readwrite', (s) => s.put(cloneForDb(group)));
}

export function dbDeleteGroup(id) {
  return tx('groups', 'readwrite', (s) => s.delete(id));
}

// --- Složky (kategorizace) ---
export function dbGetAllFolders() {
  return openDb().then((db) =>
    new Promise((resolve, reject) => {
      const t = db.transaction('folders', 'readonly');
      const req = t.objectStore('folders').getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    })
  );
}

export function dbSaveFolder(folder) {
  return tx('folders', 'readwrite', (s) => s.put(cloneForDb(folder)));
}

export function dbDeleteFolder(id) {
  return tx('folders', 'readwrite', (s) => s.delete(id));
}

// --- Skoky (Da Capo / VIDE) ---
export function dbSaveJumps(jumps) {
  return tx('jumps', 'readwrite', (s) => s.put(cloneForDb(jumps)));
}

export function dbGetJumps(songId) {
  return tx('jumps', 'readonly', (s) => s.get(songId));
}
