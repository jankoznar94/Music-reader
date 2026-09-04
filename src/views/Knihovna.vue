<template>
  <div class="library">
    <header class="topbar">
      <h1>Noty</h1>
      <button class="add" @click="openFile">Nahrát PDF</button>
      <input ref="fileInput" type="file" accept="application/pdf" hidden @change="onFile" />
    </header>

    <div v-if="loading" class="center muted">Načítám…</div>
    <div v-else-if="songs.length === 0" class="center muted">
      Zatím žádné noty. Nahraj první PDF.
    </div>

    <ul v-else class="songlist">
      <li
        v-for="s in songs"
        :key="s.id"
        class="song"
        @click="openSong(s)"
      >
        <div class="song-info">
          <div class="song-name">{{ s.name || s.fileName }}</div>
          <div v-if="s.composer" class="song-composer">{{ s.composer }}</div>
        </div>
        <button class="delsong" @click.stop="confirmDelete(s)">Smazat</button>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { dbGetAllSongs, dbSaveSong, dbDeleteSong } from '../db.js';
import { getPageCount } from '../pdf.js';

const router = useRouter();
const songs = ref([]);
const loading = ref(true);
const fileInput = ref(null);

function openFile() {
  fileInput.value.click();
}

async function loadSongs() {
  loading.value = true;
  songs.value = await dbGetAllSongs();
  loading.value = false;
}

async function onFile(e) {
  const file = e.target.files[0];
  e.target.value = '';
  if (!file) return;

  let pageCount = 1;
  try {
    // Zjistit počet stránek (pro zobrazení v seznamu)
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
    createdAt: Date.now(),
  };
  await dbSaveSong(song);
  await loadSongs();
}

function openSong(s) {
  router.push({ name: 'Prohlizec', params: { id: s.id } });
}

async function confirmDelete(s) {
  if (confirm(`Smazat "${s.name || s.fileName}"?`)) {
    await dbDeleteSong(s.id);
    await loadSongs();
  }
}

onMounted(loadSongs);
</script>

<style scoped>
.library { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px; gap: 12px; border-bottom: 1px solid var(--border);
}
.topbar h1 { margin: 0; font-size: 1.4rem; font-weight: 700; }

.center { flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px; text-align: center; }
.muted { color: var(--text-dim); }

.songlist { list-style: none; margin: 0; padding: 12px; overflow-y: auto; flex: 1; }
.song {
  display: flex; align-items: center; justify-content: space-between;
  background: var(--bg-elev); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px; margin-bottom: 10px;
  cursor: pointer;
}
.song:active { background: var(--bg-elev2); }
.song-info { min-width: 0; }
.song-name { font-size: 1.05rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.song-composer { color: var(--text-dim); font-size: 0.9rem; margin-top: 2px; }

.delsong { background: transparent; border: 1px solid var(--border); padding: 8px 12px; color: var(--danger); }

.add { background: var(--accent); color: #17130f; border: none; font-weight: 600; }
</style>
