<template>
  <div class="viewer" ref="viewerEl">
    <!-- Toolbar -->
    <div class="toolbar" :class="{ hiding: hideToolbar }">
      <button class="back" @click="goBack">Zpět</button>
      <div class="title">{{ songName }}</div>
      <div class="controls">
        <span class="page-ind">{{ currentPage }}/{{ totalPages }}</span>
        <button class="icon" @mousedown.prevent @click="zoomOut">−</button>
        <button class="icon" @mousedown.prevent @click="zoomIn">+</button>
        <span class="zoom-val">{{ Math.round(zoom * baseFit) }}%</span>
        <button
          v-if="!pencilOnly"
          class="icon"
          :class="{ active: tool === 'pencil' }"
          @click="setTool('pencil')"
          title="Tužka"
        >✏️</button>
        <button
          v-if="!pencilOnly"
          class="icon"
          :class="{ active: tool === 'highlighter' }"
          @click="setTool('highlighter')"
          title="Zvýraznění"
        >🖍️</button>
        <button class="icon" @click="clearAnnots" title="Smazat anotace">🗑️</button>
      </div>
    </div>

    <!-- Scrollovatelné pásmo stránek -->
    <div
      ref="drawEl"
      class="draw-area"
      @scroll="onScroll"
      @touchstart.passive="onTouchStart"
      @touchmove.passive="onTouchMove"
      @touchend.passive="onTouchEnd"
    >
      <div class="spacer-top" :style="{ height: headPad + 'px' }"></div>

      <div
        v-for="idx in pageIndices"
        :key="idx"
        class="pdf-page-wrap"
        :style="{ width: pageW + 'px', height: pageH + 'px' }"
      >
        <canvas ref="pageCanvas" :data-page="idx" />
        <!-- Anotační vrstva nad PDF -->
        <svg
          ref="layerSvg"
          class="annot-layer"
          :data-page="idx"
          :width="pageW"
          :height="pageH"
          @mousedown.prevent="onLayerPointerDown($event, idx)"
          @mousemove.prevent="onLayerPointerMove($event, idx)"
          @mouseup.stop="onLayerPointerUp"
          @mouseleave="onLayerPointerUp"
          @touchstart.passive="onLayerPointerDown($event, idx)"
          @touchmove.passive="onLayerPointerMove($event, idx)"
          @touchend.passive="onLayerPointerUp"
        >
          <!-- Překreslené anotace -->
          <g v-for="it in pageItems(idx)" :key="it.id">
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
            v-if="activeStroke && activeStroke.page === idx"
            :d="pathD(activeStroke)"
            fill="none"
            :stroke="activeStroke.color"
            :stroke-width="activeStroke.width"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </div>

      <div class="spacer-bottom" :style="{ height: headPad + 'px' }"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { dbGetSong, dbSaveAnnotations, dbGetAnnotations } from '../db.js';
import { renderPage, getPageWidthHeight, getPageCount } from '../pdf.js';

const props = defineProps({ id: { type: String, required: true } });
const router = useRouter();

const viewerEl = ref(null);
const drawEl = ref(null);
const pageCanvas = ref([]);
const layerSvg = ref([]);

const song = reactive({ data: null, name: '', fileName: '', id: props.id });
const totalPages = ref(0);
const currentPage = ref(1);
const pageW = ref(800);
const pageH = ref(1100);
const zoom = ref(1);            // násobitel
const baseFit = ref(1);         // kolikrát je zoom=1 oproti šířce
const tool = ref('pencil');     // 'pencil' | 'highlighter'
const pencilOnly = ref(false);
const hideToolbar = ref(false);
const headPad = ref(0);

const pageIndices = computed(() => Array.from({ length: totalPages.value }, (_, i) => i));
const rendered = reactive(new Set());

const annotations = reactive({ items: [] }); // items: {id,page,tool,color,width,points:[{x,y}]}
const activeStroke = ref(null);

const songName = computed(() => song.name || song.fileName || '');
const zoomPct = computed(() => Math.round(zoom.value * baseFit.value));

// --- Načtení ---
onMounted(async () => {
  const s = await dbGetSong(props.id);
  if (!s) { router.push('/'); return; }
  song.data = s.data; song.name = s.name; song.fileName = s.fileName;

  const dim = await getPageWidthHeight(song, 1);
  // Velikost stránky v CSS px — odvozeno od šířky prohlížeče pro "fit"
  const avail = Math.max(320, drawEl.value.clientWidth || 800);
  baseFit.value = avail / dim.width;
  pageH.value = Math.round(dim.height * baseFit.value);
  pageW.value = Math.round(dim.width * baseFit.value);

  totalPages.value = await getPageCount(song);
  pencilOnly.value = totalPages.value > 1;

  const saved = await dbGetAnnotations(props.id);
  if (saved && Array.isArray(saved.items)) annotations.items = saved.items;

  await nextTick();
  prime();
  window.addEventListener('resize', onResize);
});

onUnmounted(() => window.removeEventListener('resize', onResize));

// --- Virtualizace renderu ---
function visible() {
  const el = drawEl.value;
  if (!el) return [];
  const st = el.scrollTop, ch = el.clientHeight;
  const per = pageH.value + 16;
  const i0 = Math.max(0, Math.floor((st - per) / per));
  const i1 = Math.min(totalPages.value - 1, Math.ceil((st + ch) / per));
  const out = [];
  for (let i = i0; i <= i1; i++) out.push(i);
  return out;
}

function prime() {
  for (const idx of visible()) {
    if (!rendered.has(idx)) renderOne(idx);
  }
  // aktualizace indikátoru stránky
  const el = drawEl.value;
  currentPage.value = el ? Math.min(totalPages.value, Math.floor(el.scrollTop / (pageH.value + 16)) + 1) : 1;
  hideToolbar.value = el ? el.scrollTop > 40 : false;
}

async function renderOne(idx) {
  rendered.add(idx);
  const canvas = pageCanvas.value && pageCanvas.value[idx];
  if (!canvas) { rendered.delete(idx); return; }
  try {
    await renderPage(song, idx + 1, canvas, pageH.value);
  } catch (e) {
    console.warn('render selhal', idx, e);
    rendered.delete(idx);
  }
}

function onScroll() { prime(); }
function onResize() { nextTick(prime); }

// --- Zoom (CSS zoom na pásmu; souřadnice SVG zůstávají v px stránky = stabilní) ---
function zoomIn() { zoom.value = Math.min(zoom.value * 1.15, 3.5); applyZoom(); }
function zoomOut() { zoom.value = Math.max(zoom.value / 1.15, 0.5); applyZoom(); }
function applyZoom() {
  const el = drawEl.value; if (!el) return;
  el.style.zoom = zoom.value;
  // CSS zoom nemění scrollTop rozsah správně — posuneme, aby aktuální stránka zůstala
  el.scrollTop = el.scrollTop;
}

// --- Anotace ---
function pageItems(idx) { return annotations.items.filter(i => i.page === idx); }

function pathD(it) {
  return it.points.map((p, i) => (i === 0 ? `M${p.x},${p.y}` : `L${p.x},${p.y}`)).join(' ');
}

function toLayerCoords(e, idx) {
  const rect = layerSvg.value[idx].getBoundingClientRect();
  const scale = pageW.value / rect.width; // zoom korekce
  return {
    x: (e.clientX - rect.left) * scale,
    y: (e.clientY - rect.top) * scale,
  };
}

function onLayerPointerDown(e, idx) {
  const p = toLayerCoords(e, idx);
  activeStroke.value = {
    id: crypto.randomUUID(),
    page: idx,
    tool: tool.value,
    color: tool.value === 'highlighter' ? 'rgba(201,168,124,0.55)' : '#e5d7a6',
    width: tool.value === 'highlighter' ? 16 : 3,
    points: [p],
  };
  _prev = p;
  e.stopPropagation();
}

let _prev = null;
function onLayerPointerMove(e, idx) {
  if (!activeStroke.value || activeStroke.value.page !== idx) return;
  const p = toLayerCoords(e, idx);
  // přerušení bodů, aby tah nebyl extrémně hustý
  const prev = _prev;
  if (!prev || Math.abs(p.x - prev.x) > 1 || Math.abs(p.y - prev.y) > 1) {
    activeStroke.value.points.push(p); _prev = p;
  }
}
function onLayerPointerUp() {
  if (!activeStroke.value) return;
  annotations.items.push(activeStroke.value);
  activeStroke.value = null;
  saveAnnotations();
}

function setTool(t) { tool.value = t; }

function clearAnnots() {
  if (confirm('Smazat všechny anotace?')) {
    annotations.items = [];
    saveAnnotations();
  }
}

let saveTimer = null;
function saveAnnotations() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    await dbSaveAnnotations({ songId: props.id, items: annotations.items });
  }, 200);
}
</script>

<style scoped>
.viewer { flex: 1; display: flex; flex-direction: column; position: relative; overflow: hidden; background: var(--bg); }
.toolbar {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; background: var(--bg-elev); border-bottom: 1px solid var(--border);
  transition: transform 0.2s;
  z-index: 10;
}
.toolbar.hiding { transform: translateY(-100%); }
.back { background: transparent; border: 1px solid var(--border); padding: 8px 12px; }
.title { flex: 1; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.controls { display: flex; align-items: center; gap: 6px; }
.controls .icon {
  background: var(--bg-elev2); border: 1px solid var(--border);
  padding: 8px 10px; line-height: 1; font-size: 1rem;
}
.controls .icon.active { background: var(--accent); color: #17130f; border-color: var(--accent); }
.page-ind { color: var(--text-dim); font-size: 0.9rem; }
.zoom-val { color: var(--text-dim); font-size: 0.85rem; width: 44px; text-align: right; }

.draw-area {
  flex: 1; overflow: auto; position: relative;
  background: var(--bg);
  -webkit-overflow-scrolling: touch;
}

.pdf-page-wrap { position: relative; margin: 0 auto 16px; }
.pdf-page-wrap canvas { display: block; background: #fff; box-shadow: 0 2px 10px rgba(0,0,0,0.5); }

.annot-layer { position: absolute; top: 0; left: 0; touch-action: none; cursor: crosshair; }
.annot-layer .hl { mix-blend-mode: multiply; opacity: 0.9; }
</style>
