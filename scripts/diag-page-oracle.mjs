// ORACLE: nezávislé spočítání taktových čar v systému.
// Pro každý systém najde sloupce, které jsou tmavé PŘES CELÝ systém (včetně
// mezer mezi osnovami) — to jsou taktové čary sazby, ne nožičky.
// Slouží jen k porovnání s `detectBarlines`; nic v appce nemění.
//
// node scripts/diag-page-oracle.mjs <pdf> <strana> [strana…]
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import fs from 'node:fs';

globalThis.document = { createElement: () => createCanvas(1, 1) };
globalThis.window = globalThis;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);

const { detectPageSystems } = await import('../src/barLines.js');

const [, , file, ...pageArgs] = process.argv;
const pages = pageArgs.map(Number);
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data, useSystemFonts: true }).promise;
const PPT = 5, MAX_PX = 12e6;

function otsu(hist, total) {
  let sum = 0;
  for (let i = 0; i < 256; i++) sum += i * hist[i];
  let sumB = 0, wB = 0, best = -1, thr = 127;
  for (let t = 0; t < 256; t++) {
    wB += hist[t]; if (!wB) continue;
    const wF = total - wB; if (!wF) break;
    sumB += t * hist[t];
    const mB = sumB / wB, mF = (sum - sumB) / wF;
    const v = wB * wF * (mB - mF) * (mB - mF);
    if (v > best) { best = v; thr = t; }
  }
  return thr;
}

function maskOf(cv) {
  const w = cv.width, h = cv.height;
  const d = cv.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  const gray = new Uint8Array(w * h);
  for (let i = 0, p = 0; p < w * h; p++, i += 4) {
    gray[p] = (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000;
  }
  const mask = new Uint8Array(w * h);
  for (let y0 = 0; y0 < h; y0 += 64) {
    const y1 = Math.min(h, y0 + 64);
    const hist = new Uint32Array(256);
    for (let y = y0; y < y1; y++) { const off = y * w; for (let x = 0; x < w; x++) hist[gray[off + x] | 0]++; }
    const thr = Math.min(235, otsu(hist, (y1 - y0) * w) + 35);
    for (let y = y0; y < y1; y++) {
      const off = y * w;
      for (let x = 0; x < w; x++) if (gray[off + x] < thr) mask[off + x] = 1;
    }
  }
  return { w, h, mask };
}

for (const pageNum of pages) {
  const page = await doc.getPage(pageNum);
  const base = page.getViewport({ scale: 1 });
  const pw = base.width, ph = base.height;
  let scale = PPT;
  if (pw * ph * scale * scale > MAX_PX) scale = Math.sqrt(MAX_PX / (pw * ph));
  const vp = page.getViewport({ scale });
  const cv = createCanvas(Math.round(vp.width), Math.round(vp.height));
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height);
  await page.render({ canvasContext: ctx, viewport: vp }).promise;
  const pxPerPt = cv.width / pw;
  const d = detectPageSystems(cv, pxPerPt, {});
  const { w, mask } = maskOf(cv);
  const rows = d.rowsPt;
  console.log(`=== PDF ${pageNum}`);
  (d.systems || []).forEach((s, si) => {
    const a = s.sysA, b = s.sysB;
    const y0 = Math.round(rows[a][0] * pxPerPt), y1 = Math.round(rows[b][1] * pxPerPt);
    const need = y1 - y0 + 1;
    // plné sloupce přes CELÝ systém
    const cols = [];
    for (let x = 0; x < w; x++) {
      let ink = 0;
      for (let y = y0; y <= y1; y++) ink += mask[y * w + x];
      if (ink / need >= 0.97) cols.push(x);
    }
    const groups = [];
    for (const x of cols) {
      const g = groups[groups.length - 1];
      if (g && x - g[g.length - 1] <= 2) g.push(x); else groups.push([x]);
    }
    const thick = groups.filter((g) => g.length >= 1 && g.length <= Math.max(2, 0.9 * (rows[a][1] - rows[a][0]) / 4 * 0.5));
    const list = groups.map((g) => [+(((g[0] + g[g.length - 1]) / 2) / pxPerPt).toFixed(1), g.length]);
    console.log(`  sys${si + 1} osnov ${s.staves} bars=${s.bars} det=${JSON.stringify(s.lines)} open=${s.opening == null ? null : +(s.opening / pxPerPt).toFixed(1)} close=${s.closing == null ? null : +(s.closing / pxPerPt).toFixed(1)}`);
    console.log(`         full-cols=${JSON.stringify(list)}`);
  });
}
