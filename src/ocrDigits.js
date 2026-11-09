// src/ocrDigits.js — ČTENÍ ČÍSEL Z OBRÁZKU (pro nástroj „Lupa“)
//
// Proč: stažené noty jsou často SKEN (bez textové vrstvy), takže se číslo taktu
// nedá přečíst z textu PDF — musí se přečíst z PIXELŮ. Jan (Nov 2026): „stáhnu
// noty z internetu s již očíslovanými takty a po kliknutí na číslo taktu si
// appka dané číslo přečte z PDF plátna a vytvoří pro něj neviditelný index“.
//
// Běží CELÉ LOKÁLNĚ (offline PWA): worker, wasm jádro i jazyková data leží
// v public/ocr/ a service worker je přednačítá. Nikam se nic neposílá.
//
// Model je angličtina OMEZENÁ na číslice (whitelist) — je to nejmenší rozumný
// kompromis: rozpoznává jen 0-9, takže v notách nečte písmena a je rychlejší.
import { createWorker } from 'tesseract.js';

const BASE = import.meta.env.BASE_URL || '/';
let _workerP = null;

export function ocrAssetsReady() { return !!_workerP; }

async function getWorker() {
  if (_workerP) return _workerP;
  _workerP = (async () => {
    const w = await createWorker('eng', 1, {
      workerPath: `${BASE}ocr/worker.min.js`,
      // Cesta končící na „js“ = načti PŘESNĚ tenhle soubor jádra (jinak by si
      // tesseract.js vybíral mezi simd/relaxedsimd variantami a museli bychom
      // vozit tři kopie wasm jádra).
      corePath: `${BASE}ocr/tesseract-core-lstm.wasm.js`,
      langPath: `${BASE}ocr`,
      cacheMethod: 'none',
      logger: () => {},
      errorHandler: () => {},
    });
    await w.setParameters({
      tessedit_char_whitelist: '0123456789',
      tessedit_pageseg_mode: '7',        // jeden řádek
      preserve_interword_spaces: '0',
    });
    return w;
  })().catch((e) => { _workerP = null; throw e; });
  return _workerP;
}

/**
 * Binarizace (Otsu) + bílý okraj — tesseract je na malé šedé číslice ze skenu
 * háklivý: na surovém výřezu dal u reálných not jistotu 11–63, po binarizaci
 * 91 se stejným textem. Okraj je potřeba, aby se číslice nedotýkaly hrany.
 * @param {HTMLCanvasElement} cv
 * @param {number} pad
 * @returns {HTMLCanvasElement}
 */
export function binarizeCanvas(cv, pad = 18) {
  const w = cv.width, h = cv.height;
  const src = cv.getContext('2d').getImageData(0, 0, w, h).data;
  const gray = new Uint8ClampedArray(w * h);
  const hist = new Array(256).fill(0);
  for (let i = 0, p = 0; i < src.length; i += 4, p++) {
    const g = (src[i] * 299 + src[i + 1] * 587 + src[i + 2] * 114) / 1000;
    gray[p] = g;
    hist[Math.round(g)]++;
  }
  // Otsu
  const total = gray.length;
  let sum = 0;
  for (let i = 0; i < 256; i++) sum += i * hist[i];
  let sumB = 0, wB = 0, best = -1, thr = 127;
  for (let t = 0; t < 256; t++) {
    wB += hist[t];
    if (!wB) continue;
    const wF = total - wB;
    if (!wF) break;
    sumB += t * hist[t];
    const mB = sumB / wB, mF = (sum - sumB) / wF;
    const between = wB * wF * (mB - mF) * (mB - mF);
    if (between > best) { best = between; thr = t; }
  }
  const out = document.createElement('canvas');
  out.width = w + pad * 2;
  out.height = h + pad * 2;
  const ctx = out.getContext('2d');
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, out.width, out.height);
  const img = ctx.createImageData(w, h);
  for (let p2 = 0, i = 0; p2 < gray.length; p2++, i += 4) {
    const v = gray[p2] < thr ? 0 : 255;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  ctx.putImageData(img, pad, pad);
  return out;
}

/**
 * Přečte číslice z canvasu (výřez not).
 * @param {HTMLCanvasElement} canvas
 * @returns {Promise<{digits:string, confidence:number}>}
 */
export async function ocrDigitsFromCanvas(canvas) {
  const w = await getWorker();
  const res = await w.recognize(canvas);
  const data = res && res.data ? res.data : {};
  return {
    digits: String(data.text || '').replace(/[^0-9]/g, ''),
    confidence: Number(data.confidence) || 0,
  };
}
