<template>
  <div class="library">
    <header class="topbar">
      <h1>Noty</h1>
      <div class="top-actions">
        <button class="add" @click="openFile">Nahrát PDF</button>
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
    <div v-if="tab === 'songs'" class="content">
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
      <ul v-else class="songlist">
        <li v-for="s in filteredSongs" :key="s.id" class="song" @click="openSong(s)">
          <div class="song-info">
            <div class="song-name">{{ s.name || s.fileName }}</div>
            <div v-if="s.composer" class="song-composer">{{ s.composer }}</div>
            <div class="song-meta">
              {{ s.pages }} str. · {{ s.groups?.length || 0 }} skupin
              <span v-if="folderName(s.folderId)" class="song-folder">· {{ folderName(s.folderId) }}</span>
            </div>
          </div>
          <div class="song-actions" @click.stop>
            <button class="icon-btn" @click="openAssignFolder(s)" title="Přiřadit do složky">📁</button>
            <button class="icon-btn" @click="openAddToGroup(s)" title="Přidat do skupiny">＋</button>
            <button class="icon-btn danger" @click="confirmDelete(s)" title="Smazat">🗑</button>
          </div>
        </li>
      </ul>
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
            <div class="group-meta">{{ folderCount(f.id) }} not</div>
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
            <div class="group-meta">{{ g.songIds.length }} not</div>
          </div>
          <div class="song-actions" @click.stop>
            <button class="icon-btn" @click="openGroup(g)" title="Otevřít">▶</button>
            <button class="icon-btn danger" @click="confirmDeleteGroup(g)" title="Smazat skupinu">🗑</button>
          </div>
        </li>
      </ul>
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import {
  dbGetAllSongs, dbSaveSong, dbDeleteSong,
  dbGetAllGroups, dbSaveGroup, dbDeleteGroup,
  dbGetAllFolders, dbSaveFolder, dbDeleteFolder,
} from '../db.js';
import { getPageCount } from '../pdf.js';

const router = useRouter();
const songs = ref([]);
const groups = ref([]);
const folders = ref([]);
const loading = ref(true);
const fileInput = ref(null);
const search = ref('');
const sortBy = ref('name');
const tab = ref('songs');
const folderFilter = ref(null); // null = vše, 'none' = bez složky, jinak folderId

const addToGroupSong = ref(null);
const assignFolderSong = ref(null);
const openGroupDetail = ref(null);

function openFile() { fileInput.value.click(); }

async function loadAll() {
  loading.value = true;
  const [s, g, f] = await Promise.all([dbGetAllSongs(), dbGetAllGroups(), dbGetAllFolders()]);
  songs.value = s;
  groups.value = g;
  folders.value = f;
  loading.value = false;
}

async function onFiles(e) {
  const files = Array.from(e.target.files || []);
  e.target.value = '';
  if (files.length === 0) return;
  for (const file of files) {
    let pageCount = 1;
    try {
      const dummy = { id: 'tmp', data: file };
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
  }
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

function openSong(s) {
  router.push({ name: 'Prohlizec', params: { id: s.id } });
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
  await loadAll();
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

onMounted(loadAll);
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
</style>
