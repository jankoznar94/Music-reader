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
