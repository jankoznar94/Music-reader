// src/pdf.js — obal nad pdf.js (renderování stránek do canvasu)
import * as pdfjsLib from 'pdfjs-dist';

// Worker pro pdf.js
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.mjs',
  import.meta.url
).toString();

// Cache načtených dokumentů (podle song id), aby se PDF neparsovalo opakovaně
const _docs = new Map();

async function getDoc(song) {
  if (_docs.has(song.id)) return _docs.get(song.id);
  const arrayBuffer = await song.data.arrayBuffer();
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

export function clearPdfCache() {
  _docs.clear();
}
