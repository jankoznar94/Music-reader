// src/pdf.js — obal nad pdf.js (renderování stránek do canvasu)
import * as pdfjsLib from 'pdfjs-dist';
import { toRaw } from 'vue';

// Worker pro pdf.js
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.mjs',
  import.meta.url
).toString();

// Cache načtených dokumentů (podle song id), aby se PDF neparsovalo opakovaně
const _docs = new Map();

async function getDoc(song) {
  if (_docs.has(song.id)) return _docs.get(song.id);
  // song.data je Blob uložený v IndexedDB. Pozor: v Prohlížeči bývá obalený
  // Vue reactive proxy — tu pdf.js nerozpozná, proto ji rozbalíme přes toRaw().
  // pdf.js v `data` NEakceptuje Blob (jen TypedArray/string/array-like), takže
  // Blob převedeme na ArrayBuffer. (Pozn.: streamování Blobu přímo do pdf.js
  // nefunguje — pdf.js Blob v data nepodporuje.)
  const blob = toRaw(song.data);
  const arrayBuffer = await blob.arrayBuffer();
  const doc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  _docs.set(song.id, doc);
  return doc;
}

export async function getPageCount(song) {
  const doc = await getDoc(song);
  return doc.numPages;
}

export async function getPageWidthHeight(song, pageNum) {
  const doc = await getDoc(song);
  const page = await doc.getPage(pageNum);
  const vp1 = page.getViewport({ scale: 1 });
  return { width: vp1.width, height: vp1.height };
}

/**
 * Vykreslí stránku PDF do canvasu.
 * @param {*} song skladba (musí mít .data Blob)
 * @param {number} pageNum 1-based
 * @param {HTMLCanvasElement} canvas
 * @param {number} renderScale výška v CSS px (šířka se odvodí poměrem)
 * @returns {Promise<{width:number,height:number}>} CSS px rozměry stránky
 */
export async function renderPage(song, pageNum, canvas, renderScale = 900) {
  const doc = await getDoc(song);
  const page = await doc.getPage(pageNum);
  const base = page.getViewport({ scale: 1 });
  const devicePixelRatio = window.devicePixelRatio || 1;

  // Cílový cssH ~ renderScale px; cssW podle poměru stran
  const cssH = renderScale;
  const cssW = (base.width / base.height) * cssH;

  // Render v plném rozlišení pro ostrý obraz
  // scale je násobitel vůči základním rozměrům (scale 1): cssW/base.width == cssH/base.height
  const viewport = page.getViewport({ scale: cssW / base.width });
  canvas.width = Math.max(1, Math.floor(cssW * devicePixelRatio));
  canvas.height = Math.max(1, Math.floor(cssH * devicePixelRatio));
  canvas.style.width = `${cssW}px`;
  canvas.style.height = `${cssH}px`;

  const context = canvas.getContext('2d');
  context.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  await page.render({ canvasContext: context, viewport }).promise;
  return { width: cssW, height: cssH };
}

/**
 * Vykreslí VÝŘEZ stránky (ořez okrajů) do canvasu.
 * @param {*} song skladba
 * @param {number} pageNum 1-based
 * @param {HTMLCanvasElement} canvas
 * @param {{x:number,y:number,w:number,h:number}} crop výřez v PDF bodech (scale 1)
 * @param {number} outW cílová šířka v CSS px
 * @param {number} outH cílová výška v CSS px
 */
export async function renderPageRegion(song, pageNum, canvas, crop, outW, outH, opts = {}) {
  const doc = await getDoc(song);
  const page = await doc.getPage(pageNum);
  // `opts.dpr` = pevné měřítko plátna. Detekce taktových čar MUSÍ být na
  // zařízení nezávislá: s window.devicePixelRatio se stejná stránka vykreslí
  // jinak (jiné zaokrouhlení/antialiasing) a na tabletu s dpr 2 vycházely jiné
  // počty taktů než na dpr 1 (naměřeno Mozart str. 9: 5 taktů vs 4). Proto
  // detekční volání předávají dpr: 1.
  const devicePixelRatio = opts.dpr != null ? opts.dpr : (window.devicePixelRatio || 1);
  const s = outW / crop.w;                      // CSS px na PDF bod
  const viewport = page.getViewport({ scale: s });

  canvas.width = Math.max(1, Math.round(outW * devicePixelRatio));
  canvas.height = Math.max(1, Math.round(outH * devicePixelRatio));
  canvas.style.width = `${outW}px`;
  canvas.style.height = `${outH}px`;

  const context = canvas.getContext('2d');
  context.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  // pdf.js skládá `transform` až za viewport transformaci → posun je
  // v CSS px výstupu (crop.x * s), ne v bodech.
  await page.render({
    canvasContext: context,
    viewport,
    transform: [1, 0, 0, 1, -crop.x * s, -crop.y * s],
  }).promise;
  return { width: outW, height: outH };
}

export function clearPdfCache() {
  _docs.clear();
}

/**
 * Přečte čísla taktů z TEXTOVÉ VRSTVY PDF.
 *
 * Proč: noty z notačních programů (LilyPond, Finale, Sibelius, MuseScore) mají
 * čísla taktů jako SKUTEČNÝ TEXT, ne jako obrázek — dají se tedy přečíst přesně.
 * Skeny textovou vrstvu nemají, tam vrátíme prázdné pole (a čísla se čtou
 * z ručních anotací nástroje „Čísla taktů“).
 *
 * Heuristika (naměřeno na reálných notách: číslo taktu je samostatné celé
 * číslo drobným písmem u LEVÉHO okraje, vždy na začátku systému):
 *  - text je jen číslice (příp. s tečkou na konci),
 *  - levý okraj: x < 14 % šířky stránky (čísla stránek jsou uprostřed, názvy
 *    skladeb velkým písmem → vypadnou),
 *  - malé písmo: velikost < 3 % šířky stránky,
 *  - na stránce musí čísla ve směru čtení RŮST (dolů po stránce), jinak jde
 *    o náhodné číslo (tempo, poznámka) a zahodí se.
 *
 * @param {*} song skladba s .data Blob
 * @param {(done:number,total:number)=>void} onProgress průběh po stránkách
 * @returns {Promise<Array<{n:number,page:number,y:number,src:'pdf'}>>}
 */
export async function readBarNumbers(song, onProgress) {
  const doc = await getDoc(song);
  const total = doc.numPages;
  const out = [];
  for (let pno = 1; pno <= total; pno++) {
    let page = null;
    try { page = await doc.getPage(pno); } catch (e) { continue; }
    const vp = page.getViewport({ scale: 1 });
    let tc = null;
    try { tc = await page.getTextContent(); } catch (e) { tc = null; }
    if (tc && tc.items && tc.items.length) {
      const cand = [];
      for (const item of tc.items) {
        const txt = String(item.str || '').trim();
        if (!/^\d{1,4}\.?$/.test(txt)) continue;
        const n = parseInt(txt, 10);
        if (!Number.isFinite(n)) continue;
        const tr = item.transform || [];
        const x = tr[4] || 0;
        const y = tr[5] || 0;
        const size = Math.hypot(tr[2] || 0, tr[3] || 0);
        if (x > vp.width * 0.14) continue;          // ne levý okraj
        if (size > vp.width * 0.03) continue;       // moc velké písmo
        cand.push({ n, x, y, size });
      }
      // Čtení shora dolů (PDF má y odspodu) a jen ta čísla, která v tom směru
      // rostou — přesně to dělají čísla taktů na začátcích systémů.
      cand.sort((a, b) => b.y - a.y);
      let last = -Infinity;
      for (const c of cand) {
        if (c.n <= last) continue;
        last = c.n;
        out.push({ n: c.n, page: pno - 1, y: 1 - (c.y / (vp.height || 1)), src: 'pdf' });
      }
    }
    if (onProgress) { try { onProgress(pno, total); } catch (e) { /* UI klidně spadne */ } }
  }
  return out;
}
/**
 * Vytištěná ČÍSLA v textové vrstvě JEDNÉ stránky, se souřadnicemi (Nov 2026).
 *
 * Pro nástroj „Lupa“ (v okně čísel taktů): uživatel klepne na místo, kde je
 * v originálním PDF VYTISKNUTÉ číslo taktu, a appka v okolí najde to číslo
 * a udělá z něj skrytý index pro skok na takt. Na rozdíl od `readBarNumbers()`
 * se tu NEfiltruje podle okraje ani rostoucí řady — hledá se číslo v okolí
 * klepnutí, takže může být kdekoli na stránce.
 *
 * Souřadnice jsou v BODECH PDF (scale 1) s y od SHORA — to je přesně soustava
 * anotační vrstvy (viewBox = cropBox, také v bodech PDF), takže se dají přímo
 * porovnávat s `toLayerCoords()`.
 *
 * @returns {Promise<Array<{n:number,x:number,yTop:number,w:number,h:number}>>}
 */
export async function readPageTextNumbers(song, pageNum) {
  const doc = await getDoc(song);
  const page = await doc.getPage(pageNum);
  const vp = page.getViewport({ scale: 1 });
  let tc = null;
  try { tc = await page.getTextContent(); } catch (e) { return []; }
  const out = [];
  for (const item of (tc && tc.items) || []) {
    const txt = String(item.str || '').trim();
    if (!/^\d{1,4}\.?$/.test(txt)) continue;
    const n = parseInt(txt, 10);
    if (!Number.isFinite(n)) continue;
    const tr = item.transform || [];
    const x = tr[4] || 0;
    const y = tr[5] || 0;
    const size = Math.hypot(tr[2] || 0, tr[3] || 0) || 10;
    out.push({
      n,
      x,
      yTop: (vp.height || 0) - y,          // účaří, ale y od SHORA
      w: Number(item.width) || size * 0.6 * txt.length,
      h: size,
    });
  }
  return out;
}
