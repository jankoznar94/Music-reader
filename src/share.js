// src/share.js — sdílení not i s poznámkami
//
// Dvě cesty (uživatel si vybírá podle toho, komu noty posílá):
//   1) VYPÁLENÍ  — anotace se nakreslí do stránek PDF. Výsledek otevře kdokoli
//      (i bez aplikace) a vypadá jako popsané noty. Navíc se do PDF přibalí
//      skrytá příloha s overlay daty, takže uživatel naší aplikace si poznámky
//      naimportuje zpět jako editovatelné.
//   2) BALÍČEK   — čisté (nepopsané) PDF + overlay.json v jednom .zip. Pro
//      tisk nebo pro kolegu, který si noty chce popsat sám; data jsou přesná
//      a nic se nerasterizuje.
//
// Overlay data = anotace + skoky + záložky + odebrané stránky + rám. Díky tomu
// příjemce nevidí jen čáry, ale má stejné noty „jak je autor slyší“.

import {
  PDFDocument, PDFName, decodePDFRawStream,
  pushGraphicsState, popGraphicsState, concatTransformationMatrix, drawObject,
} from 'pdf-lib';
import { zipSync, unzipSync, strToU8, strFromU8 } from 'fflate';
import { renderAnnotationLayer, ensureNotationFont } from './annotRaster.js';

export const OVERLAY_FORMAT = 'harlequin-music-reader/overlay';
export const OVERLAY_VERSION = 1;
const ATTACH_NAME = 'overlay.json';
const OVERLAY_SUFFIX = '.overlay.json';

// --- jména souborů ---
export function safeBaseName(name) {
  return String(name || 'noty')
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 80) || 'noty';
}

// --- overlay data ---
export function buildOverlayPayload({ song, annotations, jumps, bookmarks, bmManualOrder }) {
  return {
    format: OVERLAY_FORMAT,
    version: OVERLAY_VERSION,
    createdAt: new Date().toISOString(),
    song: {
      name: song.name || '',
      composer: song.composer || '',
      pages: song.pages || 0,
      hiddenPages: Array.isArray(song.hiddenPages) ? song.hiddenPages : [],
      frame: !!song.frame,
    },
    annotations: {
      ref: annotations.ref || null,
      items: annotations.items || [],
    },
    jumps: jumps || [],
    bookmarks: bookmarks || [],
    bookmarksManualOrder: !!bmManualOrder,
  };
}

// --- vypálení do PDF ---

// Kolik pixelů smí mít jedna vypalovaná stránka. Anotace se kreslí do canvasu
// v "ref px" (souřadnice, které má stránka na displeji) — na telefonu je to
// klidně 1200×1900 ref px, takže 3× zoom udělal canvas 3600×5700 = 20 M px.
// Android Chrome takový canvas buď vyplní, nebo `toBlob` NIKDY nezavolá —
// a protože se čeká na callback, tlačítko zůstalo šedé a nestalo se nic.
// Proto: 1) rastr se počítá z rozměru STRÁNKY v bodech (~300 dpi), ne z ref px;
//        2) plocha stránky má tvrdý strop;
//        3) canvas se po každé stránce uvolní.
const TARGET_DPI = 300;
const MAX_PAGE_PX = 8_000_000;      // ~8 M px na stránku = bezpečné i na mobilu
const MAX_PAGE_SIDE = 4200;         // px na delší stranu
const PNG_TIMEOUT_MS = 12000;       // když toBlob mlčí, jde se na synchronní cestu

function rotationMatrix(page) {
  const angle = ((page.getRotation().angle % 360) + 360) % 360;
  const W = page.getWidth();
  const H = page.getHeight();
  // Matice mapuje jednotkový čtverec obrázku na stránku v ORIENTACI, kterou
  // čtenář vidí (PDF /Rotate) — bez toho by se poznámky na otočené stránce
  // posunuly o 90°.
  if (angle === 90) return [0, H, -W, 0, W, 0];
  if (angle === 180) return [-W, 0, 0, -H, W, H];
  if (angle === 270) return [0, -H, W, 0, 0, H];
  return [W, 0, 0, H, 0, 0];
}

function canvasToPngBytes(canvas) {
  return new Promise((resolve, reject) => {
    let done = false;
    const finish = (bytes) => { if (done) return; done = true; resolve(bytes); };
    const fail = (msg) => { if (done) return; done = true; reject(new Error(msg)); };

    const syncFallback = () => {
      // Android Chrome občas `toBlob` vůbec nezavolá (velký canvas / málo
      // paměti). Synchronní převod sice chvíli blokuje, ale vždy vrátí data.
      try {
        finish(dataUrlToBytes(canvas.toDataURL('image/png')));
      } catch (e) {
        fail('Canvas se nepodařilo převést na PNG');
      }
    };

    let timer = null;
    try {
      canvas.toBlob(async (blob) => {
        if (done) return;
        if (timer) clearTimeout(timer);
        if (!blob) { syncFallback(); return; }
        try {
          finish(new Uint8Array(await blob.arrayBuffer()));
        } catch (e) {
          fail('Canvas se nepodařilo převést na PNG');
        }
      }, 'image/png');
    } catch (e) {
      syncFallback();
      return;
    }
    timer = setTimeout(() => { if (!done) syncFallback(); }, PNG_TIMEOUT_MS);
  });
}

function dataUrlToBytes(dataUrl) {
  const comma = dataUrl.indexOf(',');
  if (comma < 0) throw new Error('Neplatná data URL');
  const b64 = dataUrl.slice(comma + 1);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/**
 * Jak velký rastr pro tuhle stránku? Vychází z rozměru stránky v bodech
 * (~300 dpi), ne z "ref px" — ty jsou na mobilu mnohem větší a canvas pak
 * přeteče limity prohlížeče. Výsledek se navíc vejde do MAX_PAGE_PX.
 */
function pageRasterScale(page, ref) {
  const angle = ((page.getRotation().angle % 360) + 360) % 360;
  const visW = (angle === 90 || angle === 270) ? page.getHeight() : page.getWidth();
  const visH = (angle === 90 || angle === 270) ? page.getWidth() : page.getHeight();
  const refW = (ref && ref.w > 0) ? ref.w : visW;
  const refH = (ref && ref.h > 0) ? ref.h : visH;
  let scale = (TARGET_DPI / 72) * (visW / refW);
  // strop na plochu i na delší stranu (prohlížeče mají limity na canvas)
  const area = refW * scale * refH * scale;
  if (area > MAX_PAGE_PX) scale *= Math.sqrt(MAX_PAGE_PX / area);
  const longSide = Math.max(refW * scale, refH * scale);
  if (longSide > MAX_PAGE_SIDE) scale *= MAX_PAGE_SIDE / longSide;
  return Math.max(0.5, scale);
}

/** Nechá prohlížeč překreslit hlášku o průběhu (jinak mobil zamrzne na místě). */
function nextFrame() {
  return new Promise((r) => {
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(() => r());
    else setTimeout(r, 0);
  });
}

/**
 * Vypálí anotace do PDF a (volitelně) přibalí overlay jako přílohu.
 * @param {Uint8Array} pdfBytes původní PDF
 * @param {Object} opts { items, ref:{w,h}, helpers, dpi, payload, onProgress }
 * @returns {Promise<Uint8Array>}
 */
export async function burnOverlayIntoPdf(pdfBytes, opts) {
  const { items = [], ref, helpers = {}, payload = null, onProgress = null } = opts || {};
  const doc = await PDFDocument.load(pdfBytes, { ignoreEncryption: true });
  const pages = doc.getPages();

  const jobs = [];
  if (items.length) {
    for (let i = 0; i < pages.length; i++) {
      const pageItems = items.filter((x) => x && x.page === i);
      if (pageItems.length) jobs.push({ index: i, pageItems });
    }
  }

  if (jobs.length) {
    await ensureNotationFont();
    const canvas = document.createElement('canvas');
    for (let k = 0; k < jobs.length; k++) {
      const { index, pageItems } = jobs[k];
      const page = pages[index];
      const scale = pageRasterScale(page, ref);
      renderAnnotationLayer(canvas, pageItems, {
        w: ref && ref.w, h: ref && ref.h, scale,
        displayText: helpers.displayText,
        borderRects: helpers.borderRects,
        noteStroke: helpers.noteStroke,
        noteFlipY: helpers.noteFlipY,
      });
      const png = await canvasToPngBytes(canvas);
      // Paměť se uvolní DŘÍV, než se začne kreslit další stránka — na mobilu
      // jinak součet canvasů shodí renderer.
      canvas.width = 0;
      canvas.height = 0;
      const img = await doc.embedPng(png);
      const key = page.node.newXObject('AnnotOverlay', img.ref);
      const m = rotationMatrix(page);
      page.pushOperators(
        pushGraphicsState(),
        concatTransformationMatrix(m[0], m[1], m[2], m[3], m[4], m[5]),
        drawObject(key),
        popGraphicsState(),
      );
      if (onProgress) {
        try { onProgress(k + 1, jobs.length, { page: index + 1, scale }); } catch { /* UI nesmí shodit export */ }
      }
      await nextFrame();
    }
  }

  // Prázdný overlay nemá smysl přibalu­ovat — vypálené noty bez poznámek
  // mají být prostě kopie původního PDF.
  const hasData = payload && (
    (payload.annotations?.items?.length || 0) > 0
    || (payload.jumps?.length || 0) > 0
    || (payload.bookmarks?.length || 0) > 0
  );
  if (hasData) await attachOverlayToDoc(doc, payload);

  return doc.save();
}

export async function attachOverlayToDoc(doc, payload) {
  await doc.attach(strToU8(JSON.stringify(payload)), ATTACH_NAME, {
    mimeType: 'application/json',
    description: 'Harlequin Music Reader – overlay (anotace, skoky, záložky)',
  });
  doc.setKeywords(['Harlequin Music Reader', 'overlay']);
  doc.setSubject('Noty s poznámkami (overlay přiložen)');
}

/** Vypálené PDF včetně skryté přílohy (overlay dat). */
export async function exportBurnedPdf(pdfBytes, opts) {
  return burnOverlayIntoPdf(pdfBytes, opts);
}

// --- čtení přílohy z PDF ---
function readEmbeddedJson(bytes) {
  return PDFDocument.load(bytes, { ignoreEncryption: true }).then((doc) => {
    const ctx = doc.context;
    try {
      const names = ctx.lookup(doc.catalog.get(PDFName.of('Names')));
      if (!names || typeof names.get !== 'function') return null;
      const ef = ctx.lookup(names.get(PDFName.of('EmbeddedFiles')));
      if (!ef || typeof ef.get !== 'function') return null;
      const arr = ctx.lookup(ef.get(PDFName.of('Names')));
      if (!arr || typeof arr.size !== 'function') return null;
      for (let i = 0; i + 1 < arr.size(); i += 2) {
        const spec = ctx.lookup(arr.get(i + 1));
        if (!spec || typeof spec.get !== 'function') continue;
        const efDict = ctx.lookup(spec.get(PDFName.of('EF')));
        if (!efDict || typeof efDict.get !== 'function') continue;
        const stream = ctx.lookup(efDict.get(PDFName.of('F')));
        if (!stream || typeof stream.getContents !== 'function') continue;
        const raw = stream.getContents();
        const decoded = stream.dict && stream.dict.get(PDFName.of('Filter'))
          ? decodePDFRawStream(stream).decode()
          : raw;
        const text = strFromU8(decoded instanceof Uint8Array ? decoded : new Uint8Array(decoded));
        if (!text || !text.includes(OVERLAY_FORMAT)) continue;
        return JSON.parse(text);
      }
      return null;
    } catch {
      return null;
    }
  });
}

/** Přečte overlay z PDF; null když tam žádný není. */
export async function readOverlayFromPdf(bytes) {
  const payload = await readEmbeddedJson(bytes);
  return payload && payload.format === OVERLAY_FORMAT ? payload : null;
}

// --- balíček PDF + JSON ---
export function buildShareZip(pdfBytes, payload, baseName) {
  const base = safeBaseName(baseName);
  const files = {};
  files[`${base}.pdf`] = pdfBytes;
  files[`${base}${OVERLAY_SUFFIX}`] = strToU8(JSON.stringify(payload, null, 1));
  return zipSync(files, { level: 0 }); // PDF je už komprimované, zip jen obal
}

export function readShareZip(bytes) {
  const files = unzipSync(bytes);
  let pdf = null, payload = null;
  for (const [name, data] of Object.entries(files)) {
    const lower = name.toLowerCase();
    if (!pdf && lower.endsWith('.pdf')) pdf = data;
    else if (!payload && lower.endsWith('.json')) {
      try {
        const obj = JSON.parse(strFromU8(data));
        if (obj && obj.format === OVERLAY_FORMAT) payload = obj;
      } catch { /* cizí JSON ignorujeme */ }
    }
  }
  return { pdf, payload };
}

/** Je tohle naše overlay? (kontrola formátu před importem) */
export function isOverlayPayload(obj) {
  return !!obj && obj.format === OVERLAY_FORMAT && Array.isArray(obj.annotations?.items);
}

// --- stažení souboru ---
export function downloadBytes(bytes, filename, mime) {
  const blob = new Blob([bytes], { type: mime || 'application/octet-stream' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
