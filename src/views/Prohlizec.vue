<template>
  <div
    class="viewer"
    ref="viewerEl"
    :style="{ '--topbar-h': barPad + 'px', '--page-pad': 'calc(8px + env(safe-area-inset-top, 0px))', '--page-pad-b': 'calc(8px + env(safe-area-inset-bottom, 0px))', '--edge-w': edgeW + 'px' }"
    @touchstart.passive="onTouchStart"
    @touchmove.passive="onTouchMove"
    @touchend.passive="onTouchEnd"
    @touchcancel.passive="onTouchCancel"
    @click="onTap"
  >
    <!-- JEDINÁ HORNÍ LIŠTA — trvale viditelná, vše na jednom místě.
         Jeden řádek: zpět · název skladby · počítadlo stránek · anotace · záložka · skok ·
         zvětšení (panel) · přehled stránek · listování sestavou
         Ploché, bez hover/focus efektů — jediný feedback je :active (Jan: mobilní PWA). -->
    <div class="top-bar" :class="{ hidden: barHidden }" ref="barEl">
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
        <!-- Počítadlo stránek — na PŘESNÉM středu lišty (klik otevře zadání stránky).
             Je UVNITŘ .tb-row (ne jako sourozenec), aby se na úzkém displeji dalo
             přepnout do toku a nikdy nepřekrylo tlačítka — absolutní pozicování
             se pořád počítá proti .top-bar, protože .tb-row je statický. -->
        <button class="tb-page tb-page-center" @click="openPageGo" title="Přejít na stránku">
          {{ withOffset(dispPage(currentPage)) }} / {{ withOffset(totalPages) }}<span v-if="hiddenPages.length" class="tb-page-of"> (z {{ withOffset(rawPageCount) }})</span>
        </button>
        <!-- Pravá skupina -->
        <div class="tb-side right">
        <button class="tb-btn" @click="toggleAnnot" :class="{ on: annotMode }" title="Anotace / listování">✏️</button>
        <!-- Uložení stavu a vycentrování — na HLAVNÍ LIŠTĚ, ne v panelu zoomu.
             Ukládací tlačítka měla dosud stejnou podobu jako ostatní akce panelu
             a uživatel nerozeznal, které z nich ukládá STRÁNKU a které CELOU
             SKLADBU (Jan: „když ho teď sdílí dvě různé funkce“). Na liště jsou
             vidět trvale a jejich stav (uloženo / neuloženo) je po ruce. -->
        <!-- Jedno tlačítko pro veškeré uložené zobrazení: po klepnutí se
             otevře menu preferencí (stránka / celá skladba / rám) s vlastním
             košem u každé skupiny. -->
        <button class="tb-btn sm" :class="{ on: prefsPanelOpen }" @click="togglePrefsPanel"
                title="Vycentrovat a preference zobrazení">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>
        </button>
        <!-- Zvětšení a posun — vlastní nabídka (dropdown). Gesto se v ní věnuje
             JEN zoomu a posunu, nikdy rotaci. -->
        <button class="tb-btn zoom-btn" @click="toggleZoomPanel" :class="{ on: zoomPanelOpen }" title="Zvětšení a posun">
          {{ Math.round(zoom * 100) }}%
        </button>
        <!-- Rotace — samostatná nabídka s vlastními tlačítky. Gesto se v ní věnuje
             JEN rotaci (žádný zoom ani posun). -->
        <button class="tb-btn zoom-btn" @click="toggleRotPanel" :class="{ on: rotPanelOpen }" title="Rotace stránky">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/></svg>
          <span class="tb-rot-deg">{{ rotLabel }}</span>
        </button>
        <button class="tb-btn" @click="toggleSlider" :class="{ on: sliderOpen }" title="Slider stránek">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 3v18"/></svg>
        </button>
        <!-- Odebrání stránek — vlastní nabídka (odebrat / vrátit). -->
        <button class="tb-btn" @click="togglePagesPanel" :class="{ on: pagesPanelOpen }" title="Odebrat stránky">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 9h8M8 13h8M9 17h6"/><path d="M3 3l18 18"/></svg>
        </button>
        </div>
      </div>
      <!-- Počítadlo stránek se přesunulo DOVNITŘ .tb-row (viz výše) — tady už není. -->
    </div>

    <!-- Panel ZVĚTŠENÍ A POSUNU — otevírá se z tlačítka s procenty v liště.
         Dokud je otevřený, gesto dvěma prsty dělá POUZE zoom a posun
         (rotace je vypnutá) — Jan: „Při otevření nabídky zoomu se bude dělat
         zoom a změna pozice.“ -->
    <div v-if="zoomPanelOpen" class="zoom-panel" data-panel="zoom" :style="panelStyle('zoom')">
      <button class="panel-grip" title="Tažením přesuň panel, klepnutím zpět na výchozí místo"
              @pointerdown="panelDragStart($event, 'zoom')" @pointermove="panelDragMove"
              @pointerup="panelDragEnd" @pointercancel="panelDragEnd"
              @touchstart.stop.prevent="noopTouch" @touchmove.stop.prevent="noopTouch"
              @touchend.stop="noopTouch" @touchcancel.stop="noopTouch">⠿</button>

      <!-- Vycentrovat a ukládání stavu jsou na HLAVNÍ LIŠTĚ (jsou to akce
           k celému zobrazení, ne k zoomu) — a `clearPageView` je tam taky,
           aby se tři ukládací akce nepletly dohromady v jednom panelu.
           Panel zoomu teď obsahuje jen dvě tlačítka (− a +) — ať nezabírá
           na obrazovce místo, které patří notám. -->
      <button class="zp-btn" @click="zoomOut" title="Oddálit">−</button>
      <span class="zp-val">{{ Math.round(zoom * 100) }} %</span>
      <button class="zp-btn" @click="zoomIn" title="Přiblížit">+</button>
      <button class="zp-btn num wide" @click="zoomFit" title="Zpět na 100 % (fit na šířku)">100 %</button>
      <span class="zp-sep" />
      <!-- Zoom dolů pod 100 % (Jan: „abych mohl oddálit stránku, když je
           originál moc velký") — meze jsou v ZOOM_MIN/ZOOM_MAX. -->
      <button class="zp-btn num" @click="zoomOutBig" title="Oddálit po 10 %">−10</button>
      <button class="zp-btn num" @click="zoomInBig" title="Přiblížit po 10 %">+10</button>
    </div>

    <!-- MENU PREFERENCÍ — otevírá ho tlačítko „Vycentrovat“ na hlavní liště.
         Plochá řada ikon zarovnaná DOLEVA: stránka / hvězda / ořez / střed.
         Stejné ikony, jaké měla tato tlačítka dřív na liště (Jan: „ponechal
         bych původní design tlačítek pro uložení“); textové „Uložit“ mizí.
         Koše jsou druhá, drobná řada — jen pro položky, které jsou uložené. -->
    <div v-if="prefsPanelOpen" class="zoom-panel prefs-panel" data-panel="prefs" :style="panelStyle('prefs')">
      <button class="panel-grip" title="Tažením přesuň panel, klepnutím zpět na výchozí místo"
              @pointerdown="panelDragStart($event, 'prefs')" @pointermove="panelDragMove"
              @pointerup="panelDragEnd" @pointercancel="panelDragEnd"
              @touchstart.stop.prevent="noopTouch" @touchmove.stop.prevent="noopTouch"
              @touchend.stop="noopTouch" @touchcancel.stop="noopTouch">⠿</button>

      <div class="prefs-row">
        <div class="prefs-slot">
          <button class="zp-btn prefs-icon" :class="{ on: hasSavedPageView }"
                  @click="savePageViewAsDefault" title="Uložit zobrazení této stránky">
            <svg width="18" height="18" viewBox="0 0 24 24" :fill="hasSavedPageView ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 3h11l5 5v13H4z"/><path d="M15 3v5h5"/><path d="M9 13h6M9 17h4"/></svg>
          </button>
          <!-- Koš je IKONA, ne text (Jan), ale sedí přesně v rohu ikony stránky,
               takže je jasné, kterou preferenci maže. -->
          <button v-if="hasSavedPageView" class="prefs-trash-badge" @click="deletePageView"
                  title="Smazat uložené zobrazení této stránky">
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16"/><path d="M9.5 7V4.5h5V7"/><path d="M6.5 7l1 13h9l1-13"/></svg>
          </button>
        </div>
        <div class="prefs-slot">
          <button class="zp-btn prefs-icon" :class="{ on: hasSavedZoom }"
                  @click="saveZoomAsDefault" title="Uložit zobrazení celé skladby">
            <svg width="18" height="18" viewBox="0 0 24 24" :fill="hasSavedZoom ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.6 6.8 19.1l1-5.8L3.5 9.2l5.9-.9z"/></svg>
          </button>
          <button v-if="hasSavedZoom" class="prefs-trash-badge" @click="deleteSongView"
                  title="Smazat výchozí zobrazení celé skladby">
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16"/><path d="M9.5 7V4.5h5V7"/><path d="M6.5 7l1 13h9l1-13"/></svg>
          </button>
        </div>
        <span class="zp-sep" />
        <button class="zp-btn prefs-icon" :class="{ on: pageFramed }"
                @click="toggleGlobalFrame" title="Oříznout okraje — celá skladba">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3v15h15"/><path d="M3 6h15v15"/></svg>
        </button>
        <button class="zp-btn prefs-icon" @click="resetView"
                title="Vycentrovat na uložené zobrazení">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>
        </button>
        <span class="zp-sep" />
        <!-- TOVÁRNÍ RESET zobrazení: smaže všechny preference (všechny stránky,
             celou skladbu i rám). Dvě klepnutí — první jen „nabije“ tlačítko
             (bez dialogu, Jan dialogy nechce), druhé do 4 s opravdu smaže. -->
        <button class="zp-btn prefs-icon prefs-reset" :class="{ armed: resetArmed }"
                @click="factoryResetViews"
                :title="resetArmed ? 'Klepni znovu — smaže všechny preference' : 'Smazat všechny preference (tovární reset zobrazení)'">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16"/><path d="M9.5 7V4.5h5V7"/><path d="M6.5 7l1 13h9l1-13"/><path d="M10 11v6M14 11v6"/></svg>
        </button>
      </div>
    </div>

    <!-- Panel ODEBRÁNÍ STRÁNEK — vlastní nabídka v liště. Odebírání je VRATNÉ:
         nic se nevyhazuje z PDF, jen se stránka přestane zobrazovat a listovat
         přes ni (anotace, záložky a skoky na ní zůstávají v datech). -->
    <div v-if="pagesPanelOpen" class="zoom-panel" data-panel="pages" :style="panelStyle('pages')">
      <button class="panel-grip" title="Tažením přesuň panel, klepnutím zpět na výchozí místo"
              @pointerdown="panelDragStart($event, 'pages')" @pointermove="panelDragMove"
              @pointerup="panelDragEnd" @pointercancel="panelDragEnd"
              @touchstart.stop.prevent="noopTouch" @touchmove.stop.prevent="noopTouch"
              @touchend.stop="noopTouch" @touchcancel.stop="noopTouch">⠿</button>

      <button class="zp-btn" @click="removeCurrentPage" :disabled="totalPages <= 1" title="Odebrat tuto stránku ze skladby">−</button>
      <span class="zp-val">Odebrat str. {{ dispPage(currentPage) }}</span>
      <span class="zp-sep" />
      <!-- Posun číslování (jiné vydání / noty začínající vyšší stránkou).
           Krok o 1 je dost rychlý (držení tlačítka nechci — Janovy PWA
           nesmí mít hover/focus stavy; klik = akce) a hrubý skok se dělá
           zadáním „první stránky“ v dialogu Přejít na stránku. -->
      <button class="zp-btn" @click="bumpOffset(-1)" :disabled="pagesOffset <= 0" title="Posunout číslování o 1 níž">−</button>
      <span class="zp-val" :class="{ dim: pagesOffset === 0 }">posun {{ pagesOffset > 0 ? '+' : '' }}{{ pagesOffset }}</span>
      <button class="zp-btn" @click="bumpOffset(1)" title="Posunout číslování o 1 výš">+</button>
      <span class="zp-sep" />
      <button class="zp-btn" @click="restoreRemovedPages" :disabled="!hiddenPages.length" title="Vrátit odebrané stránky">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>
      </button>
      <span class="zp-val" :class="{ dim: !hiddenPages.length }">odebráno {{ hiddenPages.length }}</span>
      <span class="zp-sep" />
      <button class="zp-btn" @click="pagesListOpen = !pagesListOpen" :class="{ on: pagesListOpen }" title="Seznam odebraných stránek">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
      </button>
    </div>
    <!-- Seznam odebraných stránek — jednotlivé navrácení (vždy jde o stránky
         původního PDF, proto ukazujeme původní číslo, ne pořadí v oříznuté skladbě). -->
    <div v-if="pagesPanelOpen && pagesListOpen" class="pages-list">
      <div class="jp-subtitle">Odebrané stránky</div>
      <div v-if="!hiddenPages.length" class="jp-hint">Žádná stránka není odebraná.</div>
      <div v-for="p in hiddenPages" :key="p" class="jp-item">
        <span class="jp-item-label">Původní str. {{ p + 1 }}</span>
        <button class="jp-btn" @click="restorePage(p)" title="Vrátit tuto stránku">Vrátit</button>
      </div>
    </div>

    <!-- Panel ROTACE — samostatná nabídka s VLASTNÍM tlačítkem v liště.
         Vše, co souvisí s otáčením stránky, je jen tady (dřív to bylo společně
         s zoomem v jednom panelu a gesto pak nevědělo, co má dělat).
         Dokud je otevřený, gesto dvěma prsty dělá POUZE rotaci.
         Referenční mřížka se zobrazuje JEN u rotace, u zoomu ne. -->
    <div v-if="rotPanelOpen" class="zoom-panel rot-panel" data-panel="rot" :style="panelStyle('rot')">
      <button class="panel-grip" title="Tažením přesuň panel, klepnutím zpět na výchozí místo"
              @pointerdown="panelDragStart($event, 'rot')" @pointermove="panelDragMove"
              @pointerup="panelDragEnd" @pointercancel="panelDragEnd"
              @touchstart.stop.prevent="noopTouch" @touchmove.stop.prevent="noopTouch"
              @touchend.stop="noopTouch" @touchcancel.stop="noopTouch">⠿</button>

      <!-- Otočení stránky: hrubé po 90° (na šířku), jemné po 1° a nejjemnější
           po 0,1° (křivý sken). Tlačítka 1° a 0,1° jdou DRŽET — úhel plynule
           nabíhá, takže se dostane i na velký úhel bez mnoha klepání. -->
      <button class="zp-btn" @click="rotateBy(-90)" title="Otočit vlevo o 90°">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>
      </button>
      <button class="zp-btn" @click="rotateClick(-1)" title="Otočit vlevo o 1° (drž pro plynulé otáčení)"
              @pointerdown="rotHoldStart(-1)" @pointerup="rotHoldStop" @pointercancel="rotHoldStop" @pointerleave="rotHoldStop">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
      </button>
      <button class="zp-btn fine" @click="rotateClick(-0.1)" title="Otočit vlevo o 0,1° (drž pro plynulé doladění)"
              @pointerdown="rotHoldStart(-0.1)" @pointerup="rotHoldStop" @pointercancel="rotHoldStop" @pointerleave="rotHoldStop">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
      </button>
      <button class="zp-rot" @click="resetRotation" title="Klepnutím zrušit otočení">{{ rotLabel }}</button>
      <button class="zp-btn fine" @click="rotateClick(0.1)" title="Otočit vpravo o 0,1° (drž pro plynulé doladění)"
              @pointerdown="rotHoldStart(0.1)" @pointerup="rotHoldStop" @pointercancel="rotHoldStop" @pointerleave="rotHoldStop">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
      </button>
      <button class="zp-btn" @click="rotateClick(1)" title="Otočit vpravo o 1° (drž pro plynulé otáčení)"
              @pointerdown="rotHoldStart(1)" @pointerup="rotHoldStop" @pointercancel="rotHoldStop" @pointerleave="rotHoldStop">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
      </button>
      <button class="zp-btn" @click="rotateBy(90)" title="Otočit vpravo o 90°">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/></svg>
      </button>
    </div>

    <!-- Aktivní stránka (vlastní oblast pod lištou — lišta noty nepřekrývá) -->
    <div class="page-area" ref="pageAreaEl">
    <!-- Bílé plátno POD stránkou — VŽDY, pro každou stránku (Jan, Sep 2026:
         „Tohle by měl být výchozí stav u všech stránek. I neupravených.“).
         Dřív svítilo jen u transformovaného papíru a výchozí stav nechával
         tmavý rám, takže neupravená stránka vypadala opticky menší než
         upravená — po zoomu/rotaci se okolí vybílilo a papír „přiskočil“.
         Je to viewport-ový overlay pod lištou, takže kryje celou čtecí plochu
         bez ohledu na to, jak je papír zrovna transformovaný. -->
    <div class="sheet-backdrop" aria-hidden="true" />
    <!-- Pruhy u okrajů = místo, kde se listuje PRSTEM (jen při čtení).
         Vizuální pomůcka, nedrží dotyk — ten dojde až na .viewer.
         Šířku drží --edge-w, aby vizuál odpovídal přesně tomu, kde listování
         opravdu funguje (edgeWidth() v JS). -->
    <div v-if="!jumpPlaceMode && !annotMode" class="edge-hint left" />
    <div v-if="!jumpPlaceMode && !annotMode" class="edge-hint right" />

    <!-- Přepínání stránek v ANOTAČNÍM režimu. Okrajové tap zóny v anotaci
         mizí (jinak by nešlo psát poznámky až do kraje), takže listování
         obstarají dvě samostatná tlačítka — jen v anotaci. -->
    <div v-if="annotMode" class="annot-nav">
      <button class="annot-nav-btn" :disabled="!canPrevPage" @click.stop="prevPage"
              title="Předchozí stránka">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15.5 5L8.5 12l7 7"/></svg>
      </button>
      <button class="annot-nav-btn" :disabled="!canNextPage" @click.stop="nextPage"
              title="Další stránka">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 5l7 7-7 7"/></svg>
      </button>
    </div>
    <!-- .stage = vnější box, jehož rozměry odpovídají tomu, jak stránka zabírá
         na obrazovce PO OTOČENÍ (při 90°/270° prohozené). Nese zoom a posun.
         .rotor uvnitř je přesně velký jako neotočená stránka a otáčí se kolem
         svého středu — díky tomu se canvas, anotační vrstva I tlačítka skoků
         otočí SPOLU a poznámky zůstanou přilepené k notám. -->
    <div class="stage backdrop" :class="{ rotated: rot !== 0 }" :style="stageStyle"
         @pointerleave="onLayerUp" @pointercancel="onLayerUp">
     <div class="rotor" :style="rotorStyle">
      <canvas ref="canvasEl" class="pdf-canvas" />
      <!-- Anotační vrstva nad PDF -->
      <svg
        ref="layerSvgEl"
        class="annot-layer"
        :class="{ active: annotMode || jumpPlaceMode }"
        :width="cssW"
        :height="cssH"
        :viewBox="viewBoxStr"
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
          <!-- Zvýrazňovač: čtyřúhelník postavený vodorovně se čtečkou, uložený
               v souřadnicích vrstvy (poly) — drží se not i při rotaci. -->
          <path
            v-else-if="it.tool === 'highlighter' && it.poly"
            :d="hlPathD(it)"
            :fill="it.color" :opacity="it.opacity != null ? it.opacity : 1"
            class="hl"
          />
          <!-- Starší zvýrazňovače bez poly (uložené před opravou) — obdélník -->
          <rect
            v-else-if="it.tool === 'highlighter'"
            :x="Math.min(it.x1, it.x2)" :y="Math.min(it.y1, it.y2)"
            :width="Math.abs(it.x2 - it.x1)" :height="Math.abs(it.y2 - it.y1)"
            :fill="it.color" :opacity="it.opacity != null ? it.opacity : 1"
            class="hl"
          />
          <!-- Textová anotace — volitelně v hranatém rámečku (Jan, Oct 2026).
               Rámeček se počítá ze STEJNÉ geometrie jako výběr rukou a hit-test
               (textBorderBox), aby rám seděl na text a prvek šel chytit uvnitř něj. -->
          <g v-else-if="isText(it)">
            <rect
              v-for="r in (it.border ? textBorderRects(it) : [])" :key="r.key"
              :x="r.x" :y="r.y" :width="r.width" :height="r.height"
              :stroke-dasharray="r.dash || undefined"
              class="text-border"
              fill="none" :stroke="it.color" stroke-width="1.5"
              :opacity="it.opacity != null ? it.opacity : 1"
            />
            <text
              :x="it.x" :y="it.y"
              :fill="it.color"
              :font-size="it.size"
              font-family="system-ui, sans-serif"
              :opacity="it.opacity != null ? it.opacity : 1"
              text-anchor="start"
            >{{ it.text }}</text>
          </g>
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
          <!-- Značky pro výšky not (posuvky, ozdoby, artikulace) a VLOŽENÉ NOTY —
               stejný princip jako dynamika: klepnutím na dlaždici se glyf položí na
               noty. Nota se kreslí týmž prvkem i ukotvením (střed = místo klepnutí). -->
          <text
            v-else-if="it.tool === 'mark' || it.tool === 'note'"
            :x="it.x" :y="it.y"
            :transform="noteFlipTransform(it)"
            :fill="it.color"
            :stroke="it.tool === 'note' ? it.color : 'none'"
            :stroke-width="noteStroke(it)"
            paint-order="stroke"
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
          <!-- Dynamika / značka: náhled budoucího glyfu (text zatím prázdný → tečka), ať uživatel vidí, co dostane -->
          <text
            v-else-if="isNotationText(activeItem) && activeItem.text"
            :x="activeItem.x" :y="activeItem.y"
            :transform="noteFlipTransform(activeItem)"
            :fill="activeItem.color"
            :font-size="activeItem.size"
            font-family="'NotyDyn', serif"
            :opacity="activeItem.opacity != null ? activeItem.opacity : 1"
            text-anchor="middle"
          >{{ annotDisplayText(activeItem) }}</text>
          <!-- Text: náhled rámečku už při umísťování — uživatel vidí čtverec
               ještě předtím, než napíše text (jinak by „border“ objevil až po uložení). -->
          <g v-else-if="activeItem.tool === 'text'">
            <rect
              v-for="r in (activeItem.border ? textBorderRects(activeItem) : [])" :key="r.key"
              :x="r.x" :y="r.y" :width="r.width" :height="r.height"
              :stroke-dasharray="r.dash || undefined"
              class="text-border"
              fill="none" :stroke="activeItem.color" stroke-width="1.5"
              :opacity="activeItem.opacity != null ? activeItem.opacity : 1"
            />
            <circle :cx="activeItem.x" :cy="activeItem.y" r="6"
              fill="none" :stroke="activeItem.color" stroke-width="2" />
          </g>
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
          <path
            v-if="hlPoints.length >= 2"
            :d="hlPreviewD"
            :fill="annotColor" opacity="0.3" :stroke="annotColor" stroke-width="1.5" stroke-dasharray="4 3"
            class="hl-preview"
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
        <!-- Aktuální anotační prvky — pro SKUTEČNÉ měření textu v prohlížeči.
             Je to potřeba proto, že rámeček kolem textu se musí trefit přesně:
             odhad šířky znaku a výšky písma se od skutečného vykreslení liší
             (Jan: „text teď není v rámečku vycentrovaný“). Změřeno u systému:
             skutečná výška písma 12 px vs odhad 12,24 px a skutečná šířka znaku
             0,553 em vs odhad 0,62 em → odchylka ~3,8 px. Měření je proto zdroj
             pravdy a odhad slouží jen jako záloha (první vykreslení po startu).
             `aria-hidden` + neviditelný styl, aby to nerušilo čtečku obrazovky. -->
        <text
          v-for="(it, i) in measurableTexts" :key="'m' + (it.id || i)"
          :id="it.id"
          ref="textProbeEls" class="text-measure" aria-hidden="true"
          x="0" y="0" text-anchor="start" fill="none"
          :font-size="it.size || 20" font-family="system-ui, sans-serif"
        >{{ it.text }}</text>
      </svg>

      <!-- Skoky (Da Capo / VIDE) umístěné PŘÍMO NA NOTÁCH.
           Uvnitř .stage → posouvají se a zoomují spolu s notami, takže tlačítko
           drží na místě, kam ho uživatel naklepal (třemi body). Souřadnice
           place {x,y,w,h} jsou ve stejné soustavě jako anotační vrstva. -->
      <!-- NÁHLED umístění: hned po naklepání tří bodů je vidět, kde a jak velké
           tlačítko bude. Dřív se ukázalo až po uložení skoku — uživatel tedy
           po "Umístění: hotovo" neviděl nic a nevěděl, co se stalo. -->
      <div v-if="jumpPlace" class="jump-on-page" :class="{ 'edit-mode': annotMode && tool === 'edit' }">
        <div class="jump-on-btn preview" :style="jumpBoxStyle({ place: jumpPlace })">
          {{ (jumpLabel || '').trim() || 'Skok' }}
        </div>
      </div>
      <div v-if="placerJumps.length" class="jump-on-page" :class="{ 'edit-mode': annotMode && tool === 'edit' }">
        <button
          v-for="j in placerJumps"
          :key="j.id"
          class="jump-on-btn"
          :style="jumpBoxStyle(j)"
          @click="goJump(j)"
          :title="'Skok na str. ' + withOffset(dispPage(j.toPage))"
        >{{ j.label }}</button>
      </div>
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
          <span class="pg-total">/ {{ withOffset(totalPages) }}</span>
          <button class="pg-btn primary" @click="goToTypedPage">Přejít</button>
          <button class="pg-btn" @click="closePageGo">Zavřít</button>
        </div>
        <!-- Posun číslování: noty často začínají až 7. stranou nebo jsou proti
             jinému vydání posunuté. Tady se jen řekne, jaké číslo má první
             stránka PDF — číslování se srovná, noty se nemění. -->
        <div class="pg-offset">
          <span class="pg-offset-label">První stránka má číslo</span>
          <input
            v-model="firstPageValue"
            class="pg-offset-input"
            type="text"
            inputmode="numeric"
            pattern="-?[0-9]*"
            placeholder="např. 7"
            @keydown.enter="applyFirstPage"
          />
          <button class="pg-btn" @click="applyFirstPage">Nastavit</button>
        </div>
        <div class="pg-hint">
          Číslování je posunuté o {{ pagesOffset > 0 ? '+' : '' }}{{ pagesOffset }}
          (1. stránka PDF = {{ 1 + pagesOffset }}.).
        </div>
        <!-- SKOKY V ČÍSLOVÁNÍ — noty, kde jsou vynechané stránky sólistů, mají
             v číslech díry. Na libovolné stránce se prostě řekne, jaké číslo
             na papíře MÁ, a od té stránky dál se počítadlo posune. Skok drží,
             dokud se nezruší, a ukládá se na skladbu (putuje do zálohy). -->
        <div class="pg-offset">
          <span class="pg-offset-label">Tato stránka má číslo</span>
          <input
            v-model="thisPageValue"
            class="pg-offset-input"
            type="text"
            inputmode="numeric"
            pattern="[0-9]*"
            placeholder="např. 9"
            @keydown.enter="applyNumberHere"
          />
          <button class="pg-btn" @click="applyNumberHere">Nastavit odsud</button>
        </div>
        <div v-if="numberJumpsSorted.length" class="pg-jumps">
          <div class="jp-subtitle">Skoky v číslování</div>
          <div v-for="j in numberJumpsSorted" :key="j.page" class="jp-item">
            <span class="jp-item-label">od str. {{ withOffset(jumpSlot(j)) }} dál</span>
            <span class="jp-item-pages">skok {{ j.delta > 0 ? '+' : '' }}{{ j.delta }}</span>
            <button class="jp-btn" @click="removeNumberJump(j.page)" title="Zrušit tento skok">Zrušit</button>
          </div>
        </div>
        <div v-if="hiddenPages.length" class="pg-hint">Stránky {{ hiddenLabel }} jsou odebrané — čísluje se {{ withOffset(totalPages) }} zobrazenými z {{ withOffset(rawPageCount) }} původních.</div>
      </div>
    </div>

    <!-- Loading overlay při prvním načtení / přechodu mezi skladbami -->
    <div v-if="loading" class="viewer-loading">
      <div class="spinner" />
      <div class="loading-text">Načítám noty…</div>
    </div>

    <!-- Hláška o uložení výchozího zobrazení. Tlačítko se sice vybarví, ale to
         znamená jen „pro tuhle stránku/skladbu je něco uložené" — po dalším
         stisknutí z vybarvení nepoznáš, že se uložil NOVÝ stav. Proto se po
         každém skutečném zápisu do DB ukáže tahle krátká zpráva. -->
    <div v-if="toast" class="viewer-toast">{{ toast }}</div>

    <!-- Referenční mřížka pro srovnání horizontální rovnosti not. Patří VÝHRADNĚ
         k rotaci (Jan: „Mřížka pro porovnání horizontální rovnosti se zobrazí jen
         u rotace. U zoomu ne.") — u zoomu a posunu by jen překážela. -->
    <div v-if="rotPanelOpen" class="rot-grid" aria-hidden="true" />

    <div v-if="edgeJumps.length" class="jump-strip">
      <button v-for="j in edgeJumps" :key="j.id" class="jump-btn" @click="goJump(j)" :title="'Skok na str. ' + withOffset(dispPage(j.toPage))">{{ j.label }}</button>
    </div>

    <!-- Nápověda při umisťování — malá lišta, aby nezakrývala noty, na které se klepá -->
    <div v-if="jumpPlaceMode" class="jp-place-hint">
      <span>{{ jumpPlaceHint }}</span>
      <span class="jp-place-count">{{ jumpPlacePoints.length }}/3 · str. {{ withOffset(dispPage(currentPage)) }}</span>
    </div>

    <!-- Panel pro vytváření skoku (při umisťování se schová — jinak zakrývá noty) -->
    <div v-if="jumpMode && !jumpPlaceMode" class="jump-panel" data-panel="jump" :style="panelStyle('jump')">
      <button class="panel-grip" title="Tažením přesuň panel, klepnutím zpět na výchozí místo"
              @pointerdown="panelDragStart($event, 'jump')" @pointermove="panelDragMove"
              @pointerup="panelDragEnd" @pointercancel="panelDragEnd"
              @touchstart.stop.prevent="noopTouch" @touchmove.stop.prevent="noopTouch"
              @touchend.stop="noopTouch" @touchcancel.stop="noopTouch">⠿</button>

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
        <span class="jp-item-pages">Str. {{ withOffset(dispPage(currentPage)) }}</span>
        <button class="jp-btn primary" @click="saveJump" :disabled="jumpStart === null || jumpEnd === null">Uložit skok</button>
      </div>
      <div v-if="jumps.length" class="jp-list">
        <div class="jp-subtitle">Existující skoky</div>
        <div v-for="j in jumps" :key="j.id" class="jp-item">
          <span class="jp-item-label">{{ j.label }}</span>
          <span class="jp-item-pages">str. {{ withOffset(dispPage(j.fromPage)) }} → {{ withOffset(dispPage(j.toPage)) }}</span>
          <button class="jp-del" @click="deleteJump(j)" title="Smazat skok">🗑</button>
        </div>
      </div>
      <button class="jp-close" @click="toggleJumpMode">Zavřít</button>
    </div>

    <!-- Panel pro vytváření záložky. ÚPRAVA existující záložky se děje PŘÍMO
         na jejím řádku v seznamu níže (Jan, Oct 2026): plnit při úpravě pole
         „Nová záložka“ nahoře bylo zavádějící — nebylo jasné, kterou záložku
         uživatel vlastně mění. Horní pole slouží VÝHRADNĚ k vytvoření nové. -->
    <div v-if="bookmarkMode" class="jump-panel" data-panel="bookmark" :style="panelStyle('bookmark')">
      <button class="panel-grip" title="Tažením přesuň panel, klepnutím zpět na výchozí místo"
              @pointerdown="panelDragStart($event, 'bookmark')" @pointermove="panelDragMove"
              @pointerup="panelDragEnd" @pointercancel="panelDragEnd"
              @touchstart.stop.prevent="noopTouch" @touchmove.stop.prevent="noopTouch"
              @touchend.stop="noopTouch" @touchcancel.stop="noopTouch">⠿</button>

      <div class="jp-title">Nová záložka</div>
      <div class="jp-row">
        <span class="jp-cur">Stránka {{ withOffset(dispPage(currentPage)) }}</span>
      </div>
      <div class="jp-row">
        <input v-model="bookmarkLabel" class="jp-input" placeholder="Text záložky (např. Coda)" />
        <button class="jp-btn primary" @click="saveBookmark">Přidat</button>
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

          <!-- Režim úpravy: název se mění PŘÍMO tady na řádku (Jan, Oct 2026).
               Enter/Blur uloží, Escape zavře bez uložení. -->
          <template v-if="bookmarkEditingId === b.id">
            <span class="jp-item-label dim">str. {{ withOffset(dispPage(b.page)) }}</span>
            <input
              :ref="setBmEditInput"
              v-model="bmEditLabel"
              class="jp-input jp-input-edit"
              placeholder="Text záložky"
              @keyup.enter="commitBookmarkEdit"
              @keyup.esc="cancelBookmarkEdit"
              @blur="commitBookmarkEdit"
              @touchstart.stop
              @touchmove.stop
              @touchend.stop
            />
            <span class="jp-actions">
              <!-- mousedown.prevent: tlačítko si nesmí vzít fokus, jinak by
                   input vyhodil blur a uložil rozepsaný text dřív, než se
                   stihne vyhodnotit klik (✓ uloží, ✕ zahodí). -->
              <button class="jp-icon" @mousedown.prevent @click="commitBookmarkEdit" title="Uložit">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
              </button>
              <button class="jp-icon del" @mousedown.prevent @click="cancelBookmarkEdit" title="Zrušit">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg>
              </button>
            </span>
          </template>
          <template v-else>
            <span class="jp-item-label" :class="{ dim: !b.label }">str. {{ withOffset(dispPage(b.page)) }}<template v-if="b.label"> · {{ b.label }}</template></span>
            <span class="jp-actions">
              <button class="jp-icon" @click="startBookmarkEdit(b)" title="Přejmenovat">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.8 2.8 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></svg>
              </button>
              <button class="jp-icon del" @click="deleteBookmark(b)" title="Smazat">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
              </button>
            </span>
          </template>
        </div>
      </div>

      <button class="jp-close" @click="closeBookmarkPanel">Zavřít</button>
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
        :title="'Záložka na str. ' + bookmarkPageNo(b)"
      >
        <span class="bk-num">{{ bookmarkPageNo(b) }}</span>
        <span v-if="b.label" class="bk-label">{{ b.label }}</span>
      </button>
    </div>

    <!-- Slider stránek s miniaturami.
         POZOR: pás se vykresluje VIRTUÁLNĚ — v DOM jsou jen prvky okolo
         aktuální stránky (viz visibleThumbs). Dřív tu byl prvek pro KAŽDOU
         stránku a `thumbs` (reaktivní Mapa) se četla přes thumbs.get(i-1)
         v každém z nich, takže každá dorazivší miniatura přerenderovala celý
         pás stovek prvků → při rychlém tažení sliderem se appka zhroutila. -->
    <div v-if="sliderOpen" class="slider-panel">
      <div class="thumb-strip" ref="thumbStripEl">
        <div class="thumb-spacer" :style="{ width: thumbPadLeft + 'px' }" aria-hidden="true" />
        <button
          v-for="i in visibleThumbs"
          :key="i.slot"
          class="thumb-item"
          :class="{ on: i.slot === pageSlider }"
          :data-idx="i.slot"
          @click="gotoPage(i.idx)"
          :title="'Stránka ' + withOffset(i.slot + 1)"
        >
          <img v-if="i.src" :src="i.src" :alt="'Stránka ' + withOffset(i.slot + 1)" />
          <div v-else class="thumb-loading">…</div>
          <span class="thumb-num">{{ withOffset(i.slot + 1) }}</span>
          <!-- Odebrání stránky přímo z pásu miniatur (Jan chce odebrat
               KONKRÉTNÍ stránky, ne jen tu, na které právě stojí). -->
          <button class="thumb-x" @click.stop="removePage(i.idx)" title="Odebrat tuto stránku">✕</button>
        </button>
        <div class="thumb-spacer" :style="{ width: thumbPadRight + 'px' }" aria-hidden="true" />
      </div>
      <input
        type="range"
        class="slider"
        min="0"
        :max="Math.max(0, totalPages - 1)"
        step="1"
        :value="pageSlider"
        @input="onSliderInput($event)"
      />
    </div>

    <!-- Plovoucí panel anotací (v anotačním režimu; při umisťování skoku schovaný,
         aby nezakrýval noty, na které se klepá) -->
    <div v-if="annotMode && !jumpPlaceMode" class="annot-panel" data-panel="annot" :style="panelStyle('annot')">
      <!-- Hlavička: sbalit/rozbalit -->
      <div class="ap-header">
        <span class="ap-title">Anotace</span>
        <button class="panel-grip" title="Tažením přesuň panel, klepnutím zpět na výchozí místo"
                @pointerdown="panelDragStart($event, 'annot')" @pointermove="panelDragMove"
                @pointerup="panelDragEnd" @pointercancel="panelDragEnd"
                @touchstart.stop.prevent="noopTouch" @touchmove.stop.prevent="noopTouch"
                @touchend.stop="noopTouch" @touchcancel.stop="noopTouch">⠿</button>

        <button class="ap-collapse" @click="annotCollapsed = !annotCollapsed" :title="annotCollapsed ? 'Rozbalit' : 'Sbalit'">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path v-if="!annotCollapsed" d="M6 9l6 6 6-6"/><path v-else d="M6 15l6-6 6 6"/></svg>
        </button>
      </div>

      <template v-if="!annotCollapsed">
      <!-- Kategorie: Nástroje -->
      <div class="ap-cat">
        <div class="ap-cat-label">Nástroje</div>
        <div class="ap-row">
          <button class="ap-tool" @click="setTool('pencil')" :class="{ on: tool === 'pencil' }" title="Tužka"><span class="ap-glyph emoji">✏️</span></button>
          <button class="ap-tool" @click="setTool('highlighter')" :class="{ on: tool === 'highlighter' }" title="Zvýraznění"><span class="ap-glyph emoji">🖍️</span></button>
          <button class="ap-tool" @click="setTool('eraser')" :class="{ on: tool === 'eraser' }" title="Guma (maže anotace, přes které přejede)"><span class="ap-glyph emoji">🧽</span></button>
          <button class="ap-tool" @click="setTool('text')" :class="{ on: tool === 'text' }" title="Text (klávesnice)"><span class="ap-glyph t-glyph">T</span></button>
          <button class="ap-tool" @click="setTool('edit')" :class="{ on: tool === 'edit' }" title="Upravit / přesunout text či dynamiku"><span class="ap-glyph emoji">✋</span></button>
        </div>
      </div>

      <!-- Kategorie: Hudební značky -->
      <div class="ap-cat">
        <div class="ap-cat-label">Značky</div>
        <div class="ap-row">
          <button class="ap-tool mus" @click="setTool('crescendo')" :class="{ on: tool === 'crescendo' }" title="Crescendo (3 body)"><span class="ap-glyph">&lt;</span></button>
          <button class="ap-tool mus" @click="setTool('decrescendo')" :class="{ on: tool === 'decrescendo' }" title="Decrescendo (3 body)"><span class="ap-glyph">&gt;</span></button>
          <button class="ap-tool" @click="setTool('dynamic')" :class="{ on: tool === 'dynamic' }" title="Dynamika (p, f, mf, sfz...)">
            <span class="dyn-ico">{{ dynGlyph('mf').text }}</span>
          </button>
          <button class="ap-tool" @click="setTool('mark')" :class="{ on: tool === 'mark' }" title="Značky pro výšky not (béčko, odrážka, křížek, ozdoby...)">
            <span class="dyn-ico">{{ markGlyph('k').text }}</span>
          </button>
          <button class="ap-tool" @click="setTool('note')" :class="{ on: tool === 'note' }" title="Vkládání not (celá, půlová, čtvrťová, osminová, šestnáctinová a pomlky)">
            <span class="dyn-ico nota-ico">{{ noteGlyph('ctvrt_h').text }}</span>
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
          <button class="ap-tool pen-only" @click="penOnly = !penOnly" :class="{ on: penOnly }" title="Kreslit jen perem (ignorovat dotyk rukou)"><span class="ap-glyph emoji">🖊️</span></button>
          <span class="ap-pen-label" @click="penOnly = !penOnly">Jen pero</span>
        </div>
      </div>
      </template>
    </div>

    <!-- Pásmo úprav vybrané textové/dynamické anotace (jen v nástroji Ruka).
         POJISTKA: lišta se objevuje až PO vybrání prvku, tedy pod prstem, kterým
         uživatel vybíral — kompatibilitní `click` z téhož dotyku by jinak spadl
         na tlačítko, které se tam právě vykreslilo (nejčastěji 🗑 = „hned se to
         smaže“). Lišta proto přijme jen klepnutí, jemuž předcházelo POLOŽENÍ
         uvnitř ní. -->
    <div v-if="annotMode && tool === 'edit' && editingId" class="edit-bar"
         @pointerdown.capture="editBarArmed = true"
         @click.capture="onEditBarClickCapture">
      <!-- DVA ŘÁDKY, které se samy zalamují (Jan, Oct 2026: „nabídka možností je
           tak široká, že tlačítko ‚smazat‘ s ikonou koše utíká mimo lištu“).
           Naměřeno na tabletu 800 px: obsah 903 px do 764 px, koš na x=887..921
           (mimo displej i mimo lištu). Proto: hlavní řádek drží VŽDY viditelné
           ovládání prvku (přepsat, velikost, hotovo, smazat) a řádek rámečku
           s čipy se vejde pod něj. Koš tak zůstává uvnitř displeje. -->
      <div class="eb-row">
        <span class="eb-type">{{ editingTypeLabel }}</span>
        <button class="eb-btn" @click="editText(editingAnnot)" title="Přepsat text">✏️</button>
        <span class="eb-size">Velikost</span>
        <button class="eb-btn" @click="resizeAnnot(editingAnnot, -1)" title="Zmenšit">−</button>
        <span class="eb-val">{{ editingAnnot ? Math.round(editingAnnot.size) : 0 }}</span>
        <button class="eb-btn" @click="resizeAnnot(editingAnnot, 1)" title="Zvětšit">+</button>
        <!-- Rámeček se dá zapnout/vypnout i u UŽ VLOŽENÉHO textu — jinak by uživatel
             musel text smazat a vložit znovu, když si to rozmyslí. Volba se propíše
             i do „další text“ (stejně jako velikost zůstává nastavená).
             Tlačítko zůstává v HLAVNÍM řádku, protože musí být po ruce i tehdy,
             když je rámeček VYPNUTÝ (jinak by nešel zapnout). -->
        <button v-if="editingAnnot && editingAnnot.tool === 'text'"
                class="eb-btn" :class="{ on: editingAnnot.border }"
                @click="toggleTextBorder(editingAnnot)"
                :title="editingAnnot.border ? 'Zrušit rámeček' : 'Hranatý rámeček kolem textu'">▢</button>
        <button class="eb-btn done" @click="endEdit" title="Hotovo">✓</button>
        <button class="eb-btn" @click="deleteEditing" title="Smazat">🗑</button>
      </div>
      <!-- Šířka a styl rámu u VLOŽENÉHO textu — jinak by šly měnit jen při vkládání
           a uživatel by musel text smazat a napsat znovu, když si to rozmyslí.
           Vlastní řádek = čipy neodsouvají koš z lišty. -->
      <!-- Zrcadlení UŽ VLOŽENÉ noty — jinak by šlo měnit jen při vkládání a nota by
           se musela smazat a vložit znovu. Vlastní řádek = čipy neodsouvají koš. -->
      <div v-if="editingAnnot && editingAnnot.tool === 'note'"
           class="eb-row eb-row-frame">
        <span class="eb-size">Zrcadlení</span>
        <button class="eb-chip" :class="{ on: !!editingAnnot.flipX }"
                @click="toggleNoteFlip(editingAnnot, 'x')"
                title="Vodorovně — nožička i praporek na druhou stranu">Vodorovně</button>
        <button class="eb-chip" :class="{ on: !!editingAnnot.flipY }"
                @click="toggleNoteFlip(editingAnnot, 'y')"
                title="Svisle — nožička nahoru/dolů">Svisle</button>
      </div>
      <div v-if="editingAnnot && editingAnnot.tool === 'text' && editingAnnot.border"
           class="eb-row eb-row-frame">
        <span class="eb-size">Rám</span>
        <button
          v-for="w in TEXT_BORDER_WIDTHS" :key="'w' + w"
          class="eb-chip" :class="{ on: (editingAnnot.borderWidth || 6) === w }"
          @click="setTextBorderWidth(editingAnnot, w)"
          :title="'Odstup textu od rámečku'">{{ w }}</button>
        <button
          v-for="s in TEXT_BORDER_STYLES" :key="'s' + s.key"
          class="eb-chip" :class="{ on: (editingAnnot.borderStyle || 'solid') === s.key }"
          @click="setTextBorderStyle(editingAnnot, s.key)"
          :title="s.label">{{ s.label }}</button>
      </div>
    </div>

    <!-- Vstup pro text / dynamiku -->
    <!-- POJISTKA PROTI ZBLOUDILÉ UDÁLOSTI: dialog se otevírá až po ZVEDNUTÍ pera,
         kterým uživatel dynamiku umístil. Tentýž dotyk ale prohlížeč vyřídí ještě
         jako kompatibilitní `click` a ten spadne DO tohoto dialogu — vybere dlaždici
         pod místem položení pera („vloží se jiná dynamika, pokaždé jiná") nebo trefí
         Zrušit („okno se ani neotevře"). Dialog proto přijme jen klepnutí, kterému
         předcházelo POLOŽENÍ prstu/pera UVNITŘ dialogu. -->
    <div v-if="editingAnnotationId" class="text-input-overlay"
         @pointerdown.capture="dialogArmed = true"
         @click.capture="onDialogClickCapture">
      <div class="text-input-card">
        <span class="ti-label">{{ editingAnnotTool === 'dynamic' ? 'Dynamika' : editingAnnotTool === 'mark' ? 'Značka' : editingAnnotTool === 'note' ? 'Nota' : 'Text' }}</span>

        <!-- Rychlý výběr: klepni na dynamiku, vyplní se do pole (a rovnou se uloží) -->
        <div v-if="editingAnnotTool === 'dynamic'" class="dyn-grid">
          <button
            v-for="d in DYN_PICK"
            :key="d.key"
            class="dyn-btn"
            :class="{ on: dynKey(annotTextDraft) === d.key }"
            @pointerdown.prevent="pickDyn(d.key)"
            :title="d.key"
          >{{ d.glyph }}</button>
        </div>

        <!-- Značky pro výšky not — dlaždice rozdělené do sekcí (posuvky / ozdoby / drobnosti).
             Stejná dlaždice, stejná past: reaguje na POLOŽENÍ, ne na `click`. -->
        <template v-if="editingAnnotTool === 'mark'">
          <div v-for="g in MARK_GROUPS" :key="g.label" class="mark-sec">
            <div class="mark-sec-label">{{ g.label }}</div>
            <div class="dyn-grid">
              <button
                v-for="m in g.items"
                :key="m.key"
                class="dyn-btn"
                :class="{ on: annotTextDraft.trim().toLowerCase() === m.key }"
                @pointerdown.prevent="pickMark(m.key)"
                :title="m.label"
              >{{ markGlyph(m.key).text }}</button>
            </div>
          </div>
        </template>

        <!-- Vkládání not — dlaždice rozdělené do sekcí (noty / pomlky). Stejná
             dlaždice i stejná past: reaguje na POLOŽENÍ, ne na `click`. -->
        <template v-if="editingAnnotTool === 'note'">
          <div v-for="g in NOTE_GROUPS" :key="g.label" class="mark-sec">
            <div class="mark-sec-label">{{ g.label }}</div>
            <div class="dyn-grid">
              <button
                v-for="n in g.items.filter(x => !x.hide)"
                :key="n.key"
                class="dyn-btn"
                :class="{ on: annotTextDraft.trim().toLowerCase() === n.key }"
                @pointerdown.prevent="pickNote(n.key)"
                :title="n.label"
              ><span class="nota-glyf"
                 :style="{ transform: 'translateY(' + noteTileNudge(n.key, noteFlipY) + 'px)' }"
              >{{ noteGlyphFor(n.key, noteFlipY).text }}</span></button>
            </div>
          </div>
        </template>

        <input
          v-model="annotTextDraft"
          class="ti-input"
          :placeholder="editingAnnotTool === 'dynamic' ? 'nebo napiš vlastní (např. mf)' : editingAnnotTool === 'mark' ? 'vyber značku z nabídky výše' : editingAnnotTool === 'note' ? 'vyber notu z nabídky výše' : 'Text poznámky'"
          @keydown.enter="confirmTextAnnot"
        />

        <!-- Velikost textu JEŠTĚ PŘED vložením. Dřív se dala upravit až po vložení
             (nástrojem Ruka), takže uživatel musel vkládat „naslepo“ a pak
             dohánět velikost. Volba se pamatuje i pro příští vložení a náhled
             „Aa“ ukazuje skutečnou velikost, jakou text dostane. -->
        <!-- Velikost noty se volí TADY, ještě před vložením — nota musí sedět na
             velikost osnovy v notách a ta je u každé skladby jiná. Náhled ukazuje
             skutečný glyf v této velikosti (co uživatel dostane). -->
        <div v-if="editingAnnotTool === 'note'" class="ti-size-row">
          <span class="ti-size-label">Velikost</span>
          <button class="ti-size-btn" @click="bumpNoteSize(-1)" title="Menší nota">−</button>
          <span class="ti-size-val">{{ noteSizeDraft }}</span>
          <button class="ti-size-btn" @click="bumpNoteSize(1)" title="Větší nota">+</button>
          <span class="ti-size-sample">
            <span class="ti-size-aa nota-nahled" :style="notePreviewStyle">{{ noteGlyphFor(annotTextDraft.trim() || 'ctvrt_h', noteFlipY).text }}</span>
          </span>
        </div>

        <!-- Zrcadlení noty PŘED vložením — vodorovně (nožička i praporek na druhou
             stranu) i svisle (nožička nahoru/dolů). Zrcadlí se KOLEM UKOTVENÍ, takže
             hlavička zůstane přesně v místě klepnutí. Volba se NEPAMATUJE: zrcadlení
             je vlastnost jedné noty, ne skladby (velikost naopak ano). -->
        <div v-if="editingAnnotTool === 'note'" class="ti-row">
          <span class="ti-size-label">Zrcadlení</span>
          <button class="ti-toggle" :class="{ on: noteFlipX }" @click="toggleFlip('x')"
                  title="Vodorovně — nožička i praporek na druhou stranu">Vodorovně</button>
          <button class="ti-toggle" :class="{ on: noteFlipY }" @click="toggleFlip('y')"
                  title="Svisle — nožička nahoru/dolů">Svisle</button>
        </div>

        <div v-if="editingAnnotTool === 'text'" class="ti-size-row">
          <span class="ti-size-label">Velikost</span>
          <button class="ti-size-btn" @click="bumpTextSize(-1)" title="Menší text">−</button>
          <span class="ti-size-val">{{ textSizeDraft }}</span>
          <button class="ti-size-btn" @click="bumpTextSize(1)" title="Větší text">+</button>
          <!-- Náhled: když je zapnutý rámeček, ukáže se i s ním — ve STEJNÉM
               tvaru, v jakém se text opravdu vloží (čtverec, stejná barva).
               Když rámeček zapnutý není, náhled patří k přepínači níž. -->
          <span v-if="!textBorderDraft" class="ti-size-sample">
            <span class="ti-size-aa" :style="textPreviewStyle">{{ annotTextDraft || 'Aa' }}</span>
          </span>
        </div>

        <!-- Barva textu a rámeček PŘÍMO V TOMTO OKNĚ (Jan, Oct 2026): uživatel
             vybírá velikost i způsob vložení tady, takže barva nemá být jinde.
             Stejná paleta jako pero; volba se pamatuje (stejně jako velikost). -->
        <div v-if="editingAnnotTool === 'text'" class="ti-row">
          <span class="ti-size-label">Barva</span>
          <div class="ti-colors">
            <button
              v-for="c in PEN_COLORS" :key="c"
              class="ti-color" :class="{ on: textColorDraft === c }"
              :style="{ background: c }"
              @click="textColorDraft = c"
              :title="'Barva textu'"
            ></button>
          </div>
        </div>
        <!-- Velikost a styl rámečku (Jan, Oct 2026): „velikost a styl rámečku by
             měl být taky na výběr“. Velikost = odstup textu od rámu (Šířka),
             styl = plná / čárkovaná / tečkovaná / dvojitá. Vlastní rámeček se
             přitom zvětšuje sám podle textu, takže „velikost“ je jen odstup —
             jinak by delší text přetekl ven. -->
        <div v-if="editingAnnotTool === 'text'" class="ti-row">
          <span class="ti-size-label">Rámeček</span>
          <button class="ti-toggle" :class="{ on: textBorderDraft }"
                  @click="textBorderDraft = !textBorderDraft"
                  title="Hranatý rámeček kolem textu — stejnou barvou, do čtverce">
            {{ textBorderDraft ? 'Zapnutý' : 'Vypnutý' }}
          </button>
          <!-- Náhled rámečku i tady: tvar a styl musí být vidět dřív, než text vložíš. -->
          <span class="ti-size-sample">
            <span class="ti-size-aa" :style="textPreviewStyle">{{ annotTextDraft || 'Aa' }}</span>
          </span>
        </div>
        <template v-if="editingAnnotTool === 'text' && textBorderDraft">
          <div class="ti-row">
            <span class="ti-size-label">Šířka</span>
            <button
              v-for="w in TEXT_BORDER_WIDTHS" :key="w"
              class="ti-chip" :class="{ on: textBorderWidthDraft === w }"
              @click="textBorderWidthDraft = w"
              :title="'Odstup textu od rámečku'">{{ w }}</button>
          </div>
          <div class="ti-row">
            <span class="ti-size-label">Styl</span>
            <button
              v-for="s in TEXT_BORDER_STYLES" :key="s.key"
              class="ti-chip" :class="{ on: textBorderStyleDraft === s.key }"
              @click="textBorderStyleDraft = s.key"
              :title="s.label">{{ s.label }}</button>
          </div>
        </template>
        <!-- Neznámý výraz: font pro něj nemá glyf → zobrazil by se rozbitý znak -->
        <span v-if="editingAnnotTool === 'dynamic' && annotTextDraft.trim() && !dynGlyph(annotTextDraft).known" class="ti-warn">
          Tuhle dynamiku font nezná — vyber ji z nabídky výše.
        </span>
        <span v-if="editingAnnotTool === 'mark' && annotTextDraft.trim() && !markGlyph(annotTextDraft).known" class="ti-warn">
          Tuhle značku font nezná — vyber ji z nabídky výše.
        </span>
        <span v-else-if="editingAnnotTool === 'mark' && markLabel(annotTextDraft)" class="ti-note">
          {{ markLabel(annotTextDraft) }}
        </span>
        <span v-if="editingAnnotTool === 'note' && annotTextDraft.trim() && !noteGlyph(annotTextDraft).known" class="ti-warn">
          Tuhle notu font nezná — vyber ji z nabídky výše.
        </span>
        <span v-else-if="editingAnnotTool === 'note' && noteLabel(annotTextDraft)" class="ti-note">
          {{ noteLabel(annotTextDraft) }}
        </span>

        <div class="ti-actions">
          <button class="jp-btn" @click="cancelTextAnnot">Zrušit</button>
          <button class="jp-btn primary" @click="confirmTextAnnot(false)">Uložit</button>
          <!-- Uloží a ROVNOU přepne na ruku nad vloženým prvkem — uživatel s ním
               může hned hýbat (přesun, velikost), nemusí přepínat nástroj.
               U dialogu otevřeného RUKOU (přepis existujícího textu) tohle
               tlačítko nedává smysl — v ruce už jsme. -->
          <button v-if="editingTextSize === null" class="jp-btn hand"
                  @click="confirmTextAnnot(true)"
                  title="Uložit a přepnout na ruku (hned lze přesouvat a měnit velikost)">Uložit a ruka ✋</button>
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
import { dbGetSong, dbSaveSong, dbSaveAnnotations, dbGetAnnotations, dbGetGroup, dbGetAllSongs, dbGetJumps, dbSaveJumps, dbGetBookmarks, dbSaveBookmarks, dbGetSongView, dbSaveSongView, dbDeleteSongView, dbSavePageView, dbGetPageView, dbGetAllPageViews, dbDeletePageView, dbDeleteAllPageViews } from '../db.js';
import { renderPage, renderPageRegion, getPageWidthHeight, getPageCount } from '../pdf.js';
import { analyzeContent } from '../contentBounds.js';

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
const currentPage = ref(0); // 0-based, INDEX DO PDF (viz hiddenPages — číslování se může lišit)
const loading = ref(true);  // loading overlay při prvním načtení / přechodu mezi skladbami
const zoom = ref(1.0);     // výchozí zoom 100 % (1 = fit šířce)
const rot = ref(0);        // otočení stránky ve stupních (libovolný úhel, kladné = vpravo)
// Uložené výchozí zobrazení SKLADBY (globální): { zoom, panX, panY, rot }
// null = nic uloženo → fit 100 %, bez posunu, bez rotace
const songView = ref(null);
const songZoom = ref(1.0); // odvozeně: uložený výchozí zoom skladby (fallback 1.0)
// True, když má aktuální skladba nastavený (uložený) výchozí pohled
const hasSavedZoom = ref(false);
// Uložená zobrazení JEDNOTLIVÝCH stránek: Map(pageIdx -> {zoom,panX,panY,rot,manual}).
// Mají přednost před globálním nastavením skladby (Jan: „v případě vycentrování prioritu").
const pageViews = reactive(new Map());
const hasSavedPageView = ref(false);
const panX = ref(0);        // posun stránky (dvouprstý pan)
const panY = ref(0);

// --- Hláška o uložení (toast) ---
// Uložení výchozího zobrazení se musí uživateli POTVRDIT: tlačítko se sice
// vybarví, ale to říká jen „něco je uložené" — při dalším stisku z něj
// nepoznáš, že se uložil nový stav. Hláška se ukazuje až PO skutečném zápisu
// do IndexedDB (await výše), takže nemůže lhát o neuloženém stavu.
const toast = ref('');
let toastTimer = null;
function showToast(msg) {
  toast.value = msg;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => { toast.value = ''; }, 2200);
}

const annotMode = ref(false);
const tool = ref('pencil');
const activeItem = ref(null);

// Rozšířené anotace
// DVĚ palety:
//  - Tužka (a text/dynamika): syté, tmavší odstíny — mají držet na bílém papíře
//    jako inkoust (Jan: „barvy jsou příliš jemné a splývají").
//  - Zvýrazňovač: světlé, KŘIKLAVÉ barvy — zvýrazňovač má být vidět na první
//    pohled a přes multiply má jen podbarvit noty, ne je přebarvit (Jan).
// Pořadí odstínů je v obou paletách stejné, takže se dá přebarvovat podle indexu.
const PEN_COLORS = ['#111111', '#c0392b', '#e8a300', '#e8622a', '#2e8b57', '#1f6fd0', '#d4a017', '#d81b7a', '#0f3d6e'];
const HL_COLORS  = ['#fff200', '#ff5252', '#7bff3d', '#ff8ad8', '#3dffa0', '#4fd8ff', '#ffb300', '#c77dff', '#00e5ff'];
// Paleta podle nástroje — v panelu se ukáže ta správná
const colors = computed(() => tool.value === 'highlighter' ? HL_COLORS : PEN_COLORS);
// Stará jemná paleta → nové barvy. Klíčem je původní odstín; hodnota je nová
// barva PRO TUŽKU. Zvýrazňovač má vlastní mapu (HL_UPGRADE) a přebarvuje se jí.
const COLOR_UPGRADE = {
  '#1a1a1a': '#111111',
  '#c05a4a': '#c0392b',
  '#e5d7a6': '#e8a300',
  '#f2c4b6': '#e8622a',
  '#bcd3b6': '#2e8b57',
  '#a8c4e0': '#1f6fd0',
  '#e5c9a8': '#d4a017',
  '#d9b6d9': '#d81b7a',
  '#1a2a4a': '#0f3d6e',
};
// Zvýrazňovač: z jakékoli dřívější barvy (stará jemná i nová sytá tužková) na
// křiklavou. Index v paletě drží odstín, takže modrá zůstane modrá.
const HL_UPGRADE = {};
[...Object.keys(COLOR_UPGRADE), ...Object.values(COLOR_UPGRADE)].forEach((old, i) => {
  HL_UPGRADE[old] = HL_COLORS[i % HL_COLORS.length];
});
HL_UPGRADE['#111111'] = HL_COLORS[0];
// Přepíše uloženou barvu na novou. Zvládne i 8znakový zápis s alfou
// (zvýrazňovač dřív ukládal 'RRGGBB80') — u zvýrazňovače se alfa zahodí úplně,
// protože průhlednost nahrazuje multiply.
function upgradeColor(color, isHighlighter) {
  if (!color || typeof color !== 'string') return color;
  const base = color.slice(0, 7).toLowerCase();
  const map = isHighlighter ? HL_UPGRADE : COLOR_UPGRADE;
  return map[base] || base;
}
// Přebarví všechny existující anotace (idempotentní — klidně opakovaně).
// Zvýrazňovač se mapuje svou paletou, ostatní nástroje tužkovou.
function upgradeAnnotationColors() {
  let changed = false;
  for (const it of annotations.value.items) {
    if (!it || typeof it.color !== 'string') continue;
    const next = upgradeColor(it.color, it.tool === 'highlighter');
    if (next !== it.color) { it.color = next; changed = true; }
  }
  return changed;
}
// Noty vložené PŘED zrcadlením mají směr nožičky v klíči („ctvrt_d“). Nový zápis
// drží směr v `flipY` a klíč je vždy výchozí („_h“) — bez tohohle srovnání by se
// stará nota s nožičkou dolů po přepnutí zrcadlení otočila na „nahoru“.
// Idempotentní: po prvním průchodu už klíč „_d“ nemá.
function normalizeNoteFlips() {
  let changed = false;
  for (const it of annotations.value.items) {
    if (!it || it.tool !== 'note') continue;
    if (it.flipX == null) { it.flipX = false; changed = true; }
    if (it.flipY == null) { it.flipY = false; changed = true; }
    const k = String(it.text || '').trim().toLowerCase();
    if (/_d$/.test(k) && NOTE_DIR_SWAP[k]) {
      it.text = NOTE_DIR_SWAP[k];
      it.flipY = true;
      changed = true;
    }
  }
  return changed;
}
const sizes = [1, 2, 3, 4, 6, 8, 12];
const annotColor = ref('#111111'); // aktuální barva pera
const annotSize = ref(1);          // aktuální velikost pera (výchozí = nejmenší 1)
const annotOpacity = ref(100);     // aktuální opacity tahu v % (100 = plné krytí)
const annotCollapsed = ref(false); // anotační panel sbalený (jen přepínač)
const editingAnnotationId = ref(null); // id anotace (text/dynamika), jejíž text se právě edituje
const annotTextDraft = ref('');     // rozpisy textu při editaci
const editingId = ref(null);        // id vybrané textové/dynamické anotace pro lištu úprav

// --- Barva textu a rámeček — volba se nastavuje přímo v dialogu (Jan, Oct 2026)
// Jan: „Taky bych přidal možnost vybírat barvu textu přímo ve stejném okně, jak
// teď vybíráme velikost a způsob vložení." Volí se pro DALŠÍ vložený text a volba
// se PAMATUJE (localStorage), stejně jako velikost — uživatel si text nastaví
// jednou a další se vkládá rovnou tak.
const textColor = ref('#111111');    // barva, se kterou se vloží další text
const textColorDraft = ref('#111111'); // hodnota v dialogu (uloží se až potvrzením)
const textBorder = ref(false);       // má další text hranatý rámeček?
const textBorderDraft = ref(false);  // hodnota v dialogu (uloží se až potvrzením)
// Velikost (odstup) a styl rámu — Jan: „velikost a styl rámečku by měl být taky
// na výběr“. Drafty se propíšou do „dalšího textu“ až potvrzením dialogu.
const textBorderWidth = ref(6);
const textBorderWidthDraft = ref(6);
const textBorderStyle = ref('solid');
const textBorderStyleDraft = ref('solid');
function loadTextStyle() {
  try {
    const c = localStorage.getItem('noty.textColor');
    if (c) { textColor.value = c; textColorDraft.value = c; }
    const b = localStorage.getItem('noty.textBorder') === '1';
    textBorder.value = b; textBorderDraft.value = b;
    const bw = Number(localStorage.getItem('noty.textBorderWidth'));
    if (TEXT_BORDER_WIDTHS.includes(bw)) { textBorderWidth.value = bw; textBorderWidthDraft.value = bw; }
    const bs = localStorage.getItem('noty.textBorderStyle');
    if (TEXT_STYLE_MAP[bs]) { textBorderStyle.value = bs; textBorderStyleDraft.value = bs; }
  } catch (e) { /* soukromý režim prohlížeče — jede se s výchozí */ }
}
function saveTextStyle() {
  try {
    localStorage.setItem('noty.textColor', textColor.value);
    localStorage.setItem('noty.textBorder', textBorder.value ? '1' : '0');
    localStorage.setItem('noty.textBorderWidth', String(textBorderWidth.value));
    localStorage.setItem('noty.textBorderStyle', textBorderStyle.value);
  } catch (e) { /* viz výše */ }
}
// Náhled v dialogu kreslí STEJNOU geometrií jako rámeček na stránce — jinak by
// uživatel viděl jiný tvar, než jaký se opravdu vloží. Velké velikosti se
// zmenšují transformem, aby neroztlačily dialog (poměr zůstává).
const _previewMetrics = (() => {
  if (typeof document === 'undefined') return null;
  try { return document.createElement('canvas').getContext('2d'); } catch (e) { return null; }
})();
const _previewWidthCache = new Map();
function previewTextWidth(text, size) {
  const key = size + '|' + text;
  if (_previewWidthCache.has(key)) return _previewWidthCache.get(key);
  let w = text.length * size * TEXT_ADV_EM;
  if (_previewMetrics) {
    try {
      _previewMetrics.font = size + 'px system-ui, sans-serif';
      const m = _previewMetrics.measureText(text);
      if (m.width) w = m.width;
    } catch (e) { /* zůstane odhad */ }
  }
  _previewWidthCache.set(key, w);
  return w;
}
const textPreviewStyle = computed(() => {
  const s = textSizeDraft.value;
  const txt = annotTextDraft.value || 'Aa';
  const w = previewTextWidth(txt, s);
  const h = _fontHeight(s);
  const pad = TEXT_BORDER_WIDTHS.includes(textBorderWidthDraft.value) ? textBorderWidthDraft.value : 6;
  const side = Math.max(w, h) + pad * 2;
  const scale = Math.min(1, 48 / Math.max(side, s));
  const st = { fontSize: s + 'px', color: textColorDraft.value, lineHeight: 1 };
  if (scale < 1) st.transform = 'scale(' + scale.toFixed(3) + ')';
  if (textBorderDraft.value) {
    const m = TEXT_STYLE_MAP[textBorderStyleDraft.value] || TEXT_STYLE_MAP.solid;
    st.width = side + 'px';
    st.height = side + 'px';
    st.boxSizing = 'border-box';
    st.display = 'flex';
    st.alignItems = 'center';
    st.justifyContent = 'center';
    st.border = '1.5px ' + (m.dash ? (textBorderStyleDraft.value === 'dotted' ? 'dotted' : 'dashed') : 'solid')
                + ' ' + textColorDraft.value;
  }
  return st;
});

// --- Velikost textu PŘED vložením (Jan, Oct 2026) ------------------------
// Jan: „Uživatel nemá možnost vybrat velikost písma. Může ji upravit až po
// vložení pomocí nástroje ‚ruka‘. Měla by být možnost tento text nastavit ještě
// před vložením. A po vložení by na vložený text měl být rovnou aplikovaný
// nástroj ‚ruka‘, aby mohl hned manipulovat s vloženým prvkem.“
// Volba se PAMATUJE (localStorage) — uživatel si velikost poznámek nastaví jednou
// a další text se vkládá rovnou v ní, ne pořád „naslepo“ z výchozí hodnoty.
const TEXT_SIZE_MIN = 10, TEXT_SIZE_MAX = 120;
const textSize = ref(20);           // velikost, se kterou se vloží další text
const textSizeDraft = ref(20);      // hodnota v dialogu (uloží se až potvrzením)
// Text, který se právě otevřel rukou (existující prvek) — dialog musí ukázat
// JEHO velikost, ne tu připravenou pro nový text (viz editText).
const editingTextSize = ref(null);
function clampTextSize(v) {
  const n = Math.round(Number(v) || 0);
  return Math.min(TEXT_SIZE_MAX, Math.max(TEXT_SIZE_MIN, n || 20));
}
function loadTextSize() {
  try {
    const raw = localStorage.getItem('noty.textSize');
    if (raw != null) { const v = clampTextSize(raw); textSize.value = v; textSizeDraft.value = v; }
  } catch (e) { /* soukromý režim prohlížeče — jede se s výchozí */ }
}
function saveTextSize() {
  try { localStorage.setItem('noty.textSize', String(textSize.value)); } catch (e) { /* viz výše */ }
}
// Krok pro tlačítka ± — JEDNA konstanta pro celou čtečku (Jan, Oct 2026):
// „Velikost textu se tlačítkem + mění pokaždé jinak. Jednou po 3 bodech, někdy
// po 2, někdy po 4… Potřebuji nějaký konzistentní způsob. Třeba po 3 bodech."
// Dřív se krok odvozoval z aktuální velikosti (2 / 5 / 10), takže se s každým
// stiskem měnil — uživatel neměl šanci odhadnout, o kolik text zvětší.
const TEXT_SIZE_STEP = 3;
function bumpTextSize(dir) {
  textSizeDraft.value = clampTextSize(textSizeDraft.value + dir * TEXT_SIZE_STEP);
}

// --- VKLÁDÁNÍ NOT: velikost noty (Jan, Oct 2026) --------------------------
// Nota se musí trefit do velikosti osnovy V NOTÁCH — to je jiné číslo než
// velikost textové poznámky (osnova = 1 em, poznámka ~20 px), proto má vlastní
// pamatovanou hodnotu. Stejný krok i meze jako u textu (TEXT_SIZE_STEP), aby se
// „+“ chovalo všude stejně.
// Krok u NOT je 1 px, ne 3 (Jan, Oct 2026): „Velikost not bych ideálně měnil po 1px.
// Teď to skáče po 3px.“ Nota se musí trefit do velikosti osnovy V NOTÁCH, a tam je
// každý pixel znát — u textu zůstává krok 3 (tam je to jedno a ubývá to zbytečně
// pomalu). Proto vlastní konstanta, ne TEXT_SIZE_STEP.
const NOTE_SIZE_STEP = 1;
const noteSize = ref(30);        // velikost, se kterou se vloží další nota
const noteSizeDraft = ref(30);   // hodnota v dialogu (uloží se až potvrzením)
function clampNoteSize(v) { return clampTextSize(v); }
function loadNoteSize() {
  try {
    const raw = localStorage.getItem('noty.noteSize');
    if (raw != null) { const v = clampNoteSize(raw); noteSize.value = v; noteSizeDraft.value = v; }
  } catch (e) { /* soukromý režim prohlížeče — jede se s výchozí */ }
}
function saveNoteSize() {
  try { localStorage.setItem('noty.noteSize', String(noteSize.value)); } catch (e) { /* viz výše */ }
}
function bumpNoteSize(dir) {
  noteSizeDraft.value = clampNoteSize(noteSizeDraft.value + dir * NOTE_SIZE_STEP);
}

// --- Zrcadlení noty (Jan, Oct 2026): „možnost noty zrcadlově otočit, horizontálně
// --- i vertikálně“ ---------------------------------------------------------------
// Zrcadlí se KOLEM BODU UKOTVENÍ (střed hlavičky na účaří), takže hlavička zůstane
// přesně tam, kam uživatel klepl — mění se jen to, na kterou stranu jde nožička.
// Vertikální zrcadlení NENÍ totéž co „nožička dolů“ z nabídky: tam se nožička i
// přesune na druhou stranu hlavičky, zrcadlení ji nechá na stejné straně.
// Volba se ZÁMĚRNĚ NEPAMATUJE (na rozdíl od velikosti): zrcadlení je vlastnost jedné
// noty, ne skladby, takže další nota začíná nezrcadlená.
const noteFlipX = ref(false);
const noteFlipY = ref(false);
// Transformace pro SVG <text>: měřítko kolem ukotvení (translate → scale → zpět).
// Bez zrcadlení vrací undefined, aby se atribut vůbec nevypsal.
// Svisle se u not s nožičkou překlápí VÝMĚNOU GLYFU (viz NOTE_DIR_SWAP), takže
// měřítko svisle se použije jen tam, kde protějšek neexistuje (celá nota, pomlky).
function noteMirrorY(it) {
  if (!it || it.tool !== 'note' || !it.flipY) return false;
  return !NOTE_DIR_SWAP[String(it.text || '').trim().toLowerCase()];
}
function noteFlipTransform(it) {
  if (!it || it.tool !== 'note' || it.x == null || it.y == null) return undefined;
  const my = noteMirrorY(it);
  if (!it.flipX && !my) return undefined;
  const sx = it.flipX ? -1 : 1, sy = my ? -1 : 1;
  return `translate(${it.x} ${it.y}) scale(${sx} ${sy}) translate(${-it.x} ${-it.y})`;
}
// Přepnutí zrcadlení v dialogu (před vložením). Propíše se i do rozpracované noty,
// aby náhled na stránce ukazoval totéž co mini náhled v dialogu.
function toggleFlip(axis) {
  if (axis === 'x') noteFlipX.value = !noteFlipX.value;
  else noteFlipY.value = !noteFlipY.value;
  const it = activeItem.value;
  if (it && it.tool === 'note' && editingAnnotationId.value === it.id) {
    it.flipX = noteFlipX.value;
    it.flipY = noteFlipY.value;
  }
}
// Přepnutí zrcadlení u UŽ VLOŽENÉ noty (pás úprav nástroje Ruka).
function toggleNoteFlip(it, axis) {
  if (!it || it.tool !== 'note') return;
  if (axis === 'x') it.flipX = !it.flipX;
  else it.flipY = !it.flipY;
  noteFlipX.value = !!it.flipX;
  noteFlipY.value = !!it.flipY;
  saveAnnotations();
}

// Náhled noty ve SKUTEČNÉ velikosti — notační font (NotyDyn), ne systémové písmo.
// Nota je na výšku celá osnova (1 em), takže velké velikosti se v náhledu zmenšují
// stejně jako u textu (jinak by roztlačily dialog). Zrcadlení je vidět i tady —
// uživatel musí vidět, co opravdu dostane (na rozdíl od textu se tu překlápí znak).
const notePreviewStyle = computed(() => {
  const s = noteSizeDraft.value;
  const scale = Math.min(1, 48 / Math.max(s, 1));
  // Svislý směr u not s nožičkou řeší VÝMĚNA GLYFU (níž), takže měřítko svisle
  // se překlápí jen tam, kde protějšek není (celá nota, pomlky).
  const mirrorY = noteFlipY.value
    && !NOTE_DIR_SWAP[String(annotTextDraft.value || '').trim().toLowerCase()];
  const sx = scale * (noteFlipX.value ? -1 : 1);
  const sy = scale * (mirrorY ? -1 : 1);
  const st = { fontFamily: "'NotyDyn', serif", fontSize: s + 'px', lineHeight: 1,
               color: annotColor.value };
  if (sx !== 1 || sy !== 1) st.transform = `scale(${sx.toFixed(3)}, ${sy.toFixed(3)})`;
  return st;
});

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
// Text k vykreslení: dynamika/značka = SMuFL znak (font NotyDyn), ostatní = jak je
function annotDisplayText(it) {
  if (!it) return '';
  if (it.tool === 'dynamic') return dynGlyph(it.text).text;
  if (it.tool === 'mark') return markGlyph(it.text).text;
  if (it.tool === 'note') return noteGlyphFor(it.text, it.flipY).text;
  return it.text || '';
}
// Je to dynamika/značka/nota, kterou font neumí? (zvýrazníme v náhledu, ať uživatel ví)
function dynUnknown(it) {
  if (!it || !it.text) return false;
  if (it.tool === 'dynamic') return !dynGlyph(it.text).known;
  if (it.tool === 'mark') return !markGlyph(it.text).known;
  if (it.tool === 'note') return !noteGlyphFor(it.text, it.flipY).known;
  return false;
}

// --- Značky pro výšky not: posuvky, ozdoby a artikulace ---
// Stejný princip jako dynamika: každá značka je JEDEN glyf v notačním fontu
// NotyDyn (SMuFL), ne ASCII znak. Uživatel klepne na dlaždici v novém nástroji
// „Značky" a značka se položí na noty; rukou se přesune, guma ji smaže.
// Kódy i šířky jsou ověřené z fontu (advance width v em).
const MARK_GROUPS = [
  {
    label: 'Posuvky',
    items: [
      { key: 'bb',    label: 'dvojité béčko',   cp: 0xE264 },
      { key: 'b',     label: 'béčko',           cp: 0xE260 },
      { key: 'odr',   label: 'odrážka',         cp: 0xE261 },
      { key: 'k',     label: 'křížek',          cp: 0xE262 },
      { key: 'kk',    label: 'dvojitý křížek',  cp: 0xE263 },
    ],
  },
  {
    label: 'Ozdoby',
    items: [
      { key: 'trylek', label: 'trylek',           cp: 0xE566 },
      { key: 'obal',   label: 'obal',             cp: 0xE567 },
      { key: 'obalo',  label: 'obrácený obal',    cp: 0xE568 },
      { key: 'trylks', label: 'kratší trylek',    cp: 0xE56C },
      { key: 'mord',   label: 'mordent',          cp: 0xE56D },
    ],
  },
  {
    label: 'Drobnosti',
    items: [
      { key: 'ferm',  label: 'fermata (koruna)', cp: 0xE4C0 },
      { key: 'cez',   label: 'cezura',           cp: 0xE4D1 },
      { key: 'dech',  label: 'dech',             cp: 0xE4CE },
      { key: 'akc',   label: 'akcent',           cp: 0xE4A0 },
      { key: 'stacc', label: 'staccato',         cp: 0xE4A2 },
      { key: 'ten',   label: 'tenuto',           cp: 0xE4A4 },
    ],
  },
];
// Šířky glyfů (advance width v em) — pro přesný rámeček výběru i hit-test.
// Musí odpovídat fontu; když se sem dostane špatné číslo, rámeček a klikatelná
// plocha se rozejdou (přesně ta vada, kterou u dynamiky řeší DYN_ADV).
const MARK_ADV = {
  bb: 0.413, b: 0.226, odr: 0.168, k: 0.249, kk: 0.250,
  trylek: 0.521, obal: 0.460, obalo: 0.457, trylks: 0.730, mord: 0.729,
  ferm: 0.605, cez: 0.385, dech: 0.153, akc: 0.339, stacc: 0.084, ten: 0.338,
};
const MARK_LOOKUP = (() => {
  const m = new Map();
  for (const g of MARK_GROUPS) for (const it of g.items) m.set(it.key, it);
  return m;
})();
// Povolené klíče značek — pro validaci uložených anotací (viz markGlyph).
const MARK_KEYS = new Set(MARK_LOOKUP.keys());
function markGlyph(raw) {
  const k = String(raw || '').trim().toLowerCase();
  if (!MARK_KEYS.has(k)) return { text: '', known: false };
  return { text: String.fromCodePoint(MARK_LOOKUP.get(k).cp), known: true };
}
function markAdvEm(raw) {
  const k = String(raw || '').trim().toLowerCase();
  return MARK_ADV[k] != null ? MARK_ADV[k] : 0.5;
}
function markLabel(raw) {
  const it = MARK_LOOKUP.get(String(raw || '').trim().toLowerCase());
  return it ? it.label : '';
}
// Je to notační text? (dynamika i značky se vykreslují fontem NotyDyn)
function isNotationText(it) {
  return !!it && (it.tool === 'dynamic' || it.tool === 'mark' || it.tool === 'note');
}
// Rodiny anotací, které se umisťují klepnutím a nesou `x`/`y` (dialogy, přesun
// rukou, sledování prstu). JEDNO místo pro všechny sourozenecké kontroly —
// nová rodina se přidá sem a nepropadne na pěti místech zvlášť (přesně ta vada,
// kdy „někde to funguje a někde ne“).
const TEXT_ANNOT_TOOLS = new Set(['text', 'dynamic', 'mark', 'note']);
// Bere i nástroj (řetězec) i hotový prvek — volá se obojím: `isTextAnnot(tool.value)`.
function isTextAnnot(x) {
  return TEXT_ANNOT_TOOLS.has(typeof x === 'string' ? x : (x && x.tool));
}
// Klepnutí na dlaždici značky: vyplní klíč a rovnou potvrdí.
// Stejná past jako u dynamiky — dialog se otevírá až po ZVEDNUTÍ pera, a tentýž
// dotyk se vzápětí vyřídí jako kompatibilitní `click`; dlaždice proto reaguje na
// POLOŽENÍ (pointerdown), na které zbloudilá událost nedosáhne.
function pickMark(k) {
  annotTextDraft.value = k;
  confirmTextAnnot();
}

// --- Vkládání not: notové hodnoty a pomlky (SMuFL, blok „Individual notes") ---
// Stejný princip jako Značky: dlaždice položí JEDEN glyf z fontu NotyDyn na osnovu.
// Kódy, šířky (adv) i obrysové meze (box = x0, x1, y0, y1 v em; kladné y = nahoru
// jako v fontu) jsou VYČTENÉ Z FONTU (fontTools), ne odhadem — stejné číslo platí
// pro rámeček výběru I pro plochu, na kterou se dá klepnout. Nota je posazená na
// účaří (střed hlavičky = účaří), takže hlavička sedne na místo klepnutí.
const NOTE_GROUPS = [
  {
    // V nabídce je JEDNA dlaždice na hodnotu (směr nožičky se přepíná zrcadlením
    // svisle) — Jan: „po výběru délky noty jsou tam zbytečně i ty zrcadlené
    // varianty. Stačí možnost to otočit.“ Varianty „_d“ proto zůstávají v datech
    // (kvůli UŽ ULOŽENÝM notám a kvůli výměně glyfu při svislém zrcadlení), ale
    // dlaždici nedostanou (`hide`).
    label: 'Noty',
    items: [
      { key: 'cela',     label: 'celá nota',              cp: 0xE1D2, adv: 0.4590, box: [0.0000, 0.4590, -0.1370, 0.1360] },
      { key: 'pulova_h', label: 'půlová nota',            cp: 0xE1D3, adv: 0.3410, box: [0.0000, 0.3410, -0.1450, 0.8750] },
      { key: 'ctvrt_h',  label: 'čtvrťová nota',          cp: 0xE1D5, adv: 0.3320, box: [0.0000, 0.3320, -0.1410, 0.8750] },
      { key: 'osm_h',    label: 'osminová nota',          cp: 0xE1D7, adv: 0.5660, box: [0.0000, 0.5660, -0.1380, 0.8730] },
      { key: 'sestn_h',  label: 'šestnáctinová nota',     cp: 0xE1D9, adv: 0.5810, box: [0.0000, 0.5810, -0.1380, 0.8730] },
      { key: 'pulova_d', label: 'půlová nota (dolů)',     cp: 0xE1D4, adv: 0.3410, box: [0.0000, 0.3410, -0.8750, 0.1450], hide: true },
      { key: 'ctvrt_d',  label: 'čtvrťová nota (dolů)',   cp: 0xE1D6, adv: 0.3320, box: [0.0000, 0.3320, -0.8750, 0.1410], hide: true },
      { key: 'osm_d',    label: 'osminová nota (dolů)',   cp: 0xE1D8, adv: 0.3320, box: [0.0000, 0.3320, -0.8820, 0.1410], hide: true },
      { key: 'sestn_d',  label: 'šestnáctinová nota (dolů)', cp: 0xE1DA, adv: 0.3320, box: [0.0000, 0.3320, -0.8830, 0.1410], hide: true },
    ],
  },
  {
    label: 'Pomlky',
    items: [
      { key: 'poml_cela',  label: 'pomlka celá',          cp: 0xE4E3, adv: 0.2830, box: [0.0000, 0.2820, -0.1350, 0.0090] },
      { key: 'poml_pul',   label: 'pomlka půlová',        cp: 0xE4E4, adv: 0.2830, box: [0.0000, 0.2820, -0.0020, 0.1420] },
      { key: 'poml_ctvrt', label: 'pomlka čtvrťová',      cp: 0xE4E5, adv: 0.2700, box: [0.0010, 0.2700, -0.3750, 0.3730] },
      { key: 'poml_osm',   label: 'pomlka osminová',      cp: 0xE4E6, adv: 0.2500, box: [0.0000, 0.2470, -0.2510, 0.1740] },
      { key: 'poml_sestn', label: 'pomlka šestnáctinová', cp: 0xE4E7, adv: 0.3200, box: [0.0000, 0.3200, -0.5000, 0.1790] },
    ],
  },
];
const NOTE_LOOKUP = (() => {
  const m = new Map();
  for (const g of NOTE_GROUPS) for (const it of g.items) m.set(it.key, it);
  return m;
})();
const NOTE_KEYS = new Set(NOTE_LOOKUP.keys());
// Výměna směru nožičky. Klíč nese VÝCHOZÍ směr („_h“), směr DOLŮ drží `flipY`.
// ⚠️ Svislé zrcadlení u not s nožičkou NENÍ překlopení obrázku, ale VÝMĚNA GLYFU:
// v Bravuře má „nožička dolů“ (noteQuarterDown) nožičku na druhé straně hlavičky
// než zrcadlový obraz noty s nožičkou nahoru (v fontu je to vidět: u „_d“ je
// nožička vlevo, u překlopeného „_h“ by zůstala vpravo). Noty v notách vypadají
// tak, jak je kreslí `_d`, proto se svislé zrcadlení dělá výměnou glyfu.
const NOTE_DIR_SWAP = {
  pulova_h: 'pulova_d', pulova_d: 'pulova_h',
  ctvrt_h: 'ctvrt_d',   ctvrt_d: 'ctvrt_h',
  osm_h: 'osm_d',       osm_d: 'osm_h',
  sestn_h: 'sestn_d',   sestn_d: 'sestn_h',
};
// Klíč, kterým se nota SKUTEČNĚ kreslí (zrcadlení svisle vymění směr nožičky).
function noteEffKey(raw, flipY) {
  const k = String(raw == null ? '' : raw).trim().toLowerCase();
  return (flipY && NOTE_DIR_SWAP[k]) ? NOTE_DIR_SWAP[k] : k;
}
function noteGlyphFor(raw, flipY) {
  const it = NOTE_LOOKUP.get(noteEffKey(raw, flipY));
  if (!it) return { text: '', known: false };
  return { text: String.fromCodePoint(it.cp), known: true };
}
function noteGlyph(raw) { return noteGlyphFor(raw, false); }
function noteLabel(raw) {
  const it = NOTE_LOOKUP.get(String(raw || '').trim().toLowerCase());
  return it ? it.label : '';
}
// Rámeček výběru i hit-test pro notu: SKUTEČNÉ obrysové meze glyfu z fontu.
// Kreslí se s text-anchor="middle", takže počátek glyfu leží o půl šířky VLEVO
// od `it.x`; svisle je účaří v `it.y` a kladné y fontu jde na obrazovce NAHORU.
// Kdyby se sem dostalo jiné číslo než do rámečku, rámeček a klikatelná plocha se
// rozejdou — u noty je to vidět víc než u značek, protože nožička je vysoká.
function noteInkBox(it) {
  // Bere SKUTEČNĚ kreslený glyf (po výměně směru nožičky) — jeho obrys i šířku.
  const n = NOTE_LOOKUP.get(noteEffKey(it.text, it.flipY));
  if (!n || it.x == null || it.y == null) return null;
  const s = it.size || noteSize.value;
  const [bx0, bx1, by0, by1] = n.box;
  let x0 = it.x + (bx0 - n.adv / 2) * s;
  let x1 = it.x + (bx1 - n.adv / 2) * s;
  let y0 = it.y - by1 * s;
  let y1 = it.y - by0 * s;
  // Stejné zrcadlení, jaké kreslí noteFlipTransform — jinak by rámeček výběru
  // i hit-test zůstaly na NEzrcadlené straně a nota by se „dala vybrat jen jinde“.
  if (it.flipX) { const a = 2 * it.x - x1; x1 = 2 * it.x - x0; x0 = a; }
  if (noteMirrorY(it)) { const a = 2 * it.y - y1; y1 = 2 * it.y - y0; y0 = a; }
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}
// Dlaždice noty se musí vycentrovat na CELÝ OTISK noty, ne na účaří (Jan: „obrázky
// not [jsou] zarovnané na střed podle bříška. Měly by být zarovnané na střed celé.
// Nožičky jsou teď mimo tlačítka.“). CSS (flex) vycentruje ÚČAŘÍ — font NotyDyn má
// souměrné ascent/descent (2,012 em obojí), takže účaří padne přesně do středu
// dlaždice. Otisk noty ale visí NAD účařím: u noty s nožičkou o (y0+y1)/2 em, což je
// při 26 px skoro 10 px. Tímtéž posunem se dorovná (stejný princip jako kalibrace
// ikony nástroje v CSS — tam vyšlo 8,5 px při 24 px, což je 0,367 em × 24 px).
const NOTE_TILE_PX = 26;   // musí odpovídat font-size v .dyn-btn
function noteTileNudge(key, flipY) {
  const n = NOTE_LOOKUP.get(noteEffKey(key, flipY));
  if (!n) return 0;
  // Střed otisku je `cy` em NAD účařím → na obrazovce je o `cy × px` VÝŠ, takže ho
  // musíme posunout DOLŮ (kladné translateY = dolů). Opačné znaménko notu vystrčí
  // z dlaždice ještě víc (nožička ven) — proto se to měří.
  const cy = (n.box[2] + n.box[3]) / 2;
  return Number((cy * NOTE_TILE_PX).toFixed(2));
}
// Tloušťka nožičky noty. Font kreslí nožičku 0,030 em (0,12 notové mezery, doporučení
// SMuFL) — při velikosti 30 je to jen 0,9 px, takže na obrazovce šedne a působí tence
// (Jan: „Nešla by nožička noty udělat o trochu tlustší?“). Tloušťku jednoho tahu UVNITŘ
// glyfu měnit nelze, proto se celý obrys obtáhne (stroke + `paint-order: stroke`) —
// nožička se tím ztluští relativně nejvíc, hlavička jen o ~8 %. Hodnota je v em, takže
// drží i při jiné velikosti noty. Změřeno `scripts/diag-note-stem-thickness.py`.
const NOTE_STEM_GAIN = 0.025;
function noteStroke(it) {
  return it.tool === 'note' ? Number((it.size * NOTE_STEM_GAIN).toFixed(2)) : 0;
}
// Klepnutí na dlaždici noty: vyplní klíč a rovnou potvrdí (jako u značek).
// Dlaždice reaguje na POLOŽENÍ (pointerdown), ne na `click` — viz pickMark.
// Jan: „Po vložení noty by se nota automaticky měla označit. Aby mohl uživatel hned
// notu upravit a přemístit.“ → dlaždice se chová jako „Uložit a ruka“: nota se vloží,
// nástroj přepne na ruku a nota se ROVNOU vybere (rámeček + pás úprav), takže se s ní
// dá hned hýbat a měnit velikost. Znamená to ale, že na další notu se nástroj vybírá
// znovu — vkládání více not v řadě po sobě tak nejde (tak to Jan chce).
function pickNote(k) {
  annotTextDraft.value = k;
  confirmTextAnnot(true);
}

// Nabídka dynamik v dialogu — pořadí odpovídá běžnému notačnímu úzu (od slabé k silné).
// glyph = hotový znak z fontu, takže uživatel vidí přesně to, co dostane.
const DYN_PICK = [
  'ppp', 'pp', 'p', 'mp', 'mf', 'f', 'ff', 'fff',
  'fp', 'sf', 'sfz', 'fz', 'rf', 'rfz', 'sffz', 'sfp', 'n',
].map(k => ({ key: k, glyph: dynGlyph(k).text }));
// Klepnutí na dlaždici: vyplní text a rovnou potvrdí (méně klikání na tabletu).
// POZOR: dlaždice reaguje na POLOŽENÍ prstu/pera (pointerdown), ne na `click`.
// Dialog dynamiky se otevírá až po ZVEDNUTÍ pera, kterým uživatel dynamiku umístil.
// Tentýž dotyk ale prohlížeč vyřídí i jako kompatibilitní `click` — ten spadne
// DO právě otevřeného dialogu, vybere dlaždici ležící pod místem položení pera
// a okno hned zavře. Uživatel to vidí jako „okno se neotevře a rovnou se vloží
// dynamika, pokaždé jiná". Na `pointerdown` tahle zbloudilá událost nedosáhne,
// protože vzniká až po něm.
function pickDyn(k) {
  annotTextDraft.value = k;
  confirmTextAnnot();
}
// Je dialog „ozbrojený"? Tj. položil uživatel prst/pero UVNITŘ dialogu?
// Dialog se otevírá až po zvednutí pera, a tentýž dotyk se vzápětí vyřídí jako
// kompatibilitní `click` — ten spadne do už otevřeného dialogu a může vybrat
// dlaždici pod místem položení pera (jiná dynamika) nebo stisknout Zrušit
// (okno jako by se vůbec neotevřelo). Takové klepnutí nemá v dialogu co dělat:
// přijmeme jen klepnutí, jemuž předcházelo položení prstu uvnitř dialogu.
const dialogArmed = ref(false);
watch(editingAnnotationId, (id) => { dialogArmed.value = false; });
function onDialogClickCapture(e) {
  if (dialogArmed.value) { dialogArmed.value = false; return; }
  e.preventDefault();
  e.stopPropagation();
}

// --- Stejná past u LIŠTY ÚPRAV (Jan, Oct 2026) ---------------------------
// Jan: „Když vyberu nástroj ‚ruka‘ a vyberu prvek, který je přímo na pozici
// tlačítka ‚smazat‘ u okna pro editaci prvku, tak se rovnou smaže. Jak kdyby se
// označení nástrojem ruka rovnou počítalo i jako pokyn po smazání.“
//
// Příčina je táž jako u dialogu dynamiky: výběr prvku vzniká už v `pointerdown`
// (`onLayerDown` → `editingId = hit.id`), takže lišta úprav se vykreslí POD PRSTEM
// a tentýž dotyk prohlížeč vzápětí vyřídí jako kompatibilitní `click` — ten
// dopadne na to, co je teď na tom místě, tedy na tlačítko lišty (🗑, ✏️, ±, ✓).
//
// Proto lišta přijme jen klepnutí, jemuž předcházelo POLOŽENÍ uvnitř sebe.
// Platí pro CELOU lištu, ne jen pro koš — pod prstem může být kterékoli tlačítko.
const editBarArmed = ref(false);
watch(editingId, () => { editBarArmed.value = false; });
function onEditBarClickCapture(e) {
  if (editBarArmed.value) { editBarArmed.value = false; return; }
  e.preventDefault();
  e.stopPropagation();
}

// Náhled zvýrazňovače při sběru bodů — stejná geometrie jako výsledek, takže
// uživatel hned vidí, že pás je vodorovně se čtečkou (i na otočené stránce).
const hlPreviewD = computed(() => {
  const pts = hlPoints.value;
  if (pts.length < 2) return '';
  const fake = pts.length >= 3
    ? pts
    : [...pts, { x: pts[0].x + 60, y: pts[0].y, cx: (pts[0].cx != null ? pts[0].cx : pts[0].x) + 60, cy: pts[0].cy != null ? pts[0].cy : pts[0].y }];
  const corners = hlCorners(fake);
  if (!corners) return '';
  return 'M' + corners.map(q => `${q.x},${q.y}`).join('L') + 'Z';
});

const editingAnnot = computed(() =>
  editingId.value ? annotations.value.items.find(x => x.id === editingId.value) || null : null
);
// Ohraničující rámeček vybraného prvku (režim Upravit/ruka) — pro vizuální označení
const selectedBox = computed(() => {
  const it = editingAnnot.value;
  if (!it) return null;
  let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
  if (isTextAnnot(it)) {
    // Nota: rámeček ze SKUTEČNÝCH obrysových mezí glyfu (noteInkBox) — stejné
    // číslo jako hit-test v itemBox, jinak se „dá vybrat jen někde“.
    const nb = it.tool === 'note' ? noteInkBox(it) : null;
    if (nb) {
      x1 = nb.x; y1 = nb.y; x2 = nb.x + nb.w; y2 = nb.y + nb.h;
    } else if (it.x != null && it.y != null) {
      const s = it.size || 20;
      x1 = it.x; y1 = it.y - s;
      // Dynamika/značka = glyf z fontu (šířka z metrik, ne odhad), text = odhad podle znaků
      let w;
      if (it.tool === 'dynamic') w = dynAdvEm(it.text) * s;
      else if (it.tool === 'mark') w = markAdvEm(it.text) * s;
      else w = it.text ? it.text.length * s * 0.6 : s;
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
    if (it.poly && it.poly.length) {
      for (const q of it.poly) {
        if (q.x < x1) x1 = q.x; if (q.y < y1) y1 = q.y;
        if (q.x > x2) x2 = q.x; if (q.y > y2) y2 = q.y;
      }
    } else {
      x1 = Math.min(it.x1, it.x2); x2 = Math.max(it.x1, it.x2);
      y1 = Math.min(it.y1, it.y2); y2 = Math.max(it.y1, it.y2);
    }
  }
  if (x2 < x1 || y2 < y1) return null;
  const pad = 8;
  return { x: x1 - pad, y: y1 - pad, w: (x2 - x1) + pad * 2, h: (y2 - y1) + pad * 2 };
});
const editingTypeLabel = computed(() => {
  const t = editingAnnot.value ? editingAnnot.value.tool : '';
  if (t === 'dynamic') return 'Dynamika';
  if (t === 'mark') return 'Značka';
  if (t === 'note') return 'Nota';
  return t ? 'Text' : '';
});
const wedgePoints = ref([]); // body zobáčku (crescendo/decrescendo), až 3 × {x,y}
const hlPoints = ref([]);    // body zvýrazňovače (3 × {x,y}: levý spodní, levý horní, vpravo) — ve „vzpřímené" soustavě
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
// Horní lišta se dá schovat (Jan: „schovat horní lištu a zobrazit ji až po
// tapu na střední oblast stránky“) — pak noty využijí i horní pruh. Volba se
// pamatuje; v anotaci se lišta vždy ukáže, aby se z ní dalo vystoupit.
const barHidden = ref(localStorage.getItem('topbarHidden') !== '0');
// Rezervovaná výška nad stránkou: celá lišta, nebo jen malý odstup od notche
// (safe-area řeší horní lišta, když je vidět).
const barPad = computed(() => (barHidden.value ? 10 : (topBarH.value || 0)));
// Panel zvětšení (z tlačítka s procenty v liště) — z lišty zmizela 4 samostatná
// tlačítka zoomu, která zabírala skoro polovinu šířky a nutila zbytek na 35 px.
// Od Sep 2026 je to nabídka ZVĚTŠENÍ A POSUNU: rotace má vlastní tlačítko
// i vlastní panel, protože jedno gesto nemůže dělat obojí najednou.
const zoomPanelOpen = ref(false);
const prefsPanelOpen = ref(false);   // menu Zobrazení (stránka / skladba / rám)
function togglePrefsPanel() {
  prefsPanelOpen.value = !prefsPanelOpen.value;
  if (prefsPanelOpen.value) {
    annotMode.value = false; jumpMode.value = false; bookmarkMode.value = false;
    sliderOpen.value = false; zoomPanelOpen.value = false; rotPanelOpen.value = false;
    pagesPanelOpen.value = false; pagesListOpen.value = false; endEdit();
  } else {
    disarmReset();   // zavření panelu ruší „nabité“ tovární tlačítko
  }
}
function toggleZoomPanel() {
  zoomPanelOpen.value = !zoomPanelOpen.value;
  if (zoomPanelOpen.value) { annotMode.value = false; jumpMode.value = false; bookmarkMode.value = false; sliderOpen.value = false; rotPanelOpen.value = false; pagesPanelOpen.value = false; pagesListOpen.value = false; prefsPanelOpen.value = false; endEdit(); }
}
// Panel ODEBRÁNÍ STRÁNEK — samostatná nabídka, vzájemně se vylučuje s ostatními
// (jako všechny ostatní panely; Jan: „když kliknu na něco jiného, anotační mód
// se automaticky vypne“).
function togglePagesPanel() {
  pagesPanelOpen.value = !pagesPanelOpen.value;
  if (pagesPanelOpen.value) {
    annotMode.value = false; jumpMode.value = false; bookmarkMode.value = false;
    sliderOpen.value = false; zoomPanelOpen.value = false; rotPanelOpen.value = false;
    endEdit();
  } else {
    pagesListOpen.value = false;
  }
}
// Panel ROTACE — samostatná nabídka. Otevřením se zoom zavře a naopak; gesto
// se pak věnuje jen tomu, co má uživatel otevřené (Jan: „Při otevření nabídky
// rotace se budem gestem pouze rotovat. Při otevření nabídky zoomu se bude
// dělat zoom a změna pozice.“).
const rotPanelOpen = ref(false);
function toggleRotPanel() {
  rotPanelOpen.value = !rotPanelOpen.value;
  if (rotPanelOpen.value) {
    annotMode.value = false; jumpMode.value = false; bookmarkMode.value = false;
    sliderOpen.value = false; zoomPanelOpen.value = false; endEdit();
    pagesPanelOpen.value = false; pagesListOpen.value = false;
    prefsPanelOpen.value = false;
    cancelRotTween(true);        // ať úhel nevisí mezi polohami
  }
}
// GESTO SÁM ZAPNE SVŮJ REŽIM (Jan, Sep 2026): „když použiji gesto třemi prsty,
// tak se automaticky zapne rotační mód. Když použiji gesto dvěma prsty, tak se
// automaticky zapne zoom/pozice režim.“
// Volá se PŘI ZAČÁTKU gesta (touchstart s daným počtem prstů), takže uživatel
// vidí mřížku/panel ještě během otáčení a nemusí nic zapínat předem.
// Vzájemné vylučování ostatních panelů drží toggleRotPanel/toggleZoomPanel,
// takže se tu nekopíruje; už otevřený panel se jen nezavírá (žádné blikání).
function autoOpenRotMode() {
  if (!rotPanelOpen.value) toggleRotPanel();
}
function autoOpenZoomMode() {
  if (!zoomPanelOpen.value) toggleZoomPanel();
}

const cssW = ref(800);
const cssH = ref(1100);

// --- AUTOMATICKÝ RÁM (ořez okrajů + vycentrování) -------------------------
// `refW/refH` = CELÁ stránka v referenčních CSS px (fit na šířku jako dřív).
// V téhle soustavě jsou uložené anotace, takže se kvůli ořezu nic nepřemapovává.
// `cropBox` = výřez v téže soustavě; `cssW/cssH` = jak je výřez velký NA DISPLEJI.
// Anotační SVG má viewBox = cropBox, takže anotace zůstanou přesně na notách.
const refW = ref(800);
const refH = ref(1100);
const cropBox = ref({ x: 0, y: 0, w: 800, h: 1100 });
const viewBoxStr = computed(() =>
  `${cropBox.value.x} ${cropBox.value.y} ${cropBox.value.w} ${cropBox.value.h}`);
// Rám (ořez okrajů) je GLOBÁLNÍ volba celé skladby (Jan: „ořez by měl být
// globální, ne jen pro danou stránku“), ukládá se na skladbu jako `frame`.
// Priorita zobrazení je: preference STRÁNKY → preference CELÉ SKLADBY → rám.
// Díky tomu si stránka může ořez sama vypnout (uložené zobrazení má `frame: 0`),
// ale dokud žádná preference není, platí globální přepínač rámu.
const songFrame = ref(false);
const cropCache = new Map();   // `${songId}:${pageIdx}` -> {x,y,w,h} v poměrech 0..1
const pageFramed = ref(false); // je AKTUÁLNÍ stránka právě oříznutá?
function clearCropCache() { cropCache.clear(); }

// Přepnutí rámu pro CELOU skladbu. Uloží se globálně a překreslí se všechny
// stránky (cache klíčuje rám, takže se staré bitmapy zahodí).
async function toggleGlobalFrame() {
  const enable = !songFrame.value;
  songFrame.value = enable;
  // Uložit na skladbu (přežije zavření appky i přepnutí skladby).
  const s = await dbGetSong(song.id);
  if (s) { s.frame = enable ? 1 : 0; await dbSaveSong(s); }
  // Když existuje globální preference zobrazení, drží se s přepínačem ve shodě —
  // jinak by tlačítko nic nedělalo (global preference má před rámem přednost).
  if (songView.value) {
    songView.value = { ...songView.value, songId: song.id, frame: enable ? 1 : 0 };
    await dbSaveSongView(songView.value);
  }
  // Uložené zobrazení AKTUÁLNÍ stránky má přednost; aby přepínač vždy něco
  // udělal, sundá se z něj jen příznak rámu (zoom/posun/rotace zůstávají).
  const pv = pageViews.get(currentPage.value);
  if (pv && pv.frame != null) {
    const rest = { ...pv };
    delete rest.frame;
    pageViews.set(currentPage.value, rest);
    await dbSavePageView(rest);
  }
  // Ořez je „stránka se vejde na displej“ — srovnat přiblížení a posun, aby
  // obsah neutíkal doprava/dolů (Jan).
  zoom.value = 1; panX.value = 0; panY.value = 0;
  cached.clear();
  preRendered.clear();
  renderPromises.clear();
  await renderCurrent();
  showToast(enable ? 'Rám: celá skladba oříznuta' : 'Rám: celá skladba');
}

// Jaký rám si přeje uložená preference? Starší uložená zobrazení příznak
// nemají — byla vytvořena na celé stránce, takže = bez rámu.
function preferredFrame(page) {
  const pv = pageViews.get(page);
  if (pv && (pv.zoom != null || pv.rot != null || pv.panX != null || pv.panY != null || pv.frame != null)) {
    return !!pv.frame;
  }
  const v = songView.value;
  if (v && (v.zoom != null || v.rot != null || v.panX != null || v.panY != null || v.frame != null)) {
    return !!v.frame;
  }
  return songFrame.value;
}

// Detekce obsahu běží nad malým náhledem stránky (rychlost ~30 ms) a výsledek
// se drží v paměti pro každou stránku. Selhání = celá stránka (nic neořezat).
const ANALYZE_W = 560;
async function getPageCrop(pageIdx) {
  // Analýza má smysl jen pro stránky, které si rám přejí (uložený příznak).
  if (!preferredFrame(pageIdx)) return { x: 0, y: 0, w: 1, h: 1 };
  const key = `${song.id}:${pageIdx}`;
  if (cropCache.has(key)) return cropCache.get(key);
  const job = (async () => {
    try {
      const dim = await getPageWidthHeight(song, pageIdx + 1);
      const w = ANALYZE_W;
      const h = Math.max(40, Math.round((dim.height / dim.width) * w));
      // Vlastní canvas pro každou analýzu — přednačítání sousedů běží
      // souběžně s aktuální stránkou a sdílený canvas by se míchal.
      const cv = document.createElement('canvas');
      cv.width = w;
      cv.height = h;
      await renderPage(song, pageIdx + 1, cv, h);
      // renderPage kreslí v dpr rozlišení → pro analýzu zmenšit na w×h
      const small = document.createElement('canvas');
      small.width = w;
      small.height = h;
      const sctx = small.getContext('2d', { willReadFrequently: true });
      sctx.drawImage(cv, 0, 0, w, h);
      const data = sctx.getImageData(0, 0, w, h).data;
      const res = analyzeContent(data, w, h);
      return res.ok ? res.crop : { x: 0, y: 0, w: 1, h: 1 };
    } catch (e) {
      console.warn('[auto-ram] detekce selhala', e);
      return { x: 0, y: 0, w: 1, h: 1 };
    }
  })();
  cropCache.set(key, job);
  return job;
}
const annotations = ref({ items: [] });
const pagesPanelOpen = ref(false); // nabídka odebírání stránek
const pagesListOpen = ref(false);  // seznam odebraných stránek uvnitř té nabídky
// --- ODEBRANÉ STRÁNKY (vratné) ---------------------------------------------
// `currentPage` je dál INDEX DO PDF (0-based, přes všechny původní stránky) —
// proto se nic nemusí přečíslovávat v anotacích, záložkách ani skocích.
// Do světa se ale číslo stránky hlásí v POŘADÍ ZOBRAZENÝCH stránek, aby číslování
// sedělo na to, co uživatel vidí („1 / 6" místo „1 / 7" s dírou).
const hiddenPages = ref([]);        // [0-based indexy do PŮVODNÍHO PDF], vzestupně
const rawPageCount = ref(0);        // počet stránek v PDF (včetně odebraných)
// Viditelné stránky v pořadí (čísluje se 1..N přes ně) — zdroj pravdy pro UI.
const visiblePages = computed(() => {
  const out = [];
  for (let i = 0; i < rawPageCount.value; i++) {
    if (!hiddenPages.value.includes(i)) out.push(i);
  }
  return out;
});
// Pozice aktuální stránky mezi zobrazenými (pro počítadlo). Když je aktuální
// stránka odebraná (nemělo by nastat), vrať 0.
const visibleIndex = computed(() => {
  const i = visiblePages.value.indexOf(currentPage.value);
  return i < 0 ? 0 : i;
});
// Zobrazené číslo stránky pro daný index do PDF — s odebranými se počítá
// v pořadí viditelných stránek.
function dispPage(idx) {
  if (idx == null) return '';
  const i = visiblePages.value.indexOf(idx);
  return i < 0 ? idx + 1 : i + 1;
}
// Výčet odebraných stránek pro dialog („3, 5, 8").
const hiddenLabel = computed(() =>
  hiddenPages.value.map(p => dispPage(p)).join(', ')
);
// --- POSUN ČÍSLOVÁNÍ (jiné vydání) ----------------------------------------
// Jan: noty často začínají až 7. stranou nebo jsou proti jinému vydání
// posunuté o pár stránek. `pagesOffset` = číslo, které se PŘIČTE k pořadí
// zobrazené stránky, takže 1. stránka PDF se hlásí jako 1 + offset.
// Je to VÝHRADNĚ číslování — PDF, pořadí stránek, anotace, skoky ani záložky
// se nemění (ty pracují dál s indexy do PDF). Ukládá se na skladbu, takže
// s ní putuje do zálohy a platí i po zavření appky.
const pagesOffset = ref(0);
// --- SKOKY V ČÍSLOVÁNÍ (chybějící stránky sólistů) --------------------------
// Jan: „Často se stává, že máme noty, kde jsou vynechány stránky sólistů. Jsou
// tam tedy skoky v číslech. … Přidali možnost na libovolných stránkách změnit
// počítadlo, od dané stránky by se posunulo.“
// `numberJumps` = seznam skoků [{ page, delta }], kde `page` je INDEX DO PDF
// (jako u záložek a skoků — při odebírání stránek se nic nepřepočítává) a
// `delta` se PŘIČTE od této stránky dál (kumulativně přes všechny skoky).
// `pagesOffset` výše zůstává jako posun CELÉ skladby („první stránka má číslo“),
// skoky se přičítají k němu.
const numberJumps = ref([]);   // [{ page: <0-based index do PDF>, delta: <int> }]
// Pořadí ZOBRAZENÉ stránky (1-based) pro index do PDF; odebraná stránka → null.
function slotOfPdf(idx) {
  const i = visiblePages.value.indexOf(idx);
  return i < 0 ? null : i + 1;
}
// Skok je ukotvený na stránce PDF; když je ta stránka odebraná, platí od první
// ZOBRAZENÉ stránky za ní (jinak by se číslo ztratilo a skok by nikdy nezačal).
function jumpSlot(j) {
  if (!j || j.page == null) return null;
  const s = slotOfPdf(j.page);
  if (s != null) return s;
  for (let p = j.page; p < rawPageCount.value; p++) {
    const t = slotOfPdf(p);
    if (t != null) return t;
  }
  return null;
}
const numberJumpsSorted = computed(() =>
  [...numberJumps.value].sort((a, b) => (jumpSlot(a) || 0) - (jumpSlot(b) || 0))
);
// Kumulativní posun od skoků pro dané POŘADÍ ZOBRAZENÉ stránky (1-based).
function jumpsUptoSlot(slot) {
  let s = 0;
  for (const j of numberJumps.value) {
    const at = jumpSlot(j);
    if (at != null && at <= slot) s += j.delta;
  }
  return s;
}
// Zobrazené číslo stránky včetně posunu (pro všechny výpisy adresované uživateli).
// Vstup je VŽDY pořadí zobrazené stránky (výsledek dispPage / totalPages).
function withOffset(n) {
  if (n == null || n === '') return '';
  return n + pagesOffset.value + jumpsUptoSlot(n);
}
async function loadHiddenPages() {
  const s = await dbGetSong(song.id);
  hiddenPages.value = Array.isArray(s?.hiddenPages) ? [...s.hiddenPages].sort((a, b) => a - b) : [];
  // Rám (ořez) je globální volba skladby — načte se s ní.
  songFrame.value = !!(s && s.frame === 1);
  pagesOffset.value = Number.isFinite(s?.pagesOffset) ? s.pagesOffset : 0;
  numberJumps.value = Array.isArray(s?.numberJumps)
    ? s.numberJumps
        .filter(j => j && Number.isFinite(j.page) && Number.isFinite(j.delta) && j.delta !== 0)
        .map(j => ({ page: j.page, delta: j.delta }))
    : [];
}
// Po jakékoli změně množiny odebraných stránek: přepočítat `totalPages`
// (počítadlo, slider i pás miniatur pracují se ZOBRAZENÝMI stránkami).
function recomputePageOrder() {
  totalPages.value = visiblePages.value.length;
}
// Uloží seznam odebraných stránek na skladbu (nesahá na PDF ani na anotace).
async function persistHiddenPages() {
  const s = await dbGetSong(song.id);
  if (!s) return;
  s.hiddenPages = [...hiddenPages.value].sort((a, b) => a - b);
  await dbSaveSong(s);
}
// Posun číslování se ukládá na skladbu stejně jako odebrané stránky —
// je to vlastnost not, ne stav UI.
async function persistPagesOffset() {
  const s = await dbGetSong(song.id);
  if (!s) return;
  s.pagesOffset = pagesOffset.value;
  await dbSaveSong(s);
}
// Tlačítka − / + v panelu Odebrat stránky. Krok o 1 stačí — posun je
// typicky o jednu až pět stránek a hrubý skok se dělá zadáním „první stránky“.
async function bumpOffset(delta) {
  if (delta === 0) return;
  pagesOffset.value += delta;
  await persistPagesOffset();
  showToast('Číslování posunuto o ' + (pagesOffset.value > 0 ? '+' : '') + pagesOffset.value
    + ' (1. strana = ' + (1 + pagesOffset.value) + ')');
}
// Zadání „první stránky“: uživatel řekne, jaké číslo má podle předlohy
// první stránka PDF. Offset je z toho dopočítaný, takže se číslování
// okamžitě srovná s notami, které má v ruce.
async function applyFirstPage() {
  const raw = String(firstPageValue.value).trim();
  const n = parseInt(raw, 10);
  if (!raw || !Number.isFinite(n)) return;
  pagesOffset.value = n - 1;
  await persistPagesOffset();
  showToast('Číslování nastaveno — 1. strana je ' + n + '.');
  firstPageValue.value = '';
}
// --- Skoky v číslování: „tato stránka má číslo K" --------------------------
// Uloží se na skladbu (jako odebrané stránky a posun) — je to vlastnost not,
// ne stav UI, takže s ní putuje do zálohy.
async function persistNumberJumps() {
  const s = await dbGetSong(song.id);
  if (!s) return;
  s.numberJumps = numberJumps.value.map(j => ({ page: j.page, delta: j.delta }));
  await dbSaveSong(s);
}
// Nejbližší POŘADÍ ZOBRAZENÉ stránky pro zadané zobrazené číslo (inverze
// k `withOffset`). Slouží k zadání čísla stránky, když jsou ve hře skoky.
function slotForDisplayed(n) {
  const total = visiblePages.value.length;
  if (total <= 0) return 0;
  let best = 0, bestErr = Infinity;
  for (let s = 1; s <= total; s++) {
    const err = Math.abs(s + pagesOffset.value + jumpsUptoSlot(s) - n);
    if (err < bestErr) { bestErr = err; best = s; }
  }
  return best - 1;   // 0-based slot
}
// „Tato stránka má číslo K": nastaví skok ukotvený na AKTUÁLNÍ stránce tak,
// aby tato stránka hlásila K a od ní dál se číslování posunulo. Skok, který na
// téže stránce už je, se přepíše — nemusí se nic rušit předem.
async function applyNumberHere() {
  const raw = String(thisPageValue.value).trim();
  const n = parseInt(raw, 10);
  if (!raw || !Number.isFinite(n)) return;
  const idx = currentPage.value;              // index do PDF — kotva skoku
  const slot = visibleIndex.value + 1;        // pořadí zobrazené stránky (1-based)
  // Posun platný PŘED touto stránkou + základní posun celé skladby.
  const before = pagesOffset.value + jumpsUptoSlot(slot - 1);
  const delta = n - slot - before;
  // Zruš případný skok, který působí právě na téhle stránce (i když je ukotvený
  // na odebrané stránce před ní) — jinak by se oba sečetly.
  const rest = numberJumps.value.filter(j => jumpSlot(j) !== slot);
  numberJumps.value = delta === 0
    ? rest
    : [...rest, { page: idx, delta }].sort((a, b) => a.page - b.page);
  await persistNumberJumps();
  showToast(delta === 0
    ? 'Číslo ' + n + ' už této stránce odpovídá'
    : 'Od této stránky se čísluje ' + (delta > 0 ? '+' : '') + delta
      + ' (tato stránka = ' + n + '.)');
  thisPageValue.value = '';
}
// Zrušení jednoho skoku v číslování (stránky za ním se vrátí k předchozímu číslování).
async function removeNumberJump(page) {
  numberJumps.value = numberJumps.value.filter(j => j.page !== page);
  await persistNumberJumps();
  showToast('Skok v číslování zrušen');
}
// Odebere stránku z listování (VRATNĚ). Když uživatel odebere stránku, na které
// PRÁVĚ STOJÍ, přesune se na nejbližší viditelnou; když odebere jinou (třeba
// z pásu miniatur), jeho místo v notách se NESMÍ hnout (Jan: čteš noty a ono to
// odskočí jinam — to je přesně to, co u čtečky obtěžuje).
async function removePage(idx) {
  if (idx == null || idx < 0 || idx >= rawPageCount.value) return;
  if (hiddenPages.value.includes(idx)) return;
  if (visiblePages.value.length <= 1) { showToast('Poslední stránku odebrat nelze'); return; }
  const wasCurrent = (idx === currentPage.value);
  const dispNo = dispPage(idx);
  hideCacheEntry(idx);
  hiddenPages.value = [...hiddenPages.value, idx].sort((a, b) => a - b);
  recomputePageOrder();
  await persistHiddenPages();
  if (wasCurrent) await moveToPage(nearestVisible(idx));
  showToast(wasCurrent
    ? 'Stránka odebrána — zobrazeno ' + totalPages.value + ' stránek'
    : 'Odebrána stránka ' + dispNo + ' (původní ' + (idx + 1) + ') · zbývá ' + totalPages.value);
}
async function removeCurrentPage() {
  await removePage(currentPage.value);
}
// Vrátí konkrétní odebranou stránku zpět do listování.
async function restorePage(idx) {
  if (!hiddenPages.value.includes(idx)) return;
  hiddenPages.value = hiddenPages.value.filter(p => p !== idx);
  recomputePageOrder();
  await persistHiddenPages();
  showToast('Stránka vrácena (celkem ' + totalPages.value + ')');
}
async function restoreRemovedPages() {
  if (!hiddenPages.value.length) return;
  hiddenPages.value = [];
  recomputePageOrder();
  await persistHiddenPages();
  showToast('Všechny stránky vráceny (celkem ' + totalPages.value + ')');
}
// Nejbližší viditelná stránka k danému indexu (preferuj následující).
function nearestVisible(idx) {
  const vis = visiblePages.value;
  if (!vis.length) return 0;
  if (vis.includes(idx)) return idx;
  let up = null, down = null;
  for (const p of vis) {
    if (p > idx && up === null) up = p;
    if (p < idx) down = p;
  }
  return up !== null ? up : down;
}
// Uvolní cache odebrané stránky (ať nedrží bitmapu, když už ji nikdo neuvidí).
function hideCacheEntry(idx) {
  for (const k of [...cached.keys()]) {
    const page = Number(String(k).split('@')[0]);
    if (page === idx) {
      const c = cached.get(k);
      if (c) { c.width = 0; c.height = 0; }
      cached.delete(k); preRendered.delete(k); renderPromises.delete(k);
    }
  }
  clearCanvas();
}

// Slider stránek + miniatury
const pageSlider = ref(0);        // 0-based, vázaný na currentPage
const sliderOpen = ref(false);    // zobrazení slideru
const thumbs = new Map();           // pageIdx -> dataURL miniatury (NEREAKTIVNÍ: viz thumbTick)
const thumbTick = ref(0);           // bump při nové miniatuře → překreslí se jen pás
const thumbPromises = new Map();    // pageIdx -> Promise (probíhající render miniatury)
let thumbObserver = null;           // IntersectionObserver pro lazy-load miniatur
// Virtuální pás miniatur: v DOM držíme jen okno kolem aktuální stránky.
// Šířka jednoho prvku je 72 px + 8 px mezera = 80 px (viz .thumb-item CSS).
const THUMB_ITEM_W = 80;
const THUMB_WINDOW = 21;            // počet prvků v DOM (lichý → uprostřed aktuální)
const visibleThumbs = computed(() => {
  thumbTick.value;                  // závislost: dorazila nová miniatura
  const total = totalPages.value;   // počet ZOBRAZENÝCH stránek
  if (!total) return [];
  const cur = pageSlider.value;     // pozice mezi ZOBRAZENÝMI stránkami
  const half = Math.floor(THUMB_WINDOW / 2);
  let from = Math.max(0, cur - half);
  let to = Math.min(total - 1, from + THUMB_WINDOW - 1);
  from = Math.max(0, to - THUMB_WINDOW + 1);
  const out = [];
  const vis = visiblePages.value;
  for (let slot = from; slot <= to; slot++) {
    const idx = vis[slot];          // index do PDF (odebrané stránky v pásu nejsou)
    if (idx == null) continue;
    out.push({ slot, idx, src: thumbs.get(idx) || '' });
  }
  return out;
});
// Prázdné pruhy po stranách drží geometrii pásu (scroll i slider sedí na
// skutečný počet stránek, i když je v DOM jen okno).
const thumbPadLeft = computed(() => {
  const v = visibleThumbs.value;
  return v.length ? v[0].slot * THUMB_ITEM_W : 0;
});
const thumbPadRight = computed(() => {
  const v = visibleThumbs.value;
  if (!v.length) return 0;
  return Math.max(0, (totalPages.value - 1 - v[v.length - 1].slot) * THUMB_ITEM_W);
});
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
  // POZOR: annotMode se tu ZÁMĚRNĚ NEMĚNÍ. Dřív se vypínal, jenže tím se spustil
  // watch na annotMode, který umisťování hned zrušil — a když uživatel měl otevřené
  // anotace, nemohl umístit vůbec nic. Anotační panel se při umisťování jen schová
  // (v-if="annotMode && !jumpPlaceMode"), vrstva se aktivuje přes jumpPlaceMode.
}
// Ze tří bodů spočítá obdélník: levé body = svislé stěny, krajní = vodorovné.
function commitJumpPlace() {
  const [a, b, c] = jumpPlacePoints.value;
  const left = Math.min(a.x, b.x), top = Math.min(a.y, b.y);
  const right = Math.max(c.x, a.x, b.x), bottom = Math.max(a.y, b.y);
  const w = Math.max(60, right - left), h = Math.max(28, bottom - top);
  // page = stránka, na kterou uživatel klepal; tlačítko se má zobrazovat TADY
  jumpPlace.value = { x: left, y: top, w, h, page: currentPage.value };
  jumpPlaceMode.value = false;
  jumpPlacePoints.value = [];
}

// Záložky (konkrétní stránky) — per skladba
const bookmarks = ref([]);        // [{id, page, label}]
const bookmarkMode = ref(false);  // režim přidávání záložky
const bookmarkLabel = ref('');    // text záložky (volitelný)
const bookmarkEditingId = ref(null); // id záložky, jejíž řádek je právě v režimu úpravy
const bmEditLabel = ref('');         // text v inputu NA ŘÁDKU (ne v poli pro novou)
const bmEditInput = ref(null);       // element inputu v řádku (fokus po tapu na tužku)
// v-for → funkční ref (pole elementů); vždy drží jen jediný prvek v úpravě.
function setBmEditInput(el) {
  bmEditInput.value = el || null;
}
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

// Rotace jde na .rotor, ne na canvas — anotační vrstva i tlačítka skoků jsou
// jeho sourozenci, takže se otočí SPOLU s notami a zůstanou přilepené k místu,
// kam je uživatel naklepal. Kdyby se otáčel jen canvas, kreslilo by se vedle.
// .stage jen nese zoom a posun a má rozměry podle toho, jak stránka po otočení
// zabírá (při 90°/270° prohozené) — tím se otočená stránka správně vejde.
//
// ŽIVÁ rotace (prsty / držení tlačítka) je POUZE CSS a PDF se při ní nikdy
// nepřekresluje (Jan: „obrázek se neustále přegenerovává, hrozně se to seká“).
//
// Model, který to drží jednoduchý a plynulý:
//   * Bitmapa stránky se VŽDY kreslí v NEOTOČENÉM měřítku (fit-na-šířku), ať je
//     zrovna otočená jakkoli. Cache tedy nemusí být klíčovaná rotací a otočení
//     neinvaliduje ani jeden canvas → žádné překreslování při rotaci.
//   * `.rotor` se jen otočí (`rotate(Ndeg)`) a `.stage` přeškáluje hotovou
//     bitmapu (`liveFit`) — ale JEN u čtvrtvrtových orientací (±90° tlačítko),
//     kde se papír musí vejít. Rotace prsty je rigidní (měřítko 1).
//   * `liveFit` = poměr měřítka, které má papír po otočení mít (`fitScale`),
//     k měřítku, ve kterém je bitmapa nakreslená. Otočený papír se ZMENŠUJE jen
//     při vědomé změně orientace; meziúhly se jen otáčejí a smí přesáhnout okraj
//     (Jan: „Může být mimo okraje. Případně si to pak zmenším.“).
//   * DŮSLEDEK: zoom ani posun uživatele se otočením NESMÍ hnout. Uživatel
//     vidí přesně ten stav, který měl pod rukama, jen otočený.
const stageStyle = computed(() => ({
  width: visW.value + 'px',
  height: visH.value + 'px',
  transform: 'translate(' + panX.value + 'px,' + panY.value + 'px) scale(' + (zoom.value * liveFit.value) + ')',
  transformOrigin: 'center center',
  willChange: 'transform',
}));
// `liveFit` = přeškálování už vykreslené bitmapy. Je to OBYČEJNÝ REF, ne computed
// z úhlu — a v tom je celá oprava Janovy stížnosti „po dokončení rotace se obraz
// pohne. Zoom i pozici.“
//
// CO BYLO ŠPATNĚ (naměřeno v headless Chrome, sonda probe-release-snap.py):
//   Dřív se `liveFit` počítal Z ÚHLU (contain-fit otočeného papíru dělený
//   měřítkem bitmapy), a aby nebyl vidět skok v okamžiku, kdy se gesto rozhodne
//   pro rotaci, byl zpožděný „rampou“ (ROT_EASE_DEG = 30°). Jenže tím se skok
//   jen PŘESUNUL na konec gesta: dokud rampa běžela, držel `liveFit` vyhlazenou
//   (a tedy ŠPATNOU) hodnotu, a v okamžiku puštění prstu se přepnul na přesnou —
//   naměřeno 0,9097 → 0,7741 v JEDNOM SNÍMKU, tj. **−14,9 % skok**. Uživatel to
//   vidí přesně tak, jak to popsal: po dokončení rotace (při „přegenerování“)
//   se papír zmenší a s ním se posune i střed obrazu. U krátkého gesta (12°) je
//   rampa nejvíc mimo, takže skok je největší.
//
// SPRÁVNÝ MODEL (a Jan ho popsal slovy „obraz po rotaci zkrátka zůstal přesně
// tak jak je, jak si ho uživatel nastavil“): **rotace je RIGIDNÍ — mění jen
// úhel, měřítko ani posun nikdy.** `liveFit` proto mění VÝHRADNĚ ±90° TLAČÍTKO
// (vědomá změna orientace stránky, kde se papír opravdu musí vejít) a vycentrování;
// žádná rotační cesta (gesto prsty, 1°, 0,1°, držení) na něj nesahá.
//   * Gesto: `liveFit` se nemění vůbec → není co skákat, ani na začátku, ani po
//     puštění. Zbývá jediná práce na snímek = `rotate()` na `.rotor` (GPU), takže
//     je to plynulejší i výkonnostně — vypadla reaktivní závislost stage na úhlu.
//   * Otočený papír na velký úhel přesahuje čtecí plochu (ořez) — to je záměr
//     a je to vidět; na srovnání křivého skenu i na 90° orientaci slouží tlačítka.
//   * Strop 2,5 je jen pojistka proti absurdnímu roztažení; reálně je cíl <= 1.
const liveFit = ref(1);
// Měřítko, které má papír po otočení na `deg` mít (poměr k nakreslené bitmapě).
// V nule vychází přesně 1 (fitScale(0) == měřítko bitmapy), takže návrat do 0°
// nemá zlom pravidla.
function fitFor(deg) {
  const bd = baseDims.value;
  if (!bd.w || !bd.h) return 1;
  // Bez otočení je bitmapa nakreslená přesně v cílové velikosti (fit-na-šířku,
  // u rámu navíc omezený výškou) → žádné přeškálování.
  if (!deg) return 1;
  const drawn = cssW.value / bd.w;          // měřítko nakreslené bitmapy
  if (!(drawn > 0)) return 1;
  return Math.min(2.5, fitScale(bd.w, bd.h, deg) / drawn);
}
// Cílové měřítko pro daný úhel. „Vejít se CELÁ" má smysl jen u ČTVRTVRTOVÝCH
// orientací (tlačítko ±90°, uložené zobrazení stránky na šířku) — tam se papír
// opravdu musí vejít, jinak by na šířku přetékal. U MEZIÚHLŮ (křivý sken
// srovnávaný prsty o 2°) by „vejít se celá" znamenalo, že se papír při každém
// stupni zmenšuje a zase zvětšuje — přesně to cuknutí, které Jan nechce.
// Meziúhly proto jedou RIGIDNĚ: měřítko 1, papír se jen otáčí.
function fitTargetFor(deg) {
  const whole = Math.abs(deg % 90) < 0.001 || Math.abs(Math.abs(deg % 90) - 90) < 0.001;
  return whole ? fitFor(deg) : 1;
}
const rotorStyle = computed(() => ({
  width: cssW.value + 'px',
  height: cssH.value + 'px',
  transform: 'translate(-50%, -50%)' + (rot.value ? ' rotate(' + rot.value + 'deg)' : ''),
}));
// Rozměry, jak stránka po otočení zabírá na obrazovce
const visW = computed(() => Math.round(rotAvail(cssW.value, cssH.value, rot.value).w));
const visH = computed(() => Math.round(rotAvail(cssW.value, cssH.value, rot.value).h));

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
  await nextTick();
  loadPanelOffsets();   // panely tam, kam si je uživatel odtáhl
  installBackGuard();   // obrana proti systémovému gestu zpět
  loadTextSize();   // velikost textu zvolená při minulém vkládání (viz textSize)
  loadTextStyle();  // barva textu + rámeček zvolené při minulém vkládání
  loadNoteSize();   // velikost noty zvolená při minulém vkládání (viz noteSize)
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
  rawPageCount.value = await getPageCount(song);
  // Odebrané stránky jsou uložené na skladbě (součást PDF, ne UI stav).
  await loadHiddenPages();
  recomputePageOrder();
  // PRVNÍ otevření skladby musí respektovat odebrané stránky: `currentPage`
  // začíná na 0 (index do PDF), takže když je 1. stránka odebraná, vykreslila se
  // právě ona — počítadlo hlásilo „1 / 5“, ale na papíře byla odebraná stránka.
  // Při listování to spraví `gotoPage()`, `switchSong()` to dělá taky; tady to
  // chybělo (Jan, Oct 2026).
  currentPage.value = visiblePages.value[0] ?? 0;

  const saved = await dbGetAnnotations(props.id);
  if (saved && Array.isArray(saved.items)) annotations.value.items = saved.items;
  // Staré noty (směr nožičky v klíči) → nový zápis se `flipY` (viz normalizeNoteFlips)
  const norm1 = normalizeNoteFlips();
  // Staré jemné barvy → nová výrazná paleta (rovnou, bez zásahu uživatele)
  const upg1 = upgradeAnnotationColors();
  if (norm1 || upg1) {
    await dbSaveAnnotations({ songId: song.id, items: annotations.value.items });
  }

  // Načíst skoky (Da Capo / VIDE)
  const savedJumps = await dbGetJumps(props.id);
  if (savedJumps && Array.isArray(savedJumps.items)) jumps.value = savedJumps.items;

  // Načíst záložky (konkrétní stránky)
  const savedBookmarks = await dbGetBookmarks(props.id);
  if (savedBookmarks && Array.isArray(savedBookmarks.items)) {
    bookmarks.value = savedBookmarks.items;
    // Pořadí přežije reload: ruční přerovnání (manualOrder) se ukládá do DB.
    // Bez něj se záložky srovnají vzestupně podle stránky.
    bmManualOrder.value = !!savedBookmarks.manualOrder;
    if (!bmManualOrder.value) bookmarks.value.sort((a, b) => a.page - b.page);
  }

  // Načíst uložená zobrazení jednotlivých stránek (zoom/posun/rotace)
  pageViews.clear();
  const pvs = await dbGetAllPageViews(song.id);
  for (const pv of pvs) if (pv && pv.page != null) pageViews.set(pv.page, pv);

  // Velikost stránky aby se vešla na výšku
  computeFit();
  syncViewerW();   // šířka okna pro --edge-w (okrajové pruhy nesmí lhát o hraně)
  // Aplikovat uložené výchozí zobrazení (stránka → skladba → fit), jinak fit 1.0
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
  panelDragEnd();          // nedokončené tažení panelu nesmí nechat viset listenery
  uninstallBackGuard();
  window.removeEventListener('resize', onResize);
  if (barObs) { barObs.disconnect(); barObs = null; }
  disconnectThumbObserver();
  releaseWakeLock();
  clearTimeout(_bmSaveTimer);
  if (toastTimer) { clearTimeout(toastTimer); toastTimer = null; }
  if (_rotCommitTimer) { window.clearTimeout(_rotCommitTimer); _rotCommitTimer = null; }
  cancelRotTween(false);
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
  wakeVisibleHandler = () => {
    // Návrat do karty: OS mohl během spánku zahodit dotyky/tah perem bez
    // pointerupu → visel by `_activePointerId` a listování by bylo mrtvé.
    resetGestureState();
    if (document.visibilityState === 'visible') acquireWakeLock();
  };
  document.addEventListener('visibilitychange', wakeVisibleHandler);
}
function releaseWakeLock() {
  if (wakeTimer) { window.clearInterval(wakeTimer); wakeTimer = null; }
  if (wakeVisibleHandler) { document.removeEventListener('visibilitychange', wakeVisibleHandler); wakeVisibleHandler = null; }
  if (wakeLock) { wakeLock.release().catch(() => {}); wakeLock = null; }
  // Držení otáčení nesmí přežít odchod z prohlížeče
  rotHoldCancel();
}

let availW = 800, availH = 1100;
// Je pro aktuální stránku rám opravdu aktivní? (řídí se uloženou preferencí)
let frameActive = false;

// Rozměry, jak stránka PO OTOČENÍ zabere na obrazovce (pro fit a centrování)
function rotAvail(baseW, baseH, deg) {
  if (!deg) return { w: baseW, h: baseH };
  const a = Math.abs(deg) * Math.PI / 180;
  const cos = Math.abs(Math.cos(a)), sin = Math.abs(Math.sin(a));
  return { w: baseW * cos + baseH * sin, h: baseW * sin + baseH * cos };
}
// Měřítko stránky. Bez otočení zůstává ZABĚHNUTÉ fit-na-šířku (Jan: „ze všeho
// vejde celá stránka" je moc malé); s otočením se musí otočená stránka vejít
// CELÁ, jinak by její okraje zašly pod horní lištu.
// `zoom` zůstává násobitel nad tímhle měřítkem (1 = přesně tohle).
function fitScale(baseW, baseH, deg) {
  if (!baseW || !baseH) return 1;
  // Obsah se vždy vejde do CELÉ šířky čtecí plochy (i s rámem — okrajové
  // tap zóny se s rámem ignorují, Jan: „roztáhneme ten rám až do krajů“).
  if (!deg) return availW / baseW;
  const r = rotAvail(baseW, baseH, deg);
  return Math.min(availW / r.w, availH / r.h) * 0.985;
}

// Uložené výchozí zobrazení skladby (globální) — zoom, posun i rotace
async function applySongView() {
  const view = await dbGetSongView(song.id);
  songView.value = view || null;
  songZoom.value = (view && view.zoom) ? view.zoom : 1.0;
  hasSavedZoom.value = !!view;
  await applyPageView();
  updatePageViewFlag();
}
// Uložené zobrazení AKTUÁLNÍ stránky má přednost; jinak globální nastavení
// skladby; jinak fit 100 %. Uložená hodnota `null` = „tuhle položku zdediť
// z globálního nastavení" (aby stránka s uloženým zoomem nepotlačila
// globální rotaci).
async function applyPageView() {
  const pv = pageViews.get(currentPage.value) || null;
  const v = songView.value;
  zoom.value = (pv && pv.zoom != null) ? pv.zoom : ((v && v.zoom) ? v.zoom : 1.0);
  rot.value  = (pv && pv.rot  != null) ? pv.rot  : ((v && v.rot)  ? v.rot  : 0);
  panX.value = (pv && pv.panX != null) ? pv.panX : ((v && v.panX) ? v.panX : 0);
  panY.value = (pv && pv.panY != null) ? pv.panY : ((v && v.panY) ? v.panY : 0);
  // Rám znamená „výřez se vejde na displej“. Uložený posun/přiblížení
  // z dřívějška by výřez posunul dolů a doprava a spodek vystrčil z obrazovky
  // (Jan: „celé posunuté dolů a doprava, část mimo obrazovku“). Když je rám
  // aktivní, zoom i posun se proto nulují — jinak by spodek neměl prioritu.
  if (preferredFrame(currentPage.value)) {
    zoom.value = 1;
    panX.value = 0;
    panY.value = 0;
  }
  // Měřítko musí odpovídat právě nastavenému úhlu — uložená stránka na šířku
  // (nebo vrácení na 0°) se musí správně vejít, ne zdědit měřítko z jiné orientace.
  liveFit.value = fitTargetFor(rot.value);
  // Až se canvas po případném renderu dovykreslí, dorovnat jeho rozměry.
  nextTick(() => commitRotation());
}
// Je aktuální stránka nastavená zvlášť?
function updatePageViewFlag() {
  const pv = pageViews.get(currentPage.value);
  hasSavedPageView.value = !!(pv && (pv.zoom != null || pv.rot != null || pv.panX != null || pv.panY != null));
}
// Uloží aktuální zoom + posun + rotaci jako výchozí pro CELOU skladbu
async function saveZoomAsDefault() {
  songView.value = { zoom: zoom.value, panX: panX.value, panY: panY.value, rot: rot.value, frame: songFrame.value ? 1 : 0 };
  songZoom.value = zoom.value;
  hasSavedZoom.value = true;
  await dbSaveSongView({
    songId: song.id, zoom: zoom.value, panX: panX.value, panY: panY.value, rot: rot.value,
    frame: songFrame.value ? 1 : 0,
  });
  showToast('Výchozí zobrazení skladby uloženo');
}
// Uloží aktuální zoom + posun + rotaci jako výchozí pro TUTO stránku.
// Při vycentrování má přednost před globálním nastavením skladby.
async function savePageViewAsDefault() {
  const page = currentPage.value;
  const view = {
    songId: song.id, page, zoom: zoom.value, panX: panX.value, panY: panY.value,
    rot: rot.value, frame: frameActive ? 1 : 0,
  };
  pageViews.set(page, view);
  hasSavedPageView.value = true;
  await dbSavePageView(view);
  showToast('Výchozí zobrazení stránky ' + (page + 1) + ' uloženo');
}
// Zruší zvláštní nastavení této stránky → zpět na globální / fit
// Pomocná cesta po jakékoli změně preferencí: zahodit cache (mění se rám,
// zoom i rozměry) a překreslit podle nového stavu.
async function afterPrefsChange(msg) {
  cached.clear();
  preRendered.clear();
  renderPromises.clear();
  await applyPageView();
  updatePageViewFlag();
  await renderCurrent();
  if (msg) showToast(msg);
}
// Samostatné mazání pro každou formu preference (menu Zobrazení).
async function deletePageView() {
  const page = currentPage.value;
  if (!pageViews.has(page)) return;
  pageViews.delete(page);
  await dbDeletePageView(song.id, page);
  await afterPrefsChange('Zobrazení stránky smazáno');
}
async function deleteSongView() {
  if (!songView.value) return;
  songView.value = null;
  songZoom.value = 1.0;
  hasSavedZoom.value = false;
  await dbDeleteSongView(song.id);
  await afterPrefsChange('Výchozí zobrazení skladby smazáno');
}
// Rám je GLOBÁLNÍ přepínač skladby — žádné mazání „rámu stránky“ tu není;
// vypnutí dělá totéž tlačítko ořezu.

// --- TOVÁRNÍ RESET ZOBRAZENÍ ------------------------------------------------
// Smaže úplně všechny preference zobrazení této skladby: uložené pohledy
// všech stránek, globální zobrazení skladby i globální rám. Anotace, záložky,
// skoky ani odebrané stránky se NEMAŽOU — je to reset zobrazení, ne not.
// Destruktivní akce bez dialogu (Jan dialogy nechce): první klepnutí tlačítko
// jen „nabije“, druhé do 4 s teprve maže.
const resetArmed = ref(false);
let resetArmTimer = null;
function disarmReset() {
  resetArmed.value = false;
  if (resetArmTimer) { clearTimeout(resetArmTimer); resetArmTimer = null; }
}
async function factoryResetViews() {
  if (!resetArmed.value) {
    resetArmed.value = true;
    if (resetArmTimer) clearTimeout(resetArmTimer);
    resetArmTimer = setTimeout(disarmReset, 4000);
    showToast('Klepni znovu — smaže všechny preference zobrazení');
    return;
  }
  disarmReset();
  await dbDeleteAllPageViews(song.id);
  pageViews.clear();
  await dbDeleteSongView(song.id);
  songView.value = null;
  songZoom.value = 1.0;
  hasSavedZoom.value = false;
  songFrame.value = false;
  const s = await dbGetSong(song.id);
  if (s) { s.frame = 0; await dbSaveSong(s); }
  await afterPrefsChange('Všechny preference zobrazení smazány');
}
// Otočení stránky o delta stupňů (kladné = vpravo) — z TLAČÍTEK.
// Rotace je ČISTĚ CSS záležitost (bitmapa je vždy neotočená), takže velký skok
// (90°) se dá plynule DOBĚHNOUT animací úhlu — nic se přitom nepočítá z pdf.js
// a nic se nepřekresluje. Bez toho papír na jeden snímek skočí a je cítit
// cuknutí; s tweenem se otočí stejně plynule jako prsty.
// ⚠️ Tween mění i měřítko (`liveFit`) — je to vědomá změna orientace, kdy se
// otočená stránka musí vejít do čtecí plochy. Proto se cíl měřítka nastaví JEDNOU
// na začátku animace (papír se plynule zmenšuje/zvětšuje spolu s otáčením)
// a snímky animace do něj už nesahají.
function rotateBy(delta) {
  if (Math.abs(delta) >= ROT_TWEEN_MIN_DEG) { tweenRotation(delta); return; }
  setRotation(normDeg(rot.value + delta));
}
const ROT_TWEEN_MIN_DEG = 20;    // menší kroky (1°, 0,1°) jsou spojité samy
let _rotTween = null;            // { from, delta, dur, start, raf }
function tweenRotation(delta) {
  cancelRotTween(true);
  const from = rot.value;
  const to = normDeg(from + delta);
  // Trvání roste s úhlem, ale drží se v rozumných mezích (delší už působí loudavě).
  const dur = Math.max(140, Math.min(340, Math.abs(delta) * 3.0));
  // ⚠️ Měřítko se musí animovat SPOLU s úhlem — kdyby se nastavilo na cílovou
  // hodnotu hned na začátku, papír by v jednom snímku skočil (naměřeno −30 %)
  // a teprve pak se otáčel. Oba konce drží `fitTargetFor`: u meziúhlů je to 1
  // (rigidní), u ±90° fit otočené stránky, takže se papír plynule zmenšuje.
  const fitFrom = fitTargetFor(from);
  const fitTo = fitTargetFor(to);
  liveFit.value = fitFrom;
  const start = performance.now();
  const state = { from, delta, dur, start, raf: 0 };
  _rotTween = state;
  const step = (now) => {
    const t = Math.min(1, (now - start) / dur);
    const e = t * t * (3 - 2 * t);            // smoothstep — rozjezd i doběh
    rot.value = normDeg(from + delta * e);
    liveFit.value = fitFrom + (fitTo - fitFrom) * e;
    if (t < 1) {
      state.raf = requestAnimationFrame(step);
    } else {
      if (_rotTween === state) _rotTween = null;
      rot.value = to;
      liveFit.value = fitTo;
      if (_rotCommitTimer) { window.clearTimeout(_rotCommitTimer); _rotCommitTimer = null; }
      commitRotation();
    }
  };
  state.raf = requestAnimationFrame(step);
}
// Zruší rozběhnutou animaci. `settle` = dorazit na cílový úhel (jinak by stránka
// zůstala viset mezi dvěma polohami, když uživatel klikne podruhé).
function cancelRotTween(settle = false) {
  const s = _rotTween;
  if (!s) return;
  cancelAnimationFrame(s.raf);
  _rotTween = null;
  if (settle) rot.value = normDeg(s.from + s.delta);
}
// Jediné místo, které mění úhel po MALÝCH krocích (tlačítka 1°/0,1°, držení):
// nastaví úhel a po chvíli nečinnosti (tj. po skončení držení) dorovná cache.
// ⚠️ Měřítko (`liveFit`) tady ZÁMĚRNĚ neměníme. Rotace je rigidní: když si
// uživatel drží prstem nebo tlačítkem 1° papír v nějakém přiblížení, papír se
// jen otáčí a nikdy se mu nezmění měřítko ani posun (Jan: „obraz po rotaci
// zkrátka zůstal přesně tak jak je, jak si ho uživatel nastavil“). Měřítko mění
// pouze ±90° tlačítko (vědomá změna orientace) — viz tweenRotation.
let _rotCommitTimer = null;
const ROT_COMMIT_MS = 450;
function setRotation(deg) {
  rot.value = deg;
  if (_rotCommitTimer) window.clearTimeout(_rotCommitTimer);
  _rotCommitTimer = window.setTimeout(() => { _rotCommitTimer = null; commitRotation(); }, ROT_COMMIT_MS);
}
// Dorovnání po skončení změny úhlu. V novém modelu rotace NEMĚNÍ nic, co by
// vyžadovalo práci: bitmapa je vždy neotočená, `cssW/cssH` na rotaci nezávisí
// a cache je klíčovaná jen stránkou. Kopie canvasy by tedy byla čistě zbytečná
// práce navíc (naměřeno: 1 `drawImage` navíc po každém otočení, i když se obraz
// nezměnil). Kontrolujeme proto jedinou věc, která reálně může nesedět: rozměry
// viditelného canvasu (např. po změně velikosti okna) — a jen tehdy vykreslíme.
function commitRotation() {
  syncViewerW();
  const c = canvasEl.value;
  if (!c) return;
  const want = cssW.value + 'x' + cssH.value;
  const has = parseFloat(c.style.width) + 'x' + parseFloat(c.style.height);
  if (want !== has) renderCurrent();
}
// Zachováno pro gesto dvěma prsty (konec tahu). Dřív tady byl reset zoomu na
// 1.0 a posunu na 0 — to bylo přesně to cuknutí, které Janovi vadilo („stránka
// prvně resetuje svůj zoom a pozici, pak teprve začne rotovat“). Dnes je zoom
// i posun soustředný s rotací, takže se s nimi nesmí hýbat: `keepUserView` proto
// říká jen to, že si uživatel drží svůj pohled a nesahá se na nic.
// Funkce zůstává (volá ji gesto i staré cesty), ale je záměrně inertní vůči
// zoomu/posunu — jediné, co dělá, je dorovnání cache.
async function refreshAfterRotation(keepUserView = false) {
  void keepUserView;
  commitRotation();
}
// Držení tlačítka otáčení = plynulé otáčení (jako auto-repeat na klávesnici).
// Klepnutí udělá JEDEN krok přes @click; držení pustí opakování až po počáteční
// prodlevě, aby se krok nepočítal dvakrát (pointerdown + click u jednoho ťuknutí).
// Během držení se NEPŘEKRESLUJE nic — papír se jen otočí (CSS) a přesné
// dorovnání proběhne jednou po puštění tlačítka (setRotation → commitRotation).
let _rotHoldTimer = null;
let _rotDelayTimer = null;
let _rotHoldValue = 0;
let _rotHoldRepeats = 0;
const ROT_HOLD_DELAY_MS = 400;   // jak dlouho držet, než se rozjede opakování
const ROT_HOLD_STEP_MS = 60;
function rotHoldStart(delta) {
  rotHoldCancel();
  _rotHoldValue = rot.value;
  _rotHoldRepeats = 0;
  _rotDelayTimer = window.setTimeout(() => {
    _rotDelayTimer = null;
    _rotHoldTimer = window.setInterval(() => {
      _rotHoldValue = ((_rotHoldValue + delta) % 360 + 360) % 360;
      setRotation(_rotHoldValue);
      _rotHoldRepeats++;
    }, ROT_HOLD_STEP_MS);
  }, ROT_HOLD_DELAY_MS);
}
function rotHoldCancel() {
  if (_rotDelayTimer) { window.clearTimeout(_rotDelayTimer); _rotDelayTimer = null; }
  if (_rotHoldTimer) { window.clearInterval(_rotHoldTimer); _rotHoldTimer = null; }
}
// Dokončení držení: doladit přesně. Když se opravdu opakovalo, klik, který po
// pointerup následuje, se zahodí (jinak by přidal ještě jeden krok navíc).
function rotHoldStop() {
  const repeated = _rotHoldRepeats > 0;
  rotHoldCancel();
  if (!repeated) return;              // ťuknutí → jeden krok udělá @click
  if (_rotCommitTimer) { window.clearTimeout(_rotCommitTimer); _rotCommitTimer = null; }
  commitRotation();                   // finální dorovnání
  _rotHoldDidRepeat = true;
  window.setTimeout(() => { _rotHoldDidRepeat = false; }, 0);
}
let _rotHoldDidRepeat = false;
// Klepnutí na tlačítko otáčení — po držení se zahodí (krok už proběhl v držení).
function rotateClick(delta) {
  if (_rotHoldDidRepeat) { _rotHoldDidRepeat = false; return; }
  rotateBy(delta);
}
// Úhel pro popisek: celé stupně, ale u jemného doladění ukáže desetinu.
// Jan si u křivého skenu ladí třeba 0,4° — „3°" by mu to zatajilo.
const rotLabel = computed(() => {
  const v = rot.value;
  const rounded = Math.round(v * 10) / 10;
  const isWhole = Math.abs(rounded - Math.round(rounded)) < 0.05;
  return (isWhole ? String(Math.round(rounded)) : rounded.toFixed(1).replace('.', ',')) + '°';
});
// Zruší rotaci a vrátí stránku do výchozího zobrazení.
// Tween se nejdřív dorazí (jinak by animace přepsala nulu, kterou jsme právě
// nastavili) — a zoom/posun uživatele zůstávají, stejně jako u ostatních cest.
async function resetRotation() {
  cancelRotTween(false);
  liveFit.value = fitTargetFor(0);   // zpět do svislé orientace → znovu fit na šířku
  setRotation(0);
}
function computeFit() {
  // .page-area je přes celou výšku (lišta je overlay), ale má padding-top o výšce
  // lišty. Odečteme ho, aby se noty vešly POD lištu a nepod ni nezajely.
  const el = pageAreaEl.value || viewerEl.value;
  if (el) {
    // Lišta je overlay → do fitu nevstupuje. Odečítá se jen skutečné odsazení
    // plochy (symetrické, včetně safe-area), takže ořez využije celou výšku
    // a papír zůstane vycentrovaný.
    const cs = getComputedStyle(el);
    const padT = parseFloat(cs.paddingTop) || 0;
    const padB = parseFloat(cs.paddingBottom) || 0;
    availH = Math.max(200, el.clientHeight - padT - padB - 8);
    availW = Math.max(200, el.clientWidth - 12);
  }
}

// Základní (neotočené) rozměry aktuální stránky v PDF bodech — z nich se počítá
// fit pro otočenou stránku i inverzní rotace souřadnic pero → canvas.
// Musí být reaktivní, protože z něj počítá `fitFor` (a přes něj měřítko pro ±90°).
// Původní past: dokud `liveFit` byl computed s ranou návratovou cestou nad
// NEREAKTIVNÍ proměnnou, dependency tracking se nikdy nezapnul a měřítko zůstalo
// navždy v cache (naměřeno: během celého gesta se nezměnilo). Ref to drží.
const baseDims = ref({ w: 0, h: 0 });

// Referenční soustava = celá stránka při fit na šířku (šířka = availW).
// V ní jsou uložené anotace; ořez se do ní promítá jen přes viewBox.
function pageReference(dim) {
  return { w: Math.round(availW), h: Math.round((dim.height / dim.width) * availW) };
}
// Geometrie zobrazení stránky: výřez obsahu, jeho velikost na displeji
// a tentýž výřez v PDF bodech pro render.
function pageGeometry(dim, frac, ref, targetW, maxH = 0) {
  const box = {
    x: frac.x * ref.w, y: frac.y * ref.h,
    w: frac.w * ref.w, h: frac.h * ref.h,
  };
  let scale = targetW / box.w;
  // Oříznutá stránka se musí vejít i NA VÝŠKU. Samotné fit-na-šířku stačilo
  // u celé stránky, ale úzký/svislý výřez se šířkou roztáhl tak, že přetekl
  // displej (Jan: „zvětší na větší velikost než se vejde“). U neoříznuté
  // stránky se nic nemění — tam zůstává zaběhnuté fit-na-šířku.
  if (maxH > 0) scale = Math.min(scale, maxH / box.h);
  return {
    frac, box,
    w: Math.max(1, Math.round(box.w * scale)),
    h: Math.max(1, Math.round(box.h * scale)),
    cropPt: {
      x: frac.x * dim.width, y: frac.y * dim.height,
      w: frac.w * dim.width, h: frac.h * dim.height,
    },
  };
}

async function renderCurrent() {
  const doc = song.data;
  if (!doc) return;
  // Čerstvé měření plochy PŘED geometrií: uložená (zastaralá) výška by
  // nechala výřez přerůst displej a spodek by se ořízl.
  computeFit();
  // Nárok na tuto generaci renderu — při rychlém listování se starší render zruší
  const myToken = ++renderToken;
  const page = currentPage.value;
  const dim = await getPageWidthHeight(song, page + 1);
  if (myToken !== renderToken) return; // mezitím se listovalo dál
  // Bitmapa se VŽDY kreslí v NEOTOČENÉM měřítku — rotaci nese jen CSS na
  // `.rotor` a přeškálování na `.stage` (`liveFit`). Otočením se tedy
  // neinvaliduje cache ani nic nepřekresluje.
  const ref = pageReference(dim);
  refW.value = ref.w;
  refH.value = ref.h;
  const frac = await getPageCrop(page);
  if (myToken !== renderToken) return;
  // Rám je aktivní jen když si ho přeje preference (uložené zobrazení má
  // přednost) nebo je zapnutý, A detekce našla skutečný výřez.
  const wantFrame = preferredFrame(page);
  const framed = wantFrame && !(frac.x <= 0.001 && frac.y <= 0.001 && frac.w >= 0.999 && frac.h >= 0.999);
  frameActive = framed;
  pageFramed.value = framed;
  const usedFrac = framed ? frac : { x: 0, y: 0, w: 1, h: 1 };
  // Oříznutá stránka nedostane plnou šířku: 15 px rezervy z každé strany,
  // aby osnovy nebyly nalepené na hraně displeje (Jan).
  const geo = pageGeometry(dim, usedFrac, ref, availW - (framed ? 30 : 0), framed ? availH : 0);
  cropBox.value = geo.box;
  // fitFor počítá měřítko bitmapy vůči těmhle rozměrům (referenční px).
  baseDims.value = { w: geo.box.w, h: geo.box.h };
  cssW.value = geo.w;
  cssH.value = geo.h;
  // Měřítko po rotaci musí odpovídat právě zjištěnému rámu (fitScale se
  // opírá o `frameActive`).
  liveFit.value = fitTargetFor(rot.value);
  await nextTick();
  if (myToken !== renderToken) return;
  // Render vždy do offscreen canvasu, pak zkopírovat na viditelný.
  // Dva souběžné rendery tak nikdy nepíšou do stejného canvasu.
  const cacheKey = keyFor(page);
  const off = getOrCreateCacheCanvas(cacheKey, geo.w, geo.h);
  if (!preRendered.has(cacheKey)) {
    const pending = renderPromises.get(cacheKey);
    if (pending) {
      await pending;
      if (myToken !== renderToken) return;
    } else {
      const p = renderPageRegion(song, page + 1, off, geo.cropPt, geo.w, geo.h).then(() => {
        preRendered.add(cacheKey);
        renderPromises.delete(cacheKey);
      });
      renderPromises.set(cacheKey, p);
      await p;
      if (myToken !== renderToken) return;
    }
  }
  // Zkopírovat offscreen canvas na viditelný (scalovaně podle dpr)
  const ctx = canvasEl.value.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  canvasEl.value.width = Math.round(geo.w * dpr);
  canvasEl.value.height = Math.round(geo.h * dpr);
  canvasEl.value.style.width = geo.w + 'px';
  canvasEl.value.style.height = geo.h + 'px';
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.drawImage(off, 0, 0, canvasEl.value.width, canvasEl.value.height);
  evictCache(page);          // držet jen okno kolem aktuální stránky
  prefetchSiblings(page);
}

// Přednačtení sousedních stránek do offscreen cache, aby listování nečekalo
async function prefetchSiblings(center) {
  const doc = song.data;
  if (!doc) return;
  for (const i of [center - 1, center + 1, center - 2, center + 2]) {
    if (i < 0 || i >= rawPageCount.value) continue;
    const key = keyFor(i);
    if (preRendered.has(key)) continue;
    if (renderPromises.has(key)) continue; // už probíhá
    // Cache canvas musí mít rozměry TÉ stránky (jiný poměr stran → při kopírování by se natáhlo/ořízlo)
    const dim = await getPageWidthHeight(song, i + 1);
    const ref = pageReference(dim);
    const frac = await getPageCrop(i);
    const framed = preferredFrame(i) && !(frac.x <= 0.001 && frac.y <= 0.001 && frac.w >= 0.999 && frac.h >= 0.999);
    const usedFrac = framed ? frac : { x: 0, y: 0, w: 1, h: 1 };
    // Oříznutá stránka nedostane plnou šířku: 15 px rezervy z každé strany,
  // aby osnovy nebyly nalepené na hraně displeje (Jan).
  const geo = pageGeometry(dim, usedFrac, ref, availW - (framed ? 30 : 0), framed ? availH : 0);
    const off = getOrCreateCacheCanvas(key, geo.w, geo.h);
    const p = renderPageRegion(song, i + 1, off, geo.cropPt, geo.w, geo.h).then(() => {
      preRendered.add(key);
      renderPromises.delete(key);
    });
    renderPromises.set(key, p);
  }
}
// Klíč cache = jen stránka. Rotace do klíče NEPATŘÍ — bitmapa je vždy neotočená,
// takže otočení stránky nesmí invalidovat cache (dřív se tu klíčovalo `page@deg`,
// což při každé změně úhlu vyhodilo celou cache a přinutilo překreslit PDF).
function keyFor(pageIdx) { return pageIdx + (preferredFrame(pageIdx) ? '@f' : '@n'); }

function getOrCreateCacheCanvas(i, w, h) {
  if (cached.has(i)) return cached.get(i);
  const c = document.createElement('canvas');
  c.width = Math.round(w);
  c.height = Math.round(h);
  cached.set(i, c);
  return c;
}

// Cache stránek smí držet jen omezený počet offscreen canvasů. Každý je
// plnorozlišťový (A4 na dpr 2 ≈ 2,6 Mpx ≈ 10 MB), takže bez omezení jich
// prohlížeč po prolistování dokumentu drží stovky (měřeno: 47 stránek = 630 MB)
// a aplikace se „čím dál více seká" (Jan). Držíme okno kolem aktuální stránky
// (aktuální ±2 a sousedy pro přednačtení) a starší uvolňujeme — při návratu
// zpět se stránka jen znovu vykreslí, což je levnější než držet gigabajty.
const CACHE_KEEP = 7;   // ±3 stránky od aktuální
function evictCache(center) {
  if (cached.size <= CACHE_KEEP) return;
  const keep = new Set();
  for (let d = -3; d <= 3; d++) {
    const p = center + d;
    if (p >= 0 && p < rawPageCount.value) keep.add(p);
  }
  for (const k of [...cached.keys()]) {
    const page = Number(String(k).split('@')[0]);   // klíč je jen číslo stránky
    if (!keep.has(page)) {
      const c = cached.get(k);
      if (c) { c.width = 0; c.height = 0; }   // uvolnit bitmapu hned, ne až s GC
      cached.delete(k);
      preRendered.delete(k);
      renderPromises.delete(k);
    }
  }
}

function onResize() { syncViewerW(); computeFit(); renderCurrent(); }
// Šířka okna pro výpočet okrajové zóny (--edge-w). Musí se aktualizovat při
// každé změně rozměru, jinak by vizuál zůstal na staré hodnotě.
function syncViewerW() {
  const el = viewerEl.value;
  if (el) viewerW.value = el.clientWidth;
  // Přetažené panely mohou po změně velikosti/otočení displeje skončit mimo
  // obrazovku — vrátit úchyt na dosah (viz rescuePanelOffsets).
  nextTick(rescuePanelOffsets);
}

// Vyčistí viditelný canvas — při přechodu na novou stránku se nezobrazuje stará
function clearCanvas() {
  const c = canvasEl.value;
  if (!c) return;
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, c.width, c.height);
}

// Přesun na stránku (await-ovatelný) — používá se tam, kde na dokončení záleží
// (odebrání stránky, přechod mezi skladbami). `gotoPage` je synchronní varianta
// pro gesta a tlačítka, kde čekat nelze.
async function moveToPage(i) {
  if (i == null || i < 0 || i >= rawPageCount.value) return;
  if (hiddenPages.value.includes(i)) i = nearestVisible(i);
  gotoPage(i);
}
function gotoPage(i, force) {
  if (i < 0 || i >= rawPageCount.value) return;
  // Odebranou stránku přeskoč na nejbližší viditelnou — jinak by zůstal
  // prázdný canvas (stránka se sice vykreslí, ale do listování nepatří).
  if (hiddenPages.value.includes(i)) i = nearestVisible(i);
  if (i === currentPage.value && !force) return;
  endEdit();   // listování = konec výběru prvku (rámeček patří jiné stránce)
  resetGestureState();   // otočení stránky = starý tah/gesto je mrtvé (nedoručí pointerup)
  currentPage.value = i;
  pageSlider.value = visibleIndex.value;
  // Nová stránka má vlastní uložené zobrazení (nebo se použije globální skladby)
  applyPageView();
  updatePageViewFlag();
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
    rotPanelOpen.value = false;
    pagesPanelOpen.value = false; pagesListOpen.value = false;
    endEdit();               // a zrušit výběr prvku (rámeček by zůstal viset)
    pageSlider.value = visibleIndex.value;
    for (let i = Math.max(0, visibleIndex.value - 3); i <= Math.min(visiblePages.value.length - 1, visibleIndex.value + 3); i++) {
      ensureThumb(visiblePages.value[i]);
    }
    // Po vykreslení pásu miniatur posunout na aktuální stránku a zapojit lazy-load
    nextTick(() => {
      const strip = thumbStripEl.value;
      if (strip) {
        scrollThumbIntoView(currentPage.value);
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
// Lazy-load miniatur: načte se, když se miniatura přiblíží do viewportu pásu.
// Pás je virtuální, takže se observer musí znovu zapojit po každé změně okna
// (jinak by se nové prvky nikdy nenačetly).
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
    if (child.dataset.idx != null && !thumbs.has(Number(child.dataset.idx))) {
      thumbObserver.observe(child);
    }
  }
}
function disconnectThumbObserver() {
  if (thumbObserver) { thumbObserver.disconnect(); thumbObserver = null; }
}
// Slidování → živý náhled (hodnota + miniatura), bez navigace.
// Debounce: při rychlém tažení se renderuje jen POSLEDNÍ pozice, ne každá mezilehlá.
// Virtuální pás se při tažení posouvá oknem, takže se musí znovu zapojit observer
// a přednačíst miniatury okna — jinak by přišel prázdný pás.
function onSliderInput(e) {
  const v = Math.round(Number(e.target.value));
  pageSlider.value = v;
  if (thumbDebounce) clearTimeout(thumbDebounce);
  thumbDebounce = setTimeout(() => {
    thumbDebounce = null;
    for (let i = Math.max(0, v - 3); i <= Math.min(visiblePages.value.length - 1, v + 3); i++) {
      ensureThumb(visiblePages.value[i]);
    }
    nextTick(() => {
      const strip = thumbStripEl.value;
      if (strip) { scrollThumbIntoView(v); setupThumbObserver(strip); }
    });
  }, 90);
}
// Puštění slideru → NIKAM neskočit; skok jen kliknutím na miniaturu nebo stránku.
// (slidování jen zvýrazní náhled přes pageSlider)
// Posunout pás miniatur tak, aby byla aktuální miniatura na očích.
// Pás je virtuální → prvek se hledá podle data-idx, ne podle pořadí v DOM.
function scrollThumbIntoView(idx) {
  const strip = thumbStripEl.value;
  if (!strip) return;
  const item = strip.querySelector(`[data-idx="${idx}"]`);
  if (item) item.scrollIntoView({ inline: 'center', block: 'nearest' });
}
// Zajistit miniaturu stránky (render do malého canvasu → dataURL).
// Fronta s omezením souběžnosti — při rychlém tažení sliderem se nespustí
// stovky renderů najednou (to dřív zahltilo paměť a shodilo appku).
function ensureThumb(i) {
  if (i == null || i < 0 || i >= rawPageCount.value) return;
  if (hiddenPages.value.includes(i)) return;   // odebraná stránka miniaturu nemá
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
  // Uvolnit bitmapu miniaturního canvasu hned (drží se jen dataURL) a dát vědět
  // pásu, ať překreslí jen okno — ne celý dokument.
  c.width = 0; c.height = 0;
  thumbTick.value++;
  pruneThumbs(i);
}
// Miniatury držíme jen v okně kolem aktuální stránky — u velkých skladbách by
// dataURL za všechny stránky zbytečně bobtnaly (a každá nová miniatura by
// rozhýbala celý pás).
const THUMB_KEEP = 60;
function pruneThumbs(center) {
  if (thumbs.size <= THUMB_KEEP) return;
  const keep = new Set();
  for (let d = -THUMB_KEEP / 2; d <= THUMB_KEEP / 2; d++) {
    const p = center + d;
    if (p >= 0 && p < rawPageCount.value) keep.add(p);
  }
  for (const k of [...thumbs.keys()]) if (!keep.has(k)) thumbs.delete(k);
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
  // Uložená zobrazení nové skladby (per-stránková i globální) — vycentruje,
  // nastaví zoom, posun i rotaci
  pageViews.clear();
  const pvsNew = await dbGetAllPageViews(s.id);
  for (const pv of pvsNew) if (pv && pv.page != null) pageViews.set(pv.page, pv);
  await applySongView();
  // vyčistit cache a anotace
  cached.clear(); preRendered.clear(); renderPromises.clear();
  thumbs.clear(); thumbPromises.clear(); sliderOpen.value = false; disconnectThumbObserver();
  if (thumbDebounce) { clearTimeout(thumbDebounce); thumbDebounce = null; }
  thumbQueue = [];
  loading.value = true; // loading overlay při přechodu mezi skladbami
  const saved = await dbGetAnnotations(s.id);
  annotations.value.items = (saved && Array.isArray(saved.items)) ? saved.items : [];
  // Staré noty (směr nožičky v klíči) → nový zápis se `flipY` (viz normalizeNoteFlips)
  const norm2 = normalizeNoteFlips();
  // Staré jemné barvy → nová výrazná paleta i při přechodu mezi skladbami
  const upg2 = upgradeAnnotationColors();
  if (norm2 || upg2) {
    await dbSaveAnnotations({ songId: song.id, items: annotations.value.items });
  }
  rawPageCount.value = await getPageCount(song);
  await loadHiddenPages();
  recomputePageOrder();
  currentPage.value = toEnd ? visiblePages.value[visiblePages.value.length - 1] : (visiblePages.value[0] ?? 0);
  // Aplikovat zobrazení až TEĎ, kdy je známá cílová stránka (applySongView výše
  // pracuje s currentPage, který se nastavuje až tady — jinak by se vzalo
  // nastavení předchozí stránky).
  await applyPageView();
  updatePageViewFlag();
  await renderCurrent();
  loading.value = false;
}

// Plynulý přechod: na poslední ZOBRAZENÉ stránce dopředu → další skladba, na první dozadu → předchozí
async function nextPage() {
  const vi = visibleIndex.value;
  if (vi < visiblePages.value.length - 1) {
    await gotoPage(visiblePages.value[vi + 1]);
  } else if (group.value && groupIndex.value < groupSongs.value.length - 1) {
    await switchSong(groupIndex.value + 1);
  }
}
// Tlačítka listování v anotačním režimu: aktivní jen když existuje
// předchozí/další stránka (nebo skladba ve skupině).
const canPrevPage = computed(() =>
  visibleIndex.value > 0 || !!(group.value && groupIndex.value > 0));
const canNextPage = computed(() =>
  visibleIndex.value < visiblePages.value.length - 1 ||
  !!(group.value && groupIndex.value < groupSongs.value.length - 1));

async function prevPage() {
  const vi = visibleIndex.value;
  if (vi > 0) {
    await gotoPage(visiblePages.value[vi - 1]);
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
let _pinch = null;      // stav DVOUPRSTÉHO gesta (zoom + posun): { lastD, lastM }
let _rot3 = null;       // stav TŘÍPRSTÉHO gesta (rotace): { angle0, rot0 }
// GESTA PODLE POČTU PRSTŮ (Jan, Sep 2026) — nahrazuje poměrové rozhodování:
//   2 prsty = zoom + posun   (dělá se pořád, žádné rozhodování podle pohybu)
//   3 prsty = rotace         (jen rotace; měřítko ani posun se nehýbou — rigidní)
// Režim se ale PŘEPÍNÁ podle AKTUÁLNÍHO počtu dotyků, ne jen při začátku gesta —
// jinak každý dotek navíc (opřená dlaň, kloub) gesto natrvalo vypne a zoom
// přestane reagovat, přestože prsty dál táhnou. Viz probe-pinch-robustness.py.
function _mid3(t) {
  return {
    x: (t[0].clientX + t[1].clientX + t[2].clientX) / 3,
    y: (t[0].clientY + t[1].clientY + t[2].clientY) / 3,
  };
}
// Úhel tří prstů: průměr úhlů dvojic (0-1) a (1-2) — stabilnější než jedna dvojice.
function _angle3(t) {
  const a = angleOf(t[0], t[1]);
  const b = angleOf(t[1], t[2]);
  let d = a - b;
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return b + d / 2;
}
// Rozptyl tří prstů (průměrná vzdálenost od těžiště) — z něj měřítko rotace.
function _spread3(t) {
  const m = _mid3(t);
  return (Math.hypot(t[0].clientX - m.x, t[0].clientY - m.y)
        + Math.hypot(t[1].clientX - m.x, t[1].clientY - m.y)
        + Math.hypot(t[2].clientX - m.x, t[2].clientY - m.y)) / 3;
}
// Dva prsty: ZOOM + POSUN (rotace je na třech prstech, prahy ani poměrové
// rozhodování neexistují — počet dotyků je jednoznačný). Tenhle komentář
// nahrazuje starý popis poměrového modelu, který je zrušený:
//   * mrtvý úsek na začátku gesta (prahy 8° / 20 % → 6 snímků bez pohybu)
//   * „cuknutí“ po puštění prstu (liveFit se počítal z úhlu a byl zpožděný rampou)
// Obojí dnes řeší rigidní rotace: rotace nemění měřítko ani posun, takže
// falešné rozhodnutí režimu neublíží (uživatel jen o pár stupňů pootočí).
// Pero právě kreslí / kreslilo = stránku NELISTOVAT (Jan: „anotace se dělají perem“).
// _lastPenAt drží čas posledního tahu perem — chrání i proti zpožděnému touchendu,
// který na reálném tabletu dorazí až po uvolnění pera.
let _lastPenAt = 0;
let _lastTouchStrokeAt = 0;   // prst kreslil na anotační vrstvě → teprve pak smí listovat
let _palmUntil = 0;           // do kdy se nesmí listovat kvůli opřené dlani
const PEN_GUARD_MS = 800;
// Kratší okno pro MRTVÝ TAH: uživatel začal nový tah → ten starý, který nikdy
// nedostal pointerup, je mrtvý už po ~250 ms. Pero, které PRÁVĚ kreslí, píše
// průběžné `pointermove`, takže se tím neuvolní (ověřeno sondou).
const STALE_POINTER_MS = 250;
function blockedNav() {
  _staleGuard();   // mrtvý tah (nedoručený pointerup) nesmí blokovat listování navěky
  if (_activePointerId !== null) return true;
  if (Date.now() - _lastPenAt < PEN_GUARD_MS) return true;
  if (Date.now() - _lastTouchStrokeAt < PEN_GUARD_MS) return true;
  return false;
}
function markPen() { _lastPenAt = Date.now(); }
// Dva prsty (zoom/posun) a tři prsty (rotace) jsou dva režimy JEDNOHO gesta.
// Režim se určuje z AKTUÁLNÍCH dotyků a přepíná se za pochodu — ale OPŘENÁ DLAŇ
// se do počtu nepočítá. Kdyby se počítala, dlaň ležící vedle dvou prstů by
// gesto překlopila do rotace: zoom by přestal hýbat a stránka by se pootočila
// (přesně Janovo „chvíli zoomuje, pak najednou ne“).
function fingersNow(touches) {
  if (!touches) return [];
  return [...touches].filter((t) => !isPalmTouch(t));
}
function onTouchStart(e) {
  // V anotačním režimu se listovat SMÍ, ale JEN prstem na kraji displeje.
  // Rozlišení je na úrovni pointerType (viz onLayerDown), tady rozhoduje jen
  // to, že pero zrovna kreslí nebo kreslilo → dotyk patří opřené ruce.
  if (blockedNav()) { _touchStart = null; _pinch = null; _rot3 = null; return; }
  // Dotyk v notách ozbrojí okno, ve kterém se spolkne náhodné gesto zpět
  // (swipe od okraje displeje) — viz backGuard().
  armBackGuard();
  // Tah na liště záložek (horizontální scroll) nekreslí jako swipe stránky
  if (e.target && e.target.closest && e.target.closest('.bookmark-strip')) return;
  const fs = fingersNow(e.touches);
  const n = fs.length;
  // ---------------------------------------------------------------
  // ZMĚNA POČTU DOTYKŮ BĚHEM GESTA (Jan, Sep 2026)
  // Dřív se stav gesta nastavoval JEN při touchstartu s přesně 2 (nebo 3)
  // dotyky a při jiném počtu se jen zrušil. Na reálném tabletu je ale
  // touchstart častý — opřená dlaň, kloub, druhá ruka, překlepnutí firmwaru —
  // a každý takový dotyk gesto trvale vypnul: zoom se přestal hýbat, i když
  // prsty dál táhly, a uživatel to vidí jako „prsty ztratily kontakt“.
  // Naměřeno (probe-pinch-robustness.py, 800×1280): zoom po takovém dotyku
  // neudělal +0,000 až do konce gesta.
  // Teď se režim jen PŘEPNE podle aktuálního počtu PRSTŮ a stav se vždy znovu
  // založí z AKTUÁLNÍ geometrie, takže gesto navazuje tam, kde papír je.
  // ---------------------------------------------------------------
  if (n >= 3) {
    // TŘI prsty = ROTACE (rigidní — měřítko ani posun se nehýbou).
    // Gesto ZAPNE rotační režim samo (Jan) — mřížka se tak ukáže i tomu, kdo
    // si rotaci vyvolal gestem, ne tlačítkem.
    autoOpenRotMode();
    if (!_rot3) _rot3 = { angle0: _angle3(fs), rot0: rot.value };
    _pinch = null;
    _touchStart = null;
    return;
  }
  if (n === 2) {
    // DVA prsty = ZOOM + POSUN. `lastD`/`lastM` jsou klíčové pro plynulost:
    // kotva se obnoví na AKTUÁLNÍ vzdálenost a střed, takže právě proběhlá
    // změna geometrie (přidání/odebrání dotyku) neudělá zoom skok.
    autoOpenZoomMode();   // gesto dvěma prsty = režim zvětšení a posunu
    const d = dist(fs[0], fs[1]);
    const m = mid(fs[0], fs[1]);
    _pinch = { lastD: d, lastM: m, lastAt: Date.now() };
    _rot3 = null;
    _touchStart = null;
    return;
  }
  if (n === 1) {
    const t = fs[0];
    // Ukládáme i CÍL dotyku — při uvolnění se podle něj pozná, že klepnutí
    // patřilo ovládacímu prvku (anotační panel je v okrajové zóně) a nemá listovat.
    _touchStart = {
      x: t.clientX, y: t.clientY, t: Date.now(), target: e.target,
      palm: false,
      edge: inEdgeZone(t.clientX), // začátek tahu v okrajovém pruhu
    };
  }
  if (n === 0) {
    // Zbyly jen DOTYKY S POLOMĚREM DLANĚ → tohle gesto nesmí dělat nic:
    // ani zoom, ani rotaci, a hlavně NESMÍ LISTOVAT (Jan: „ať to nepřepíná
    // třeba i opřená dlaň“). Dřív se dlaň zahazovala hned tady v touchstartu;
    // když jsem dlaň začala filtrovat z celého gesta, muselo se tohle hlídat
    // zvlášť — jinak dlaň na okraji začala listovat (naměřeno jako regrese).
    if (e.touches && e.touches.length > 0) {
      _palmUntil = Date.now() + 700;
      _touchStart = null;
    }
  }
}
function onTouchMove(e) {
  if (blockedNav()) return;   // pero kreslí → neposouvat ani zoomovat
  const fs = fingersNow(e.touches);
  const n = fs.length;
  if (n >= 3) {
    // TŘI prsty = rotace. Když se třetí PRST objevil až v průběhu gesta, začne
    // se rotace měřit od TEĎ — jinak by dlaň ležící na místě vyrobila úhel
    // z prstu, který se mezitím pohnul, a stránka by cukla.
    if (!_rot3) {
      _rot3 = { angle0: _angle3(fs), rot0: rot.value };
      _pinch = null;
      return;
    }
    // Rotace se bere od ZAČÁTKU rotační fáze (ne po krocích), jinak by se chyba
    // nasčítala a stránka by ujížděla. Rotace je RIGIDNÍ: měřítko ani posun se
    // jí nehýbou, takže papír zůstane přesně tam, kde si ho uživatel nastavil
    // (Jan: „obraz po rotaci zůstane přesně tak, jak je“).
    rot.value = normDeg(_rot3.rot0 + angleDelta(_angle3(fs), _rot3.angle0));
    return;
  }
  if (n === 2) {
    // Když se počet PRSTŮ změnil (z 1 nebo ze 3), stav se tu ZALOŽÍ ZNOVU
    // z aktuální geometrie — gesto tím pokračuje plynule z místa, kde papír je.
    const d = dist(fs[0], fs[1]);
    const m = mid(fs[0], fs[1]);
    if (!_pinch) { _pinch = { lastD: d, lastM: m, lastAt: Date.now() }; _rot3 = null; return; }
    const g = _pinch;
    // DVA prsty = zoom + posun. Žádné rozhodování podle pohybu — zoom i posun
    // se dělají vždy, takže gesto nikdy „neujede“ do jiného režimu.
    if (d !== g.lastD) {
      zoom.value = clampZoom(zoom.value * (d / g.lastD));
      g.lastD = d;
    }
    panX.value += m.x - g.lastM.x;
    panY.value += m.y - g.lastM.y;
    g.lastM = m;
    g.lastAt = Date.now();
    return;
  }
  if (n === 1 && (_pinch === null) && (_rot3 === null)) return;
  // Zbyl jediný PRST. Gesto tím končí (posun jedním prstem záměrně NEEXISTUJE:
  // pere se s okrajovým swipem na listování a s klepnutím na střed, které
  // přepíná ovládání). Důležité ale je, že se stav UKLIDÍ — dřív zůstal viset
  // a další dva prsty se do mrtvého stavu jen „přilepily“, takže zoom nereagoval.
  // Nic se s papírem neděje; jakmile uživatel přiloží dva prsty, touchmove stav
  // znovu zakotví z aktuální geometrie a zoom plynule pokračuje.
  _pinch = null;
  _rot3 = null;
}
// Klepnutí v anotačním režimu patří nástrojům, NIKDY listování — kromě okrajových
// zón, kde listovat chceme.
// Proč: okrajová klepnutí se dřív vyhodnocovala i nad anotačním panelem, který
// sedí v LEVÉ části displeje a je široký (min-width 220 px) → klepnutí na
// tlačítko nástroje (např. tužka) přepnulo i stránku. Proto se ověřuje CÍL
// dotyku: cokoli uvnitř panelu/lišty/tlačítka se nepočítá jako listování.
function isControlTarget(el) {
  if (!el || !el.closest) return false;
  return !!el.closest(
    'button, input, textarea, select, a, label,' +
    '.annot-panel, .top-bar, .zoom-panel, .jump-panel, .edit-bar, .slider-panel,' +
    '.bookmark-strip, .jump-strip, .jump-on-page, .page-go, .text-input-card,' +
    '.wedge-hint, .viewer-loading, .jp-place-hint'
  );
}
// Šířka okrajové zóny pro listování — JEN úzký pruh u okraje displeje.
// Jan: „stránky se přepínají jen prstem, a to jen na krajích displeje.“
// Historie zmenšování (vždy −10 px na tabletu, na mobilu se musel hýbat i podíl,
// jinak by se krok na malém displeji vůbec neprojevil):
//   * 1. kolo: strop 90 → 80 px, podíl 20 % → 15 %  (tablet 80, mobil 58,5)
//   * 2. kolo (nyní, Jan: „ještě o dalších 10 px užší“): strop 80 → 70 px,
//     podíl 15 % → 10 %. Naměřeno: tablet 800 px → 70 px (přesně −10),
//     mobil 390 px → 48 px (bylo 58,5; 10 % z 390 = 39 px, takže se uplatní
//     podlaha EDGE_MIN_PX). Podlaha 48 px zůstává, aby pruh na malém displeji
//     nezmizel úplně.
const EDGE_MAX_PX = 70;   // strop na tabletu
const EDGE_SHARE = 0.10;  // podíl šířky okna
const EDGE_MIN_PX = 48;   // podlaha na malém displeji
function edgeWidth() {
  const el = viewerEl.value;
  if (!el) return EDGE_MAX_PX;
  return Math.max(EDGE_MIN_PX, Math.min(el.clientWidth * EDGE_SHARE, EDGE_MAX_PX));
}
// Okrajová zóna pro ROZHODNUTÍ o listování. Vykreslený pruh (--edge-w) ukazuje
// přesně tuhle šířku, takže co uživatel vidí, je to, kde se listuje.
function inEdgeZone(clientX) {
  const el = viewerEl.value;
  if (!el) return false;
  const r = el.getBoundingClientRect();
  const localX = clientX - r.left;
  return localX < edgeWidth() || localX > r.width - edgeWidth();
}
// Šířka okrajové zóny jako reaktivní hodnota pro vizuál (--edge-w). Musí být
// přesně stejná, jako počítá edgeWidth() — jinak by pruh ukazoval jinou hranu,
// než kde listování opravdu funguje. Zvlášť důležité teď, když je pruh vidět.
// POZOR: čtení `el.clientWidth` NENÍ reaktivní — computed by se vyhodnotil
// jednou a svoje číslo by si držel i po změně velikosti okna (naměřeno: při
// zúžení okna na 390 px zůstal --edge-w na 80 px, zatímco edgeWidth() už
// počítala 58,5 px → vizuál LHAL o 20 px a klepnutí uvnitř pruhu nelistovalo).
// Šířku proto držíme v `viewerW` a aktualizujeme ji při každé změně rozměru.
const viewerW = ref(0);
const edgeW = computed(() => {
  const w = viewerW.value;
  if (!w) return EDGE_MAX_PX;
  return Math.max(EDGE_MIN_PX, Math.min(w * EDGE_SHARE, EDGE_MAX_PX));
});
// Opřená dlaň: dotyk má násobně větší poloměr kontaktu než prst. Takový dotyk
// nikdy nelistuje (Jan: „ať to nepřepíná třeba i opřená dlaň“).
// Prst se hlásí asi 25–35 px, dlaň 60+ px → práh 50 px.
// POZOR: dlaň se musí vyfiltrovat z CELÉHO gesta, ne jen z listování — když se
// počítá jako „třetí prst“, překlopí dvouprstý zoom do rotačního režimu a
// uživatel vidí, že „zoom přestal reagovat a stránka se místo toho pootočila“.
// Naměřeno (probe-pinch-robustness.py): dlaň (r=70) ležící vedle pinche otočila
// stránku o 7,6° a zoom se nehnul o 0,000.
function isPalmTouch(t) {
  const rx = t.radiusX || 0;
  const ry = t.radiusY || 0;
  return Math.max(rx, ry) > 50;
}
function annotEdgeTap(x, y, target) {
  // V anotačním režimu se okrajovým klepnutím NElístuje — kraj patří psaní
  // poznámek. Listuje se dvěma tlačítky (annot-nav).
  if (annotMode.value) return;
  // Klepnutí na ovládací prvek (tlačítko nástroje, panel, lišta) NElístuje
  if (isControlTarget(target)) return;
  if (blockedNav()) return;
  const el = viewerEl.value;
  if (!el) return;
  const r = el.getBoundingClientRect();
  // Vertikálně vynecháme pruh horní lišty (patří ovládání)
  const inTop = y < (r.top + (topBarH.value || 0) + 8);
  if (inTop) return;
  const localX = x - r.left;
  if (localX < edgeWidth()) prevPage();
  else if (localX > r.width - edgeWidth()) nextPage();
}

function onTouchEnd(e) {
  // Gesto se ukončuje, když nezůstane žádný PRST (dlaň se nepočítá). Při
  // PŘECHODNÉM úbytku (jeden ze dvou/tří prstů se zvedl) se stav NERUŠÍ —
  // jinak by pokračující pinch po znovupřiložení prstu neměl na co navázat
  // a zoom by přestal hýbat.
  const fs = fingersNow(e.touches);
  const left = fs.length;
  // Dlaň se musí poznat i na KONCI dotyku: prohlížeč po dotyku vygeneruje
  // kompatibilitní `click`, a ten nese poloměr jen tady. Bez tohohle by dlaň
  // položená na okraji displeje stránku přepnula (naměřeno jako regrese).
  if (e.changedTouches && [...e.changedTouches].some(isPalmTouch)) {
    _palmUntil = Date.now() + 700;
    _pinch = null; _rot3 = null; _touchStart = null;
    return;
  }
  const g = _pinch;
  const r3 = _rot3;
  if (left > 0) {
    if (left >= 3) { _pinch = null; }
    else if (left === 2) { _rot3 = null; _pinch = null; }   // re-anchoring až v touchmove
    else { _pinch = null; _rot3 = null; }
    return;
  }
  _pinch = null;
  _rot3 = null;
  // Tříprstové gesto = rotace: po puštění jen dorovnat cache (během tahu se
  // nevykresluje nic — rotuje se pouze CSS). Zoom ani posun se nedotýkají.
  if (r3) { refreshAfterRotation(true); return; }
  // Dvouprstové gesto: po zoomu/posunu není co dorovnávat, ale cache se dorovná
  // stejnou cestou (drží rozměry canvasu v souladu s oknem).
  if (g) { refreshAfterRotation(true); return; }
  const t = e.changedTouches && e.changedTouches[0];
  const st = _touchStart;
  _touchStart = null;
  // Pero právě kreslí / během tohoto dotyku kreslilo → dotyk patřil opřené ruce
  if (_activePointerId !== null || _penDrewDuringTouch) { _penDrewDuringTouch = false; return; }
  if (!st || !t) return;
  // Opřená dlaň (na začátku i na konci dotyku) NIKDY nelistuje.
  // Dlaň ale nesmí listovat ani přes kompatibilitní `click`, který prohlížeč
  // po dotyku vygeneruje — tam poloměr dotyku k dispozici není, takže si
  // dlaň poznamenáme stranou a onTap se podle toho zahodí.
  if (st.palm || isPalmTouch(t)) { _palmUntil = Date.now() + 700; return; }
  const dx = t.clientX - st.x;
  const dy = t.clientY - st.y;
  const dt = Date.now() - st.t;
  const tapped = Math.abs(dx) < 20 && Math.abs(dy) < 20 && dt < 400;
  const wasAnnot = annotMode.value;
  if (tapped) {
    // V anotaci klepnutí na noty NElístuje. Listuje jen klepnutí, které
    // ZAČALO i SKONČILO v okrajovém pruhu (prst se nepřesunul z kraje doprostřed)
    // a netrefilo ovládací prvek (anotační panel sedí v levém kraji).
    if (wasAnnot && st.edge && inEdgeZone(t.clientX)) {
      annotEdgeTap(t.clientX, t.clientY, st.target);
    } else if (!wasAnnot && !isControlTarget(st.target)) {
      // Ťuknutí prstem na stránku v režimu čtení = režimy gesta (zoom/rotace)
      // končí. Dělá se i tady, ne jen v onTap: na reálném tabletu nemusí
      // kompatibilitní `click` po každém dotyku dorazit (např. hned po
      // tříprstém gestu ho prohlížeč nevygeneruje), takže spoléhat jen na
      // onTap by nechalo mřížku viset na obrazovce.
      closeGesturePanels();
    }
    return; // v režimu čtení tap dál řeší onTap (listování v okrajové zóně)
  }
  // Swipe prstem listuje JEN když začal v okrajovém pruhu (Jan: „jen na krajích displeje“)
  // POZOR: Jan swipe pro listování ZÁMĚRNĚ NECHCE — listuje se jen klepnutím
  // na okraj. Tenhle kus je tu historicky; nesmí ale dělat nic jiného než
  // přesun o stránku, aby se po dotyku na okraj nechovalo nic neočekávaně.
  // V ANOTACI se nelistuje vůbec — kraj patří psaní (listuje se tlačítky).
  if (!wasAnnot && st.edge && Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) {
    if (dx < 0) nextPage(); // swipe vlevo → další stránka/nota
    else prevPage();        // swipe vpravo → předchozí stránka/nota
  }
}
function dist(a, b) {
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
}

// touchcancel = prohlížeč/OS gesto ukončil (na tabletu typicky proto, že si
// systém převzal dotyky — třemi prsty dělá PrintScreen). Dřív appka tenhle
// signál VŮBEC neposlouchala: stav gesta zůstal viset, takže následné dva
// prsty se do starého (mrtvého) stavu jen „přilepily“ a zoom nereagoval.
// Teď se vše uklidí, takže následné dva prsty se chytí čistého stavu.
function onTouchCancel(e) {
  const fs = fingersNow(e && e.touches);
  // Zůstaly-li PRSTY (typicky: OS si vzal tři prsty, dva zůstaly), gesto
  // nekončí — jen se překlopí režim a stav se znovu založí z aktuální
  // geometrie. Kdyby se tu všechno zahodilo, dva zbylé prsty by dál táhly
  // a papír by nereagoval (přesně „prsty ztratily kontakt“).
  if (fs.length > 0) {
    _pinch = null;
    _rot3 = null;
    return;
  }
  _pinch = null;
  _rot3 = null;
  _touchStart = null;
  refreshAfterRotation(true);
}
function mid(a, b) {
  return { x: (a.clientX + b.clientX) / 2, y: (a.clientY + b.clientY) / 2 };
}
// Úhel spojnice dvou prstů (stupně, 0 = vodorovně doprava). Slouží k otáčení
// stránky dvěma prsty — měří se ZMĚNA úhlu proti začátku gesta.
function angleOf(a, b) {
  return Math.atan2(b.clientY - a.clientY, b.clientX - a.clientX) * 180 / Math.PI;
}
// Nejkratší rozdíl dvou úhlů v rozsahu (-180, 180] — aby přechod přes 180°
// (nebo 0°) neudělal skok o 350°.
function angleDelta(now, start) {
  let d = (now - start) % 360;
  if (d > 180) d -= 360;
  if (d <= -180) d += 360;
  return d;
}
function normDeg(v) {
  return ((v % 360) + 360) % 360;
}

// Klepnutí jedním prstem na stránku ZAVŘE režimy, které otevřelo gesto
// (Jan, Oct 2026): „Když po těchto úpravách uživatel jedním prstem ťukne na
// stránku, tak by se tyto módy měly všechny zavřít.“
// Proč zvlášť funkce: zavírá se z VÍCE cest (klepnutí myší/prstem přes onTap,
// tap prstem přes touch cestu) a každá z nich musí uklidit stejně.
function closeGesturePanels() {
  zoomPanelOpen.value = false;
  rotPanelOpen.value = false;
  prefsPanelOpen.value = false;
}

// Tap: okraje → listování (jen mimo anotaci, tlačítka, lištu a formuláře).
// Pero klepnutím NElístuje — listuje se jen prstem (Jan: „anotace se dělají perem,
// stránky se přepínají jen prstem“), a navíc jen v úzkém pruhu u okraje.
function onTap(e) {
  if (annotMode.value) return;
  if (jumpPlaceMode.value) return;   // probíhá umisťování — klepnutí patří vrstvě
  if (e.pointerType === 'pen') return;   // pero nikdy nelistuje
  if (blockedNav()) return;              // právě kreslilo pero → spíš dlaň než prst
  if (Date.now() < _palmUntil) return;   // opřená dlaň — její dotyk právě skončil
  // Plovoucí tlačítka, panely a vstupy necháme bez stránkování (input ve správci záložek
  // by jinak spadl do okrajové zóny a skočil na předchozí stránku).
  if (e.target.closest('button')) return;
  if (e.target.closest('input, textarea, select')) return;
  if (e.target.closest('.top-bar, .jump-panel, .slider-panel, .bookmark-strip, .page-go-backdrop')) return;
  if (e.target.closest('.zoom-panel, .annot-panel, .edit-bar, .jp-list, .page-go')) return;
  // Ťuknutí na stránku (mimo lištu i panely) = režimy gesta končí. Dělá se to
  // PŘED listováním, aby se panel zavřel i při klepnutí v okrajové zóně.
  // Když tap jen zavírá otevřený panel, lišta se NEsundává (jinak by uživatel
  // při zavírání panelu přišel i o lištu, ze které ho otevřel).
  const hadPanel = zoomPanelOpen.value || rotPanelOpen.value || prefsPanelOpen.value
    || pagesPanelOpen.value || sliderOpen.value || jumpMode.value || bookmarkMode.value;
  closeGesturePanels();
  if (hadPanel) return;
  const el = viewerEl.value;
  if (!el) return;
  const localX = e.clientX - el.getBoundingClientRect().left;
  if (localX < edgeWidth()) prevPage();
  else if (localX > el.clientWidth - edgeWidth()) nextPage();
  // Střed = přepínač horní lišty (Jan: schovat a ukázat tapem na střed).
  else toggleTopBar();
}

// Schování/ukázání horní lišty. Noty se při schované liště roztáhnou do
// uvolněného pruhu, proto se po přepnutí znovu spočítá fit a překreslí stránka.
function toggleTopBar() {
  if (annotMode.value || jumpPlaceMode.value) return;   // v anotaci se kreslí
  barHidden.value = !barHidden.value;
  try { localStorage.setItem('topbarHidden', barHidden.value ? '1' : '0'); } catch (e) {}
  if (barHidden.value) {
    // Panely visí na liště — se schovanou lištou by zůstaly bez kontextu.
    zoomPanelOpen.value = false; rotPanelOpen.value = false; prefsPanelOpen.value = false;
    pagesPanelOpen.value = false; pagesListOpen.value = false; sliderOpen.value = false;
    jumpMode.value = false; bookmarkMode.value = false; endEdit();
  }
  // Žádné přepočítávání fitu: lišta je overlay, stránka se nesmí pohnout.
}
function showTopBar() {
  if (!barHidden.value) return;
  barHidden.value = false;
  try { localStorage.setItem('topbarHidden', '0'); } catch (e) {}
}

// --- Anotace ---
function toggleAnnot() {
  annotMode.value = !annotMode.value;
  if (annotMode.value) { jumpMode.value = false; bookmarkMode.value = false; sliderOpen.value = false; zoomPanelOpen.value = false; rotPanelOpen.value = false; pagesPanelOpen.value = false; pagesListOpen.value = false; prefsPanelOpen.value = false; } // jiné panely zavřít
  // vypnutí řeší watch na annotMode níže (pokrývá i cesty, které by na endEdit zapomněly)
}

// POJISTKA: jakmile se anotační režim vypne (jakýmkoli způsobem — FAB, jiný panel,
// přechod skladby…), výběr prvku se zruší. Dřív se endEdit() volal ručně na ~8 místech
// a stačilo jedno opomenutí a rámeček zůstal viset přes celou obrazovku.
watch(annotMode, (on) => {
  if (on) showTopBar();   // v anotaci musí být lišta vidět (východ z režimu)
  if (!on) {
    endEdit();
    // Přerušené umisťování skončí — jinak by zůstal viset režim sběru bodů
    if (jumpPlaceMode.value) { jumpPlaceMode.value = false; jumpPlacePoints.value = []; }
    // Vrstva při vypnutí režimu ztratí `pointer-events` → nedoručí pointerup,
    // takže nedokončený tah by nechal viset `_activePointerId` a ZABIL listování
    // (Jan: „sekne se a pak už listovat nejde“). Proto úklid i tady.
    resetGestureState();
  }
});
// Totéž při změně nástroje: rámeček patří nástroji Ruka, u jiného nástroje nemá co dělat.
watch(tool, () => endEdit());

function setTool(t) {
  endEdit();
  // Přepnutí mezi tužkou a zvýrazňovačem musí přehodit i barvu — palety jsou
  // různé, jinak by zvýrazňovač kreslil černou (a tužka křiklavě žlutou).
  // Index v paletě drží odstín: červená zůstane červená.
  const wasHl = tool.value === 'highlighter';
  const isHl = t === 'highlighter';
  if (wasHl !== isHl) {
    const from = wasHl ? HL_COLORS : PEN_COLORS;
    const to = isHl ? HL_COLORS : PEN_COLORS;
    const i = from.indexOf(annotColor.value);
    if (i >= 0) annotColor.value = to[i];
    else annotColor.value = to[0];
  }
  tool.value = t;
  wedgePoints.value = []; hlPoints.value = []; annotMode.value = true;
  jumpMode.value = false; bookmarkMode.value = false; sliderOpen.value = false; zoomPanelOpen.value = false; rotPanelOpen.value = false;
}

function toLayerCoords(e) {
  // Přes převodní matici SVG (getScreenCTM) — ta zná zoom, posun I ROTACI stage.
  // Dřív se měřilo jen podle poměru šířek, takže na otočené stránce pero kreslilo
  // mimo kurzor (a ruka neuchopila, na co uživatel klepl).
  const clientX = e.touches ? e.touches[0].clientX : e.clientX;
  const clientY = e.touches ? e.touches[0].clientY : e.clientY;
  const svg = layerSvgEl.value;
  const ctm = svg.getScreenCTM();
  if (ctm && typeof DOMPoint !== 'undefined') {
    const p = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  }
  // Záložní cesta (kdyby matice nebyla k dispozici) — bez rotace jako dřív.
  // Souřadnice vrstvy jsou referenční px celé stránky, ne displayed px.
  const rect = svg.getBoundingClientRect();
  const scale = cropBox.value.w / rect.width;
  return {
    x: (clientX - rect.left) * scale,
    y: (clientY - rect.top) * scale,
  };
}

// Kolik stupňů je vrstva natočená na obrazovce (kladně = po směru hodin).
function layerAngleDeg() {
  const svg = layerSvgEl.value;
  if (!svg) return 0;
  const m = svg.getScreenCTM();
  if (!m) return 0;
  return Math.atan2(m.b, m.a) * 180 / Math.PI;
}
// Zvýrazňovač se staví ve souřadnicích OBRAZOVKY (noty jsou tam vodorovně),
// ale ukládá se do souřadnic vrstvy, aby zůstal přilepený k notám. Vrstva je
// vůči obrazovce pootočená o -rot, proto se čtyřúhelník počítá v obrazovém
// rámci a teprve výsledné rohy se převedou zpět do vrstvy.
// Vrací 4 rohy [levý-horní, pravý-horní, pravý-dolní, levý-dolní] ve vrstvě.
function hlCorners(pts) {
  if (pts.length < 3) return null;
  const [a, b, c] = pts;
  // Obrazové souřadnice bodů (cx, cy); když chybí (starý zápis), vezmeme vrstvu
  const ax = a.cx != null ? a.cx : a.x, ay = a.cy != null ? a.cy : a.y;
  const bx = b.cx != null ? b.cx : b.x, by = b.cy != null ? b.cy : b.y;
  const cx = c.cx != null ? c.cx : c.x, cy = c.cy != null ? c.cy : c.y;
  // Body 1+2 určují (vodorovnou) výšku pásu, bod 3 pravý okraj.
  const left = ax;
  const top = Math.min(ay, by);
  const bottom = Math.max(ay, by);
  const right = cx;
  const screen = [
    { x: left, y: top }, { x: right, y: top },
    { x: right, y: bottom }, { x: left, y: bottom },
  ];
  // Převod obraz → vrstva inverzí matice vrstvy
  const svg = layerSvgEl.value;
  const ctm = svg && svg.getScreenCTM();
  if (!ctm || typeof DOMPoint === 'undefined') {
    // bez matice (nemělo by nastat) – vrať aspoň obdélník ve vrstvě
    return [
      { x: a.x, y: Math.min(a.y, b.y) }, { x: c.x, y: Math.min(a.y, b.y) },
      { x: c.x, y: Math.max(a.y, b.y) }, { x: a.x, y: Math.max(a.y, b.y) },
    ];
  }
  const inv = ctm.inverse();
  return screen.map(pt => {
    const q = new DOMPoint(pt.x, pt.y).matrixTransform(inv);
    return { x: q.x, y: q.y };
  });
}
// SVG cesta pro vyplněný čtyřúhelník zvýrazňovače
function hlPathD(it) {
  const p = it.poly;
  if (!p || p.length < 4) return '';
  return 'M' + p.map(q => `${q.x},${q.y}`).join('L') + 'Z';
}
// Střed zvýrazňovače (pro náhled a popisky)
function hlCenter(it) {
  if (it.poly && it.poly.length) {
    const n = it.poly.length;
    return {
      x: it.poly.reduce((s, q) => s + q.x, 0) / n,
      y: it.poly.reduce((s, q) => s + q.y, 0) / n,
    };
  }
  return { x: (it.x1 + it.x2) / 2, y: (it.y1 + it.y2) / 2 };
}

function onLayerDown(e) {
  _logEv('down ' + e.pointerType + ' tool=' + tool.value + ' annot=' + annotMode.value);
  // Umisťování tlačítka skoku: tři klepnutí určují obdélník tlačítka.
  // Musí být PŘED kontrolou annotMode — jinak by klepnutí spadlo do kreslení.
  if (jumpPlaceMode.value) {
    const p2 = toLayerCoords(e);
    jumpPlacePoints.value.push({ x: p2.x, y: p2.y });
    if (jumpPlacePoints.value.length === 3) commitJumpPlace();
    return;
  }
  // POZOR: úklid mrtvého tahu musí být PŘED větví `penOnly`. Když se dělal až
  // za ní, první dotek prstu s mrtvým pointerem zůstal na `penOnly` větvi
  // (return) a teprve DRUHÝ dotek se dostal k úklidu — přesně Jan: „první
  // gesto je ignorováno a tužka začne psát až při druhém doteku“.
  // Okno je KRÁTKÉ (STALE_POINTER_MS), protože uživatel začíná nový tah —
  // pero, které právě kreslí, se tím neuvolní (píše průběžné pointermove).
  _staleGuard(STALE_POINTER_MS);
  if (!annotMode.value) { _logEv('  down: bez anotace'); return; }
  // Pero = kreslení (Jan: „anotace se dělají perem“). Zaznamenáme čas, aby
  // opřená ruka, jejíž touchend dorazí až po tahu perem, neotočila stránku.
  if (e.pointerType === 'pen') markPen();
  // Pen-only mód: dotyk prstem/rukou NEKRESLÍ (palm-rejection) — kreslí jen pero.
  // Listování prstem v anotaci řeší touch obsluha na .viewer (onTouchStart/End),
  // která pozná, že pero zrovna kreslí, přes _activePointerId.
  if (penOnly.value && e.pointerType !== 'pen') { _logEv('  down: penOnly blok'); return; }
  // V ANOTACI se přes okraje LISTUJE TLAČÍTKY, ne klepnutím — kraj tedy patří
  // psaní poznámek i pro prst (Jan: „v anotačním režimu nejsou vidět klikací
  // oblasti, ale poznámky tam psát nejdou“). Dřív se dotyk v okrajovém pruhu
  // zahodil bez toho, aby cokoli udělal.
  // Zaseknutý pointer z tahu, který NIKDY nedostal pointerup (pero odjelo
  // z dosahu tabletu), se pouští UŽ TADY a KRÁTKÝM oknem. `blockedNav()` volá
  // _staleGuard() s dlouhým PEN_GUARD_MS, takže do prvního dotyku prstu byl
  // „ještě živý“ a první dotek se zahodil — Jan: „první gesto je ignorováno
  // a tužka začne psát až při druhém doteku“. Uživatel začal NOVÝ tah, takže
  // ten starý je mrtvý, i když je mu jen 250 ms.
  _staleGuard(STALE_POINTER_MS);
  if (_activePointerId !== null) { _lastDownDbg = 'blok: jiný tah'; return; } // už kreslí jiný tah (např. druhá ruka)
  // Prstem se (s vypnutým „jen pero“) taky kreslí → po takovém tahu chvíli
  // nelistovat, aby dokončení tahu neotočilo stránku.
  if (e.pointerType === 'touch') _lastTouchStrokeAt = Date.now();
  // Pero začíná kreslit. Když v tu chvíli běží dotykový tah (opřená ruka),
  // označíme ho — jeho dokončení NESMÍ otočit stránku (na reálném tabletu
  // může touchend dorazit až po tahu perem).
  if (_touchStart) _penDrewDuringTouch = true;
  _activePointerId = e.pointerId;
  // ČAS STARTU TAHU PRO VŠECHNY NÁSTROJE. `_staleGuard()` posuzuje živý tah
  // podle `_lastLayerAt`, a to se dřív plnilo JEN v `onLayerMove` a v tužkové
  // větvi. U textu/dynamiky/značky se tedy tah, který jen čeká na dialog,
  // tvářil jako mrtvý: první `touchstart` (→ `blockedNav()` → `_staleGuard()`)
  // zavolal `resetGestureState()`, což zahodilo `activeItem` i `_activePointerId`
  // a `pointerup` pak spadl do větve „bez activeItem“ — vstup se vůbec
  // neotevřel (Jan: „při ručním režimu nelze vložit značky ani dynamiku,
  // ani text“). Naměřeno sondou scripts/probe-manual-insert.py.
  _lastLayerAt = Date.now();
  const p = toLayerCoords(e);
  _lastDownDbg = 'start tahu ' + e.pointerType + ' nástroj=' + tool.value;

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
  // POZOR: obdélník se počítá v souřadnicích OBRAZOVKY, ne otočené vrstvy.
  // Vrstva se otáčí s papírem, takže obdélník zarovnaný podle vrstvy je na
  // obrazovce nakloněný o úhel rotace — Jan: „zvýrazňovač se po rotaci chová
  // zvláštně, jak kdyby byl z kopce; měl by být stále naprosto vodorovně."
  // Uživatel klepá body vodorovně se čtečkou, proto se obdélník staví tam
  // a do vrstvy se uloží jako čtyřúhelník (aby zůstal přilepený k notám).
  if (tool.value === 'highlighter') {
    _activePointerId = null;   // guard by jinak zablokoval 2. a 3. klik
    hlPoints.value.push({ x: p.x, y: p.y, cx: e.clientX, cy: e.clientY });
    if (hlPoints.value.length === 3) {
      const corners = hlCorners(hlPoints.value);
      if (corners) {
        const xs = corners.map(c => c.x), ys = corners.map(c => c.y);
        const it = {
          id: crypto.randomUUID(), page: currentPage.value,
          tool: 'highlighter', color: annotColor.value,
          opacity: 1,
          width: Math.max(1, Math.round(annotSize.value)),
          poly: corners,               // čtyřúhelník ve souřadnicích vrstvy
          x1: Math.min(...xs), y1: Math.min(...ys),
          x2: Math.max(...xs), y2: Math.max(...ys),   // bounding box (hledání, guma)
        };
        // POZOR na pořadí: historie se musí uložit PŘED vložením anotace.
        // Dřív to bylo obráceně, takže snapshot už zvýraznění obsahoval a „zpět"
        // nemělo co vrátit — Jan: „je potřeba ho kliknout několikrát, než anotace
        // zmizí. Nebo nezmizí vůbec." Stejné pořadí jako u ostatních nástrojů.
        pushHistory();
        annotations.value.items.push(it);
        saveAnnotations();
      }
      hlPoints.value = [];
    }
    _activePointerId = null;
    _prev = p;
    return;
  }

  // Text / dynamika / značka / nota: umístění na stránku (vytvoří se po uvolnění)
  if (isTextAnnot(tool.value)) {
    // Nová nota začíná NEZRCADLENÁ — zrcadlení je vlastnost jedné noty, ne skladby
    // (na rozdíl od velikosti, ta se pamatuje). Drží to `noteFlipX/Y` z dialogu.
    if (tool.value === 'note') { noteFlipX.value = false; noteFlipY.value = false; }
    activeItem.value = {
      id: crypto.randomUUID(), page: currentPage.value,
      tool: tool.value,
      // Text má vlastní barvu (volenou v dialogu) — pero kreslí jinam, ale barva
      // textu se nastavuje tam, kde i velikost (Jan, Oct 2026).
      color: tool.value === 'text' ? textColor.value : annotColor.value,
      opacity: annotOpacity.value / 100,
      // Text i NOTA si nesou VLASTNÍ velikost (zvolenou před vložením, viz
      // textSize / noteSize); dynamika/značka zůstává na velikosti od voliče tužky.
      // Nota potřebuje vlastní číslo, protože musí sedět na osnovu v notách.
      size: tool.value === 'text' ? textSize.value
          : tool.value === 'note' ? noteSize.value
          : Math.max(14, 20 + annotSize.value * 3),
      // Rámeček kolem textu (hranatý, stejnou barvou, do čtverce) — volba z dialogu.
      border: tool.value === 'text' ? textBorder.value : false,
      borderWidth: tool.value === 'text' ? textBorderWidth.value : undefined,
      borderStyle: tool.value === 'text' ? textBorderStyle.value : undefined,
      // Zrcadlení nese jen nota (viz noteFlipX/Y a toggleFlip).
      flipX: tool.value === 'note' ? noteFlipX.value : undefined,
      flipY: tool.value === 'note' ? noteFlipY.value : undefined,
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
    // Zvýrazňovač už není poloprůhledný ('80') — výraznost řeší sytý odstín
    // + mix-blend-mode: multiply, takže noty pod ním zůstanou čitelné.
    color: annotColor.value,
    opacity: pen ? 1 : annotOpacity.value / 100,
    width: w,
    points: [p],
  };
  _prev = p;
}
// Listování prstem během anotačního režimu zajišťuje touch obsluha .viewer —
// pero kreslí (blokuje swipe přes _activePointerId), prst listuje.
// _penDrewDuringTouch: během dotyku pero kreslilo → dotyk nesmí listovat.
let _penDrewDuringTouch = false;
let _prev = null;
let _activePointerId = null;
let _lastLayerAt = 0;   // čas posledního pohybu na anotační vrstvě (viz _staleGuard)
let _dragAnnot = null;
// Tažení tlačítka skoku po notách (režim Ruka) — aby si uživatel doladil umístění
let _dragJump = null, _dragJumpFrom = null, _dragJumpSnap = null;   // prvek přetahovaný v režimu Upravit (ruka)
let _dragFrom = null;    // výchozí bod přetažení (x,y)
let _dragSnap = null;    // snapshot geometrie prvku na začátku přetažení
// Diagnostický hook pro sondy (window.__navdbg) — JEN ve vývojovém režimu,
// do produkčního bundle se nedostane (import.meta.env.DEV je při buildu false).
// `lastDown`/`lastUp` = kterou větví se klepnutí na vrstvu rozhodlo. Bez toho
// se „klepnutí nic neudělá“ hledá jen čtením kódu (každá větev má vlastní return).
let _lastDownDbg = '', _lastUpDbg = '';
// ÚPLNÝ log rozhodnutí (jen DEV) — „klepnutí nic neudělá“ se jinak hledá čtením
// kódu, protože každá větev má vlastní `return`.
let _evLog = [];
function _logEv(tag) {
  if (!import.meta.env.DEV) return;
  _evLog.push(tag);
  if (_evLog.length > 60) _evLog.shift();
}
if (import.meta.env.DEV && typeof window !== 'undefined') {
  window.__navdbg = () => ({
    activePointerId: _activePointerId,
    penAgo: _lastPenAt ? Date.now() - _lastPenAt : null,
    touchStrokeAgo: _lastTouchStrokeAt ? Date.now() - _lastTouchStrokeAt : null,
    palmIn: _palmUntil ? _palmUntil - Date.now() : null,
    penDrewDuringTouch: _penDrewDuringTouch,
    annotMode: annotMode.value,
    jumpPlaceMode: jumpPlaceMode.value,
    editingId: editingId.value,
    tool: tool.value,
    touchStart: _touchStart ? { edge: _touchStart.edge, age: Date.now() - _touchStart.t } : null,
    annotCount: annotations.value.items.length,
    activeStroke: !!activeItem.value,
    page: currentPage.value,
    lastDown: _lastDownDbg,
    lastUp: _lastUpDbg,
    evLog: _evLog,
    editingAnnotationId: editingAnnotationId.value,
    blocked: (_activePointerId !== null)
      || (Date.now() - _lastPenAt < PEN_GUARD_MS)
      || (Date.now() - _lastTouchStrokeAt < PEN_GUARD_MS),
  });
}
let _eraserHistoryPushed = false; // aby guma uložila history jen jednou za tah

// --- Uklizení stavu gest (listování) --------------------------------------
// PROČ TO EXISTUJE (Jan, Oct 2026: „při anotačním režimu přestane fungovat
// listování stránek. Funguje to, ale po určité době nebo akci se to sekne a pak
// už listovat nejde.“):
//
// `blockedNav()` vypíná listování, dokud je `_activePointerId !== null`.
// Uvolňuje se VÝHRADNĚ v `onLayerUp`, který je navěšený jen na `.annot-layer`
// (`@pointerup` / `@pointercancel`). Ale:
//   * `.annot-layer:not(.active) { pointer-events: none }` → jakmile se vrstva
//     schová (vypnutí anotačního režimu, jiný panel, přechod skladby), `pointerup`
//     na ni NEDORAZÍ a pointer zůstane viset;
//   * totéž při zrušeném tahu (OS si vezme pero, pero opustí obrazovku, dotyk
//     zruší jiný prvek) — vrstva nedostane ani `pointercancel`.
// Naměřeno (scripts/probe-stuck-pointer-proof.py): po jednom nedokončeném tahu
// zůstal `_activePointerId = 4242`, `blocked = true` a listování bylo mrtvé
// natrvalo — dokonce i po vypnutí a znovuzapnutí anotačního režimu.
//
// Řešení: jedna funkce, která stav uklidí, + zapojení na KAŽDOU cestu, kde
// může pero/pointer zmizet. Navíc `_staleGuard()` v `blockedNav()` jako pojistka
// pro cesty, které by na uklizení zapomněly.
function resetGestureState() {
  _activePointerId = null;
  _penDrewDuringTouch = false;
  _touchStart = null;
  _pinch = null;
  _rot3 = null;
  _dragAnnot = null; _dragFrom = null; _dragSnap = null;
  _dragJump = null; _dragJumpFrom = null; _dragJumpSnap = null;
  _prev = null;
  activeItem.value = null;
  _lastLayerAt = 0;
  // POZOR: guardy na ČAS (_lastPenAt, _lastTouchStrokeAt, _palmUntil) se tu
  // záměrně NEnulují — kdyby se nulovaly, opřená ruka se zpožděným touchendem
  // by zase začala listovat (naměřeno jako regrese u dlaňové ochrany).
}
// Mrtvý tah se pozná podle ČASU, ne podle `:hover`.
// POZOR (naměřeno, Jan Oct 2026): `:hover` je na dotykovém zařízení na vrstvě
// PRAVDIVÝ, takže guard „uvolni, jen když není hover“ neuvolnil NIKDY a listování
// bylo mrtvé od prvního dotyku. Proto se aktivní pointer posuzuje oknem: dokud
// od poslední události na vrstvě uplynulo méně než PEN_GUARD_MS, tah žije;
// jinak je to mrtvý tah (nedoručený pointerup) a uvolní se.
function _staleGuard(maxAge = PEN_GUARD_MS) {
  if (_activePointerId === null) return;
  if (Date.now() - _lastLayerAt < maxAge) return;   // tah se nedávno hýbal → žije
  resetGestureState();
}

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
  _lastLayerAt = Date.now();   // viz _staleGuard — živý tah se pozná podle pohybu
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
    if (isTextAnnot(it)) {
      it.x = s.x + dx; it.y = s.y + dy;
    } else if (isStroke(it)) {
      it.points = s.points.map(pt => ({ x: pt.x + dx, y: pt.y + dy }));
    } else if (it.tool === 'crescendo' || it.tool === 'decrescendo') {
      it.x1 = s.x1 + dx; it.y1 = s.y1 + dy;
      it.x2 = s.x2 + dx; it.y2 = s.y2 + dy;
      it.x3 = s.x3 + dx; it.y3 = s.y3 + dy;
    } else if (it.tool === 'highlighter') {
      // Čtyřúhelník zvýrazňovače se posouvá celý (i jeho bounding box)
      if (it.poly) it.poly = s.poly.map(q => ({ x: q.x + dx, y: q.y + dy }));
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
  // Text / dynamika / značka / nota: jen sledovat, dokud neuvolníme (pozice se nastaví na up)
  if (isTextAnnot(tool.value)) {
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
  _logEv('up ' + (e && e.pointerType) + ' activePtr=' + _activePointerId + ' item=' + !!activeItem.value);
  // Pero ukončilo tah → drž krátký ochranný interval, po který dotyk
  // (opřená ruka se zpožděným touchendem) nesmí otočit stránku.
  if (e && e.pointerType === 'pen') markPen();
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
  // Pozor: `activeItem` může být mezitím prázdný (dialog textu/značky už tah
  // uzavřel) — pointer se ale musí uvolnit VŽDY, jinak visí `_activePointerId`
  // a `blockedNav()` zabije listování (Jan: „listování nefunguje vůbec“).
  if (!activeItem.value) {
    _logEv('  up: bez activeItem');
    if (_activePointerId === e.pointerId) { _activePointerId = null; _prev = null; _lastUpDbg = 'bez activeItem'; }
    return;
  }
  if (_activePointerId === null) { _logEv('  up: nic neběží'); return; }
  if (_activePointerId !== e.pointerId) { _logEv('  up: jiný pointer'); _lastUpDbg = 'ignorováno: jiný pointer'; return; }
  _activePointerId = null;
  const it = activeItem.value;

  // Guma: okamžité mazání už běží v onLayerMove; tady jen ukončíme tah
  if (tool.value === 'eraser') {
    _logEv('  up: guma');
    activeItem.value = null;
    _activePointerId = null;
    _prev = null;
    _eraserHistoryPushed = false;   // reset pro další gumovací tah
    return;
  }

  // Text / dynamika / značka / nota: místo uvolnění → otevřít dialog (pending)
  if (isTextAnnot(tool.value)) {
    _logEv('  up: otevírám vstup ' + tool.value);
    it.pending = true;
    editingAnnotationId.value = it.id;
    _lastUpDbg = 'otevírám vstup pro ' + tool.value;
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
    endEdit();   // vybraný prvek mohl být na této stránce — pás úprav nesmí zůstat viset
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
// POZOR: je `async` kvůli `await nextTick()` ve větvi „Uložit a ruka“ —
// bez toho by `watch(tool)` smazal právě nastavený výběr (viz níže).
async function confirmTextAnnot(withHand = false) {
  const id = editingAnnotationId.value;
  if (!id) return;
  const it = annotations.value.items.find(x => x.id === id) || activeItem.value;
  if (it) {
    it.text = annotTextDraft.value.trim();
    // Velikost + barva + rámeček zvolené v dialogu PŘED vložením; volby se pamatují.
    if (it.tool === 'text') {
      textSize.value = clampTextSize(textSizeDraft.value);
      it.size = textSize.value;
      textColor.value = textColorDraft.value;
      it.color = textColor.value;
      textBorder.value = textBorderDraft.value;
      it.border = textBorder.value;
      textBorderWidth.value = textBorderWidthDraft.value;
      it.borderWidth = textBorderWidth.value;
      textBorderStyle.value = textBorderStyleDraft.value;
      it.borderStyle = textBorderStyle.value;
      saveTextSize();
      saveTextStyle();
      nextTick(() => measureTexts());   // skutečná šířka textu pro rám (viz textMetrics)
    }
    if (it.tool === 'note') {
      // Neznámý klíč by vložil PRÁZDNÝ glyf (a v notách by po něm zůstalo jen
      // prázdné místo) — radši nic neukládej a nech uživatele vybrat z nabídky.
      if (!noteGlyph(it.text).known) return;
      noteSize.value = clampNoteSize(noteSizeDraft.value);
      it.size = noteSize.value;
      it.flipX = noteFlipX.value;
      it.flipY = noteFlipY.value;
      saveNoteSize();
    }
  }
  if (!annotations.value.items.includes(it)) {
    pushHistory();
    annotations.value.items.push(it);
  }
  activeItem.value = null;
  editingAnnotationId.value = null;
  annotTextDraft.value = '';
  saveAnnotations();
  // „Uložit a ruka“ — nástroj se přepne na ruku a vložený prvek se ROVNOU vybere,
  // takže uživatel s ním hned hýbe (posun prstem/perem, velikost v pásu úprav)
  // a nemusí přepínat nástroj a znovu na prvek klepat.
  if (withHand && it) {
    const keep = it.id;
    setTool('edit');
    // POZOR: `setTool` sám volá `endEdit()` a navíc `watch(tool, () => endEdit())`
    // doběhne až po tomto bloku — nastavit `editingId` hned by ten watch smazal
    // (naměřeno: rámeček ani pás úprav se neobjevily). Proto až po nextTick.
    await nextTick();
    if (annotations.value.items.some(x => x.id === keep)) editingId.value = keep;
  }
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

// Jan: „Ke vkládání textu bych přidal možnost dát hranatý Border. Ve stejné
// barvě jako text. Do čtverce." a pak: „Text teď není v rámečku vycentrovaný.
// A velikost a styl rámečku by měl být taky na výběr."
//
// ⚠️ PŮVODNÍ CHYBA: rámeček se počítal z ODHADU (šířka = počet znaků × 0,62 em,
// výška = (0,78 + 0,24) em). Skutečné vykreslení se liší — naměřeno u systémového
// písma: výška písma 12 px místo 12,24 px a šířka znaku 0,553 em místo 0,62 em,
// takže text seděl ~3,8 px VLEVO od středu rámečku. Jan to poznal okamžitě.
// Měření prohlížeče (getComputedTextLength + výška písma z canvasu) je proto
// ZDROJ PRAVDY; odhad slouží jen jako záloha pro první vykreslení po startu.
const TEXT_BORDER_PAD = 6;      // výchozí odstup textu od rámečku (px v souřadnicích vrstvy)
const TEXT_LINE_DESC = 0.24;    // místo pod účařím (hloubka minusek) v em — ZÁLOHA
const TEXT_LINE_ASC  = 0.78;    // výška nad účařím (velká písmena) v em — ZÁLOHA
const TEXT_ADV_EM    = 0.62;    // odhad šířky znaku v em — ZÁLOHA (jen pro první kreslení)
// Na výběr: odstup textu od rámu a styl čáry. Rám se jinak zvětšuje sám podle
// textu — kdyby měl pevný rozměr, delší text by z něj přetekl.
const TEXT_BORDER_WIDTHS = [4, 6, 8, 12, 16];
const TEXT_BORDER_STYLES = [
  { key: 'solid',  label: 'Plná' },
  { key: 'dashed', label: 'Čárky' },
  { key: 'dotted', label: 'Tečky' },
  { key: 'double', label: 'Dvojitá' },
];
// Styl rámu → atributy <rect>. „Dvojitá“ = dvě soustředné linky (SVG na dvojitou
// čáru vlastní atribut nemá, takže se kreslí dvěma obdélníky).
const TEXT_STYLE_MAP = {
  solid:  { dash: null,       double: false },
  dashed: { dash: '7 5',      double: false },
  dotted: { dash: '1.5 4',    double: false },
  double: { dash: null,       double: true  },
};
const textProbeEls = ref([]);   // skryté <text> pro měření (viz measurableTexts)

function textBorderWidthOf(it) {
  const w = it.borderWidth;
  return (typeof w === 'number' && w > 0) ? w : TEXT_BORDER_PAD;
}
function textBorderStyleOf(it) {
  return TEXT_STYLE_MAP[it.borderStyle] ? it.borderStyle : 'solid';
}
// Skutečná šířka a výška textu z prohlížeče, klíčované podle id prvku.
// getComputedTextLength() dá PŘESNĚ to, co prohlížeč vykreslí (včetně kerningu),
// a výška písma se měří přes canvas — v prohlížeči je jinak nedostupná.
const textMetrics = ref({});
function measureTexts() {
  const els = textProbeEls.value || [];
  for (const el of els) {
    if (!el || !el.id) continue;
    const size = Number(el.getAttribute('font-size')) || el.getBoundingClientRect().height || 20;
    const txt = el.textContent || '';
    let w = 0;
    try { w = el.getComputedTextLength(); } catch (e) { w = 0; }
    if (!w) w = Math.max(size, txt.length * size * TEXT_ADV_EM);
    const ink = _inkMetrics(txt, size);
    textMetrics.value[el.id] = { w, size, inkAsc: ink.asc, inkDesc: ink.desc };
  }
}
// ⚠️ Svisle se centruje podle SKUTEČNÉHO OTISKU PÍSMEN, ne podle boxu písma.
// Rozdíl je vidět: text bez descendentů („noty“ má jen vzestupnice) má otisk
// jen po účaří, takže zarovnání podle font-boxu ho posune o ~3 px nad střed
// (naměřeno dy = −3,03 px). Oko hodnotí otisk, proto je otisk zdrojem pravdy.
// `actualBoundingBox*` z canvasu dává přesně hranice vykreslených znaků.
function _inkMetrics(text, size) {
  const fallback = { asc: size * TEXT_LINE_ASC, desc: size * TEXT_LINE_DESC };
  try {
    const c = _fontHeightCache.ctx
      || (_fontHeightCache.ctx = document.createElement('canvas').getContext('2d'));
    c.font = size + 'px system-ui, sans-serif';
    // Prázdný/nedostupný text → měř velké písmeno, ať je z čeho počítat.
    const m = c.measureText(text || 'H');
    if (m.actualBoundingBoxAscent) {
      return { asc: m.actualBoundingBoxAscent, desc: Math.max(0, m.actualBoundingBoxDescent) };
    }
  } catch (e) { /* zůstane záloha */ }
  return fallback;
}
const _fontHeightCache = new Map();
function _fontHeight(size) {
  const key = Math.round(size * 10);
  if (_fontHeightCache.has(key)) return _fontHeightCache.get(key);
  const h = _inkMetrics('H', size).asc;    // výška velkého písmene = vizuální výška písma
  _fontHeightCache.set(key, h);
  return h;
}
// Zjisti, které prvky potřebuje proměřit (uložené texty na stránce + náhled
// aktivního textu) a po vykreslení zavolej měření. Hlídej i pozdější změny
// velikosti — proto se proměřuje i v pásu úprav (viz resizeAnnot).
// ⚠️ `immediate: true` tu NESMÍ být: při setupu ještě `textMetrics` neexistuje
// (je deklarovaný níž) a přístup na něj shodí celý komponent na TDZ chybě —
// projevilo se to jako „stránka se vůbec nevykreslí“ (timeout v sondě).
const measurableTexts = computed(() => {
  const out = pageItems.value.filter(isText);
  const active = activeItem.value;
  if (active && isText(active)) out.push(active);
  return out;
});
watch(measurableTexts, () => {
  nextTick(() => measureTexts());
}, { deep: true });

// Kolik místa si text vyžádá (bez okraje rámečku). Jeden zdroj pravdy pro
// vykreslení rámečku i pro hit-test rukou — jinak by se rám a klikatelná
// plocha rozešly (Jan to pozná: „chytím to jen někde").
function textExtents(it) {
  const s = it.size || 20;
  const m = textMetrics.value[it.id];
  const w = (m && m.w) || (it.text ? Math.max(s, it.text.length * s * TEXT_ADV_EM) : s);
  // Svisle se vychází z OTISKU PÍSMEN (viz _inkMetrics) — zarovnání podle boxu
  // písma posouvalo text o ~3 px nad střed rámu (naměřeno dy = −3,03 px).
  // Bez měření je záloha stejně velká jako dřívější odhad, takže se do té doby
  // nic nerozbije (první vykreslení po startu).
  const inkAsc  = (m && m.inkAsc)  != null ? m.inkAsc  : s * TEXT_LINE_ASC;
  const inkDesc = (m && m.inkDesc) != null ? m.inkDesc : s * TEXT_LINE_DESC;
  const h = inkAsc + inkDesc;
  // Účaří je v `it.y`; horní hrana otisku je nad ním o `inkAsc`.
  return { x: it.x, y: it.y - inkAsc, w, h };
}
// Čtvercový rám: hrana = max(šířka, výška) + okraje na obou stranách; středem se
// drží text, aby byl rám kolem něj vždycky stejně „obalený".
function textBorderBox(it) {
  const e = textExtents(it);
  const pad = textBorderWidthOf(it);
  const side = Math.max(e.w, e.h) + pad * 2;
  return {
    x: e.x + e.w / 2 - side / 2,
    y: e.y + e.h / 2 - side / 2,
    w: side, h: side,
  };
}
// Atributy <rect> pro Vue — rámeček kreslí stejnou barvou jako text a nese
// zvolený styl čáry (čárky / tečky / dvojitá).
function textBorderRects(it) {
  const b = textBorderBox(it);
  const st = TEXT_STYLE_MAP[textBorderStyleOf(it)];
  if (st.double) {
    // „Dvojitá“ = dvě soustředné linky; SVG vlastní atribut pro dvojitou čáru nemá.
    const gap = 2.5;
    return [
      { key: 'o', x: b.x, y: b.y, width: b.w, height: b.h, dash: null },
      { key: 'i', x: b.x + gap, y: b.y + gap,
        width: Math.max(1, b.w - gap * 2), height: Math.max(1, b.h - gap * 2), dash: null },
    ];
  }
  return [{ key: 'o', x: b.x, y: b.y, width: b.w, height: b.h, dash: st.dash }];
}

// --- Režim "Upravit" — výběr, přetažení, změna velikosti textu/dynamiky ---
// Vrátí ohraničující box prvku (plocha, kam lze kliknout pro výběr rukou), nebo null
function itemBox(it) {
  let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
  const pad = 10;
  if (isTextAnnot(it)) {
    if (it.x == null || it.y == null) return null;
    if (it.tool === 'note') {
      // Nota: hit-test ze STEJNÝCH obrysových mezí glyfu jako rámeček (noteInkBox).
      const b = noteInkBox(it);
      if (!b) return null;
      return { x: b.x - pad, y: b.y - pad, w: b.w + pad * 2, h: b.h + pad * 2 };
    }
    if (it.tool === 'text') {
      // Rámeček se počítá JEDNOU funkcí pro vykreslení, výběr rukou i hit-test.
      const r = textBorderBox(it);
      return { x: r.x - pad, y: r.y - pad, w: r.w + pad * 2, h: r.h + pad * 2 };
    }
    const s = it.size || 20;
    x1 = it.x; y1 = it.y - s;
    // Dynamika/značka = šířka glyfu z metrik fontu; text = odhad podle znaků
    let w;
    if (it.tool === 'dynamic') w = dynAdvEm(it.text) * s;
    else if (it.tool === 'mark') w = markAdvEm(it.text) * s;
    else w = it.text ? Math.max(s, it.text.length * s * 0.6) : s;
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
    if (it.poly && it.poly.length) {
      // čtyřúhelník: box z jeho skutečných rohů (x1/x2 je jen hrubý bounding box)
      for (const q of it.poly) {
        if (q.x < x1) x1 = q.x; if (q.y < y1) y1 = q.y;
        if (q.x > x2) x2 = q.x; if (q.y > y2) y2 = q.y;
      }
    } else {
      if (it.x1 == null) return null;
      x1 = Math.min(it.x1, it.x2); x2 = Math.max(it.x1, it.x2);
      y1 = Math.min(it.y1, it.y2); y2 = Math.max(it.y1, it.y2);
    }
  } else {
    return null;
  }
  return { x: x1 - pad, y: y1 - pad, w: (x2 - x1) + pad * 2, h: (y2 - y1) + pad * 2 };
}
// Skok, jehož obdélník je pod daným bodem (pro tažení i pro klepnutí)
function jumpAtPoint(p) {
  for (const j of jumps.value) {
    const b = j.place;
    if (!b) continue;
    // Obdélník se kreslí na stránce, na které ho uživatel naklepal (b.page).
    // Dřív se tu porovnávalo j.fromPage — jenže umístění se dá naklepat i na
    // JINÉ stránce, než odkud skok vede (typicky dopředu na stránce, kde má
    // být tlačítko). Pak tlačítko bylo vidět, ale ruka ho nemohla uchopit.
    const onPage = (b.page != null) ? b.page : j.fromPage;
    if (onPage !== currentPage.value) continue;
    if (p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h) return { j };
  }
  return null;
}
// Skoky na aktuální stránce rozdělené podle toho, zda mají umístění na notách
const jumpsOnPage = computed(() => jumps.value.filter(j =>
  j.fromPage === currentPage.value
  || (j.place && (j.place.page != null ? j.place.page : j.fromPage) === currentPage.value)
));
const placerJumps = computed(() => jumpsOnPage.value.filter(j => j.place));
const edgeJumps = computed(() => jumpsOnPage.value.filter(j => !j.place));
// Styl obdélníku tlačítka na stránce (v souřadnicích anotační vrstvy = CSS px)
function jumpBoxStyle(j) {
  const b = j.place;
  if (!b) return {};
  // Souřadnice skoku jsou v REFERENČNÍ soustavě celé stránky (jako anotace),
  // zobrazení je ale jen výřez cropBox → převést do displejových px.
  const s = cssW.value / (cropBox.value.w || 1);
  return {
    left: (b.x - cropBox.value.x) * s + 'px',
    top: (b.y - cropBox.value.y) * s + 'px',
    width: b.w * s + 'px', height: b.h * s + 'px',
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
  // Do dialogu se načte SOUČASNÁ velikost prvku — jinak by přepsání textu
  // rukou tiše přehodilo velikost na tu, co měl uživatel nastavenou pro nový text.
  if (it.tool === 'text') {
    textSizeDraft.value = clampTextSize(it.size || 20);
    // Totéž pro barvu a rámeček — dialog musí ukazovat, jak prvek VYPADÁ TEĎ,
    // ne jak je nastavený „další text“.
    textColorDraft.value = it.color || textColor.value;
    textBorderDraft.value = !!it.border;
    textBorderWidthDraft.value = textBorderWidthOf(it);
    textBorderStyleDraft.value = textBorderStyleOf(it);
  }
  // Stejná logika pro OTEVŘENÍ dialogu klepnutím na noty (pero i prst): dialog
  // musí ukazovat velikost, se kterou se prvek skutečně kreslí (viz itemBox —
  // text má vlastní `size`, ne hodnotu z voliče tužky).
  // Nota: dialog musí ukázat velikost TOHOTO prvku, ne tu připravenou pro novou
  // notu — jinak by přepsání noty rukou tiše přehodilo velikost.
  if (it.tool === 'note') {
    noteSizeDraft.value = clampNoteSize(it.size || noteSize.value);
    noteFlipX.value = !!it.flipX;
    noteFlipY.value = !!it.flipY;
  }
  editingTextSize.value = it.tool === 'text' ? clampTextSize(it.size || 20) : null;
  editingAnnotationId.value = it.id;
  // Aktivní (ještě nevložený) prvek: dialog otevírá sám textSizeDraft.
}
function resizeAnnot(it, dir) {
  if (!it) return;
  // Stejný krok jako v dialogu před vložením — Jan: velikost se musí měnit
  // KONZISTENTNĚ. Dřív tu byl pevný krok 4, takže stejná akce („+“) ubírala jinde
  // jiný počet bodů než v dialogu. Noty mají vlastní krok (NOTE_SIZE_STEP = 1 px),
  // protože se musí trefit do velikosti osnovy; text zůstává na 3 px.
  const step = it.tool === 'note' ? NOTE_SIZE_STEP : TEXT_SIZE_STEP;
  it.size = clampTextSize((it.size || 20) + dir * step);
  saveAnnotations();
  // Rámeček se počítá ze SKUTEČNÉ šířky textu — po změně velikosti se musí přeměřit,
  // jinak by rám u nové velikosti neseděl (viz textMetrics).
  nextTick(() => measureTexts());
}
// Rámeček u už vloženého textu — ať se dá zapnout i zpět, bez mazání a vkládání znovu.
// Bere i šířku a styl rámu; volba se propíše do „dalšího textu“ (jako velikost).
function toggleTextBorder(it) {
  if (!it) return;
  it.border = !it.border;
  textBorder.value = it.border;
  textBorderDraft.value = it.border;
  if (it.border) {
    // Prvek může mít rámeček z dřívějška bez volby šířky/stylu — doplň z dialogu.
    it.borderWidth = it.borderWidth || textBorderWidth.value;
    it.borderStyle = it.borderStyle || textBorderStyle.value;
  }
  saveTextStyle();
  saveAnnotations();
}
// Změna šířky / stylu rámu u VLOŽENÉHO textu (pás úprav).
function setTextBorderWidth(it, w) {
  if (!it) return;
  it.borderWidth = w;
  textBorderWidth.value = w;
  textBorderWidthDraft.value = w;
  saveTextStyle();
  saveAnnotations();
}
function setTextBorderStyle(it, key) {
  if (!it || !TEXT_STYLE_MAP[key]) return;
  it.borderStyle = key;
  textBorderStyle.value = key;
  textBorderStyleDraft.value = key;
  saveTextStyle();
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
    // Text s rámečkem: guma musí brát i JEHO HRANY — u velkého čtverce by se
    // jinak muselo trefit přesně na střed textu, což je pro uživatele hádanka.
    if (it.tool === 'text' && it.border) {
      const b = textBorderBox(it);
      const corners = [
        { x: b.x, y: b.y }, { x: b.x + b.w, y: b.y },
        { x: b.x + b.w, y: b.y + b.h }, { x: b.x, y: b.y + b.h }, { x: b.x, y: b.y },
      ];
      for (const pt of pts) {
        for (let i = 0; i < corners.length - 1; i++) {
          if (distToSeg(pt.x, pt.y, corners[i].x, corners[i].y, corners[i + 1].x, corners[i + 1].y) < w) return true;
        }
      }
    }
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
  if (it.tool === 'highlighter' && (it.poly || it.x1 != null)) {
    // zvýrazňovač = čtyřúhelník/obdélník: smaže se, když guma protne jeho plochu
    const fineSeg = fine;
    if (it.poly && it.poly.length >= 3) {
      // protne guma mnohoúhelník? (test hran + bod uvnitř)
      for (let j = 0; j < fineSeg.length - 1; j++) {
        const a = fineSeg[j], b = fineSeg[j + 1];
        for (let k = 0; k < it.poly.length; k++) {
          const p1 = it.poly[k], p2 = it.poly[(k + 1) % it.poly.length];
          if (distSegSeg(a.x, a.y, b.x, b.y, p1.x, p1.y, p2.x, p2.y) < 1.5) return true;
        }
      }
      // guma začala uvnitř pásu
      const c = hlCenter(it);
      return distToPoly(c.x, c.y, fineSeg) < 12;
    }
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
// ZOOM_MIN = 0,25 → stránku lze oddálit POD 100 % (Jan: „abych mohl oddálit
// stránku, když je originál moc velký“). 100 % zůstává výchozí stav (fit na šířku).
const ZOOM_MIN = 0.25;
const ZOOM_MAX = 2.5;
function clampZoom(v) {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(v * 100) / 100));
}
function zoomIn() { zoom.value = clampZoom(zoom.value + 0.05); }
function zoomOut() { zoom.value = clampZoom(zoom.value - 0.05); }
function zoomInBig() { zoom.value = clampZoom(zoom.value + 0.10); }
function zoomOutBig() { zoom.value = clampZoom(zoom.value - 0.10); }
// Zpět na 100 % = výchozí fit na šířku (bez posunu a rotace).
function zoomFit() { zoom.value = 1.0; panX.value = 0; panY.value = 0; }
// Vycentrovat = vrátit se na uložené výchozí zobrazení; uložené nastavení
// KONKRÉTNÍ stránky má přednost před globálním nastavením skladby.
// Ruční vycentrování zároveň VYPNE automatický rám — jinak by tlačítko
// „nešlo přemazat“ (stránka by zůstala oříznutá a zbytečně malá).
function resetView() { applyPageView(); }

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

// --- PŘETAHOVÁNÍ PANELŮ (Jan, Oct 2026) -----------------------------------
// „Přidáme možnost Drag And drop ke všem dropdown oknům v menu." Panely se
// kotví pod horní lištu a na malém displeji zakrývají noty, proto si je
// uživatel může odtáhnout. Posun se pamatuje (localStorage), aby panel zůstal
// tam, kam si ho kdo dal — a klepnutí na úchyt (bez tažení) ho vrátí zpátky,
// jinak by se odtažený panel nedal rozumně vrátit.
const PANEL_POS_KEY = 'noty-panel-pos';
const panelOffsets = ref({});   // { jméno panelu: { x, y } }
let _panelDrag = null;
let _panelMoved = 0;
const PANEL_SNAP_PX = 6;        // pod tuhle vzdálenost je to klepnutí, ne tažení
function loadPanelOffsets() {
  try {
    const raw = localStorage.getItem(PANEL_POS_KEY);
    panelOffsets.value = raw ? (JSON.parse(raw) || {}) : {};
  } catch (e) { panelOffsets.value = {}; }
}
function savePanelOffsets() {
  try { localStorage.setItem(PANEL_POS_KEY, JSON.stringify(panelOffsets.value)); } catch (e) { /* nevadí */ }
}
// Posun panelu jde přes CSS proměnné — transform panelů zůstává v CSS, protože
// ho potřebuje centrování (.zoom-panel je na středu lišty přes translateX(-50%)).
function panelStyle(name) {
  const o = panelOffsets.value[name];
  return { '--pd-x': (o ? o.x : 0) + 'px', '--pd-y': (o ? o.y : 0) + 'px' };
}
// Gesto patří panelu, ne listování stránek: `.viewer` poslouchá dotyky PASIVNĚ,
// takže tah po úchytu by jinak zároveň obracel stránky (stejná pojistka jako
// u přetahování záložek — touch-action: none na úchytu + stop u pointerdown).
// Záchrana pozic: když panel po uložené pozici vyjede mimo displej (změna
// orientace, jiná velikost okna, pozice z doby před omezením tahu), vrátíme
// posun tak, aby úchyt zůstal na displeji. Úchyt je jediná cesta, jak panel
// dostat klepnutím zpět na výchozí místo — mimo displej by se ztratil.
function rescuePanelOffsets() {
  const M = 8;
  const out = { ...panelOffsets.value };
  let changed = false;
  for (const name of Object.keys(out)) {
    const grip = document.querySelector('[data-panel="' + name + '"] .panel-grip');
    if (!grip) continue;   // panel zrovna není otevřený, nemá co měřit
    const r = grip.getBoundingClientRect();
    const o = out[name] || { x: 0, y: 0 };
    let dx = 0, dy = 0;
    if (r.left < 0) dx = -r.left + M;
    else if (r.right > window.innerWidth) dx = window.innerWidth - M - r.right;
    if (r.top < 0) dy = -r.top + M;
    else if (r.bottom > window.innerHeight) dy = window.innerHeight - M - r.bottom;
    if (dx || dy) { out[name] = { x: o.x + dx, y: o.y + dy }; changed = true; }
  }
  if (changed) { panelOffsets.value = out; savePanelOffsets(); }
}
// Otevření kteréhokoli panelu zkontroluje, že jeho úchyt je na displeji.
watch([zoomPanelOpen, rotPanelOpen, pagesPanelOpen, jumpMode, bookmarkMode, annotMode],
  () => { nextTick(rescuePanelOffsets); });

function panelDragStart(e, name) {
  e.stopPropagation();
  const o = panelOffsets.value[name] || { x: 0, y: 0 };
  _panelMoved = 0;
  // Rozměry úchytu v době uchopení — podle nich se tah OMEZÍ (clamp) tak, aby
  // úchyt zůstal na displeji. Bez toho se panel dá odtáhnout mimo obrazovku
  // a úchyt (jediná cesta k vrácení klepnutím) zmizí — naměřeno: panel na
  // x = −74 px a úchyt mimo displej, takže se nedal vrátit.
  const gr = e.currentTarget.getBoundingClientRect();
  _panelDrag = {
    name, x0: e.clientX, y0: e.clientY, bx: o.x, by: o.y,
    grip: { left: gr.left, right: gr.right, top: gr.top, bottom: gr.bottom },
  };
  window.addEventListener('pointermove', panelDragMove);
  window.addEventListener('pointerup', panelDragEnd);
  window.addEventListener('pointercancel', panelDragEnd);
}
function panelDragMove(e) {
  if (!_panelDrag) return;
  const M = 8;   // rezerva od okraje displeje, aby byl úchyt pořád chytatelný
  const gp = _panelDrag.grip;
  // Posun se OMEZÍ (clamp): úchyt musí zůstat na displeji, jinak panel zmizí.
  const dx = Math.min(Math.max(e.clientX - _panelDrag.x0, M - gp.left),
                      window.innerWidth - M - gp.right);
  const dy = Math.min(Math.max(e.clientY - _panelDrag.y0, M - gp.top),
                      window.innerHeight - M - gp.bottom);
  _panelMoved = Math.max(_panelMoved, Math.abs(e.clientX - _panelDrag.x0) + Math.abs(e.clientY - _panelDrag.y0));
  panelOffsets.value = {
    ...panelOffsets.value,
    [_panelDrag.name]: { x: _panelDrag.bx + dx, y: _panelDrag.by + dy },
  };
}
function panelDragEnd() {
  if (!_panelDrag) return;
  const name = _panelDrag.name;
  const moved = _panelMoved >= PANEL_SNAP_PX;
  _panelDrag = null;
  window.removeEventListener('pointermove', panelDragMove);
  window.removeEventListener('pointerup', panelDragEnd);
  window.removeEventListener('pointercancel', panelDragEnd);
  if (!moved) panelOffsets.value = { ...panelOffsets.value, [name]: { x: 0, y: 0 } };
  savePanelOffsets();
}
// Prázdný cíl pro touch listenery úchytu (`.prevent` = NEPASIVNÍ listener,
// který skutečně zabrání posunu/listování; v pasivním by jen hlásil chybu).
function noopTouch() {}

// --- Obrana proti systémovému gestu zpět (swipe od okraje displeje) --------
// Appka sama do knihovny NIKDY neskočí — sonda scripts/probe-nav-jump-to-library.py
// projela 40 listovacích gest (čtení, anotace, odebraná stránka, skok
// v číslování, sestava) a historie zůstala netknutá. „Vyskočení do seznamu
// skladeb" tedy dělá prohlížeč/OS gestem zpět: historie je [knihovna, čtečka],
// takže gesto zpět = knihovna — a gesto se chytá právě od okraje displeje
// (na některých tabletech až do poloviny šířky), tedy přesně v zóně listování.
// Řešení: dotyk v notách ozbrojí krátké okno; dorazí-li v něm navigace zpět,
// zrušíme ji a vrátíme adresu i záznam do not. Tlačítko Zpět v liště je vždy
// úmysl a projde okamžitě.
const BACK_GUARD_MS = 1500;
let _backGuardUntil = 0;
let _exitByButton = false;
let _unhookBackGuard = null;
function armBackGuard() { _backGuardUntil = Date.now() + BACK_GUARD_MS; }
function backGuard(to, from) {
  if (to.path !== '/' || !from.path.startsWith('/prohlizec')) return true;
  if (_exitByButton) { _exitByButton = false; return true; }
  if (Date.now() >= _backGuardUntil) return true;
  _backGuardUntil = 0;
  // Záznam v historii je už spolknutý prohlížečem — vrátíme adresu zpět do not.
  history.pushState(history.state, '', from.fullPath);
  return false;
}
function installBackGuard() {
  if (!_unhookBackGuard) _unhookBackGuard = router.beforeEach(backGuard);
}
function uninstallBackGuard() {
  if (_unhookBackGuard) { _unhookBackGuard(); _unhookBackGuard = null; }
}

// Tlačítko Zpět v liště = úmysl odejít (obrana proti gestu zpět ho nechá projít).
function goBack() { _exitByButton = true; router.push('/'); }

// --- Skoky (Da Capo / VIDE) ---
function toggleJumpMode() {
  jumpMode.value = !jumpMode.value;
  if (jumpMode.value) { annotMode.value = false; endEdit(); zoomPanelOpen.value = false; rotPanelOpen.value = false; pagesPanelOpen.value = false; pagesListOpen.value = false; sliderOpen.value = false; } // jiný panel → vypnout anotaci i výběr prvku
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
const firstPageValue = ref('');   // „první stránka" pro posun číslování
const thisPageValue = ref('');    // „tato stránka má číslo" pro skok v číslování
const pageGoInputEl = ref(null);
let _pageGoPrevPage = null;   // stránka, ze které jsme zadání otevřeli (Esc = zpět na ni)

function openPageGo() {
  _pageGoPrevPage = currentPage.value;
  // Předvyplní se číslo, které uživatel VIDÍ v notách (tedy včetně posunu).
  pageGoValue.value = String(withOffset(dispPage(currentPage.value)));
  firstPageValue.value = '';
  // Prázdné schválně: předvyplněné číslo by se dalo omylem potvrdit a zrušilo
  // by skok, který na stránce už je. Aktuální číslo je vidět v počítadle.
  thisPageValue.value = '';
  pageGoOpen.value = true;
  // panel se otevře i mimo anotační režim; ostatní mody zavřít, aby se nepřekrývaly
  annotMode.value = false; jumpMode.value = false; bookmarkMode.value = false; sliderOpen.value = false;
  zoomPanelOpen.value = false; rotPanelOpen.value = false;
  pagesPanelOpen.value = false; pagesListOpen.value = false;
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
  // Uživatel píše POŘADÍ ZOBRAZENÝCH stránek (to vidí v počítadle), ne index do PDF.
  // S posunem číslování a skoky se zadané číslo překládá zpět na pořadí.
  const slot = slotForDisplayed(n);
  const target = visiblePages.value[slot];
  if (target == null) return;
  // gotoPage je synchronní fire-and-forget (token v renderCurrent vykreslí jen poslední stránku)
  if (target === currentPage.value && _pageGoPrevPage === target) return;
  gotoPage(target);
}

// --- Záložky (konkrétní stránky) ---
function resetBookmarkEdit() {
  bookmarkEditingId.value = null;
  bmEditLabel.value = '';
}
async function closeBookmarkPanel() {
  // Rozepsaný název na řádku se při zavření uloží (uzavření panelu = potvrzení).
  if (bookmarkEditingId.value) await commitBookmarkEdit();
  bookmarkMode.value = false;
  bookmarkLabel.value = '';
}
function openBookmark() {
  // Opětovný tap na tlačítko záložek panel ZAVŘE (jinak se dal jen otevřít
  // a ven se šlo přes "Zavřít" v panelu).
  if (bookmarkMode.value) {
    closeBookmarkPanel();
    return;
  }
  bookmarkMode.value = true;
  annotMode.value = false;  // jiný panel → vypnout anotaci
  zoomPanelOpen.value = false;
  rotPanelOpen.value = false;
  pagesPanelOpen.value = false; pagesListOpen.value = false;
  sliderOpen.value = false;
  endEdit();               // a zrušit výběr prvku (rámeček by zůstal viset)
  bookmarkLabel.value = '';
  resetBookmarkEdit();
}
async function saveBookmark() {
  // Horní pole zakládá VÝHRADNĚ novou záložku na aktuální stránce.
  const label = bookmarkLabel.value.trim();
  if (bookmarks.value.some(x => x.page === currentPage.value)) { openBookmark(); return; }
  bookmarks.value.push({ id: crypto.randomUUID(), page: currentPage.value, label });
  // Nová záložka se zařadí vzestupně podle stránky — ale jen dokud si uživatel
  // pořadí nepřerovnal ručně (od té chvíle si drží své pořadí, Janovo rozhodnutí).
  // POZOR: v <script setup> se ref v JS NEODVÍJÍ sám — musí se přes .value,
  // jinak je `!bmManualOrder` vždy false a řazení se nikdy neprovede.
  if (!bmManualOrder.value) {
    bookmarks.value.sort((a, b) => a.page - b.page);
  }
  await dbSaveBookmarks({ songId: song.id, items: bookmarks.value, manualOrder: bmManualOrder.value }); // ruční pořadí
  bookmarkMode.value = false;
  bookmarkLabel.value = '';
  resetBookmarkEdit();
}
// Úprava názvu PŘÍMO NA ŘÁDKU (Jan, Oct 2026): tužka otevře input v tomtéž
// řádku, kde záložka je. Horní pole pro novou záložku se NEPOUŽÍVÁ — dřív se
// název přesouval nahoru a nebylo poznat, kterou záložku uživatel mění.
function startBookmarkEdit(b) {
  bookmarkEditingId.value = b.id;
  bmEditLabel.value = b.label || '';
  nextTick(() => {
    const el = bmEditInput.value;
    if (el) { el.focus(); el.select?.(); }
  });
}
function cancelBookmarkEdit() {
  resetBookmarkEdit();
}
async function commitBookmarkEdit() {
  const id = bookmarkEditingId.value;
  if (!id) return;
  const b = bookmarks.value.find(x => x.id === id);
  const label = bmEditLabel.value.trim();
  if (b && b.label !== label) {
    b.label = label;   // mění se jen text, stránka zůstává
    await dbSaveBookmarks({ songId: song.id, items: bookmarks.value, manualOrder: bmManualOrder.value });
  }
  resetBookmarkEdit();
}
// --- Řazení záložek tažením za táhlo (drag & drop) ---
// Jan: v úpravě záložek chce měnit pořadí tažením, ne šipkami.
// Řádek se přesouvá živě podle polohy prstu; do IndexedDB se ukládá až po puštění (jeden zápis).
const bmDragId = ref(null);       // id záložky, která se právě táhne (jen vizuální stav)
const bmManualOrder = ref(false); // uživatel si pořadí přerovnal ručně → už needit podle stránky
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
  if (d.moved) {
    bmManualOrder.value = true;                      // ruční přerovnání → držet toto pořadí
    bmSaveNow();                                      // jeden zápis po dokončení tažení
  }
}
function bmScheduleSave() {
  clearTimeout(_bmSaveTimer);
  _bmSaveTimer = setTimeout(() => { _bmSaveTimer = null; bmSaveNow(); }, 400);
}
function bmSaveNow() {
  clearTimeout(_bmSaveTimer);
  _bmSaveTimer = null;
  return dbSaveBookmarks({ songId: song.id, items: bookmarks.value, manualOrder: bmManualOrder.value });
}
async function goBookmark(b) {
  await gotoPage(b.page);
}
// Číslo stránky záložky pro UŽIVATELE — stejná cesta jako počítadlo stránek
// a seznam skoků: index do PDF → pořadí ZOBRAZENÝCH stránek → + posun číslování.
// POZOR (Jan, Oct 2026): dřív tu stálo `withOffset(b.page + 1)` — tedy index do
// PDF bez ohledu na odebrané stránky, takže lišta záložek si držela PŮVODNÍ
// čísla a po odebrání stránky se s počítadlem rozešla. `bookmarkPageNo` je
// jediná cesta, kterou se číslo záložky smí počítat (používá ji lišta i mazání).
function bookmarkPageNo(b) {
  return withOffset(dispPage(b && b.page != null ? b.page : null));
}
async function deleteBookmark(b) {
  if (confirm(`Smazat záložku „${b.label || 'str. ' + bookmarkPageNo(b)}"?`)) {
    bookmarks.value = bookmarks.value.filter(x => x.id !== b.id);
    await dbSaveBookmarks({ songId: song.id, items: bookmarks.value, manualOrder: bmManualOrder.value });
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
  /* Skrytí/ukázání tapem na střed stránky — plynulý, ale krátký přesun. */
  transition: transform 0.18s cubic-bezier(0.2, 0.7, 0.3, 1), opacity 0.15s linear;
}
/* Schovaná lišta: pryč z obrazu i z dosahu dotyku, aby tap prošel na noty. */
.top-bar.hidden {
  transform: translateY(-105%);
  opacity: 0;
  pointer-events: none;
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
.tb-mid-space { flex: 1 1 auto; min-width: clamp(16px, 4vw, 40px); }
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
  font-size: clamp(0.75rem, 1.9vw, 0.9rem); font-weight: 600; border-radius: 16px;
  gap: 4px; }
/* Tlačítko ROTACE: ikona + aktuální úhel. Úhel musí být vidět i se zavřenou
   nabídkou — jinak uživatel nepozná, že je stránka pootočená. */
.tb-rot-deg { font-size: clamp(0.7rem, 1.7vw, 0.84rem); font-weight: 600; }
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
   Klik otevře ruční zadání stránky. Je to absolutní prvek UVNITŘ .tb-row
   (statický), takže se pozicuje proti .top-bar — stejně jako dřív. */
.tb-page-center {
  position: absolute; left: 50%; top: 50%;
  transform: translate(-50%, -50%);
  z-index: 1;
}
/* ÚZKÝ DISPLEJ: absolutní střed přestane být bezpečný — lišta má po vytažení
   ukládacích tlačítek 10 tlačítek a pravá skupina se dostane POD počítadlo.
   Naměřeno (probe-breakpoint.py): volné místo mezi počítadlem a skupinami
   108,9 px na 1100, 16,2 px na 900, ale UŽ −0,9 px na 860 a −26,6 px na 800.
   Proto se od 960 px dolů počítadlo přesune do TOKU (mezi obě skupiny): pak
   tlačítka nemají kam zajet a nic se nepřekryje. Nad 960 zůstává na přesném
   středu — to je vzhled, který Jan odsouhlasil.
   ⚠️ Breakpoint NEstanovuj odhadem: hranice je daná skutečnou šířkou 10 tlačítek,
   mezer a počítadla, a posouvá se s každým dalším tlačítkem v liště.
   S počítadlem v toku musí ubrat i tlačítka — proto se tu zmenší `--tb` a mezery. */
@media (max-width: 960px) {
  .tb-page-center {
    position: static; transform: none;
    margin-left: auto; margin-right: auto;
  }
  .tb-mid-space { min-width: 0; }
}
@media (max-width: 620px) {
  .top-bar { --tb: clamp(30px, 7.8vw, 44px); }
  .tb-side { gap: 2px; }
  .tb-btn.zoom-btn { padding: 0 4px; min-width: calc(var(--tb, 38px) + 2px); }
  .tb-page { padding: 3px 5px; font-size: 0.78rem; }
}
/* Ještě užší telefon: úhel u rotace se schová (je vidět v nabídce rotace) —
   jinak by tlačítko bylo širší než ostatní a lišta by přetekla.
   ⚠️ S 11. tlačítkem („Odebrat stránky“) na 390 px počítadlo kolidovalo
   s tlačítky (naměřeno probe-counter-overlap.py: překryv 23 px s Anotací),
   proto se tu zmenší i `--tb` a mezery — ne jen skrytí úhlu. */
@media (max-width: 430px) {
  .top-bar { --tb: clamp(26px, 6.8vw, 40px); }
  .tb-rot-deg { display: none; }
  .tb-side { gap: 1px; }
  .tb-row { gap: 2px; }
  .tb-page { padding: 3px 6px; font-size: 0.74rem; }
  .tb-btn.zoom-btn { padding: 0 3px; min-width: calc(var(--tb, 38px) + 0px); }
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
/* Úzký displej (telefon na výšku): lišta má 10 tlačítek (po vytažení ukládacích
   na lištu) a s absolutním počítadlem se pravá skupina dostala POD něj
   (naměřeno na 390 px: Anotace 216,6 vs počítadlo do 217,7 — klepnutí na
   počítadlo by trefilo Anotaci). Zúžení je proto součástí breakpointu 620 px
   výše (počítadlo do toku + menší --tb); tady se už jen schová úhel u rotace,
   aby tlačítko nebylo širší než ostatní. Ověřuje probe-topbar-rotation.py
   a probe-counter-overlap.py. */
.tb-sep { display: none; }
.tb-nav { display: flex; align-items: center; gap: 3px; }
.tb-grp {
  font-size: 0.8rem; font-weight: 600; color: var(--text);
  min-width: 32px; text-align: center;
}
/* (Duplikát breakpointu 430 px byl odstraněn — zúžení lišty drží JEDEN
   breakpoint 620 px výše, tady zůstává jen skrytí úhlu u rotace.) */

/* Panel zvětšení — otevírá se z tlačítka s procenty, kotví se POD lištu */
.prefs-panel {
  flex-direction: row; flex-wrap: wrap; align-items: center; gap: 7px;
  width: max-content; max-width: 92vw; border-radius: 22px; padding: 8px 10px;
}
/* Řada ikon — stejné tvary jako dřívější ukládací tlačítka na liště.
   Zarovnaná DOLEVA (Jan: „taky bych to vše zarovnal doleva“), žádné
   roztahování na plnou šířku panelu. */
.prefs-row { display: flex; align-items: center; gap: 7px; }
.prefs-panel .prefs-icon { width: 40px; height: 40px; }
.prefs-panel .prefs-icon svg { display: block; }
/* Koš = malá ikona v ROHU té které ukládací ikony. Je to ikona (žádný text),
   ale je zřejmé, kterou preferenci maže (Jan). */
.prefs-slot { position: relative; }
.prefs-trash-badge {
  position: absolute; right: -3px; bottom: -3px; width: 18px; height: 18px;
  padding: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  background: var(--bg-elev); border: 1px solid rgba(224, 131, 111, 0.65);
  color: #e0836f; z-index: 1; touch-action: manipulation;
}
/* Tovární reset: „nabité“ tlačítko svítí výstražně, druhé klepnutí maže. */
.prefs-reset.armed { background: #e0836f; border-color: #e0836f; color: #17130f; }
/* Na úzkém telefonu se musí řada pěti ikon vejít bez přetečení — mírně menší
   tlačítka i mezery (jinak panel zabírá 92 % šířky displeje). */
@media (max-width: 430px) {
  .prefs-panel { gap: 5px; padding: 7px 8px; }
  .prefs-panel .prefs-icon { width: 36px; height: 36px; }
  .prefs-panel .prefs-icon svg { width: 16px; height: 16px; }
}
@media (max-width: 340px) {
  .prefs-panel .prefs-icon { width: 32px; height: 32px; }
  .prefs-panel .prefs-icon svg { width: 14px; height: 14px; }
}
.zp-btn.danger { color: #e0836f; border-color: rgba(224, 131, 111, 0.45); }
.zp-btn:disabled { opacity: 0.3; }
.zoom-panel {
  position: absolute; top: calc(var(--topbar-h, 96px) + 6px); left: 50%;
  /* Centrování i posun přetažením v jednom transformu — posun drží
     --pd-x/--pd-y z panelStyle(). */
  transform: translateX(-50%) translate(var(--pd-x, 0px), var(--pd-y, 0px));
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
/* Číselné a procentové akce (100 %, −10, +10) — je to POPISEK, ne symbol.
   Dřív dědily 1.3rem určené pro „−“ a „+“, takže v panelu křičely
   (Jan: „hrozně velký text“). Symboly − / + zůstávají velké. */
.zp-btn.num { font-size: 0.85rem; font-weight: 600; white-space: nowrap; }
/* „100 %“ je delší popisek než „−10“ — do 44px kruhu se s jednotnou
   velikostí nevejde na jeden řádek, proto vlastní (širší) tvar. */
.zp-btn.wide { width: 56px; }
/* Jemné otáčení (0,1°) — menší tlačítko, ať se řada vejde a je vidět,
   že jde o jemnější krok než sousední 1°. */
.zp-btn.fine { width: 38px; height: 38px; font-size: 1.1rem; }
.zp-val { min-width: 56px; text-align: center; font-size: 0.85rem; font-weight: 600; color: var(--text); }
.zp-sep { width: 1px; height: 26px; background: var(--border); }
/* Úhel otočení — klepnutím se zruší (ploché, jen :active feedback) */
.zp-rot {
  min-width: 48px; padding: 4px 6px; text-align: center;
  background: transparent; border: 1px solid var(--border); border-radius: 14px;
  font: inherit; font-size: 0.92rem; font-weight: 600; color: var(--text-dim);
  cursor: pointer; touch-action: manipulation;
}
.zp-rot:active { background: var(--bg-elev2); }

/* Panel rotace — na užším displeji se řada tlačítek musí vejít, proto povolíme
   zalomení (zoom panel má prvků málo a zůstává v jednom řádku). */
.rot-panel { flex-wrap: wrap; justify-content: center; max-width: min(96vw, 620px); }

/* Hláška o uložení — plochá, teplá, bez glow (Jan: mobilní PWA, žádné efekty).
   Sedí dole nad lištou záložek, aby nepřekážela v čtení not. */
.viewer-toast {
  position: fixed; left: 50%; bottom: calc(48px + var(--sab));
  transform: translateX(-50%);
  z-index: 34;
  background: var(--bg-elev2);
  border: 1px solid var(--accent-dim);
  color: var(--text);
  border-radius: 20px;
  padding: 8px 16px;
  font-size: 0.88rem; font-weight: 600;
  white-space: nowrap; pointer-events: none;
  box-shadow: 0 3px 14px rgba(0,0,0,0.5);
}

/* Referenční mřížka při ladění rotace. Kreslí se PŘES CELÝ DISPLEJ (fixed), ne
   přes papír — je to pomůcka pro oko, aby uživatel viděl, co je na obrazovce
   vodorovně a co svisle, a mohl podle toho srovnat noty. Linky jsou jemné,
   teplé a poloprůhledné (Jan: ploché, bez křiklavých barev), nesmí chytat dotyk. */
.rot-grid {
  position: fixed; inset: 0;
  pointer-events: none;
  z-index: 26;
  opacity: 0.5;
  background-image:
    /* svislé linky */
    linear-gradient(to right, rgba(201, 168, 124, 0.34) 1px, transparent 1px),
    /* vodorovné linky */
    linear-gradient(to bottom, rgba(201, 168, 124, 0.34) 1px, transparent 1px),
    /* zdůrazněné osy středu */
    linear-gradient(to right, rgba(201, 168, 124, 0.6) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(201, 168, 124, 0.6) 1px, transparent 1px);
  background-size: 40px 40px, 40px 40px, 100% 100%, 100% 100%;
  background-position: 0 0, 0 0, 50% 0, 0 50%;
}

/* Oblast stránky pod lištou — z její velikosti se počítá fit not */
.page-area {
  flex: 1 1 auto; min-height: 0; position: relative;
  /* Lišta je jen OVERLAY — stránku nikdy neposouvá (Jan: „lišta se musí
     objevit jako overlay, nesmí posunout zbytek stránky“). Plocha má proto
     stálý malý odstup + safe-area, ať noty nelezou pod notche; když se lišta
     ukáže, prostě se překryje přes horní pruh not. */
  /* Odsazení je SYMETRICKÉ (nahoře i dole stejně). Jednostranný padding
     posouval střed plochy dolů — stránka pak seděla níž, „jakoby pořád
     počítala s horní lištou“ (Jan). Se symetrickým odsazením je papír
     vycentrovaný na displeji a zároveň neleze pod notch ani pod gesture bar. */
  padding: var(--page-pad, 8px) 0 var(--page-pad-b, 8px);
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
.stage { position: relative; touch-action: none; z-index: 1; }
/* Bílé plátno POD stránkou — svítí VŽDY, i pro neupravenou stránku.
   Kotví se na displej pod horní lištu, takže kryje celou čtecí plochu — ať je
   papír posunutý nebo přiblížený jakkoli. Jeden vzhled pro všechny stránky,
   aby neupravená stránka nevypadala menší než upravená (Jan, Sep 2026).
   DŮLEŽITÉ: musí zůstat POD papírem. .stage má z-index auto (0), takže plátno
   s nižším z-indexem sedí pod ním — kdyby mělo vyšší, překrylo by noty a nešlo
   by je odstranit (Jan). Proto z-index: 0 a .stage dostává z-index: 1. */
.sheet-backdrop {
  position: fixed; left: 0; right: 0; bottom: 0;
  top: var(--topbar-h, 96px);
  background: #fff;
  pointer-events: none;
  z-index: 0;
}
/* Při rotaci jsou za otočeným papírem vidět šikmé hrany (tmavé pozadí). Bílá
   plocha POD papírem, která přesně kopíruje jeho otočený obrys, je schová —
   papír pak vypadá jako souvislá bílá stránka, ne jako otočený obdélník.
   Je to bratr .rotor (ne jeho potomek), aby se rotace neaplikovala dvakrát. */
.stage::before {
  content: '';
  position: absolute; inset: 0;
  background: #fff;
  border-radius: 8px;
  opacity: 0;
  transition: opacity 0.12s linear;
  pointer-events: none;
}
.stage.rotated::before { opacity: 1; }
/* Vnitřní otočný box — přesně velký jako (neotočená) stránka, otáčí se kolem
   svého středu. Obsahuje canvas, anotační vrstvu i tlačítka skoků, takže se
   vše otočí společně a poznámky zůstanou na svém místě v notách. */
.rotor {
  position: absolute; top: 50%; left: 50%;
  transform-origin: center center;
  /* Rotace i zoom se mění v rukávu (gesto / držení tlačítka). Bez tohohle
     prohlížeč při každé změně transformu znovu rasterizuje vrstvu, což je
     znát jako sekání — se `will-change` drží vrstvu na GPU. */
  will-change: transform;
}
.pdf-canvas { display: block; background: #fff; box-shadow: 0 2px 14px rgba(0,0,0,0.6); border-radius: 6px; touch-action: none; }
/* Na bílém plátně (<- zoom / posun / rotace) by stín papíru prozradil, že jde
   o papír položený na jiném podkladu (Jan: „jsou na plátně ještě vidět vnější
   stíny od stránky s notami“). Když plátno svítí, stín se vypne — papír i plátno
   jsou bílé, takže splynou v jednu plochu. V tmavém výchozím stavu stín zůstává. */
.stage.backdrop .pdf-canvas { box-shadow: none; }
/* Stín papíru při rotaci: měkký stín canvasu kopíruje OTOČENÝ okraj papíru, takže
   přes bílé plátno (.stage::before, které má obrys opsaného obdélníku) prosvítá
   šikmá tmavá hrana a je vidět, že je to pootočený papír na jiném podkladu (Jan).
   Proto při rotaci stín canvasu vypneme a stín nese samo plátno — obrys papíru
   i stín tak mají stejný, vodorovně zarovnaný tvar. */
.stage.rotated .pdf-canvas { box-shadow: none; }
.stage.rotated::before { box-shadow: 0 2px 14px rgba(0,0,0,0.6); }
/* Když je plátno aktivní (zoom/posun/rotace), stín papíru i bílého obrysu se
   vypne — jinak je na bílé ploše vidět šedý lem a prozradí „pootočený papír na
   jiném podkladu“. Papír i plátno jsou bílé, takže mají splynout v jednu plochu. */
.stage.backdrop .pdf-canvas,
.stage.backdrop::before { box-shadow: none; }
.annot-layer { position: absolute; top: 0; left: 0; touch-action: none; cursor: crosshair; }
/* V anotaci vrstva přijímá dotyk, ale stránkování okrajovými klepnutími se
   rozhoduje už v onTouchEnd (musí vidět pointerType i poloměr dotyku). */
.annot-layer.active { pointer-events: auto; }
.annot-layer.active + .stage {  }
.annot-layer:not(.active) { pointer-events: none; }
/* Pruh u okrajů = listování prstem (jen při čtení). Je to vizuální pomůcka,
   nesmí chytat dotyk — ten musí dojít až na .viewer. */
.edge-hint {
  position: absolute; top: 0; bottom: 0; left: 0;
  width: var(--edge-w, 70px);
  /* ŽÁDNÉ max-width v procentech! Dřívější `max-width: 20%` přebíjel vypočtenou
     šířku: na okně 390 px držel pruh na 78 px, zatímco edgeWidth() už listoval
     jen v 58,5 px — vizuál pak lhal o 20 px a klepnutí uvnitř pruhu nelistovalo.
     Šířku drží VÝHRADNĚ `--edge-w` (jediný zdroj pravdy s JS). */
  pointer-events: none; z-index: 18;
  /* Lehké průhledné vybarvení + čárkovaný vnitřní okraj — uživatel přesně
     vidí, kde okrajová zóna pro listování začíná. Hrana je na vnitřní straně
     pruhu, tedy přesně tam, kde přestává platit edgeWidth() v JS. */
  background: rgba(201, 168, 124, 0.07);
  border-right: 1px dashed rgba(201, 168, 124, 0.38);
}
.edge-hint.right {
  left: auto; right: 0;
  border-right: none;
  border-left: 1px dashed rgba(201, 168, 124, 0.38);
}
/* Listování v ANOTAČNÍM režimu — dvě plovoucí tlačítka u spodních rohů.
   Okrajové tap zóny jsou v anotaci vypnuté (kraj patří psaní poznámek),
   takže listování obstarají tahle dvě tlačítka. Jen v anotaci. */
.annot-nav {
  /* FIXED, ne absolute: kotví se k OBRAZOVCE, ne ke čtecí ploše. Na telefonu
     se tím tlačítka nikdy nedostanou pod spodní hranu (Jan: „mimo obrazovku,
     příliš nízko“). `--sab` drží odstup od systémové lišty a 56 px je nad
     lištou záložek, která sedí u spodní hrany. */
  position: fixed; left: 0; right: 0; bottom: calc(56px + var(--sab));
  display: flex; justify-content: space-between;
  padding: 0 14px; z-index: 31; pointer-events: none;
}
.annot-nav-btn {
  pointer-events: auto; width: 54px; height: 54px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: rgba(24, 22, 20, 0.78); color: #f0ece4;
  border: 1px solid rgba(255, 255, 255, 0.22);
  /* Ikona je SVG (dřív textový znak ‹ / ›, který seděl opticky výš) — flex
     ji teď vycentruje přesně na střed knoflíku, bez dorovnávacího paddingu. */
  padding: 0; line-height: 0;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.45);
  -webkit-tap-highlight-color: transparent;
}
.annot-nav-btn svg { display: block; }
.annot-nav-btn:disabled { opacity: 0.35; }
.annot-nav-btn:active:not(:disabled) { background: rgba(60, 56, 50, 0.9); }
.annot-layer .hl { mix-blend-mode: multiply; opacity: 0.9; }
/* Náhled zvýrazňovače při sytých barvách: ať je vidět, že jde o zvýraznění,
   a ne o přebarvení not — náhled multiplikuje stejně jako hotový tvar. */
.annot-layer .hl-preview { mix-blend-mode: multiply; opacity: 0.55; }

/* ===== Panely a modaly se kotví POD horní lištu (tlačítko i panel u sebe) ===== */

/* Tlačítko skoku umístěné PŘÍMO NA NOTÁCH — obdélník, který si uživatel
   naklepal třemi body (levý horní, levý spodní, pravý) a může ho posouvat tažením.
   Souřadnice jsou ve stejné soustavě jako anotační vrstva (CSS px stránky). */
.jump-on-page {
  position: absolute; top: 0; left: 0; width: 100%; height: 100%;
  pointer-events: none;   /* samotná vrstva nesmí blokovat kreslení/gesta */
  z-index: 19;
}
/* V nástroji Ruka (Upravit) musí tlačítko skoku pustit klepnutí až na anotační
   vrstvu — jinak ho ruka „neuchopí": tlačítko má pointer-events: auto a leží NAD
   vrstvou, takže pointerdown skončil na něm a na vrstvě se vůbec nespustil
   (uživatel sice viděl rámeček, ale tlačítko nešlo přesunout). */
.jump-on-page.edit-mode { pointer-events: none; }
.jump-on-page.edit-mode .jump-on-btn { pointer-events: none; }
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
/* Náhled před uložením — čárkovaně, ať je jasné, že ještě není uložený */
.jump-on-btn.preview {
  background: rgba(201,168,124,0.30); border: 2px dashed var(--accent);
  color: var(--text); pointer-events: none;
}
/* Nápověda u sběru tří bodů (v panelu skoku) */
.jp-hint {
  font-size: 0.82rem; color: var(--accent); font-weight: 600;
  background: var(--bg-elev2); border-radius: 8px; padding: 6px 8px;
}
/* Nápověda při umisťování tlačítka na noty — úzká lišta DOLE, aby nezakrývala
   noty, na které uživatel klepá. Panel skoku je při umisťování schovaný. */
.jp-place-hint {
  position: absolute; left: 50%; bottom: calc(16px + var(--sab)); transform: translateX(-50%);
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

/* --- PŘETAHOVÁNÍ PANELŮ (Jan, Oct 2026) ---
   Panely (anotace, zvětšení, rotace, odebrání stránek, skoky, záložky) se dají
   odtáhnout mimo noty. Posun drží --pd-x/--pd-y z panelStyle(); transform
   panelů proto zůstává tady v CSS (jinak by se ztratilo centrování zoomu). */
.jump-panel, .annot-panel {
  transform: translate(var(--pd-x, 0px), var(--pd-y, 0px));
}
.panel-grip {
  flex: 0 0 auto; width: 30px; height: 30px; padding: 0; line-height: 1;
  border-radius: 50%; border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text-dim); font-size: 0.95rem; cursor: grab;
  touch-action: none;   /* tah po úchytu nesmí posouvat stránku ani listovat */
}
.panel-grip:active { background: var(--accent); border-color: var(--accent); color: #17130f; }

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
/* Input PŘÍMO V ŘÁDKU záložky (přejmenování na místě) — o něco menší než
   pole pro novou záložku, ať se řádek nerozjede do výšky. */
.jp-input-edit { padding: 5px 8px; font-size: 0.85rem; }
.jp-close { background: var(--bg-elev2); border: 1px solid var(--border); border-radius: 10px; padding: 8px; color: var(--text); cursor: pointer; }
.jp-cur { color: var(--text); font-size: 0.9rem; font-weight: 600; }

/* Záložky — vždy viditelná lišta u spodní hrany, overlay nad plátnem.
   position: fixed → kotví proti viewportu (obrazovce), ne proti výšce plátna,
   takže se nemůže dostat pod obraz, ať je canvas jakkoli velký. */
.bookmark-strip {
  position: fixed; left: 16px; right: 16px; bottom: calc(4px + var(--sab));
  display: flex; flex-wrap: nowrap; gap: 6px; align-items: center;
  justify-content: flex-start; z-index: 22;
  overflow-x: auto; overflow-y: hidden;    /* jediný řádek, při přetečení horizontální scroll */
  scrollbar-width: none;                   /* skrýt scrollbar (Firefox) */
  -ms-overflow-style: none;                /* (IE) */
  padding: 3px 6px;
  pointer-events: auto;                     /* lišta musí reagovat, aby šla horizontálně scrollovat */
  /* .viewer má touch-action: none (obrana proti gestu zpět), takže posun
     musíme povolit tady — jinak by lišta přestala scrollovat. */
  touch-action: pan-x;
  /* Lišta má být JEN jemný pruh záložek nad notami, ne panel — skoro průhledná,
     bez výrazného stínu a s minimálním vnitřním okrajem. */
  background: rgba(28,25,23,0.28);
  border: 1px solid rgba(58,53,50,0.55);
  border-radius: 20px;
  backdrop-filter: blur(3px);
  box-shadow: 0 2px 10px rgba(0,0,0,0.35);
}
.bookmark-strip::-webkit-scrollbar { display: none; }  /* skrýt scrollbar (Chrome/Safari) */
.bookmark-btn {
  flex: 0 0 auto; display: inline-flex; align-items: center; gap: 5px;
  background: rgba(38,34,32,0.55); border: 1px solid rgba(58,53,50,0.7);
  border-radius: 16px; padding: 3px 9px;
  font-size: 0.85rem; font-weight: 600; color: var(--text);
  cursor: pointer; touch-action: manipulation; pointer-events: auto;
}
.bookmark-btn.circle {
  border-radius: 50%;
  width: 30px; height: 30px; padding: 0;
  justify-content: center;
}
.bookmark-btn.on { border-color: var(--accent); background: rgba(51,46,43,0.75); }
.bookmark-btn:active { background: rgba(51,46,43,0.8); }
.bk-num {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 18px; padding: 0 3px;
  background: var(--accent); color: #17130f; border-radius: 50%;
  font-size: 0.72rem; font-weight: 700;
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
  /* Dialog má víc sekcí (posun i skoky v číslování) — na malém displeji se
     musí dát odscrollovat, jinak poslední řádek zmizí pod okrajem. */
  max-height: calc(100dvh - var(--topbar-h, 96px) - 32px);
  overflow-y: auto;
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
/* ✕ na miniaturách — odebrání stránky. Jen v pásu, ploché, bez hoveru. */
.thumb-x {
  position: absolute; top: 2px; left: 2px; z-index: 3;
  width: 22px; height: 22px; padding: 0; line-height: 1;
  border-radius: 50%; border: 1px solid rgba(0,0,0,0.45);
  background: rgba(20,18,16,0.78); color: #f0e6da;
  font-size: 0.72rem; cursor: pointer; touch-action: manipulation;
}
.thumb-x:active { background: var(--accent); color: #17130f; }
/* Panel odebírání stránek — seznam odebraných (kotví se pod lištu jako ostatní) */
.pages-list {
  position: absolute; top: calc(var(--topbar-h, 96px) + 52px); right: 8px;
  width: min(320px, calc(100% - 16px));
  display: flex; flex-direction: column; gap: 6px;
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: 10px;
  padding: 10px 12px; box-shadow: 0 4px 18px rgba(0,0,0,0.6); z-index: 31;
  max-height: min(46dvh, 340px); overflow-y: auto;
}
/* Počítadlo: doplněk „(z N)" je jen informace, nesmí přebít hlavní číslo */
.tb-page-of { font-weight: 400; opacity: 0.72; font-size: 0.9em; }
/* Nápověda v dialogu zadání stránky (odebrané stránky se přeskakují) */
.pg-hint { font-size: 0.8rem; color: var(--text-dim); line-height: 1.35; }
/* Posun číslování v dialogu Přejít na stránku — jeden plochý řádek. */
.pg-offset {
  display: flex; align-items: center; gap: 8px;
  border-top: 1px solid var(--border); padding-top: 10px;
}
.pg-offset-label { font-size: 0.85rem; color: var(--text-dim); flex: 1; }
.pg-offset-input {
  width: 72px; padding: 7px 9px; text-align: center;
  background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
  color: var(--text); font-size: 0.95rem;
}
.zp-val.dim { opacity: 0.55; }
/* Seznam skoků v číslování — pod zadávacím řádkem, ploché řádky bez karet. */
.pg-jumps {
  display: flex; flex-direction: column; gap: 6px;
  border-top: 1px solid var(--border); padding-top: 10px;
}
.pg-jumps .jp-item { padding: 6px 8px; }
.pg-jumps .jp-item .jp-btn { flex: 0 0 auto; }
.thumb-item {
  position: relative; flex: 0 0 auto; width: 72px; height: 96px;
  border-radius: 6px; overflow: hidden; border: 2px solid var(--border);
  background: #fff; padding: 0; cursor: pointer; touch-action: manipulation;
}
.thumb-item.on { border-color: var(--accent); }
/* Mezera virtuálního pásu — drží geometrii pro scroll i slider (prvky v DOM
   jsou jen okolo aktuální stránky). */
.thumb-spacer { flex: 0 0 auto; height: 96px; }
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
/* ⚠️ ZNAKY V KRUHOVÝCH TLAČÍTKÁCH SEDÍ PODLE METRIK PÍSMA, NE PODLE STŘEDU ŘÁDKU.
   Naměřeno z pixelů (scripts/diag-menu-centering.py, snímek obrazovky): čísla
   velikosti měla střed otisku o ~1,2 px NAD středem tlačítka, „T“ o ~2,25 px
   a glyf dynamiky z fontu NotyDyn o ~3,0 px. Jan: „čísla a znaky nejsou
   vycentrovaný uprostřed tlačítek“. Flex centruje ŘÁDEK, ale znak v něm visí
   podle účaří — proto se textové znaky posouvají dolů.

   ⚠️ EMOJI SE NEPOSOUVAJÍ — canvas u nich měří záložní písmo, ne barevný glyf,
   a emoji mají svůj vlastní střed (naměřeno: bez posunu sedí).
   ⚠️ Hodnoty jsou ZMĚŘENÉ a jsou to kompromisy: přesnost měření z pixelů je
   0,5 px (fyzické pixely při dsf=2), takže zbytek je do ~1 px. Zkusila jsem
   posun počítat z metrik fontu pro každý znak zvlášť — u glyfů NotyDyn to
   SELHALO (canvas je měří záložním písmem) a vyšlo to hůř, proto jsou tu pevné
   hodnoty. Když se změní font nebo velikost znaků, přeměř. */
.ap-tool > span.ap-glyph:not(.emoji), .ap-size > span, .dyn-ico {
  display: inline-block;
  transform: translateY(var(--glyph-nudge, 1.2px));
}
/* Pevné posuny — ZMĚŘENÉ kalibrací `scripts/calibrate-menu-glyphs.py`, která
   v jednom běhu projede řadu hodnot a najde tu, při které je střed otisku přesně
   ve středu tlačítka (ladit to rebuildem je plýtvání: jeden rebuild na jednu
   hodnotu). Znaménko: kladná odchylka = znak je NÍŽ, než má být.
   Emoji se neposouvají — canvas u nich měří záložní písmo, ne barevný glyf;
   kalibrace u nich ukázala odchylku nezávislou na posunu (−1 px), takže posunem
   se to nespraví. */
.ap-tool > span.ap-glyph.emoji { --glyph-nudge: 0px; }
.ap-glyph.t-glyph { --glyph-nudge: 1.0px; }         /* „T“   (kalibrace: 1,00) */
.ap-tool.mus .ap-glyph { --glyph-nudge: 0px; }      /* „<“/„>“ (kalibrace: 0,00) */
.ap-size span { --glyph-nudge: 1.5px; }             /* čísla velikosti (kalibrace: 1,50) */
.dyn-ico { --glyph-nudge: 3.5px; }                  /* „mf“  (kalibrace: 3,50) */
/* Značky (♮, ♯, trylek…) mají jiný otisk než „mf“ — kalibrace pro ně vyšla 0,25 px.
   Drž je zvlášť, ať se jedno neladí na úkor druhého. */
.ap-tool[title^='Značky'] .dyn-ico { --glyph-nudge: 0.25px; }
/* Ikona nástroje Vkládání not = nota z fontu. Její otisk visí ÚPLNĚ JINAK než
   „mf“ nebo značky: nota má skoro celý otisk NAD účařím (nožička nahoru), takže
   ho flex vycentruje vysoko. Naměřeno `scripts/diag-note-icon-centering.py`
   (z pixelů, výřez přes CELÉ tlačítko): bez posunu je střed otisku 8,5 px nad
   středem tlačítka → posun 8,5 px. */
.ap-tool[title^='Vkládání not'] .dyn-ico { --glyph-nudge: 8.5px; }
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

/* Pásmo úprav vybrané textové/dynamické anotace — POD horní lištou.
   DVA ŘÁDKY: hlavní (vždy: typ, ✏️, velikost ±, ▢, ✓, 🗑) a řádek rámu (čipy).
   Naměřeno před opravou na tabletu 800 px: jediný řádek měl obsah 903 px do
   764 px a koš skončil na x=887..921, tedy mimo lištu I mimo displej.
   Řádky se navíc samy zalamují (`flex-wrap`), takže se lišta vejde i na mobil
   a při zvětšeném systémovém písmu. */
.edit-bar {
  position: fixed; left: 50%; top: calc(var(--topbar-h, 96px) + 8px); transform: translateX(-50%);
  display: flex; flex-direction: column; align-items: stretch; gap: 6px;
  background: var(--bg-elev); border: 2px solid var(--accent); border-radius: 24px;
  padding: 8px 12px; box-shadow: 0 4px 18px rgba(0,0,0,0.6);
  z-index: 27; max-width: 96vw; box-sizing: border-box;
}
.eb-row {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  justify-content: center;
  /* `width: max-content` je TU PODSTATNÉ: bez něj si `position: fixed` lišta
     vzala šířku podle PRVNÍHO řádku (naměřeno: lišta 400 px, protože hlavní
     řádek měřil 369 px) a řádek rámu s čipy (439 px) se pak zbytečně lámal
     do dvou řádků. S `max-content` na řádcích určí šířku lišty ten NEJŠIRŠÍ
     řádek a `max-width: 100%` zajistí zalamování teprve tehdy, když se řádek
     do lišty (do 96vw) opravdu nevejde. */
  width: max-content; max-width: 100%;
}
.eb-row-frame { row-gap: 6px; }
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
/* Zapnutý přepínač v pásu úprav (rámeček textu) — stejné pravidlo jako u
   anotačních tlačítek: stav je vidět i bez otevřeného panelu. */
.eb-btn.on { border-color: var(--accent); color: var(--accent); }
/* Čipy pro šířku/styl rámu v pásu úprav — menší než hlavní kruhová tlačítka,
   aby se lišta na tabletu vešla (viz breakpoint v pwa-pdf-viewer). */
.eb-chip {
  padding: 5px 10px; border-radius: 12px; flex: 0 0 auto;
  border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); font-size: 0.75rem; font-weight: 600;
  cursor: pointer; touch-action: manipulation;
}
.eb-chip.on { border-color: var(--accent); color: var(--accent); }

/* Sběr bodů zobáčku — hint lišta */
.wedge-overlay {
  position: fixed; left: 50%; bottom: calc(14px + var(--sab)); transform: translateX(-50%);
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

/* Velikost textu před vložením — jednořádkový ovladač s živým náhledem „Aa“.
   Jan nedělá karty, ale tohle je uvnitř dialogu: plochý řádek, teplé tóny. */
.ti-size-row { display: flex; align-items: center; gap: 8px; }
.ti-size-label { font-size: 0.85rem; color: var(--text-dim); }
.ti-size-btn {
  width: 34px; height: 34px; flex: 0 0 auto; padding: 0;
  border-radius: 50%; border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); font-size: 1.05rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center; touch-action: manipulation;
}
.ti-size-val { min-width: 34px; text-align: center; font-size: 0.95rem; font-weight: 600; }
.ti-size-sample {
  flex: 1; min-width: 0; display: flex; align-items: center; justify-content: flex-end;
  height: 60px; overflow: hidden;
}
/* Náhled velikosti: ukazuje SKUTEČNOU hodnotu font-size, jakou text dostane.
   Řádek má pevnou výšku, aby náhled velkých velikostí neroztlačil dialog;
   velké velikosti se proto zmenšují transformem (poměr zůstává, jen se vejde). */
.ti-size-aa { line-height: 1; color: var(--text); transform-origin: right center; }
/* Náhled noty: překlápí se (scale −1) i zmenšuje kolem SVÉHO STŘEDU — u pravého
   okraje by zrcadlení uteklo mimo náhled. */
.nota-nahled { transform-origin: center center; }
/* Barva textu a rámeček — plochý řádek, stejná paleta jako pero (Jan, Oct 2026) */
.ti-row { display: flex; align-items: center; gap: 8px; }
.ti-colors { display: flex; flex-wrap: wrap; gap: 8px; }
.ti-color {
  width: 28px; height: 28px; flex: 0 0 auto; padding: 0;
  border-radius: 50%; box-sizing: border-box;
  border: 2px solid var(--border); cursor: pointer;
}
.ti-color.on { border-color: var(--accent); }
.ti-toggle {
  padding: 7px 14px; border-radius: 18px;
  border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); font-size: 0.85rem; font-weight: 600;
  cursor: pointer; touch-action: manipulation;
}
.ti-toggle.on { border-color: var(--accent); color: var(--accent); }
/* Volba šířky a stylu rámečku textu — malé ploché čipy (Jan: žádné karty).
   Tvar připomíná volenou vlastnost: čip je obdélník, ne kruh jako u barev. */
.ti-chip {
  padding: 6px 12px; border-radius: 14px;
  border: 1px solid var(--border); background: var(--bg-elev2);
  color: var(--text); font-size: 0.82rem; font-weight: 600;
  cursor: pointer; touch-action: manipulation;
}
.ti-chip.on { border-color: var(--accent); color: var(--accent); }
/* Skryté <text> pro měření skutečné šířky textu (viz textMetrics). Nesmí být
   vidět ani chytat dotyk — slouží jen prohlížeči k měření. */
.text-measure { visibility: hidden; pointer-events: none; }
/* Tlačítko „Uložit a ruka“ = potvrzení + přepnutí nástroje; musí být vidět,
   že je to ta akce, kterou uživatel po vložení chce. */
.jp-btn.hand { background: var(--bg-elev2); border-color: var(--accent); color: var(--accent); font-weight: 600; }

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
.ti-note { font-size: 0.8rem; color: var(--text-dim); }
/* Obal glyfu noty v dlaždici: posouvá se tak, aby byl otisk vycentrovaný (viz
   noteTileNudge). `display: block` drží dlaždici v řádku gridu, `line-height: 1`
   stejnou výšku jako měření. */
.nota-glyf { display: block; line-height: 1; }
/* Stejné ztluštění nožičky jako na stránce (SVG `stroke` + `paint-order`) — dlaždice
   i mini náhled musí ukazovat přesně to, co se vloží. Hodnota v em drží s velikostí. */
.nota-glyf, .nota-nahled, .ap-tool[title^='Vkládání not'] .dyn-ico {
  -webkit-text-stroke: 0.025em currentColor;
}
/* Sekce nabídky značek (Posuvky / Ozdoby / Drobnosti) — dlaždice zůstávají stejné */
.mark-sec { display: flex; flex-direction: column; gap: 4px; }
.mark-sec-label {
  font-size: 0.75rem; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--text-dim);
}

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
