// Vypíše osnovy a systémy (jen data, bez detekce) do JSON pro offline oracle.
// node scripts/diag-rows-json.mjs <pdf> <strana,...> <out.json>
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import fs from 'node:fs';

globalThis.document = { createElement: () => createCanvas(1, 1) };
globalThis.window = globalThis;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
const { detectPageSystems } = await import('../src/barLines.js');

const [, , file, pagesStr, out] = process.argv;
const pages = pagesStr.split(',').map(Number);
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data, useSystemFonts: true }).promise;
const PPT = 5, MAX_PX = 12e6;
const res = {};
for (const n of pages) {
  const page = await doc.getPage(n);
  const base = page.getViewport({ scale: 1 });
  let scale = PPT;
  if (base.width * base.height * scale * scale > MAX_PX) scale = Math.sqrt(MAX_PX / (base.width * base.height));
  const vp = page.getViewport({ scale });
  const cv = createCanvas(Math.round(vp.width), Math.round(vp.height));
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height);
  await page.render({ canvasContext: ctx, viewport: vp }).promise;
  const d = detectPageSystems(cv, cv.width / base.width, {});
  res[n] = {
    systems: d.systems.map((s) => ({
      rows: d.rowsPt.slice(s.sysA, s.sysB + 1),
      lines: s.lines, opening: s.opening, closing: s.closing, bars: s.bars,
      staffLeft: s.staffLeft, staffRight: s.staffRight,
    })),
  };
}
fs.writeFileSync(out, JSON.stringify(res));
console.log('ok ' + out);
