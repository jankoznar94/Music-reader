<template>
  <div
    class="viewer"
    ref="viewerEl"
    @touchstart.passive="onTouchStart"
    @touchmove.passive="onTouchMove"
    @touchend.passive="onTouchEnd"
    @click="onTap"
  >
    <!-- Aktivní stránka -->
    <div class="stage" :style="{ transform: 'translate(' + panX + 'px,' + panY + 'px) scale(' + zoom + ')' }">
      <canvas ref="canvasEl" class="pdf-canvas" />
      <!-- Anotační vrstva nad PDF -->
      <svg
        ref="layerSvgEl"
        class="annot-layer"
        :class="{ active: annotMode }"
        :width="cssW"
        :height="cssH"
        @pointerdown.prevent="onLayerDown($event)"
        @pointermove.prevent="onLayerMove($event)"
        @pointerup.prevent="onLayerUp"
        @pointercancel.prevent="onLayerUp"
        @pointerleave.prevent="onLayerUp"
      >
        <!-- Překreslené anotace aktuální stránky -->
        <g v-for="it in pageItems" :key="it.id">
          <path
            :d="pathD(it)"
            fill="none"
            :stroke="it.color"
            :stroke-width="it.width"
            stroke-linecap="round"
            stroke-linejoin="round"
            :class="{ hl: it.tool === 'highlighter' }"
          />
        </g>
        <!-- Aktivní tah -->
        <path
          v-if="activeStroke"
          :d="pathD(activeStroke)"
          fill="none"
          :stroke="activeStroke.color"
          :stroke-width="activeStroke.width"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </div>

    <!-- Indikátor stránky + názvu noty -->
    <div class="page-ind">
      <span v-if="group" class="ind-song">{{ songName }} · {{ groupIndex + 1 }}/{{ groupSongs.length }}</span>
      <span>{{ currentPage + 1 }} / {{ totalPages }}</span>
    </div>

    <!-- Loading overlay při prvním načtení / přechodu mezi skladbami -->
    <div v-if="loading" class="viewer-loading">
      <div class="spinner" />
      <div class="loading-text">Načítám noty…</div>
    </div>

    <!-- Přepínání skladeb ve skupině (setlist) -->
    <div v-if="group" class="nav-strip">
      <button class="nav-btn" @click="prevSong" :disabled="groupIndex <= 0" title="Předchozí skladba">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
      </button>
      <span class="nav-label">{{ groupIndex + 1 }} / {{ groupSongs.length }}</span>
      <button class="nav-btn" @click="nextSong" :disabled="groupIndex >= groupSongs.length - 1" title="Další skladba">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
      </button>
    </div>

    <!-- Skoky (Da Capo / VIDE) — tlačítko se zobrazí jen na stránce, kde skok začíná -->
    <div v-if="currentJumps.length" class="jump-strip">
      <button
        v-for="j in currentJumps"
        :key="j.id"
        class="jump-btn"
        @click="goJump(j)"
        :title="'Skok na str. ' + (j.toPage + 1)"
      >{{ j.label }}</button>
    </div>

    <!-- Panel pro vytváření skoku -->
    <div v-if="jumpMode" class="jump-panel">
      <div class="jp-title">Nový skok</div>
      <div class="jp-row">
        <button class="jp-btn" @click="setJumpStart" :class="{ on: jumpStart !== null }">
          {{ jumpStart === null ? 'Start' : 'Start: str. ' + (jumpStart + 1) }}
        </button>
        <button class="jp-btn" @click="setJumpEnd" :disabled="jumpStart === null" :class="{ on: jumpEnd !== null }">
          {{ jumpEnd === null ? 'Konec' : 'Konec: str. ' + (jumpEnd + 1) }}
        </button>
      </div>
      <div class="jp-row">
        <input v-model="jumpLabel" class="jp-input" placeholder="Text tlačítka (např. Da Capo)" />
        <button class="jp-btn primary" @click="saveJump" :disabled="jumpStart === null || jumpEnd === null">Uložit</button>
      </div>
      <div v-if="jumps.length" class="jp-list">
        <div class="jp-subtitle">Existující skoky</div>
        <div v-for="j in jumps" :key="j.id" class="jp-item">
          <span class="jp-item-label">{{ j.label }}</span>
          <span class="jp-item-pages">str. {{ j.fromPage + 1 }} → {{ j.toPage + 1 }}</span>
          <button class="jp-del" @click="deleteJump(j)" title="Smazat skok">🗑</button>
        </div>
      </div>
      <button class="jp-close" @click="toggleJumpMode">Zavřít</button>
    </div>

    <!-- Panel pro vytváření/úpravu záložky -->
    <div v-if="bookmarkMode" class="jump-panel">
      <div class="jp-title">{{ bookmarkEditing ? 'Upravit záložku' : 'Nová záložka' }}</div>
      <div class="jp-row">
        <span class="jp-cur">{{ bookmarkEditing ? 'Stránka ' + ((bookmarks.find(x => x.id === bookmarkEditing) || {}).page + 1) : 'Stránka ' + (currentPage + 1) }}</span>
      </div>
      <div class="jp-row">
        <input v-model="bookmarkLabel" class="jp-input" placeholder="Text záložky (např. Coda)" />
        <button class="jp-btn primary" @click="saveBookmark">{{ bookmarkEditing ? 'Uložit' : 'Přidat' }}</button>
      </div>

      <!-- Seznam existujících záložek (editace + řazení + smazání) -->
      <div v-if="bookmarks.length" class="jp-list">
        <div class="jp-subtitle">Záložky</div>
        <div v-for="(b, idx) in bookmarks" :key="b.id" class="jp-item">
          <span class="jp-item-label" :class="{ dim: !b.label }">str. {{ b.page + 1 }}<template v-if="b.label"> · {{ b.label }}</template></span>
          <span class="jp-actions">
            <button class="jp-icon" @click="startEditBookmark(b)" title="Upravit">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.8 2.8 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></svg>
            </button>
            <button class="jp-icon del" @click="deleteBookmark(b)" title="Smazat">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
            </button>
          </span>
          <span class="jp-moves">
            <button class="jp-icon" @click="moveBookmark(b, -1)" :disabled="idx === 0" title="Přesunout nahoru">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg>
            </button>
            <button class="jp-icon" @click="moveBookmark(b, 1)" :disabled="idx === bookmarks.length - 1" title="Přesunout dolů">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M19 12l-7 7-7-7"/></svg>
            </button>
          </span>
        </div>
      </div>

      <button class="jp-close" @click="bookmarkMode = false; bookmarkLabel = ''; bookmarkEditing = null">Zavřít</button>
    </div>

    <!-- Záložky — vždy viditelná lišta u spodní hrany -->
    <div v-if="bookmarks.length" class="bookmark-strip">
      <button
        v-for="b in bookmarks"
        :key="b.id"
        class="bookmark-btn"
        :class="{ on: b.page === currentPage, circle: !b.label }"
        @click="goBookmark(b)"
        :title="'Záložka na str. ' + (b.page + 1)"
      >
        <span class="bk-num">{{ b.page + 1 }}</span>
        <span v-if="b.label" class="bk-label">{{ b.label }}</span>
        <span class="bk-del" @click.stop="deleteBookmark(b)" title="Smazat záložku">✕</span>
      </button>
    </div>

    <!-- Slider stránek s miniaturami -->
    <div v-if="sliderOpen" class="slider-panel">
      <div class="thumb-strip" ref="thumbStripEl">
        <button
          v-for="i in totalPages"
          :key="i"
          class="thumb-item"
          :class="{ on: (i - 1) === pageSlider }"
          :data-idx="i - 1"
          @click="gotoPage(i - 1)"
          :title="'Stránka ' + i"
        >
          <img v-if="thumbs.get(i - 1)" :src="thumbs.get(i - 1)" alt="Stránka {{ i }}" />
          <div v-else class="thumb-loading">…</div>
          <span class="thumb-num">{{ i }}</span>
        </button>
      </div>
      <input
        type="range"
        class="slider"
        min="0"
        :max="totalPages - 1"
        step="1"
        :value="pageSlider"
        @input="onSliderInput($event)"
        @change="onSliderChange($event)"
      />
    </div>

    <!-- Plovoucí ovládací tlačítka (pravý okraj) — zobrazí se na povel (tap na střed) -->
    <div class="fab-col" v-if="controlsVisible || annotMode">
      <button class="fab" @click="toggleAnnot" :class="{ on: annotMode }" title="Anotace / listování">✏️</button>
      <button class="fab" @click="openBookmark" :class="{ on: bookmarkMode }" title="Přidat záložku na tuto stránku">🔖</button>
      <button class="fab" @click="toggleJumpMode" :class="{ on: jumpMode }" title="Vytvořit skok (Da Capo / VIDE)">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17L17 7"/><path d="M7 7h10v10"/></svg>
      </button>
    </div>

    <!-- Plovoucí panel anotací (jen v anotačním režimu) -->
    <div v-if="annotMode" class="annot-panel">
      <!-- Řádek 1: typ nástroje -->
      <div class="ap-row">
        <button class="ap-tool" @click="setTool('pencil')" :class="{ on: tool === 'pencil' }" title="Tužka">✏️</button>
        <button class="ap-tool" @click="setTool('highlighter')" :class="{ on: tool === 'highlighter' }" title="Zvýraznění">🖍️</button>
      </div>
      <!-- Řádek 2: barva -->
      <div class="ap-row">
        <button
          v-for="c in colors"
          :key="c"
          class="ap-color"
          :class="{ on: annotColor === c }"
          :style="{ background: c }"
          @click="annotColor = c"
          :title="'Barva'"
        ></button>
      </div>
      <!-- Řádek 3: velikost -->
      <div class="ap-row">
        <button
          v-for="s in sizes"
          :key="s"
          class="ap-size"
          :class="{ on: annotSize === s }"
          @click="annotSize = s"
          :title="'Velikost ' + s"
        ><span :style="{ width: s + 'px', height: s + 'px' }"></span></button>
      </div>
      <!-- Řádek 4: akce -->
      <div class="ap-row">
        <button class="ap-tool" @click="undoAnnot" title="Zpět" :disabled="!canUndo">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>
        </button>
        <button class="ap-tool" @click="redoAnnot" title="Dopředu" :disabled="!canRedo">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3L21 13"/></svg>
        </button>
        <button v-if="hasAnnotations" class="ap-tool" @click="clearAnnots" title="Smazat všechny anotace">🗑️</button>
      </div>
      <!-- Řádek 5: jen pero (palm-rejection) -->
      <div class="ap-row">
        <button class="ap-tool pen-only" @click="penOnly = !penOnly" :class="{ on: penOnly }" title="Kreslit jen perem (ignorovat dotyk rukou)">🖊️</button>
        <span class="ap-pen-label" @click="penOnly = !penOnly">Jen pero</span>
      </div>
    </div>

    <!-- Plovoucí zoom (levý okraj) — zobrazí se na povel (tap na střed) -->
    <div class="fab-col left" v-if="controlsVisible">
      <div class="zoom-val">{{ Math.round(zoom * 100) }}%</div>
      <button class="fab" @click="zoomIn" title="Přiblížit">+</button>
      <button class="fab" @click="zoomOut" title="Oddálit">−</button>
      <button class="fab" @click="resetView" title="Vycentrovat">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>
      </button>
      <button class="fab" @click="toggleSlider" :class="{ on: sliderOpen }" title="Slider stránek">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 3v18"/></svg>
      </button>
    </div>

    <!-- Plovoucí zpět (levý horní roh) -->
    <button class="fab back" @click="goBack" title="Zpět">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
    </button>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { dbGetSong, dbSaveAnnotations, dbGetAnnotations, dbGetGroup, dbGetAllSongs, dbGetJumps, dbSaveJumps, dbGetBookmarks, dbSaveBookmarks } from '../db.js';
import { renderPage, getPageWidthHeight, getPageCount } from '../pdf.js';

const props = defineProps({ id: { type: String, required: true } });
const router = useRouter();

// Skupina (setlist) — pokud je otevřeno přes skupinu, umožní plynulý přechod mezi notami
const group = ref(null);        // { id, name, songIds: [] }
const groupSongs = ref([]);     // načtené noty ve skupině (v pořadí)
const groupIndex = ref(-1);     // index aktuální noty ve skupině

const viewerEl = ref(null);
const canvasEl = ref(null);
const layerSvgEl = ref(null);
const thumbStripEl = ref(null);

const song = reactive({ data: null, name: '', fileName: '', id: props.id });

const totalPages = ref(0);
const currentPage = ref(0); // 0-based
const loading = ref(true);  // loading overlay při prvním načtení / přechodu mezi skladbami
const zoom = ref(1.0);     // výchozí zoom 100 % (1 = fit výšce)
const panX = ref(0);        // posun stránky (dvouprstý pan)
const panY = ref(0);

const annotMode = ref(false);
const tool = ref('pencil');
const activeStroke = ref(null);

// Rozšířené anotace
const colors = ['#1a1a1a', '#c05a4a', '#e5d7a6', '#f2c4b6', '#bcd3b6', '#a8c4e0', '#e5c9a8', '#d9b6d9', '#1a2a4a'];
const sizes = [2, 3, 4, 6, 8, 12];
const annotColor = ref('#1a1a1a'); // aktuální barva pera
const annotSize = ref(2);          // aktuální velikost pera (výchozí = nejmenší)
const history = ref([]);           // undo stack (kopie předchozích stavů items)
const redoStack = ref([]);         // redo stack
const canUndo = computed(() => history.value.length > 0);
const canRedo = computed(() => redoStack.value.length > 0);
const hasAnnotations = computed(() => annotations.value.items.length > 0);
const controlsVisible = ref(false); // ovládací tlačítka (zoom/anotace) — zobrazí se na tap na střed

const cssW = ref(800);
const cssH = ref(1100);
const baseFit = ref(1);
const annotations = ref({ items: [] });

// Slider stránek + miniatury
const pageSlider = ref(0);        // 0-based, vázaný na currentPage
const sliderOpen = ref(false);    // zobrazení slideru
const thumbs = reactive(new Map()); // pageIdx -> dataURL miniatury
const thumbPromises = new Map();    // pageIdx -> Promise (probíhající render miniatury)
let thumbObserver = null;           // IntersectionObserver pro lazy-load miniatur
let thumbDebounce = null;           // debounce pro rychlé tažení sliderem
let thumbQueue = [];                // fronta stránek čekajících na render miniatury
let thumbActive = 0;                // počet právě renderovaných miniatur
const THUMB_MAX_CONCURRENT = 2;     // max souběžných renderů miniatur

// Skoky (Da Capo / VIDE) — per skladba
const jumps = ref([]);            // [{id, fromPage, toPage, label}]
const jumpMode = ref(false);      // režim vytváření skoku
const jumpStart = ref(null);      // výchozí stránka (0-based) nebo null
const jumpEnd = ref(null);        // cílová stránka (0-based) nebo null
const jumpLabel = ref('');        // text tlačítka

// Záložky (konkrétní stránky) — per skladba
const bookmarks = ref([]);        // [{id, page, label}]
const bookmarkMode = ref(false);  // režim přidávání záložky
const bookmarkLabel = ref('');    // text záložky (volitelný)
const bookmarkEditing = ref(null); // id záložky, kterou upravujeme (null = nová)
const penOnly = ref(true);        // v anotaci kreslit jen perem (ignorovat dotyk prstem/rukou) — výchozí zapnuto

// Rozměry a stránka

const pageItems = computed(() => annotations.value.items.filter(i => i.page === currentPage.value));

// Skoky, které začínají na aktuální stránce
const currentJumps = computed(() => jumps.value.filter(j => j.fromPage === currentPage.value));

// Cache přednačtených stránek (canvasy) pro rychlé listování
const cached = reactive(new Map());      // pageIdx -> canvas
const preRendered = reactive(new Set()); // pageIdx, které jsou hotové
const renderPromises = new Map();        // pageIdx -> Promise (probíhající render)
const docMap = new Map();                 // songId -> offscreen doc cache (od pdf.js)
let renderToken = 0;                      // generační token: zruší zastaralé rendery při rychlém listování

const songName = computed(() => song.name || song.fileName || '');

function pathD(it) {
  return it.points.map((p, i) => (i === 0 ? `M${p.x},${p.y}` : `L${p.x},${p.y}`)).join(' ');
}

// --- Načtení ---
onMounted(async () => {
  const s = await dbGetSong(props.id);
  if (!s) { router.push('/'); return; }
  song.id = s.id; song.data = s.data; song.name = s.name; song.fileName = s.fileName;

  // Načíst skupinu (setlist) z query, pokud je otevřeno přes skupinu
  const gid = router.currentRoute.value.query.group;
  console.log('[group] query.group =', gid);
  if (gid) {
    const g = await dbGetGroup(gid);
    console.log('[group] dbGetGroup =', g);
    if (g && g.songIds.length) {
      group.value = g;
      const all = await dbGetAllSongs();
      groupSongs.value = g.songIds.map(id => all.find(x => x.id === id)).filter(Boolean);
      groupIndex.value = groupSongs.value.findIndex(x => x.id === props.id);
      console.log('[group] loaded, groupSongs =', groupSongs.value.length, 'groupIndex =', groupIndex.value);
    } else {
      console.log('[group] group null nebo bez skladeb');
    }
  }

  const dim = await getPageWidthHeight(song, 1);
  totalPages.value = await getPageCount(song);

  const saved = await dbGetAnnotations(props.id);
  if (saved && Array.isArray(saved.items)) annotations.value.items = saved.items;

  // Načíst skoky (Da Capo / VIDE)
  const savedJumps = await dbGetJumps(props.id);
  if (savedJumps && Array.isArray(savedJumps.items)) jumps.value = savedJumps.items;

  // Načíst záložky (konkrétní stránky)
  const savedBookmarks = await dbGetBookmarks(props.id);
  if (savedBookmarks && Array.isArray(savedBookmarks.items)) bookmarks.value = savedBookmarks.items;

  // Velikost stránky aby se vešla na výšku
  computeFit();
  await renderCurrent();
  loading.value = false; // první stránka vykreslena → skrýt loading
  window.addEventListener('resize', onResize);
  // Udržet displej zapnutý, dokud je prohlížeč otevřený (jako jiné appky)
  acquireWakeLock();
});

onUnmounted(() => {
  window.removeEventListener('resize', onResize);
  disconnectThumbObserver();
  releaseWakeLock();
});

// --- Screen Wake Lock: displej nezhasíná, dokud je prohlížeč otevřený ---
let wakeLock = null;
async function acquireWakeLock() {
  try {
    if ('wakeLock' in navigator) {
      wakeLock = await navigator.wakeLock.request('screen');
      // Pokud se wake lock ztratí (např. přepnutí karty), zkusit znovu
      wakeLock.addEventListener('release', () => { wakeLock = null; });
    }
  } catch (err) {
    console.warn('Wake Lock nelze aktivovat', err);
  }
}
function releaseWakeLock() {
  if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; }
}

let availW = 800, availH = 1100;

function computeFit() {
  const el = viewerEl.value;
  if (el) {
    availH = Math.max(200, el.clientHeight - 12);
    availW = Math.max(200, el.clientWidth - 12);
  }
}

async function renderCurrent() {
  const doc = song.data;
  if (!doc) return;
  // Nárok na tuto generaci renderu — při rychlém listování se starší render zruší
  const myToken = ++renderToken;
  const page = currentPage.value;
  const dim = await getPageWidthHeight(song, page + 1);
  if (myToken !== renderToken) return; // mezitím se listovalo dál
  const ar = dim.width / dim.height;
  // Fit na šířku: vyplnit šířku, výška se může oříznout
  const w = availW;
  const h = w / ar;
  cssW.value = Math.round(w);
  cssH.value = Math.round(h);
  await nextTick();
  if (myToken !== renderToken) return;
  // Render vždy do offscreen canvasu, pak zkopírovat na viditelný.
  // Dva souběžné rendery tak nikdy nepíšou do stejného canvasu.
  const off = getOrCreateCacheCanvas(page, w, h);
  if (!preRendered.has(page)) {
    const pending = renderPromises.get(page);
    if (pending) {
      await pending;
      if (myToken !== renderToken) return;
    } else {
      const p = renderPage(song, page + 1, off, h).then(() => {
        preRendered.add(page);
        renderPromises.delete(page);
      });
      renderPromises.set(page, p);
      await p;
      if (myToken !== renderToken) return;
    }
  }
  // Zkopírovat offscreen canvas na viditelný (scalovaně podle dpr)
  const ctx = canvasEl.value.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  canvasEl.value.width = Math.round(cssW.value * dpr);
  canvasEl.value.height = Math.round(cssH.value * dpr);
  canvasEl.value.style.width = cssW.value + 'px';
  canvasEl.value.style.height = cssH.value + 'px';
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.drawImage(off, 0, 0, canvasEl.value.width, canvasEl.value.height);
  prefetchSiblings(page);
}

// Přednačtení sousedních stránek do offscreen cache, aby listování nečekalo
async function prefetchSiblings(center) {
  const doc = song.data;
  if (!doc) return;
  for (const i of [center - 1, center + 1, center - 2, center + 2]) {
    if (i < 0 || i >= totalPages.value) continue;
    if (preRendered.has(i)) continue;
    if (renderPromises.has(i)) continue; // už probíhá
    // Cache canvas musí mít rozměry TÉ stránky (jiný poměr stran → při kopírování by se natáhlo/ořízlo)
    const dim = await getPageWidthHeight(song, i + 1);
    const ar = dim.width / dim.height;
    const w = availW;
    const h = w / ar;
    const off = getOrCreateCacheCanvas(i, w, h);
    const p = renderPage(song, i + 1, off, h).then(() => {
      preRendered.add(i);
      renderPromises.delete(i);
    });
    renderPromises.set(i, p);
  }
}

function getOrCreateCacheCanvas(i, w, h) {
  if (cached.has(i)) return cached.get(i);
  const c = document.createElement('canvas');
  c.width = Math.round(w);
  c.height = Math.round(h);
  cached.set(i, c);
  return c;
}

function onResize() { computeFit(); renderCurrent(); }

// Vyčistí viditelný canvas — při přechodu na novou stránku se nezobrazuje stará
function clearCanvas() {
  const c = canvasEl.value;
  if (!c) return;
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, c.width, c.height);
}

function gotoPage(i) {
  if (i < 0 || i >= totalPages.value || i === currentPage.value) return;
  currentPage.value = i;
  pageSlider.value = i;
  panX.value = 0; panY.value = 0; // nová stránka = bez posunu
  // Okamžitá navigace: vyčistit canvas (nezobrazovat starou stránku) a
  // spustit render na pozadí. NEčekáme na dokončení — při rychlém listování
  // by se každý tap zablokoval. Token v renderCurrent zajistí, že se vykreslí
  // jen ta poslední požadovaná stránka.
  clearCanvas();
  renderCurrent();
}

// --- Slider stránek + miniatury ---
function toggleSlider() {
  sliderOpen.value = !sliderOpen.value;
  if (sliderOpen.value) {
    annotMode.value = false; // jiný panel → vypnout anotaci
    pageSlider.value = currentPage.value;
    // Přednačíst miniatury okolí aktuální stránky
    for (let i = Math.max(0, currentPage.value - 3); i <= Math.min(totalPages.value - 1, currentPage.value + 3); i++) {
      ensureThumb(i);
    }
    // Po vykreslení pásu miniatur posunout na aktuální stránku a zapojit lazy-load
    nextTick(() => {
      const strip = thumbStripEl.value;
      if (strip) {
        const item = strip.children[currentPage.value];
        if (item) item.scrollIntoView({ inline: 'center', block: 'nearest' });
        setupThumbObserver(strip);
      }
    });
  } else {
    disconnectThumbObserver();
    // Při zavření slideru zrušit čekající miniatury (rychlé tažení na konec
    // by jinak nechalo ve frontě stovky stránek, které se pak zbytečně renderují)
    if (thumbDebounce) { clearTimeout(thumbDebounce); thumbDebounce = null; }
    thumbQueue = [];
  }
}
// Lazy-load miniatur: načte se, když se miniatura přiblíží do viewportu pásu
function setupThumbObserver(strip) {
  disconnectThumbObserver();
  if (!('IntersectionObserver' in window)) return;
  thumbObserver = new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (en.isIntersecting) {
        const idx = Number(en.target.dataset.idx);
        ensureThumb(idx);
        thumbObserver.unobserve(en.target);
      }
    }
  }, { root: strip, rootMargin: '200px' });
  for (const child of strip.children) {
    if (!thumbs.has(Number(child.dataset.idx))) thumbObserver.observe(child);
  }
}
function disconnectThumbObserver() {
  if (thumbObserver) { thumbObserver.disconnect(); thumbObserver = null; }
}
// Slidování → živý náhled (hodnota + miniatura), bez navigace.
// Debounce: při rychlém tažení se renderuje jen POSLEDNÍ pozice, ne každá mezilehlá.
function onSliderInput(e) {
  const v = Math.round(Number(e.target.value));
  pageSlider.value = v;
  scrollThumbIntoView(v);
  if (thumbDebounce) clearTimeout(thumbDebounce);
  thumbDebounce = setTimeout(() => {
    thumbDebounce = null;
    ensureThumb(v);
  }, 120);
}
// Puštění slideru → skočit na přesně trefenou stránku (change střílí s finální hodnotou)
async function onSliderChange(e) {
  const v = Math.round(Number(e.target.value));
  const target = Math.max(0, Math.min(totalPages.value - 1, v));
  pageSlider.value = target;
  await gotoPage(target);
}
// Posunout pás miniatur tak, aby byla aktuální miniatura na očích
function scrollThumbIntoView(idx) {
  const strip = thumbStripEl.value;
  if (!strip) return;
  const item = strip.children[idx];
  if (item) item.scrollIntoView({ inline: 'center', block: 'nearest' });
}
// Zajistit miniaturu stránky (render do malého canvasu → dataURL).
// Fronta s omezením souběžnosti — při rychlém tažení sliderem se nespustí
// stovky renderů najednou (to dřív zahltilo paměť a shodilo appku).
function ensureThumb(i) {
  if (i < 0 || i >= totalPages.value) return;
  if (thumbs.has(i)) return;
  if (thumbPromises.has(i)) return;
  if (thumbQueue.includes(i)) return;
  thumbQueue.push(i);
  pumpThumbQueue();
}

function pumpThumbQueue() {
  while (thumbActive < THUMB_MAX_CONCURRENT && thumbQueue.length > 0) {
    const i = thumbQueue.shift();
    thumbActive++;
    const p = renderThumb(i).finally(() => {
      thumbActive--;
      thumbPromises.delete(i);
      pumpThumbQueue();
    });
    thumbPromises.set(i, p);
  }
}

async function renderThumb(i) {
  const c = document.createElement('canvas');
  // Miniatura ~ 120px na šířku
  const dim = await getPageWidthHeight(song, i + 1);
  const ar = dim.width / dim.height;
  const w = 120;
  const h = w / ar;
  await renderPage(song, i + 1, c, h);
  thumbs.set(i, c.toDataURL('image/jpeg', 0.7));
}

// Přepnutí na jinou skladbu ve skupině (setlist)
// toEnd = true → skočit na POSLEDNÍ stránku (při zpětném listování), jinak na první
async function switchSong(idx, toEnd) {
  const s = groupSongs.value[idx];
  if (!s) return;
  // Okamžitě uložit anotace aktuální skladby (jinak by se debounce odpálil až po přepnutí
  // a uložil by B-čkové items pod B-čkový song.id → A-čková anotace by se ztratila)
  await flushAnnotations();
  // načíst novou skladbu
  song.id = s.id; song.data = s.data; song.name = s.name; song.fileName = s.fileName;
  groupIndex.value = idx;
  panX.value = 0; panY.value = 0;
  zoom.value = 1.0;
  // vyčistit cache a anotace
  cached.clear(); preRendered.clear(); renderPromises.clear();
  thumbs.clear(); thumbPromises.clear(); sliderOpen.value = false; disconnectThumbObserver();
  if (thumbDebounce) { clearTimeout(thumbDebounce); thumbDebounce = null; }
  thumbQueue = [];
  loading.value = true; // loading overlay při přechodu mezi skladbami
  const saved = await dbGetAnnotations(s.id);
  annotations.value.items = (saved && Array.isArray(saved.items)) ? saved.items : [];
  totalPages.value = await getPageCount(song);
  currentPage.value = toEnd ? totalPages.value - 1 : 0;
  await renderCurrent();
  loading.value = false;
}

// Plynulý přechod: na poslední stránce dopředu → další skladba, na první dozadu → předchozí
async function nextPage() {
  if (currentPage.value < totalPages.value - 1) {
    await gotoPage(currentPage.value + 1);
  } else if (group.value && groupIndex.value < groupSongs.value.length - 1) {
    await switchSong(groupIndex.value + 1);
  }
}
async function prevPage() {
  if (currentPage.value > 0) {
    await gotoPage(currentPage.value - 1);
  } else if (group.value && groupIndex.value > 0) {
    await switchSong(groupIndex.value - 1, true); // zpět → konec předchozí skladby
  }
}

// Přímé přepnutí na předchozí/další skladbu (tlačítka) — vždy na první stránku skladby
async function prevSong() {
  if (group.value && groupIndex.value > 0) await switchSong(groupIndex.value - 1);
}
async function nextSong() {
  if (group.value && groupIndex.value < groupSongs.value.length - 1) await switchSong(groupIndex.value + 1);
}

// --- Swipe / tap / pinch / pan pro přepínání stránek, zoom a posun ---
let _touchStart = null;
let _pinchDist = null;
let _pinchMid = null; // střed dvou prstů (pro pan)
function onTouchStart(e) {
  if (annotMode.value) return; // v anotaci swipe nekreslí listování
  if (e.touches.length === 2) {
    _pinchDist = dist(e.touches[0], e.touches[1]);
    _pinchMid = mid(e.touches[0], e.touches[1]);
    _touchStart = null;
    return;
  }
  if (e.touches.length === 1) {
    const t = e.touches[0];
    _touchStart = { x: t.clientX, y: t.clientY, t: Date.now() };
  }
}
function onTouchMove(e) {
  if (annotMode.value) return;
  if (e.touches.length === 2 && _pinchDist) {
    const d = dist(e.touches[0], e.touches[1]);
    const ratio = d / _pinchDist;
    _pinchDist = d;
    // zoom s minimem na výchozí (1)
    zoom.value = Math.min(3.5, Math.max(1, zoom.value * ratio));
    // pan: posun středu dvou prstů
    const m = mid(e.touches[0], e.touches[1]);
    panX.value += m.x - _pinchMid.x;
    panY.value += m.y - _pinchMid.y;
    _pinchMid = m;
    return;
  }
}
function onTouchEnd(e) {
  if (annotMode.value) return;
  _pinchDist = null;
  _pinchMid = null;
  if (!_touchStart) return;
  const t = e.changedTouches[0];
  const dx = t.clientX - _touchStart.x;
  const dy = t.clientY - _touchStart.y;
  const dt = Date.now() - _touchStart.t;
  const tapped = Math.abs(dx) < 20 && Math.abs(dy) < 20 && dt < 400;
  _touchStart = null;
  if (tapped) return; // tap řeší onTap
  if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) {
    if (dx < 0) nextPage(); // swipe vlevo → další stránka/nota
    else prevPage();        // swipe vpravo → předchozí stránka/nota
  }
}
function dist(a, b) {
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
}
function mid(a, b) {
  return { x: (a.clientX + b.clientX) / 2, y: (a.clientY + b.clientY) / 2 };
}

// Tap: okraje → listování, střed → zobrazit/skrýt ovládací prvky (jen mimo anotaci a tlačítka)
function onTap(e) {
  if (annotMode.value) return;
  if (e.target.closest('button')) return; // plovoucí tlačítka necháme bez stránkování
  const el = viewerEl.value;
  if (!el) return;
  const x = e.clientX - el.getBoundingClientRect().left;
  const half = el.clientWidth / 2;
  const edge = el.clientWidth * 0.2; // 20 % od okraje = listování
  if (x < edge) prevPage();
  else if (x > el.clientWidth - edge) nextPage();
  else controlsVisible.value = !controlsVisible.value; // střed = povel pro ovládací prvky
}

// --- Anotace ---
function toggleAnnot() {
  annotMode.value = !annotMode.value;
  if (annotMode.value) { jumpMode.value = false; bookmarkMode.value = false; sliderOpen.value = false; } // jiné panely zavřít
}
function setTool(t) { tool.value = t; annotMode.value = true; jumpMode.value = false; bookmarkMode.value = false; sliderOpen.value = false; }

function toLayerCoords(e) {
  const svg = layerSvgEl.value;
  const rect = svg.getBoundingClientRect();
  const scale = cssW.value / rect.width; // zoom korekce
  const clientX = e.touches ? e.touches[0].clientX : e.clientX;
  const clientY = e.touches ? e.touches[0].clientY : e.clientY;
  return {
    x: (clientX - rect.left) * scale,
    y: (clientY - rect.top) * scale,
  };
}

function onLayerDown(e) {
  if (!annotMode.value) return;
  // Pen-only mód: ignorovat dotyk prstem/rukou (palm-rejection), kreslit jen stylusem
  if (penOnly.value && e.pointerType !== 'pen') return;
  if (_activePointerId !== null) return; // už kreslí jiný tah (např. druhá ruka)
  _activePointerId = e.pointerId;
  const p = toLayerCoords(e);
  const w = tool.value === 'highlighter' ? annotSize.value * 2 : annotSize.value;
  activeStroke.value = {
    id: crypto.randomUUID(),
    page: currentPage.value,
    tool: tool.value,
    color: tool.value === 'highlighter' ? annotColor.value + '55' : annotColor.value,
    width: w,
    points: [p],
  };
  _prev = p;
}
let _prev = null;
let _activePointerId = null;
function onLayerMove(e) {
  if (!activeStroke.value) return;
  if (_activePointerId !== e.pointerId) return; // jiný tah (druhá ruka) — nekreslit
  const p = toLayerCoords(e);
  const prev = _prev;
  if (!prev || Math.abs(p.x - prev.x) > 1 || Math.abs(p.y - prev.y) > 1) {
    activeStroke.value.points.push(p); _prev = p;
  }
}
function onLayerUp(e) {
  if (!activeStroke.value) return;
  if (_activePointerId !== e.pointerId) return;
  _activePointerId = null;
  // Maličká/rychá poznámka: tah s pouhým 1 bodem je při kreslení prakticky neviditelný
  // a užívala se s tím, že se nic nezaznamená. Přidáme drobnou stopu podél směru tahu.
  if (activeStroke.value.points.length < 2) {
    const p = toLayerCoords(e);
    activeStroke.value.points.push(p);
  }
  pushHistory();
  annotations.value.items.push(activeStroke.value);
  activeStroke.value = null;
  saveAnnotations();
}

function clearAnnots() {
  if (confirm('Smazat všechny anotace?')) {
    pushHistory();
    annotations.value.items = [];
    saveAnnotations();
  }
}

// History (undo/redo)
function pushHistory() {
  history.value.push(JSON.parse(JSON.stringify(annotations.value.items)));
  if (history.value.length > 50) history.value.shift();
  redoStack.value = []; // nový tah vymaže redo
}
function undoAnnot() {
  if (history.value.length === 0) return;
  redoStack.value.push(JSON.parse(JSON.stringify(annotations.value.items)));
  annotations.value.items = history.value.pop();
  saveAnnotations();
}
function redoAnnot() {
  if (redoStack.value.length === 0) return;
  history.value.push(JSON.parse(JSON.stringify(annotations.value.items)));
  annotations.value.items = redoStack.value.pop();
  saveAnnotations();
}

// zoom — vždy po 5 % (sčítání, ne násobení → pravidelné a symetrické kroky)
function zoomIn() { zoom.value = Math.min(zoom.value + 0.05, 2.5); }
function zoomOut() { zoom.value = Math.max(zoom.value - 0.05, 1); }
function resetView() { zoom.value = 1.15; panX.value = 0; panY.value = 0; }

// save
let saveTimer = null;
function saveAnnotations() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => flushAnnotations(), 200);
}
// Okamžité uložení (bez debounce) — volá se před přepnutím skladby
async function flushAnnotations() {
  clearTimeout(saveTimer);
  saveTimer = null;
  await dbSaveAnnotations({ songId: song.id, items: annotations.value.items });
}

function goBack() { router.push('/'); }

// --- Skoky (Da Capo / VIDE) ---
function toggleJumpMode() {
  jumpMode.value = !jumpMode.value;
  if (jumpMode.value) annotMode.value = false; // jiný panel → vypnout anotaci
  if (!jumpMode.value) { jumpStart.value = null; jumpEnd.value = null; jumpLabel.value = ''; }
}
// Krok 1: označit výchozí stránku (kde skok začíná)
function setJumpStart() {
  jumpStart.value = currentPage.value;
  jumpEnd.value = null;
}
// Krok 2: označit cílovou stránku (kam skok vede)
function setJumpEnd() {
  if (jumpStart.value === null) return;
  jumpEnd.value = currentPage.value;
}
// Krok 3: uložit skok pod tlačítko s textem
async function saveJump() {
  if (jumpStart.value === null || jumpEnd.value === null) return;
  const label = jumpLabel.value.trim() || `Skok ${jumps.value.length + 1}`;
  jumps.value.push({ id: crypto.randomUUID(), fromPage: jumpStart.value, toPage: jumpEnd.value, label });
  await dbSaveJumps({ songId: song.id, items: jumps.value });
  jumpMode.value = false; jumpStart.value = null; jumpEnd.value = null; jumpLabel.value = '';
}
// Kliknutí na tlačítko skoku → skočit na cílovou stránku
async function goJump(j) {
  await gotoPage(j.toPage);
}
async function deleteJump(j) {
  if (confirm(`Smazat skok „${j.label}"?`)) {
    jumps.value = jumps.value.filter(x => x.id !== j.id);
    await dbSaveJumps({ songId: song.id, items: jumps.value });
  }
}

// --- Záložky (konkrétní stránky) ---
function openBookmark() {
  bookmarkMode.value = true;
  annotMode.value = false; // jiný panel → vypnout anotaci
  bookmarkLabel.value = '';
  bookmarkEditing.value = null;
}
async function saveBookmark() {
  const label = bookmarkLabel.value.trim();
  if (bookmarkEditing.value) {
    const b = bookmarks.value.find(x => x.id === bookmarkEditing.value);
    if (b) b.label = label; // úprava: jen text, stránka zůstává
  } else {
    if (bookmarks.value.some(x => x.page === currentPage.value)) { openBookmark(); return; }
    bookmarks.value.push({ id: crypto.randomUUID(), page: currentPage.value, label });
  }
  await dbSaveBookmarks({ songId: song.id, items: bookmarks.value }); // ruční pořadí
  bookmarkMode.value = false;
  bookmarkLabel.value = '';
  bookmarkEditing.value = null;
}
function startEditBookmark(b) {
  bookmarkEditing.value = b.id;
  bookmarkLabel.value = b.label || '';
}
function moveBookmark(b, dir) {
  const i = bookmarks.value.findIndex(x => x.id === b.id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= bookmarks.value.length) return;
  [bookmarks.value[i], bookmarks.value[j]] = [bookmarks.value[j], bookmarks.value[i]];
  dbSaveBookmarks({ songId: song.id, items: bookmarks.value });
}
async function goBookmark(b) {
  await gotoPage(b.page);
}
async function deleteBookmark(b) {
  if (confirm(`Smazat záložku „${b.label || 'str. ' + (b.page + 1)}"?`)) {
    bookmarks.value = bookmarks.value.filter(x => x.id !== b.id);
    await dbSaveBookmarks({ songId: song.id, items: bookmarks.value });
  }
}
</script>

<style scoped>
.viewer {
  flex: 1; position: relative; overflow: hidden;
  height: 100%; /* deterministická výška → absolutní kotvy (záložky dole, zpět nahoře) kotví proti celé ploše */
  background: var(--bg); display: flex; align-items: center; justify-content: center;
  touch-action: pan-x pan-y;
}
.stage { position: relative; }
.pdf-canvas { display: block; background: #fff; box-shadow: 0 2px 14px rgba(0,0,0,0.6); border-radius: 6px; }
.annot-layer { position: absolute; top: 0; left: 0; touch-action: none; cursor: crosshair; }
.annot-layer.active { pointer-events: auto; }
.annot-layer.active + .stage {  }
.annot-layer:not(.active) { pointer-events: none; }
.annot-layer .hl { mix-blend-mode: multiply; opacity: 0.9; }

.page-ind {
  position: absolute; top: 14px; left: 50%; transform: translateX(-50%);
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 20px;
  padding: 6px 14px; font-size: 0.9rem; color: var(--text-dim);
  display: flex; gap: 8px; align-items: center; max-width: 60vw; white-space: nowrap;
}
.ind-song { color: var(--text); font-weight: 600; overflow: hidden; text-overflow: ellipsis; }

/* Přepínání not ve skupině */
.nav-strip {
  position: absolute; bottom: 24px; right: 16px;
  display: flex; align-items: center; gap: 10px; z-index: 20;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 28px;
  padding: 6px 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.5);
}
.nav-btn {
  width: 40px; height: 40px; border-radius: 50%;
  border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  touch-action: manipulation; padding: 0;
}
.nav-btn:disabled { opacity: 0.3; pointer-events: none; }
.nav-label {
  color: var(--text); font-size: 0.95rem; font-weight: 600;
  min-width: 44px; text-align: center; padding: 0 4px;
}

/* Skoky (Da Capo / VIDE) — vpravo, pod tlačítkem Jump menu, výrazně barevné */
.jump-strip {
  position: absolute; right: 16px; top: calc(50% + 67px);
  display: flex; flex-direction: column; align-items: flex-end; gap: 8px; z-index: 20;
  pointer-events: none;
}
.jump-btn {
  background: var(--accent); border: 1px solid var(--accent);
  border-radius: 24px; padding: 12px 22px; font-size: 1rem; font-weight: 700;
  color: #17130f; cursor: pointer;
  box-shadow: 0 4px 14px rgba(0,0,0,0.5);
  touch-action: manipulation; pointer-events: auto;
}
.jump-btn:active { background: var(--bg-elev2); border-color: var(--border); color: var(--text); }

.jump-panel {
  position: absolute; bottom: 92px; left: 16px;
  display: flex; flex-direction: column; gap: 8px;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 16px;
  padding: 12px; box-shadow: 0 4px 18px rgba(0,0,0,0.6); z-index: 25; max-width: 94vw;
}
.jp-title { font-weight: 700; font-size: 0.95rem; }
.jp-row { display: flex; gap: 8px; align-items: center; }
.jp-btn {
  background: var(--bg-elev2); border: 1px solid var(--border);
  border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; color: var(--text); cursor: pointer;
  touch-action: manipulation;
}
.jp-btn.on { border-color: var(--accent); background: var(--bg-elev); }
.jp-btn.primary { background: var(--accent); color: #17130f; border-color: var(--accent); font-weight: 600; }
.jp-btn:disabled { opacity: 0.35; pointer-events: none; }
.jp-input {
  flex: 1; min-width: 0; background: var(--bg-elev2); border: 1px solid var(--border);
  border-radius: 10px; padding: 8px 10px; color: var(--text); font-size: 0.9rem;
}
.jp-close { background: var(--bg-elev2); border: 1px solid var(--border); border-radius: 10px; padding: 8px; color: var(--text); cursor: pointer; }
.jp-cur { color: var(--text); font-size: 0.9rem; font-weight: 600; }

/* Záložky — vždy viditelná lišta u spodní hrany */
.bookmark-strip {
  position: absolute; left: 16px; right: 16px; bottom: 10px;
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  justify-content: flex-start; z-index: 22;
  pointer-events: none;
}
.bookmark-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--bg-elev); border: 1px solid var(--border);
  border-radius: 20px; padding: 6px 12px;
  font-size: 0.92rem; font-weight: 600; color: var(--text);
  cursor: pointer; touch-action: manipulation; pointer-events: auto;
  box-shadow: 0 3px 12px rgba(0,0,0,0.4);
}
.bookmark-btn.circle {
  border-radius: 50%;
  width: 38px; height: 38px; padding: 0;
  justify-content: center;
}
.bookmark-btn.on { border-color: var(--accent); background: var(--bg-elev2); }
.bookmark-btn:active { background: var(--bg-elev2); }
.bk-num {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 22px; height: 22px; padding: 0 4px;
  background: var(--accent); color: #17130f; border-radius: 50%;
  font-size: 0.8rem; font-weight: 700;
}
.bk-label { max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bk-del { color: var(--text-dim); font-size: 0.9rem; padding: 0 2px; cursor: pointer; }
.bk-del:active { color: var(--text); }

.jp-actions { margin-left: auto; display: flex; align-items: center; gap: 2px; }
.jp-moves { display: flex; align-items: center; gap: 0; }
.jp-icon {
  width: 32px; height: 32px; flex: 0 0 auto; padding: 0;
  background: transparent; border: none; border-radius: 50%;
  color: var(--text-dim); display: flex; align-items: center; justify-content: center;
  cursor: pointer; touch-action: manipulation;
}
.jp-icon:active { color: var(--text); }
.jp-icon.del:active { color: var(--danger); }
.jp-icon:disabled { opacity: 0.3; pointer-events: none; }

.ap-pen-label { color: var(--text-dim); font-size: 0.85rem; cursor: pointer; }
.ap-tool.pen-only.on { border-color: var(--accent); }

/* Slider stránek s miniaturami — přes celou šířku */
.slider-panel {
  position: absolute; bottom: 20px; left: 0; right: 0;
  display: flex; flex-direction: column; gap: 10px;
  background: var(--bg-elev); border-top: 1px solid var(--border);
  padding: 12px 25px 16px; box-shadow: 0 -4px 18px rgba(0,0,0,0.6); z-index: 30;
}
.thumb-strip {
  display: flex; gap: 8px; overflow-x: auto; padding: 0;
  scrollbar-width: thin; -webkit-overflow-scrolling: touch;
}
.thumb-item {
  position: relative; flex: 0 0 auto; width: 72px; height: 96px;
  border-radius: 6px; overflow: hidden; border: 2px solid var(--border);
  background: #fff; padding: 0; cursor: pointer; touch-action: manipulation;
}
.thumb-item.on { border-color: var(--accent); }
.thumb-item img { display: block; width: 100%; height: 100%; object-fit: contain; }
.thumb-loading { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-dim); font-size: 0.9rem; }
.thumb-num {
  position: absolute; bottom: 2px; right: 2px;
  background: rgba(0,0,0,0.7); color: #fff; font-size: 0.7rem; font-weight: 600;
  padding: 1px 5px; border-radius: 8px;
}
.slider { width: calc(100% - 24px); margin: 0 12px; accent-color: var(--accent); }
.jp-list { display: flex; flex-direction: column; gap: 6px; border-top: 1px solid var(--border); padding-top: 10px; }
.jp-subtitle { font-size: 0.85rem; font-weight: 600; color: var(--text-dim); }
.jp-item {
  display: flex; align-items: center; gap: 8px;
  background: var(--bg-elev2); border: 1px solid var(--border); border-radius: 10px; padding: 8px 10px;
}
.jp-item-label { font-weight: 600; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.jp-item-pages { color: var(--text-dim); font-size: 0.8rem; white-space: nowrap; }
.jp-del {
  margin-left: auto; width: 30px; height: 30px; flex: 0 0 auto; border-radius: 50%;
  border: 1px solid var(--border); background: var(--bg-elev); color: var(--danger);
  display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 0.9rem;
}

/* Plovoucí tlačítka */
.fab-col {
  position: absolute; right: 16px; top: 50%; transform: translateY(-50%);
  display: flex; flex-direction: column; align-items: center; gap: 10px; z-index: 20;
}
.fab-col.left { right: auto; left: 16px; }
.fab {
  width: 52px; height: 52px; border-radius: 50%;
  border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); font-size: 1.3rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 14px rgba(0,0,0,0.5);
  touch-action: manipulation;
}
.fab.on { background: var(--accent); color: #17130f; border-color: var(--accent); }
.fab-col.left .zoom-val { color: var(--text-dim); font-size: 0.85rem; text-align: center; width: 52px; height: 52px; display: flex; align-items: center; justify-content: center; }
.fab.back {
  position: absolute; top: 14px; left: 16px;
  width: 48px; height: 48px; border-radius: 50%;
  padding: 0; display: flex; align-items: center; justify-content: center;
}

/* Plovoucí panel anotací — řádky, zarovnáno doleva */
.annot-panel {
  position: absolute; bottom: 92px; left: 16px;
  display: flex; flex-direction: column; align-items: flex-start; gap: 8px;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 16px;
  padding: 10px; box-shadow: 0 4px 18px rgba(0,0,0,0.6);
  z-index: 25; max-width: 94vw;
}
.ap-row { display: flex; align-items: center; gap: 6px; }
.ap-tool {
  width: 34px; height: 34px; flex: 0 0 auto; min-width: 0; padding: 0;
  border-radius: 50%; box-sizing: border-box;
  border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); font-size: 1rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  touch-action: manipulation;
}
.ap-tool.on { background: var(--accent); color: #17130f; border-color: var(--accent); }
.ap-tool:disabled { opacity: 0.35; pointer-events: none; }
.ap-color {
  width: 26px; height: 26px; flex: 0 0 auto; min-width: 0; padding: 0;
  border-radius: 50%; box-sizing: border-box;
  border: 2px solid var(--border); cursor: pointer;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}
.ap-color.on { border-color: var(--accent); }
.ap-size {
  width: 30px; height: 30px; flex: 0 0 auto; min-width: 0; padding: 0;
  border-radius: 50%; box-sizing: border-box;
  border: 1px solid var(--border); background: var(--bg-elev2);
  display: flex; align-items: center; justify-content: center; cursor: pointer;
}
.ap-size span { border-radius: 50%; background: var(--text); display: block; flex: 0 0 auto; }
.ap-size.on { border-color: var(--accent); }

/* Loading overlay při prvním načtení / přechodu mezi skladbami */
.viewer-loading {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px;
  background: var(--bg);
  z-index: 30;
}
.viewer-loading .spinner {
  width: 40px; height: 40px; border-radius: 50%;
  border: 3px solid var(--bg-elev2); border-top-color: var(--accent);
  animation: spin 0.9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { color: var(--text-dim); font-size: 0.95rem; }
</style>
