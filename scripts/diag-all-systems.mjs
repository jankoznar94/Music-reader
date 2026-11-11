// Dávkový přehled systémů po CELÉ skladbě — jen čte.
// node scripts/diag-all-systems.mjs <pdf> [maxStran]
// Vypíše pro každou stránku: [počet osnov v jednotlivých systémech] a počty čar.
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import fs from 'node:fs';

globalThis.document = { createElement: () => createCanvas(1, 1) };
globalThis.window = globalThis;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);

const { detectPageSystems } = await import('../src/barLines.js');

const [, , file, maxStr] = process.argv;
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data, useSystemFonts: true }).promise;
const last = Math.min(doc.numPages, Number(maxStr || doc.numPages));
const PPT = 5, MAX_PX = 12e6;

const rows = [];
for (let n = 1; n <= last; n++) {
  const page = await doc.getPage(n);
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
  const staffs = (d.systems || []).map((s) => s.staves);
  const barsum = (d.systems || []).map((s) => s.bars + 1);
  const uniq = [...new Set(staffs)];
  rows.push({ page: n, staves: d.staves, staffs, barsum, uniform: uniq.length === 1 });
  console.log(`${String(n).padStart(2)} staves=${String(d.staves).padStart(2)} systems=${JSON.stringify(staffs)} bars=${JSON.stringify(barsum)}${uniq.length > 1 ? '  <<< NEUNIFORMNI' : ''}`);
}
const bad = rows.filter((r) => !r.uniform);
console.log(`--- stran ${rows.length}, neuniformnich ${bad.length}: ${bad.map((r) => r.page).join(',')}`);
