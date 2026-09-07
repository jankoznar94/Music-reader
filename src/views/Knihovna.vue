<template>
  <div class="library">
    <header class="topbar">
      <h1>Noty</h1>
      <div class="top-actions">
        <template v-if="!selectMode">
          <button class="add" @click="openFile">Nahrát PDF</button>
          <button class="btn" @click="enterSelect">Vybrat</button>
        </template>
        <template v-else>
          <button class="btn" @click="toggleSelectAll">{{ allSelected ? 'Zrušit výběr' : 'Vybrat vše' }}</button>
          <button class="add" @click="exitSelect">Hotovo</button>
        </template>
        <input ref="fileInput" type="file" accept="application/pdf" multiple hidden @change="onFiles" />
      </div>
    </header>

    <!-- Vyhledávání + řazení -->
    <div class="toolbar">
      <input v-model="search" type="text" placeholder="Hledat…" class="search" />
      <select v-model="sortBy" class="sort">
        <option value="name">Název</option>
        <option value="date">Datum</option>
      </select>
    </div>

    <!-- Tabs: Noty / Složky / Skupiny -->
    <div class="tabs">
      <button class="tab" :class="{ on: tab === 'songs' }" @click="tab = 'songs'">Noty</button>
      <button class="tab" :class="{ on: tab === 'folders' }" @click="tab = 'folders'">Složky</button>
      <button class="tab" :class="{ on: tab === 'groups' }" @click="tab = 'groups'">Skupiny</button>
    </div>

    <!-- ===== NOTY ===== -->
    <div v-if="tab === 'songs'" class="content" ref="contentEl" @scroll.passive="onScroll">
      <!-- Filtr složek -->
      <div class="folder-filter">
        <button
          class="ff-chip"
          :class="{ on: folderFilter === null }"
          @click="folderFilter = null"
        >Vše</button>
        <button
          v-for="f in folders"
          :key="f.id"
          class="ff-chip"
          :class="{ on: folderFilter === f.id }"
          @click="folderFilter = f.id"
        >{{ f.name }}</button>
        <button
          class="ff-chip"
          :class="{ on: folderFilter === 'none' }"
          @click="folderFilter = 'none'"
        >Bez složky</button>
      </div>

      <div v-if="loading" class="center muted">Načítám…</div>
      <div v-else-if="filteredSongs.length === 0" class="center muted">
        {{ songs.length === 0 ? 'Zatím žádné noty. Nahraj první PDF.' : 'Nic nenalezeno.' }}
      </div>
      <template v-else>
        <!-- Seskupení podle autora (rozbalitelné záložky) -->
        <div v-for="g in songGroups" :key="g.key" class="author-group">
          <button class="author-header" @click="toggleAuthor(g.key)">
            <span class="author-caret">{{ isAuthorOpen(g.key) ? '▾' : '▸' }}</span>
            <span class="author-name">{{ g.label }}</span>
            <span class="author-count">{{ g.items.length }} {{ g.items.length === 1 ? 'soubor' : (g.items.length < 5 ? 'soubory' : 'souborů') }}</span>
          </button>
          <ul v-if="isAuthorOpen(g.key)" class="songlist">
            <li v-for="s in g.items" :key="s.id" class="song" :class="{ sel: isSelected(s.id) }" @click="onSongClick(s)">
              <span v-if="selectMode" class="check" :class="{ on: isSelected(s.id) }" @click.stop="toggleSelect(s.id)">✓</span>
              <div class="song-info">
                <div class="song-name">{{ s.name || s.fileName }}</div>
                <div class="song-meta">
                  {{ s.pages }} str. · {{ s.groups?.length || 0 }} skupin
                  <span v-if="folderName(s.folderId)" class="song-folder">· {{ folderName(s.folderId) }}</span>
                </div>
              </div>
              <div class="song-actions" @click.stop>
                <template v-if="!selectMode">
                  <button class="icon-btn" @click="openEditSong(s)" title="Upravit (název, autor)">✏️</button>
                  <button class="icon-btn" @click="openAssignFolder(s)" title="Přiřadit do složky">📁</button>
                  <button class="icon-btn" @click="openAddToGroup(s)" title="Přidat do skupiny">＋</button>
                  <button class="icon-btn danger" @click="confirmDelete(s)" title="Smazat">🗑</button>
                </template>
              </div>
            </li>
          </ul>
        </div>
      </template>
    </div>

    <!-- ===== SLOŽKY ===== -->
    <div v-else-if="tab === 'folders'" class="content">
      <div class="group-actions">
        <button class="add" @click="createFolder">Nová složka</button>
      </div>
      <div v-if="folders.length === 0" class="center muted">
        Zatím žádné složky. Vytvoř první a roztřiď noty (sólový repertoár, sborový, barokní…).
      </div>
      <ul v-else class="grouplist">
        <li v-for="f in folders" :key="f.id" class="group">
          <div class="group-info">
            <div class="group-name">{{ f.name }}</div>
            <div class="group-meta">{{ folderCount(f.id) }} {{ folderCount(f.id) === 1 ? 'soubor' : (folderCount(f.id) < 5 ? 'soubory' : 'souborů') }}</div>
          </div>
          <div class="song-actions" @click.stop>
            <button class="icon-btn" @click="renameFolder(f)" title="Přejmenovat">✏️</button>
            <button class="icon-btn danger" @click="confirmDeleteFolder(f)" title="Smazat složku">🗑</button>
          </div>
        </li>
      </ul>
    </div>

    <!-- ===== SKUPINY ===== -->
    <div v-else class="content">
      <div class="group-actions">
        <button class="add" @click="createGroup">Nová skupina</button>
      </div>
      <div v-if="groups.length === 0" class="center muted">
        Zatím žádné skupiny. Vytvoř první a seskupte noty pro plynulé přehrávání.
      </div>
      <ul v-else class="grouplist">
        <li v-for="g in groups" :key="g.id" class="group" @click="openGroup(g)">
          <div class="group-info">
            <div class="group-name">{{ g.name }}</div>
            <div class="group-meta">{{ g.songIds.length }} {{ g.songIds.length === 1 ? 'soubor' : (g.songIds.length < 5 ? 'soubory' : 'souborů') }}</div>
          </div>
          <div class="song-actions" @click.stop>
            <button class="icon-btn" @click="openGroup(g)" title="Otevřít">▶</button>
            <button class="icon-btn danger" @click="confirmDeleteGroup(g)" title="Smazat skupinu">🗑</button>
          </div>
        </li>
      </ul>
    </div>

    <!-- Akční lišta pro hromadný výběr (mimo řetězec v-if/v-else záložek) -->
    <div v-if="selectMode" class="bulk-bar">
      <span class="bulk-count">{{ selectedIds.size }} vybráno</span>
      <div class="bulk-actions">
        <button class="bulk-btn" @click="openBulkFolder" :disabled="selectedIds.size === 0">📁 Složka</button>
        <button class="bulk-btn" @click="openBulkGroup" :disabled="selectedIds.size === 0">＋ Skupina</button>
        <button class="bulk-btn danger" @click="confirmBulkDelete" :disabled="selectedIds.size === 0">🗑 Smazat</button>
      </div>
    </div>

    <!-- Modal: přidat do skupiny -->
    <div v-if="addToGroupSong" class="modal-overlay" @click.self="addToGroupSong = null">
      <div class="modal">
        <h3>Přidat „{{ addToGroupSong.name }}" do skupiny</h3>
        <div v-if="groups.length === 0" class="muted">Zatím žádné skupiny.</div>
        <div v-else class="modal-list">
          <button
            v-for="g in groups"
            :key="g.id"
            class="modal-item"
            :class="{ on: addToGroupSong.groups?.includes(g.id) }"
            @click="toggleInGroup(g, addToGroupSong)"
          >{{ g.name }}</button>
        </div>
        <button class="modal-close" @click="addToGroupSong = null">Zavřít</button>
      </div>
    </div>

    <!-- Modal: přiřadit do složky -->
    <div v-if="assignFolderSong" class="modal-overlay" @click.self="assignFolderSong = null">
      <div class="modal">
        <h3>Přiřadit „{{ assignFolderSong.name }}" do složky</h3>
        <div v-if="folders.length === 0" class="muted">Zatím žádné složky. Vytvoř ji v záložce Složky.</div>
        <div v-else class="modal-list">
          <button
            v-for="f in folders"
            :key="f.id"
            class="modal-item"
            :class="{ on: assignFolderSong.folderId === f.id }"
            @click="assignFolder(f, assignFolderSong)"
          >{{ f.name }}</button>
          <button
            class="modal-item"
            :class="{ on: !assignFolderSong.folderId }"
            @click="assignFolder(null, assignFolderSong)"
          >Bez složky</button>
        </div>
        <button class="modal-close" @click="assignFolderSong = null">Zavřít</button>
      </div>
    </div>

    <!-- Modal: hromadně přiřadit do složky -->
    <div v-if="bulkFolderOpen" class="modal-overlay" @click.self="bulkFolderOpen = false">
      <div class="modal">
        <h3>Přesunout {{ selectedIds.size }} {{ selectedIds.size === 1 ? 'soubor' : (selectedIds.size < 5 ? 'soubory' : 'souborů') }} do složky</h3>
        <div v-if="folders.length === 0" class="muted">Zatím žádné složky. Vytvoř ji v záložce Složky.</div>
        <div v-else class="modal-list">
          <button
            v-for="f in folders"
            :key="f.id"
            class="modal-item"
            @click="bulkAssignFolder(f)"
          >{{ f.name }}</button>
          <button class="modal-item" @click="bulkAssignFolder(null)">Bez složky</button>
        </div>
        <button class="modal-close" @click="bulkFolderOpen = false">Zavřít</button>
      </div>
    </div>

    <!-- Modal: hromadně přidat do skupiny -->
    <div v-if="bulkGroupOpen" class="modal-overlay" @click.self="bulkGroupOpen = false">
      <div class="modal">
        <h3>Přidat {{ selectedIds.size }} {{ selectedIds.size === 1 ? 'soubor' : (selectedIds.size < 5 ? 'soubory' : 'souborů') }} do skupiny</h3>
        <div v-if="groups.length === 0" class="muted">Zatím žádné skupiny. Vytvoř ji v záložce Skupiny.</div>
        <div v-else class="modal-list">
          <button
            v-for="g in groups"
            :key="g.id"
            class="modal-item"
            @click="bulkAddToGroup(g)"
          >{{ g.name }}</button>
        </div>
        <button class="modal-close" @click="bulkGroupOpen = false">Zavřít</button>
      </div>
    </div>

    <!-- Modal: detail skupiny (setlist) -->
    <div v-if="openGroupDetail" class="modal-overlay" @click.self="openGroupDetail = null">
      <div class="modal wide">
        <h3>{{ openGroupDetail.name }}</h3>
        <div class="modal-list">
          <div v-for="(sid, idx) in openGroupDetail.songIds" :key="sid" class="setlist-item">
            <button class="icon-btn" @click="moveInGroup(openGroupDetail, idx, -1)" :disabled="idx === 0" title="Nahoru">↑</button>
            <span class="setlist-name">{{ songName(sid) }}</span>
            <button class="icon-btn" @click="moveInGroup(openGroupDetail, idx, 1)" :disabled="idx === openGroupDetail.songIds.length - 1" title="Dolů">↓</button>
            <button class="icon-btn danger" @click="removeFromGroup(openGroupDetail, sid)" title="Odebrat">✕</button>
          </div>
        </div>
        <div class="modal-actions">
          <button class="add" @click="playGroup(openGroupDetail)">Přehrát setlist</button>
          <button class="modal-close" @click="openGroupDetail = null">Zavřít</button>
        </div>
      </div>
    </div>
    <!-- Modal: upravit notu (název + autor) -->
    <div v-if="editSong" class="modal-overlay" @click.self="editSong = null">
      <div class="modal">
        <h3>Upravit notu</h3>
        <label class="edit-label">Název</label>
        <input
          ref="editNameInput"
          v-model="editName"
          class="edit-input"
          type="text"
          placeholder="Název noty"
        />
        <label class="edit-label">Autor</label>
        <input
          v-model="editComposer"
          class="edit-input"
          type="text"
          placeholder="Např. Wolfgang Amadeus Mozart"
        />
        <div class="modal-actions">
          <button class="modal-close" @click="editSong = null">Zrušit</button>
          <button class="add" @click="saveEdit" :disabled="!editName.trim()">Uložit</button>
        </div>
      </div>
    </div>

    <!-- Loading overlay při nahrávání not -->
    <div v-if="uploading" class="upload-overlay">
      <div class="upload-box">
        <div class="spinner" />
        <div class="upload-text">Nahrávám noty…</div>
        <div v-if="uploadTotal > 0" class="upload-progress">{{ uploadDone }} / {{ uploadTotal }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue';
import { useRouter } from 'vue-router';
import {
  dbGetAllSongs, dbSaveSong, dbDeleteSong,
  dbGetAllGroups, dbSaveGroup, dbDeleteGroup,
  dbGetAllFolders, dbSaveFolder, dbDeleteFolder,
} from '../db.js';
import { getPageCount, clearPdfCache } from '../pdf.js';
import { getLibraryState, saveLibraryState } from '../libraryState.js';

const router = useRouter();
const libState = getLibraryState();
const songs = ref([]);
const groups = ref([]);
const folders = ref([]);
const loading = ref(true);
const fileInput = ref(null);
const contentEl = ref(null);
// Výchozí stav přehledu pochází z libraryState (přežije přechod do prohlížeče,
// po reloadu resetován v main.js)
const search = ref(libState.search);
const sortBy = ref(libState.sortBy);
const tab = ref(libState.tab);
const folderFilter = ref(libState.folderFilter); // null = vše, 'none' = bez složky, jinak folderId

const addToGroupSong = ref(null);
const assignFolderSong = ref(null);
const openGroupDetail = ref(null);

// Hromadný výběr
const selectMode = ref(false);
const selectedIds = reactive(new Set());
const bulkFolderOpen = ref(false);
const bulkGroupOpen = ref(false);

// Editace noty (název + autor)
const editSong = ref(null);   // nota k editaci
const editName = ref('');
const editComposer = ref('');
const editNameInput = ref(null);
// Nahrávání
const uploading = ref(false);
const uploadDone = ref(0);
const uploadTotal = ref(0);

function openFile() { fileInput.value.click(); }

async function loadAll() {
  loading.value = true;
  const [s, g, f] = await Promise.all([dbGetAllSongs(), dbGetAllGroups(), dbGetAllFolders()]);
  songs.value = s;
  groups.value = g;
  folders.value = f;
  loading.value = false;
  // Po vykreslení seznamu obnovit scroll pozici (návrat z prohlížeče)
  nextTick(() => restoreScroll());
}

async function onFiles(e) {
  const files = Array.from(e.target.files || []);
  e.target.value = '';
  if (files.length === 0) return;
  uploading.value = true;
  uploadDone.value = 0;
  uploadTotal.value = files.length;
  // Dočasně vyčistit PDF cache, aby se u každého souboru počítal počet stránek zvlášť
  clearPdfCache();
  for (const file of files) {
    let pageCount = 1;
    try {
      const dummy = { id: 'tmp-' + crypto.randomUUID(), data: file };
      pageCount = await getPageCount(dummy);
    } catch (err) {
      console.warn('Nepodařilo se zjistit počet stránek', err);
    }
    const song = {
      id: crypto.randomUUID(),
      name: file.name.replace(/\.pdf$/i, ''),
      composer: '',
      fileName: file.name,
      data: file,
      pages: pageCount,
      groups: [],
      folderId: null,
      createdAt: Date.now(),
    };
    await dbSaveSong(song);
    uploadDone.value++;
  }
  uploading.value = false;
  await loadAll();
}

const filteredSongs = computed(() => {
  let list = songs.value;
  if (folderFilter.value === 'none') {
    list = list.filter(s => !s.folderId);
  } else if (folderFilter.value) {
    list = list.filter(s => s.folderId === folderFilter.value);
  }
  if (search.value.trim()) {
    const q = search.value.trim().toLowerCase();
    list = list.filter(s => (s.name || '').toLowerCase().includes(q) || (s.composer || '').toLowerCase().includes(q));
  }
  if (sortBy.value === 'name') {
    list = [...list].sort((a, b) => (a.name || '').localeCompare(b.name || '', 'cs'));
  } else {
    list = [...list].sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));
  }
  return list;
});

// Otevřené záložky autorů (reactive Set — Vue reaguje na add/delete).
// Výchozí stav: vše ZABALENÉ, uživatel si rozbalí. Po reloadu se vynuluje.
const openAuthors = reactive(new Set());

// Autor se extrahuje AUTOMATICKY z názvu ve formátu "Autor - Skladba".
// Přednost má vyplněné pole author; jinak se parsuje z názevu.
// Bez autora → kategorie "Ostatní".
function authorOf(s) {
  if (s.composer && s.composer.trim()) return s.composer.trim();
  const n = (s.name || s.fileName || '').trim();
  const m = n.match(/^(.*?)\s*-\s*(.+)$/);
  if (m) {
    const author = m[1].trim();
    if (author) return author;
  }
  return '';
}

// Seskupení not podle autora. "Ostatní" (bez autora) jde vždy NA KONEC
// jako výjimka z abecedního řazení.
const songGroups = computed(() => {
  const map = new Map();
  for (const s of filteredSongs.value) {
    const author = authorOf(s);
    const key = author.toLowerCase();
    const label = author || 'Ostatní';
    if (!map.has(key)) map.set(key, { key, label, items: [] });
    map.get(key).items.push(s);
  }
  const groups = [...map.values()];
  // Abecedně, ale "Ostatní" (prázdný autor) na konec
  return groups.sort((a, b) => {
    const aOther = a.key === '';
    const bOther = b.key === '';
    if (aOther !== bOther) return aOther ? 1 : -1;
    return a.label.localeCompare(b.label, 'cs');
  });
});

function isAuthorOpen(key) { return openAuthors.has(key); }
function toggleAuthor(key) {
  if (openAuthors.has(key)) openAuthors.delete(key);
  else openAuthors.add(key);
}

function openSong(s) {
  router.push({ name: 'Prohlizec', params: { id: s.id } });
}

// --- Hromadný výběr ---
function enterSelect() {
  selectMode.value = true;
  selectedIds.clear();
}
function exitSelect() {
  selectMode.value = false;
  selectedIds.clear();
  bulkFolderOpen.value = false;
  bulkGroupOpen.value = false;
}
function isSelected(id) { return selectedIds.has(id); }
function toggleSelect(id) {
  if (selectedIds.has(id)) selectedIds.delete(id);
  else selectedIds.add(id);
}
const allSelected = computed(() =>
  filteredSongs.value.length > 0 && filteredSongs.value.every(s => selectedIds.has(s.id))
);
function toggleSelectAll() {
  if (allSelected.value) {
    for (const s of filteredSongs.value) selectedIds.delete(s.id);
  } else {
    for (const s of filteredSongs.value) selectedIds.add(s.id);
  }
}
function onSongClick(s) {
  if (selectMode.value) toggleSelect(s.id);
  else openSong(s);
}
function selectedSongs() {
  return songs.value.filter(s => selectedIds.has(s.id));
}
function openBulkFolder() { bulkFolderOpen.value = true; }
function openBulkGroup() { bulkGroupOpen.value = true; }

async function bulkAssignFolder(folder) {
  const sel = selectedSongs();
  for (const s of sel) {
    s.folderId = folder ? folder.id : null;
    await dbSaveSong(s);
  }
  bulkFolderOpen.value = false;
  // In-place mutace — seznam se aktualizuje sám, scroll zůstává
}

async function bulkAddToGroup(g) {
  const sel = selectedSongs();
  for (const s of sel) {
    if (!(s.groups || []).includes(g.id)) {
      s.groups = [...(s.groups || []), g.id];
      g.songIds = [...g.songIds, s.id];
      await dbSaveSong(s);
    }
  }
  await dbSaveGroup(g);
  bulkGroupOpen.value = false;
}

async function confirmBulkDelete() {
  const sel = selectedSongs();
  if (sel.length === 0) return;
  if (!confirm(`Smazat ${sel.length} ${sel.length === 1 ? 'soubor' : (sel.length < 5 ? 'soubory' : 'souborů')}?`)) return;
  for (const s of sel) {
    await dbDeleteSong(s.id);
    for (const g of groups.value) {
      if (g.songIds.includes(s.id)) {
        g.songIds = g.songIds.filter(x => x !== s.id);
        await dbSaveGroup(g);
      }
    }
  }
  exitSelect();
  await loadAll();
}

function openEditSong(s) {
  editSong.value = s;
  editName.value = s.name || s.fileName || '';
  editComposer.value = s.composer || '';
  nextTick(() => editNameInput.value && editNameInput.value.focus());
}

async function saveEdit() {
  const s = editSong.value;
  const name = editName.value.trim();
  if (!s || !name) return;
  s.name = name;
  s.composer = editComposer.value.trim() || '';
  await dbSaveSong(s);
  editSong.value = null;
  await loadAll();
}

async function confirmDelete(s) {
  if (confirm(`Smazat „${s.name || s.fileName}"?`)) {
    await dbDeleteSong(s.id);
    // odebrat ze všech skupin
    for (const g of groups.value) {
      if (g.songIds.includes(s.id)) {
        g.songIds = g.songIds.filter(x => x !== s.id);
        await dbSaveGroup(g);
      }
    }
    await loadAll();
  }
}

// --- Složky ---
async function createFolder() {
  const name = prompt('Název složky:');
  if (!name || !name.trim()) return;
  await dbSaveFolder({ id: crypto.randomUUID(), name: name.trim(), createdAt: Date.now() });
  await loadAll();
}

async function renameFolder(f) {
  const name = prompt('Nový název složky:', f.name);
  if (!name || !name.trim() || name.trim() === f.name) return;
  f.name = name.trim();
  await dbSaveFolder(f);
  await loadAll();
}

function openAssignFolder(s) { assignFolderSong.value = s; }

async function assignFolder(folder, song) {
  song.folderId = folder ? folder.id : null;
  await dbSaveSong(song);
  assignFolderSong.value = null;
  // Nevoláme loadAll() — `song` už je reactive objekt v songs.value, takže se seznam
  // neobnoví od nuly a zachová se pozice scrollu.
}

function folderName(id) {
  if (!id) return '';
  const f = folders.value.find(x => x.id === id);
  return f ? f.name : '';
}

function folderCount(id) {
  return songs.value.filter(s => s.folderId === id).length;
}

async function confirmDeleteFolder(f) {
  if (confirm(`Smazat složku „${f.name}"? Noty v ní zůstanou, jen se přesunou do „Bez složky".`)) {
    await dbDeleteFolder(f.id);
    // uvolnit skladby z této složky
    for (const s of songs.value) {
      if (s.folderId === f.id) {
        s.folderId = null;
        await dbSaveSong(s);
      }
    }
    if (folderFilter.value === f.id) folderFilter.value = null;
    await loadAll();
  }
}

// --- Skupiny ---
async function createGroup() {
  const name = prompt('Název skupiny:');
  if (!name || !name.trim()) return;
  await dbSaveGroup({ id: crypto.randomUUID(), name: name.trim(), songIds: [], createdAt: Date.now() });
  await loadAll();
}

function openAddToGroup(s) { addToGroupSong.value = s; }

async function toggleInGroup(g, song) {
  const inGroup = (song.groups || []).includes(g.id);
  if (inGroup) {
    song.groups = (song.groups || []).filter(x => x !== g.id);
    g.songIds = g.songIds.filter(x => x !== song.id);
  } else {
    song.groups = [...(song.groups || []), g.id];
    g.songIds = [...g.songIds, song.id];
  }
  await dbSaveSong(song);
  await dbSaveGroup(g);
  await loadAll();
}

function openGroup(g) {
  openGroupDetail.value = { ...g, songIds: [...g.songIds] };
}

async function moveInGroup(g, idx, dir) {
  const j = idx + dir;
  if (j < 0 || j >= g.songIds.length) return;
  const arr = [...g.songIds];
  [arr[idx], arr[j]] = [arr[j], arr[idx]];
  g.songIds = arr;
  await dbSaveGroup(g);
  openGroupDetail.value = { ...g, songIds: [...arr] };
}

async function removeFromGroup(g, sid) {
  g.songIds = g.songIds.filter(x => x !== sid);
  const song = songs.value.find(s => s.id === sid);
  if (song) {
    song.groups = (song.groups || []).filter(x => x !== g.id);
    await dbSaveSong(song);
  }
  await dbSaveGroup(g);
  openGroupDetail.value = { ...g, songIds: [...g.songIds] };
}

function songName(id) {
  const s = songs.value.find(x => x.id === id);
  return s ? (s.name || s.fileName) : '?';
}

function playGroup(g) {
  if (g.songIds.length === 0) return;
  router.push({ name: 'Prohlizec', params: { id: g.songIds[0] }, query: { group: g.id } });
}

async function confirmDeleteGroup(g) {
  if (confirm(`Smazat skupinu „${g.name}"?`)) {
    await dbDeleteGroup(g.id);
    // odebrat ze všech not
    for (const s of songs.value) {
      if ((s.groups || []).includes(g.id)) {
        s.groups = s.groups.filter(x => x !== g.id);
        await dbSaveSong(s);
      }
    }
    await loadAll();
  }
}

// Obnovit scroll pozici po vykreslení seznamu (po návratu z prohlížeče)
function restoreScroll() {
  const el = contentEl.value;
  if (el && libState.scrollReady && tab.value === 'songs') {
    el.scrollTop = libState.scrollTop;
  }
}

// Uložit scroll pozici při scrollování seznamu not
function onScroll() {
  const el = contentEl.value;
  if (el) {
    libState.scrollTop = el.scrollTop;
    libState.scrollReady = true;
  }
}

async function persistState() {
  saveLibraryState({
    tab: tab.value,
    folderFilter: folderFilter.value,
    search: search.value,
    sortBy: sortBy.value,
  });
}

onMounted(loadAll);

watch(() => tab.value, () => { nextTick(() => restoreScroll()); persistState(); });

// Změna filtru/hledání/řazení resetuje scroll NA VRCHOL jen v aktuálním zobrazení,
// ale uložený stav (pro návrat z prohlížeče) NEpřepisujeme.
watch(() => folderFilter.value, () => {
  const el = contentEl.value;
  if (el) { el.scrollTop = 0; libState.scrollTop = 0; }
  persistState();
});
watch(() => search.value, () => {
  const el = contentEl.value;
  if (el) { el.scrollTop = 0; libState.scrollTop = 0; }
  persistState();
});
watch(() => sortBy.value, persistState);
</script>

<style scoped>
.library { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px; gap: 12px; border-bottom: 1px solid var(--border);
}
.topbar h1 { margin: 0; font-size: 1.4rem; font-weight: 700; }
.top-actions { display: flex; gap: 8px; }

.toolbar { display: flex; gap: 8px; padding: 10px 16px; }
.search { flex: 1; }
.sort { background: var(--bg-elev); border: 1px solid var(--border); border-radius: 10px; padding: 0 10px; color: var(--text); }

.tabs { display: flex; gap: 8px; padding: 0 16px 10px; }
.tab {
  flex: 1; background: var(--bg-elev); border: 1px solid var(--border);
  border-radius: 10px; padding: 10px; font-weight: 600;
}
.tab.on { background: var(--accent); color: #17130f; border-color: var(--accent); }

.content { flex: 1; overflow-y: auto; padding: 0 12px 12px; }
.center { flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px; text-align: center; }
.muted { color: var(--text-dim); }

/* Filtr složek */
.folder-filter { display: flex; gap: 8px; flex-wrap: wrap; padding: 0 0 12px; }
.ff-chip {
  background: var(--bg-elev); border: 1px solid var(--border);
  border-radius: 20px; padding: 6px 14px; font-size: 0.9rem; cursor: pointer;
}
.ff-chip.on { background: var(--accent); color: #17130f; border-color: var(--accent); }

.songlist, .grouplist { list-style: none; margin: 0; padding: 0; }

/* Seskupení podle autora */
.author-group { margin-bottom: 4px; }
.author-header {
  width: 100%;
  display: flex; align-items: center; gap: 10px;
  background: transparent; border: none; cursor: pointer;
  padding: 12px 6px; border-radius: 10px;
  color: var(--text, #eee); text-align: left;
}
.author-header:active { background: var(--bg-elev2, #222); }
.author-caret { color: var(--accent, #e5d7a6); font-size: 1rem; width: 16px; }
.author-name { font-size: 1.05rem; font-weight: 700; flex: 1; }
.author-count { color: var(--text-dim, #888); font-size: 0.85rem; }
.author-group + .author-group { border-top: 1px solid var(--border, #333); padding-top: 2px; }
.song, .group {
  display: flex; align-items: center; justify-content: space-between;
  background: var(--bg-elev); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 14px; margin-bottom: 10px; cursor: pointer;
}
.song:active, .group:active { background: var(--bg-elev2); }
.song-info, .group-info { min-width: 0; }
.song-name, .group-name { font-size: 1.05rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.song-composer { color: var(--text-dim); font-size: 0.9rem; margin-top: 2px; }
.song-meta, .group-meta { color: var(--text-dim); font-size: 0.8rem; margin-top: 2px; }
.song-folder { color: var(--accent); }
.song-actions { display: flex; gap: 6px; }
.icon-btn {
  width: 36px; height: 36px; border-radius: 50%;
  border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); font-size: 1rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.icon-btn.danger { color: var(--danger); }
.icon-btn:disabled { opacity: 0.3; pointer-events: none; }

.group-actions { padding: 4px 0 12px; }
.add { background: var(--accent); color: #17130f; border: none; font-weight: 600; }
.btn { background: var(--bg-elev2); border: 1px solid var(--border); color: var(--text); font-weight: 600; }

/* Hromadný výběr */
.check {
  width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0;
  border: 2px solid var(--border); background: var(--bg-elev2);
  color: transparent; font-size: 0.9rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.check.on { background: var(--accent); border-color: var(--accent); color: #17130f; }
.song.sel { border-color: var(--accent); background: var(--bg-elev); }
.bulk-bar {
  position: sticky; bottom: 0; z-index: 20;
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  background: var(--bg-elev); border-top: 1px solid var(--border);
  padding: 10px 12px;
}
.bulk-count { color: var(--text-dim); font-size: 0.9rem; white-space: nowrap; }
.bulk-actions { display: flex; gap: 8px; }
.bulk-btn {
  background: var(--bg-elev2); border: 1px solid var(--border);
  color: var(--text); border-radius: 10px; padding: 10px 12px; font-weight: 600;
}
.bulk-btn.danger { color: var(--danger); }
.bulk-btn:disabled { opacity: 0.3; pointer-events: none; }

/* Modaly */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center; z-index: 50; padding: 20px;
}
.modal {
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 16px;
  padding: 20px; width: 100%; max-width: 420px; max-height: 80vh; overflow-y: auto;
}
.modal.wide { max-width: 520px; }
.modal h3 { margin: 0 0 14px; }
.modal-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.modal-item {
  text-align: left; background: var(--bg-elev2); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px; cursor: pointer;
}
.modal-item.on { border-color: var(--accent); background: var(--bg-elev); }
.setlist-item {
  display: flex; align-items: center; gap: 8px;
  background: var(--bg-elev2); border: 1px solid var(--border); border-radius: 10px; padding: 8px;
}
.setlist-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
.modal-close { background: var(--bg-elev2); border: 1px solid var(--border); }

/* Editace noty (název + autor) */
.edit-label {
  display: block;
  font-size: 0.8rem;
  color: var(--text-dim);
  margin: 0 0 6px;
}
.edit-input {
  width: 100%; box-sizing: border-box; margin-bottom: 14px;
  background: var(--bg-elev2); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px; color: var(--text); font-size: 1rem;
}

/* Loading overlay při nahrávání not */
.upload-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center; z-index: 60;
}
.upload-box {
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 16px;
  padding: 28px 36px; display: flex; flex-direction: column; align-items: center; gap: 12px;
}
.spinner {
  width: 36px; height: 36px; border-radius: 50%;
  border: 3px solid var(--bg-elev2); border-top-color: var(--accent);
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.upload-text { font-weight: 600; }
.upload-progress { color: var(--text-dim); font-size: 0.9rem; }
</style>
