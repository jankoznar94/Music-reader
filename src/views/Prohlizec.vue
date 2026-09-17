<template>
  <div
    class="viewer"
    ref="viewerEl"
    :style="{ '--topbar-h': topBarH + 'px' }"
    @touchstart.passive="onTouchStart"
    @touchmove.passive="onTouchMove"
    @touchend.passive="onTouchEnd"
    @click="onTap"
  >
    <!-- JEDINÁ HORNÍ LIŠTA — trvale viditelná, vše na jednom místě.
         Jeden řádek: zpět · název skladby · počítadlo stránek · anotace · záložka · skok ·
         zvětšení (panel) · přehled stránek · listování sestavou
         Ploché, bez hover/focus efektů — jediný feedback je :active (Jan: mobilní PWA). -->
    <div class="top-bar" ref="barEl">
      <div class="tb-row">
        <!-- Levá skupina -->
        <div class="tb-side left">
          <button class="tb-btn" @click="goBack" title="Zpět">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
          </button>
          <span v-if="group" class="tb-song">{{ songName }}</span>
          <!-- Listování sestavou — navigace, proto vlevo (a vyvažuje lištu) -->
          <div v-if="group" class="tb-nav">
            <button class="tb-btn" @click="prevSong" :disabled="groupIndex <= 0" title="Předchozí skladba">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
            </button>
            <span class="tb-grp">{{ groupIndex + 1 }}/{{ groupSongs.length }}</span>
            <button class="tb-btn" @click="nextSong" :disabled="groupIndex >= groupSongs.length - 1" title="Další skladba">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
            </button>
          </div>
          <button class="tb-btn" @click="openBookmark" :class="{ on: bookmarkMode }" title="Přidat záložku na tuto stránku">🔖</button>
          <button class="tb-btn" @click="toggleJumpMode" :class="{ on: jumpMode }" title="Vytvořit skok (Da Capo / VIDE)">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17L17 7"/><path d="M7 7h10v10"/></svg>
          </button>
        </div>
        <!-- Rezerva: drží místo pro počítadlo, které je na přesném středu lišty -->
        <div class="tb-mid-space" />
        <!-- Pravá skupina -->
        <div class="tb-side right">
        <button class="tb-btn" @click="toggleAnnot" :class="{ on: annotMode }" title="Anotace / listování">✏️</button>
        <button class="tb-btn zoom-btn" @click="toggleZoomPanel" :class="{ on: zoomPanelOpen }" title="Zvětšení">
          {{ Math.round(zoom * 100) }}%
        </button>
        <button class="tb-btn" @click="toggleSlider" :class="{ on: sliderOpen }" title="Slider stránek">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 3v18"/></svg>
        </button>
        </div>
      </div>
      <!-- Počítadlo stránek — na přesném středu lišty (klik otevře zadání stránky) -->
      <button class="tb-page tb-page-center" @click="openPageGo" title="Přejít na stránku">
        {{ currentPage + 1 }} / {{ totalPages }}
      </button>
    </div>

    <!-- Panel zvětšení — otevírá se z tlačítka s procenty v liště -->
    <div v-if="zoomPanelOpen" class="zoom-panel">
      <button class="zp-btn" @click="zoomOut" title="Oddálit">−</button>
      <span class="zp-val">{{ Math.round(zoom * 100) }} %</span>
      <button class="zp-btn" @click="zoomIn" title="Přiblížit">+</button>
      <span class="zp-sep" />
      <button class="zp-btn" @click="resetView" title="Vycentrovat">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>
      </button>
      <button class="zp-btn" :class="{ on: hasSavedZoom }" @click="saveZoomAsDefault" title="Uložit zoom jako výchozí">
        <svg width="20" height="20" viewBox="0 0 24 24" :fill="hasSavedZoom ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.6 6.8 19.1l1-5.8L3.5 9.2l5.9-.9z"/></svg>
      </button>
    </div>

    <!-- Aktivní stránka (vlastní oblast pod lištou — lišta noty nepřekrývá) -->
    <div class="page-area" ref="pageAreaEl">
    <div class="stage" :style="{ transform: 'translate(' + panX + 'px,' + panY + 'px) scale(' + zoom + ')' }">
      <canvas ref="canvasEl" class="pdf-canvas" />
      <!-- Anotační vrstva nad PDF -->
      <svg
        ref="layerSvgEl"
        class="annot-layer"
        :class="{ active: annotMode || jumpPlaceMode }"
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
          <!-- Vykreslit tah (tužka / zvýraznění) -->
          <path
            v-if="isStroke(it)"
            :d="pathD(it)"
            fill="none"
            :stroke="it.color"
            :stroke-width="it.width"
            :opacity="it.opacity"
            stroke-linecap="round"
            stroke-linejoin="round"
            :class="{ hl: it.tool === 'highlighter' }"
          />
          <!-- Zvýrazňovač: 3-bodový obdélník (levý spodní, levý horní, vpravo) -->
          <rect
            v-else-if="it.tool === 'highlighter'"
            :x="Math.min(it.x1, it.x2)" :y="Math.min(it.y1, it.y2)"
            :width="Math.abs(it.x2 - it.x1)" :height="Math.abs(it.y2 - it.y1)"
            :fill="it.color" :opacity="it.opacity != null ? it.opacity : 1"
            class="hl"
          />
          <!-- Textová anotace -->
          <text
            v-else-if="isText(it)"
            :x="it.x" :y="it.y"
            :fill="it.color"
            :font-size="it.size"
            font-family="system-ui, sans-serif"
            :opacity="it.opacity != null ? it.opacity : 1"
            text-anchor="start"
          >{{ it.text }}</text>
          <!-- Dynamika (p, f, mp...) — notační font NotyDyn (SMuFL glyfy) -->
          <text
            v-else-if="it.tool === 'dynamic'"
            :x="it.x" :y="it.y"
            :fill="it.color"
            :font-size="it.size"
            font-family="'NotyDyn', serif"
            :opacity="it.opacity != null ? it.opacity : 1"
            text-anchor="middle"
          >{{ annotDisplayText(it) }}</text>
          <!-- Crescendo (otvírá se vpravo) / decrescendo (otvírá se vlevo) -->
          <!-- Uložený klín: špička (x1,y1), dvě ramena (x2,y2) a (x3,y3). ŽÁDNÁ středová čára. -->
          <g v-else-if="it.tool === 'crescendo' || it.tool === 'decrescendo'"
             :opacity="it.opacity != null ? it.opacity : 1">
            <line :x1="it.x1" :y1="it.y1" :x2="it.x2" :y2="it.y2" :stroke="it.color" :stroke-width="it.width" stroke-linecap="round" />
            <line :x1="it.x1" :y1="it.y1" :x2="it.x3" :y2="it.y3" :stroke="it.color" :stroke-width="it.width" stroke-linecap="round" />
          </g>
        </g>
        <!-- Aktivní prvek -->
        <!-- Aktivní tah / klín / umístění textu -->
        <g v-if="activeItem">
          <path
            v-if="isStroke(activeItem)"
            :d="pathD(activeItem)"
            fill="none" :stroke="activeItem.color" :stroke-width="activeItem.width"
            :opacity="activeItem.opacity" stroke-linecap="round" stroke-linejoin="round"
          />
          <line v-else-if="activeItem.tool === 'crescendo' || activeItem.tool === 'decrescendo'"
            :x1="activeItem.x1" :y1="activeItem.y1" :x2="activeItem.x2" :y2="activeItem.y2"
            :stroke="activeItem.color" :stroke-width="activeItem.width" stroke-linecap="round" />
          <!-- Dynamika: náhled budoucího glyfu (text zatím prázdný → tečka), ať uživatel vidí, co dostane -->
          <text
            v-else-if="activeItem.tool === 'dynamic' && activeItem.text"
            :x="activeItem.x" :y="activeItem.y"
            :fill="activeItem.color"
            :font-size="activeItem.size"
            font-family="'NotyDyn', serif"
            :opacity="activeItem.opacity != null ? activeItem.opacity : 1"
            text-anchor="middle"
          >{{ annotDisplayText(activeItem) }}</text>
          <circle v-else :cx="activeItem.x" :cy="activeItem.y" r="6"
            fill="none" :stroke="activeItem.color" stroke-width="2" />
        </g>

        <!-- Live preview při sběru bodů zobáčku — kam uživatel klikl, než se klín vykreslí -->
        <g v-if="wedgePoints.length" class="wedge-preview">
          <line
            v-if="wedgePoints.length >= 2"
            :x1="wedgePoints[0].x" :y1="wedgePoints[0].y"
            :x2="wedgePoints[1].x" :y2="wedgePoints[1].y"
            :stroke="annotColor" :stroke-width="annotSize" stroke-linecap="round"
            :opacity="0.5"
          />
          <circle
            v-for="(pt, i) in wedgePoints" :key="i"
            :cx="pt.x" :cy="pt.y" r="9"
            fill="none" :stroke="annotColor" stroke-width="2.5"
          />
          <circle
            v-for="(pt, i) in wedgePoints" :key="'c'+i"
            :cx="pt.x" :cy="pt.y" r="3.5"
            :fill="annotColor"
          />
        </g>

        <!-- Umisťování tlačítka skoku: náhled nasbíraných bodů a obdélníku -->
        <g v-if="jumpPlaceMode && jumpPlacePoints.length" class="wedge-preview">
          <rect
            v-if="jumpPlacePoints.length >= 2"
            :x="Math.min(jumpPlacePoints[0].x, jumpPlacePoints[1].x)"
            :y="Math.min(jumpPlacePoints[0].y, jumpPlacePoints[1].y)"
            :width="Math.max(60, (jumpPlacePoints.length >= 3 ? jumpPlacePoints[2].x : jumpPlacePoints[0].x + 80) - jumpPlacePoints[0].x)"
            :height="Math.abs(jumpPlacePoints[1].y - jumpPlacePoints[0].y)"
            fill="none" stroke="var(--accent,#d8a657)" stroke-width="2" stroke-dasharray="6 4" rx="4"
          />
          <circle
            v-for="(pt, i) in jumpPlacePoints" :key="'jp'+i"
            :cx="pt.x" :cy="pt.y" r="8"
            fill="none" stroke="var(--accent,#d8a657)" stroke-width="2.5"
          />
        </g>

        <!-- Live preview bodů zvýrazňovače — kam uživatel klikl + náhled boxu -->
        <g v-if="tool === 'highlighter' && hlPoints.length" class="wedge-preview">
          <rect
            v-if="hlPoints.length >= 2"
            :x="hlPoints[0].x" :y="Math.min(hlPoints[0].y, hlPoints[1].y)"
            :width="(hlPoints.length >= 3 ? hlPoints[2].x : hlPoints[0].x + 60) - hlPoints[0].x"
            :height="Math.abs(hlPoints[1].y - hlPoints[0].y)"
            :fill="annotColor" opacity="0.3" :stroke="annotColor" stroke-width="1.5" stroke-dasharray="4 3"
          />
          <circle
            v-for="(pt, i) in hlPoints" :key="'o'+i"
            :cx="pt.x" :cy="pt.y" r="9"
            fill="none" :stroke="annotColor" stroke-width="2.5"
          />
          <circle
            v-for="(pt, i) in hlPoints" :key="'f'+i"
            :cx="pt.x" :cy="pt.y" r="3.5"
            :fill="annotColor"
          />
        </g>

        <!-- Kolečko gumy — ukazuje, kam míříš a jaký rozsah guma promaže -->
        <circle
          v-if="tool === 'eraser' && activeItem && activeItem.points && activeItem.points.length"
          :cx="activeItem.points[activeItem.points.length - 1].x"
          :cy="activeItem.points[activeItem.points.length - 1].y"
          :r="Math.max(4, activeItem.width || 4) / 2"
          class="eraser-cursor"
        />

        <!-- Označení vybraného prvku v režimu Upravit (ruka) — plochý čárkovaný rámeček.
             Podmínka drží i tool === 'edit' a annotMode: rámeček smí existovat JEN
             v nástroji Ruka a jen když je anotační režim zapnutý. I kdyby někde
             zůstal viset editingId, rámeček se nevykreslí. -->
        <g v-if="annotMode && tool === 'edit' && editingAnnot && selectedBox" class="annot-selected">
          <rect
            :x="selectedBox.x" :y="selectedBox.y"
            :width="selectedBox.w" :height="selectedBox.h"
            fill="none" stroke="var(--accent,#d8a657)" stroke-width="1.5"
            stroke-dasharray="6 4" rx="5"
          />
        </g>
      </svg>

      <!-- Skoky (Da Capo / VIDE) umístěné PŘÍMO NA NOTÁCH.
           Uvnitř .stage → posouvají se a zoomují spolu s notami, takže tlačítko
           drží na místě, kam ho uživatel naklepal (třemi body). Souřadnice
           place {x,y,w,h} jsou ve stejné soustavě jako anotační vrstva. -->
      <div v-if="placerJumps.length" class="jump-on-page">
        <button
          v-for="j in placerJumps"
          :key="j.id"
          class="jump-on-btn"
          :style="jumpBoxStyle(j)"
          @click="goJump(j)"
          :title="'Skok na str. ' + (j.toPage + 1)"
        >{{ j.label }}</button>
      </div>
    </div>
    </div>

    <!-- Ruční zadání čísla stránky (plovoucí modal, stejná logika jako u skoku na skladbu) -->
    <div v-if="pageGoOpen" class="page-go-backdrop" @click.self="closePageGo">
      <div class="page-go">
        <span class="pg-label">Přejít na stránku</span>
        <div class="pg-row">
          <input
            ref="pageGoInputEl"
            v-model="pageGoValue"
            class="pg-input"
            type="text"
            inputmode="numeric"
            pattern="[0-9]*"
            @keydown.enter="goToTypedPage"
            @keydown.esc="closePageGo"
          />
          <span class="pg-total">/ {{ totalPages }}</span>
          <button class="pg-btn primary" @click="goToTypedPage">Přejít</button>
          <button class="pg-btn" @click="closePageGo">Zavřít</button>
        </div>
      </div>
    </div>

    <!-- Loading overlay při prvním načtení / přechodu mezi skladbami -->
    <div v-if="loading" class="viewer-loading">
      <div class="spinner" />
      <div class="loading-text">Načítám noty…</div>
    </div>

    <div v-if="edgeJumps.length" class="jump-strip">
      <button
        v-for="j in edgeJumps"
        :key="j.id"
        class="jump-btn"
        @click="goJump(j)"
        :title="'Skok na str. ' + (j.toPage + 1)"
      >{{ j.label }}</button>
    </div>

    <!-- Nápověda při umisťování — malá lišta, aby nezakrývala noty, na které se klepá -->
    <div v-if="jumpPlaceMode" class="jp-place-hint">
      <span>{{ jumpPlaceHint }}</span>
      <span class="jp-place-count">{{ jumpPlacePoints.length }}/3</span>
    </div>

    <!-- Panel pro vytváření skoku (při umisťování se schová — jinak zakrývá noty) -->
    <div v-if="jumpMode && !jumpPlaceMode" class="jump-panel">
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
      </div>
      <!-- Umístění tlačítka přímo na noty — tři body jako u zvýrazňovače.
           Uživatel často potřebuje tlačítko tam, kde mu končí noty, ne na okraji displeje. -->
      <div class="jp-row">
        <button class="jp-btn" @click="startJumpPlace" :class="{ on: jumpPlaceMode }">
          {{ jumpPlaceMode ? 'Umísťuji… (' + jumpPlacePoints.length + '/3)' : (jumpPlace ? 'Umístění: hotovo' : 'Umístit na stránku') }}
        </button>
        <button v-if="jumpPlace" class="jp-btn" @click="jumpPlace = null" title="Zrušit umístění">✕</button>
      </div>
      <div v-if="jumpPlaceMode" class="jp-hint">{{ jumpPlaceHint }}</div>
      <div class="jp-row">
        <span class="jp-item-pages">Str. {{ currentPage + 1 }}</span>
        <button class="jp-btn primary" @click="saveJump" :disabled="jumpStart === null || jumpEnd === null">Uložit skok</button>
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
        <div v-for="b in bookmarks" :key="b.id" class="jp-item" :class="{ dragging: bmDragId === b.id }">
          <button
            class="jp-drag"
            title="Přetáhnout pro změnu pořadí"
            @pointerdown="bmDragStart($event, b)"
            @pointermove="bmDragMove"
            @pointerup="bmDragEnd"
            @pointercancel="bmDragEnd"
            @touchstart.stop.prevent="bmNoop"
            @touchmove.stop.prevent="bmNoop"
            @touchend.stop="bmNoop"
            @touchcancel.stop="bmNoop"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 9h16"/><path d="M4 15h16"/></svg>
          </button>
          <span class="jp-item-label" :class="{ dim: !b.label }">str. {{ b.page + 1 }}<template v-if="b.label"> · {{ b.label }}</template></span>
          <span class="jp-actions">
            <button class="jp-icon" @click="startEditBookmark(b)" title="Upravit">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.8 2.8 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></svg>
            </button>
            <button class="jp-icon del" @click="deleteBookmark(b)" title="Smazat">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
            </button>
          </span>
        </div>
      </div>

      <button class="jp-close" @click="bookmarkMode = false; bookmarkLabel = ''; bookmarkEditing = null">Zavřít</button>
    </div>

    <!-- Záložky — vždy viditelná lišta u spodní hrany -->
    <!-- Lišta záložek — skrytá, když se upravuje vybraný prvek (edit-bar by s ní splýval) -->
    <div v-if="bookmarks.length && !editingId" class="bookmark-strip">
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
      />
    </div>

    <!-- Plovoucí panel anotací (jen v anotačním režimu) -->
    <div v-if="annotMode" class="annot-panel">
      <!-- Hlavička: sbalit/rozbalit -->
      <div class="ap-header">
        <span class="ap-title">Anotace</span>
        <button class="ap-collapse" @click="annotCollapsed = !annotCollapsed" :title="annotCollapsed ? 'Rozbalit' : 'Sbalit'">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path v-if="!annotCollapsed" d="M6 9l6 6 6-6"/><path v-else d="M6 15l6-6 6 6"/></svg>
        </button>
      </div>

      <template v-if="!annotCollapsed">
      <!-- Kategorie: Nástroje -->
      <div class="ap-cat">
        <div class="ap-cat-label">Nástroje</div>
        <div class="ap-row">
          <button class="ap-tool" @click="setTool('pencil')" :class="{ on: tool === 'pencil' }" title="Tužka">✏️</button>
          <button class="ap-tool" @click="setTool('highlighter')" :class="{ on: tool === 'highlighter' }" title="Zvýraznění">🖍️</button>
          <button class="ap-tool" @click="setTool('eraser')" :class="{ on: tool === 'eraser' }" title="Guma (maže anotace, přes které přejede)">🧽</button>
          <button class="ap-tool" @click="setTool('text')" :class="{ on: tool === 'text' }" title="Text (klávesnice)">T</button>
          <button class="ap-tool" @click="setTool('edit')" :class="{ on: tool === 'edit' }" title="Upravit / přesunout text či dynamiku">✋</button>
        </div>
      </div>

      <!-- Kategorie: Hudební značky -->
      <div class="ap-cat">
        <div class="ap-cat-label">Značky</div>
        <div class="ap-row">
          <button class="ap-tool mus" @click="setTool('crescendo')" :class="{ on: tool === 'crescendo' }" title="Crescendo (3 body)">&lt;</button>
          <button class="ap-tool mus" @click="setTool('decrescendo')" :class="{ on: tool === 'decrescendo' }" title="Decrescendo (3 body)">&gt;</button>
          <button class="ap-tool" @click="setTool('dynamic')" :class="{ on: tool === 'dynamic' }" title="Dynamika (p, f, mf, sfz...)">
            <span class="dyn-ico">{{ dynGlyph('mf').text }}</span>
          </button>
        </div>
      </div>

      <!-- Kategorie: Styl -->
      <div class="ap-cat">
        <div class="ap-cat-label">Styl</div>
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
        <div class="ap-row">
          <button
            v-for="s in sizes"
            :key="s"
            class="ap-size"
            :class="{ on: annotSize === s }"
            @click="annotSize = s"
            :title="'Velikost ' + s"
          ><span class="ap-size-num">{{ s }}</span></button>
        </div>
        <div class="ap-row op-row">
          <span class="ap-op-label">Krytí</span>
          <input
            type="range"
            class="ap-opacity"
            min="10" max="100" step="5"
            :value="annotOpacity"
            @input="annotOpacity = Number($event.target.value)"
          />
          <span class="ap-op-val">{{ annotOpacity }}%</span>
        </div>
      </div>

      <!-- Kategorie: Akce -->
      <div class="ap-cat">
        <div class="ap-cat-label">Akce</div>
        <div class="ap-row">
          <button class="ap-tool" @click="undoAnnot" title="Zpět" :disabled="!canUndo">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>
          </button>
          <button class="ap-tool" @click="redoAnnot" title="Dopředu" :disabled="!canRedo">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3L21 13"/></svg>
          </button>
          <button v-if="hasAnnotations" class="ap-tool" @click="clearAnnots" title="Smazat všechny anotace (celá skladba)">🗑️</button>
          <button v-if="hasPageItems" class="ap-tool" @click="clearPageAnnots" title="Smazat anotace na této stránce">🗑️<span class="ap-delpage">str.</span></button>
          <button class="ap-tool pen-only" @click="penOnly = !penOnly" :class="{ on: penOnly }" title="Kreslit jen perem (ignorovat dotyk rukou)">🖊️</button>
          <span class="ap-pen-label" @click="penOnly = !penOnly">Jen pero</span>
        </div>
      </div>
      </template>
    </div>

    <!-- Pásmo úprav vybrané textové/dynamické anotace (jen v nástroji Ruka) -->
    <div v-if="annotMode && tool === 'edit' && editingId" class="edit-bar">
      <span class="eb-type">{{ editingTypeLabel }}</span>
      <button class="eb-btn" @click="editText(editingAnnot)" title="Přepsat text">✏️</button>
      <span class="eb-size">Velikost</span>
      <button class="eb-btn" @click="resizeAnnot(editingAnnot, -1)" title="Zmenšit">−</button>
      <span class="eb-val">{{ editingAnnot ? Math.round(editingAnnot.size) : 0 }}</span>
      <button class="eb-btn" @click="resizeAnnot(editingAnnot, 1)" title="Zvětšit">+</button>
      <button class="eb-btn done" @click="endEdit" title="Hotovo">✓</button>
      <button class="eb-btn" @click="deleteEditing" title="Smazat">🗑</button>
    </div>

    <!-- Vstup pro text / dynamiku -->
    <div v-if="editingAnnotationId" class="text-input-overlay">
      <div class="text-input-card">
        <span class="ti-label">{{ editingAnnotTool === 'dynamic' ? 'Dynamika' : 'Text' }}</span>

        <!-- Rychlý výběr: klepni na dynamiku, vyplní se do pole (a rovnou se uloží) -->
        <div v-if="editingAnnotTool === 'dynamic'" class="dyn-grid">
          <button
            v-for="d in DYN_PICK"
            :key="d.key"
            class="dyn-btn"
            :class="{ on: dynKey(annotTextDraft) === d.key }"
            @click="pickDyn(d.key)"
            :title="d.key"
          >{{ d.glyph }}</button>
        </div>

        <input
          v-model="annotTextDraft"
          class="ti-input"
          :placeholder="editingAnnotTool === 'dynamic' ? 'nebo napiš vlastní (např. mf)' : 'Text poznámky'"
          @keydown.enter="confirmTextAnnot"
        />
        <!-- Neznámý výraz: font pro něj nemá glyf → zobrazil by se rozbitý znak -->
        <span v-if="editingAnnotTool === 'dynamic' && annotTextDraft.trim() && !dynGlyph(annotTextDraft).known" class="ti-warn">
          Tuhle dynamiku font nezná — vyber ji z nabídky výše.
        </span>

        <div class="ti-actions">
          <button class="jp-btn" @click="cancelTextAnnot">Zrušit</button>
          <button class="jp-btn primary" @click="confirmTextAnnot">Uložit</button>
        </div>
      </div>
    </div>

    <!-- Sběr bodů zobáčku (crescendo / decrescendo) -->
    <div v-if="wedgePoints.length || (tool === 'highlighter' && hlPoints.length)" class="wedge-overlay">
      <div class="wedge-hint">{{ wedgeHintText }}
        <span class="wedge-cancel" @click="wedgePoints = []; hlPoints = []">Zrušit</span>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { dbGetSong, dbSaveAnnotations, dbGetAnnotations, dbGetGroup, dbGetAllSongs, dbGetJumps, dbSaveJumps, dbGetBookmarks, dbSaveBookmarks, dbGetSongView, dbSaveSongView } from '../db.js';
import { renderPage, getPageWidthHeight, getPageCount } from '../pdf.js';

const props = defineProps({ id: { type: String, required: true } });
const router = useRouter();

// Skupina (setlist) — pokud je otevřeno přes skupinu, umožní plynulý přechod mezi notami
const group = ref(null);        // { id, name, songIds: [] }
const groupSongs = ref([]);     // načtené noty ve skupině (v pořadí)
const groupIndex = ref(-1);     // index aktuální noty ve skupině

const viewerEl = ref(null);
const barEl = ref(null);       // horní lišta (měříme její výšku → vejde se stránka pod ni)
const pageAreaEl = ref(null);  // oblast stránky pod lištou (z ní se počítá fit na šířku/výšku)
const canvasEl = ref(null);
const layerSvgEl = ref(null);
const thumbStripEl = ref(null);

const song = reactive({ data: null, name: '', fileName: '', id: props.id });

const totalPages = ref(0);
const currentPage = ref(0); // 0-based
const loading = ref(true);  // loading overlay při prvním načtení / přechodu mezi skladbami
const zoom = ref(1.0);     // výchozí zoom 100 % (1 = fit výšce)
const songZoom = ref(1.0); // uložený výchozí zoom aktuální skladby (per-skladba), fallback 1.0
// True, když má aktuální skladba nastavený (uložený) výchozí zoom ≠ fit 1.0
const hasSavedZoom = ref(false);
const panX = ref(0);        // posun stránky (dvouprstý pan)
const panY = ref(0);

const annotMode = ref(false);
const tool = ref('pencil');
const activeItem = ref(null);

// Rozšířené anotace
const colors = ['#1a1a1a', '#c05a4a', '#e5d7a6', '#f2c4b6', '#bcd3b6', '#a8c4e0', '#e5c9a8', '#d9b6d9', '#1a2a4a'];
const sizes = [1, 2, 3, 4, 6, 8, 12];
const annotColor = ref('#1a1a1a'); // aktuální barva pera
const annotSize = ref(1);          // aktuální velikost pera (výchozí = nejmenší 1)
const annotOpacity = ref(100);     // aktuální opacity tahu v % (100 = plné krytí)
const annotCollapsed = ref(false); // anotační panel sbalený (jen přepínač)
const editingAnnotationId = ref(null); // id anotace (text/dynamika), jejíž text se právě edituje
const annotTextDraft = ref('');     // rozpisy textu při editaci
const editingId = ref(null);        // id vybrané textové/dynamické anotace pro lištu úprav

// --- Dynamika: psaný text -> SMuFL kód (font NotyDyn, blok U+E520-U+E549) ---
// Uživatel píše "mf", "sfz", "fp" atd. — v notačním fontu je každá dynamika
// JEDEN glyf na vlastním kódu, nikoli ASCII písmena. Bez tohoto překladu by
// se zobrazila prázdná/nesmyslná místa (ASCII písmena v tom fontu nejsou).
// Všechny kódy a jejich šířky ověřené z fontu (advance width v em).
const DYN_GLYPHS = {
  pppppp: 0xE527, ppppp: 0xE528, pppp: 0xE529, ppp: 0xE52A,
  pp: 0xE52B, p: 0xE520, mp: 0xE52C, mf: 0xE52D, pf: 0xE52E,
  ffffff: 0xE533, fffff: 0xE532, ffff: 0xE531, fff: 0xE530,
  ff: 0xE52F, f: 0xE522,
  fp: 0xE534, fz: 0xE535, sfz: 0xE536, sf: 0xE524,
  sfp: 0xE537, sfpp: 0xE538, sz: 0xE539, szp: 0xE53A,
  sffz: 0xE53B, rf: 0xE523, rfz: 0xE53C, rfz2: 0xE53D,
  z: 0xE525, n: 0xE526,
};
// Normalizace: bez diakritiky/mezer, malá písmena (uživatel může psát "mf ", "MF")
function dynKey(raw) {
  return String(raw || '').trim().toLowerCase().replace(/\s+/g, '');
}
// Přeloží napsaný text na SMuFL znak(y). Když výraz v mapě není, vrátí text
// beze změny (radši nic než rozbité znaky) — a vrátí i příznak, že chybí.
function dynGlyph(raw) {
  const k = dynKey(raw);
  const cp = DYN_GLYPHS[k];
  if (cp) return { text: String.fromCodePoint(cp), known: true };
  return { text: String(raw || ''), known: false };
}
// Šířka dynamiky v em (z metrik fontu) — pro přesný rámeček výběru.
// Když výraz neznáme, odhadneme (0,42 em na znak) — jen pro rámeček, ne pro text.
const DYN_ADV = {
  pppppp: 2.1240, ppppp: 1.7760, pppp: 1.4170, ppp: 1.0720, pp: 0.7270, p: 0.3650,
  mp: 0.8260, mf: 0.7970, pf: 0.7700,
  ffffff: 1.5500, fffff: 1.3100, ffff: 1.0700, fff: 0.8310, ff: 0.6090, f: 0.3640,
  fp: 0.6190, fz: 0.4970, sfz: 0.6040, sf: 0.2290, sfp: 0.8460, sfpp: 1.1980,
  sz: 0.7320, szp: 1.0750, sffz: 0.9640, rf: 0.2770, rfz: 0.6250, rfz2: 0.7440,
  z: 0.2440, n: 0.3080,
};
function dynAdvEm(raw) {
  const k = dynKey(raw);
  if (DYN_ADV[k] != null) return DYN_ADV[k];
  return 0.42 * Math.max(1, String(raw || '').length);
}
// Text k vykreslení: dynamika = SMuFL znak (font NotyDyn), ostatní = jak je
function annotDisplayText(it) {
  if (!it) return '';
  if (it.tool === 'dynamic') return dynGlyph(it.text).text;
  return it.text || '';
}
// Je to dynamika, kterou font neumí? (zvýrazníme v náhledu, ať uživatel ví)
function dynUnknown(it) {
  return it && it.tool === 'dynamic' && it.text && !dynGlyph(it.text).known;
}

// Nabídka dynamik v dialogu — pořadí odpovídá běžnému notačnímu úzu (od slabé k silné).
// glyph = hotový znak z fontu, takže uživatel vidí přesně to, co dostane.
const DYN_PICK = [
  'ppp', 'pp', 'p', 'mp', 'mf', 'f', 'ff', 'fff',
  'fp', 'sf', 'sfz', 'fz', 'rf', 'rfz', 'sffz', 'sfp', 'n',
].map(k => ({ key: k, glyph: dynGlyph(k).text }));
// Klepnutí na dlaždici: vyplní text a rovnou potvrdí (méně klikání na tabletu)
function pickDyn(k) {
  annotTextDraft.value = k;
  confirmTextAnnot();
}

const editingAnnot = computed(() =>
  editingId.value ? annotations.value.items.find(x => x.id === editingId.value) || null : null
);
// Ohraničující rámeček vybraného prvku (režim Upravit/ruka) — pro vizuální označení
const selectedBox = computed(() => {
  const it = editingAnnot.value;
  if (!it) return null;
  let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
  if (it.tool === 'text' || it.tool === 'dynamic') {
    if (it.x != null && it.y != null) {
      const s = it.size || 20;
      x1 = it.x; y1 = it.y - s;
      // Dynamika = glyf z fontu (šířka z metrik, ne odhad), text = odhad podle znaků
      const w = it.tool === 'dynamic'
        ? dynAdvEm(it.text) * s
        : (it.text ? it.text.length * s * 0.6 : s);
      x2 = it.x + w; y2 = it.y;
    }
  } else if (isStroke(it)) {
    for (const p of (it.points || [])) {
      if (p.x < x1) x1 = p.x; if (p.y < y1) y1 = p.y;
      if (p.x > x2) x2 = p.x; if (p.y > y2) y2 = p.y;
    }
  } else if (it.tool === 'crescendo' || it.tool === 'decrescendo') {
    const xs = [it.x1, it.x2, it.x3], ys = [it.y1, it.y2, it.y3];
    x1 = Math.min(...xs); x2 = Math.max(...xs);
    y1 = Math.min(...ys); y2 = Math.max(...ys);
  } else if (it.tool === 'highlighter') {
    x1 = Math.min(it.x1, it.x2); x2 = Math.max(it.x1, it.x2);
    y1 = Math.min(it.y1, it.y2); y2 = Math.max(it.y1, it.y2);
  }
  if (x2 < x1 || y2 < y1) return null;
  const pad = 8;
  return { x: x1 - pad, y: y1 - pad, w: (x2 - x1) + pad * 2, h: (y2 - y1) + pad * 2 };
});
const editingTypeLabel = computed(() =>
  editingAnnot.value ? (editingAnnot.value.tool === 'dynamic' ? 'Dynamika' : 'Text') : ''
);
const wedgePoints = ref([]); // body zobáčku (crescendo/decrescendo), až 3 × {x,y}
const hlPoints = ref([]);    // body zvýrazňovače (3 × {x,y}: levý spodní, levý horní, vpravo)
const wedgeHintText = computed(() => {
  if (tool.value === 'crescendo') {
    return wedgePoints.value.length === 0 ? '1. Špička (klepni)' :
           wedgePoints.value.length === 1 ? '2. Konec ramena (klepni)' :
           '3. Druhý konec ramena (klepni)';
  }
  if (tool.value === 'decrescendo') {
    return wedgePoints.value.length === 0 ? '1. Konec ramena (klepni)' :
           wedgePoints.value.length === 1 ? '2. Druhý konec ramena (klepni)' :
           '3. Špička (klepni)';
  }
  if (tool.value === 'highlighter') {
    return hlPoints.value.length === 0 ? '1. Levý spodní (klepni)' :
           hlPoints.value.length === 1 ? '2. Levý horní (klepni)' :
           '3. Pravý (klepni)';
  }
  return '';
});
const history = ref([]);           // undo stack (kopie předchozích stavů items)
const redoStack = ref([]);         // redo stack
const canUndo = computed(() => history.value.length > 0);
const canRedo = computed(() => redoStack.value.length > 0);
const hasAnnotations = computed(() => annotations.value.items.length > 0);
const hasPageItems = computed(() => annotations.value.items.some(x => x.page === currentPage.value));
// Změřená výška horní lišty → CSS proměnná --topbar-h. Panely a modaly se pod ni
// kotví, takže i když se lišta zalomí jinam (delší název, větší písmo systému),
// nic se nepřekryje. ResizeObserver to drží v aktuální hodnotě.
const topBarH = ref(96);
let barObs = null;
// Panel zvětšení (z tlačítka s procenty v liště) — z lišty zmizela 4 samostatná
// tlačítka zoomu, která zabírala skoro polovinu šířky a nutila zbytek na 35 px.
const zoomPanelOpen = ref(false);
function toggleZoomPanel() {
  zoomPanelOpen.value = !zoomPanelOpen.value;
  if (zoomPanelOpen.value) { annotMode.value = false; jumpMode.value = false; bookmarkMode.value = false; sliderOpen.value = false; endEdit(); }
}

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
// Umístění tlačítka přímo na noty. Sběr tří bodů jako u zvýrazňovače:
//   1) levý horní   2) levý spodní (spolu s 1. dávají horní a spodní stěnu)
//   3) pravý (určuje pravou stěnu)
// Uloží se jako obdélník, do kterého se vloží text tlačítka.
const jumpPlace = ref(null);       // {x, y, w, h} hotové umístění na stránce
const jumpPlaceMode = ref(false);  // probíhá sběr bodů
const jumpPlacePoints = ref([]);   // nasbírané body (max 3)
const jumpPlaceHint = computed(() => {
  const n = jumpPlacePoints.value.length;
  if (n === 0) return '1. Levý horní roh tlačítka (klepni na noty)';
  if (n === 1) return '2. Levý spodní roh (určí výšku tlačítka)';
  return '3. Pravý roh (určí šířku tlačítka)';
});
function startJumpPlace() {
  if (jumpPlaceMode.value) { jumpPlaceMode.value = false; jumpPlacePoints.value = []; return; }
  jumpPlaceMode.value = true;
  jumpPlacePoints.value = [];
  jumpPlace.value = null;
  // POZOR: záměrně NEZAPÍNÁME annotMode — tím by se otevřel anotační panel,
  // který přes noty zakryje celou plochu a klepnutí by šla do něj, ne na vrstvu.
  // Vrstva se aktivuje přes `active: annotMode || jumpPlaceMode` (viz šablona).
  annotMode.value = false;
}
// Ze tří bodů spočítá obdélník: levé body = svislé stěny, krajní = vodorovné.
function commitJumpPlace() {
  const [a, b, c] = jumpPlacePoints.value;
  const left = Math.min(a.x, b.x), top = Math.min(a.y, b.y);
  const right = Math.max(c.x, a.x, b.x), bottom = Math.max(a.y, b.y);
  const w = Math.max(60, right - left), h = Math.max(28, bottom - top);
  jumpPlace.value = { x: left, y: top, w, h };
  jumpPlaceMode.value = false;
  jumpPlacePoints.value = [];
}

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
  // 1-bodový díl (zbytek tahu rozdělený gumou) se vykreslí jako tečka
  if (it.points.length === 1) {
    const p = it.points[0];
    const r = Math.max(1.5, (it.width || 2) / 2);
    return `M${p.x - r},${p.y} a${r},${r} 0 1,0 ${r * 2},0 a${r},${r} 0 1,0 ${-r * 2},0`;
  }
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
  // Aplikovat uložený výchozí zoom skladby (pokud existuje), jinak fit 1.0
  await applySongView();
  await renderCurrent();
  loading.value = false; // první stránka vykreslena → skrýt loading
  window.addEventListener('resize', onResize);
  // Udržet displej zapnutý, dokud je prohlížeč otevřený (jako jiné appky)
  setupWakeLock();
  // Změřit výšku horní lišty → CSS proměnná pro kotvení panelů pod ni.
  // ResizeObserver ji drží aktuální i při změně písma/otočení displeje.
  measureBar();
  if (barEl.value && typeof ResizeObserver !== 'undefined') {
    barObs = new ResizeObserver(measureBar);
    barObs.observe(barEl.value);
  }
});

function measureBar() {
  const b = barEl.value;
  if (b) topBarH.value = Math.round(b.getBoundingClientRect().height);
}

onUnmounted(() => {
  window.removeEventListener('resize', onResize);
  if (barObs) { barObs.disconnect(); barObs = null; }
  disconnectThumbObserver();
  releaseWakeLock();
  clearTimeout(_bmSaveTimer);
  _bmDrag = null;
});

// --- Screen Wake Lock: displej nezhasíná, dokud je prohlížeč otevřený ---
let wakeLock = null;
let wakeTimer = null;
let wakeVisibleHandler = null;
async function acquireWakeLock() {
  try {
    if ('wakeLock' in navigator) {
      wakeLock = await navigator.wakeLock.request('screen');
      // Znovu vyžádat, když se lock ztratí (OS/prohlížeč ho časem uvolňuje) —
      // jinak se displej po chvíli začne zase stmívat.
      wakeLock.addEventListener('release', () => {
        wakeLock = null;
        // Pokud je viewer stále otevřený, okamžitě vyžádáme znovu
        acquireWakeLock();
      });
    }
  } catch (err) {
    console.warn('Wake Lock nelze aktivovat', err);
  }
}
function setupWakeLock() {
  acquireWakeLock();
  // Prohlížeč může lock uvolnit i bez události (např. při ztrátě aktivity),
  // proto periodicky znovu vyžádáme a při návratu do karty taky.
  window.clearInterval(wakeTimer);
  wakeTimer = setInterval(() => { if (!wakeLock) acquireWakeLock(); }, 10000);
  wakeVisibleHandler = () => { if (document.visibilityState === 'visible') acquireWakeLock(); };
  document.addEventListener('visibilitychange', wakeVisibleHandler);
}
function releaseWakeLock() {
  if (wakeTimer) { window.clearInterval(wakeTimer); wakeTimer = null; }
  if (wakeVisibleHandler) { document.removeEventListener('visibilitychange', wakeVisibleHandler); wakeVisibleHandler = null; }
  if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; }
}

let availW = 800, availH = 1100;

async function applySongView() {
  const view = await dbGetSongView(song.id);
  songZoom.value = (view && view.zoom) ? view.zoom : 1.0;
  hasSavedZoom.value = !!(view && view.zoom);
  // Vycentrovat = uložený výchozí (ne vždy 1.0)
  zoom.value = songZoom.value;
  panX.value = 0; panY.value = 0;
}

// Uloží aktuální zoom jako výchozí zobrazení pro DANOU skladbu
async function saveZoomAsDefault() {
  songZoom.value = zoom.value;
  hasSavedZoom.value = true;
  await dbSaveSongView({ songId: song.id, zoom: zoom.value });
}

function computeFit() {
  // .page-area je přes celou výšku (lišta je overlay), ale má padding-top o výšce
  // lišty. Odečteme ho, aby se noty vešly POD lištu a nepod ni nezajely.
  const el = pageAreaEl.value || viewerEl.value;
  if (el) {
    const barH = topBarH.value || 0;
    availH = Math.max(200, el.clientHeight - barH - 12);
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
  endEdit();   // listování = konec výběru prvku (rámeček patří jiné stránce)
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
    zoomPanelOpen.value = false;
    endEdit();               // a zrušit výběr prvku (rámeček by zůstal viset)
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
// Puštění slideru → NIKAM neskočit; skok jen kliknutím na miniaturu nebo stránku.
// (slidování jen zvýrazní náhled přes pageSlider)
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
  endEdit(); // výběr prvku patří předchozí skladbě → zrušit
  // Okamžitě uložit anotace aktuální skladby (jinak by se debounce odpálil až po přepnutí
  // a uložil by B-čkové items pod B-čkový song.id → A-čková anotace by se ztratila)
  await flushAnnotations();
  // načíst novou skladbu
  song.id = s.id; song.data = s.data; song.name = s.name; song.fileName = s.fileName;
  groupIndex.value = idx;
  // Uložený výchozí zoom nové skladby (vycentruje a nastaví zoom), jinak fit 1.0
  await applySongView();
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
  // Tah na liště záložek (horizontální scroll) nekreslí jako swipe stránky
  if (e.target && e.target.closest && e.target.closest('.bookmark-strip')) return;
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

// Tap: okraje → listování (jen mimo anotaci, tlačítka, lištu a formuláře)
function onTap(e) {
  if (annotMode.value) return;
  if (jumpPlaceMode.value) return;   // probíhá umisťování — klepnutí patří vrstvě
  // Plovoucí tlačítka, panely a vstupy necháme bez stránkování (input ve správci záložek
  // by jinak spadl do okrajové zóny a skočil na předchozí stránku).
  if (e.target.closest('button')) return;
  if (e.target.closest('input, textarea, select')) return;
  if (e.target.closest('.top-bar, .jump-panel, .slider-panel, .bookmark-strip, .page-go-backdrop')) return;
  const el = viewerEl.value;
  if (!el) return;
  const x = e.clientX - el.getBoundingClientRect().left;
  const edge = el.clientWidth * 0.2; // 20 % od okraje = listování
  if (x < edge) prevPage();
  else if (x > el.clientWidth - edge) nextPage();
}

// --- Anotace ---
function toggleAnnot() {
  annotMode.value = !annotMode.value;
  if (annotMode.value) { jumpMode.value = false; bookmarkMode.value = false; sliderOpen.value = false; zoomPanelOpen.value = false; } // jiné panely zavřít
  // vypnutí řeší watch na annotMode níže (pokrývá i cesty, které by na endEdit zapomněly)
}

// POJISTKA: jakmile se anotační režim vypne (jakýmkoli způsobem — FAB, jiný panel,
// přechod skladby…), výběr prvku se zruší. Dřív se endEdit() volal ručně na ~8 místech
// a stačilo jedno opomenutí a rámeček zůstal viset přes celou obrazovku.
watch(annotMode, (on) => {
  if (!on) {
    endEdit();
    // Přerušené umisťování skončí — jinak by zůstal viset režim sběru bodů
    if (jumpPlaceMode.value) { jumpPlaceMode.value = false; jumpPlacePoints.value = []; }
  }
});
// Totéž při změně nástroje: rámeček patří nástroji Ruka, u jiného nástroje nemá co dělat.
watch(tool, () => endEdit());

function setTool(t) { endEdit(); tool.value = t; wedgePoints.value = []; hlPoints.value = []; annotMode.value = true; jumpMode.value = false; bookmarkMode.value = false; sliderOpen.value = false; zoomPanelOpen.value = false; }

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
  // Umisťování tlačítka skoku: tři klepnutí určují obdélník tlačítka.
  // Musí být PŘED kontrolou annotMode — jinak by klepnutí spadlo do kreslení.
  if (jumpPlaceMode.value) {
    const p2 = toLayerCoords(e);
    jumpPlacePoints.value.push({ x: p2.x, y: p2.y });
    if (jumpPlacePoints.value.length === 3) commitJumpPlace();
    return;
  }
  if (!annotMode.value) return;
  // Pen-only mód: ignorovat dotyk prstem/rukou (palm-rejection), kreslit jen stylusem
  if (penOnly.value && e.pointerType !== 'pen') return;
  if (_activePointerId !== null) return; // už kreslí jiný tah (např. druhá ruka)
  _activePointerId = e.pointerId;
  const p = toLayerCoords(e);

  // Režim "Upravit": vybrat prvek na daném místě a připravit k přetažení
  if (tool.value === 'edit') {
    // Tažení za tlačítko skoku (má uložené umístění) — přesun celého obdélníku
    const jHit = jumpAtPoint(p);
    if (jHit) {
      _dragJump = jHit.j;
      _dragJumpFrom = { x: p.x, y: p.y };
      _dragJumpSnap = { ...jHit.j.place };
      editingId.value = null;
      _prev = p;
      return;
    }
    _dragJump = null;
    const hit = pageHits(p);
    if (hit) {
      editingId.value = hit.id;
      _dragAnnot = hit;
      _dragFrom = { x: p.x, y: p.y };
      // Snapshot geometrie, aby se celý prvek přesunul jedním delta posunem
      _dragSnap = JSON.parse(JSON.stringify(hit));
    } else {
      editingId.value = null;
    }
    _prev = p;
    return;
  }

  const pen = tool.value === 'highlighter';
  const w = pen ? annotSize.value * 2 : annotSize.value;

  // Klín (crescendo / decrescendo): sbírání 3 bodů klepnutím → vygeneruje zobák.
  if (tool.value === 'crescendo' || tool.value === 'decrescendo') {
    // Reset pointeru ZA KAŽDÝ klik — guard na začátku by jinak zablokoval
    // 2. a 3. bod (pointer zůstal „aktivní" z předchozího kliku).
    _activePointerId = null;
    wedgePoints.value.push({ x: p.x, y: p.y });
    if (wedgePoints.value.length === 3) {
      const [a, b, c] = wedgePoints.value;
      // Crescendo: špička = a, dvě ramena = a→b a a→c.
      // Decrescendo: špička = c, dvě ramena = c→a a c→b.
      const tip = tool.value === 'crescendo' ? a : c;
      const r1  = tool.value === 'crescendo' ? b : a;
      const r2  = tool.value === 'crescendo' ? c : b;
      const it = {
        id: crypto.randomUUID(), page: currentPage.value,
        tool: tool.value, color: annotColor.value,
        opacity: annotOpacity.value / 100,
        width: Math.max(1, Math.round(annotSize.value)), // tloušťka zobáčku = vybraná velikost tužky
        x1: tip.x,
        // Hrot vertikálně na střed mezi konci ramen (konce jsou už vodorovně
        // nad sebou z předchozí úpravy → hrot tak sedí přímo doprostřed).
        y1: (r1.y + r2.y) / 2,
        x2: r1.x, y2: r1.y,
        x3: r1.x, y3: r2.y,
      };
      wedgePoints.value = [];
      pushHistory();
      annotations.value.items.push(it);
      saveAnnotations();
    }
    // Reset pointer, aby další klik (další bod/klín) prošel guardem
    // (_activePointerId by jinak zůstal nastavený z prvního kliknutí a blokoval).
    _activePointerId = null;
    _prev = p;
    return;
  }

  // Zvýrazňovač: 3 body klepnutím → levý spodní, levý horní, vpravo → přesný obdélník.
  // Levá vertikála z prvního bodu, horní/dolní horizontála z 1.+2., pravá vertikála z 3.
  if (tool.value === 'highlighter') {
    _activePointerId = null;   // guard by jinak zablokoval 2. a 3. klik
    hlPoints.value.push({ x: p.x, y: p.y });
    if (hlPoints.value.length === 3) {
      const [a, b, c] = hlPoints.value;
      const x1 = a.x;                 // levá vertikála z prvního bodu
      const y1 = Math.min(a.y, b.y);  // horní horizontála
      const y2 = Math.max(a.y, b.y);  // dolní horizontála
      const x2 = c.x;                 // pravá vertikála z třetího bodu
      const it = {
        id: crypto.randomUUID(), page: currentPage.value,
        tool: 'highlighter', color: annotColor.value + '80',
        opacity: 1,
        width: Math.max(1, Math.round(annotSize.value)),
        x1, y1, x2, y2,
      };
      hlPoints.value = [];
      pushHistory();
      annotations.value.items.push(it);
      saveAnnotations();
    }
    _activePointerId = null;
    _prev = p;
    return;
  }

  // Text / dynamika: umístění na stránku (vytvoří se po uvolnění)
  if (tool.value === 'text' || tool.value === 'dynamic') {
    activeItem.value = {
      id: crypto.randomUUID(), page: currentPage.value,
      tool: tool.value, color: annotColor.value,
      opacity: annotOpacity.value / 100,
      size: Math.max(14, 20 + annotSize.value * 3),
      x: p.x, y: p.y, text: '',
      pending: true,   // po uvolnění otevře vstup
    };
    _prev = p;
    return;
  }

  // Guma: jako tah, ale po uvolnění se anotace přes které přejede smažou.
  // Šířka kopíruje vybranou velikost tužky (stejně jako tužka).
  if (tool.value === 'eraser') {
    activeItem.value = {
      id: crypto.randomUUID(), page: currentPage.value,
      tool: 'eraser', color: 'none',
      opacity: 1,
      width: Math.max(4, annotSize.value),
      points: [p],
    };
    _prev = p;
    return;
  }

  // Tužka / zvýraznění: tah s body
  activeItem.value = {
    id: crypto.randomUUID(), page: currentPage.value,
    tool: tool.value,
    color: pen ? annotColor.value + '80' : annotColor.value,   // '80'=50% alfa: výraznější, noty se stále prosvítají
    opacity: pen ? 1 : annotOpacity.value / 100,
    width: w,
    points: [p],
  };
  _prev = p;
}
let _prev = null;
let _activePointerId = null;
let _dragAnnot = null;
// Tažení tlačítka skoku po notách (režim Ruka) — aby si uživatel doladil umístění
let _dragJump = null, _dragJumpFrom = null, _dragJumpSnap = null;   // prvek přetahovaný v režimu Upravit (ruka)
let _dragFrom = null;    // výchozí bod přetažení (x,y)
let _dragSnap = null;    // snapshot geometrie prvku na začátku přetažení
let _eraserHistoryPushed = false; // aby guma uložila history jen jednou za tah
function isStroke(it) {
  return it && it.tool === 'pencil';   // highlighter je teď 3-bodový obdélník, ne tah
}
function isText(it) {
  return it && it.tool === 'text';
}
function isFreehand() {
  return tool.value === 'pencil' || tool.value === 'highlighter';
}
function onLayerMove(e) {
  // Režim "Upravit": přetahování tlačítka skoku po notách
  if (tool.value === 'edit' && _dragJump && _dragJumpSnap) {
    const p2 = toLayerCoords(e);
    const s = _dragJumpSnap;
    _dragJump.place = {
      x: Math.round(s.x + (p2.x - _dragJumpFrom.x)),
      y: Math.round(s.y + (p2.y - _dragJumpFrom.y)),
      w: s.w, h: s.h,
    };
    _prev = p2;
    return;
  }
  // Režim "Upravit": přetahování vybraného prvku (text, dynamika, tah, klín)
  if (tool.value === 'edit' && _dragAnnot) {
    if (_activePointerId !== e.pointerId) return;
    const p = toLayerCoords(e);
    const dx = p.x - _dragFrom.x;
    const dy = p.y - _dragFrom.y;
    const it = _dragAnnot;
    const s = _dragSnap;
    if (it.tool === 'text' || it.tool === 'dynamic') {
      it.x = s.x + dx; it.y = s.y + dy;
    } else if (isStroke(it)) {
      it.points = s.points.map(pt => ({ x: pt.x + dx, y: pt.y + dy }));
    } else if (it.tool === 'crescendo' || it.tool === 'decrescendo') {
      it.x1 = s.x1 + dx; it.y1 = s.y1 + dy;
      it.x2 = s.x2 + dx; it.y2 = s.y2 + dy;
      it.x3 = s.x3 + dx; it.y3 = s.y3 + dy;
    } else if (it.tool === 'highlighter') {
      it.x1 = s.x1 + dx; it.y1 = s.y1 + dy;
      it.x2 = s.x2 + dx; it.y2 = s.y2 + dy;
    }
    _prev = p;
    return;
  }
  if (!activeItem.value) return;
  if (_activePointerId !== e.pointerId) return; // jiný prvek (druhá ruka) — nekreslit
  const p = toLayerCoords(e);
  const prev = _prev;
  // Text / dynamika: jen sledovat, dokud neuvolníme (pozice se nastaví na up)
  if (tool.value === 'text' || tool.value === 'dynamic') {
    activeItem.value.x = p.x; activeItem.value.y = p.y;
    _prev = p;
    return;
  }
  // Guma: okamžitá zpětná vazba jako u tužky. Každý snímek maže JEN ten
  // nový úsek dráhy (minulý bod → aktuální), jemně subdividovaný, takže
  // mazání je plynulé a přesně v poloměru kolečka — ne trhané, nepřemazává.
  if (tool.value === 'eraser') {
    const hadPrev = !!prev;
    // NASTAV _prev VŽDY (i když je posun menší než 1px)! Bug: předtím se
    // při posunu<1px _prev NEaktualizoval, ale seg se konstruoval z něj →
    // guma se opakovaně dívala na starý segment a mazala desítky bodů
    // mimo rozsah kolečka.
    let effectivePrev = prev;
    if (!hadPrev || Math.abs(p.x - prev.x) > 1 || Math.abs(p.y - prev.y) > 1) {
      activeItem.value.points.push(p);
      _prev = p;
      effectivePrev = prev;
    } else {
      // posun < 1px — segment je nulový, nemazat
      _prev = p;
      effectivePrev = null;
    }
    // jen poslední segment (effectivePrev → p) = nový kus dráhy pro tento snímek
    const seg = effectivePrev
      ? [{ x: effectivePrev.x, y: effectivePrev.y }, { x: p.x, y: p.y }]
      : [{ x: p.x, y: p.y }];
    // jemně subdividovat, aby rychlý pohyb neroztrhal stopu a nevynechal mezery
    const fine = [];
    for (let i = 0; i < seg.length - 1; i++) {
      const a = seg[i], b = seg[i + 1];
      const d = Math.hypot(b.x - a.x, b.y - a.y);
      const n = Math.max(1, Math.ceil(d / 4));
      for (let s = 0; s < n; s++) fine.push({ x: a.x + (b.x - a.x) * s / n, y: a.y + (b.y - a.y) * s / n });
    }
    fine.push(seg[seg.length - 1]);
    const eraserR = Math.max(4, activeItem.value.width || 4) / 2; // poloměr
    let changed = false;
    const items = annotations.value.items;
    const next = [];
    for (const x of items) {
      if (x.page !== currentPage.value) { next.push(x); continue; }
      // Tah (tužka/zvýrazňovač): rozdělit jen podle nového úseku
      if (isStroke(x)) {
        const parts = eraseStrokeOnSeg(x, fine, eraserR);
        if (parts === null) { next.push(x); continue; }
        changed = true;
        next.push(...parts);
        continue;
      }
      // Klín / text / dynamika: smazat, když se dotkneš
      if (segOnUnder(fine, eraserR, x)) { changed = true; continue; }
      next.push(x);
    }
    // History se ukládá JEŠTĚ PŘED přiřazením nové podoby
    if (changed) {
      if (!_eraserHistoryPushed) { pushHistory(); _eraserHistoryPushed = true; }
    }
    annotations.value.items = next;
    if (changed) saveAnnotations();
    return;
  }
  // Tužka / zvýraznění: přidat body
  if (!prev || Math.abs(p.x - prev.x) > 1 || Math.abs(p.y - prev.y) > 1) {
    activeItem.value.points.push(p); _prev = p;
  }
}
function onLayerUp(e) {
  // Režim "Upravit": ukončit přetahování, uložit novou pozici
  if (tool.value === 'edit') {
    // Přesun tlačítka skoku → uložit nové umístění do DB
    if (_dragJump) {
      dbSaveJumps({ songId: song.id, items: jumps.value });
      _dragJump = null; _dragJumpFrom = null; _dragJumpSnap = null;
      _activePointerId = null;
      _prev = null;
      return;
    }
    if (_dragAnnot && _activePointerId === e.pointerId) {
      saveAnnotations();
    }
    _dragAnnot = null; _dragFrom = null; _dragSnap = null;
    _activePointerId = null;
    _prev = null;
    return;
  }
  if (!activeItem.value) return;
  if (_activePointerId !== e.pointerId) return;
  _activePointerId = null;
  const it = activeItem.value;

  // Guma: okamžité mazání už běží v onLayerMove; tady jen ukončíme tah
  if (tool.value === 'eraser') {
    activeItem.value = null;
    _activePointerId = null;
    _prev = null;
    _eraserHistoryPushed = false;   // reset pro další gumovací tah
    return;
  }

  // Text / dynamika: místo uvolnění → otevřít textový vstup (pending)
  if (tool.value === 'text' || tool.value === 'dynamic') {
    it.pending = true;
    editingAnnotationId.value = it.id;
    return; // držet aktivní do uložení textu
  }

  // Tužka / zvýraznění
  // Maličká/rychá poznámka: tah s pouhým 1 bodem je při kreslení prakticky neviditelný
  if (it.points.length < 2) {
    const p = toLayerCoords(e);
    it.points.push(p);
  }
  pushHistory();
  annotations.value.items.push(it);
  activeItem.value = null;
  saveAnnotations();
}

function clearAnnots() {
  if (confirm('Smazat všechny anotace?')) {
    pushHistory();
    annotations.value.items = [];
    saveAnnotations();
  }
}

// Smazat anotace jen na aktuální stránce
function clearPageAnnots() {
  const page = currentPage.value;
  const count = annotations.value.items.filter(x => x.page === page).length;
  if (count === 0) return;
  if (confirm(`Smazat ${count} anotace na této stránce?`)) {
    pushHistory();
    annotations.value.items = annotations.value.items.filter(x => x.page !== page);
    saveAnnotations();
  }
}

// --- Text / dynamika — potvrzení vstupu ---
const editingAnnotTool = computed(() => {
  if (!editingAnnotationId.value) return '';
  const it = annotations.value.items.find(x => x.id === editingAnnotationId.value)
         || (activeItem.value && activeItem.value.id === editingAnnotationId.value ? activeItem.value : null);
  return it ? it.tool : '';
});
function confirmTextAnnot() {
  const id = editingAnnotationId.value;
  if (!id) return;
  const it = annotations.value.items.find(x => x.id === id) || activeItem.value;
  if (it) {
    it.text = annotTextDraft.value.trim();
  }
  if (!annotations.value.items.includes(it)) {
    pushHistory();
    annotations.value.items.push(it);
  }
  activeItem.value = null;
  editingAnnotationId.value = null;
  annotTextDraft.value = '';
  saveAnnotations();
}
function cancelTextAnnot() {
  // Odebrat případné pending (neuložené) místo
  const id = editingAnnotationId.value;
  if (id && activeItem.value && activeItem.value.id === id) {
    activeItem.value = null;
  }
  editingAnnotationId.value = null;
  annotTextDraft.value = '';
}

// --- Režim "Upravit" — výběr, přetažení, změna velikosti textu/dynamiky ---
// Vrátí ohraničující box prvku (plocha, kam lze kliknout pro výběr rukou), nebo null
function itemBox(it) {
  let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
  const pad = 10;
  if (it.tool === 'text' || it.tool === 'dynamic') {
    if (it.x == null || it.y == null) return null;
    const s = it.size || 20;
    x1 = it.x; y1 = it.y - s;
    // Dynamika = šířka glyfu z metrik fontu; text = odhad podle počtu znaků
    const w = it.tool === 'dynamic'
      ? dynAdvEm(it.text) * s
      : (it.text ? Math.max(s, it.text.length * s * 0.6) : s);
    x2 = it.x + w; y2 = it.y;
  } else if (isStroke(it)) {
    if (!it.points || !it.points.length) return null;
    for (const p of it.points) {
      if (p.x < x1) x1 = p.x; if (p.y < y1) y1 = p.y;
      if (p.x > x2) x2 = p.x; if (p.y > y2) y2 = p.y;
    }
  } else if (it.tool === 'crescendo' || it.tool === 'decrescendo') {
    if (it.x1 == null) return null;
    const xs = [it.x1, it.x2, it.x3], ys = [it.y1, it.y2, it.y3];
    x1 = Math.min(...xs); x2 = Math.max(...xs);
    y1 = Math.min(...ys); y2 = Math.max(...ys);
  } else if (it.tool === 'highlighter') {
    if (it.x1 == null) return null;
    x1 = Math.min(it.x1, it.x2); x2 = Math.max(it.x1, it.x2);
    y1 = Math.min(it.y1, it.y2); y2 = Math.max(it.y1, it.y2);
  } else {
    return null;
  }
  return { x: x1 - pad, y: y1 - pad, w: (x2 - x1) + pad * 2, h: (y2 - y1) + pad * 2 };
}
// Skok, jehož obdélník je pod daným bodem (pro tažení i pro klepnutí)
function jumpAtPoint(p) {
  for (const j of jumps.value) {
    if (!j.place) continue;
    if (j.fromPage !== currentPage.value) continue;
    const b = j.place;
    if (p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h) return { j };
  }
  return null;
}
// Skoky na aktuální stránce rozdělené podle toho, zda mají umístění na notách
const jumpsOnPage = computed(() => jumps.value.filter(j => j.fromPage === currentPage.value));
const placerJumps = computed(() => jumpsOnPage.value.filter(j => j.place));
const edgeJumps = computed(() => jumpsOnPage.value.filter(j => !j.place));
// Styl obdélníku tlačítka na stránce (v souřadnicích anotační vrstvy = CSS px)
function jumpBoxStyle(j) {
  const b = j.place;
  if (!b) return {};
  return {
    left: b.x + 'px', top: b.y + 'px',
    width: b.w + 'px', height: b.h + 'px',
  };
}
function pageHits(p) {
  // Najde anotaci na stránce, do jejíž celé plochy (boxu) kliknutí patří.
  // Reaguje tak prakticky všude v oblasti prvku, ne jen na jeho střed.
  const items = pageItems.value;
  let best = null, bestArea = Infinity;
  for (const it of items) {
    const b = itemBox(it);
    if (!b || p.x < b.x || p.y < b.y || p.x > b.x + b.w || p.y > b.y + b.h) continue;
    const area = b.w * b.h;
    if (area < bestArea) { bestArea = area; best = it; }
  }
  return best;
}
function editText(it) {
  annotTextDraft.value = it.text || '';
  editingAnnotationId.value = it.id;
}
function resizeAnnot(it, dir) {
  if (!it) return;
  it.size = Math.max(10, it.size + dir * 4);
  saveAnnotations();
}
function endEdit() {
  editingId.value = null;
}
function deleteEditing() {
  const id = editingId.value;
  if (!id) return;
  pushHistory();
  annotations.value.items = annotations.value.items.filter(x => x.id !== id);
  editingId.value = null;
  saveAnnotations();
}

// History (undo/redo)
function pushHistory() {
  history.value.push(JSON.parse(JSON.stringify(annotations.value.items)));
  if (history.value.length > 50) history.value.shift();
  redoStack.value = []; // nový tah vymaže redo
}

// Vzdálenost bodu od úsečky
function distToSeg(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1, dy = y2 - y1;
  const len2 = dx * dx + dy * dy;
  if (len2 === 0) return Math.hypot(px - x1, py - y1);
  let t = ((px - x1) * dx + (py - y1) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

// Je guma (polyčára pts o šířce w) v kontaktu s anotací it?
function strokeUnder(pts, w, it) {
  // Tah / klín: body či ramena anotace
  const seg = [];
  if (it.points && it.points.length) seg.push(...it.points);
  if (it.x1 != null) seg.push({ x: it.x1, y: it.y1 }, { x: it.x2, y: it.y2 }, { x: it.x3, y: it.y3 });
  if (seg.length) {
    for (const pt of seg) {
      for (let i = 0; i < pts.length - 1; i++) {
        if (distToSeg(pt.x, pt.y, pts[i].x, pts[i].y, pts[i + 1].x, pts[i + 1].y) < w) return true;
      }
    }
    return false;
  }
  // Text / dynamika: střed (x,y)
  if (it.x != null) {
    for (let i = 0; i < pts.length - 1; i++) {
      if (distToSeg(it.x, it.y, pts[i].x, pts[i].y, pts[i + 1].x, pts[i + 1].y) < w) return true;
    }
  }
  return false;
}

// Vzdálenost bodu od lomené čáry poly (fine segment) = minimum přes úsečky
function distToPoly(px, py, poly) {
  let best = Infinity;
  for (let i = 0; i < poly.length - 1; i++) {
    const d = distToSeg(px, py, poly[i].x, poly[i].y, poly[i + 1].x, poly[i + 1].y);
    if (d < best) best = d;
  }
  return best;
}

// Vzdálenost dvou úseček (segment-segment distance)
function distSegSeg(a1x, a1y, a2x, a2y, b1x, b1y, b2x, b2y) {
  // minimum ze 4 distToSeg (bod na jedné úsečce k druhé) stačí pro náš účel
  const d1 = distToSeg(a1x, a1y, b1x, b1y, b2x, b2y);
  const d2 = distToSeg(a2x, a2y, b1x, b1y, b2x, b2y);
  const d3 = distToSeg(b1x, b1y, a1x, a1y, a2x, a2y);
  const d4 = distToSeg(b2x, b2y, a1x, a1y, a2x, a2y);
  return Math.min(d1, d2, d3, d4);
}

// Dotkne se guma (fine-segment o poloměru r) prvku it? (klín/text/dynamika/zvýrazňovač)
function segOnUnder(fine, r, it) {
  const pts = [];
  if (it.tool === 'highlighter' && it.x1 != null) {
    // zvýrazňovač = obdélník: smaže se, když guma protne jeho box
    const x1 = Math.min(it.x1, it.x2), y1 = Math.min(it.y1, it.y2);
    const x2 = Math.max(it.x1, it.x2), y2 = Math.max(it.y1, it.y2);
    // zkontroluj, jestli guma přejela přes obdélník (segment protne box)
    for (let j = 0; j < fine.length - 1; j++) {
      const a = fine[j], b = fine[j + 1];
      if (segCrossRect(a.x, a.y, b.x, b.y, x1, y1, x2, y2)) return true;
    }
    return false;
  }
  if (it.x1 != null) pts.push({ x: it.x1, y: it.y1 }, { x: it.x2, y: it.y2 }, { x: it.x3, y: it.y3 });
  else if (it.x != null) pts.push({ x: it.x, y: it.y });
  for (const pt of pts) {
    if (distToPoly(pt.x, pt.y, fine) < r) return true;
  }
  return false;
}
// Protne úsečka (a→b) obdélník (x1,y1,x2,y2)?
function segCrossRect(ax, ay, bx, by, rx1, ry1, rx2, ry2) {
  // rychlá bounding-box odmítnutí
  if (Math.max(ax, bx) < rx1 || Math.min(ax, bx) > rx2 || Math.max(ay, by) < ry1 || Math.min(ay, by) > ry2) return false;
  // kontrola každé hrany obdélníku pro průnik s úsečkou
  const edges = [[rx1,ry1,rx2,ry1],[rx2,ry1,rx2,ry2],[rx2,ry2,rx1,ry2],[rx1,ry2,rx1,ry1]];
  for (const [e1x,e1y,e2x,e2y] of edges) {
    if (distSegSeg(ax,ay,bx,by,e1x,e1y,e2x,e2y) === 0) return true;
  }
  return false;
}

// Guma na tahu (tužka/zvýrazňovač): vhodí jen BODY čáry, které jsou uvnitř
// poloměru r od dráhy gumy (fine), a zbylé sousedící body rozdělí na souvislé
// kusy. Zachovává i kusy s 1 bodem (vykreslí se jako tečka), takže krátký tah
// protnutý gumou se nikdy celý nevypustí — guma smaže jen to, co protne.
// Vrací pole nových itemů (0 = celý tah pryč, null = kousek není kontakt).
function eraseStrokeOnSeg(it, fine, r) {
  const orig = (it.points || []);
  if (!orig.length) return null;
  const keep = [];
  for (const pt of orig) {
    let under = false;
    for (let j = 0; j < fine.length - 1; j++) {
      if (distToSeg(pt.x, pt.y, fine[j].x, fine[j].y, fine[j + 1].x, fine[j + 1].y) <= r) {
        under = true; break;
      }
    }
    if (!under) keep.push(pt);
  }
  if (keep.length === orig.length) return null;   // nedotklo se
  if (keep.length === 0) return [];                 // celý tah pryč
  // rozdělit zbylé body na souvislé podsahy (sousedící body ≤1.7px k sobě;
  // izolované body zůstanou jako samostatné kusy a vykreslí se jako tečky)
  const out = [];
  let cur = [];
  for (let i = 0; i < keep.length; i++) {
    if (cur.length) cur.push(keep[i]);
    else cur = [keep[i]];
    const next = keep[i + 1];
    const last = cur[cur.length - 1];
    if (i === keep.length - 1 || !next || Math.hypot(next.x - last.x, next.y - last.y) > 1.8) {
      out.push(mkStroke(it, cur.slice()));   // i 1-bodový kus zachovej (tečka)
      cur = [];
    }
  }
  return out;
}
function mkStroke(it, pts) {
  return {
    id: crypto.randomUUID(), page: it.page,
    tool: it.tool, color: it.color, opacity: it.opacity, width: it.width,
    points: pts.map(pt => ({ x: pt.x, y: pt.y })),
  };
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
function resetView() { zoom.value = songZoom.value; panX.value = 0; panY.value = 0; }

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
  if (jumpMode.value) { annotMode.value = false; endEdit(); zoomPanelOpen.value = false; } // jiný panel → vypnout anotaci i výběr prvku
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
  jumps.value.push({
    id: crypto.randomUUID(), fromPage: jumpStart.value, toPage: jumpEnd.value, label,
    // Umístění na stránce (nepovinné) — kde přesně má tlačítko na notách stát
    place: jumpPlace.value ? { ...jumpPlace.value } : null,
  });
  await dbSaveJumps({ songId: song.id, items: jumps.value });
  jumpMode.value = false; jumpStart.value = null; jumpEnd.value = null; jumpLabel.value = '';
  jumpPlace.value = null; jumpPlaceMode.value = false; jumpPlacePoints.value = [];
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

// --- Ruční zadání čísla stránky (indikátor nahoře) ---
// Jan: "dalo by se ručně zadat číslo stránky, na kterou chci skočit" — klik na číslo
// v indikátoru stránky otevře zadání; 1-based vstup, uvnitř se pracuje s 0-based currentPage.
const pageGoOpen = ref(false);
const pageGoValue = ref('');
const pageGoInputEl = ref(null);
let _pageGoPrevPage = null;   // stránka, ze které jsme zadání otevřeli (Esc = zpět na ni)

function openPageGo() {
  _pageGoPrevPage = currentPage.value;
  pageGoValue.value = String(currentPage.value + 1);
  pageGoOpen.value = true;
  // panel se otevře i mimo anotační režim; ostatní mody zavřít, aby se nepřekrývaly
  annotMode.value = false; jumpMode.value = false; bookmarkMode.value = false; sliderOpen.value = false;
  endEdit(); // zrušit výběr prvku — jinak by rámeček zůstal viset přes dialog
  nextTick(() => {
    const el = pageGoInputEl.value;
    if (el) { el.focus(); el.select(); }
  });
}
function closePageGo() {
  pageGoOpen.value = false;
}
// Zadej číslo → skoč na stránku; prázdný/neplatný vstup nebo Esc → zpět na výchozí stránku
function goToTypedPage() {
  const raw = String(pageGoValue.value).trim();
  const n = parseInt(raw, 10);
  pageGoOpen.value = false;
  if (!raw || !Number.isFinite(n)) return;
  const target = Math.max(0, Math.min(totalPages.value - 1, n - 1));
  // gotoPage je synchronní fire-and-forget (token v renderCurrent vykreslí jen poslední stránku)
  if (target === currentPage.value && _pageGoPrevPage === target) return;
  gotoPage(target);
}

// --- Záložky (konkrétní stránky) ---
function openBookmark() {
  // Opětovný tap na tlačítko záložek panel ZAVŘE (jinak se dal jen otevřít
  // a ven se šlo přes "Zavřít" v panelu).
  if (bookmarkMode.value) {
    bookmarkMode.value = false;
    bookmarkLabel.value = '';
    bookmarkEditing.value = null;
    return;
  }
  bookmarkMode.value = true;
  annotMode.value = false;  // jiný panel → vypnout anotaci
  zoomPanelOpen.value = false;
  endEdit();               // a zrušit výběr prvku (rámeček by zůstal viset)
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
// --- Řazení záložek tažením za táhlo (drag & drop) ---
// Jan: v úpravě záložek chce měnit pořadí tažením, ne šipkami.
// Řádek se přesouvá živě podle polohy prstu; do IndexedDB se ukládá až po puštění (jeden zápis).
const bmDragId = ref(null);       // id záložky, která se právě táhne (jen vizuální stav)
let _bmDrag = null;               // { id, lastY, moved }
let _bmSaveTimer = null;

function bmRows(el) {
  const list = el.closest('.jp-list');
  return list ? Array.from(list.querySelectorAll('.jp-item')) : [];
}
function bmNoop() {}   // dlaždicové touch eventy jen pohlcujeme, ať je .viewer nebere jako swipe
function bmDragStart(e, b) {
  if (_bmDrag) return;
  e.stopPropagation();
  _bmDrag = { id: b.id, lastY: e.clientY, moved: false };
  try { e.currentTarget.setPointerCapture(e.pointerId); } catch (err) { /* ignorovat */ }
  e.preventDefault();
}
function bmDragMove(e) {
  const d = _bmDrag;
  if (!d) return;
  if (!d.moved) {
    if (Math.abs(e.clientY - d.lastY) < 6) return;  // tolerance: tap na táhlo nic neposouvá
    d.moved = true;
    bmDragId.value = d.id;
  }
  d.lastY = e.clientY;
  const arr = bookmarks.value;
  const rows = bmRows(e.currentTarget);
  if (rows.length !== arr.length) return;
  let i = arr.findIndex(x => x.id === d.id);
  if (i < 0) return;
  let moved = false;
  while (i > 0) {                                   // nahoru přes střed předchozího řádku
    const r = rows[i - 1].getBoundingClientRect();
    if (e.clientY >= r.top + r.height / 2) break;
    [arr[i - 1], arr[i]] = [arr[i], arr[i - 1]];
    rows.splice(i - 1, 0, rows.splice(i, 1)[0]);
    i--; moved = true;
  }
  while (i < arr.length - 1) {                      // dolů přes střed následujícího řádku
    const r = rows[i + 1].getBoundingClientRect();
    if (e.clientY <= r.top + r.height / 2) break;
    [arr[i], arr[i + 1]] = [arr[i + 1], arr[i]];
    rows.splice(i + 1, 0, rows.splice(i, 1)[0]);
    i++; moved = true;
  }
  if (moved) bmScheduleSave();
}
function bmDragEnd() {
  const d = _bmDrag;
  if (!d) return;
  _bmDrag = null;
  bmDragId.value = null;
  if (d.moved) bmSaveNow();                          // jeden zápis po dokončení tažení
}
function bmScheduleSave() {
  clearTimeout(_bmSaveTimer);
  _bmSaveTimer = setTimeout(() => { _bmSaveTimer = null; bmSaveNow(); }, 400);
}
function bmSaveNow() {
  clearTimeout(_bmSaveTimer);
  _bmSaveTimer = null;
  return dbSaveBookmarks({ songId: song.id, items: bookmarks.value });
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
  height: 100dvh; /* přesně výška obrazovky → overlay kotvy (lišta nahoře, záložky dole) kotví proti viewportu */
  min-height: 0;
  background: var(--bg); display: flex; flex-direction: column;
  /* touch-action: none — VŠECHNA gesta si bere naše JS obsluha.
     Tohle je jediná spolehlivá obrana proti SYSTÉMOVÉMU GESTU ZPĚT: s 'pan-x pan-y'
     si Chrome horizontální swipe vyložil jako "panování" a když nebylo kam
     scrollovat, udělal z něj gesto zpět a vyhodil aplikaci do knihovny (ověřeno
     na 11 startovacích pozicích, chytalo se to až do poloviny šířky displeje).
     Scrollovací lišty (záložky, miniatury) si posun povolují vlastním
     touch-action: pan-x níže — jinak by se přestaly posouvat. */
  touch-action: none;
  overscroll-behavior-x: none;
}

/* ===== JEDINÁ HORNÍ LIŠTA =====
   Jeden řádek, absolutně pozicovaná (neodtlačuje dokument dolů — noty mají
   vlastní plochu s odpovídajícím paddingem). Lehce průhledná, ať není těžká.
   Plochá, bez hover/focus efektů (Jan: mobilní PWA) — feedback jen :active / .on. */
.top-bar {
  position: absolute; top: 0; left: 0; right: 0;
  display: flex; flex-direction: row; align-items: center;
  padding: 3px 8px;
  padding-top: calc(3px + env(safe-area-inset-top, 0px));
  /* Velikost prvků roste s šířkou displeje. Dřív jsem je zmenšila napevno, aby se
     "vešly" — jenže na širším displeji pak zůstaly malé v levém rohu a zbytek lišty
     byl prázdný. Pružná velikost + space-between vyplní lištu na každé šířce. */
  /* --tb = velikost hlavního tlačítka. 9.2vw dá na 412px displeji ~38 px
     (pohodlný dotyk), na malém telefonu se zastaví na 33 px, na tabletu na 50 px.
     Dřív tu bylo 4.6vw, což vyšlo na ~19 px — clamp vždy skončil na minimu
     a tlačítka zůstala malá bez ohledu na šířku displeje. */
  --tb: clamp(34px, 10vw, 48px);
  /* Lehká průhlednost + jemný rozostření pozadí — noty pod lištou neprosvítají rušivě */
  background: rgba(38, 34, 32, 0.78);
  backdrop-filter: blur(3px);
  -webkit-backdrop-filter: blur(3px);
  border-bottom: 1px solid var(--border);
  /* Když je displej úzký (telefon na výšku), méně důležité prvky se odsunou
     do strany — scrollbar skrytý, ať lišta zůstane čistá. */
  overflow-x: auto; overflow-y: hidden;
  scrollbar-width: none; -ms-overflow-style: none;
  touch-action: pan-x;
  /* Vlastní vrstva NAD podkladem modalu (41) — podklad je zkrácený pod lištu,
     takže lišta zůstává čitelná a klikatelná i s otevřeným modalem. */
  z-index: 45;
}
.top-bar::-webkit-scrollbar { display: none; }
.tb-row {
  display: flex; align-items: center; justify-content: space-between;
  gap: clamp(3px, 1.2vw, 12px);
  min-height: 38px; width: 100%;
}
/* Levá a pravá skupina tlačítek */
/* Obě skupiny stejně široké (1 1 0) — tím je počítadlo mezi nimi PŘESNĚ
   uprostřed a tlačítka se drží u okrajů. Dřív měla levá jen tlačítko zpět,
   takže byla prázdná a počítadlo se překrývalo s tlačítky. */
/* Skupiny NEROSTOU (0 1 auto) — jinak by se jejich obsah tlačil do středu
   a tlačítka by zajela pod počítadlo (ověřeno: 28 px překryv). */
.tb-side { display: flex; align-items: center; gap: clamp(3px, 1.2vw, 12px);
           flex: 0 1 auto; min-width: 0; }
.tb-side.left { justify-content: flex-start; }
.tb-side.right { justify-content: flex-end; }
/* Rezerva na středu: roste a drží odstup tlačítek od počítadla.
   min-width musí být VŽDY větší než šířka počítadla, aby se nikdy nepřekryla. */
.tb-mid-space { flex: 1 1 auto; min-width: clamp(60px, 16vw, 90px); }
.tb-btn {
  width: var(--tb, 38px); height: var(--tb, 38px); flex: 0 0 auto; padding: 0;
  border-radius: 50%; border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); font-size: 1.05rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  touch-action: manipulation;
}
.tb-btn.sm { width: calc(var(--tb, 38px) - 8px); height: calc(var(--tb, 38px) - 8px); font-size: 1rem; }
.tb-btn.sm svg { width: calc(var(--tb, 38px) * 0.46); height: calc(var(--tb, 38px) * 0.46); }
/* Tlačítko zvětšení má místo ikony text s procenty — potřebuje víc šířky */
.tb-btn.zoom-btn { width: auto; min-width: calc(var(--tb, 38px) + 8px); padding: 0 7px;
  font-size: clamp(0.75rem, 1.9vw, 0.9rem); font-weight: 600; border-radius: 16px; }
.tb-btn.on { background: var(--accent); color: #17130f; border-color: var(--accent); }
.tb-btn:disabled { opacity: 0.3; pointer-events: none; }
.tb-btn:active { background: var(--bg-elev); }

/* Název skladby — zabírá zbylé místo, zkracuje se třemi tečkami */
.tb-song {
  /* POZOR: nesmí mít flex-grow. Prázdný (bez skupiny) si jinak bere všechno
     volné místo a odtlačí tlačítka doleva — lišta pak byla zaplněná z 40 %. */
  flex: 0 1 auto; min-width: 0; max-width: 24vw;
  font-weight: 600; font-size: clamp(0.8rem, 1.7vw, 1rem); color: var(--text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
/* Počítadlo stránek — na PŘESNÉM středu lišty (nezávisle na šířce skupin).
   Klik otevře ruční zadání stránky. */
.tb-page-center {
  position: absolute; left: 50%; top: 50%;
  transform: translate(-50%, -50%);
  z-index: 1;
}
/* Počítadlo stránek — klik otevře ruční zadání stránky */
.tb-page {
  flex: 0 0 auto; background: transparent; border: 1px solid var(--border);
  border-radius: 14px; padding: 4px 9px; font: inherit;
  font-size: clamp(0.8rem, 2vw, 0.95rem);
  font-weight: 600; color: var(--text-dim); cursor: pointer;
  touch-action: manipulation; white-space: nowrap;
}
.tb-page:active { background: var(--bg-elev2); }
.tb-zoom {
  flex: 0 0 auto; min-width: 34px; text-align: center;
  font-size: clamp(0.74rem, 1.5vw, 0.9rem); color: var(--text-dim); font-weight: 600;
}
.tb-sep { display: none; }
.tb-nav { display: flex; align-items: center; gap: 3px; }
.tb-grp {
  font-size: 0.8rem; font-weight: 600; color: var(--text);
  min-width: 32px; text-align: center;
}

/* Panel zvětšení — otevírá se z tlačítka s procenty, kotví se POD lištu */
.zoom-panel {
  position: absolute; top: calc(var(--topbar-h, 96px) + 6px); left: 50%;
  transform: translateX(-50%);
  display: flex; align-items: center; gap: 8px;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 26px;
  padding: 8px 12px; box-shadow: 0 4px 18px rgba(0,0,0,0.6); z-index: 30;
}
.zp-btn {
  width: 44px; height: 44px; flex: 0 0 auto; padding: 0;
  border-radius: 50%; border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); font-size: 1.3rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center; touch-action: manipulation;
}
.zp-btn.on { background: var(--accent); color: #17130f; border-color: var(--accent); }
.zp-val { min-width: 56px; text-align: center; font-size: 1rem; font-weight: 600; color: var(--text); }
.zp-sep { width: 1px; height: 26px; background: var(--border); }

/* Oblast stránky pod lištou — z její velikosti se počítá fit not */
.page-area {
  flex: 1 1 auto; min-height: 0; position: relative;
  /* Lišta je absolutní overlay (neposouvá dokument), ale noty pod ni zajet nesmí —
     plocha si proto drží odsazení přesně o její výšku. */
  padding-top: var(--topbar-h, 96px);
  display: flex; align-items: center; justify-content: center;
  /* overflow: hidden má DVA důvody:
     1) Stránka nesmí přetéct nad horní lištu ani pod displej. V krajině je
        fit-na-šířku vyšší než plocha (noty se ořezávají výškou — to je záměr),
        takže bez ořezu canvas zalézal pod lištu (ověřeno: top: -383 px).
     2) Z plochy se tím stane scroll kontejner, a teprve pak se na ni uplatní
        touch-action: none. Chrome bere touch-action z nejbližšího SCROLL
        kontejneru — s overflow: visible se .page-area přeskočila, použil se
        .viewer (pan-x pan-y) a ze swipu vpravo vzniklo SYSTÉMOVÉ GESTO ZPĚT
        (aplikace se vyhodila do knihovny). V portraitu to prošlo jen náhodou,
        protože se stránka vešla a nebylo co panovat. */
  overflow: hidden;
  touch-action: none;
  overscroll-behavior-x: none;
}
.stage { position: relative; touch-action: none; }
.pdf-canvas { display: block; background: #fff; box-shadow: 0 2px 14px rgba(0,0,0,0.6); border-radius: 6px; touch-action: none; }
.annot-layer { position: absolute; top: 0; left: 0; touch-action: none; cursor: crosshair; }
.annot-layer.active { pointer-events: auto; }
.annot-layer.active + .stage {  }
.annot-layer:not(.active) { pointer-events: none; }
.annot-layer .hl { mix-blend-mode: multiply; opacity: 0.9; }

/* ===== Panely a modaly se kotví POD horní lištu (tlačítko i panel u sebe) ===== */

/* Tlačítko skoku umístěné PŘÍMO NA NOTÁCH — obdélník, který si uživatel
   naklepal třemi body (levý horní, levý spodní, pravý) a může ho posouvat tažením.
   Souřadnice jsou ve stejné soustavě jako anotační vrstva (CSS px stránky). */
.jump-on-page {
  position: absolute; top: 0; left: 0; width: 100%; height: 100%;
  pointer-events: none;   /* samotná vrstva nesmí blokovat kreslení/gesta */
  z-index: 19;
}
.jump-on-btn {
  position: absolute; pointer-events: auto;
  display: flex; align-items: center; justify-content: center;
  padding: 2px 6px; box-sizing: border-box;
  background: var(--accent); border: 1.5px solid var(--accent);
  border-radius: 8px; color: #17130f;
  font-weight: 700; font-size: clamp(0.7rem, 2vw, 0.95rem);
  line-height: 1.1; text-align: center; overflow: hidden;
  cursor: pointer; touch-action: manipulation;
}
.jump-on-btn:active { background: var(--bg-elev2); border-color: var(--border); color: var(--text); }
/* Nápověda u sběru tří bodů (v panelu skoku) */
.jp-hint {
  font-size: 0.82rem; color: var(--accent); font-weight: 600;
  background: var(--bg-elev2); border-radius: 8px; padding: 6px 8px;
}
/* Nápověda při umisťování tlačítka na noty — úzká lišta DOLE, aby nezakrývala
   noty, na které uživatel klepá. Panel skoku je při umisťování schovaný. */
.jp-place-hint {
  position: absolute; left: 50%; bottom: 16px; transform: translateX(-50%);
  display: flex; align-items: center; gap: 10px;
  background: var(--bg-elev); border: 1.5px solid var(--accent); border-radius: 22px;
  padding: 8px 16px; box-shadow: 0 4px 18px rgba(0,0,0,0.6); z-index: 32;
  font-size: 0.85rem; font-weight: 600; color: var(--text); white-space: nowrap;
}
.jp-place-count { color: var(--accent); font-weight: 700; }

/* Skoky (Da Capo / VIDE) bez umístění — velká tlačítka na pravém okraji.
   Jan je chce velké (mačkají se při zpěvu). */
.jump-strip {
  position: absolute; right: 16px;
  top: calc(var(--topbar-h, 96px) + (100dvh - var(--topbar-h, 96px)) / 2);
  display: flex; flex-direction: column; align-items: flex-end; gap: 8px; z-index: 24;
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
  position: absolute; top: calc(var(--topbar-h, 96px) + 8px); left: 16px;
  display: flex; flex-direction: column; gap: 8px;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 16px;
  padding: 12px; box-shadow: 0 4px 18px rgba(0,0,0,0.6); z-index: 25; max-width: 94vw;
  /* Panel sám nikdy nesmí přetéct mimo displej (Jan: seznam záložek přetékal dolů).
     Přebytek řeší scroll uvnitř .jp-list, takže zadávací pole i tlačítko Zavřít
     zůstávají pořád vidět. */
  max-height: calc(100dvh - var(--topbar-h, 96px) - 24px);
  overflow: hidden;
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

/* Záložky — vždy viditelná lišta u spodní hrany, overlay nad plátnem.
   position: fixed → kotví proti viewportu (obrazovce), ne proti výšce plátna,
   takže se nemůže dostat pod obraz, ať je canvas jakkoli velký. */
.bookmark-strip {
  position: fixed; left: 16px; right: 16px; bottom: 12px;
  display: flex; flex-wrap: nowrap; gap: 8px; align-items: center;
  justify-content: flex-start; z-index: 22;
  overflow-x: auto; overflow-y: hidden;    /* jediný řádek, při přetečení horizontální scroll */
  scrollbar-width: none;                   /* skrýt scrollbar (Firefox) */
  -ms-overflow-style: none;                /* (IE) */
  padding: 8px 12px;
  pointer-events: auto;                     /* lišta musí reagovat, aby šla horizontálně scrollovat */
  /* .viewer má touch-action: none (obrana proti gestu zpět), takže posun
     musíme povolit tady — jinak by lišta přestala scrollovat. */
  touch-action: pan-x;
  background: rgba(28,25,23,0.85);          /* podbarvení panelu záložek */
  border: 1px solid var(--border);
  border-radius: 24px;
  backdrop-filter: blur(2px);
  box-shadow: 0 4px 18px rgba(0,0,0,0.5);
}
.bookmark-strip::-webkit-scrollbar { display: none; }  /* skrýt scrollbar (Chrome/Safari) */
.bookmark-btn {
  flex: 0 0 auto; display: inline-flex; align-items: center; gap: 6px;
  background: var(--bg-elev); border: 1px solid var(--border);
  border-radius: 20px; padding: 6px 12px;
  font-size: 0.92rem; font-weight: 600; color: var(--text);
  cursor: pointer; touch-action: manipulation; pointer-events: auto;
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

/* Ruční zadání stránky — plovoucí modal, plochý design bez karet.
   Podklad začíná AŽ POD horní lištou (top: var(--topbar-h)), aby lišta zůstala
   viditelná a klikatelná — jinak klepnutí na lištu spadlo do podkladu a modal
   se zavřel. Klik mimo kartu (na podklad) modal pořád zavírá. */
.page-go-backdrop {
  position: fixed; left: 0; right: 0; bottom: 0; top: var(--topbar-h, 96px); z-index: 41;
  background: rgba(0,0,0,0.35);
  display: flex; align-items: flex-start; justify-content: center;
  padding: 16px;
}
.page-go {
  display: flex; flex-direction: column; gap: 10px;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 16px;
  padding: 12px 14px; box-shadow: 0 4px 18px rgba(0,0,0,0.6); max-width: 94vw;
}
.pg-label { font-weight: 700; font-size: 0.95rem; }
.pg-row { display: flex; align-items: center; gap: 8px; }
.pg-input {
  width: 84px; background: var(--bg-elev2); border: 1px solid var(--border);
  border-radius: 10px; padding: 8px 10px; color: var(--text); font-size: 1rem;
  font-weight: 600; text-align: center;
}
.pg-total { color: var(--text-dim); font-size: 0.9rem; font-weight: 600; }
.pg-btn {
  background: var(--bg-elev2); border: 1px solid var(--border);
  border-radius: 10px; padding: 8px 12px; font-size: 0.9rem; color: var(--text); cursor: pointer;
  touch-action: manipulation;
}
.pg-btn.primary { background: var(--accent); color: #17130f; border-color: var(--accent); font-weight: 600; }

.jp-actions { margin-left: auto; display: flex; align-items: center; gap: 2px; }
.jp-drag {
  width: 32px; height: 32px; flex: 0 0 auto; padding: 0;
  background: transparent; border: none; border-radius: 50%;
  color: var(--text-dim); display: flex; align-items: center; justify-content: center;
  cursor: grab; touch-action: none;   /* touch-action: none → tažení neposouvá stránku */
}
.jp-drag:active { color: var(--text); }
.jp-item.dragging { border-color: var(--accent); }
.jp-item.dragging .jp-drag { color: var(--accent); }
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

/* Přehled stránek (miniatury + slider) — přes celou šířku, POD horní lištou
   (tlačítko i panel u sebe), ať nekryje spodní lištu záložek. */
.slider-panel {
  position: absolute; top: var(--topbar-h, 96px); left: 0; right: 0;
  display: flex; flex-direction: column; gap: 10px;
  background: var(--bg-elev); border-bottom: 1px solid var(--border);
  padding: 12px 25px 16px; box-shadow: 0 4px 18px rgba(0,0,0,0.6); z-index: 30;
}
.thumb-strip {
  display: flex; gap: 8px; overflow-x: auto; padding: 0;
  scrollbar-width: thin; -webkit-overflow-scrolling: touch;
  touch-action: pan-x;   /* viz lišta záložek — .viewer má none */
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
/* Seznam existujících záložek / skoků — SCROLLOVATELNÝ.
   Při mnoha záložkách jinak přetékal pod okraj displeje a poslední nebyly
   dosažitelné. Pole pro novou záložku a "Zavřít" zůstávají vidět nad/pod ním. */
.jp-list {
  display: flex; flex-direction: column; gap: 6px;
  border-top: 1px solid var(--border); padding-top: 10px;
  overflow-y: auto; overflow-x: hidden;
  max-height: min(46dvh, 340px);
  -webkit-overflow-scrolling: touch;
  touch-action: pan-y;   /* svislý posun seznamu (lišta má touch-action: none) */
}
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

/* Plovoucí tlačítka byla zrušena — všechna ovládací tlačítka jsou v horní liště. */

/* Plovoucí panel anotací — větší, kategorizovaný. Kotví se POD horní lištu.
   position: fixed → přes overlay; max-height s interním scrollením. */
.annot-panel {
  position: absolute; top: calc(var(--topbar-h, 96px) + 8px); left: 16px;
  display: flex; flex-direction: column; align-items: stretch; gap: 12px;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 18px;
  padding: 12px; box-shadow: 0 4px 18px rgba(0,0,0,0.6);
  z-index: 26; max-width: 96vw; min-width: 220px;
  max-height: calc(100dvh - var(--topbar-h, 96px) - 24px);
  overflow-y: auto;
}
.ap-header {
  display: flex; align-items: center; justify-content: space-between;
  width: 100%;
}
.ap-title { font-weight: 700; font-size: 0.95rem; }
.ap-cat { display: flex; flex-direction: column; gap: 8px; }
.ap-cat-label {
  font-size: 0.72rem; font-weight: 600; letter-spacing: 0.5px;
  text-transform: uppercase; color: var(--text-dim);
}
.ap-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.toggle-row { width: 100%; }
.ap-collapse {
  width: 32px; height: 32px; flex: 0 0 auto; padding: 0;
  background: transparent; border: none; border-radius: 50%;
  color: var(--text-dim); display: flex; align-items: center; justify-content: center;
  cursor: pointer; touch-action: manipulation;
}
.ap-collapse:active { color: var(--text); }
.ap-collapse-label { font-size: 0.85rem; color: var(--text-dim); cursor: pointer; }
.ap-tool.mus { font-size: 1.15rem; font-weight: 700; }
/* Ikona nástroje Dynamika = skutečný glyf z fontu NotyDyn (ne unicode 𝆏, který
   se na různých zařízeních vykresluje různě nebo vůbec). */
.dyn-ico { font-family: 'NotyDyn', serif; font-size: 1.5rem; line-height: 1; }
.op-row { width: 100%; gap: 8px; }
.ap-op-label { font-size: 0.8rem; color: var(--text-dim); white-space: nowrap; }
.ap-opacity { flex: 1; min-width: 0; accent-color: var(--accent); height: 4px; }
.ap-op-val { font-size: 0.8rem; color: var(--text-dim); min-width: 32px; text-align: right; }
.ap-tool {
  width: 40px; height: 40px; flex: 0 0 auto; min-width: 0; padding: 0;
  border-radius: 50%; box-sizing: border-box;
  border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); font-size: 1.15rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  touch-action: manipulation;
}
.ap-tool.on { background: var(--accent); color: #17130f; border-color: var(--accent); }
.ap-tool:disabled { opacity: 0.35; pointer-events: none; }
.ap-color {
  width: 30px; height: 30px; flex: 0 0 auto; min-width: 0; padding: 0;
  border-radius: 50%; box-sizing: border-box;
  border: 2px solid var(--border); cursor: pointer;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}
.ap-color.on { border-color: var(--accent); }
.ap-size {
  width: 34px; height: 34px; flex: 0 0 auto; min-width: 0; padding: 0;
  border-radius: 50%; box-sizing: border-box;
  border: 1px solid var(--border); background: var(--bg-elev2);
  display: flex; align-items: center; justify-content: center; cursor: pointer;
}
.ap-size span { font-size: 0.9rem; color: var(--text); line-height: 1; }
.ap-size.on span { color: #fff; }
.ap-size.on { border-color: var(--accent); }
.ap-delpage { font-size: 0.55rem; font-weight: 700; margin-left: 1px; }

/* Pásmo úprav vybrané textové/dynamické anotace — POD horní lištou */
.edit-bar {
  position: fixed; left: 50%; top: calc(var(--topbar-h, 96px) + 8px); transform: translateX(-50%);
  display: flex; align-items: center; gap: 8px;
  background: var(--bg-elev); border: 2px solid var(--accent); border-radius: 32px;
  padding: 8px 14px; box-shadow: 0 4px 18px rgba(0,0,0,0.6);
  z-index: 27; max-width: 96vw;
}
.eb-type { font-weight: 600; font-size: 0.85rem; color: var(--accent); }
.eb-size { font-size: 0.8rem; color: var(--text-dim); }
.eb-val { font-size: 0.9rem; font-weight: 600; min-width: 20px; text-align: center; }
.eb-btn {
  width: 34px; height: 34px; flex: 0 0 auto; padding: 0;
  border-radius: 50%; border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); font-size: 1rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center; touch-action: manipulation;
}
.eb-btn.done { background: var(--accent); border-color: var(--accent); color: #17130f; font-weight: 700; }

/* Sběr bodů zobáčku — hint lišta */
.wedge-overlay {
  position: fixed; left: 50%; bottom: 14px; transform: translateX(-50%);
  z-index: 30;
}
.wedge-hint {
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 24px;
  padding: 10px 18px; font-size: 0.95rem; color: var(--text); font-weight: 600;
  box-shadow: 0 4px 18px rgba(0,0,0,0.6);
  display: flex; align-items: center; gap: 10px; white-space: nowrap;
}
.wedge-cancel { color: var(--accent); cursor: pointer; }

/* Text / dynamika — vstupní overlay */
.text-input-overlay {
  position: fixed; inset: 0; z-index: 40;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.45);
}
.text-input-card {
  display: flex; flex-direction: column; gap: 10px;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 16px;
  padding: 16px; width: 86vw; max-width: 420px; box-shadow: 0 6px 24px rgba(0,0,0,0.6);
}
.ti-label { font-weight: 700; font-size: 0.95rem; }
.ti-input {
  width: 100%; background: var(--bg-elev2); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px; color: var(--text); font-size: 1rem;
}
.ti-actions { display: flex; gap: 8px; justify-content: flex-end; }

/* Nabídka dynamik — dlaždice s hotovými glyfy z fontu NotyDyn.
   Uživatel tak vidí přesně to, co se vloží, a nemusí znát SMuFL kódy.
   Bez hoveru/focusu (Jan: mobilní PWA) — jediný feedback je :active. */
.dyn-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(56px, 1fr));
  gap: 6px;
}
.dyn-btn {
  display: flex; align-items: center; justify-content: center;
  font-family: 'NotyDyn', serif;
  font-size: 26px; line-height: 1;
  min-height: 46px; padding: 4px;
  background: var(--bg-elev2); border: 1px solid var(--border);
  border-radius: 10px; color: var(--text);
}
.dyn-btn.on { border-color: var(--accent); background: var(--bg-elev); }
.ti-warn { font-size: 0.8rem; color: var(--danger); }

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
/* Live preview bodů zobáčku — kroužky nesmí blokovat klikání na plátno */
.wedge-preview { pointer-events: none; }
/* Kolečko gumy — ploché, nesmí blokovat klikání; zviditelní rozsah gumy na plátně */
.eraser-cursor {
  pointer-events: none;
  fill: rgba(255,255,255,0.18);
  stroke: var(--accent, #d8a657);
  stroke-width: 1.5;
  stroke-dasharray: 4 3;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { color: var(--text-dim); font-size: 0.95rem; }
</style>
