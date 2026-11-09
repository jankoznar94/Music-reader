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
 * Šedotónová data canvasu + histogram (jeden `getImageData` na celou oblast).
 * @param {HTMLCanvasElement} cv
 * @returns {{g:Uint8ClampedArray,w:number,h:number,hist:Uint32Array}}
 */
function grayOf(cv) {
  const w = cv.width, h = cv.height;
  const src = cv.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  const g = new Uint8ClampedArray(w * h);
  const hist = new Uint32Array(256);
  for (let i = 0, p = 0; p < w * h; p++, i += 4) {
    const v = (src[i] * 299 + src[i + 1] * 587 + src[i + 2] * 114) / 1000;
    g[p] = v;
    hist[v | 0]++;
  }
  return { g, w, h, hist };
}

/** Otsuův práh z histogramu. */
function otsuFromHist(hist, total) {
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
  return thr;
}

/**
 * Najde SHLUKY ČÍSLIC v oblasti (souvislé komponenty + seskupení na účaří).
 *
 * Proč ne rovnou OCR celého okna: kolem čísla taktu bývá taktová čára, začátek
 * osnovy a svorka systému. Tesseract si z těch svislic dělá „1" — Janův případ
 * „místo 9 přečte 19" (naměřeno: široký výřez 48×22 bodu dal u devítky „4"
 * s jistotou 58, úzké okno kolem skutečných číslic „9" s jistotou 95).
 * Komponenty výšky písmen (3–12 bodu) a šířky do 12 bodu jsou číslice; dlouhé
 * vodorovné linky osnov a svislé taktové čáry vypadnou filtrem.
 *
 * @param {HTMLCanvasElement} cv oblast (už vykreslená, NEBINARIZOVANÁ)
 * @param {number} pxPerPt skutečné pixely canvasu na PDF bod
 * @param {{x:number,y:number}} tap bod klepnutí v pixelech canvasu
 * @returns {{clusters:Array<{x0:number,y0:number,x1:number,y1:number,n:number,d:number,h:number}>,thr:number}}
 *          boxy v PIXELECH canvasu, seřazené od nejbližšího ke klepnutí; `thr` je
 *          Otsuův práh CELÉ oblasti — použij ho i pro binarizaci výřezu, jinak
 *          si malý výřez spočítá práh z pár pixelů a číslice se rozpadne.
 */
export function findDigitClusters(cv, pxPerPt, tap, opt = {}) {
  const minHpt = opt.minHpt == null ? 3.0 : opt.minHpt;
  const maxHpt = opt.maxHpt == null ? 12.0 : opt.maxHpt;
  const maxWpt = opt.maxWpt == null ? 12.0 : opt.maxWpt;
  const { g, w, h, hist } = grayOf(cv);
  const thr = otsuFromHist(hist, w * h);
  const mask = new Uint8Array(w * h);
  let ink = 0;
  for (let p = 0; p < w * h; p++) {
    if (g[p] < thr) { mask[p] = 1; ink++; }
  }
  const seen = new Uint8Array(w * h);
  const stack = new Int32Array(w * h);
  const minH = minHpt * pxPerPt, maxH = maxHpt * pxPerPt;
  const minW = 0.7 * pxPerPt, maxW = maxWpt * pxPerPt;
  const comps = [];
  let compCount = 0, maxHpx = 0;
  for (let start = 0; start < w * h; start++) {
    if (!mask[start] || seen[start]) continue;
    let sp = 0;
    stack[sp++] = start;
    seen[start] = 1;
    let x0 = w, y0 = h, x1 = -1, y1 = -1, area = 0;
    while (sp) {
      const p = stack[--sp];
      const x = p % w, y = (p - x) / w;
      area++;
      if (x < x0) x0 = x; if (x > x1) x1 = x;
      if (y < y0) y0 = y; if (y > y1) y1 = y;
      for (let dy = -1; dy <= 1; dy++) {
        const yy = y + dy;
        if (yy < 0 || yy >= h) continue;
        for (let dx = -1; dx <= 1; dx++) {
          const xx = x + dx;
          if (xx < 0 || xx >= w) continue;
          const q = yy * w + xx;
          if (mask[q] && !seen[q]) { seen[q] = 1; stack[sp++] = q; }
        }
      }
    }
    const cw = x1 - x0 + 1, ch = y1 - y0 + 1;
    compCount++;
    if (ch > maxHpx) maxHpx = ch;
    if (area < 12 || ch < minH || ch > maxH || cw < minW || cw > maxW) continue;
    if (cw / ch > 6) continue;                 // vodorovná čárka
    comps.push({ x0, y0, x1, y1, base: y1, ch });
  }
  // Seskupení na stejné účaří: mezera mezi číslicemi je zlomek výšky písmen.
  comps.sort((a, b) => (a.base - b.base) || (a.x0 - b.x0));
  const groups = [];
  for (const c of comps) {
    let hit = null;
    for (const gr of groups) {
      const last = gr[gr.length - 1];
      const sameBase = Math.abs(c.base - last.base) < 0.35 * last.ch;
      const gap = c.x0 - last.x1 - 1;
      if (sameBase && gap > -0.8 * c.ch && gap < 0.7 * c.ch) { hit = gr; break; }
    }
    if (hit) hit.push(c); else groups.push([c]);
  }
  const out = [];
  for (const gr of groups) {
    const x0 = Math.min(...gr.map(c => c.x0)), x1 = Math.max(...gr.map(c => c.x1));
    const y0 = Math.min(...gr.map(c => c.y0)), y1 = Math.max(...gr.map(c => c.y1));
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    out.push({ x0, y0, x1, y1, n: gr.length, h: (y1 - y0 + 1) / pxPerPt,
               d: Math.hypot(cx - tap.x, cy - tap.y) });
  }
  out.sort((a, b) => a.d - b.d);
  return {
    clusters: out, thr,
    stats: {
      comps: compCount,
      inkPct: Math.round((ink / (w * h)) * 1000) / 10,
      maxHpt: Math.round((maxHpx / pxPerPt) * 10) / 10,
      pxW: w, pxH: h,
    },
  };
}

/**
 * Kopie výřezu canvasu (v pixelech) s bílým okrajem — vstup pro OCR.
 * @param {HTMLCanvasElement} cv
 * @param {{x:number,y:number,w:number,h:number}} box v pixelech canvasu
 * @param {number} pad bílý okraj v pixelech
 */
export function cropCanvas(cv, box, pad = 8) {
  const x0 = Math.max(0, Math.round(box.x)), y0 = Math.max(0, Math.round(box.y));
  const x1 = Math.min(cv.width, Math.round(box.x + box.w));
  const y1 = Math.min(cv.height, Math.round(box.y + box.h));
  const out = document.createElement('canvas');
  out.width = Math.max(1, x1 - x0) + pad * 2;
  out.height = Math.max(1, y1 - y0) + pad * 2;
  const ctx = out.getContext('2d');
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, out.width, out.height);
  ctx.drawImage(cv, x0, y0, Math.max(1, x1 - x0), Math.max(1, y1 - y0), pad, pad,
                Math.max(1, x1 - x0), Math.max(1, y1 - y0));
  return out;
}

/**
 * Ohraničení INKOUSTU (černých pixelů) v už zbinarizovaném canvasu.
 * @param {HTMLCanvasElement} cv
 * @returns {{x:number,y:number,w:number,h:number}|null}
 */
export function inkBox(cv) {
  const w = cv.width, h = cv.height;
  const d = cv.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  let x0 = w, y0 = h, x1 = -1, y1 = -1;
  for (let y = 0, i = 0; y < h; y++) {
    for (let x = 0; x < w; x++, i += 4) {
      if (d[i] < 128) {
        if (x < x0) x0 = x; if (x > x1) x1 = x;
        if (y < y0) y0 = y; if (y > y1) y1 = y;
      }
    }
  }
  if (x1 < 0) return null;
  return { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
}

/**
 * Připraví výřez pro tesseract: okraj kolem inkoustu + NORMALIZOVANÁ VÝŠKA.
 *
 * Naměřeno na skutečných výřezech z appky (5 čísel, 18 kombinací): bez
 * normalizace výšky se správně přečtou 4 z 5, s normalizací na 96 px 5 z 5
 * (Ø jistota 92). Tesseract je háklivý na to, jak velký podíl obrazu číslice
 * zaujímá — samotné bílé okolí (dřívější `pad = 18`) z devítky udělalo „4“.
 *
 * @param {HTMLCanvasElement} cv zbinarizovaný výřez
 * @param {{x:number,y:number,w:number,h:number}} box inkoust
 * @param {number} margin okraj jako zlomek výšky inkoustu
 * @param {number} targetH cílová výška výřezu v px
 */
export function normalizeForOcr(cv, box, margin = 0.6, targetH = 96) {
  const pad = Math.max(2, Math.round(box.h * margin));
  const x0 = Math.max(0, box.x - pad), y0 = Math.max(0, box.y - pad);
  const x1 = Math.min(cv.width, box.x + box.w + pad);
  const y1 = Math.min(cv.height, box.y + box.h + pad);
  const sw = Math.max(1, x1 - x0), sh = Math.max(1, y1 - y0);
  const sc = targetH / sh;
  const out = document.createElement('canvas');
  out.width = Math.max(1, Math.round(sw * sc));
  out.height = Math.max(1, Math.round(sh * sc));
  const ctx = out.getContext('2d');
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, out.width, out.height);
  ctx.drawImage(cv, x0, y0, sw, sh, 0, 0, out.width, out.height);
  return out;
}

/**
 * Binarizace (Otsu) + bílý okraj — tesseract je na malé šedé číslice ze skenu
 * háklivý: na surovém výřezu dal u reálných not jistotu 11–63, po binarizaci
 * 91 se stejným textem. Okraj je potřeba, aby se číslice nedotýkaly hrany.
 * @param {HTMLCanvasElement} cv
 * @param {number} pad
 * @returns {HTMLCanvasElement}
 */
export function binarizeCanvas(cv, pad = 18, thrIn = null) {
  const w = cv.width, h = cv.height;
  const src = cv.getContext('2d').getImageData(0, 0, w, h).data;
  const gray = new Uint8ClampedArray(w * h);
  const hist = new Array(256).fill(0);
  for (let i = 0, p = 0; i < src.length; i += 4, p++) {
    const g = (src[i] * 299 + src[i + 1] * 587 + src[i + 2] * 114) / 1000;
    gray[p] = g;
    hist[Math.round(g)]++;
  }
  let thr = thrIn;
  // Otsu — jen když práh nedodá volající. U DROBNÉHO výřezu (okno s jedním
  // číslem a bílým okolím) je histogram skoro celý bílý a Otsu práh spadne
  // nízko; číslice se pak rozpadne a tesseract nepřečte nic (naměřeno:
  // str. 2 „5“ → prázdno, po použití prahu celé oblasti „5“ s jistotou 84).
  if (thr == null) {
    const total = gray.length;
    let sum = 0;
    for (let i = 0; i < 256; i++) sum += i * hist[i];
    let sumB = 0, wB = 0, best = -1;
    thr = 127;
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
 * Rozdělí připravený výřez na JEDNOTLIVÉ ČÍSLICE podle svislých mezer a vrátí
 * jejich canvasu (normalizované na stejnou výšku). Používá se u dvouciferných
 * čísel: tesseract v režimu „jeden řádek“ zaměňuje 5/3 (naměřeno „75“ → „73“
 * s jistotou 83, zatímco samostatná pětka i sedmička se čtou bezpečně).
 * @param {HTMLCanvasElement} cv zbinarizovaný, normalizovaný výřez
 * @returns {HTMLCanvasElement[]} prázdné pole, když se rozdělit nedá
 */
export function splitDigitCells(cv, expected = 0) {
  const w = cv.width, h = cv.height;
  const d = cv.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  const inkCol = new Uint16Array(w);
  for (let x = 0; x < w; x++) {
    let ink = 0;
    for (let y = 0; y < h; y++) if (d[(y * w + x) * 4] < 128) ink++;
    inkCol[x] = ink;
  }
  // sloupce s inkoustem → souvislé bloky (mezera aspoň 1 px)
  const blocks = [];
  let x0 = -1, gap = 0;
  for (let x = 0; x < w; x++) {
    if (inkCol[x] > 0) {
      if (x0 < 0) x0 = x;
      gap = 0;
    } else if (x0 >= 0) {
      gap++;
      if (gap >= 1) {
        blocks.push([x0, x - gap]);
        x0 = -1;
        gap = 0;
      }
    }
  }
  if (x0 >= 0) blocks.push([x0, w - 1]);
  // Jen skutečné číslice: blok musí být aspoň 3 px široký.
  let cells = blocks.filter(([a, b]) => b - a >= 3);
  // Číslice se na skenu často DOTÝKAJÍ (naměřeno: „75“ i „78“ = jeden blok),
  // takže když je bloků méně, než kolik číslic jsme přečetli celkem, rozdělí se
  // inkoustový rozsah rovnoměrně (v notách mají číslice stejnou šířku) a řez se
  // posune do nejužšího místa v okolí.
  if (expected >= 2 && cells.length < expected) {
    const a = Math.min(...cells.map(c => c[0]));
    const b = Math.max(...cells.map(c => c[1]));
    const span = b - a + 1;
    const cuts = [a];
    for (let i = 1; i < expected; i++) {
      let best = a + Math.round((span * i) / expected);
      let bestInk = Infinity;
      const lo = Math.max(a + 1, best - Math.round(span * 0.15));
      const hi = Math.min(b - 1, best + Math.round(span * 0.15));
      for (let x = lo; x <= hi; x++) if (inkCol[x] < bestInk) { bestInk = inkCol[x]; best = x; }
      cuts.push(best);
    }
    cells = cuts.map((c, i) => [c, (i + 1 < cuts.length ? cuts[i + 1] - 1 : b)]);
  }
  if (cells.length < 2) return [];
  return cells.map(([a, b]) => {
    const bw = b - a + 1;
    const out = document.createElement('canvas');
    out.width = Math.max(8, Math.round(bw * (96 / h)) + 8);
    out.height = 96 + 8;
    const ctx = out.getContext('2d');
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, out.width, out.height);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(cv, a, 0, bw, h, 4, 4, Math.round(bw * (96 / h)), 96);
    return out;
  });
}

/**
 * Přečte číslice z canvasu (výřez not).
 * @param {HTMLCanvasElement} canvas
 * @returns {Promise<{digits:string, confidence:number}>}
 */
export async function ocrDigitsFromCanvas(canvas, psm) {
  const w = await getWorker();
  if (psm) await w.setParameters({ tessedit_pageseg_mode: String(psm) });
  const res = await w.recognize(canvas);
  const data = res && res.data ? res.data : {};
  // psm se nastavuje globálne na workeru — po dočtení ho vrať na „jeden řádek“.
  if (psm) await w.setParameters({ tessedit_pageseg_mode: '7' });
  return {
    digits: String(data.text || '').replace(/[^0-9]/g, ''),
    confidence: Number(data.confidence) || 0,
  };
}

/**
 * Přečte číslo taktu PO JEDNOTLIVÝCH ČÍSLICÍCH (psm 10) a spojí je.
 * @param {HTMLCanvasElement} prepared zbinarizovaný, normalizovaný výřez
 * @returns {Promise<{digits:string, confidence:number, cells:number}>}
 */
export async function ocrDigitsPerCell(prepared, expected = 0) {
  const cells = splitDigitCells(prepared, expected);
  if (!cells.length) return { digits: '', confidence: 0, cells: 0 };
  let digits = '', conf = 0;
  for (const c of cells) {
    const r = await ocrDigitsFromCanvas(c, 10);
    if (!r.digits || r.digits.length !== 1) return { digits: '', confidence: 0, cells: cells.length };
    digits += r.digits;
    conf += Number(r.confidence) || 0;
  }
  return { digits, confidence: conf / cells.length, cells: cells.length };
}
