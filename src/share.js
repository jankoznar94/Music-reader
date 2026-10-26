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
import { renderAnnotationLayer, ensureNotationFont, ANNOT_SCALE } from './annotRaster.js';

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
    canvas.toBlob(async (blob) => {
      if (!blob) { reject(new Error('Canvas se nepodařilo převést na PNG')); return; }
      resolve(new Uint8Array(await blob.arrayBuffer()));
    }, 'image/png');
  });
}

/**
 * Vypálí anotace do PDF a (volitelně) přibalí overlay jako přílohu.
 * @param {Uint8Array} pdfBytes původní PDF
 * @param {Object} opts { items, ref:{w,h}, helpers, scale, payload }
 * @returns {Promise<Uint8Array>}
 */
export async function burnOverlayIntoPdf(pdfBytes, opts) {
  const { items = [], ref, helpers = {}, payload = null } = opts || {};
  const scale = opts.scale || ANNOT_SCALE;
  const doc = await PDFDocument.load(pdfBytes, { ignoreEncryption: true });
  const pages = doc.getPages();

  if (items.length) {
    await ensureNotationFont();
    for (let i = 0; i < pages.length; i++) {
      const pageItems = items.filter((x) => x && x.page === i);
      if (!pageItems.length) continue;
      const canvas = document.createElement('canvas');
      renderAnnotationLayer(canvas, pageItems, {
        w: ref && ref.w, h: ref && ref.h, scale,
        displayText: helpers.displayText,
        borderRects: helpers.borderRects,
        noteStroke: helpers.noteStroke,
        noteFlipY: helpers.noteFlipY,
      });
      const png = await canvasToPngBytes(canvas);
      const img = await doc.embedPng(png);
      const page = pages[i];
      const key = page.node.newXObject('AnnotOverlay', img.ref);
      const m = rotationMatrix(page);
      page.pushOperators(
        pushGraphicsState(),
        concatTransformationMatrix(m[0], m[1], m[2], m[3], m[4], m[5]),
        drawObject(key),
        popGraphicsState(),
      );
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
