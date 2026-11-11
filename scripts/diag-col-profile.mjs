// Profil sloupců: jak moc je který svislý sloupec "plný" v jednotlivých osnovách
// a v mezerách mezi nimi. Slouží k rozboru chybějících/falešných taktových čar.
// node scripts/diag-col-profile.mjs <pdf> <strana> <systemIdx> [x0 x1]
// Strana = index v PDF (1-based), systemIdx = 0-based.
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import fs from 'node:fs';

globalThis.document = { createElement: () => createCanvas(1, 1) };
globalThis.window = globalThis;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);

const { detectPageSystems } = await import('../src/barLines.js');

function otsu(hist, total) {
  let sum = 0;
  for (let i = 0; i < 256; i++) sum += i * hist[i];
  let sumB = 0, wB = 0, best = 0, thr = 128;
  for (let i = 0; i < 256; i++) {
    wB += hist[i]; if (!wB) continue;
    const wF = total - wB; if (!wF) break;
    sumB += i * hist[i];
    const mB = sumB / wB, mF = (sum - sumB) / wF;
    const v = wB * wF * (mB - mF) * (mB - mF);
    if (v > best) { best = v; thr = i; }
  }
  return thr;
}
function buildMask(cv) {
  const w = cv.width, h = cv.height;
  const d = cv.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  const gray = new Uint8Array(w * h);
  for (let i = 0, p = 0; p < w * h; p++, i += 4)
    gray[p] = (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000;
  const mask = new Uint8Array(w * h);
  const BLOCK = 64;
  for (let y0 = 0; y0 < h; y0 += BLOCK) {
    const y1 = Math.min(h, y0 + BLOCK);
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

const [, , file, pageStr, sysStr, x0s, x1s] = process.argv;
const pageNo = Number(pageStr), sysIdx = Number(sysStr);
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data, useSystemFonts: true }).promise;
const page = await doc.getPage(pageNo);
const base = page.getViewport({ scale: 1 });
const PPT = 5, MAX_PX = 12e6;
let scale = PPT;
if (base.width * base.height * scale * scale > MAX_PX) scale = Math.sqrt(MAX_PX / (base.width * base.height));
const vp = page.getViewport({ scale });
const cv = createCanvas(Math.round(vp.width), Math.round(vp.height));
const ctx = cv.getContext('2d');
ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height);
await page.render({ canvasContext: ctx, viewport: vp }).promise;
const pxPerPt = cv.width / base.width;

const d = detectPageSystems(cv, pxPerPt, {});
const sys = d.systems[sysIdx];
if (!sys) { console.log('system nenalezen, systems=' + d.systems.length); process.exit(1); }
const rowsPt = d.rowsPt;
const staffRows = [];
for (let i = sys.sysA; i <= sys.sysB; i++) staffRows.push(rowsPt[i]);
const { w, h, mask } = buildMask(cv);

const x0 = x0s != null ? Math.round(Number(x0s) * pxPerPt) : 0;
const x1 = x1s != null ? Math.round(Number(x1s) * pxPerPt) : w - 1;
const sc = sys.sysCount || staffRows.length;
console.log(`strana ${pageNo} (PDF) sys ${sysIdx}: ${sc} osnov, ok=${sys.ok} bars=${sys.bars} lines=${JSON.stringify(sys.lines)}`);
console.log(`open=${sys.opening} close=${sys.closing} staffLeft=${sys.staffLeft} staffRight=${sys.staffRight}`);
console.log('cands=' + JSON.stringify(sys.cands));
console.log('osnovy(pt): ' + JSON.stringify(staffRows));
console.log('x(b) | cov v osnovách (%) | #st>=90 #st>=78 #st>=60 | mezery #>=90');
const stepPx = Math.max(1, Math.round(0.2 * pxPerPt));
for (let xb = x0; xb <= x1; xb += stepPx) {
  const covs = [], gc = [];
  let n90 = 0, n78 = 0, n60 = 0;
  for (const r of staffRows) {
    const yT = Math.round(r[0] * pxPerPt), yB = Math.round(r[1] * pxPerPt);
    let ink = 0;
    for (let y = yT; y <= yB; y++) ink += mask[y * w + xb];
    const c = ink / Math.max(1, yB - yT);
    covs.push(Math.round(c * 100));
    if (c >= 0.9) n90++; if (c >= 0.78) n78++; if (c >= 0.6) n60++;
  }
  for (let i = 0; i < staffRows.length - 1; i++) {
    const y0 = Math.round(staffRows[i][1] * pxPerPt) + 2, y1 = Math.round(staffRows[i + 1][0] * pxPerPt) - 2;
    if (y1 <= y0) { gc.push(-1); continue; }
    let ink = 0;
    for (let y = y0; y <= y1; y++) ink += mask[y * w + xb];
    gc.push(Math.round((ink / (y1 - y0 + 1)) * 100));
  }
  const nG = gc.filter(v => v >= 90).length;
  const interesting = n60 > 0 || nG > 0 || Math.max(...covs) >= 25;
  if (interesting) {
    console.log(`${(xb / pxPerPt).toFixed(1)} | ${covs.join(' ')} | ${n90} ${n78} ${n60} | ${gc.join(' ')} (${nG})`);
  }
}
